"""
TEST DOC: Custom Verb Support

WHAT: Tests for custom verbs defined in game JSON
WHY: Adventure creators should be able to add verbs without Python changes
HOW: Test GameParser, handle_custom, and GameValidator

CASES:
- Custom verb parsing
- Custom verb execution
- Validator catches unknown verbs
"""

import pytest

from text_adventure.engine.engine import GameEngine
from text_adventure.models.game import Game
from text_adventure.parser.game_parser import GameParser
from text_adventure.validator import ValidationSeverity, validate_game


@pytest.fixture
def game_with_custom_verbs():
    """A game that defines custom verbs."""
    return Game.model_validate(
        {
            "metadata": {"title": "Custom Verb Test", "description": "Testing"},
            "rooms": [
                {
                    "id": "temple",
                    "name": "Ancient Temple",
                    "description": "A dusty temple with an altar.",
                    "exits": {},
                    "objects": ["altar", "statue"],
                }
            ],
            "objects": [
                {
                    "id": "altar",
                    "name": "stone altar",
                    "description": "An ancient altar.",
                    "location": "temple",
                    "takeable": False,
                    "actions": {
                        "pray": {
                            "message": "You kneel and pray. A sense of peace fills you.",
                            "state_changes": {"flags.blessed": True},
                        },
                        "worship": "You bow before the altar.",
                    },
                },
                {
                    "id": "statue",
                    "name": "golden statue",
                    "description": "A golden statue.",
                    "location": "temple",
                    "takeable": False,
                    "actions": {
                        "dance": "You dance around the statue. Nothing happens.",
                    },
                },
            ],
            "verbs": [
                {
                    "verb": "pray",
                    "aliases": ["worship", "kneel"],
                    "requires_object": False,
                },
                {
                    "verb": "dance",
                    "aliases": ["boogie"],
                    "requires_object": False,
                },
            ],
            "initial_state": {"current_room": "temple", "inventory": []},
            "win_condition": {"type": "flag_set", "flag": "blessed"},
        }
    )


class TestGameParser:
    """Test GameParser with custom verbs."""

    def test_parses_custom_verb(self, game_with_custom_verbs):
        """Custom verbs defined in game.verbs are recognized."""
        parser = GameParser(game_with_custom_verbs)
        result = parser.parse("pray")

        assert result.success
        assert result.command.custom_verb == "pray"

    def test_parses_custom_verb_alias(self, game_with_custom_verbs):
        """Custom verb aliases are recognized."""
        parser = GameParser(game_with_custom_verbs)
        result = parser.parse("kneel")

        assert result.success
        assert result.command.custom_verb == "pray"  # Canonical name

    def test_parses_custom_verb_with_object(self, game_with_custom_verbs):
        """Custom verbs can have objects."""
        parser = GameParser(game_with_custom_verbs)
        result = parser.parse("pray to altar")

        assert result.success
        assert result.command.custom_verb == "pray"
        # "to altar" becomes direct object since pray doesn't require indirect

    def test_unknown_verb_fails(self, game_with_custom_verbs):
        """Unknown verbs that aren't in game.verbs fail."""
        parser = GameParser(game_with_custom_verbs)
        result = parser.parse("fly")

        assert not result.success
        assert "don't know" in result.error.message.lower()

    def test_builtin_verbs_still_work(self, game_with_custom_verbs):
        """Built-in verbs work alongside custom verbs."""
        parser = GameParser(game_with_custom_verbs)

        result = parser.parse("examine altar")
        assert result.success
        assert result.command.verb.name == "EXAMINE"


class TestHandleCustom:
    """Test custom verb execution."""

    def test_custom_verb_triggers_action(self, game_with_custom_verbs):
        """Custom verb triggers matching action on room object."""
        engine = GameEngine(game_with_custom_verbs)

        result = engine.process_input("pray")

        assert "peace" in result.message.lower()
        assert engine.state.get_flag("blessed") is True

    def test_custom_verb_alias_works(self, game_with_custom_verbs):
        """Custom verb alias triggers same action."""
        engine = GameEngine(game_with_custom_verbs)

        result = engine.process_input("kneel")

        assert "peace" in result.message.lower()

    def test_custom_verb_no_matching_action(self, game_with_custom_verbs):
        """Custom verb with no matching action gives helpful message."""
        engine = GameEngine(game_with_custom_verbs)

        # Dance is defined but only on statue, not altar
        # With no object specified, it should find the statue's action
        result = engine.process_input("dance")

        assert "dance" in result.message.lower()


