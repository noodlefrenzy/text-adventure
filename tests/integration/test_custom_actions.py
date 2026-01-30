"""
TEST DOC: Custom Action Integration Tests

WHAT: Tests for custom actions defined in game JSON working correctly with the engine
WHY: We found several bugs where custom actions weren't triggered or conditions weren't evaluated
HOW: Creates minimal game fixtures with custom actions and verifies engine behavior

CASES:
- Custom unlock action (code-based lock, no key_object)
- Custom open action (puzzle door, openable=false)
- Custom enter action (door that moves player)
- Compound conditions (flags && inventory)
- State changes with flags.flag_name syntax
- Revealed objects start hidden

EDGE CASES:
- Condition with only one part failing
- ENTER <object> vs IN direction
"""

import pytest

from text_adventure.engine.engine import GameEngine
from text_adventure.models.game import Game


@pytest.fixture
def game_with_custom_actions():
    """A minimal game with various custom action patterns."""
    return Game.model_validate(
        {
            "metadata": {"title": "Custom Action Test", "description": "Testing"},
            "rooms": [
                {
                    "id": "start",
                    "name": "Start Room",
                    "description": "A test room.",
                    "exits": {},
                    "objects": ["code_door", "npc", "machine"],
                },
                {
                    "id": "secret_room",
                    "name": "Secret Room",
                    "description": "You made it!",
                    "exits": {"south": "start"},
                    "objects": [],
                },
            ],
            "objects": [
                {
                    "id": "code_door",
                    "name": "door",
                    "description": "A door with a keypad.",
                    "location": "start",
                    "takeable": False,
                    "lockable": True,
                    "locked": True,
                    "openable": False,  # Can't open normally
                    "key_object": None,  # No physical key
                    "actions": {
                        "unlock": {
                            "message": "You enter the code. Click!",
                            "condition": "flags.has_code",
                            "state_changes": {"code_door.locked": False},
                        },
                        "open": {
                            "message": "The door swings open.",
                            "condition": "!code_door.locked",
                            "state_changes": {"code_door.is_open": True},
                        },
                        "enter": {
                            "message": "You step through the door.",
                            "condition": "code_door.is_open",
                            "moves_player": "secret_room",
                        },
                    },
                },
                {
                    "id": "npc",
                    "name": "guard",
                    "description": "A guard.",
                    "location": "start",
                    "takeable": False,
                    "actions": {
                        "talk": {
                            "message": "The guard whispers: 'The code is 1234.'",
                            "state_changes": {"flags.has_code": True},
                        },
                    },
                },
                {
                    "id": "machine",
                    "name": "vending machine",
                    "description": "A machine.",
                    "location": "start",
                    "takeable": False,
                    "actions": {
                        "use": {
                            "message": "You use the machine.",
                            "condition": "flags.has_code && inventory.includes('coin')",
                            "state_changes": {"flags.used_machine": True},
                            "reveals_object": "prize",
                        },
                    },
                },
                {
                    "id": "coin",
                    "name": "coin",
                    "description": "A shiny coin.",
                    "location": "start",
                    "takeable": True,
                },
                {
                    "id": "prize",
                    "name": "prize",
                    "description": "A prize from the machine.",
                    "location": "start",
                    "takeable": True,
                    "hidden": True,  # Revealed by machine
                },
            ],
            "verbs": [],
            "initial_state": {"current_room": "start", "inventory": []},
            "win_condition": {"type": "reach_room", "room": "secret_room"},
        }
    )


class TestCustomUnlockAction:
    """Test UNLOCK with custom actions (code-based locks)."""

    def test_unlock_without_key_uses_custom_action(self, game_with_custom_actions):
        """UNLOCK DOOR should work via custom action when no key_object defined."""
        engine = GameEngine(game_with_custom_actions)

        # First, talk to guard to get the code
        result = engine.process_input("talk to guard")
        assert "code is 1234" in result.message.lower()
        assert engine.state.get_flag("has_code") is True

        # Now unlock should work
        result = engine.process_input("unlock door")
        assert "click" in result.message.lower()
        assert engine.state.objects["code_door"].locked is False

    def test_unlock_fails_without_condition(self, game_with_custom_actions):
        """UNLOCK DOOR should fail if condition not met."""
        engine = GameEngine(game_with_custom_actions)

        # Try to unlock without talking to guard first
        result = engine.process_input("unlock door")
        # Should get a hint about needing something
        assert (
            result.error or "need" in result.message.lower() or "missing" in result.message.lower()
        )


