"""
TEST DOC: Object Resolver

WHAT: Tests for resolving text references to game object IDs
WHY: Correct resolution enables natural language object references
HOW: Test various reference formats, ambiguity, and visibility rules

CASES:
- Exact name match
- Adjective + name match
- ID match
- Ambiguity detection
- Visibility filtering

EDGE CASES:
- Multiple objects with same name
- Objects in containers
- Hidden objects
"""

import pytest

from text_adventure.models.command import Command, Preposition, Verb
from text_adventure.models.game import Game
from text_adventure.models.state import GameState
from text_adventure.parser.resolver import ObjectResolver, ResolutionError


@pytest.fixture
def two_keys_game() -> Game:
    """A game with two keys for ambiguity testing."""
    return Game.model_validate(
        {
            "metadata": {"title": "Two Keys"},
            "rooms": [
                {
                    "id": "room1",
                    "name": "Room One",
                    "description": "A room with two keys.",
                    "exits": {},
                }
            ],
            "objects": [
                {
                    "id": "brass_key",
                    "name": "key",
                    "adjectives": ["brass", "small"],
                    "description": "A small brass key.",
                    "location": "room1",
                },
                {
                    "id": "silver_key",
                    "name": "key",
                    "adjectives": ["silver", "large"],
                    "description": "A large silver key.",
                    "location": "room1",
                },
                {
                    "id": "lamp",
                    "name": "lamp",
                    "adjectives": ["brass"],
                    "description": "A brass lamp.",
                    "location": "room1",
                },
            ],
            "initial_state": {"current_room": "room1"},
            "win_condition": {"type": "reach_room", "room": "room1"},
        }
    )


@pytest.fixture
def container_game() -> Game:
    """A game with containers for visibility testing."""
    return Game.model_validate(
        {
            "metadata": {"title": "Containers"},
            "rooms": [
                {
                    "id": "room1",
                    "name": "Room",
                    "description": "A room with a box.",
                    "exits": {},
                }
            ],
            "objects": [
                {
                    "id": "wooden_box",
                    "name": "box",
                    "adjectives": ["wooden"],
                    "description": "A wooden box.",
                    "location": "room1",
                    "container": True,
                    "openable": True,
                    "contains": ["coin"],
                },
                {
                    "id": "coin",
                    "name": "coin",
                    "adjectives": ["gold"],
                    "description": "A gold coin.",
                    "location": "wooden_box",
                },
            ],
            "initial_state": {"current_room": "room1"},
            "win_condition": {"type": "reach_room", "room": "room1"},
        }
    )


class TestBasicResolution:
    """Tests for basic object resolution."""

    def test_exact_name_match(self, two_keys_game: Game):
        """Exact name match works."""
        state = GameState.from_game(two_keys_game)
        resolver = ObjectResolver(two_keys_game, state)

        cmd = Command(verb=Verb.TAKE, direct_object="lamp")
        result = resolver.resolve(cmd)

        assert result.success
        assert result.resolved is not None
        assert result.resolved.direct_object_id == "lamp"

    def test_adjective_match(self, two_keys_game: Game):
        """Adjective + name match works."""
        state = GameState.from_game(two_keys_game)
        resolver = ObjectResolver(two_keys_game, state)

        cmd = Command(verb=Verb.TAKE, direct_object="brass key")
        result = resolver.resolve(cmd)

        assert result.success
        assert result.resolved.direct_object_id == "brass_key"

    def test_multiple_adjectives(self, two_keys_game: Game):
        """Multiple adjectives work."""
        state = GameState.from_game(two_keys_game)
        resolver = ObjectResolver(two_keys_game, state)

        cmd = Command(verb=Verb.TAKE, direct_object="small brass key")
        result = resolver.resolve(cmd)

        assert result.success
        assert result.resolved.direct_object_id == "brass_key"

    def test_id_match(self, two_keys_game: Game):
        """Exact ID match works."""
        state = GameState.from_game(two_keys_game)
        resolver = ObjectResolver(two_keys_game, state)

        cmd = Command(verb=Verb.TAKE, direct_object="brass_key")
        result = resolver.resolve(cmd)

        assert result.success
        assert result.resolved.direct_object_id == "brass_key"


class TestAmbiguity:
    """Tests for ambiguous object resolution."""

    def test_ambiguous_name(self, two_keys_game: Game):
        """Ambiguous name produces error."""
        state = GameState.from_game(two_keys_game)
        resolver = ObjectResolver(two_keys_game, state)

        cmd = Command(verb=Verb.TAKE, direct_object="key")
        result = resolver.resolve(cmd)

        assert not result.success
        assert result.error_type == ResolutionError.AMBIGUOUS
        assert "which" in result.error_message.lower()
        assert result.ambiguous_objects is not None
        assert len(result.ambiguous_objects) == 2

    def test_adjective_disambiguates(self, two_keys_game: Game):
        """Adjective resolves ambiguity."""
        state = GameState.from_game(two_keys_game)
        resolver = ObjectResolver(two_keys_game, state)

        cmd = Command(verb=Verb.TAKE, direct_object="silver key")
        result = resolver.resolve(cmd)

        assert result.success
        assert result.resolved.direct_object_id == "silver_key"


