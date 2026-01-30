"""
state.py

PURPOSE: Mutable game state that changes during play.
DEPENDENCIES: pydantic, game.py

ARCHITECTURE NOTES:
GameState is separate from the static Game definition.
It tracks what has changed: player location, inventory, object states, etc.
The engine modifies state in response to commands.
State can be saved/loaded for game persistence.
"""

from copy import deepcopy
from typing import Any

from pydantic import BaseModel, Field

from text_adventure.models.game import Game, InitialState


class ObjectState(BaseModel):
    """
    Runtime state of a game object.

    Tracks mutable properties that can change during play.
    """

    location: str = Field(..., description="Current location: room_id, 'inventory', or 'nowhere'")
    is_open: bool = Field(default=False)
    locked: bool = Field(default=False)
    is_lit: bool = Field(default=False)
    worn: bool = Field(default=False)
    hidden: bool = Field(default=False)
    examined: bool = Field(default=False)
    custom: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom state for game-specific properties",
    )


class RoomState(BaseModel):
    """
    Runtime state of a room.

    Tracks mutable room properties.
    """

    visited: bool = Field(default=False)
    custom: dict[str, Any] = Field(
        default_factory=dict,
        description="Custom state for game-specific properties",
    )


class GameState(BaseModel):
    """
    Complete mutable state of a game in progress.

    This is what gets saved/loaded and modified during play.
    """

    current_room: str = Field(..., description="ID of the room the player is in")
    inventory: list[str] = Field(
        default_factory=list,
        description="Object IDs in the player's inventory",
    )
    turns: int = Field(default=0, description="Number of turns taken")
    score: int = Field(default=0, description="Player's current score")
    flags: dict[str, Any] = Field(
        default_factory=dict,
        description="Game-specific boolean/value flags",
    )
    objects: dict[str, ObjectState] = Field(
        default_factory=dict,
        description="State of each object by ID",
    )
    rooms: dict[str, RoomState] = Field(
        default_factory=dict,
        description="State of each room by ID",
    )
    game_over: bool = Field(default=False)
    won: bool = Field(default=False)
    death_message: str | None = Field(default=None)

    @classmethod
    def from_game(cls, game: Game) -> "GameState":
        """
        Create initial state from a game definition.

        This initializes all object and room states from the game's
        initial_state and object/room definitions.
        """
        initial: InitialState = game.initial_state

        # Initialize object states
        objects: dict[str, ObjectState] = {}
        for obj in game.objects:
            # Objects in initial inventory start there; otherwise use defined location
            location = "inventory" if obj.id in initial.inventory else obj.location

            objects[obj.id] = ObjectState(
                location=location,
                is_open=obj.is_open,
                locked=obj.locked,
                is_lit=obj.is_lit,
                worn=obj.worn,
                hidden=obj.hidden,
                examined=False,
            )

        # Initialize room states
        rooms: dict[str, RoomState] = {room.id: RoomState(visited=False) for room in game.rooms}

        # Mark starting room as visited
        if initial.current_room in rooms:
            rooms[initial.current_room].visited = True

        return cls(
            current_room=initial.current_room,
            inventory=list(initial.inventory),
            turns=0,
            score=0,
            flags=deepcopy(initial.flags),
            objects=objects,
            rooms=rooms,
            game_over=False,
            won=False,
        )

    def get_object_location(self, object_id: str) -> str | None:
        """Get the current location of an object."""
        if object_id in self.objects:
            return self.objects[object_id].location
        return None

    def get_objects_at(self, location: str) -> list[str]:
        """Get all object IDs at a given location."""
        return [
            obj_id
            for obj_id, state in self.objects.items()
            if state.location == location and not state.hidden
        ]

    def get_visible_objects_at(self, location: str, game: Game) -> list[str]:
        """
        Get visible object IDs at a location.

        Excludes hidden objects and objects inside closed containers.
        """
        visible = []
        for obj_id, state in self.objects.items():
            if state.location != location:
                continue
            if state.hidden:
                continue

            obj_def = game.get_object(obj_id)
            if obj_def and obj_def.scenery:
                continue  # Scenery is part of room description, not listed separately

            visible.append(obj_id)

        return visible

    def move_object(self, object_id: str, new_location: str) -> None:
        """Move an object to a new location."""
        if object_id in self.objects:
            self.objects[object_id].location = new_location

    def is_in_inventory(self, object_id: str) -> bool:
        """Check if an object is in the player's inventory."""
        return object_id in self.inventory

    def add_to_inventory(self, object_id: str) -> None:
        """Add an object to inventory and update its location."""
        if object_id not in self.inventory:
            self.inventory.append(object_id)
        self.move_object(object_id, "inventory")

    def remove_from_inventory(self, object_id: str) -> None:
        """Remove an object from inventory (does not update location)."""
        if object_id in self.inventory:
            self.inventory.remove(object_id)

    def set_flag(self, flag_name: str, value: Any = True) -> None:
        """Set a game flag."""
        self.flags[flag_name] = value

    def get_flag(self, flag_name: str, default: Any = None) -> Any:
        """Get a game flag value."""
        return self.flags.get(flag_name, default)

    def increment_turns(self) -> None:
        """Increment the turn counter."""
        self.turns += 1

    def add_score(self, points: int) -> None:
        """Add to the player's score."""
        self.score += points

    def end_game(self, won: bool, message: str | None = None) -> None:
        """Mark the game as over."""
        self.game_over = True
        self.won = won
        if not won and message:
            self.death_message = message

    def to_save_dict(self) -> dict[str, Any]:
        """Convert state to a dictionary for saving."""
        return self.model_dump()

    @classmethod
    def from_save_dict(cls, data: dict[str, Any]) -> "GameState":
        """Load state from a saved dictionary."""
        return cls.model_validate(data)
