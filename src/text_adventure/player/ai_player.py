"""
ai_player.py

PURPOSE: LLM-based player that can play text adventures autonomously.
DEPENDENCIES: LLM client, game engine

ARCHITECTURE NOTES:
The AI player maintains a play history and uses the LLM to decide
what commands to issue. It aims to explore and solve the game.
"""

import logging
from dataclasses import dataclass, field
from typing import Any

from text_adventure.engine.engine import GameEngine
from text_adventure.llm.client import LLMClient, LLMMessage, LLMRequest
from text_adventure.models.game import Game

logger = logging.getLogger(__name__)


AI_PLAYER_SYSTEM_PROMPT = """You are an expert text adventure game player. You are playing a classic text adventure game in the style of Zork or similar Infocom games.

Your goal is to explore the game world, solve puzzles, and achieve the win condition.

Strategy tips:
- Use LOOK to understand your surroundings
- EXAMINE interesting objects for clues
- Pick up items that seem useful (TAKE/GET)
- Check your INVENTORY regularly
- Try obvious directions first (NORTH, SOUTH, EAST, WEST)
- READ any books, notes, or signs for hints
- If a door is locked, look for a key
- Use items WITH other items when appropriate (UNLOCK DOOR WITH KEY)

Commands you can use:
- Movement: NORTH, SOUTH, EAST, WEST, UP, DOWN (or N, S, E, W, U, D)
- Looking: LOOK, EXAMINE <object>
- Objects: TAKE <object>, DROP <object>, PUT <object> IN <container>
- Containers: OPEN <object>, CLOSE <object>
- Reading: READ <object>
- Locking: UNLOCK <object> WITH <key>, LOCK <object> WITH <key>
- Meta: INVENTORY (or I), HELP

Respond with ONLY a single command, nothing else. No explanation, no commentary, just the command.

Examples of valid responses:
NORTH
EXAMINE LAMP
TAKE BRASS KEY
UNLOCK DOOR WITH KEY
PUT GEM IN BOX"""


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
    stuck_count: int = 0  # Consecutive turns without progress


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
                break

            # Get the next command from the LLM
            command = await self._get_next_command(game, session)
            command = command.strip().upper()

            logger.debug(f"Turn {session.turns + 1}: {command}")

            # Execute the command
            result = engine.process_input(command)

            # Track the turn
            session.turns += 1
            session.commands_issued.append(command)
            session.responses_received.append(result.message)

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

            if made_progress or not result.error:
                session.stuck_count = 0
            else:
                session.stuck_count += 1

            # Callback
            if on_turn:
                on_turn(session.turns, command, result)

            # Check for game over
            if result.game_over:
                session.won = result.won
                logger.info(f"Game over! Won: {result.won}")
                break

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
            "",
            "Recent history (last 5 turns):",
        ]

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

        parts.append("What is your next command?")

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
