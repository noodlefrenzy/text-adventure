"""
TEST DOC: Generator Transformations

WHAT: Tests for LLM output transformation/sanitization methods in GameGenerator
WHY: LLMs produce ~20% invalid output that needs fixing before Pydantic validation
HOW: Test each transform method in isolation with known-bad inputs

CASES:
- ID sanitization: hyphens, spaces, numbers, special chars
- Room ID sanitization: updates exits, returns mapping
- Object ID sanitization: updates location, key_object, contains
- Room object refs: removes non-existent, keeps valid
- Action fixes: adds missing message, preserves valid

EDGE CASES:
- Empty strings, already-valid inputs, multiple issues combined
"""

import pytest

from text_adventure.generator.generator import GameGenerator
from text_adventure.llm.client import LLMClient


class MockLLMClient(LLMClient):
    """Minimal mock client for testing generator methods."""

    @property
    def model_name(self) -> str:
        return "mock"

    async def complete(self, request):
        raise NotImplementedError

    async def complete_json(self, request, schema):
        raise NotImplementedError


@pytest.fixture
def generator():
    """Create a generator with a mock client for testing transform methods."""
    return GameGenerator(MockLLMClient())


class TestSanitizeId:
    """Test _sanitize_id() method."""

    def test_sanitize_id_with_hyphens(self, generator):
        """Hyphens are converted to underscores."""
        assert generator._sanitize_id("foo-bar") == "foo_bar"
        assert generator._sanitize_id("room-1-entrance") == "room_1_entrance"

    def test_sanitize_id_with_spaces(self, generator):
        """Spaces are converted to underscores."""
        assert generator._sanitize_id("foo bar") == "foo_bar"
        assert generator._sanitize_id("brass key") == "brass_key"

    def test_sanitize_id_starting_with_number(self, generator):
        """IDs starting with numbers get 'obj_' prefix."""
        assert generator._sanitize_id("7up") == "obj_7up"
        assert generator._sanitize_id("123abc") == "obj_123abc"

    def test_sanitize_id_with_special_chars(self, generator):
        """Special characters are removed."""
        assert generator._sanitize_id("foo@bar!") == "foobar"
        assert generator._sanitize_id("café") == "caf"
        assert generator._sanitize_id("item#1") == "item1"

    def test_sanitize_id_empty_string(self, generator):
        """Empty string returns 'unknown'."""
        assert generator._sanitize_id("") == "unknown"

    def test_sanitize_id_already_valid(self, generator):
        """Valid IDs pass through unchanged."""
        assert generator._sanitize_id("valid_id") == "valid_id"
        assert generator._sanitize_id("room1") == "room1"
        assert generator._sanitize_id("brass_key_123") == "brass_key_123"

    def test_sanitize_id_multiple_underscores(self, generator):
        """Multiple consecutive underscores are collapsed."""
        assert generator._sanitize_id("foo__bar") == "foo_bar"
        assert generator._sanitize_id("a___b___c") == "a_b_c"

    def test_sanitize_id_leading_trailing_underscores(self, generator):
        """Leading and trailing underscores are removed."""
        assert generator._sanitize_id("_foo_") == "foo"
        assert generator._sanitize_id("__bar__") == "bar"

    def test_sanitize_id_mixed_issues(self, generator):
        """Multiple issues are fixed together."""
        assert generator._sanitize_id("Room-1 (Main)") == "room_1_main"
        assert generator._sanitize_id("--foo--bar--") == "foo_bar"


