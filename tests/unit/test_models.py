"""
TEST DOC: Core Models

WHAT: Tests for Game, Room, GameObject, Command, and GameState models.
WHY: Ensure Pydantic validation works correctly and models behave as expected.
HOW: Test valid/invalid data, edge cases, and model methods.

CASES:
- Valid game JSON validates successfully
- Invalid references are rejected
- Command validation works
- GameState initializes correctly from Game

EDGE CASES:
- Empty objects list
- Nested win conditions
- Objects in containers
"""

import pytest
from pydantic import ValidationError

from text_adventure.models.command import (
    DIRECTION_VERBS,
    VERB_ALIASES,
    Command,
    Preposition,
    Verb,
)
from text_adventure.models.game import (
    Game,
    GameMetadata,
    GameObject,
    Room,
    WinCondition,
)
from text_adventure.models.state import GameState


class TestCommand:
    """Tests for the Command model."""

    def test_simple_command(self):
        """A verb-only command is valid."""
        cmd = Command(verb=Verb.NORTH)
        assert cmd.verb == Verb.NORTH
        assert cmd.direct_object is None

    def test_command_with_direct_object(self):
        """A command with a direct object is valid."""
        cmd = Command(verb=Verb.TAKE, direct_object="lamp")
        assert cmd.verb == Verb.TAKE
        assert cmd.direct_object == "lamp"

    def test_command_with_all_parts(self):
        """A full command with prep and indirect object is valid."""
        cmd = Command(
            verb=Verb.PUT,
            direct_object="key",
            preposition=Preposition.IN,
            indirect_object="box",
            raw_input="put key in box",
        )
        assert cmd.verb == Verb.PUT
        assert cmd.direct_object == "key"
        assert cmd.preposition == Preposition.IN
        assert cmd.indirect_object == "box"

    def test_command_indirect_without_preposition_fails(self):
        """An indirect object without preposition is invalid."""
        with pytest.raises(ValueError, match="no preposition"):
            Command(
                verb=Verb.PUT,
                direct_object="key",
                indirect_object="box",
            )

    def test_command_preposition_without_both_objects_fails(self):
        """A preposition requires both objects."""
        with pytest.raises(ValueError, match="both direct and indirect"):
            Command(
                verb=Verb.PUT,
                direct_object="key",
                preposition=Preposition.IN,
            )

    def test_command_is_frozen(self):
        """Commands are immutable."""
        cmd = Command(verb=Verb.LOOK)
        with pytest.raises(AttributeError):
            cmd.verb = Verb.TAKE  # type: ignore

    def test_verb_aliases_exist(self):
        """Verb aliases map to correct verbs."""
        assert VERB_ALIASES["get"] == Verb.TAKE
        assert VERB_ALIASES["grab"] == Verb.TAKE
        assert VERB_ALIASES["n"] == Verb.NORTH
        assert VERB_ALIASES["x"] == Verb.EXAMINE
        assert VERB_ALIASES["i"] == Verb.INVENTORY

    def test_direction_verbs(self):
        """Direction verbs are correctly identified."""
        assert Verb.NORTH in DIRECTION_VERBS
        assert Verb.UP in DIRECTION_VERBS
        assert Verb.TAKE not in DIRECTION_VERBS


class TestGameMetadata:
    """Tests for GameMetadata model."""

    def test_minimal_metadata(self):
        """Minimal metadata requires only title."""
        meta = GameMetadata(title="Test Game")
        assert meta.title == "Test Game"
        assert meta.author == "Generated"
        assert meta.version == "1.0"

    def test_empty_title_fails(self):
        """Empty title is rejected."""
        with pytest.raises(ValidationError):
            GameMetadata(title="")