class TestValidator:
    """Test game validator."""

    def test_validates_clean_game(self, game_with_custom_verbs):
        """Clean game passes validation."""
        issues = validate_game(game_with_custom_verbs)

        # Should have no errors
        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        assert len(errors) == 0

    def test_catches_unknown_verb(self):
        """Validator catches actions with unknown verbs."""
        game = Game.model_validate(
            {
                "metadata": {"title": "Test", "description": "Test"},
                "rooms": [
                    {
                        "id": "room",
                        "name": "Room",
                        "description": "A room.",
                        "exits": {},
                        "objects": ["thing"],
                    }
                ],
                "objects": [
                    {
                        "id": "thing",
                        "name": "thing",
                        "description": "A thing.",
                        "location": "room",
                        "takeable": False,
                        "actions": {
                            "frobnicate": "You frobnicate the thing.",  # Unknown verb
                        },
                    }
                ],
                "verbs": [],  # No custom verbs defined
                "initial_state": {"current_room": "room", "inventory": []},
                "win_condition": {"type": "reach_room", "room": "room"},
            }
        )

        issues = validate_game(game)

        # Should have a warning about unknown verb
        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]
        assert any("frobnicate" in w.message for w in warnings)

    def test_catches_missing_reveals_object(self):
        """Validator catches reveals_object pointing to non-existent object."""
        game = Game.model_validate(
            {
                "metadata": {"title": "Test", "description": "Test"},
                "rooms": [
                    {
                        "id": "room",
                        "name": "Room",
                        "description": "A room.",
                        "exits": {},
                        "objects": ["thing"],
                    }
                ],
                "objects": [
                    {
                        "id": "thing",
                        "name": "thing",
                        "description": "A thing.",
                        "location": "room",
                        "takeable": False,
                        "actions": {
                            "use": {
                                "message": "You use it.",
                                "reveals_object": "nonexistent",  # Doesn't exist
                            },
                        },
                    }
                ],
                "verbs": [],
                "initial_state": {"current_room": "room", "inventory": []},
                "win_condition": {"type": "reach_room", "room": "room"},
            }
        )

        issues = validate_game(game)

        # Should have an error about missing object
        errors = [i for i in issues if i.severity == ValidationSeverity.ERROR]
        assert any("nonexistent" in e.message for e in errors)

    def test_catches_unrevealed_hidden(self):
        """Validator warns about revealed objects that aren't hidden."""
        game = Game.model_validate(
            {
                "metadata": {"title": "Test", "description": "Test"},
                "rooms": [
                    {
                        "id": "room",
                        "name": "Room",
                        "description": "A room.",
                        "exits": {},
                        "objects": ["box", "gem"],
                    }
                ],
                "objects": [
                    {
                        "id": "box",
                        "name": "box",
                        "description": "A box.",
                        "location": "room",
                        "takeable": False,
                        "actions": {
                            "open": {
                                "message": "You open the box.",
                                "reveals_object": "gem",
                            },
                        },
                    },
                    {
                        "id": "gem",
                        "name": "gem",
                        "description": "A gem.",
                        "location": "room",
                        "takeable": True,
                        "hidden": False,  # Should be True!
                    },
                ],
                "verbs": [],
                "initial_state": {"current_room": "room", "inventory": []},
                "win_condition": {"type": "reach_room", "room": "room"},
            }
        )

        issues = validate_game(game)

        # Should warn about gem not being hidden
        warnings = [i for i in issues if i.severity == ValidationSeverity.WARNING]
        assert any("hidden" in w.message.lower() for w in warnings)
