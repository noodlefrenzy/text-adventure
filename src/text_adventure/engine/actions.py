"""
actions.py

PURPOSE: Action handlers for game commands.
DEPENDENCIES: models

ARCHITECTURE NOTES:
Each verb has an action handler that:
- Validates the action is possible
- Updates game state
- Returns narrative text

Actions are pure functions that take resolved commands and state,
returning results without side effects beyond state mutation.
"""

from dataclasses import dataclass

from text_adventure.models.command import Preposition, Verb
from text_adventure.models.game import Game, GameObject
from text_adventure.models.state import GameState
from text_adventure.parser.resolver import ResolvedCommand


@dataclass
class ActionResult:
    """Result of executing an action."""

    message: str
    success: bool = True


def execute_action(
    command: ResolvedCommand,
    game: Game,
    state: GameState,
) -> ActionResult:
    """
    Execute a resolved command.

    This is the main dispatch function that routes to specific handlers.

    Args:
        command: The resolved command with object IDs
        game: The game definition
        state: The current game state (will be modified)

    Returns:
        ActionResult with message and success status
    """
    handlers = {
        Verb.TAKE: handle_take,
        Verb.DROP: handle_drop,
        Verb.EXAMINE: handle_examine,
        Verb.READ: handle_read,
        Verb.OPEN: handle_open,
        Verb.CLOSE: handle_close,
        Verb.PUT: handle_put,
        Verb.GIVE: handle_give,
        Verb.LOCK: handle_lock,
        Verb.UNLOCK: handle_unlock,
        Verb.USE: handle_use,
    }

    handler = handlers.get(command.verb)
    if handler:
        return handler(command, game, state)

    return ActionResult(
        message="I don't know how to do that.",
        success=False,
    )


def handle_take(
    command: ResolvedCommand,
    game: Game,
    state: GameState,
) -> ActionResult:
    """Handle TAKE/GET commands."""
    if not command.direct_object_id:
        return ActionResult(message="Take what?", success=False)

    obj = game.get_object(command.direct_object_id)
    if not obj:
        return ActionResult(message="You can't see that here.", success=False)

    obj_state = state.objects.get(command.direct_object_id)
    if not obj_state:
        return ActionResult(message="You can't see that here.", success=False)

    # Check if already in inventory
    if obj_state.location == "inventory":
        return ActionResult(message="You already have that.", success=False)

    # Check if takeable
    if not obj.takeable:
        return ActionResult(
            message=f"You can't take the {obj.name}.",
            success=False,
        )

    # Check if in a closed container
    container_id = obj_state.location
    container = game.get_object(container_id)
    if container and container.container:
        container_state = state.objects.get(container_id)
        if container_state and not container_state.is_open:
            return ActionResult(
                message=f"The {container.name} is closed.",
                success=False,
            )

    # Take the object
    state.add_to_inventory(command.direct_object_id)

    return ActionResult(message="Taken.")


def handle_drop(
    command: ResolvedCommand,
    game: Game,
    state: GameState,
) -> ActionResult:
    """Handle DROP commands."""
    if not command.direct_object_id:
        return ActionResult(message="Drop what?", success=False)

    obj = game.get_object(command.direct_object_id)
    if not obj:
        return ActionResult(message="You can't see that here.", success=False)

    # Check if in inventory
    if not state.is_in_inventory(command.direct_object_id):
        return ActionResult(message="You're not carrying that.", success=False)

    # Check if droppable
    if not obj.droppable:
        return ActionResult(
            message=f"You can't drop the {obj.name}.",
            success=False,
        )

    # Drop the object
    state.remove_from_inventory(command.direct_object_id)
    state.move_object(command.direct_object_id, state.current_room)

    return ActionResult(message="Dropped.")


