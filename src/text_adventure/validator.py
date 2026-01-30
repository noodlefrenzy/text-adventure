"""
validator.py

PURPOSE: Validate game definitions for common issues.
DEPENDENCIES: models

ARCHITECTURE NOTES:
The validator checks games for issues that would cause runtime errors:
- Unknown verbs in custom actions
- Invalid condition syntax
- Missing object references (reveals_object, moves_player, key_object)
- Revealed objects that aren't hidden

Running validation at game load time catches these issues early.
"""

import re
from dataclasses import dataclass
from enum import Enum, auto

from text_adventure.models.command import VERB_ALIASES
from text_adventure.models.game import Game, GameObject, ObjectAction, WinCondition


class ValidationSeverity(Enum):
    """Severity level for validation issues."""

    ERROR = auto()  # Will cause runtime failure
    WARNING = auto()  # May cause unexpected behavior
    INFO = auto()  # Suggestion for improvement


@dataclass
class ValidationIssue:
    """A single validation issue found in a game."""

    severity: ValidationSeverity
    message: str
    location: str  # e.g., "object:brass_key", "room:entrance"

    def __str__(self) -> str:
        return f"[{self.severity.name}] {self.location}: {self.message}"


class GameValidator:
    """
    Validates game definitions for common issues.

    Usage:
        validator = GameValidator(game)
        issues = validator.validate()
        for issue in issues:
            print(issue)
    """

    # Built-in verbs that don't need to be defined in game.verbs
    BUILTIN_VERBS = set(VERB_ALIASES.keys())

    # Additional action verbs that handlers recognize
    BUILTIN_ACTION_VERBS = {
        "examine",
        "take",
        "drop",
        "open",
        "close",
        "lock",
        "unlock",
        "read",
        "use",
        "put",
        "give",
        "talk",
        "show",
        "insert",
        "enter",
    }

    # Valid condition patterns
    CONDITION_PATTERNS = [
        r"^flags\.\w+$",  # flags.flag_name
        r"^\w+\.\w+$",  # object.attribute
        r"^inventory\.includes\(['\"][^'\"]+['\"]\)$",  # inventory.includes('x')
        r"^!\s*",  # negation prefix
    ]

    def __init__(self, game: Game):
        self.game = game
        self.issues: list[ValidationIssue] = []

        # Build lookup tables
        self.room_ids = {room.id for room in game.rooms}
        self.object_ids = {obj.id for obj in game.objects}
        self.custom_verbs = {v.verb.lower() for v in game.verbs}
        self.custom_verb_aliases = {
            alias.lower() for v in game.verbs for alias in v.aliases
        }

    def validate(self) -> list[ValidationIssue]:
        """
        Run all validation checks.

        Returns:
            List of ValidationIssue objects, sorted by severity.
        """
        self.issues = []

        self._validate_objects()
        self._validate_rooms()
        self._validate_initial_state()
        self._validate_win_condition()

        # Sort by severity (errors first)
        self.issues.sort(key=lambda i: i.severity.value)
        return self.issues

    def _validate_objects(self) -> None:
        """Validate all game objects."""
        revealed_objects: set[str] = set()

        # First pass: collect revealed objects
        for obj in self.game.objects:
            for action in obj.actions.values():
                if isinstance(action, ObjectAction) and action.reveals_object:
                    revealed_objects.add(action.reveals_object)

        # Second pass: validate each object
        for obj in self.game.objects:
            self._validate_object(obj, revealed_objects)

    def _validate_object(
        self, obj: GameObject, revealed_objects: set[str]
    ) -> None:
        """Validate a single game object."""
        location = f"object:{obj.id}"

        # Check if revealed objects are hidden
        if obj.id in revealed_objects and not obj.hidden:
            self.issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message="Object is revealed by an action but hidden=False. "
                    "It will be visible before being revealed.",
                    location=location,
                )
            )

        # Check key_object reference
        if obj.key_object and obj.key_object not in self.object_ids:
            self.issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"key_object '{obj.key_object}' does not exist.",
                    location=location,
                )
            )

        # Validate actions
        for action_name, action in obj.actions.items():
            self._validate_action(obj.id, action_name, action)

    def _validate_action(
        self,
        obj_id: str,
        action_name: str,
        action: ObjectAction | str,
    ) -> None:
        """Validate a custom action."""
        location = f"object:{obj_id}/action:{action_name}"

        # Check verb is recognized
        verb = action_name.split(":")[0].lower()
        if not self._is_known_verb(verb):
            self.issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.WARNING,
                    message=f"Verb '{verb}' is not a built-in verb and not defined "
                    f"in game.verbs. Players won't be able to trigger this action.",
                    location=location,
                )
            )

        # String actions are always valid
        if isinstance(action, str):
            return

        # Validate condition syntax
        if action.condition:
            self._validate_condition(action.condition, location)

        # Validate reveals_object reference
        if action.reveals_object and action.reveals_object not in self.object_ids:
            self.issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"reveals_object '{action.reveals_object}' does not exist.",
                    location=location,
                )
            )

        # Validate moves_player reference
        if action.moves_player and action.moves_player not in self.room_ids:
            self.issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"moves_player '{action.moves_player}' room does not exist.",
                    location=location,
                )
            )

        # Validate state_changes references
        for key in action.state_changes:
            if "." in key:
                obj_ref, _ = key.split(".", 1)
                if obj_ref != "flags" and obj_ref not in self.object_ids:
                    self.issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            message=f"state_change '{key}' references unknown object '{obj_ref}'.",
                            location=location,
                        )
                    )

    def _validate_condition(self, condition: str, location: str) -> None:
        """Validate a condition string."""
        # Split compound conditions
        parts = re.split(r"\s*(?:&&|\|\|)\s*", condition)

        for part in parts:
            part = part.strip()
            if not part:
                continue

            # Remove negation prefix for checking
            check_part = part.lstrip("!")

            # Check against known patterns
            valid = False
            for pattern in self.CONDITION_PATTERNS:
                if re.match(pattern, check_part):
                    valid = True
                    break

            if not valid:
                self.issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.WARNING,
                        message=f"Condition '{part}' may not be supported. "
                        f"Use flags.x, object.attr, or inventory.includes('x').",
                        location=location,
                    )
                )

    def _validate_rooms(self) -> None:
        """Validate all rooms."""
        for room in self.game.rooms:
            location = f"room:{room.id}"

            # Check exit targets
            for direction, exit_info in room.exits.items():
                if isinstance(exit_info, str):
                    target = exit_info
                else:
                    target = exit_info.target
                    if exit_info.unlock_object and exit_info.unlock_object not in self.object_ids:
                        self.issues.append(
                            ValidationIssue(
                                severity=ValidationSeverity.ERROR,
                                message=f"Exit {direction} unlock_object '{exit_info.unlock_object}' does not exist.",
                                location=location,
                            )
                        )

                if target not in self.room_ids:
                    self.issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.ERROR,
                            message=f"Exit {direction} target '{target}' does not exist.",
                            location=location,
                        )
                    )

            # Check object references
            for obj_id in room.objects:
                if obj_id not in self.object_ids:
                    self.issues.append(
                        ValidationIssue(
                            severity=ValidationSeverity.WARNING,
                            message=f"Room references non-existent object '{obj_id}'.",
                            location=location,
                        )
                    )

    def _validate_initial_state(self) -> None:
        """Validate initial game state."""
        location = "initial_state"

        if self.game.initial_state.current_room not in self.room_ids:
            self.issues.append(
                ValidationIssue(
                    severity=ValidationSeverity.ERROR,
                    message=f"Starting room '{self.game.initial_state.current_room}' does not exist.",
                    location=location,
                )
            )

        for obj_id in self.game.initial_state.inventory:
            if obj_id not in self.object_ids:
                self.issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        message=f"Starting inventory item '{obj_id}' does not exist.",
                        location=location,
                    )
                )

    def _validate_win_condition(self) -> None:
        """Validate win condition."""
        self._validate_win_condition_recursive(
            self.game.win_condition, "win_condition"
        )

    def _validate_win_condition_recursive(
        self, condition: WinCondition, location: str
    ) -> None:
        """Recursively validate win conditions."""
        if condition.type == "reach_room" and condition.room:
            if condition.room not in self.room_ids:
                self.issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        message=f"Win condition room '{condition.room}' does not exist.",
                        location=location,
                    )
                )
        elif condition.type == "have_object" and condition.object:
            if condition.object not in self.object_ids:
                self.issues.append(
                    ValidationIssue(
                        severity=ValidationSeverity.ERROR,
                        message=f"Win condition object '{condition.object}' does not exist.",
                        location=location,
                    )
                )
        elif condition.type in ("all_of", "any_of") and condition.conditions:
            for i, sub in enumerate(condition.conditions):
                self._validate_win_condition_recursive(
                    sub, f"{location}/conditions[{i}]"
                )

    def _is_known_verb(self, verb: str) -> bool:
        """Check if a verb is recognized by the engine."""
        return (
            verb in self.BUILTIN_VERBS
            or verb in self.BUILTIN_ACTION_VERBS
            or verb in self.custom_verbs
            or verb in self.custom_verb_aliases
        )


def validate_game(game: Game) -> list[ValidationIssue]:
    """
    Convenience function to validate a game.

    Args:
        game: The game to validate.

    Returns:
        List of validation issues (empty if game is valid).
    """
    validator = GameValidator(game)
    return validator.validate()