class TestSanitizeRoomIds:
    """Test _sanitize_room_ids() method."""

    def test_fixes_invalid_room_ids(self, generator):
        """Room IDs with invalid characters are fixed."""
        rooms = [
            {"id": "room-1", "name": "Room 1", "description": "...", "exits": {}},
            {"id": "room-2", "name": "Room 2", "description": "...", "exits": {}},
        ]
        fixed_rooms, id_map = generator._sanitize_room_ids(rooms)

        assert fixed_rooms[0]["id"] == "room_1"
        assert fixed_rooms[1]["id"] == "room_2"
        assert id_map == {"room-1": "room_1", "room-2": "room_2"}

    def test_updates_exit_string_targets(self, generator):
        """String exit targets are updated when room IDs change."""
        rooms = [
            {"id": "room-1", "name": "Room 1", "description": "...", "exits": {"north": "room-2"}},
            {"id": "room-2", "name": "Room 2", "description": "...", "exits": {"south": "room-1"}},
        ]
        fixed_rooms, _ = generator._sanitize_room_ids(rooms)

        assert fixed_rooms[0]["exits"]["north"] == "room_2"
        assert fixed_rooms[1]["exits"]["south"] == "room_1"

    def test_updates_exit_object_targets(self, generator):
        """Exit objects with target field are updated."""
        rooms = [
            {
                "id": "room-1",
                "name": "Room 1",
                "description": "...",
                "exits": {
                    "north": {"target": "room-2", "locked": True, "lock_message": "Locked!"}
                },
            },
            {"id": "room-2", "name": "Room 2", "description": "...", "exits": {}},
        ]
        fixed_rooms, _ = generator._sanitize_room_ids(rooms)

        assert fixed_rooms[0]["exits"]["north"]["target"] == "room_2"
        assert fixed_rooms[0]["exits"]["north"]["locked"] is True

    def test_returns_id_mapping(self, generator):
        """Returns mapping of old IDs to new IDs."""
        rooms = [
            {"id": "valid_room", "name": "Valid", "description": "...", "exits": {}},
            {"id": "invalid-room", "name": "Invalid", "description": "...", "exits": {}},
        ]
        _, id_map = generator._sanitize_room_ids(rooms)

        # Only changed IDs are in the map
        assert "valid_room" not in id_map
        assert id_map["invalid-room"] == "invalid_room"

    def test_preserves_valid_ids(self, generator):
        """Valid IDs pass through unchanged."""
        rooms = [
            {"id": "entrance", "name": "Entrance", "description": "...", "exits": {"north": "exit"}},
            {"id": "exit", "name": "Exit", "description": "...", "exits": {"south": "entrance"}},
        ]
        fixed_rooms, id_map = generator._sanitize_room_ids(rooms)

        assert fixed_rooms[0]["id"] == "entrance"
        assert fixed_rooms[1]["id"] == "exit"
        assert id_map == {}


class TestSanitizeObjectIds:
    """Test _sanitize_object_ids() method."""

    def test_fixes_invalid_object_ids(self, generator):
        """Object IDs with invalid characters are fixed."""
        objects = [
            {"id": "brass-key", "name": "key", "description": "...", "location": "room1"},
            {"id": "old book", "name": "book", "description": "...", "location": "room1"},
        ]
        fixed_objects, id_map = generator._sanitize_object_ids(objects, {})

        assert fixed_objects[0]["id"] == "brass_key"
        assert fixed_objects[1]["id"] == "old_book"
        assert id_map == {"brass-key": "brass_key", "old book": "old_book"}

    def test_updates_location_with_room_map(self, generator):
        """Object locations are updated using room_id_map."""
        objects = [
            {"id": "key", "name": "key", "description": "...", "location": "room-1"},
        ]
        room_id_map = {"room-1": "room_1"}
        fixed_objects, _ = generator._sanitize_object_ids(objects, room_id_map)

        assert fixed_objects[0]["location"] == "room_1"

    def test_updates_key_object_reference(self, generator):
        """key_object references are updated."""
        objects = [
            {"id": "brass-key", "name": "key", "description": "...", "location": "room1"},
            {
                "id": "chest",
                "name": "chest",
                "description": "...",
                "location": "room1",
                "lockable": True,
                "key_object": "brass-key",
            },
        ]
        fixed_objects, _ = generator._sanitize_object_ids(objects, {})

        assert fixed_objects[1]["key_object"] == "brass_key"

    def test_updates_contains_references(self, generator):
        """contains references are updated."""
        objects = [
            {"id": "small-coin", "name": "coin", "description": "...", "location": "chest"},
            {
                "id": "chest",
                "name": "chest",
                "description": "...",
                "location": "room1",
                "container": True,
                "contains": ["small-coin"],
            },
        ]
        fixed_objects, _ = generator._sanitize_object_ids(objects, {})

        assert fixed_objects[1]["contains"] == ["small_coin"]

    def test_returns_id_mapping(self, generator):
        """Returns mapping of old IDs to new IDs."""
        objects = [
            {"id": "valid_key", "name": "key", "description": "...", "location": "room1"},
            {"id": "invalid-key", "name": "key", "description": "...", "location": "room1"},
        ]
        _, id_map = generator._sanitize_object_ids(objects, {})

        assert "valid_key" not in id_map
        assert id_map["invalid-key"] == "invalid_key"


