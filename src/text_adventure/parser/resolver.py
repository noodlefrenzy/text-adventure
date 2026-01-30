"""
resolver.py

PURPOSE: Resolve object references in commands to actual game objects.
DEPENDENCIES: game model, state model

ARCHITECTURE NOTES:
The resolver takes a parsed Command (with string object references like
"brass key") and resolves them to actual object IDs in the game.

It handles:
- Exact name matches ("lamp" -> lamp)
- Adjective-qualified references ("brass key" -> brass_key)
- Ambiguity detection ("key" when multiple keys exist)
- Visibility checks (can't interact with objects in other rooms)
"""

from dataclasses import dataclass
from enum import Enum, auto

from text_adventure.models.command import Command, Preposition, Verb
from text_adventure.models.game import Game, GameObject
from text_adventure.models.state import GameState


class ResolutionError(Enum):
    """Types of resolution failures."""

    NOT_FOUND = auto()  # Object doesn't exist or isn't visible
    AMBIGUOUS = auto()  # Multiple objects match
    NOT_HERE = auto()  # Object exists but isn't accessible


@dataclass
class ResolvedCommand:
    """A command with resolved object IDs."""

    verb: Verb
    direct_object_id: str | None = None
    preposition: "Preposition | None" = None
    indirect_object_id: str | None = None
    raw_input: str = ""
    custom_verb: str | None = None  # Canonical name for CUSTOM verbs


@dataclass
class ResolutionResult:
    """Result of resolution - either resolved command or error."""

    resolved: ResolvedCommand | None
    error_type: ResolutionError | None
    error_message: str | None
    # For ambiguous results, list the matching objects
    ambiguous_objects: list[str] | None = None

    @property
    def success(self) -> bool:
        return self.resolved is not None

    @classmethod
    def ok(cls, resolved: ResolvedCommand) -> "ResolutionResult":
        return cls(resolved=resolved, error_type=None, error_message=None)

    @classmethod
    def not_found(cls, object_ref: str) -> "ResolutionResult":
        return cls(
            resolved=None,
            error_type=ResolutionError.NOT_FOUND,
            error_message=f"You can't see any {object_ref} here.",
        )

    @classmethod
    def not_here(cls, object_ref: str) -> "ResolutionResult":
        return cls(
            resolved=None,
            error_type=ResolutionError.NOT_HERE,
            error_message=f"The {object_ref} isn't here.",
        )

    @classmethod
    def ambiguous(cls, object_ref: str, matches: list[GameObject]) -> "ResolutionResult":
        names = [obj.name for obj in matches]
        return cls(
            resolved=None,
            error_type=ResolutionError.AMBIGUOUS,
            error_message=f"Which {object_ref} do you mean?",
            ambiguous_objects=names,
        )