def handle_examine(
    command: ResolvedCommand,
    game: Game,
    state: GameState,
) -> ActionResult:
    """Handle EXAMINE/LOOK AT commands."""
    if not command.direct_object_id:
        return ActionResult(message="Examine what?", success=False)

    obj = game.get_object(command.direct_object_id)
    if not obj:
        return ActionResult(message="You can't see that here.", success=False)

    obj_state = state.objects.get(command.direct_object_id)
    if obj_state:
        obj_state.examined = True

    # Check for custom examine action
    custom_msg = _get_custom_action(obj, "examine", state)
    if custom_msg:
        return ActionResult(message=custom_msg)

    # Use examine_text if available, otherwise description
    text = obj.examine_text or obj.description

    # If container, also describe contents
    if obj.container and obj_state and obj_state.is_open:
        contents = _get_container_contents(command.direct_object_id, game, state)
        if contents:
            text += f"\n\nInside the {obj.name} you see: {contents}"
        else:
            text += f"\n\nThe {obj.name} is empty."

    return ActionResult(message=text)


def handle_read(
    command: ResolvedCommand,
    game: Game,
    _state: GameState,
) -> ActionResult:
    """Handle READ commands."""
    if not command.direct_object_id:
        return ActionResult(message="Read what?", success=False)

    obj = game.get_object(command.direct_object_id)
    if not obj:
        return ActionResult(message="You can't see that here.", success=False)

    if not obj.readable:
        return ActionResult(
            message=f"There's nothing to read on the {obj.name}.",
            success=False,
        )

    return ActionResult(message=obj.read_text or "It's blank.")


def handle_open(
    command: ResolvedCommand,
    game: Game,
    state: GameState,
) -> ActionResult:
    """Handle OPEN commands."""
    if not command.direct_object_id:
        return ActionResult(message="Open what?", success=False)

    obj = game.get_object(command.direct_object_id)
    if not obj:
        return ActionResult(message="You can't see that here.", success=False)

    obj_state = state.objects.get(command.direct_object_id)
    if not obj_state:
        return ActionResult(message="You can't see that here.", success=False)

    if not obj.openable:
        return ActionResult(
            message=f"You can't open the {obj.name}.",
            success=False,
        )

    if obj_state.is_open:
        return ActionResult(message="It's already open.", success=False)

    if obj_state.locked:
        return ActionResult(message="It's locked.", success=False)

    # Open it
    obj_state.is_open = True

    # Describe contents if it's a container
    if obj.container:
        contents = _get_container_contents(command.direct_object_id, game, state)
        if contents:
            return ActionResult(message=f"Opened. Inside you see: {contents}")

    return ActionResult(message="Opened.")


def handle_close(
    command: ResolvedCommand,
    game: Game,
    state: GameState,
) -> ActionResult:
    """Handle CLOSE commands."""
    if not command.direct_object_id:
        return ActionResult(message="Close what?", success=False)

    obj = game.get_object(command.direct_object_id)
    if not obj:
        return ActionResult(message="You can't see that here.", success=False)

    obj_state = state.objects.get(command.direct_object_id)
    if not obj_state:
        return ActionResult(message="You can't see that here.", success=False)

    if not obj.openable:
        return ActionResult(
            message=f"You can't close the {obj.name}.",
            success=False,
        )

    if not obj_state.is_open:
        return ActionResult(message="It's already closed.", success=False)

    obj_state.is_open = False
    return ActionResult(message="Closed.")


def handle_put(
    command: ResolvedCommand,
    game: Game,
    state: GameState,
) -> ActionResult:
    """Handle PUT X IN/ON Y commands."""
    if not command.direct_object_id:
        return ActionResult(message="Put what?", success=False)
    if not command.indirect_object_id:
        return ActionResult(message="Put it where?", success=False)

    obj = game.get_object(command.direct_object_id)
    container = game.get_object(command.indirect_object_id)

    if not obj:
        return ActionResult(message="You can't see that here.", success=False)
    if not container:
        return ActionResult(message="You can't see that here.", success=False)

    # Must be holding the object
    if not state.is_in_inventory(command.direct_object_id):
        return ActionResult(
            message=f"You're not holding the {obj.name}.",
            success=False,
        )

    # Check if target is a container (for IN) or surface (for ON)
    container_state = state.objects.get(command.indirect_object_id)

    if command.preposition == Preposition.IN:
        if not container.container:
            return ActionResult(
                message=f"You can't put things in the {container.name}.",
                success=False,
            )
        if container_state and not container_state.is_open:
            return ActionResult(
                message=f"The {container.name} is closed.",
                success=False,
            )

    # Put the object
    state.remove_from_inventory(command.direct_object_id)
    state.move_object(command.direct_object_id, command.indirect_object_id)

    return ActionResult(message="Done.")