class TestFixRoomObjectReferences:
    """Test _fix_room_object_references() method."""

    def test_removes_nonexistent_object_refs(self, generator):
        """References to non-existent objects are removed."""
        rooms = [
            {"id": "room1", "name": "Room", "description": "...", "exits": {}, "objects": ["key", "ghost", "phantom"]},
        ]
        objects = [
            {"id": "key", "name": "key", "description": "...", "location": "room1"},
        ]
        fixed_rooms = generator._fix_room_object_references(rooms, objects)

        assert fixed_rooms[0]["objects"] == ["key"]

    def test_preserves_valid_object_refs(self, generator):
        """Valid object references are kept."""
        rooms = [
            {"id": "room1", "name": "Room", "description": "...", "exits": {}, "objects": ["key", "lamp", "book"]},
        ]
        objects = [
            {"id": "key", "name": "key", "description": "...", "location": "room1"},
            {"id": "lamp", "name": "lamp", "description": "...", "location": "room1"},
            {"id": "book", "name": "book", "description": "...", "location": "room1"},
        ]
        fixed_rooms = generator._fix_room_object_references(rooms, objects)

        assert fixed_rooms[0]["objects"] == ["key", "lamp", "book"]

    def test_handles_empty_objects_list(self, generator):
        """Room with empty objects list works."""
        rooms = [
            {"id": "room1", "name": "Room", "description": "...", "exits": {}, "objects": []},
        ]
        fixed_rooms = generator._fix_room_object_references(rooms, [])

        assert fixed_rooms[0]["objects"] == []

    def test_handles_all_invalid_refs(self, generator):
        """Room with only invalid refs ends up with empty list."""
        rooms = [
            {"id": "room1", "name": "Room", "description": "...", "exits": {}, "objects": ["ghost1", "ghost2"]},
        ]
        fixed_rooms = generator._fix_room_object_references(rooms, [])

        assert fixed_rooms[0]["objects"] == []

    def test_handles_room_without_objects_key(self, generator):
        """Room without objects key is handled."""
        rooms = [
            {"id": "room1", "name": "Room", "description": "...", "exits": {}},
        ]
        fixed_rooms = generator._fix_room_object_references(rooms, [])

        assert "objects" not in fixed_rooms[0] or fixed_rooms[0].get("objects") is None


class TestFixObjectActions:
    """Test _fix_object_actions() method."""

    def test_adds_missing_message_field(self, generator):
        """Default message is added when missing."""
        objects = [
            {
                "id": "machine",
                "name": "vending machine",
                "description": "...",
                "location": "room1",
                "actions": {
                    "use": {"condition": "flags.ready", "state_changes": {"flags.done": True}},
                },
            }
        ]
        fixed_objects = generator._fix_object_actions(objects)

        assert "message" in fixed_objects[0]["actions"]["use"]
        assert "vending machine" in fixed_objects[0]["actions"]["use"]["message"]

    def test_preserves_valid_action_objects(self, generator):
        """Valid action objects are unchanged."""
        objects = [
            {
                "id": "machine",
                "name": "machine",
                "description": "...",
                "location": "room1",
                "actions": {
                    "use": {"message": "You use it.", "state_changes": {"flags.done": True}},
                },
            }
        ]
        fixed_objects = generator._fix_object_actions(objects)

        assert fixed_objects[0]["actions"]["use"]["message"] == "You use it."

    def test_preserves_string_actions(self, generator):
        """String actions pass through unchanged."""
        objects = [
            {
                "id": "sign",
                "name": "sign",
                "description": "...",
                "location": "room1",
                "actions": {"examine": "You see a sign."},
            }
        ]
        fixed_objects = generator._fix_object_actions(objects)

        assert fixed_objects[0]["actions"]["examine"] == "You see a sign."

    def test_handles_object_without_actions(self, generator):
        """Object without actions field is handled."""
        objects = [
            {"id": "key", "name": "key", "description": "...", "location": "room1"},
        ]
        fixed_objects = generator._fix_object_actions(objects)

        assert "actions" not in fixed_objects[0] or fixed_objects[0].get("actions") is None

    def test_handles_verb_with_target_in_action_key(self, generator):
        """Action keys like 'use:door' generate appropriate messages."""
        objects = [
            {
                "id": "key",
                "name": "brass key",
                "description": "...",
                "location": "room1",
                "actions": {
                    "use:door": {"state_changes": {"door.locked": False}},
                },
            }
        ]
        fixed_objects = generator._fix_object_actions(objects)

        # Should use "use" verb from "use:door"
        assert "use" in fixed_objects[0]["actions"]["use:door"]["message"].lower()


