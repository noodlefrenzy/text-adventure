"""
ai_player.py

PURPOSE: LLM-based player that can play text adventures autonomously.
DEPENDENCIES: LLM client, game engine

ARCHITECTURE NOTES:
The AI player maintains a play history and uses the LLM to decide
what commands to issue. It aims to explore and solve the game.
Includes OpenTelemetry tracing for observability.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from text_adventure.engine.engine import GameEngine
from text_adventure.llm.client import LLMClient, LLMMessage, LLMRequest
from text_adventure.models.game import Game
from text_adventure.observability import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


AI_PLAYER_SYSTEM_PROMPT = """You are an expert text adventure game player. You are playing a classic text adventure game in the style of Zork or similar Infocom games.

Your goal is to explore the game world, solve puzzles, and achieve the win condition.

CRITICAL RULES:
- NEVER repeat the same command twice in a row
- NEVER keep checking INVENTORY or using LOOK repeatedly - once is enough per room
- If a command fails or does nothing useful, try something DIFFERENT
- If you're stuck, explore a NEW direction or try a NEW object
- EXAMINE objects you haven't examined yet for clues
- Progress means: visiting new rooms, taking new items, or solving puzzles

Strategy tips:
- When entering a new room, LOOK once, then EXAMINE interesting objects
- Pick up items that seem useful (TAKE/GET)
- Check INVENTORY only when you need to remember what you have
- Try all exits from a room before giving up
- READ any books, notes, or signs for hints
- If a door is locked, search other rooms for a key
- Use items WITH other items when appropriate (UNLOCK DOOR WITH KEY)
- TALK to characters you meet - they may give hints

Commands you can use:
- Movement: NORTH, SOUTH, EAST, WEST, UP, DOWN (or N, S, E, W, U, D)
- Looking: LOOK, EXAMINE <object>
- Objects: TAKE <object>, DROP <object>, PUT <object> IN <container>
- Containers: OPEN <object>, CLOSE <object>
- Reading: READ <object>
- Locking: UNLOCK <object> WITH <key>, LOCK <object> WITH <key>
- Interaction: TALK TO <character>, SHOW <object> TO <character>
- Meta: INVENTORY (or I)

Respond with ONLY a single command, nothing else. No explanation, no commentary, just the command.

