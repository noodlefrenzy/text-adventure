"""
TEST DOC: AI Player

WHAT: Tests for the LLM-based AI player
WHY: Ensure AI player can navigate and play games correctly
HOW: Use respx to mock Anthropic API responses with realistic commands

CASES:
- AI player explores rooms
- AI player collects items
- AI player can complete simple games
- AI player gives up when stuck

EDGE CASES:
- AI player handles errors gracefully
- AI player respects max_turns limit
"""

import pytest
import respx
from httpx import Response

from text_adventure.llm.anthropic import AnthropicClient
from text_adventure.models.game import Game
from text_adventure.player import AIPlayer, PlaySession


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
def simple_game():
    """A simple two-room game for testing."""
    return Game.model_validate(
        {
            "metadata": {
                "title": "Simple Test Game",
                "description": "A simple two-room test game.",
            },
            "rooms": [
                {
                    "id": "start",
                    "name": "Starting Room",
                    "description": "You are in a plain room. There is an exit to the north.",
                    "exits": {"north": "goal"},
                    "objects": ["key"],
                },
                {
                    "id": "goal",
                    "name": "Goal Room",
                    "description": "You made it! This is the goal room.",
                    "exits": {"south": "start"},
                    "objects": [],
                },
            ],
            "objects": [
                {
                    "id": "key",
                    "name": "brass key",
                    "adjectives": ["brass", "small"],
                    "description": "A small brass key.",
                    "location": "start",
                    "takeable": True,
                },
            ],
            "initial_state": {
                "current_room": "start",
                "inventory": [],
            },
            "win_condition": {
                "type": "reach_room",
                "room": "goal",
                "win_message": "You win!",
            },
        }
    )


def make_llm_response(text: str) -> Response:
    """Create a mock LLM response."""
    return Response(
        200,
        json={
            "id": "msg_123",
            "type": "message",
            "role": "assistant",
            "model": "claude-sonnet-4-20250514",
            "content": [{"type": "text", "text": text}],
            "stop_reason": "end_turn",
            "usage": {"input_tokens": 100, "output_tokens": 10},
        },
    )


class TestAIPlayer:
    """Tests for the AI player."""

    @pytest.mark.asyncio
    async def test_ai_player_explores_rooms(self, mock_anthropic, client, simple_game):
        """AI player explores rooms based on LLM commands."""
        # Mock LLM to return "NORTH" command
        mock_anthropic.post("/v1/messages").mock(
            side_effect=[
                make_llm_response("NORTH"),  # First turn: go north to goal
            ]
        )

        player = AIPlayer(client)
        session = await player.play(simple_game, max_turns=1)

        assert session.turns == 1
        assert "start" in session.rooms_visited
        assert "goal" in session.rooms_visited
        assert session.won  # Should win by reaching goal room

    @pytest.mark.asyncio
    async def test_ai_player_collects_items(self, mock_anthropic, client, simple_game):
        """AI player can collect items."""
        mock_anthropic.post("/v1/messages").mock(
            side_effect=[
                make_llm_response("TAKE KEY"),
                make_llm_response("NORTH"),
            ]
        )

        player = AIPlayer(client)
        session = await player.play(simple_game, max_turns=2)

        assert "key" in session.items_collected
        assert session.won

    @pytest.mark.asyncio
    async def test_ai_player_respects_max_turns(self, mock_anthropic, client, simple_game):
        """AI player stops after max_turns."""
        # Mock LLM to just look around
        mock_anthropic.post("/v1/messages").mock(
            side_effect=[make_llm_response("LOOK") for _ in range(5)]
        )

        player = AIPlayer(client)
        session = await player.play(simple_game, max_turns=5)

        assert session.turns == 5
        assert not session.won  # Didn't go north

    @pytest.mark.asyncio
    async def test_ai_player_gives_up_when_stuck(self, mock_anthropic, client, simple_game):
        """AI player gives up after too many failed commands."""
        # Mock LLM to issue invalid commands
        mock_anthropic.post("/v1/messages").mock(
            side_effect=[make_llm_response("GO NOWHERE") for _ in range(15)]
        )

        player = AIPlayer(client, max_stuck_turns=10)
        session = await player.play(simple_game, max_turns=100)

        assert session.gave_up
        assert session.stuck_count >= 10

    @pytest.mark.asyncio
    async def test_ai_player_callback(self, mock_anthropic, client, simple_game):
        """AI player calls on_turn callback."""
        mock_anthropic.post("/v1/messages").mock(
            side_effect=[
                make_llm_response("LOOK"),
                make_llm_response("NORTH"),
            ]
        )

        turns_recorded = []

        def on_turn(turn, command, result):
            turns_recorded.append((turn, command, result.message))

        player = AIPlayer(client)
        await player.play(simple_game, max_turns=2, on_turn=on_turn)

        assert len(turns_recorded) == 2
        assert turns_recorded[0][0] == 1
        assert turns_recorded[0][1] == "LOOK"
        assert turns_recorded[1][0] == 2
        assert turns_recorded[1][1] == "NORTH"

    @pytest.mark.asyncio
    async def test_ai_player_handles_multiline_response(self, mock_anthropic, client, simple_game):
        """AI player handles LLM responses with extra text."""
        mock_anthropic.post("/v1/messages").mock(
            side_effect=[
                make_llm_response("NORTH\n\nI'm going north to explore."),
            ]
        )

        player = AIPlayer(client)
        session = await player.play(simple_game, max_turns=1)

        # Should extract just "NORTH" and win
        assert session.commands_issued[0] == "NORTH"
        assert session.won

    @pytest.mark.asyncio
    async def test_ai_player_handles_quoted_response(self, mock_anthropic, client, simple_game):
        """AI player handles LLM responses with quotes."""
        mock_anthropic.post("/v1/messages").mock(
            side_effect=[
                make_llm_response('"NORTH"'),
            ]
        )

        player = AIPlayer(client)
        session = await player.play(simple_game, max_turns=1)

        assert session.commands_issued[0] == "NORTH"
        assert session.won


class TestPlaySession:
    """Tests for the PlaySession dataclass."""

    def test_play_session_defaults(self):
        """PlaySession has correct defaults."""
        session = PlaySession()

        assert session.turns == 0
        assert session.commands_issued == []
        assert session.responses_received == []
        assert session.rooms_visited == set()
        assert session.items_collected == []
        assert not session.won
        assert not session.gave_up
        assert session.stuck_count == 0