class TestNotFound:
    """Tests for objects not found."""

    def test_nonexistent_object(self, two_keys_game: Game):
        """Nonexistent object produces error."""
        state = GameState.from_game(two_keys_game)
        resolver = ObjectResolver(two_keys_game, state)

        cmd = Command(verb=Verb.TAKE, direct_object="sword")
        result = resolver.resolve(cmd)

        assert not result.success
        assert result.error_type == ResolutionError.NOT_FOUND
        assert "sword" in result.error_message.lower()

    def test_object_in_other_room(self, sample_game: Game):
        """Object in another room is not visible."""
        state = GameState.from_game(sample_game)
        # Player is in entrance, silver_key is in pantry
        resolver = ObjectResolver(sample_game, state)

        cmd = Command(verb=Verb.TAKE, direct_object="silver key")
        result = resolver.resolve(cmd)

        assert not result.success
        assert result.error_type == ResolutionError.NOT_FOUND


class TestVisibility:
    """Tests for object visibility rules."""

    def test_object_in_current_room(self, sample_game: Game):
        """Objects in current room are visible."""
        state = GameState.from_game(sample_game)
        resolver = ObjectResolver(sample_game, state)

        cmd = Command(verb=Verb.TAKE, direct_object="brass key")
        result = resolver.resolve(cmd)

        assert result.success
        assert result.resolved.direct_object_id == "brass_key"

    def test_object_in_inventory(self, sample_game: Game):
        """Objects in inventory are visible."""
        state = GameState.from_game(sample_game)
        state.add_to_inventory("brass_key")
        resolver = ObjectResolver(sample_game, state)

        cmd = Command(verb=Verb.DROP, direct_object="brass key")
        result = resolver.resolve(cmd)

        assert result.success
        assert result.resolved.direct_object_id == "brass_key"

    def test_object_in_closed_container_not_visible(self, container_game: Game):
        """Objects in closed containers are not visible."""
        state = GameState.from_game(container_game)
        # Box is closed by default
        resolver = ObjectResolver(container_game, state)

        cmd = Command(verb=Verb.TAKE, direct_object="coin")
        result = resolver.resolve(cmd)

        assert not result.success
        assert result.error_type == ResolutionError.NOT_FOUND

    def test_object_in_open_container_visible(self, container_game: Game):
        """Objects in open containers are visible."""
        state = GameState.from_game(container_game)
        state.objects["wooden_box"].is_open = True
        resolver = ObjectResolver(container_game, state)

        cmd = Command(verb=Verb.TAKE, direct_object="coin")
        result = resolver.resolve(cmd)

        assert result.success
        assert result.resolved.direct_object_id == "coin"

    def test_hidden_object_not_visible(self, two_keys_game: Game):
        """Hidden objects are not visible."""
        state = GameState.from_game(two_keys_game)
        state.objects["lamp"].hidden = True
        resolver = ObjectResolver(two_keys_game, state)

        # Lamp should not be found because it's hidden
        cmd = Command(verb=Verb.TAKE, direct_object="lamp")
        result = resolver.resolve(cmd)

        assert not result.success
        assert result.error_type == ResolutionError.NOT_FOUND


class TestIndirectObjects:
    """Tests for resolving indirect objects."""

    def test_both_objects_resolved(self, container_game: Game):
        """Both direct and indirect objects are resolved."""
        state = GameState.from_game(container_game)
        state.objects["wooden_box"].is_open = True
        state.add_to_inventory("coin")
        resolver = ObjectResolver(container_game, state)

        cmd = Command(
            verb=Verb.PUT,
            direct_object="coin",
            preposition=Preposition.IN,
            indirect_object="box",
        )
        result = resolver.resolve(cmd)

        assert result.success
        assert result.resolved.direct_object_id == "coin"
        assert result.resolved.indirect_object_id == "wooden_box"

    def test_direct_not_found(self, container_game: Game):
        """Error if direct object not found."""
        state = GameState.from_game(container_game)
        resolver = ObjectResolver(container_game, state)

        cmd = Command(
            verb=Verb.PUT,
            direct_object="gem",
            preposition=Preposition.IN,
            indirect_object="box",
        )
        result = resolver.resolve(cmd)

        assert not result.success
        assert "gem" in result.error_message.lower()

    def test_indirect_not_found(self, container_game: Game):
        """Error if indirect object not found."""
        state = GameState.from_game(container_game)
        state.add_to_inventory("coin")
        resolver = ObjectResolver(container_game, state)

        cmd = Command(
            verb=Verb.PUT,
            direct_object="coin",
            preposition=Preposition.IN,
            indirect_object="chest",
        )
        result = resolver.resolve(cmd)

        assert not result.success
        assert "chest" in result.error_message.lower()


class TestResolveInContext:
    """Tests for context-aware resolution."""

    def test_inventory_context(self, sample_game: Game):
        """Inventory context only searches inventory."""
        state = GameState.from_game(sample_game)
        state.add_to_inventory("brass_key")
        resolver = ObjectResolver(sample_game, state)

        # Key is in inventory
        obj_id, error = resolver.resolve_in_context("brass key", "inventory")
        assert obj_id == "brass_key"
        assert error is None

        # Coat rack is in room, not inventory
        obj_id, error = resolver.resolve_in_context("coat rack", "inventory")
        assert obj_id is None
        assert error is not None
        assert "carrying" in error.lower()

    def test_room_context(self, sample_game: Game):
        """Room context only searches current room."""
        state = GameState.from_game(sample_game)
        state.add_to_inventory("brass_key")
        resolver = ObjectResolver(sample_game, state)

        # Coat rack is in room
        obj_id, error = resolver.resolve_in_context("coat rack", "room")
        assert obj_id == "coat_rack"

        # Key is in inventory, not room
        obj_id, error = resolver.resolve_in_context("brass key", "room")
        assert obj_id is None
        assert error is not None
