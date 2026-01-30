"""
client.py

PURPOSE: Abstract LLM client interface.
DEPENDENCIES: None (pure Python + typing)

ARCHITECTURE NOTES:
This module defines the protocol that all LLM clients must implement.
Using a Protocol allows duck-typing without requiring inheritance.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LLMResponse:
    """Response from an LLM call."""

    content: str
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    stop_reason: str | None = None
    raw_response: Any = None


@dataclass
class LLMMessage:
    """A message in a conversation."""

    role: str  # "user", "assistant", or "system"
    content: str


@dataclass
class LLMRequest:
    """Request to an LLM."""

    messages: list[LLMMessage] = field(default_factory=list)
    system: str | None = None
    temperature: float = 0.7
    max_tokens: int = 4096
    json_schema: dict[str, Any] | None = None  # For structured output


class LLMClient(ABC):
    """Abstract base class for LLM clients."""

    @abstractmethod
    async def complete(self, request: LLMRequest) -> LLMResponse:
        """
        Send a completion request to the LLM.

        Args:
            request: The request containing messages and parameters

        Returns:
            LLMResponse with the generated content
        """
        ...

    @abstractmethod
    async def complete_json(
        self,
        request: LLMRequest,
        schema: dict[str, Any],
    ) -> dict[str, Any]:
        """
        Request a JSON-structured response.

        Args:
            request: The request containing messages
            schema: JSON schema for the expected response

        Returns:
            Parsed JSON response

        Raises:
            ValueError: If response cannot be parsed as valid JSON
        """
        ...

    @property
    @abstractmethod
    def model_name(self) -> str:
        """Return the name of the model being used."""
        ...
