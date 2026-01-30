# ADR-004: State Management Architecture

## Status

Accepted

## Context

Text adventure games have mutable state:
- Player location
- Inventory contents
- Object positions
- Door/container states (open, locked)
- Game flags (puzzles solved, events triggered)

With LLMs involved in both game generation and AI play, we needed to decide how state is managed:

1. **LLM-managed state**: Let the LLM track and report state
2. **Hybrid**: LLM generates narrative, system infers state changes
3. **Server-side authority**: System maintains authoritative state, LLM generates content only

## Decision

We chose **server-side state authority**:

- The `GameEngine` is the single source of truth for game state
- `GameState` is a Pydantic model tracking all mutable state
- LLMs generate content (games, commands) but never directly modify state
- All state changes go through the engine's action handlers

```
┌─────────────────┐
│   LLM (Claude)  │  Generates: games, AI commands
└────────┬────────┘
         │ content only
         ▼
┌─────────────────┐
│     Parser      │  Interprets commands
└────────┬────────┘
         │ Command objects
         ▼
┌─────────────────┐
│   GameEngine    │  AUTHORITATIVE STATE
│                 │  Executes actions
│   ┌──────────┐  │  Checks win conditions
│   │GameState │  │
│   └──────────┘  │
└────────┬────────┘
         │ narrative text
         ▼
┌─────────────────┐
│       UI        │  Displays to user
└─────────────────┘
```

## Consequences

### Positive

- **Determinism**: Same commands always produce same state changes
- **Testability**: State transitions can be unit tested without LLM calls
- **Reliability**: No risk of LLM "hallucinating" state changes
- **Save/Load**: State can be serialized and restored exactly
- **Debugging**: State is inspectable at any point

### Negative

- **Rigidity**: Custom actions must be pre-defined in schema, can't be invented dynamically
- **Complexity**: Engine must handle all possible state transitions

### Neutral

- LLM-generated games are validated before play begins
- AI player issues commands through the same parser as human players
- State includes undo history for potential future undo feature

## References

- `src/text_adventure/engine/engine.py` - GameEngine implementation
- `src/text_adventure/models/state.py` - GameState model
- `src/text_adventure/engine/actions.py` - Action handlers