class ObjectResolver:
    """Resolves object references to game object IDs."""

    def __init__(self, game: Game, state: GameState):
        self.game = game
        self.state = state

    def get_visible_objects(self) -> list[GameObject]:
        """
        Get all objects the player can currently interact with.

        Includes:
        - Objects in the current room (not hidden)
        - Objects in the player's inventory
        - Objects in open containers in the room or inventory
        """
        visible: list[GameObject] = []
        current_room = self.state.current_room

        for obj in self.game.objects:
            obj_state = self.state.objects.get(obj.id)
            if not obj_state:
                continue

            # Hidden objects aren't visible
            if obj_state.hidden:
                continue

            location = obj_state.location

            # In current room
            if location == current_room:
                visible.append(obj)
                continue

            # In inventory
            if location == "inventory":
                visible.append(obj)
                continue

            # In an open container that's visible
            container_def = self.game.get_object(location)
            if container_def:
                container_state = self.state.objects.get(location)
                if container_state and container_state.is_open:
                    # Check if container is visible
                    container_loc = container_state.location
                    if container_loc in (current_room, "inventory"):
                        visible.append(obj)

        return visible

    def match_object(self, reference: str, objects: list[GameObject]) -> list[GameObject]:
        """
        Find objects matching a text reference.

        Matching rules (in order of priority):
        1. Exact ID match
        2. Exact name match
        3. Adjectives + name match (with all adjectives required)
        4. Partial name match (if no adjectives specified)

        Args:
            reference: The text reference (e.g., "brass key", "lamp")
            objects: Objects to search

        Returns:
            List of matching objects (may be empty or have multiple)
        """
        reference = reference.lower().strip()
        words = reference.split()

        if not words:
            return []

        # Try exact ID match first
        for obj in objects:
            if obj.id == reference.replace(" ", "_"):
                return [obj]

        # Try exact name match
        exact_matches = [obj for obj in objects if obj.name.lower() == reference]
        if exact_matches:
            return exact_matches

        # Try matching with adjectives
        # Split reference into potential adjectives and noun
        # "brass key" -> adjectives=["brass"], noun="key"
        # "small brass key" -> adjectives=["small", "brass"], noun="key"

        def score_match(obj: GameObject, ref_words: list[str]) -> int:
            """
            Score how well an object matches the reference.

            Returns:
                -1 if no match
                0+ for matches (higher = better match)
            """
            obj_name_lower = obj.name.lower()
            obj_adjectives = {a.lower() for a in obj.adjectives}

            best_score = -1

            # Try each possible split of ref_words into adjectives + noun
            for noun_start in range(len(ref_words)):
                potential_adjectives = ref_words[:noun_start]
                potential_noun = " ".join(ref_words[noun_start:])

                if not potential_noun:
                    continue

                # Check if noun matches object name
                name_matches = obj_name_lower == potential_noun

                if not name_matches:
                    continue

                # Check if all potential adjectives are in object's adjectives
                if all(adj in obj_adjectives for adj in potential_adjectives):
                    # Score based on number of matching adjectives
                    # More adjectives = more specific = better match
                    score = len(potential_adjectives)
                    best_score = max(best_score, score)

            return best_score

        # Score all objects
        scored = [(obj, score_match(obj, words)) for obj in objects]
        scored = [(obj, score) for obj, score in scored if score >= 0]

        if not scored:
            # Try partial name match as fallback (only if single word reference)
            if len(words) == 1:
                partial = [
                    obj
                    for obj in objects
                    if words[0] in obj.name.lower() or obj.name.lower() in words[0]
                ]
                if partial:
                    return partial
            return []

        # Return all objects with the best (highest) score
        best_score = max(score for _, score in scored)
        return [obj for obj, score in scored if score == best_score]

    def resolve(self, command: Command) -> ResolutionResult:
        """
        Resolve a parsed command to actual object IDs.

        Args:
            command: The parsed command with text object references

        Returns:
            ResolutionResult with resolved IDs or error
        """
        visible = self.get_visible_objects()

        direct_id: str | None = None
        indirect_id: str | None = None

        # Resolve direct object if present
        if command.direct_object:
            matches = self.match_object(command.direct_object, visible)

            if not matches:
                return ResolutionResult.not_found(command.direct_object)

            if len(matches) > 1:
                return ResolutionResult.ambiguous(command.direct_object, matches)

            direct_id = matches[0].id

        # Resolve indirect object if present
        if command.indirect_object:
            matches = self.match_object(command.indirect_object, visible)

            if not matches:
                return ResolutionResult.not_found(command.indirect_object)

            if len(matches) > 1:
                return ResolutionResult.ambiguous(command.indirect_object, matches)

            indirect_id = matches[0].id

        return ResolutionResult.ok(
            ResolvedCommand(
                verb=command.verb,
                direct_object_id=direct_id,
                preposition=command.preposition,
                indirect_object_id=indirect_id,
                raw_input=command.raw_input,
                custom_verb=command.custom_verb,
            )
        )

    def resolve_in_context(
        self,
        reference: str,
        context: str,
    ) -> tuple[str | None, str | None]:
        """
        Resolve a reference with context hint for better error messages.

        Context can be:
        - "room": Only look in current room
        - "inventory": Only look in inventory
        - "anywhere": Look everywhere visible

        Returns:
            (object_id, error_message) - one will be None
        """
        visible = self.get_visible_objects()

        if context == "room":
            visible = [
                obj
                for obj in visible
                if self.state.objects[obj.id].location == self.state.current_room
            ]
        elif context == "inventory":
            visible = [obj for obj in visible if self.state.objects[obj.id].location == "inventory"]

        matches = self.match_object(reference, visible)

        if not matches:
            if context == "inventory":
                return None, f"You're not carrying any {reference}."
            return None, f"You can't see any {reference} here."

        if len(matches) > 1:
            return None, f"Which {reference} do you mean?"

        return matches[0].id, None
