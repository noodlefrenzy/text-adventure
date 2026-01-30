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
- OpenTelemetry tracing (when enabled)
"""

import json
import logging
import time
from typing import Any

import anthropic

from text_adventure.llm.client import LLMClient, LLMRequest, LLMResponse
from text_adventure.observability import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


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
        with tracer.start_as_current_span("llm.complete") as span:
            span.set_attribute("llm.model", self._model)
            span.set_attribute("llm.max_tokens", request.max_tokens)
            span.set_attribute("llm.message_count", len(request.messages))
            if request.temperature is not None:
                span.set_attribute("llm.temperature", request.temperature)

            start_time = time.perf_counter()

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

            try:
                response = await self._client.messages.create(**kwargs)
            except Exception as e:
                span.record_exception(e)
                raise

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            # Extract text content
            content = ""
            for block in response.content:
                if block.type == "text":
                    content += block.text

            span.set_attribute("llm.input_tokens", response.usage.input_tokens)
            span.set_attribute("llm.output_tokens", response.usage.output_tokens)
            span.set_attribute("llm.latency_ms", elapsed_ms)
            span.set_attribute("llm.stop_reason", response.stop_reason or "unknown")

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
        with tracer.start_as_current_span("llm.complete_json") as span:
            span.set_attribute("llm.model", self._model)
            span.set_attribute("llm.max_tokens", request.max_tokens)
            span.set_attribute("llm.message_count", len(request.messages))
            span.set_attribute("llm.schema_name", schema.get("title", "unknown"))
            if request.temperature is not None:
                span.set_attribute("llm.temperature", request.temperature)

            start_time = time.perf_counter()

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

            try:
                response = await self._client.messages.create(**kwargs)
            except Exception as e:
                span.record_exception(e)
                raise

            elapsed_ms = (time.perf_counter() - start_time) * 1000

            span.set_attribute("llm.input_tokens", response.usage.input_tokens)
            span.set_attribute("llm.output_tokens", response.usage.output_tokens)
            span.set_attribute("llm.latency_ms", elapsed_ms)

            # Extract tool use result
            for block in response.content:
                if block.type == "tool_use" and block.name == tool_name:
                    logger.debug(
                        f"JSON response: {response.usage.input_tokens} in, "
                        f"{response.usage.output_tokens} out"
                    )
                    span.set_attribute("llm.response_type", "tool_use")
                    return dict(block.input)

            # Fallback: try to parse text content as JSON
            for block in response.content:
                if block.type == "text":
                    try:
                        result: dict[str, Any] = json.loads(block.text)
                        span.set_attribute("llm.response_type", "text_json")
                        return result
                    except json.JSONDecodeError:
                        pass

            span.set_attribute("llm.response_type", "failed")
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
