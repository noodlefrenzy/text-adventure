# Contributing to LLM Text Adventure

Thank you for your interest in contributing to LLM Text Adventure! This document provides guidelines and information for contributors.

## Getting Started

### Prerequisites

- Python 3.11 or higher
- An Anthropic API key (for generation and AI play features)

### Development Setup

1. Clone the repository:
   ```bash
   git clone https://github.com/noodlefrenzy/text-adventure.git
   cd text-adventure
   ```

2. Create a virtual environment:
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install with development dependencies:
   ```bash
   pip install -e ".[dev]"
   ```

4. Set up your environment:
   ```bash
   export ANTHROPIC_API_KEY=your-api-key-here
   ```

5. Verify your setup:
   ```bash
   pytest
   mypy src/
   ruff check .
   ```

## Development Workflow

### Code Style

We use automated tools to maintain code quality:

- **Ruff** for linting and formatting
- **mypy** for type checking
- **pytest** for testing

Run all checks before committing:
```bash
ruff format .
ruff check .
mypy src/
pytest
```

### Type Hints

All code must have complete type hints. We use strict mypy settings:

```python
# Good
def process_command(command: str, game: Game) -> TurnResult:
    ...

# Bad - missing types
def process_command(command, game):
    ...
```

### Testing

We follow Test-Driven Development (TDD) principles:

1. Write a failing test first
2. Implement the minimum code to pass
3. Refactor while keeping tests green

**Test file structure:**
```
tests/
  unit/           # Pure function tests, no I/O
  integration/    # Tests with mocked external services
  fixtures/       # Sample data, recorded API responses
  conftest.py     # Shared fixtures
```

**Test documentation:** Each test file should include a doc block:
```python
"""
TEST DOC: Feature Name

WHAT: What behavior is being tested
WHY: Why this test exists
HOW: Brief description of test approach

CASES:
- Case 1: Expected behavior
- Case 2: Expected behavior

EDGE CASES:
- Edge case: How it's handled
"""
```

### Commit Messages

We follow [Conventional Commits](https://www.conventionalcommits.org/):

```
<type>(<scope>): <description>

[optional body]

[optional footer]
```

**Types:**
- `feat`: New feature
- `fix`: Bug fix
- `refactor`: Code change that neither fixes nor adds
- `docs`: Documentation only
- `test`: Adding/updating tests
- `chore`: Maintenance tasks

**Scopes:** `cli`, `parser`, `engine`, `generator`, `player`, `llm`, `ui`, `models`, `config`

**Examples:**
```
feat(generator): add theme-based room generation
fix(parser): handle quoted strings in commands
docs(readme): add installation instructions
test(engine): add edge cases for locked doors
```

## Architecture Overview

See [docs/adr/](docs/adr/) for Architecture Decision Records explaining key design choices.

### Key Principles

1. **Server-side state authority**: The game engine is authoritative over game state; LLMs generate content but don't control state directly.

2. **Structured data**: Games are defined in JSON and validated with Pydantic models, enabling deterministic replay and editing.

3. **Traditional parser**: We use a classic verb-noun parser (GET LAMP), not conversational AI for command interpretation.

4. **Separation of concerns**:
   - `models/` - Data structures (Game, Command, State)
   - `parser/` - Input parsing and object resolution
   - `engine/` - Game logic and state management
   - `generator/` - LLM-based game creation
   - `player/` - AI player implementation
   - `llm/` - LLM client abstraction

## Pull Request Process

1. **Create a branch** from `main`:
   ```bash
   git checkout -b feat/your-feature-name
   ```

2. **Make your changes** following the guidelines above

3. **Ensure all checks pass**:
   ```bash
   ruff format .
   ruff check .
   mypy src/
   pytest
   ```

4. **Write a clear PR description**:
   - What does this PR do?
   - Why is this change needed?
   - How was it tested?

5. **Request review** and address feedback

## Adding New Features

### Adding a New Verb

1. Add to `Verb` enum in `src/text_adventure/models/command.py`
2. Write parser tests in `tests/unit/parser/`
3. Implement handler in `src/text_adventure/engine/actions.py`
4. Add to default verb list in generator schemas

### Adding a New LLM Backend

1. Create client in `src/text_adventure/llm/` implementing the `LLMClient` protocol
2. Add to the provider selection logic in config
3. Write integration tests with mocked responses
4. Document in README

## Reporting Issues

When reporting bugs, please include:

- Python version
- Operating system
- Steps to reproduce
- Expected vs actual behavior
- Relevant error messages or logs

## Questions?

Feel free to open an issue for questions or discussions about the project.

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