class TestRoom:
    """Tests for Room model."""

    def test_simple_room(self):
        """A simple room with no exits or objects is valid."""
        room = Room(
            id="test_room",
            name="Test Room",
            description="A test room.",
        )
        assert room.id == "test_room"
        assert room.exits == {}
        assert room.objects == []

    def test_room_id_pattern(self):
        """Room IDs must be lowercase with underscores."""
        with pytest.raises(ValidationError):
            Room(
                id="Test-Room",  # Invalid: uppercase and hyphen
                name="Test Room",
                description="A test room.",
            )

    def test_room_with_string_exits(self):
        """String exits are accepted."""
        room = Room(
            id="hall",
            name="Hall",
            description="A hallway.",
            exits={"north": "library"},
        )
        assert room.exits["north"] == "library"

    def test_room_with_exit_objects(self):
        """Exit objects are accepted."""
        room = Room(
            id="hall",
            name="Hall",
            description="A hallway.",
            exits={
                "north": {
                    "target": "library",
                    "locked": True,
                    "lock_message": "It's locked!",
                }
            },
        )
        exit_obj = room.exits["north"]
        assert hasattr(exit_obj, "target")
        assert exit_obj.target == "library"  # type: ignore
        assert exit_obj.locked is True  # type: ignore


class TestGameObject:
    """Tests for GameObject model."""

    def test_simple_object(self):
        """A simple object with minimal fields."""
        obj = GameObject(
            id="lamp",
            name="brass lamp",
            description="A brass lamp.",
            location="entrance",
        )
        assert obj.id == "lamp"
        assert obj.takeable is True  # Default

    def test_scenery_not_takeable(self):
        """Scenery objects have takeable forced to False."""
        obj = GameObject(
            id="tree",
            name="oak tree",
            description="A large oak tree.",
            location="garden",
            scenery=True,
            takeable=True,  # Will be overridden
        )
        assert obj.takeable is False

    def test_readable_requires_text(self):
        """Readable objects must have read_text."""
        with pytest.raises(ValidationError, match="read_text"):
            GameObject(
                id="book",
                name="book",
                description="A book.",
                location="library",
                readable=True,
                # Missing read_text
            )

    def test_object_with_adjectives(self):
        """Objects can have adjectives for disambiguation."""
        obj = GameObject(
            id="brass_key",
            name="key",
            adjectives=["brass", "small"],
            description="A small brass key.",
            location="hall",
        )
        assert "brass" in obj.adjectives
        assert "small" in obj.adjectives

    def test_container_is_openable(self):
        """Containers are automatically made openable."""
        obj = GameObject(
            id="chest",
            name="chest",
            description="A chest.",
            location="room",
            container=True,
            openable=False,  # Will be overridden
        )
        assert obj.openable is True


class TestWinCondition:
    """Tests for WinCondition model."""

    def test_reach_room_condition(self):
        """A reach_room condition is valid."""
        cond = WinCondition(type="reach_room", room="treasure")
        assert cond.type == "reach_room"
        assert cond.room == "treasure"

    def test_reach_room_requires_room(self):
        """reach_room type requires room field."""
        with pytest.raises(ValidationError, match="room"):
            WinCondition(type="reach_room")

    def test_have_object_condition(self):
        """A have_object condition is valid."""
        cond = WinCondition(type="have_object", object="gold")
        assert cond.type == "have_object"
        assert cond.object == "gold"

    def test_nested_all_of_condition(self):
        """Nested all_of conditions work."""
        cond = WinCondition(
            type="all_of",
            conditions=[
                WinCondition(type="reach_room", room="end"),
                WinCondition(type="have_object", object="key"),
            ],
        )
        assert cond.type == "all_of"
        assert len(cond.conditions) == 2