def handle_give(
    command: ResolvedCommand,
    game: Game,
    state: GameState,
) -> ActionResult:
    """Handle GIVE X TO Y commands."""
    if not command.direct_object_id:
        return ActionResult(message="Give what?", success=False)
    if not command.indirect_object_id:
        return ActionResult(message="Give it to whom?", success=False)

    obj = game.get_object(command.direct_object_id)
    recipient = game.get_object(command.indirect_object_id)

    if not obj:
        return ActionResult(message="You can't see that here.", success=False)
    if not recipient:
        return ActionResult(message="You can't see that here.", success=False)

    # Must be holding the object
    if not state.is_in_inventory(command.direct_object_id):
        return ActionResult(
            message=f"You're not holding the {obj.name}.",
            success=False,
        )

    # Check for custom give action
    action_key = f"give:{command.indirect_object_id}"
    custom_msg = _get_custom_action(obj, action_key, state)
    if custom_msg:
        state.remove_from_inventory(command.direct_object_id)
        return ActionResult(message=custom_msg)

    return ActionResult(
        message=f"The {recipient.name} doesn't seem interested.",
        success=False,
    )


def handle_lock(
    command: ResolvedCommand,
    game: Game,
    state: GameState,
) -> ActionResult:
    """Handle LOCK X WITH Y commands."""
    if not command.direct_object_id:
        return ActionResult(message="Lock what?", success=False)
    if not command.indirect_object_id:
        return ActionResult(message="Lock it with what?", success=False)

    obj = game.get_object(command.direct_object_id)
    key = game.get_object(command.indirect_object_id)

    if not obj or not key:
        return ActionResult(message="You can't see that here.", success=False)

    obj_state = state.objects.get(command.direct_object_id)
    if not obj_state:
        return ActionResult(message="You can't see that here.", success=False)

    if not obj.lockable:
        return ActionResult(
            message=f"You can't lock the {obj.name}.",
            success=False,
        )

    if obj_state.locked:
        return ActionResult(message="It's already locked.", success=False)

    if obj_state.is_open:
        return ActionResult(message="You'll need to close it first.", success=False)

    # Check if using the right key
    if obj.key_object != command.indirect_object_id:
        return ActionResult(
            message=f"The {key.name} doesn't fit.",
            success=False,
        )

    obj_state.locked = True
    return ActionResult(message="Locked.")


def handle_unlock(
    command: ResolvedCommand,
    game: Game,
    state: GameState,
) -> ActionResult:
    """Handle UNLOCK X WITH Y commands."""
    if not command.direct_object_id:
        return ActionResult(message="Unlock what?", success=False)
    if not command.indirect_object_id:
        return ActionResult(message="Unlock it with what?", success=False)

    obj = game.get_object(command.direct_object_id)
    key = game.get_object(command.indirect_object_id)

    if not obj or not key:
        return ActionResult(message="You can't see that here.", success=False)

    obj_state = state.objects.get(command.direct_object_id)
    if not obj_state:
        return ActionResult(message="You can't see that here.", success=False)

    if not obj.lockable:
        return ActionResult(
            message=f"You can't unlock the {obj.name}.",
            success=False,
        )

    if not obj_state.locked:
        return ActionResult(message="It's not locked.", success=False)

    # Check if using the right key
    if obj.key_object != command.indirect_object_id:
        return ActionResult(
            message=f"The {key.name} doesn't fit.",
            success=False,
        )

    obj_state.locked = False
    return ActionResult(message="Unlocked.")


