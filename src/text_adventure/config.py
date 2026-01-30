"""
config.py

PURPOSE: Configuration loading and settings management.
DEPENDENCIES: pydantic

ARCHITECTURE NOTES:
Configuration comes from multiple sources (in priority order):
1. CLI flags (highest priority)
2. Environment variables
3. Config file (~/.text-adventure/config.toml)
4. Defaults (lowest priority)
"""

import os
from pathlib import Path
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings


class LLMSettings(BaseSettings):
    """Settings for LLM backends."""

    provider: Literal["anthropic", "ollama"] = Field(
        default="anthropic",
        description="LLM provider to use",
    )
    model: str = Field(
        default="claude-sonnet-4-20250514",
        description="Model name/ID",
    )
    temperature: float = Field(
        default=0.7,
        ge=0.0,
        le=2.0,
        description="Sampling temperature",
    )
    max_tokens: int = Field(
        default=4096,
        gt=0,
        description="Maximum tokens in response",
    )

    # Anthropic-specific
    anthropic_api_key: str = Field(
        default="",
        description="Anthropic API key (or set ANTHROPIC_API_KEY env var)",
    )

    # Ollama-specific
    ollama_host: str = Field(
        default="http://localhost:11434",
        description="Ollama server URL",
    )

    model_config = {"env_prefix": "TEXT_ADVENTURE_LLM_"}


class Settings(BaseSettings):
    """Main application settings."""

    data_dir: Path = Field(
        default_factory=lambda: Path.home() / ".text-adventure",
        description="Directory for game files and data",
    )
    log_level: str = Field(
        default="INFO",
        description="Logging level",
    )
    debug: bool = Field(
        default=False,
        description="Enable debug output",
    )
    llm: LLMSettings = Field(
        default_factory=LLMSettings,
        description="LLM settings",
    )

    model_config = {"env_prefix": "TEXT_ADVENTURE_"}

    def ensure_data_dir(self) -> Path:
        """Ensure data directory exists and return it."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        return self.data_dir

    def games_dir(self) -> Path:
        """Get the games directory."""
        games = self.data_dir / "games"
        games.mkdir(parents=True, exist_ok=True)
        return games


def get_settings() -> Settings:
    """Get application settings, loading from environment."""
    # Check for Anthropic API key in standard env var
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")

    llm_settings = LLMSettings(
        anthropic_api_key=api_key,
    )

    return Settings(llm=llm_settings)
