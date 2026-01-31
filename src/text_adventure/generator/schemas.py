"""
schemas.py

PURPOSE: JSON schemas for LLM-generated game content.
DEPENDENCIES: None (pure Python)

ARCHITECTURE NOTES:
These schemas define the structure of LLM output.
They are used with Claude's tool use feature to ensure valid JSON.
"""

# JSON schema for a complete game
GAME_SCHEMA = {
    "type": "object",
    "properties": {
        "metadata": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Title of the game"},
                "description": {
                    "type": "string",
                    "description": "Brief description of the game's premise",
                },
            },
            "required": ["title", "description"],
        },
        "rooms": {
            "type": "array",
            "description": "All rooms in the game",
            "items": {
                "type": "object",
                "properties": {
                    "id": {
                        "type": "string",
                        "description": "Unique ID (lowercase, underscores)",
                    },
                    "name": {"type": "string", "description": "Display name"},
                    "description": {
                        "type": "string",
                        "description": "2-4 sentence description",
                    },
                    "exits": {
                        "type": "object",
                        "description": "Map of direction to room_id or exit object",
                        "additionalProperties": {
                            "oneOf": [
                                {"type": "string"},
                                {
                                    "type": "object",
                                    "properties": {
                                        "target": {"type": "string"},
                                        "locked": {"type": "boolean"},
                                        "lock_message": {"type": "string"},
                                        "unlock_object": {"type": "string"},
                                    },
                                    "required": ["target"],
                                },
                            ]
                        },
                    },
                    "objects": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Object IDs in this room",
                    },
                    "ascii_art": {
                        "type": "string",
                        "description": "ASCII art representation (max 80 chars wide, 10-15 lines)",
                    },
                },
                "required": ["id", "name", "description", "exits"],
            },
        },
        "objects": {
            "type": "array",
            "description": "All objects in the game",
            "items": {
                "type": "object",
                "properties": {
                    "id": {"type": "string"},
                    "name": {"type": "string"},
                    "adjectives": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Words that can identify this object",
                    },
                    "description": {"type": "string"},
                    "examine_text": {
                        "type": "string",
                        "description": "Detailed text when examined",
                    },
                    "location": {
                        "type": "string",
                        "description": "Room ID or object ID for containers",
                    },
                    "takeable": {"type": "boolean", "default": True},
                    "scenery": {"type": "boolean", "default": False},
                    "readable": {"type": "boolean", "default": False},
                    "read_text": {"type": "string"},
                    "openable": {"type": "boolean", "default": False},
                    "container": {"type": "boolean", "default": False},
                    "contains": {"type": "array", "items": {"type": "string"}},
                    "lockable": {"type": "boolean", "default": False},
                    "locked": {"type": "boolean", "default": False},
                    "key_object": {"type": "string"},
                    "actions": {
                        "type": "object",
                        "description": "Custom action handlers",
                        "additionalProperties": {
                            "oneOf": [
                                {"type": "string"},
                                {
                                    "type": "object",
                                    "properties": {
                                        "message": {"type": "string"},
                                        "condition": {"type": "string"},
                                        "fail_message": {"type": "string"},
                                        "state_changes": {"type": "object"},
                                        "reveals_object": {"type": "string"},
                                        "moves_player": {"type": "string"},
                                    },
                                    "required": ["message"],
                                },
                            ]
                        },
                    },
                },
                "required": ["id", "name", "description", "location"],
            },
        },
        "initial_state": {
            "type": "object",
            "properties": {
                "current_room": {"type": "string"},
                "inventory": {"type": "array", "items": {"type": "string"}},
                "flags": {"type": "object"},
            },
            "required": ["current_room"],
        },
        "win_condition": {
            "type": "object",
            "properties": {
                "type": {
                    "type": "string",
                    "enum": [
                        "reach_room",
                        "have_object",
                        "flag_set",
                        "all_of",
                        "any_of",
                    ],
                },
                "room": {"type": "string"},
                "object": {"type": "string"},
                "flag": {"type": "string"},
                "win_message": {"type": "string"},
            },
            "required": ["type"],
        },
    },
    "required": ["metadata", "rooms", "objects", "initial_state", "win_condition"],
}
