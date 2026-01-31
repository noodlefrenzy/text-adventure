"""
ascii_art.py

PURPOSE: Generate ASCII art for game rooms using an LLM.
DEPENDENCIES: LLM client

ARCHITECTURE NOTES:
ASCII art generation is a two-pass process:
1. Generate the game first (without ASCII art)
2. Add ASCII art to each room in a separate LLM call

This separation allows:
- Better art quality with focused prompts
- Ability to retrofit existing games
- Better error recovery (game generation doesn't fail if art fails)
"""

import logging

from text_adventure.generator.prompts import (
    ASCII_ART_GENERATION_PROMPT,
    ASCII_ART_SYSTEM_PROMPT,
)
from text_adventure.llm.client import LLMClient, LLMMessage, LLMRequest
from text_adventure.models.game import Game
from text_adventure.observability import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


class AsciiArtGenerationError(Exception):
    """Error during ASCII art generation."""

    pass


class AsciiArtGenerator:
    """
    Generates ASCII art for text adventure game rooms.

    Uses an LLM to create atmospheric ASCII art that fits within
    terminal constraints (80 chars wide, 8-12 lines tall).
    """

    # Constraints for terminal art
    MAX_WIDTH = 78  # Leave margin for terminal
    MIN_HEIGHT = 8
    MAX_HEIGHT = 14

    def __init__(self, client: LLMClient):
        """
        Initialize the ASCII art generator.

        Args:
            client: The LLM client to use for generation.
        """
        self._client = client

    async def generate_for_game(
        self,
        game: Game,
        temperature: float = 0.8,
    ) -> Game:
        """
        Generate ASCII art for all rooms in a game.

        This modifies the game in-place by adding ascii_art to each room.
        If art generation fails for a room, that room is skipped with a warning.

        Args:
            game: The game to add ASCII art to.
            temperature: Creativity level for art generation.

        Returns:
            The game with ASCII art added to rooms.
        """
        with tracer.start_as_current_span("ascii_art.generate_for_game") as span:
            span.set_attribute("game.title", game.metadata.title)
            span.set_attribute("game.room_count", len(game.rooms))

            logger.info(f"Generating ASCII art for {len(game.rooms)} rooms")

            # Convert to dict for modification, then re-validate
            game_data = game.model_dump(mode="json")
            success_count = 0

            for i, room_data in enumerate(game_data["rooms"]):
                room_name = room_data["name"]
                room_description = room_data["description"]

                try:
                    art = await self.generate_for_room(
                        room_name=room_name,
                        room_description=room_description,
                        temperature=temperature,
                    )
                    game_data["rooms"][i]["ascii_art"] = art
                    success_count += 1
                    logger.debug(f"Generated art for room '{room_name}'")
                except AsciiArtGenerationError as e:
                    logger.warning(f"Failed to generate art for '{room_name}': {e}")
                    # Leave ascii_art as None for this room

            span.set_attribute("ascii_art.success_count", success_count)
            span.set_attribute("ascii_art.failed_count", len(game.rooms) - success_count)

            logger.info(
                f"Generated ASCII art for {success_count}/{len(game.rooms)} rooms"
            )

            # Re-validate and return
            return Game.model_validate(game_data)

    async def generate_for_room(
        self,
        room_name: str,
        room_description: str,
        temperature: float = 0.8,
    ) -> str:
        """
        Generate ASCII art for a single room.

        Args:
            room_name: The name of the room.
            room_description: The room's description.
            temperature: Creativity level.

        Returns:
            ASCII art string for the room.

        Raises:
            AsciiArtGenerationError: If generation fails.
        """
        with tracer.start_as_current_span("ascii_art.generate_for_room") as span:
            span.set_attribute("room.name", room_name)

            prompt = ASCII_ART_GENERATION_PROMPT.format(
                room_name=room_name,
                room_description=room_description,
            )

            request = LLMRequest(
                messages=[LLMMessage(role="user", content=prompt)],
                system=ASCII_ART_SYSTEM_PROMPT,
                max_tokens=1024,  # ASCII art is small
                temperature=temperature,
            )

            try:
                response = await self._client.complete(request)
                art = self._validate_and_clean_art(response.content)

                span.set_attribute("ascii_art.lines", len(art.split("\n")))
                span.set_attribute("ascii_art.width", max(len(line) for line in art.split("\n")))

                return art
            except ValueError as e:
                span.record_exception(e)
                raise AsciiArtGenerationError(f"Invalid ASCII art: {e}") from e

    def _validate_and_clean_art(self, raw_art: str) -> str:
        """
        Validate and clean terminal art from the LLM.

        Args:
            raw_art: Raw art string from the LLM.

        Returns:
            Cleaned art that meets constraints.

        Raises:
            ValueError: If art cannot be validated.
        """
        # Strip any markdown code blocks that might wrap the art
        art = raw_art.strip()
        if art.startswith("```"):
            # Remove opening fence
            first_newline = art.find("\n")
            if first_newline != -1:
                art = art[first_newline + 1:]
            # Remove closing fence
            if art.endswith("```"):
                art = art[:-3]
        art = art.strip()

        if not art:
            raise ValueError("Empty art")

        # Process lines
        lines = art.split("\n")

        # Enforce width constraint by truncating
        # Note: We allow Unicode characters for box-drawing and block elements
        cleaned_lines = []
        for line in lines:
            # Remove control characters but keep printable Unicode
            clean_line = "".join(c for c in line if c == "\t" or (ord(c) >= 32 and c.isprintable()))
            # Replace tabs with spaces
            clean_line = clean_line.replace("\t", "    ")
            # Truncate to max width (by characters, not bytes)
            if len(clean_line) > self.MAX_WIDTH:
                clean_line = clean_line[: self.MAX_WIDTH]
            # Strip trailing whitespace
            clean_line = clean_line.rstrip()
            cleaned_lines.append(clean_line)

        # Remove leading/trailing empty lines
        while cleaned_lines and not cleaned_lines[0]:
            cleaned_lines.pop(0)
        while cleaned_lines and not cleaned_lines[-1]:
            cleaned_lines.pop()

        # Enforce height constraint
        if len(cleaned_lines) > self.MAX_HEIGHT:
            cleaned_lines = cleaned_lines[: self.MAX_HEIGHT]

        if len(cleaned_lines) < 1:
            raise ValueError("Art too short")

        return "\n".join(cleaned_lines)


async def add_ascii_art_to_game(
    client: LLMClient,
    game: Game,
    temperature: float = 0.8,
) -> Game:
    """
    Convenience function to add ASCII art to a game.

    Args:
        client: LLM client to use.
        game: Game to add art to.
        temperature: Creativity level.

    Returns:
        Game with ASCII art added.
    """
    generator = AsciiArtGenerator(client)
    return await generator.generate_for_game(game, temperature=temperature)