Examples of valid responses:
NORTH
EXAMINE LAMP
TAKE BRASS KEY
UNLOCK DOOR WITH KEY
TALK TO GUARD"""


@dataclass
class PlaySession:
    """Tracks the state of an AI play session."""

    turns: int = 0
    commands_issued: list[str] = field(default_factory=list)
    responses_received: list[str] = field(default_factory=list)
    rooms_visited: set[str] = field(default_factory=set)
    items_collected: list[str] = field(default_factory=list)
    won: bool = False
    gave_up: bool = False
    stuck_count: float = 0  # Consecutive turns without progress (float for partial increments)
    failed_commands: list[str] = field(default_factory=list)  # Commands that didn't work
    examined_objects: set[str] = field(default_factory=set)  # Objects we've examined
    recent_commands: list[str] = field(default_factory=list)  # Last N commands for loop detection

    def is_repeating(self, command: str, window: int = 5) -> bool:
        """Check if command was recently issued."""
        recent = self.recent_commands[-window:] if self.recent_commands else []
        return command.upper() in [c.upper() for c in recent]

    def count_recent(self, command: str, window: int = 10) -> int:
        """Count how many times a command appeared recently."""
        recent = self.recent_commands[-window:] if self.recent_commands else []
        return sum(1 for c in recent if c.upper() == command.upper())


class AIPlayer:
    """
    An AI-powered player that can play text adventure games autonomously.

    Uses an LLM to decide what commands to issue based on game output.
    """

    def __init__(
        self,
        client: LLMClient,
        max_stuck_turns: int = 10,
        temperature: float = 0.3,
    ):
        """
        Initialize the AI player.

        Args:
            client: The LLM client to use for decision making.
            max_stuck_turns: Give up after this many turns without progress.
            temperature: Creativity level for command generation.
        """
        self._client = client
        self._max_stuck_turns = max_stuck_turns
        self._temperature = temperature

    async def play(
        self,
        game: Game,
        max_turns: int = 100,
        on_turn: Any | None = None,  # Callback: (turn, command, result) -> None
    ) -> PlaySession:
        """
        Play through a game autonomously.

        Args:
            game: The game to play.
            max_turns: Maximum number of turns before giving up.
            on_turn: Optional callback called after each turn.

        Returns:
            PlaySession with the results of the play-through.
        """
        with tracer.start_as_current_span("ai.play") as play_span:
            play_span.set_attribute("ai.game_title", game.metadata.title)
            play_span.set_attribute("ai.max_turns", max_turns)
            play_span.set_attribute("ai.temperature", self._temperature)
            play_span.add_event("session_started")

            engine = GameEngine(game)
            session = PlaySession()

            # Get initial room description
            initial_description = engine.describe_current_room()
            session.rooms_visited.add(engine.state.current_room)
            session.responses_received.append(initial_description)

            logger.info(f"Starting AI play of '{game.metadata.title}'")

            while session.turns < max_turns:
                # Check if we're stuck
                if session.stuck_count >= self._max_stuck_turns:
                    logger.warning("AI player is stuck, giving up")
                    session.gave_up = True
                    play_span.add_event("player_stuck")
                    break

                # Each turn gets its own span
                with tracer.start_as_current_span("ai.turn") as turn_span:
                    turn_span.set_attribute("ai.turn_number", session.turns + 1)
                    turn_span.set_attribute("ai.current_room", engine.state.current_room)

                    # Get the next command from the LLM (creates child span)
                    command = await self._get_next_command(game, session)
                    command = command.strip().upper()

                    turn_span.set_attribute("ai.command", command)
                    logger.debug(f"Turn {session.turns + 1}: {command}")

                    # Execute the command
                    result = engine.process_input(command)

                    # Track the turn
                    session.turns += 1
                    session.commands_issued.append(command)
                    session.responses_received.append(result.message)
                    session.recent_commands.append(command)

                    # Track examined objects
                    if command.startswith("EXAMINE ") or command.startswith("X "):
                        obj_name = command.split(" ", 1)[1] if " " in command else ""
                        if obj_name:
                            session.examined_objects.add(obj_name.lower())

                    # Track failed commands
                    if result.error:
                        session.failed_commands.append(command)

                    # Track progress
                    old_room_count = len(session.rooms_visited)
                    old_inventory_count = len(session.items_collected)

                    session.rooms_visited.add(engine.state.current_room)
                    for item in engine.state.inventory:
                        if item not in session.items_collected:
                            session.items_collected.append(item)

                    # Check for progress
                    made_progress = (
                        len(session.rooms_visited) > old_room_count
                        or len(session.items_collected) > old_inventory_count
                    )

                    # Detect repetitive behavior (even if commands "succeed")
                    is_repetitive = session.count_recent(command, window=6) >= 3

                    turn_span.set_attribute("ai.success", not result.error)
                    turn_span.set_attribute("ai.made_progress", made_progress)
                    turn_span.set_attribute("ai.is_repetitive", is_repetitive)

                    if made_progress:
                        session.stuck_count = 0
                    elif result.error or is_repetitive:
                        session.stuck_count += 1
                    else:
                        # Successful but no progress - slightly increment
                        session.stuck_count += 0.5

                    # Callback
                    if on_turn:
                        on_turn(session.turns, command, result)

                    # Check for game over
                    if result.game_over:
                        session.won = result.won
                        turn_span.set_attribute("ai.game_over", True)
                        turn_span.set_attribute("ai.won", result.won)
                        logger.info(f"Game over! Won: {result.won}")
                        break

            # Set final session attributes
            outcome = "won" if session.won else ("stuck" if session.gave_up else "timeout")
            play_span.set_attribute("ai.total_turns", session.turns)
            play_span.set_attribute("ai.rooms_visited", len(session.rooms_visited))
            play_span.set_attribute("ai.items_collected", len(session.items_collected))
            play_span.set_attribute("ai.outcome", outcome)
            play_span.add_event("session_ended", {"outcome": outcome})

            return session

    async def _get_next_command(
        self,
        game: Game,
        session: PlaySession,
    ) -> str:
        """
        Get the next command from the LLM.

        Args:
            game: The current game.
            session: The current play session.

        Returns:
            The command to execute.
        """
        # Build context for the LLM
        context = self._build_context(game, session)

        request = LLMRequest(
            messages=[LLMMessage(role="user", content=context)],
            system=AI_PLAYER_SYSTEM_PROMPT,
            max_tokens=50,  # Commands are short
            temperature=self._temperature,
        )

        response = await self._client.complete(request)
        command = response.content.strip()

        # Clean up the response - sometimes LLMs add extra text
        # Take only the first line
        if "\n" in command:
            command = command.split("\n")[0].strip()

        # Remove quotes if present
        command = command.strip("\"'")

        return command

    def _build_context(self, game: Game, session: PlaySession) -> str:
        """
        Build the context string for the LLM.

        Args:
            game: The current game.
            session: The current play session.

        Returns:
            Context string describing the current situation.
        """
        parts = [
            f"Game: {game.metadata.title}",
            f"Objective: {self._describe_objective(game)}",
            f"Progress: {len(session.rooms_visited)} rooms visited, {len(session.items_collected)} items collected",
            "",
        ]

        # Warn about repetitive commands
        if session.recent_commands:
            recent_5 = session.recent_commands[-5:]
            repeated = [c for c in set(recent_5) if recent_5.count(c) >= 2]
            if repeated:
                parts.append(f"WARNING: You've been repeating these commands: {', '.join(repeated)}")
                parts.append("Try something DIFFERENT!")
                parts.append("")

        # Show what has failed recently
        recent_failures = session.failed_commands[-3:] if session.failed_commands else []
        if recent_failures:
            parts.append(f"Commands that didn't work: {', '.join(recent_failures)}")
            parts.append("")

        parts.append("Recent history (last 5 turns):")

        # Show recent history
        start_idx = max(0, len(session.commands_issued) - 5)
        for i in range(start_idx, len(session.commands_issued)):
            parts.append(f"> {session.commands_issued[i]}")
            parts.append(session.responses_received[i + 1])  # +1 because first response is initial
            parts.append("")

        # Show current situation (last response)
        if session.responses_received:
            parts.append("Current situation:")
            parts.append(session.responses_received[-1])
            parts.append("")

        # Suggest what to try
        if session.stuck_count >= 3:
            parts.append("HINT: You seem stuck. Try:")
            parts.append("- Exploring a direction you haven't tried")
            parts.append("- Examining an object you haven't looked at")
            parts.append("- Using an item from your inventory")
            parts.append("")

        parts.append("What is your next command? (Remember: don't repeat recent commands)")

        return "\n".join(parts)

    def _describe_objective(self, game: Game) -> str:
        """Describe the win condition in human terms."""
        wc = game.win_condition
        if wc.type == "reach_room":
            room = game.get_room(wc.room or "")
            room_name = room.name if room else wc.room
            return f"Reach the {room_name}"
        elif wc.type == "have_object":
            obj = game.get_object(wc.object or "")
            obj_name = obj.name if obj else wc.object
            return f"Obtain the {obj_name}"
        elif wc.type == "flag_set":
            return f"Complete the objective ({wc.flag})"
        else:
            return "Explore and complete the game"


async def ai_play_game(
    client: LLMClient,
    game: Game,
    max_turns: int = 100,
    on_turn: Any | None = None,
) -> PlaySession:
    """
    Convenience function to have an AI play a game.

    Args:
        client: LLM client to use.
        game: The game to play.
        max_turns: Maximum turns.
        on_turn: Optional callback for each turn.

    Returns:
        PlaySession with results.
    """
    player = AIPlayer(client)
    return await player.play(game, max_turns, on_turn)
