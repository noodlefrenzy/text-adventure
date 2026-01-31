# Architecture Decision Records

This directory contains Architecture Decision Records (ADRs) for the LLM Text Adventure project.

ADRs document significant architectural decisions, their context, and consequences. They provide a historical record of why the system is built the way it is.

## Index

| ADR | Title | Status |
|-----|-------|--------|
| [ADR-001](001-llm-provider.md) | LLM Provider Selection | Accepted |
| [ADR-002](002-parser-design.md) | Parser Design | Accepted |
| [ADR-003](003-game-data-format.md) | Game Data Format | Accepted |
| [ADR-004](004-state-management.md) | State Management Architecture | Accepted |
| [ADR-005](005-cli-framework.md) | CLI Framework Selection | Accepted |
| [ADR-006](006-custom-actions-architecture.md) | Custom Actions Architecture | Accepted |
| [ADR-007](007-curses-ui-and-ascii-art.md) | Curses UI and ASCII Art Generation | Accepted |

## ADR Format

Each ADR follows this structure:

```markdown
# ADR-NNN: Title

## Status
[DRAFT | ACCEPTED | SUPERSEDED by ADR-XXX | DEPRECATED]

## Context
Why is this decision needed? What problem are we solving?

## Decision
What did we decide?

## Consequences
### Positive
- Benefits

### Negative
- Tradeoffs

### Neutral
- Observations

## References
- Related documents, links
```

## Creating New ADRs

1. Copy the template above
2. Number sequentially (ADR-006, ADR-007, etc.)
3. Add to the index table
4. Submit for review
