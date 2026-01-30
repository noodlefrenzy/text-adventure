"""
conftest.py

Shared pytest fixtures for text_adventure tests.
"""

import json
from pathlib import Path

import pytest

from text_adventure.models.game import Game
from text_adventure.models.state import GameState

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def sample_game_path() -> Path:
    """Path to the sample game JSON file."""
    return FIXTURES_DIR / "sample_game.json"


@pytest.fixture
def sample_game_dict(sample_game_path: Path) -> dict:
    """Load sample game as a dictionary."""
    with open(sample_game_path) as f:
        return json.load(f)


@pytest.fixture
def sample_game(sample_game_dict: dict) -> Game:
    """Load and validate the sample game."""
    return Game.model_validate(sample_game_dict)


@pytest.fixture
def sample_game_state(sample_game: Game) -> GameState:
    """Create initial game state from sample game."""
    return GameState.from_game(sample_game)


@pytest.fixture
def minimal_game_dict() -> dict:
    """A minimal valid game for testing."""
    return {
        "metadata": {
            "title": "Minimal Test Game",
        },
        "rooms": [
            {
                "id": "start",
                "name": "Starting Room",
                "description": "A simple room.",
                "exits": {},
            }
        ],
        "objects": [],
        "initial_state": {
            "current_room": "start",
        },
        "win_condition": {
            "type": "reach_room",
            "room": "start",
        },
    }


@pytest.fixture
def minimal_game(minimal_game_dict: dict) -> Game:
    """Create minimal game from dict."""
    return Game.model_validate(minimal_game_dict)


# ============================================================================
# LLM Response Fixtures for Generator Transform Tests
# ============================================================================
# These fixtures reproduce known LLM output issues for testing robustness.


@pytest.fixture
def llm_response_with_invalid_ids() -> dict:
    """Mock LLM response with IDs that need sanitization.

    Issues:
    - Room IDs contain hyphens: "room-1", "room-2"
    - Object IDs contain hyphens: "brass-key"
    - Exit targets reference invalid room IDs
    """
    return {
        "metadata": {"title": "Test Game", "description": "A test game."},
        "rooms": [
            {
                "id": "room-1",
                "name": "First Room",
                "description": "You are in the first room.",
                "exits": {"north": "room-2"},
                "objects": ["brass-key"],
            },
            {
                "id": "room-2",
                "name": "Second Room",
                "description": "You are in the second room.",
                "exits": {"south": "room-1"},
                "objects": [],
            },
        ],
        "objects": [
            {
                "id": "brass-key",
                "name": "brass key",
                "adjectives": ["brass", "small"],
                "description": "A small brass key.",
                "location": "room-1",
                "takeable": True,
            }
        ],
        "initial_state": {"current_room": "room-1", "inventory": []},
        "win_condition": {"type": "reach_room", "room": "room-2"},
    }


@pytest.fixture
def llm_response_with_phantom_objects() -> dict:
    """Mock LLM response where room references non-existent objects.

    Issues:
    - Room lists objects ["key", "taxi", "ghost_npc"] but only "key" exists
    - "taxi" and "ghost_npc" are phantom references
    """
    return {
        "metadata": {"title": "Test Game", "description": "A test game."},
        "rooms": [
            {
                "id": "entrance",
                "name": "Entrance",
                "description": "The entrance hall.",
                "exits": {},
                "objects": ["key", "taxi", "ghost_npc"],
            }
        ],
        "objects": [
            {
                "id": "key",
                "name": "key",
                "description": "A simple key.",
                "location": "entrance",
                "takeable": True,
            }
            # Note: "taxi" and "ghost_npc" are NOT defined
        ],
        "initial_state": {"current_room": "entrance", "inventory": []},
        "win_condition": {"type": "have_object", "object": "key"},
    }


@pytest.fixture
def llm_response_with_malformed_actions() -> dict:
    """Mock LLM response with actions missing required 'message' field.

    Issues:
    - "machine" has actions without message field
    - Both "use" and "kick" actions are missing messages
    """
    return {
        "metadata": {"title": "Test Game", "description": "A test game."},
        "rooms": [
            {
                "id": "room",
                "name": "Room",
                "description": "A room with a machine.",
                "exits": {},
                "objects": ["machine"],
            }
        ],
        "objects": [
            {
                "id": "machine",
                "name": "vending machine",
                "description": "A strange vending machine.",
                "location": "room",
                "takeable": False,
                "actions": {
                    "use": {
                        # Missing "message" field!
                        "condition": "flags.has_coin",
                        "state_changes": {"flags.used_machine": True},
                    },
                    "kick": {
                        # Missing "message" field!
                        "reveals_object": "hidden_coin",
                    },
                },
            },
            {
                "id": "hidden_coin",
                "name": "coin",
                "description": "A coin.",
                "location": "nowhere",
                "takeable": True,
                "hidden": True,
            },
        ],
        "initial_state": {"current_room": "room", "inventory": []},
        "win_condition": {"type": "flag_set", "flag": "used_machine"},
    }


@pytest.fixture
def llm_response_with_multiple_issues() -> dict:
    """Mock LLM response with ALL known issues combined.

    Issues:
    - Invalid IDs (hyphens)
    - Phantom object references
    - Malformed actions (missing message)
    """
    return {
        "metadata": {"title": "Combined Test", "description": "Tests all issues."},
        "rooms": [
            {
                "id": "start-room",
                "name": "Start",
                "description": "Starting room.",
                "exits": {"north": "end-room"},
                "objects": ["magic-wand", "phantom-item"],
            },
            {
                "id": "end-room",
                "name": "End",
                "description": "Ending room.",
                "exits": {"south": "start-room"},
                "objects": [],
            },
        ],
        "objects": [
            {
                "id": "magic-wand",
                "name": "magic wand",
                "description": "A wand.",
                "location": "start-room",
                "takeable": True,
                "actions": {
                    "wave": {
                        # Missing message!
                        "state_changes": {"flags.waved": True},
                    },
                },
            }
            # "phantom-item" not defined!
        ],
        "initial_state": {"current_room": "start-room", "inventory": []},
        "win_condition": {"type": "reach_room", "room": "end-room"},
    }
