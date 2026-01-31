"""
game.py

PURPOSE: Pydantic models for the static game definition (rooms, objects, verbs).
DEPENDENCIES: pydantic

ARCHITECTURE NOTES:
These models define the STATIC game content - what exists in the game world.
They are separate from GameState, which tracks MUTABLE state during play.
The Game model is the root - it contains all rooms, objects, and verbs.

Game JSON files are validated against these models when loaded.
The generator creates games that conform to these models.
"""

from typing import Any, Literal

from pydantic import BaseModel, Field, field_validator, model_validator


class GameMetadata(BaseModel):
    """Metadata about the game itself."""

    title: str = Field(..., min_length=1, max_length=100)
    author: str = Field(default="Generated")
    version: str = Field(default="1.0")
    description: str = Field(default="")


class Exit(BaseModel):
    """
    An exit from a room.

    Simple exits just point to a room_id.
    Complex exits can have conditions (locked doors, etc.).
    """

    target: str = Field(..., description="ID of the destination room")
    locked: bool = Field(default=False)
    lock_message: str = Field(
        default="The way is locked.",
        description="Message shown when trying to use a locked exit",
    )
    unlock_object: str | None = Field(
        default=None,
        description="Object ID that can unlock this exit",
    )
    hidden: bool = Field(
        default=False,
        description="Whether this exit is initially hidden",
    )


class Room(BaseModel):
    """
    A location in the game world.

    Rooms contain objects and have exits to other rooms.
    """

    id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(..., min_length=1, max_length=100)
    description: str = Field(..., min_length=1)
    exits: dict[str, Exit | str] = Field(
        default_factory=dict,
        description="Map of direction -> Exit or room_id",
    )
    objects: list[str] = Field(
        default_factory=list,
        description="IDs of objects initially in this room",
    )
    first_visit_description: str | None = Field(
        default=None,
        description="Special description shown only on first visit",
    )
    dark: bool = Field(
        default=False,
        description="Whether this room requires a light source",
    )
    ascii_art: str | None = Field(
        default=None,
        description="ASCII art representation of the room (max 80 chars wide, 10-15 lines)",
    )

    @field_validator("exits", mode="before")
    @classmethod
    def normalize_exits(cls, v: dict[str, Any]) -> dict[str, Exit | str]:
        """Convert string exits to Exit objects for consistency."""
        result: dict[str, Exit | str] = {}
        for direction, target in v.items():
            if isinstance(target, str):
                result[direction] = target
            elif isinstance(target, dict):
                result[direction] = Exit(**target)
            else:
                result[direction] = target
        return result


class ObjectAction(BaseModel):
    """
    A custom action response for an object.

    Simple actions return a message.
    Complex actions can have conditions and state changes.
    """

    message: str = Field(..., description="Text shown when action is performed")
    condition: str | None = Field(
        default=None,
        description="Condition that must be true (e.g., 'door.locked')",
    )
    fail_message: str | None = Field(
        default=None,
        description="Message shown if condition fails",
    )
    state_changes: dict[str, Any] = Field(
        default_factory=dict,
        description="State changes to apply (e.g., {'door.locked': False})",
    )
    consumes_object: bool = Field(
        default=False,
        description="Whether using this object destroys it",
    )
    reveals_object: str | None = Field(
        default=None,
        description="Object ID to reveal when this action is performed",
    )
    moves_player: str | None = Field(
        default=None,
        description="Room ID to move player to",
    )


