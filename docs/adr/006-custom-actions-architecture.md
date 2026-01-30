# ADR-006: Custom Actions Architecture

## Status
ACCEPTED

## Context
During playtesting the Kabukicho game, we found several bugs where:
1. Custom verbs (TALK, SHOW, SING) weren't recognized by the parser
2. Custom actions on objects weren't triggered by standard handlers
3. Condition syntax from LLM generation wasn't supported by the engine

This ADR documents the current architecture and proposes improvements.

## Current Architecture

### Code Layer (Python)
- **Verb Enum**: Fixed set of verbs the parser recognizes
- **Parser**: Maps input words to Verb enum values
- **Handlers**: Standard behavior for each verb (handle_take, handle_open, etc.)
- **Condition Evaluator**: Evaluates condition strings

### Config Layer (JSON Game Files)
- **Custom Actions**: Per-object actions with messages, conditions, state_changes
- **Verbs List**: Game can list verbs but parser doesn't use it dynamically

### Collaboration Points
1. Handlers check for custom actions before/after standard logic
2. Custom actions can: set flags, change object state, reveal objects, move player
3. Conditions can reference: flags, object attributes, inventory

## Problems Identified

1. **Closed Verb Set**: Adding a new verb requires code changes
2. **Handler Coupling**: Each handler must explicitly check for custom actions
3. **Condition Syntax**: LLM generates JS-like syntax; engine must support it
4. **No Validation**: Games can use verbs/conditions the engine doesn't support

## Decision

### Short-term (Implemented)
- Added TALK, SHOW, SING, INSERT verbs to enum
- Updated handlers to check custom actions first
- Enhanced condition evaluator for `&&`, `||`, `!`, `inventory.includes()`
- Added generator transform to fix common LLM output issues

### Medium-term (Proposed)

#### 1. Generic Custom Verb Handler
Allow games to define verbs in JSON that route to custom actions:

```json
{
  "custom_verbs": [
    {"verb": "pray", "aliases": ["worship"], "requires_object": false},
    {"verb": "bribe", "aliases": ["pay off"], "requires_object": true}
  ]
}
```

The engine would:
- Add these to parser at game load time
- Route unrecognized verbs to a generic handler
- Generic handler searches room objects for matching custom action

#### 2. Game Validator
A validation step that checks:
- All verbs used in custom actions are recognized
- All condition syntax is supported
- All object references in actions exist
- reveals_object targets are hidden

```python
def validate_game(game: Game) -> list[ValidationWarning]:
    warnings = []
    for obj in game.objects:
        for action_name, action in obj.actions.items():
            verb = action_name.split(":")[0]
            if verb not in KNOWN_VERBS and verb not in game.custom_verbs:
                warnings.append(f"Unknown verb '{verb}' in {obj.id}")
    return warnings
```

#### 3. Action DSL Documentation
Clear documentation for adventure creators:

```markdown
## Custom Action Reference

### Conditions
- `flags.flag_name` - Check if flag is truthy
- `object_id.attribute` - Check object state (locked, is_open, etc.)
- `inventory.includes('item_id')` - Check if player has item
- `!condition` - Negate a condition
- `cond1 && cond2` - Both must be true
- `cond1 || cond2` - Either must be true

### State Changes
- `{"flags.flag_name": true}` - Set a flag
- `{"object_id.locked": false}` - Change object state

### Special Fields
- `reveals_object: "item_id"` - Unhide an object
- `moves_player: "room_id"` - Teleport player
- `consumes_object: true` - Remove the triggering object
```

### Long-term (Future)

#### Scripting Support
For complex puzzles, allow embedded scripts:

```json
{
  "actions": {
    "use": {
      "script": "scripts/solve_puzzle.py",
      "message": "{{result}}"
    }
  }
}
```

Or a safe expression language:

```json
{
  "condition": "inventory.count('coin') >= 3 && turns < 100"
}
```

## Consequences

### Positive
- Adventure creators can use more verbs without code changes
- Validation catches errors before runtime
- Clear documentation reduces trial-and-error

### Negative
- More complexity in game loading
- Potential security concerns with scripting
- Need to maintain backwards compatibility

### Neutral
- LLM generator needs to know what's supported
- Trade-off between flexibility and safety

## References
- [Inform 7](https://inform7.com/) - DSL for interactive fiction
- [Twine](https://twinery.org/) - Visual story editor with scripting
- [TADS](https://tads.org/) - Text Adventure Development System
