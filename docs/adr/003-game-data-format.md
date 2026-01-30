# ADR-003: Game Data Format

## Status

Accepted

## Context

We needed a format for storing game definitions (rooms, objects, puzzles, win conditions). Requirements:

- Human-readable and editable
- Machine-parseable with strong validation
- Portable across systems
- Suitable for LLM generation
- Supports all game features (locked doors, containers, custom actions)

Options considered:
1. **Custom DSL**: A domain-specific language for game definition
2. **YAML**: Human-friendly but looser validation
3. **JSON with Pydantic**: Structured data with schema validation

## Decision

We use **JSON** for game definitions with **Pydantic v2** models for validation.

### Schema Structure

```json
{
  "metadata": {
    "title": "The Haunted Manor",
    "description": "Explore a mysterious manor..."
  },
  "rooms": [
    {
      "id": "entrance",
      "name": "Entrance Hall",
      "description": "A grand entrance hall...",
      "exits": {
        "north": "library",
        "east": {"target": "cellar", "locked": true, "unlock_object": "brass_key"}
      },
      "objects": ["chandelier", "coat_rack"]
    }
  ],
  "objects": [
    {
      "id": "brass_key",
      "name": "brass key",
      "adjectives": ["brass", "small"],
      "description": "A small brass key.",
      "location": "library",
      "takeable": true
    }
  ],
  "initial_state": {
    "current_room": "entrance",
    "inventory": []
  },
  "win_condition": {
    "type": "reach_room",
    "room": "treasure_room"
  }
}
```

### Validation Features

- Cross-reference validation (exits point to valid rooms)
- Object location validation (objects reference valid rooms/containers)
- Required field enforcement
- Type checking for all properties

## Consequences

### Positive

- **LLM-friendly**: JSON is a format LLMs handle well, especially with structured output
- **Strong validation**: Pydantic catches errors before game runs
- **IDE support**: JSON schema provides autocomplete and validation in editors
- **Deterministic**: Game definitions are pure data, enabling replay and testing
- **Editable**: Users can hand-edit games or use the generated output as a starting point

### Negative

- **Verbosity**: JSON is more verbose than a custom DSL would be
- **Learning curve**: Schema has many fields to understand
- **No inheritance**: Each object must be fully specified (no templates)

### Neutral

- Game state is separate from game definition (mutable vs immutable)
- Custom actions use a mini-DSL for conditions and effects

## References

- [Pydantic Documentation](https://docs.pydantic.dev/)
- `src/text_adventure/models/game.py` - Pydantic models
- `src/text_adventure/generator/schemas.py` - JSON schema for LLM generation
- `tests/fixtures/sample_game.json` - Example game file
