"""
TEST DOC: LLM Client

WHAT: Tests for the LLM client infrastructure
WHY: Ensure LLM integration works correctly with mocked responses
HOW: Use respx to mock HTTP calls to Anthropic API

CASES:
- Basic completion
- JSON structured output
- Error handling

EDGE CASES:
- Missing API key
- Invalid JSON response
"""

import pytest
import respx
from httpx import Response

from text_adventure.llm.anthropic import AnthropicClient
from text_adventure.llm.client import LLMMessage, LLMRequest


@pytest.fixture
def mock_anthropic():
    """Set up respx mock for Anthropic API."""
    with respx.mock(base_url="https://api.anthropic.com") as respx_mock:
        yield respx_mock


@pytest.fixture
def client():
    """Create a test client with a dummy API key."""
    return AnthropicClient(api_key="test-api-key", model="claude-sonnet-4-20250514")


class TestAnthropicClient:
    """Tests for the Anthropic client."""

    @pytest.mark.asyncio
    async def test_complete_basic(self, mock_anthropic, client):
        """Basic completion returns response."""
        mock_anthropic.post("/v1/messages").mock(
            return_value=Response(
                200,
                json={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Hello, world!"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 10, "output_tokens": 5},
                },
            )
        )

        request = LLMRequest(
            messages=[LLMMessage(role="user", content="Say hello")],
        )
        response = await client.complete(request)

        assert response.content == "Hello, world!"
        assert response.model == "claude-sonnet-4-20250514"
        assert response.input_tokens == 10
        assert response.output_tokens == 5

    @pytest.mark.asyncio
    async def test_complete_with_system(self, mock_anthropic, client):
        """Completion with system message works."""
        mock_anthropic.post("/v1/messages").mock(
            return_value=Response(
                200,
                json={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "I am a pirate!"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 20, "output_tokens": 10},
                },
            )
        )

        request = LLMRequest(
            messages=[LLMMessage(role="user", content="Who are you?")],
            system="You are a pirate.",
        )
        response = await client.complete(request)

        assert "pirate" in response.content.lower()

    @pytest.mark.asyncio
    async def test_complete_json(self, mock_anthropic, client):
        """JSON completion with tool use works."""
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
                            "input": {"name": "Test", "count": 42},
                        }
                    ],
                    "stop_reason": "tool_use",
                    "usage": {"input_tokens": 30, "output_tokens": 15},
                },
            )
        )

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
            "required": ["name", "count"],
        }

        request = LLMRequest(
            messages=[LLMMessage(role="user", content="Generate data")],
        )
        result = await client.complete_json(request, schema)

        assert result["name"] == "Test"
        assert result["count"] == 42

    @pytest.mark.asyncio
    async def test_model_name(self, client):
        """Model name property returns correct value."""
        assert client.model_name == "claude-sonnet-4-20250514"

    @pytest.mark.asyncio
    async def test_complete_json_fallback_text(self, mock_anthropic, client):
        """JSON completion falls back to text parsing."""
        mock_anthropic.post("/v1/messages").mock(
            return_value=Response(
                200,
                json={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": '{"name": "Fallback", "count": 1}'}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 30, "output_tokens": 15},
                },
            )
        )

        schema = {
            "type": "object",
            "properties": {
                "name": {"type": "string"},
                "count": {"type": "integer"},
            },
        }

        request = LLMRequest(
            messages=[LLMMessage(role="user", content="Generate data")],
        )
        result = await client.complete_json(request, schema)

        assert result["name"] == "Fallback"

    @pytest.mark.asyncio
    async def test_complete_json_invalid_response(self, mock_anthropic, client):
        """Invalid JSON response raises error."""
        mock_anthropic.post("/v1/messages").mock(
            return_value=Response(
                200,
                json={
                    "id": "msg_123",
                    "type": "message",
                    "role": "assistant",
                    "model": "claude-sonnet-4-20250514",
                    "content": [{"type": "text", "text": "Not valid JSON"}],
                    "stop_reason": "end_turn",
                    "usage": {"input_tokens": 30, "output_tokens": 15},
                },
            )
        )

        schema = {"type": "object"}
        request = LLMRequest(
            messages=[LLMMessage(role="user", content="Generate data")],
        )

        with pytest.raises(ValueError, match="Failed to get structured JSON"):
            await client.complete_json(request, schema)
