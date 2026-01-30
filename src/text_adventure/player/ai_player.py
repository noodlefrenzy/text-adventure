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


AI_PLAYER_SYSTEM_PROMPT = """You are an expert text adventure game player. You are playing a classic text adventure game.

Your goal is to explore the game world, solve puzzles, and achieve the win condition.

Important: When you enter a room, you automatically see its description. Only use LOOK if you think the room state may have changed (e.g., after manipulating objects, unlocking something, or if time has passed). Don't LOOK immediately after entering a room.

You must respond with valid JSON containing:
1. "command": The command to execute (e.g., "NORTH", "EXAMINE LAMP")
2. "knowledge": Your compressed understanding of the game state, including:
   - "map": Rooms you've visited and their exits (e.g., {"entrance": {"north": "hall", "east": "?"}})
   - "current_room": Where you are now
   - "inventory": Items you're carrying
   - "objects_seen": Notable objects and what you learned from them
   - "locked_doors": Doors/containers that are locked and what might open them
   - "clues": Important information you've discovered
   - "plan": Your current strategy or next steps to try
   - "tried_and_failed": Things you attempted that didn't work (to avoid repeating)

Commands you can use:
- Movement: NORTH, SOUTH, EAST, WEST, UP, DOWN (or N, S, E, W, U, D)
- Looking: LOOK, EXAMINE <object>
- Objects: TAKE <object>, DROP <object>, PUT <object> IN <container>
- Containers: OPEN <object>, CLOSE <object>
- Reading: READ <object>
- Locking: UNLOCK <object> WITH <key>, LOCK <object> WITH <key>
- Interaction: TALK TO <character>, SHOW <object> TO <character>
- Meta: INVENTORY (or I)

Example response:
```json
{
  "command": "EXAMINE BRASS KEY",
  "knowledge": {
    "map": {"entrance": {"north": "library"}, "library": {"south": "entrance", "east": "locked"}},
    "current_room": "library",
    "inventory": ["brass key", "note"],
    "objects_seen": {"note": "mentions a secret door behind bookshelf"},
    "locked_doors": {"library east door": "need to find lever?"},
    "clues": ["note mentions secret door", "brass key found in drawer"],
    "plan": "examine the key to see if it has markings, then try the locked door",
    "tried_and_failed": ["push bookshelf (doesn't move)"]
  }
}
```

Keep knowledge compact but informative. Update it each turn based on what you learn."""


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
    stuck_count: float = 0  # Consecutive turns without progress
    ai_knowledge: dict[str, Any] = field(default_factory=dict)  # AI's compressed game state
    # Token usage tracking
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    tokens_per_turn: list[tuple[int, int]] = field(default_factory=list)  # (input, output) per turn

    @property
    def total_tokens(self) -> int:
        """Total tokens used (input + output)."""
        return self.total_input_tokens + self.total_output_tokens

    @property
    def avg_tokens_per_turn(self) -> float:
        """Average tokens per turn."""
        if self.turns == 0:
            return 0
        return self.total_tokens / self.turns


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

                    turn_span.set_attribute("ai.success", not result.error)
                    turn_span.set_attribute("ai.made_progress", made_progress)

                    if made_progress:
                        session.stuck_count = 0
                    elif result.error:
                        session.stuck_count += 1
                    else:
                        # Successful but no tangible progress
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
        import json

        # Build context for the LLM
        context = self._build_context(game, session)

        request = LLMRequest(
            messages=[LLMMessage(role="user", content=context)],
            system=AI_PLAYER_SYSTEM_PROMPT,
            max_tokens=1024,  # Need more tokens for JSON response with knowledge
            temperature=self._temperature,
        )

        response = await self._client.complete(request)
        raw_response = response.content.strip()

        # Track token usage
        session.total_input_tokens += response.input_tokens
        session.total_output_tokens += response.output_tokens
        session.tokens_per_turn.append((response.input_tokens, response.output_tokens))
        logger.debug(
            f"Turn tokens: {response.input_tokens} in, {response.output_tokens} out "
            f"(total: {session.total_tokens})"
        )

        # Try to parse as JSON
        command = ""
        json_str = ""
        try:
            # Handle markdown code blocks (case-insensitive)
            raw_lower = raw_response.lower()
            if "```json" in raw_lower:
                # Find the actual position case-insensitively
                start_idx = raw_lower.find("```json") + 7
                end_idx = raw_response.find("```", start_idx)
                if end_idx > start_idx:
                    json_str = raw_response[start_idx:end_idx].strip()
                else:
                    # No closing ```, take everything after ```json
                    json_str = raw_response[start_idx:].strip()
                logger.debug(f"Extracted JSON from ```json block: {json_str[:100]}...")
            elif "```" in raw_response:
                parts = raw_response.split("```")
                if len(parts) >= 2:
                    json_str = parts[1].strip()
                    # Remove language identifier if present (e.g., "json\n{...")
                    if json_str and not json_str.startswith("{"):
                        newline_idx = json_str.find("\n")
                        if newline_idx > 0:
                            json_str = json_str[newline_idx:].strip()
                logger.debug(f"Extracted JSON from ``` block: {json_str[:100]}...")
            else:
                json_str = raw_response
                logger.debug("No code block, trying raw response as JSON")

            data = json.loads(json_str)

            # Handle dict response with command and knowledge
            if isinstance(data, dict):
                command = data.get("command", "").strip()

                # Store the AI's knowledge state
                if "knowledge" in data:
                    session.ai_knowledge = data["knowledge"]
                    logger.debug(f"AI knowledge updated: {list(session.ai_knowledge.keys())}")
            else:
                # JSON parsed but wasn't a dict (e.g., just a string)
                command = str(data).strip()

        except (json.JSONDecodeError, IndexError, ValueError) as e:
            # Fallback: try to extract command from response
            logger.warning(f"JSON parse failed ({e}), raw response: {raw_response[:200]}")

            # Look for a command-like pattern (all caps word at start of line)
            import re
            command_match = re.search(r'^([A-Z][A-Z\s]+?)(?:\n|$)', raw_response, re.MULTILINE)
            if command_match:
                command = command_match.group(1).strip()
                logger.debug(f"Extracted command via regex: {command}")
            else:
                # Last resort: first line, cleaned up
                command = raw_response.split("\n")[0].strip()
                command = command.strip("\"'`")
                logger.debug(f"Using first line as command: {command}")

        return command.upper() if command else "LOOK"

    def _build_context(self, game: Game, session: PlaySession) -> str:
        """
        Build the context string for the LLM.

        Args:
            game: The current game.
            session: The current play session.

        Returns:
            Context string describing the current situation.
        """
        import json

        parts = [
            f"Game: {game.metadata.title}",
            f"Objective: {self._describe_objective(game)}",
            f"Turn: {session.turns + 1}",
            "",
        ]

        # Include AI's previous knowledge state if available
        if session.ai_knowledge:
            parts.append("Your previous knowledge state:")
            parts.append("```json")
            parts.append(json.dumps(session.ai_knowledge, indent=2))
            parts.append("```")
            parts.append("")

        # Show recent history (last 3 turns to save tokens)
        if session.commands_issued:
            parts.append("Recent actions:")
            start_idx = max(0, len(session.commands_issued) - 3)
            for i in range(start_idx, len(session.commands_issued)):
                parts.append(f"> {session.commands_issued[i]}")
                # Truncate long responses
                response = session.responses_received[i + 1]
                if len(response) > 300:
                    response = response[:300] + "..."
                parts.append(response)
                parts.append("")

        # Show current situation (last response in full)
        if session.responses_received:
            parts.append("Current situation:")
            parts.append(session.responses_received[-1])
            parts.append("")

        parts.append("Respond with JSON containing your command and updated knowledge state.")

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
