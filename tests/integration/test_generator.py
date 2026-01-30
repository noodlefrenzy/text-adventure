"""
TEST DOC: Game Generator

WHAT: Tests for the LLM-based game generator
WHY: Ensure game generation produces valid, playable games
HOW: Use respx to mock Anthropic API responses with realistic game data

CASES:
- Basic generation with theme and room count
- Generated game validates against Pydantic models
- Generated game is playable (can load in engine)
- Error handling for LLM failures

EDGE CASES:
- Missing object locations (should be fixed by transformer)
- Missing metadata fields
- Invalid JSON response
"""

import pytest
import respx
from httpx import Response

from text_adventure.generator import GameGenerationError, GameGenerator
from text_adventure.llm.anthropic import AnthropicClient


@pytest.fixture
def mock_anthropic():
    """Set up respx mock for Anthropic API."""
    with respx.mock(base_url="https://api.anthropic.com") as respx_mock:
        yield respx_mock


@pytest.fixture
def client():
    """Create a test client with a dummy API key."""
    return AnthropicClient(api_key="test-api-key", model="claude-sonnet-4-20250514")


@pytest.fixture
def sample_generated_game():
    """A sample game response as the LLM might produce it."""
    return {
        "metadata": {
            "title": "The Haunted Lighthouse",
            "description": "Explore a mysterious lighthouse on a stormy night.",
        },
        "rooms": [
            {
                "id": "lighthouse_base",
                "name": "Lighthouse Base",
                "description": "You stand at the base of an ancient lighthouse. The heavy wooden door creaks in the wind.",
                "exits": {"up": "spiral_staircase", "south": "rocky_shore"},
                "objects": ["old_lantern", "weathered_sign"],
            },
            {
                "id": "spiral_staircase",
                "name": "Spiral Staircase",
                "description": "A narrow spiral staircase winds upward into darkness. The iron steps groan with each step.",
                "exits": {"up": "lamp_room", "down": "lighthouse_base"},
                "objects": [],
            },
            {
                "id": "lamp_room",
                "name": "Lamp Room",
                "description": "The great lamp stands dormant. Through the grimy windows, you see the churning sea below.",
                "exits": {"down": "spiral_staircase"},
                "objects": ["lighthouse_lamp", "old_logbook", "brass_key"],
            },
            {
                "id": "rocky_shore",
                "name": "Rocky Shore",
                "description": "Waves crash against the rocks. A small cave opening is visible to the east.",
                "exits": {"north": "lighthouse_base", "east": {"target": "hidden_cave", "locked": True, "lock_message": "The cave entrance is blocked by a rusty gate.", "unlock_object": "brass_key"}},
                "objects": ["driftwood", "seashells"],
            },
            {
                "id": "hidden_cave",
                "name": "Hidden Cave",
                "description": "A treasure chest gleams in the dim light filtering from above.",
                "exits": {"west": "rocky_shore"},
                "objects": ["treasure_chest"],
            },
        ],
        "objects": [
            {
                "id": "old_lantern",
                "name": "old lantern",
                "adjectives": ["old", "rusty"],
                "description": "A rusty oil lantern.",
                "examine_text": "The lantern is old but might still work with some oil.",
                "location": "lighthouse_base",
                "takeable": True,
            },
            {
                "id": "weathered_sign",
                "name": "weathered sign",
                "adjectives": ["weathered", "wooden"],
                "description": "A wooden sign nailed to the wall.",
                "examine_text": "The sign reads: 'Keeper's Log - Hidden in the Lamp Room'",
                "location": "lighthouse_base",
                "takeable": False,
                "scenery": True,
                "readable": True,
                "read_text": "Keeper's Log - Hidden in the Lamp Room",
            },
            {
                "id": "lighthouse_lamp",
                "name": "lighthouse lamp",
                "adjectives": ["great", "large"],
                "description": "The great lamp of the lighthouse.",
                "examine_text": "A massive Fresnel lens. It hasn't been lit in decades.",
                "location": "lamp_room",
                "takeable": False,
                "scenery": True,
            },
            {
                "id": "old_logbook",
                "name": "old logbook",
                "adjectives": ["old", "dusty", "leather"],
                "description": "A dusty leather logbook.",
                "examine_text": "The keeper's logbook. The last entry mentions hiding something in the cave.",
                "location": "lamp_room",
                "takeable": True,
                "readable": True,
                "read_text": "October 15th - Hid the treasure in the sea cave. The brass key opens the gate.",
            },
            {
                "id": "brass_key",
                "name": "brass key",
                "adjectives": ["brass", "small", "ornate"],
                "description": "A small brass key with an ornate handle.",
                "examine_text": "The key is engraved with a wave pattern.",
                "location": "lamp_room",
                "takeable": True,
            },
            {
                "id": "driftwood",
                "name": "driftwood",
                "adjectives": ["waterlogged"],
                "description": "A piece of waterlogged driftwood.",
                "location": "rocky_shore",
                "takeable": True,
            },
            {
                "id": "seashells",
                "name": "seashells",
                "adjectives": ["colorful"],
                "description": "A collection of colorful seashells.",
                "location": "rocky_shore",
                "takeable": False,
                "scenery": True,
            },
            {
                "id": "treasure_chest",
                "name": "treasure chest",
                "adjectives": ["wooden", "old"],
                "description": "An old wooden chest bound with iron bands.",
                "examine_text": "The chest is unlocked. Inside you see gold coins!",
                "location": "hidden_cave",
                "takeable": False,
                "openable": True,
                "container": True,
            },
        ],
        "initial_state": {
            "current_room": "lighthouse_base",
            "inventory": [],
            "flags": {},
        },
        "win_condition": {
            "type": "reach_room",
            "room": "hidden_cave",
            "win_message": "You've found the hidden treasure! The lighthouse keeper's secret is revealed!",
        },
    }


