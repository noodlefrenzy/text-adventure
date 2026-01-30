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
