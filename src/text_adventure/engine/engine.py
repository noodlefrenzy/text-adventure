"""
engine.py

PURPOSE: Core game engine that executes commands and manages game state.
DEPENDENCIES: models, parser

ARCHITECTURE NOTES:
The GameEngine is the central coordinator:
- Loads a Game definition
- Maintains GameState
- Executes Commands by delegating to action handlers
- Checks win/lose conditions after each turn
- Returns narrative text for display

The engine is the "server" - it is authoritative over game state.
"""

from dataclasses import dataclass

from text_adventure.engine.actions import execute_action
from text_adventure.models.command import Verb
from text_adventure.models.game import Exit, Game, Room, WinCondition
from text_adventure.models.state import GameState
from text_adventure.parser.game_parser import GameParser
from text_adventure.parser.parser import ParseResult
from text_adventure.parser.resolver import ObjectResolver


@dataclass
class TurnResult:
    """Result of processing a player turn."""

    message: str  # Narrative text to display
    game_over: bool = False
    won: bool = False
    error: bool = False  # True if command failed to execute


class GameEngine:
    """
    The core game engine.

    Manages game state and executes player commands.
    """

    def __init__(self, game: Game, state: GameState | None = None):
        """
        Initialize the engine with a game definition.

        Args:
            game: The game definition to play
            state: Optional existing state (for loading saves)
        """
        self.game = game
        self.state = state or GameState.from_game(game)
        self.resolver = ObjectResolver(game, self.state)
        self.parser = GameParser(game)  # Parser with custom verb support

    def describe_current_room(self, verbose: bool = False) -> str:  # noqa: ARG002
        """
        Get the description of the current room.

        Args:
            verbose: If True, always show full description.
                     If False, show brief description on revisits.

        Returns:
            Room description text
        """
        room_id = self.state.current_room
        room = self.game.get_room(room_id)
        if not room:
            return "You are nowhere."

        room_state = self.state.rooms.get(room_id)
        first_visit = room_state and not room_state.visited

        # Mark room as visited
        if room_state:
            room_state.visited = True

        lines: list[str] = []

        # Room name
        lines.append(f"**{room.name}**")
        lines.append("")

        # Description
        if first_visit and room.first_visit_description:
            lines.append(room.first_visit_description)
        else:
            lines.append(room.description)

        # List visible objects
        visible_objects = self.state.get_visible_objects_at(room_id, self.game)
        if visible_objects:
            lines.append("")
            for obj_id in visible_objects:
                obj = self.game.get_object(obj_id)
                if obj and not obj.scenery:
                    lines.append(f"There is a {obj.name} here.")

        # List exits
        exits = self._describe_exits(room)
        if exits:
            lines.append("")
            lines.append(exits)

        return "\n".join(lines)

    def _describe_exits(self, room: "Room") -> str:
        """Describe available exits from a room."""
        visible_exits = []
        for direction, exit_info in room.exits.items():
            # Check if exit is hidden
            if isinstance(exit_info, Exit) and exit_info.hidden:
                continue
            visible_exits.append(direction)

        if not visible_exits:
            return "There are no obvious exits."

        if len(visible_exits) == 1:
            return f"There is an exit to the {visible_exits[0]}."

        exit_str = ", ".join(visible_exits[:-1]) + f" and {visible_exits[-1]}"
        return f"There are exits to the {exit_str}."

    def process_input(self, user_input: str) -> TurnResult:
        """
        Process a line of player input.

        This is the main entry point for the game loop.

        Args:
            user_input: Raw text from the player

        Returns:
            TurnResult with message and game state changes
        """
        # Check if game is already over
        if self.state.game_over:
            if self.state.won:
                return TurnResult(
                    message="The game is over. You won!",
                    game_over=True,
                    won=True,
                )
            return TurnResult(
                message=self.state.death_message or "The game is over.",
                game_over=True,
                won=False,
            )

        # Parse the input (uses GameParser with custom verb support)
        parse_result: ParseResult = self.parser.parse(user_input)
        if not parse_result.success:
            return TurnResult(
                message=parse_result.error.message if parse_result.error else "I don't understand.",
                error=True,
            )

        command = parse_result.command
        assert command is not None

        # Handle meta commands that don't consume a turn
        if command.verb == Verb.QUIT:
            self.state.end_game(won=False)
            return TurnResult(
                message="Thanks for playing!",
                game_over=True,
                won=False,
            )

        if command.verb == Verb.HELP:
            return TurnResult(message=self._get_help_text())

        if command.verb == Verb.SAVE:
            return TurnResult(message="Save functionality not yet implemented.")

        if command.verb == Verb.LOAD:
            return TurnResult(message="Load functionality not yet implemented.")

        # Handle LOOK (describe room)
        if command.verb == Verb.LOOK and not command.direct_object:
            return TurnResult(message=self.describe_current_room(verbose=True))

        # Handle INVENTORY
        if command.verb == Verb.INVENTORY:
            return TurnResult(message=self._describe_inventory())

        # Handle WAIT
        if command.verb == Verb.WAIT:
            self.state.increment_turns()
            return TurnResult(message="Time passes.")

        # Handle ENTER <object> - check for custom "enter" action before treating as movement
        if command.verb == Verb.IN and command.direct_object:
            resolved = self.resolver.resolve(command)
            if resolved.success and resolved.resolved and resolved.resolved.direct_object_id:
                obj = self.game.get_object(resolved.resolved.direct_object_id)
                if obj and "enter" in obj.actions:
                    from text_adventure.engine.actions import _execute_custom_action

                    action_result = _execute_custom_action(obj, "enter", self.game, self.state)
                    if action_result:
                        self.state.increment_turns()
                        # Check win condition after action (may have moved player)
                        win_msg = self._check_win_condition()
                        if win_msg:
                            return TurnResult(
                                message=action_result.message + "\n\n" + win_msg,
                                game_over=True,
                                won=True,
                            )
                        return TurnResult(
                            message=action_result.message,
                            error=not action_result.success,
                        )

        # Handle movement
        if command.verb in (
            Verb.NORTH,
            Verb.SOUTH,
            Verb.EAST,
            Verb.WEST,
            Verb.UP,
            Verb.DOWN,
            Verb.IN,
            Verb.OUT,
        ):
            result = self._handle_movement(command.verb)
            if not result.error:
                self.state.increment_turns()
                # Check win condition after movement
                win_msg = self._check_win_condition()
                if win_msg:
                    result.message += "\n\n" + win_msg
                    result.game_over = True
                    result.won = True
            return result

        # Resolve object references for other commands
        resolved = self.resolver.resolve(command)
        if not resolved.success:
            return TurnResult(
                message=resolved.error_message or "I don't understand.",
                error=True,
            )

        assert resolved.resolved is not None

        # Execute the action
        action_result = execute_action(
            resolved.resolved,
            self.game,
            self.state,
        )

        if action_result.success:
            self.state.increment_turns()
            # Check win condition
            win_msg = self._check_win_condition()
            if win_msg:
                action_result.message += "\n\n" + win_msg
                return TurnResult(
                    message=action_result.message,
                    game_over=True,
                    won=True,
                )

        return TurnResult(
            message=action_result.message,
            error=not action_result.success,
        )

    def _handle_movement(self, direction_verb: Verb) -> TurnResult:
        """Handle movement in a direction."""
        direction_map = {
            Verb.NORTH: "north",
            Verb.SOUTH: "south",
            Verb.EAST: "east",
            Verb.WEST: "west",
            Verb.UP: "up",
            Verb.DOWN: "down",
            Verb.IN: "in",
            Verb.OUT: "out",
        }
        direction = direction_map.get(direction_verb, "")

        room = self.game.get_room(self.state.current_room)
        if not room:
            return TurnResult(message="You are nowhere.", error=True)

        if direction not in room.exits:
            return TurnResult(
                message=f"You can't go {direction} from here.",
                error=True,
            )

        exit_info = room.exits[direction]

        # Handle simple string exit
        if isinstance(exit_info, str):
            target_room = exit_info
        else:
            # Exit object with potential lock
            if exit_info.locked:
                return TurnResult(
                    message=exit_info.lock_message,
                    error=True,
                )
            target_room = exit_info.target

        # Move to new room
        self.state.current_room = target_room
        return TurnResult(message=self.describe_current_room())

    def _describe_inventory(self) -> str:
        """Describe the player's inventory."""
        if not self.state.inventory:
            return "You are empty-handed."

        lines = ["You are carrying:"]
        for obj_id in self.state.inventory:
            obj = self.game.get_object(obj_id)
            if obj:
                lines.append(f"  - {obj.name}")

        return "\n".join(lines)

    def _check_win_condition(self) -> str | None:
        """
        Check if the win condition is met.

        Returns:
            Win message if won, None otherwise
        """
        if self._evaluate_win_condition(self.game.win_condition):
            self.state.end_game(won=True)
            return self.game.win_condition.win_message
        return None

    def _evaluate_win_condition(self, condition: WinCondition) -> bool:
        """Recursively evaluate a win condition."""
        match condition.type:
            case "reach_room":
                return self.state.current_room == condition.room
            case "have_object":
                return condition.object in self.state.inventory if condition.object else False
            case "flag_set":
                return bool(self.state.get_flag(condition.flag)) if condition.flag else False
            case "all_of":
                if not condition.conditions:
                    return False
                return all(self._evaluate_win_condition(c) for c in condition.conditions)
            case "any_of":
                if not condition.conditions:
                    return False
                return any(self._evaluate_win_condition(c) for c in condition.conditions)
        return False

    def _get_help_text(self) -> str:
        """Return help text for the player."""
        return """**Available Commands**

Movement:
  NORTH (N), SOUTH (S), EAST (E), WEST (W)
  UP (U), DOWN (D), IN, OUT

Objects:
  TAKE/GET <object> - Pick up an object
  DROP <object> - Drop an object
  EXAMINE/X <object> - Look at something closely
  OPEN/CLOSE <object> - Open or close something
  PUT <object> IN/ON <container> - Put something somewhere
  UNLOCK <door> WITH <key> - Unlock something

Information:
  LOOK (L) - Describe your surroundings
  INVENTORY (I) - List what you're carrying
  HELP - Show this message

Game:
  QUIT (Q) - End the game
  SAVE - Save your progress
  LOAD - Load a saved game"""