class TestCustomOpenAction:
    """Test OPEN with custom actions (puzzle doors)."""

    def test_open_uses_custom_action_when_openable_false(self, game_with_custom_actions):
        """OPEN should use custom action even when openable=False."""
        engine = GameEngine(game_with_custom_actions)

        # Setup: get code and unlock
        engine.process_input("talk to guard")
        engine.process_input("unlock door")

        # Now open should work via custom action
        result = engine.process_input("open door")
        assert "swings open" in result.message.lower()
        assert engine.state.objects["code_door"].is_open is True


class TestCustomEnterAction:
    """Test ENTER <object> with custom actions."""

    def test_enter_object_triggers_custom_action(self, game_with_custom_actions):
        """ENTER DOOR should trigger custom enter action, not movement."""
        engine = GameEngine(game_with_custom_actions)

        # Setup: get code, unlock, and open
        engine.process_input("talk to guard")
        engine.process_input("unlock door")
        engine.process_input("open door")

        # Now enter should move us
        result = engine.process_input("enter door")
        assert "step through" in result.message.lower()
        assert engine.state.current_room == "secret_room"


class TestCompoundConditions:
    """Test compound conditions in custom actions."""

    def test_compound_condition_both_parts_required(self, game_with_custom_actions):
        """Action with && condition requires both parts to be true."""
        engine = GameEngine(game_with_custom_actions)

        # Get the code but don't have coin
        engine.process_input("talk to guard")
        engine.process_input("use machine")
        assert engine.state.get_flag("used_machine") is not True

    def test_compound_condition_succeeds_when_all_met(self, game_with_custom_actions):
        """Action succeeds when all parts of && condition are true."""
        engine = GameEngine(game_with_custom_actions)

        # Get the code AND the coin
        engine.process_input("talk to guard")
        engine.process_input("take coin")

        result = engine.process_input("use machine")
        assert "use the machine" in result.message.lower()
        assert engine.state.get_flag("used_machine") is True


class TestFlagStateChanges:
    """Test that flags.flag_name syntax works in state_changes."""

    def test_flags_prefix_sets_flag(self, game_with_custom_actions):
        """State changes with flags.x syntax should set flags."""
        engine = GameEngine(game_with_custom_actions)

        assert engine.state.get_flag("has_code") is not True
        engine.process_input("talk to guard")
        assert engine.state.get_flag("has_code") is True


class TestRevealsObject:
    """Test that reveals_object works correctly."""

    def test_revealed_object_starts_hidden(self, game_with_custom_actions):
        """Objects that are reveals_object targets should start hidden."""
        engine = GameEngine(game_with_custom_actions)

        # Prize should be hidden initially
        assert engine.state.objects["prize"].hidden is True

        # Should not be visible in room
        room_desc = engine.describe_current_room()
        assert "prize" not in room_desc.lower()

    def test_reveals_object_makes_visible(self, game_with_custom_actions):
        """Using reveals_object should unhide the object."""
        engine = GameEngine(game_with_custom_actions)

        # Setup and use machine
        engine.process_input("talk to guard")
        engine.process_input("take coin")
        engine.process_input("use machine")

        # Prize should now be visible
        assert engine.state.objects["prize"].hidden is False


class TestHintGeneration:
    """Test that hints correctly identify which condition failed.

    NOTE: Currently only INSERT uses _execute_custom_action_with_hint.
    Other handlers use _execute_custom_action which returns generic messages.
    TODO: Extend hint generation to all handlers with custom actions.
    """

    def test_condition_failure_returns_failure(self, game_with_custom_actions):
        """When condition fails, action should return failure."""
        engine = GameEngine(game_with_custom_actions)

        # Try to use machine without meeting conditions
        engine.process_input("take coin")  # Have coin but no code
        result = engine.process_input("use machine")

        # Should fail (either via hint or generic message)
        assert result.error or engine.state.get_flag("used_machine") is not True

    def test_action_fails_gracefully_with_unmet_conditions(self, game_with_custom_actions):
        """When conditions aren't met, action doesn't execute."""
        engine = GameEngine(game_with_custom_actions)

        # Get code but don't take coin
        engine.process_input("talk to guard")
        engine.process_input("use machine")

        # The action should not have executed
        assert engine.state.get_flag("used_machine") is not True
        # Prize should still be hidden
        assert engine.state.objects["prize"].hidden is True