class TestGameGenerator:
    """Tests for the game generator."""

    @pytest.mark.asyncio
    async def test_generate_basic(self, mock_anthropic, client, sample_generated_game):
        """Basic generation returns a valid game."""
        mock_anthropic.post("/v1/messages").mock(
            return_value=Response(
                200,
                json={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_123",
                            "name": "structured_response",
                            "input": sample_generated_game,
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 1000, "output_tokens": 2000},
                },
            )
        )

        generator = GameGenerator(client)
        game = await generator.generate(theme="haunted lighthouse", num_rooms=5)

        assert game.metadata.title == "The Haunted Lighthouse"
        assert len(game.rooms) == 5
        assert len(game.objects) == 8

    @pytest.mark.asyncio
    async def test_generated_game_is_playable(self, mock_anthropic, client, sample_generated_game):
        """Generated game can be loaded into the engine."""
        mock_anthropic.post("/v1/messages").mock(
            return_value=Response(
                200,
                json={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_123",
                            "name": "structured_response",
                            "input": sample_generated_game,
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 1000, "output_tokens": 2000},
                },
            )
        )

        generator = GameGenerator(client)
        game = await generator.generate(theme="haunted lighthouse", num_rooms=5)

        # Import engine here to avoid circular imports in test setup
        from text_adventure.engine.engine import GameEngine

        # Should be able to create an engine and process commands
        engine = GameEngine(game)
        result = engine.process_input("look")
        assert not result.error
        assert "lighthouse" in result.message.lower()

    @pytest.mark.asyncio
    async def test_generator_fixes_missing_locations(self, mock_anthropic, client):
        """Generator fixes objects with missing locations."""
        # Game with object that has no location but is in room.objects
        game_data = {
            "metadata": {"title": "Test Game", "description": "A test."},
            "rooms": [
                {
                    "id": "room1",
                    "name": "Room One",
                    "description": "A room.",
                    "exits": {},
                    "objects": ["key"],
                }
            ],
            "objects": [
                {
                    "id": "key",
                    "name": "key",
                    "description": "A key.",
                    # NOTE: location is missing!
                }
            ],
            "initial_state": {"current_room": "room1"},
            "win_condition": {"type": "reach_room", "room": "room1"},
        }

        mock_anthropic.post("/v1/messages").mock(
            return_value=Response(
                200,
                json={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_123",
                            "name": "structured_response",
                            "input": game_data,
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 500, "output_tokens": 500},
                },
            )
        )

        generator = GameGenerator(client)
        game = await generator.generate(theme="test", num_rooms=1)

        # Object should now have location set
        key_obj = next(obj for obj in game.objects if obj.id == "key")
        assert key_obj.location == "room1"

    @pytest.mark.asyncio
    async def test_generator_adds_default_verbs(self, mock_anthropic, client):
        """Generator adds default verbs if none provided."""
        game_data = {
            "metadata": {"title": "Test Game", "description": "A test."},
            "rooms": [
                {
                    "id": "room1",
                    "name": "Room One",
                    "description": "A room.",
                    "exits": {},
                }
            ],
            "objects": [],
            "initial_state": {"current_room": "room1"},
            "win_condition": {"type": "reach_room", "room": "room1"},
            # NOTE: verbs not provided
        }

        mock_anthropic.post("/v1/messages").mock(
            return_value=Response(
                200,
                json={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_123",
                            "name": "structured_response",
                            "input": game_data,
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 500, "output_tokens": 500},
                },
            )
        )

        generator = GameGenerator(client)
        game = await generator.generate(theme="test", num_rooms=1)

        # Should have default verbs
        assert len(game.verbs) > 0
        verb_names = [v.verb for v in game.verbs]
        assert "take" in verb_names
        assert "examine" in verb_names
        assert "look" in verb_names

    @pytest.mark.asyncio
    async def test_generator_error_on_invalid_json(self, mock_anthropic, client):
        """Generator raises error when LLM returns invalid response."""
        mock_anthropic.post("/v1/messages").mock(
            return_value=Response(
                200,
                json={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Sorry, I cannot generate that."}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 500, "output_tokens": 50},
                },
            )
        )

        generator = GameGenerator(client)

        with pytest.raises(GameGenerationError, match="LLM failed to generate valid JSON"):
            await generator.generate(theme="test", num_rooms=1)

    @pytest.mark.asyncio
    async def test_generator_error_on_validation_failure(self, mock_anthropic, client):
        """Generator raises error when generated data fails validation."""
        # Game with invalid reference (room doesn't exist)
        game_data = {
            "metadata": {"title": "Test", "description": "Test"},
            "rooms": [
                {"id": "room1", "name": "Room", "description": "A room.", "exits": {"north": "nonexistent"}}
            ],
            "objects": [],
            "initial_state": {"current_room": "room1"},
            "win_condition": {"type": "reach_room", "room": "room1"},
        }

        mock_anthropic.post("/v1/messages").mock(
            return_value=Response(
                200,
                json={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [
                        {
                            "type": "tool_use",
                            "id": "tool_123",
                            "name": "structured_response",
                            "input": game_data,
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 500, "output_tokens": 500},
                },
            )
        )

        generator = GameGenerator(client)

        with pytest.raises(GameGenerationError, match="failed validation"):
            await generator.generate(theme="test", num_rooms=1)