class GameObject(BaseModel):
    """
    An interactive object in the game world.

    Objects can be in rooms or in the player's inventory.
    They have attributes that affect how they can be used.
    Custom actions define special behaviors for verbs.
    """

    id: str = Field(..., min_length=1, pattern=r"^[a-z][a-z0-9_]*$")
    name: str = Field(..., min_length=1, max_length=50)
    adjectives: list[str] = Field(
        default_factory=list,
        description="Adjectives that can identify this object (brass, old, etc.)",
    )
    description: str = Field(..., min_length=1)
    examine_text: str | None = Field(
        default=None,
        description="Detailed text shown when examining (defaults to description)",
    )
    location: str = Field(
        ...,
        description="Room ID or 'inventory' or 'nowhere' (not yet in game)",
    )

    # Standard attributes
    takeable: bool = Field(default=True)
    droppable: bool = Field(default=True)
    readable: bool = Field(default=False)
    read_text: str | None = Field(default=None)
    openable: bool = Field(default=False)
    is_open: bool = Field(default=False)
    container: bool = Field(default=False)
    contains: list[str] = Field(
        default_factory=list,
        description="Object IDs contained in this object",
    )
    lockable: bool = Field(default=False)
    locked: bool = Field(default=False)
    key_object: str | None = Field(
        default=None,
        description="Object ID that can lock/unlock this",
    )
    light_source: bool = Field(default=False)
    is_lit: bool = Field(default=False)
    wearable: bool = Field(default=False)
    worn: bool = Field(default=False)

    # Custom actions: verb -> action or verb:target -> action
    actions: dict[str, ObjectAction | str] = Field(
        default_factory=dict,
        description="Custom action handlers. Key is verb or verb:target_id",
    )

    # Scenery objects can't be taken
    scenery: bool = Field(
        default=False,
        description="Scenery objects are described but can't be taken",
    )

    # Hidden objects aren't visible until revealed
    hidden: bool = Field(default=False)

    @field_validator("actions", mode="before")
    @classmethod
    def normalize_actions(cls, v: dict[str, Any]) -> dict[str, ObjectAction | str]:
        """Convert string actions to ObjectAction for complex ones."""
        result: dict[str, ObjectAction | str] = {}
        for key, action in v.items():
            if isinstance(action, str):
                result[key] = action
            elif isinstance(action, dict):
                result[key] = ObjectAction(**action)
            else:
                result[key] = action
        return result

    @model_validator(mode="after")
    def validate_attributes(self) -> "GameObject":
        """Ensure attribute combinations are valid."""
        if self.scenery and self.takeable:
            # Scenery objects shouldn't be takeable
            object.__setattr__(self, "takeable", False)
        if self.readable and not self.read_text:
            raise ValueError(f"Object {self.id} is readable but has no read_text")
        if self.container and not self.openable:
            # Containers should be openable
            object.__setattr__(self, "openable", True)
        if self.locked and not self.lockable:
            object.__setattr__(self, "lockable", True)
        return self


class VerbDefinition(BaseModel):
    """
    Definition of a verb available in the game.

    This allows games to define custom verbs beyond the built-in set.
    """

    verb: str = Field(..., min_length=1)
    aliases: list[str] = Field(default_factory=list)
    requires_object: bool = Field(default=False)
    requires_indirect: bool = Field(default=False)
    prepositions: list[str] = Field(
        default_factory=list,
        description="Valid prepositions for this verb",
    )
    default_message: str = Field(
        default="Nothing happens.",
        description="Message when verb is used but no handler exists",
    )


class WinCondition(BaseModel):
    """
    Defines what must be true for the player to win.

    Multiple condition types are supported.
    """

    type: Literal["reach_room", "have_object", "flag_set", "all_of", "any_of"] = Field(
        ...,
        description="Type of win condition",
    )

    # For reach_room
    room: str | None = Field(default=None)

    # For have_object
    object: str | None = Field(default=None)

    # For flag_set
    flag: str | None = Field(default=None)

    # For all_of/any_of
    conditions: list["WinCondition"] | None = Field(default=None)

    win_message: str = Field(
        default="Congratulations! You have won!",
        description="Message displayed when player wins",
    )

    @model_validator(mode="after")
    def validate_condition(self) -> "WinCondition":
        """Ensure the right fields are set for the condition type."""
        match self.type:
            case "reach_room":
                if not self.room:
                    raise ValueError("reach_room condition requires 'room' field")
            case "have_object":
                if not self.object:
                    raise ValueError("have_object condition requires 'object' field")
            case "flag_set":
                if not self.flag:
                    raise ValueError("flag_set condition requires 'flag' field")
            case "all_of" | "any_of":
                if not self.conditions:
                    raise ValueError(f"{self.type} condition requires 'conditions' list")
        return self