def handle_use(
    command: ResolvedCommand,
    game: Game,
    state: GameState,
) -> ActionResult:
    """Handle USE X [WITH Y] commands."""
    if not command.direct_object_id:
        return ActionResult(message="Use what?", success=False)

    obj = game.get_object(command.direct_object_id)
    if not obj:
        return ActionResult(message="You can't see that here.", success=False)

    # Check for custom use action
    if command.indirect_object_id:
        action_key = f"use_with:{command.indirect_object_id}"
        result = _execute_custom_action(obj, action_key, game, state)
        if result:
            return result

        target = game.get_object(command.indirect_object_id)
        target_name = target.name if target else "that"
        return ActionResult(
            message=f"You can't use the {obj.name} with the {target_name}.",
            success=False,
        )

    # Simple USE without target
    result = _execute_custom_action(obj, "use", game, state)
    if result:
        return result

    return ActionResult(
        message=f"You're not sure how to use the {obj.name}.",
        success=False,
    )


def _get_custom_action(
    obj: GameObject,
    action_key: str,
    state: GameState,
) -> str | None:
    """
    Get custom action message if action exists and conditions are met.

    Returns the message string or None if no custom action.
    """
    if action_key not in obj.actions:
        return None

    action = obj.actions[action_key]

    # Simple string action
    if isinstance(action, str):
        return action

    # Complex action with conditions
    if action.condition and not _evaluate_condition(action.condition, state):
        return action.fail_message

    return action.message


def _execute_custom_action(
    obj: GameObject,
    action_key: str,
    _game: Game,
    state: GameState,
) -> ActionResult | None:
    """
    Execute a custom action, including state changes.

    Returns ActionResult or None if no custom action.
    """
    if action_key not in obj.actions:
        return None

    action = obj.actions[action_key]

    # Simple string action
    if isinstance(action, str):
        return ActionResult(message=action)

    # Complex action with conditions
    if action.condition and not _evaluate_condition(action.condition, state):
        return ActionResult(
            message=action.fail_message or "Nothing happens.",
            success=False,
        )

    # Apply state changes
    for key, value in action.state_changes.items():
        if "." in key:
            # Object state change (e.g., "door.locked")
            obj_id, attr = key.split(".", 1)
            obj_state = state.objects.get(obj_id)
            if obj_state and hasattr(obj_state, attr):
                setattr(obj_state, attr, value)
        else:
            # Flag change
            state.set_flag(key, value)

    # Reveal object if specified
    if action.reveals_object:
        revealed_state = state.objects.get(action.reveals_object)
        if revealed_state:
            revealed_state.hidden = False

    # Consume object if specified
    if action.consumes_object:
        state.remove_from_inventory(obj.id)
        state.move_object(obj.id, "nowhere")

    # Move player if specified
    if action.moves_player:
        state.current_room = action.moves_player

    return ActionResult(message=action.message)


def _evaluate_condition(condition: str, state: GameState) -> bool:
    """
    Evaluate a condition string.

    Supports:
    - "object.attribute" (e.g., "door.locked")
    - "flag_name" (checks if flag is truthy)
    """
    if "." in condition:
        obj_id, attr = condition.split(".", 1)
        obj_state = state.objects.get(obj_id)
        if obj_state and hasattr(obj_state, attr):
            return bool(getattr(obj_state, attr))
        return False

    return bool(state.get_flag(condition))


def _get_container_contents(
    container_id: str,
    game: Game,
    state: GameState,
) -> str:
    """Get a description of items in a container."""
    items = []
    for obj_id, obj_state in state.objects.items():
        if obj_state.location == container_id and not obj_state.hidden:
            obj = game.get_object(obj_id)
            if obj:
                items.append(obj.name)

    if items:
        return ", ".join(items)
    return ""