class TestTransformGameData:
    """Test full _transform_game_data() integration."""

    def test_updates_initial_state_current_room(self, generator):
        """initial_state.current_room uses sanitized room ID."""
        data = {
            "metadata": {"title": "Test", "description": "Test"},
            "rooms": [{"id": "room-1", "name": "Room", "description": "...", "exits": {}}],
            "objects": [],
            "initial_state": {"current_room": "room-1"},
            "win_condition": {"type": "reach_room", "room": "room-1"},
        }
        result = generator._transform_game_data(data)

        assert result["initial_state"]["current_room"] == "room_1"

    def test_updates_initial_state_inventory(self, generator):
        """initial_state.inventory uses sanitized object IDs."""
        data = {
            "metadata": {"title": "Test", "description": "Test"},
            "rooms": [{"id": "room1", "name": "Room", "description": "...", "exits": {}}],
            "objects": [
                {"id": "brass-key", "name": "key", "description": "...", "location": "inventory"},
            ],
            "initial_state": {"current_room": "room1", "inventory": ["brass-key"]},
            "win_condition": {"type": "reach_room", "room": "room1"},
        }
        result = generator._transform_game_data(data)

        assert result["initial_state"]["inventory"] == ["brass_key"]

    def test_updates_win_condition_reach_room(self, generator):
        """win_condition.room uses sanitized room ID."""
        data = {
            "metadata": {"title": "Test", "description": "Test"},
            "rooms": [{"id": "treasure-room", "name": "Treasure", "description": "...", "exits": {}}],
            "objects": [],
            "initial_state": {"current_room": "treasure-room"},
            "win_condition": {"type": "reach_room", "room": "treasure-room"},
        }
        result = generator._transform_game_data(data)

        assert result["win_condition"]["room"] == "treasure_room"

    def test_updates_win_condition_have_object(self, generator):
        """win_condition.object uses sanitized object ID."""
        data = {
            "metadata": {"title": "Test", "description": "Test"},
            "rooms": [{"id": "room1", "name": "Room", "description": "...", "exits": {}}],
            "objects": [
                {"id": "golden-trophy", "name": "trophy", "description": "...", "location": "room1"},
            ],
            "initial_state": {"current_room": "room1"},
            "win_condition": {"type": "have_object", "object": "golden-trophy"},
        }
        result = generator._transform_game_data(data)

        assert result["win_condition"]["object"] == "golden_trophy"

    def test_handles_multiple_issues(self, generator):
        """Multiple issues are fixed together."""
        data = {
            "metadata": {"title": "Test", "description": "Test"},
            "rooms": [
                {
                    "id": "room-1",
                    "name": "Room",
                    "description": "...",
                    "exits": {"north": "room-2"},
                    "objects": ["brass-key", "ghost-object"],  # ghost-object doesn't exist
                },
                {"id": "room-2", "name": "Room 2", "description": "...", "exits": {"south": "room-1"}},
            ],
            "objects": [
                {
                    "id": "brass-key",
                    "name": "key",
                    "description": "...",
                    "location": "room-1",
                    "actions": {"use": {"state_changes": {"flags.done": True}}},  # Missing message
                },
            ],
            "initial_state": {"current_room": "room-1"},
            "win_condition": {"type": "reach_room", "room": "room-2"},
        }
        result = generator._transform_game_data(data)

        # Room IDs sanitized
        assert result["rooms"][0]["id"] == "room_1"
        assert result["rooms"][1]["id"] == "room_2"

        # Exits updated
        assert result["rooms"][0]["exits"]["north"] == "room_2"

        # Object ID sanitized
        assert result["objects"][0]["id"] == "brass_key"
        assert result["objects"][0]["location"] == "room_1"

        # Ghost object removed from room
        assert result["rooms"][0]["objects"] == ["brass_key"]

        # Action message added
        assert "message" in result["objects"][0]["actions"]["use"]

        # Initial state and win condition updated
        assert result["initial_state"]["current_room"] == "room_1"
        assert result["win_condition"]["room"] == "room_2"