class InitialState(BaseModel):
    """Initial game state when starting a new game."""

    current_room: str = Field(..., description="Starting room ID")
    inventory: list[str] = Field(
        default_factory=list,
        description="Object IDs player starts with",
    )
    flags: dict[str, Any] = Field(
        default_factory=dict,
        description="Initial flag values",
    )


class Game(BaseModel):
    """
    A complete game definition.

    This is the root model that contains everything needed to play a game.
    It is loaded from JSON and validated against this schema.
    """

    metadata: GameMetadata
    rooms: list[Room] = Field(..., min_length=1)
    objects: list[GameObject] = Field(default_factory=list)
    verbs: list[VerbDefinition] = Field(default_factory=list)
    initial_state: InitialState
    win_condition: WinCondition

    @model_validator(mode="after")
    def validate_references(self) -> "Game":
        """Ensure all ID references are valid."""
        room_ids = {room.id for room in self.rooms}
        object_ids = {obj.id for obj in self.objects}

        # Validate initial room exists
        if self.initial_state.current_room not in room_ids:
            raise ValueError(f"Initial room '{self.initial_state.current_room}' not found")

        # Validate initial inventory objects exist
        for obj_id in self.initial_state.inventory:
            if obj_id not in object_ids:
                raise ValueError(f"Initial inventory object '{obj_id}' not found")

        # Validate room exits point to valid rooms
        for room in self.rooms:
            for direction, exit_target in room.exits.items():
                target_id = exit_target if isinstance(exit_target, str) else exit_target.target
                if target_id not in room_ids:
                    raise ValueError(
                        f"Room '{room.id}' has exit '{direction}' to unknown room '{target_id}'"
                    )

        # Validate room object references
        for room in self.rooms:
            for obj_id in room.objects:
                if obj_id not in object_ids:
                    raise ValueError(f"Room '{room.id}' references unknown object '{obj_id}'")

        # Validate object locations (can be room, inventory, nowhere, or inside another object)
        for obj in self.objects:
            valid_locations = room_ids | object_ids | {"inventory", "nowhere"}
            if obj.location not in valid_locations:
                raise ValueError(f"Object '{obj.id}' has invalid location '{obj.location}'")

        # Validate contained objects
        for obj in self.objects:
            for contained_id in obj.contains:
                if contained_id not in object_ids:
                    raise ValueError(f"Object '{obj.id}' contains unknown object '{contained_id}'")

        # Validate win condition references
        self._validate_win_condition_refs(self.win_condition, room_ids, object_ids)

        return self

    def _validate_win_condition_refs(
        self,
        condition: WinCondition,
        room_ids: set[str],
        object_ids: set[str],
    ) -> None:
        """Recursively validate win condition references."""
        match condition.type:
            case "reach_room":
                if condition.room not in room_ids:
                    raise ValueError(f"Win condition references unknown room '{condition.room}'")
            case "have_object":
                if condition.object not in object_ids:
                    raise ValueError(
                        f"Win condition references unknown object '{condition.object}'"
                    )
            case "all_of" | "any_of":
                if condition.conditions:
                    for sub in condition.conditions:
                        self._validate_win_condition_refs(sub, room_ids, object_ids)

    def get_room(self, room_id: str) -> Room | None:
        """Get a room by ID."""
        for room in self.rooms:
            if room.id == room_id:
                return room
        return None

    def get_object(self, object_id: str) -> GameObject | None:
        """Get an object by ID."""
        for obj in self.objects:
            if obj.id == object_id:
                return obj
        return None
