"""
generator.py

PURPOSE: LLM-based game generation.
DEPENDENCIES: anthropic SDK, pydantic models

ARCHITECTURE NOTES:
The generator uses Claude's structured output feature to ensure
valid JSON responses that match our game schema.
Includes OpenTelemetry tracing for observability.
"""

import logging
import re
from typing import Any

from pydantic import ValidationError

from text_adventure.generator.prompts import GENERATION_PROMPT_TEMPLATE, SYSTEM_PROMPT
from text_adventure.generator.schemas import GAME_SCHEMA
from text_adventure.llm.client import LLMClient, LLMMessage, LLMRequest
from text_adventure.models.game import Game
from text_adventure.observability import get_tracer

logger = logging.getLogger(__name__)
tracer = get_tracer(__name__)


class GameGenerationError(Exception):
    """Error during game generation."""

    pass


class GameGenerator:
    """
    Generates text adventure games using an LLM.

    Uses structured output (tool use) to ensure valid JSON responses.
    """

    def __init__(self, client: LLMClient):
        """
        Initialize the generator.

        Args:
            client: The LLM client to use for generation.
        """
        self._client = client

    async def generate(
        self,
        theme: str,
        num_rooms: int = 8,
        max_tokens: int = 8192,
        temperature: float = 0.7,
    ) -> Game:
        """
        Generate a new text adventure game.

        Args:
            theme: The theme or setting for the game (e.g., "haunted mansion").
            num_rooms: Number of rooms to generate (default 8).
            max_tokens: Maximum tokens for the response.
            temperature: Creativity level (0.0-1.0).

        Returns:
            A validated Game object.

        Raises:
            GameGenerationError: If generation fails or produces invalid output.
        """
        with tracer.start_as_current_span("game.generate") as span:
            span.set_attribute("game.theme", theme)
            span.set_attribute("game.num_rooms", num_rooms)
            span.set_attribute("game.temperature", temperature)
            span.add_event("generation_started")

            logger.info(f"Generating game with theme '{theme}', {num_rooms} rooms")

            # Build the prompt
            user_prompt = GENERATION_PROMPT_TEMPLATE.format(
                theme=theme,
                num_rooms=num_rooms,
            )

            request = LLMRequest(
                messages=[LLMMessage(role="user", content=user_prompt)],
                system=SYSTEM_PROMPT,
                max_tokens=max_tokens,
                temperature=temperature,
            )

            try:
                # Get structured JSON response (child span created by LLM client)
                game_data = await self._client.complete_json(request, GAME_SCHEMA)
                logger.debug(f"Received game data with {len(game_data.get('rooms', []))} rooms")

                # Validate against our Pydantic model
                with tracer.start_as_current_span("game.validate") as validate_span:
                    game = self._validate_game(game_data)
                    validate_span.set_attribute("game.rooms_count", len(game.rooms))
                    validate_span.set_attribute("game.objects_count", len(game.objects))
                    validate_span.add_event("validation_complete")

                span.set_attribute("game.title", game.metadata.title)
                span.set_attribute("game.rooms_count", len(game.rooms))
                span.set_attribute("game.objects_count", len(game.objects))
                span.add_event("game_generated")

                logger.info(f"Successfully generated game: {game.metadata.title}")
                return game

            except ValidationError as e:
                span.record_exception(e)
                span.set_attribute("game.error", "validation_failed")
                # Catch ValidationError first since it inherits from ValueError
                raise GameGenerationError(f"Generated game failed validation: {e}") from e
            except ValueError as e:
                span.record_exception(e)
                span.set_attribute("game.error", "json_failed")
                raise GameGenerationError(f"LLM failed to generate valid JSON: {e}") from e

    def _validate_game(self, game_data: dict[str, Any]) -> Game:
        """
        Validate and transform raw game data into a Game object.

        Performs any necessary transformations to fix common LLM output issues.

        Args:
            game_data: Raw game data from the LLM.

        Returns:
            A validated Game object.
        """
        # Transform the data to match our model expectations
        transformed = self._transform_game_data(game_data)

        # Validate with Pydantic
        return Game.model_validate(transformed)

    def _transform_game_data(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        Transform LLM output to match our Pydantic model expectations.

        Handles common issues like:
        - Missing optional fields
        - Inconsistent naming conventions
        - Object locations that need to be inferred

        Args:
            data: Raw game data from the LLM.

        Returns:
            Transformed data ready for validation.
        """
        result = dict(data)

        # Ensure metadata has required fields
        if "metadata" not in result:
            result["metadata"] = {}
        if "title" not in result["metadata"]:
            result["metadata"]["title"] = "Untitled Adventure"
        if "description" not in result["metadata"]:
            result["metadata"]["description"] = "A text adventure game."

        # Sanitize IDs to match the expected pattern and collect mappings
        room_id_map: dict[str, str] = {}
        object_id_map: dict[str, str] = {}

        if "rooms" in result:
            result["rooms"], room_id_map = self._sanitize_room_ids(result["rooms"])
        if "objects" in result:
            result["objects"], object_id_map = self._sanitize_object_ids(
                result["objects"], room_id_map
            )
            # Fix malformed action objects
            result["objects"] = self._fix_object_actions(result["objects"])

        # Update room.objects to use sanitized object IDs
        if "rooms" in result and object_id_map:
            for room in result["rooms"]:
                if "objects" in room:
                    room["objects"] = [
                        object_id_map.get(oid, oid) for oid in room["objects"]
                    ]

        # Ensure objects have locations and rooms only reference existing objects
        if "objects" in result and "rooms" in result:
            result["objects"] = self._fix_object_locations(
                result["objects"],
                result["rooms"],
            )
            # Clean up room object references to only include objects that exist
            logger.debug(f"Before fix_room_object_references: {len(result['rooms'])} rooms, {len(result['objects'])} objects")
            logger.debug(f"Object IDs: {[obj.get('id') for obj in result['objects']]}")
            result["rooms"] = self._fix_room_object_references(
                result["rooms"],
                result["objects"],
            )
            logger.debug(f"After fix_room_object_references: {[r.get('objects', []) for r in result['rooms']]}")

        # Ensure initial_state has required fields
        if "initial_state" not in result:
            result["initial_state"] = {}
        # Default to first room if current_room not specified
        if "current_room" not in result["initial_state"] and result.get("rooms"):
            result["initial_state"]["current_room"] = result["rooms"][0]["id"]
        elif "current_room" in result["initial_state"] and room_id_map:
            # Update to sanitized room ID
            old_room = result["initial_state"]["current_room"]
            result["initial_state"]["current_room"] = room_id_map.get(old_room, old_room)
        if "inventory" not in result["initial_state"]:
            result["initial_state"]["inventory"] = []
        elif object_id_map:
            # Update inventory to sanitized object IDs
            result["initial_state"]["inventory"] = [
                object_id_map.get(oid, oid)
                for oid in result["initial_state"]["inventory"]
            ]

        # Ensure win_condition has required fields
        if "win_condition" not in result:
            result["win_condition"] = {"type": "reach_room"}
            if result.get("rooms"):
                result["win_condition"]["room"] = result["rooms"][-1]["id"]
        else:
            # Update win_condition references to sanitized IDs
            wc = result["win_condition"]
            if wc.get("type") == "reach_room" and "room" in wc and room_id_map:
                wc["room"] = room_id_map.get(wc["room"], wc["room"])
            elif wc.get("type") == "have_object" and "object" in wc and object_id_map:
                wc["object"] = object_id_map.get(wc["object"], wc["object"])

        # Add default verbs if missing
        if "verbs" not in result or not result["verbs"]:
            result["verbs"] = self._default_verbs()

        return result

    def _sanitize_id(self, raw_id: str) -> str:
        """
        Sanitize an ID to match the pattern ^[a-z][a-z0-9_]*$.

        - Converts to lowercase
        - Replaces hyphens and spaces with underscores
        - Removes other invalid characters
        - Ensures it starts with a letter
        """
        if not raw_id:
            return "unknown"

        # Lowercase and replace hyphens/spaces with underscores
        sanitized = raw_id.lower().replace("-", "_").replace(" ", "_")

        # Remove any character that's not lowercase letter, number, or underscore
        sanitized = re.sub(r"[^a-z0-9_]", "", sanitized)

        # Collapse multiple underscores
        sanitized = re.sub(r"_+", "_", sanitized)

        # Remove leading/trailing underscores
        sanitized = sanitized.strip("_")

        # Ensure starts with a letter
        if not sanitized or not sanitized[0].isalpha():
            sanitized = "obj_" + sanitized if sanitized else "unknown"

        return sanitized

    def _sanitize_room_ids(
        self,
        rooms: list[dict[str, Any]],
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """Sanitize room IDs and update exit references.

        Returns:
            Tuple of (fixed_rooms, id_map) where id_map is old_id -> new_id.
        """
        id_map: dict[str, str] = {}  # old_id -> new_id

        # First pass: collect ID mappings
        for room in rooms:
            old_id = room.get("id", "")
            new_id = self._sanitize_id(old_id)
            if old_id != new_id:
                id_map[old_id] = new_id
                logger.debug(f"Sanitizing room ID: '{old_id}' -> '{new_id}'")

        # Second pass: update rooms and exit references
        fixed_rooms = []
        for room in rooms:
            room = dict(room)
            old_id = room.get("id", "")
            if old_id in id_map:
                room["id"] = id_map[old_id]

            # Update exit targets
            if "exits" in room:
                new_exits: dict[str, Any] = {}
                for direction, exit_value in room["exits"].items():
                    if isinstance(exit_value, str):
                        new_exits[direction] = id_map.get(exit_value, exit_value)
                    elif isinstance(exit_value, dict):
                        exit_dict = dict(exit_value)
                        if "target" in exit_dict:
                            exit_dict["target"] = id_map.get(exit_dict["target"], exit_dict["target"])
                        new_exits[direction] = exit_dict
                    else:
                        new_exits[direction] = exit_value
                room["exits"] = new_exits

            fixed_rooms.append(room)

        return fixed_rooms, id_map

    def _fix_object_actions(
        self,
        objects: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Fix malformed action objects in game objects.

        LLMs sometimes produce action dicts without the required 'message' field.

        Args:
            objects: List of object definitions.

        Returns:
            Objects with fixed actions.
        """
        fixed_objects = []
        for obj in objects:
            obj = dict(obj)
            if "actions" in obj and isinstance(obj["actions"], dict):
                fixed_actions: dict[str, Any] = {}
                for action_key, action_value in obj["actions"].items():
                    if isinstance(action_value, str):
                        # Simple string action is fine
                        fixed_actions[action_key] = action_value
                    elif isinstance(action_value, dict):
                        # Ensure message field exists
                        action_dict = dict(action_value)
                        if "message" not in action_dict:
                            # Try to generate a sensible default message
                            verb = action_key.split(":")[0] if ":" in action_key else action_key
                            action_dict["message"] = f"You {verb} the {obj.get('name', 'object')}."
                            logger.warning(
                                f"Object '{obj.get('id')}' action '{action_key}' missing message, added default"
                            )
                        fixed_actions[action_key] = action_dict
                    else:
                        fixed_actions[action_key] = action_value
                obj["actions"] = fixed_actions
            fixed_objects.append(obj)
        return fixed_objects

    def _sanitize_object_ids(
        self,
        objects: list[dict[str, Any]],
        room_id_map: dict[str, str],
    ) -> tuple[list[dict[str, Any]], dict[str, str]]:
        """Sanitize object IDs and update any cross-references.

        Args:
            objects: List of object definitions.
            room_id_map: Mapping of old room IDs to sanitized IDs.

        Returns:
            Tuple of (fixed_objects, id_map) where id_map is old_id -> new_id.
        """
        id_map: dict[str, str] = {}  # old_id -> new_id

        # First pass: collect ID mappings
        for obj in objects:
            old_id = obj.get("id", "")
            new_id = self._sanitize_id(old_id)
            if old_id != new_id:
                id_map[old_id] = new_id
                logger.debug(f"Sanitizing object ID: '{old_id}' -> '{new_id}'")

        # Second pass: update objects
        fixed_objects = []
        for obj in objects:
            obj = dict(obj)
            old_id = obj.get("id", "")
            if old_id in id_map:
                obj["id"] = id_map[old_id]

            # Update key_object reference
            if "key_object" in obj and obj["key_object"] in id_map:
                obj["key_object"] = id_map[obj["key_object"]]

            # Update contains references
            if "contains" in obj:
                obj["contains"] = [
                    id_map.get(oid, oid) for oid in obj["contains"]
                ]

            # Update location to use sanitized room ID
            if "location" in obj and obj["location"] in room_id_map:
                obj["location"] = room_id_map[obj["location"]]

            fixed_objects.append(obj)

        return fixed_objects, id_map

    def _fix_object_locations(
        self,
        objects: list[dict[str, Any]],
        rooms: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Fix object locations based on room definitions.

        LLMs sometimes put objects in room.objects but don't set object.location.

        Args:
            objects: List of object definitions.
            rooms: List of room definitions.

        Returns:
            Objects with corrected locations.
        """
        # Build a map of object_id -> room_id from room.objects lists
        object_to_room: dict[str, str] = {}
        for room in rooms:
            room_id = room.get("id", "")
            for obj_id in room.get("objects", []):
                object_to_room[obj_id] = room_id

        # Fix object locations
        fixed_objects = []
        for obj in objects:
            obj = dict(obj)  # Copy to avoid modifying original
            obj_id = obj.get("id", "")

            if "location" not in obj or not obj["location"]:
                # Try to find location from room definitions
                if obj_id in object_to_room:
                    obj["location"] = object_to_room[obj_id]
                elif rooms:
                    # Default to first room if we can't find it
                    obj["location"] = rooms[0]["id"]
                    logger.warning(f"Object '{obj_id}' has no location, defaulting to first room")

            fixed_objects.append(obj)

        return fixed_objects

    def _fix_room_object_references(
        self,
        rooms: list[dict[str, Any]],
        objects: list[dict[str, Any]],
    ) -> list[dict[str, Any]]:
        """
        Remove references to non-existent objects from room definitions.

        LLMs sometimes reference objects in room.objects that don't exist
        in the objects array.

        Args:
            rooms: List of room definitions.
            objects: List of object definitions.

        Returns:
            Rooms with cleaned object references.
        """
        # Build set of valid object IDs
        valid_object_ids = {obj.get("id", "") for obj in objects}

        fixed_rooms = []
        for room in rooms:
            room = dict(room)  # Copy to avoid modifying original
            room_id = room.get("id", "")

            if "objects" in room:
                original_objects = room["objects"]
                room["objects"] = [
                    obj_id for obj_id in original_objects
                    if obj_id in valid_object_ids
                ]
                removed = set(original_objects) - set(room["objects"])
                if removed:
                    logger.warning(
                        f"Room '{room_id}' referenced non-existent objects: {removed}"
                    )

            fixed_rooms.append(room)

        return fixed_rooms

    def _default_verbs(self) -> list[dict[str, Any]]:
        """Return default verb definitions."""
        return [
            {"verb": "take", "aliases": ["get", "grab", "pick up"], "requires_object": True},
            {"verb": "drop", "aliases": ["put down", "discard"], "requires_object": True},
            {"verb": "examine", "aliases": ["look at", "x", "inspect"], "requires_object": True},
            {"verb": "open", "aliases": [], "requires_object": True},
            {"verb": "close", "aliases": ["shut"], "requires_object": True},
            {"verb": "read", "aliases": [], "requires_object": True},
            {"verb": "unlock", "aliases": [], "requires_object": True},
            {"verb": "lock", "aliases": [], "requires_object": True},
            {"verb": "put", "aliases": ["place", "insert"], "requires_object": True},
            {"verb": "inventory", "aliases": ["i"], "requires_object": False},
            {"verb": "look", "aliases": ["l"], "requires_object": False},
            {"verb": "go", "aliases": ["walk", "move"], "requires_object": True},
            {"verb": "quit", "aliases": ["exit", "q"], "requires_object": False},
            {"verb": "help", "aliases": ["?"], "requires_object": False},
        ]


async def generate_game(
    client: LLMClient,
    theme: str,
    num_rooms: int = 8,
    temperature: float = 0.7,
) -> Game:
    """
    Convenience function to generate a game.

    Args:
        client: LLM client to use.
        theme: Theme or setting for the game.
        num_rooms: Number of rooms.
        temperature: Creativity level.

    Returns:
        A validated Game object.
    """
    generator = GameGenerator(client)
    return await generator.generate(theme, num_rooms, temperature=temperature)
