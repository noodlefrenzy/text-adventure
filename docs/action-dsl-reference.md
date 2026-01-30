# Custom Actions DSL Reference

This document describes how to create custom actions for game objects in LLM Text Adventure.

## Overview

Custom actions allow adventure creators to define object-specific behaviors without modifying Python code. Actions are defined in the game JSON on each object.

## Basic Structure

```json
{
  "objects": [
    {
      "id": "altar",
      "name": "stone altar",
      "actions": {
        "pray": "You kneel and pray. A sense of peace washes over you.",
        "examine": {
          "message": "The altar is covered in ancient runes.",
          "state_changes": {"flags.examined_altar": true}
        }
      }
    }
  ]
}
```

## Action Types

### Simple String Action
The simplest action - just a message:

```json
"examine": "You see a dusty old lamp."
```

### Complex Action Object
For actions with conditions, state changes, or special effects:

```json
"unlock": {
  "message": "The door clicks open!",
  "condition": "inventory.includes('brass_key')",
  "fail_message": "You need a key to unlock this.",
  "state_changes": {"door.locked": false},
  "reveals_object": "hidden_treasure",
  "moves_player": "secret_room",
  "consumes_object": true
}
```

## Action Fields

| Field | Type | Description |
|-------|------|-------------|
| `message` | string | **Required.** Text shown when action succeeds |
| `condition` | string | Optional. Condition that must be true for action to succeed |
| `fail_message` | string | Optional. Text shown when condition fails |
| `state_changes` | object | Optional. State modifications to apply |
| `reveals_object` | string | Optional. Object ID to unhide |
| `moves_player` | string | Optional. Room ID to teleport player to |
| `consumes_object` | boolean | Optional. If true, removes the triggering object |

## Conditions

Conditions are strings that evaluate to true/false.

### Flag Conditions
```json
"condition": "flags.has_key"
"condition": "flags.talked_to_guard"
```

### Object State Conditions
```json
"condition": "door.locked"
"condition": "lamp.is_lit"
"condition": "chest.is_open"
```

### Inventory Conditions
```json
"condition": "inventory.includes('gold_coin')"
"condition": "inventory.includes('magic_wand')"
```

### Negation
```json
"condition": "!flags.already_used"
"condition": "!door.locked"
```

### Compound Conditions (AND)
```json
"condition": "flags.has_code && inventory.includes('keycard')"
```

### Compound Conditions (OR)
```json
"condition": "inventory.includes('key') || flags.door_broken"
```

## State Changes

State changes modify game state when an action succeeds.

### Setting Flags
```json
"state_changes": {
  "flags.puzzle_solved": true,
  "flags.alarm_triggered": false
}
```

### Modifying Object State
```json
"state_changes": {
  "door.locked": false,
  "lamp.is_lit": true,
  "chest.is_open": true
}
```

## Action Naming

### Simple Verb
```json
"pray": {...}      // Triggered by: PRAY, PRAY ALTAR
"examine": {...}   // Triggered by: EXAMINE ALTAR, LOOK AT ALTAR
```

### Verb with Target
```json
"use:door": {...}  // Triggered by: USE KEY WITH DOOR (on the key object)
"give:guard": {...} // Triggered by: GIVE COIN TO GUARD (on the coin object)
```

## Custom Verbs

Define new verbs that the parser will recognize:

```json
{
  "verbs": [
    {
      "verb": "pray",
      "aliases": ["worship", "kneel"],
      "requires_object": false
    },
    {
      "verb": "bribe",
      "aliases": ["pay off"],
      "requires_object": true,
      "requires_indirect": true,
      "prepositions": ["with"]
    }
  ]
}
```

### Verb Definition Fields

| Field | Type | Description |
|-------|------|-------------|
| `verb` | string | **Required.** The main verb word |
| `aliases` | array | Optional. Alternative words that mean the same thing |
| `requires_object` | boolean | If true, "VERB what?" prompt if no object given |
| `requires_indirect` | boolean | If true, allows "VERB X WITH Y" syntax |
| `prepositions` | array | Valid prepositions for this verb |
| `default_message` | string | Message when no action matches |

## Built-in Verbs

These verbs are always available:

| Verb | Aliases | Description |
|------|---------|-------------|
| `take` | get, grab, pick | Pick up an object |
| `drop` | put down | Drop an object |
| `examine` | look at, x, inspect | Look at an object |
| `open` | | Open a container or door |
| `close` | shut | Close a container or door |
| `lock` | | Lock with a key |
| `unlock` | | Unlock with a key |
| `read` | | Read text on an object |
| `use` | | Use an object (with optional target) |
| `talk` | speak, say | Talk to an NPC |
| `show` | present, display | Show an item to someone |
| `insert` | | Insert into a slot/machine |
| `give` | | Give an item to someone |
| `enter` | | Enter a door/portal |

## Examples

### NPC Conversation
```json
{
  "id": "merchant",
  "name": "traveling merchant",
  "actions": {
    "talk": {
      "message": "The merchant says 'I have wares if you have coin.'",
      "state_changes": {"flags.met_merchant": true}
    },
    "give:gold_coin": {
      "message": "The merchant takes your coin and hands you a mysterious map.",
      "condition": "inventory.includes('gold_coin')",
      "state_changes": {"flags.bought_map": true},
      "reveals_object": "treasure_map"
    }
  }
}
```

### Puzzle Lock
```json
{
  "id": "vault_door",
  "name": "vault door",
  "lockable": true,
  "locked": true,
  "openable": false,
  "actions": {
    "unlock": {
      "message": "You enter the code 1234. The vault clicks open!",
      "condition": "flags.found_code",
      "fail_message": "The keypad blinks red. You don't know the code.",
      "state_changes": {"vault_door.locked": false}
    },
    "open": {
      "message": "The heavy vault door swings open.",
      "condition": "!vault_door.locked",
      "fail_message": "The door is locked.",
      "state_changes": {"vault_door.is_open": true}
    }
  }
}
```

### Magic Item
```json
{
  "id": "magic_wand",
  "name": "magic wand",
  "actions": {
    "use": {
      "message": "The wand glows but nothing happens.",
      "condition": "!flags.wand_charged"
    },
    "use:crystal": {
      "message": "You point the wand at the crystal. It shatters, revealing a key!",
      "condition": "flags.wand_charged",
      "reveals_object": "crystal_key",
      "state_changes": {"flags.crystal_destroyed": true}
    }
  }
}
```

## Validation

Run the game validator to check for common issues:

```python
from text_adventure.validator import validate_game
from text_adventure.models.game import Game

game = Game.model_validate(game_data)
issues = validate_game(game)

for issue in issues:
    print(issue)
```

Common issues caught:
- Unknown verbs in actions
- Invalid condition syntax
- Missing object references
- Revealed objects that aren't hidden

## Tips

1. **Start simple** - Use string actions first, add complexity as needed
2. **Test conditions** - Make sure conditions are achievable in your game
3. **Provide fail messages** - Help players understand what they need
4. **Use reveals_object** - Keep surprises hidden until earned
5. **Validate early** - Run the validator after editing game JSON
