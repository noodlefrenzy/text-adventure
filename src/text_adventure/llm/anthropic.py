"""
anthropic.py

PURPOSE: Anthropic Claude LLM client implementation.
DEPENDENCIES: anthropic SDK

ARCHITECTURE NOTES:
Uses the Anthropic Python SDK to communicate with Claude.
Supports:
- Standard completions
- Structured JSON output
- Token counting for cost tracking
"""

import json
import logging
from typing import Any

import anthropic

from text_adventure.llm.client import LLMClient, LLMRequest, LLMResponse

logger = logging.getLogger(__name__)


class AnthropicClient(LLMClient):
    """
    LLM client using Anthropic's Claude API.

    Supports both standard and structured JSON completions.
    """

    def __init__(
        self,
        api_key: str | None = None,
        model: str = "claude-sonnet-4-20250514",
    ):
        """
        Initialize the Anthropic client.

        Args:
            api_key: Anthropic API key. If None, uses ANTHROPIC_API_KEY env var.
            model: Model to use for completions.
        """
        self._client = anthropic.AsyncAnthropic(api_key=api_key)
        self._model = model

    @property
    def model_name(self) -> str:
        """Return the model name."""
        return self._model

    async def complete(self, request: LLMRequest) -> LLMResponse:
        """
        Send a completion request to Claude.

        Args:
            request: The request containing messages and parameters

        Returns:
            LLMResponse with the generated content
        """
        # Convert messages to Anthropic format
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
            if msg.role != "system"
        ]

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": request.max_tokens,
            "messages": messages,
        }

        if request.temperature is not None:
            kwargs["temperature"] = request.temperature

        if request.system:
            kwargs["system"] = request.system

        logger.debug(f"Sending request to {self._model}")

        response = await self._client.messages.create(**kwargs)

        # Extract text content
        content = ""
        for block in response.content:
            if block.type == "text":
                content += block.text

        logger.debug(
            f"Response: {response.usage.input_tokens} in, {response.usage.output_tokens} out"
        )

        return LLMResponse(
            content=content,
            model=response.model,
            input_tokens=response.usage.input_tokens,
            output_tokens=response.usage.output_tokens,
            stop_reason=response.stop_reason,
            raw_response=response,
        )

    async def complete_json(
        self,
        request: LLMRequest,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Request a JSON-structured response from Claude.

        Uses Claude's tool use feature for guaranteed JSON structure.

        Args:
            request: The request containing messages
            schema: JSON schema for the expected response

        Returns:
            Parsed JSON response

        Raises:
            ValueError: If response cannot be parsed as valid JSON
        """
        # Convert messages to Anthropic format
        messages = [
            {"role": msg.role, "content": msg.content}
            for msg in request.messages
            if msg.role != "system"
        ]

        # Define a tool that returns the structured data
        tool_name = "structured_response"
        tools = [
            {
                "name": tool_name,
                "description": "Return the structured response",
                "input_schema": schema,
            }
        ]

        kwargs: dict[str, Any] = {
            "model": self._model,
            "max_tokens": request.max_tokens,
            "messages": messages,
            "tools": tools,
            "tool_choice": {"type": "tool", "name": tool_name},
        }

        if request.temperature is not None:
            kwargs["temperature"] = request.temperature

        if request.system:
            kwargs["system"] = request.system

        logger.debug(f"Sending JSON request to {self._model}")

        response = await self._client.messages.create(**kwargs)

        # Extract tool use result
        for block in response.content:
            if block.type == "tool_use" and block.name == tool_name:
                logger.debug(
                    f"JSON response: {response.usage.input_tokens} in, "
                    f"{response.usage.output_tokens} out"
                )
                return dict(block.input)

        # Fallback: try to parse text content as JSON
        for block in response.content:
            if block.type == "text":
                try:
                    result: dict[str, Any] = json.loads(block.text)
                    return result
                except json.JSONDecodeError:
                    pass

        raise ValueError("Failed to get structured JSON response from Claude")


def create_anthropic_client(
    api_key: str | None = None,
    model: str = "claude-sonnet-4-20250514",
) -> AnthropicClient:
    """
    Factory function to create an Anthropic client.

    Args:
        api_key: Optional API key (uses env var if not provided)
        model: Model to use

    Returns:
        Configured AnthropicClient
    """
    return AnthropicClient(api_key=api_key, model=model)