class TestGame:
    """Tests for the complete Game model."""

    def test_sample_game_validates(self, sample_game_dict):
        """The sample game JSON validates successfully."""
        game = Game.model_validate(sample_game_dict)
        assert game.metadata.title == "The Brass Key"
        assert len(game.rooms) == 5
        assert len(game.objects) == 9

    def test_minimal_game_validates(self, minimal_game_dict):
        """A minimal game validates."""
        game = Game.model_validate(minimal_game_dict)
        assert game.metadata.title == "Minimal Test Game"
        assert len(game.rooms) == 1

    def test_invalid_initial_room_fails(self, minimal_game_dict):
        """Invalid initial room reference is rejected."""
        minimal_game_dict["initial_state"]["current_room"] = "nonexistent"
        with pytest.raises(ValidationError, match="not found"):
            Game.model_validate(minimal_game_dict)

    def test_invalid_exit_reference_fails(self, minimal_game_dict):
        """Invalid exit target is rejected."""
        minimal_game_dict["rooms"][0]["exits"] = {"north": "nonexistent"}
        with pytest.raises(ValidationError, match="unknown room"):
            Game.model_validate(minimal_game_dict)

    def test_invalid_object_location_fails(self, minimal_game_dict):
        """Invalid object location is rejected."""
        minimal_game_dict["objects"] = [
            {
                "id": "thing",
                "name": "thing",
                "description": "A thing.",
                "location": "nonexistent",
            }
        ]
        with pytest.raises(ValidationError, match="invalid location"):
            Game.model_validate(minimal_game_dict)

    def test_get_room(self, sample_game):
        """get_room returns the correct room."""
        room = sample_game.get_room("library")
        assert room is not None
        assert room.name == "The Library"

        assert sample_game.get_room("nonexistent") is None

    def test_get_object(self, sample_game):
        """get_object returns the correct object."""
        obj = sample_game.get_object("brass_key")
        assert obj is not None
        assert obj.name == "brass key"

        assert sample_game.get_object("nonexistent") is None


class TestGameState:
    """Tests for GameState model."""

    def test_from_game(self, sample_game):
        """GameState initializes correctly from a Game."""
        state = GameState.from_game(sample_game)

        assert state.current_room == "entrance"
        assert state.inventory == []
        assert state.turns == 0
        assert state.game_over is False
        assert state.won is False

    def test_initial_room_visited(self, sample_game):
        """The starting room is marked as visited."""
        state = GameState.from_game(sample_game)
        assert state.rooms["entrance"].visited is True
        assert state.rooms["library"].visited is False

    def test_object_states_initialized(self, sample_game):
        """Object states are initialized from game definition."""
        state = GameState.from_game(sample_game)

        # Check brass key is at entrance (not in inventory initially)
        assert state.objects["brass_key"].location == "entrance"

        # Check wooden box is closed
        assert state.objects["wooden_box"].is_open is False

    def test_get_objects_at(self, sample_game):
        """get_objects_at returns objects at a location."""
        state = GameState.from_game(sample_game)

        entrance_objects = state.get_objects_at("entrance")
        assert "brass_key" in entrance_objects
        assert "coat_rack" in entrance_objects

    def test_move_object(self, sample_game):
        """move_object updates object location."""
        state = GameState.from_game(sample_game)

        state.move_object("brass_key", "library")
        assert state.objects["brass_key"].location == "library"

    def test_inventory_operations(self, sample_game):
        """Inventory add/remove works correctly."""
        state = GameState.from_game(sample_game)

        state.add_to_inventory("brass_key")
        assert state.is_in_inventory("brass_key")
        assert state.objects["brass_key"].location == "inventory"

        state.remove_from_inventory("brass_key")
        assert not state.is_in_inventory("brass_key")
        # Note: remove_from_inventory doesn't change location

    def test_flags(self, sample_game):
        """Flag get/set works."""
        state = GameState.from_game(sample_game)

        assert state.get_flag("treasure_room_revealed") is False
        state.set_flag("treasure_room_revealed", True)
        assert state.get_flag("treasure_room_revealed") is True

        assert state.get_flag("nonexistent", default="missing") == "missing"

    def test_save_and_load(self, sample_game):
        """State can be saved and loaded."""
        state = GameState.from_game(sample_game)

        # Make some changes
        state.add_to_inventory("brass_key")
        state.increment_turns()
        state.add_score(10)
        state.set_flag("custom_flag", "value")

        # Save
        save_data = state.to_save_dict()

        # Load
        loaded = GameState.from_save_dict(save_data)

        assert loaded.inventory == ["brass_key"]
        assert loaded.turns == 1
        assert loaded.score == 10
        assert loaded.get_flag("custom_flag") == "value"

    def test_end_game(self, sample_game):
        """end_game sets appropriate flags."""
        state = GameState.from_game(sample_game)

        state.end_game(won=True)
        assert state.game_over is True
        assert state.won is True

        # Test losing
        state2 = GameState.from_game(sample_game)
        state2.end_game(won=False, message="You died!")
        assert state2.game_over is True
        assert state2.won is False
        assert state2.death_message == "You died!"
