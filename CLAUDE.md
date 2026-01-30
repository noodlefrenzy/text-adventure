---
# CLAUDE.md Template Configuration
version: "1.0.0"
project_type: "cli"  # web-app | cli | backend | library | monorepo
testing_philosophy: "tdd"  # tdd | tad | bdd | lightweight | manual | hybrid
bootstrap_source: null  # Set by /plan-0-constitution when bootstrapping
last_updated: "2026-01-30"
---

<!-- SECTION: QUICK_START -->
<!-- REQUIRED -->
# LLM Text Adventure

## Project Overview

<!-- USER CONTENT START: overview -->
A Python CLI tool for generating and playing classic text adventure games using LLMs.

**Core Workflow:**
1. **Generate**: LLM creates a complete game world (rooms, objects, puzzles) in structured JSON
2. **Play (Human)**: Traditional parser interprets commands; game engine executes logic
3. **Play (AI)**: LLM acts as player, issuing commands to explore/solve the adventure
4. **Extend**: ASCII art generation, curses UI, save/load, multiple LLM backends

**Key Constraints:**
- Game state is authoritative (server-side); LLM generates content, doesn't control state
- Structured JSON format for games enables validation, editing, and deterministic replay
- Parser is traditional verb-noun (GET LAMP), not conversational
- Support both cloud (Anthropic) and local (Ollama) LLM backends
<!-- USER CONTENT END: overview -->

## Development Commands

```bash
# Essential commands
pip install -e ".[dev]"       # Install with dev dependencies
python -m text_adventure      # Run CLI (or use entry point after install)
text-adventure generate       # Generate a new game
text-adventure play game.json # Play a generated game
text-adventure ai-play game.json # Watch AI play
pytest                        # Run test suite
pytest --cov                  # Run tests with coverage
ruff check .                  # Lint
ruff format .                 # Format code
mypy src/                     # Type checking
```

## Current Status

<!-- USER CONTENT START: status -->
**Focus:** Initial implementation

**Recent Changes:**
- Project initialized
- CLAUDE.md customized for text adventure domain

**Known Issues:**
- None yet (greenfield project)
<!-- USER CONTENT END: status -->

---

<!-- SECTION: CORE_GUIDANCE -->
<!-- REQUIRED -->
## Core Guidance

### Assumption Validation (CRITICAL)

**When the user provides constraints, requirements, or claims about external systems, VERIFY them before designing around them.**

**Verifiable assumptions include:**
- API pricing models (per-call vs subscription vs free)
- API rate limits and quotas
- Data availability and formats
- Third-party service capabilities
- Technology constraints ("X can't do Y")
- Cost structures

**Verification process:**
1. **Identify** assumptions in user requirements that affect architecture
2. **Flag** which ones are verifiable via documentation, web search, or API exploration
3. **Verify** using WebSearch, WebFetch, or direct API documentation
4. **Report back** before proceeding with design:

```
## Assumption Check

| Assumption | Source | Verified | Finding |
|------------|--------|----------|---------|
| UW API is per-call billing | User constraint | ❌ INCORRECT | Monthly subscription model |
| yfinance has no rate limits | User constraint | ✅ Correct | Unlimited free access |
| Finnhub free tier is 60/min | User constraint | ✅ Correct | Documented in API docs |
```

**When to do this:**
- During `/plan-1a-explore` research phase
- Before any `/plan-3-architect` planning
- When user states something as fact that would significantly affect design
- When building features around external service constraints

**How to challenge respectfully:**
- "Before I design around [assumption], let me verify it..."
- "I found something different in the docs - [X] is actually [Y]. Want me to proceed with the corrected understanding?"
- "Your constraint about [X] appears to be [correct/incorrect] based on [source]. This affects [what]."

**Why this matters:** Building systems around incorrect assumptions creates technical debt that's expensive to remove later (see: budget tracking removal).

### Code Style Principles

**General:**
- Functional, immutable patterns preferred where practical
- async/await for I/O operations (httpx, database, IB API)
- Strict type hints throughout - no `Any` without justification
- Use `dataclasses` or `pydantic` for data structures
- Underscore prefix (`_var`) for intentionally unused variables
- Python 3.11+ features acceptable (match statements, etc.)

**Error Handling:**
- Validate at boundaries (user input, external APIs)
- Fail fast with clear error messages
- Don't swallow errors silently

**Dependencies:**
- Explicit over implicit
- No circular dependencies
- Clear dependency direction (apps -> packages -> external)

<!-- USER CONTENT START: code_style_additions -->
**Text Adventure Domain Specifics:**
- Game state stored as JSON; use Pydantic models for validation
- All text content (descriptions, messages) are strings, never f-strings with logic
- Parser output is always a structured Command object, not raw strings
- LLM responses validated against JSON schema before use
- Separate "game definition" (static) from "game state" (mutable)
- Use context managers for LLM client sessions
- Log all LLM API calls with token counts for cost tracking

**Observability:**
- All external API calls must be traced (LLM, HTTP, database)
- Traces should include: operation name, key parameters, latency, error status
- Use structured span attributes, not string concatenation
- Token counts are mandatory for LLM calls (cost visibility)
- Keep tracing overhead minimal; batch exports, sample in production
<!-- USER CONTENT END: code_style_additions -->

### File Operations Checklist

**When renaming, moving, or deleting files:**

1. Search for references to the old path:
   ```bash
   grep -r "old-filename" --include="*.md" --include="*.py" --include="*.toml"
   ```
2. Check for README.md or index files in the same/parent directory
3. Check any ADR index if touching ADRs
4. Update any documentation, imports, or links that reference changed files
5. Verify links still work after changes

### Testing Philosophy

<!-- CONDITIONAL: testing_philosophy != manual -->
**Test Documentation Block Format:**

For TAD/TDD workflows, every test file should include a Test Doc block:

```python
"""
TEST DOC: [Feature/Component Name]

WHAT: [What behavior is being tested]
WHY: [Why this test exists - what bug/requirement it covers]
HOW: [Brief description of test approach]

CASES:
- [Case 1]: [Expected behavior]
- [Case 2]: [Expected behavior]

EDGE CASES:
- [Edge case]: [How it's handled]
"""
```
<!-- END CONDITIONAL -->

**Testing Approach:**
| Philosophy | When to Use | Key Principle |
|------------|-------------|---------------|
| TDD | New features with clear specs | Write test first, then implementation |
| TAD | Exploratory development | Tests document discoveries |
| BDD | User-facing features | Describe behavior from user perspective |
| Lightweight | Simple utilities | Focus on edge cases and contracts |
| Manual | UI-heavy features | Supplement with manual verification |
| Hybrid | Complex projects | Mix approaches per component |

<!-- USER CONTENT START: testing_specifics -->
**TDD for Text Adventure:**
- Write tests first - they define parser behavior and game logic contracts
- Mock all LLM calls with realistic fixture responses
- Use `pytest-recording` or VCR.py to capture real LLM responses for fixtures
- Test edge cases: ambiguous commands, missing objects, invalid directions
- Parser tests: verify exact command parsing (GET LAMP → Command(verb=TAKE, obj=lamp))
- Game state tests: verify state transitions are deterministic

**Test Organization:**
```
tests/
  unit/           # Parser, game logic, no I/O
  integration/    # LLM client tests with mocked responses
  fixtures/       # Sample games, recorded LLM responses
  conftest.py     # Shared fixtures (game instances, mock LLM clients)
```

**Critical Test Scenarios:**
- Parser handles all standard verbs (GET, DROP, EXAMINE, GO, OPEN, CLOSE, etc.)
- Ambiguity resolution ("Which lamp?")
- Invalid commands produce helpful errors
- Game state round-trips correctly (save/load)
- LLM generation produces valid game JSON
- AI player makes progress (doesn't loop forever)
<!-- USER CONTENT END: testing_specifics -->

### Verification Philosophy

**Multi-layer verification catches different bugs:**

| Layer | What It Catches | What It Misses |
|-------|-----------------|----------------|
| Type checking | Import/export mismatches, type errors | Runtime behavior, UI interactions |
| Linting | Style issues, common mistakes | Logic errors, integration issues |
| Unit tests | Function-level logic | Integration, UI flow |
| Integration tests | Component interactions | UI polish, UX issues |
| Manual testing | UI interactions, user flows | Edge cases without explicit testing |

**Do not skip layers.** Each catches issues the others miss.

**Pre-Commit Verification:**
```bash
# Run all verification layers before committing
mypy src/                 # Type checking
ruff check .              # Linting
ruff format .             # Format code (auto-fix)
pytest                    # Tests
```

**Note on formatting:** If `ruff format .` modifies files you didn't otherwise change, commit those formatting changes separately (e.g., `style: format with ruff`) to keep feature commits focused and git blame useful.

---

<!-- SECTION: DOCUMENTATION_REQUIREMENTS -->
<!-- REQUIRED -->
## Documentation Requirements

### Exit Criteria (REQUIRED)

**Before considering any task complete, verify documentation is in sync:**

1. **Architecture Decision Records (ADRs):**
   - [ ] Does this change diverge from any existing ADR? -> Update or supersede it
   - [ ] Does this introduce a significant architectural decision? -> Create a new ADR
   - [ ] Are any ADRs now outdated due to this change? -> Update status

2. **README Files:**
   - [ ] Does the relevant README reflect current behavior?
   - [ ] Are setup instructions still accurate?
   - [ ] Are any documented features now changed or removed?

3. **Plan/Spec Status:**
   - [ ] If implementing a plan, is the status updated (DRAFT -> ACCEPTED -> SUPERSEDED)?
   - [ ] Are related plans cross-referenced if they overlap?

4. **Project Instructions:**
   - [ ] Does this change affect conventions documented in CLAUDE.md?
   - [ ] Is the project status section still accurate?
   - [ ] Are any architecture descriptions now outdated?

**Why this matters:** Documentation drift causes confusion, wasted investigation time, and bugs when developers follow outdated guidance.

### README Synchronization

**Triggers - Update README when:**
- Adding/removing commands or scripts
- Changing setup or installation steps
- Adding/removing features
- Changing environment requirements
- Modifying API endpoints or interfaces

**README Checklist:**
```
[ ] Project description accurate
[ ] Installation steps work on fresh clone
[ ] All documented commands are valid
[ ] Environment variables documented
[ ] Dependencies listed with versions
[ ] Examples reflect current API
```

### ADR Management

**ADR Triggers (create a new ADR when):**
- Choosing between multiple viable approaches (document why this one)
- Deviating from established patterns (document the exception)
- Making technology choices (document alternatives considered)
- Changing how components/packages interact (document the architecture)

**ADR Format:**
```markdown
# ADR-[NUMBER]: [TITLE]

## Status
[DRAFT | ACCEPTED | SUPERSEDED by ADR-XXX | DEPRECATED]

## Context
[Why is this decision needed? What problem are we solving?]

## Decision
[What did we decide?]

## Consequences
### Positive
- [Benefit 1]

### Negative
- [Tradeoff 1]

### Neutral
- [Observation 1]

## References
- [Related ADRs, external docs, discussions]
```

**ADR Maintenance:**
- Review ADRs quarterly or when major changes occur
- Mark superseded ADRs clearly with pointer to replacement
- Keep ADR index updated (docs/adr/README.md or similar)

### Micro-Context Standards

**File Headers (for complex files):**
```python
"""
[FILENAME]

PURPOSE: [What this file does]
OWNER: [Team or person responsible]
DEPENDENCIES: [Key external dependencies]

ARCHITECTURE NOTES:
[Any non-obvious design decisions or patterns]
"""
```

**Front-Matter (for documentation files):**
```yaml
---
title: [Document Title]
status: [draft | review | final]
last_updated: [YYYY-MM-DD]
related:
  - [path/to/related/doc.md]
---
```

**Contextual Comments:**
- Use `# WHY:` for non-obvious decisions
- Use `# TODO:` with ticket/issue reference
- Use `# HACK:` with explanation and remediation plan
- Use `# PERF:` for performance-critical sections

---

<!-- SECTION: PROJECT_SPECIFIC -->
<!-- OPTIONAL -->
## Project Architecture

<!-- USER CONTENT START: architecture -->
### Overview

```
┌─────────────────┐     ┌─────────────────┐
│   LLM Backend   │     │   Game Engine   │
│ (Claude/Ollama) │     │  (state mgmt)   │
└────────┬────────┘     └────────┬────────┘
         │                       │
    ┌────▼────┐             ┌────▼────┐
    │Generator│             │ Parser  │
    │ (create │             │(commands│
    │  games) │             │→actions)│
    └────┬────┘             └────┬────┘
         │                       │
         └───────────┬───────────┘
                     │
               ┌─────▼─────┐
               │    CLI    │
               │ (commands)│
               └─────┬─────┘
                     │
         ┌───────────┼───────────┐
         │           │           │
    ┌────▼────┐ ┌────▼────┐ ┌────▼────┐
    │ Curses  │ │  Plain  │ │  JSON   │
    │   UI    │ │  Text   │ │ Output  │
    └─────────┘ └─────────┘ └─────────┘
```

**Data Flow - Generate:**
1. CLI invokes generator with theme/parameters
2. Generator prompts LLM with structured output schema
3. LLM returns game JSON (rooms, objects, verbs, puzzles)
4. Generator validates against Pydantic models
5. Game saved to .json file

**Data Flow - Play (Human):**
1. CLI loads game JSON → GameEngine initializes state
2. Player types command → Parser produces Command object
3. GameEngine executes command → State updated
4. GameEngine returns narrative text → CLI displays

**Data Flow - Play (AI):**
1. CLI loads game JSON → GameEngine initializes state
2. GameEngine provides current state to AIPlayer
3. AIPlayer (LLM) generates command
4. Parser validates command → GameEngine executes
5. Loop until win/lose/max_turns

### Directory Structure

```
text-adventure/
  src/
    text_adventure/
      __init__.py
      cli.py              # Typer CLI entry points
      config.py           # Settings, LLM backend config
      models/
        game.py           # Pydantic models: Room, Object, Game, etc.
        command.py        # Command, Verb enums
        state.py          # GameState (mutable state)
      parser/
        __init__.py
        lexer.py          # Tokenize input
        parser.py         # Parse tokens → Command
        resolver.py       # Resolve ambiguous objects
      engine/
        __init__.py
        engine.py         # GameEngine: executes commands
        actions.py        # Action handlers (take, drop, go, etc.)
      generator/
        __init__.py
        generator.py      # LLM game generation
        schemas.py        # JSON schemas for LLM output
        prompts.py        # Prompt templates
      player/
        __init__.py
        ai_player.py      # LLM-based player
      llm/
        __init__.py
        client.py         # Abstract LLM client
        anthropic.py      # Claude implementation
        ollama.py         # Ollama implementation
      ui/
        __init__.py
        plain.py          # Plain text output
        curses_ui.py      # Curses-based UI (future)
        ascii_art.py      # ASCII art generator (future)
  tests/
    unit/
    integration/
    fixtures/
    conftest.py
  docs/
    adr/
  pyproject.toml
```

### Technology Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| CLI | Typer + Rich | Command-line interface with nice formatting |
| LLM (Cloud) | anthropic SDK | Claude API for generation/playing |
| LLM (Local) | ollama-python | Local model support |
| Validation | Pydantic v2 | Game JSON validation, config |
| UI | curses (stdlib) | Terminal UI (future) |
| Testing | pytest | Test framework |
| Observability | OpenTelemetry | Distributed tracing |

### Domain Concepts

| Concept | Definition | Where Used |
|---------|------------|------------|
| **Game** | Complete game definition (rooms, objects, verbs) | generator, engine |
| **Room** | Location with description, exits, contained objects | models, engine |
| **Object** | Interactive item with attributes and action handlers | models, engine |
| **Verb** | Player action (TAKE, DROP, EXAMINE, GO, etc.) | parser, engine |
| **Command** | Parsed player input (verb + objects) | parser, engine |
| **GameState** | Mutable state (location, inventory, object states) | engine |
| **Action** | Executable game logic for a verb | engine/actions |

### Game JSON Format

```json
{
  "metadata": {
    "title": "The Haunted Manor",
    "author": "Generated",
    "version": "1.0"
  },
  "rooms": [
    {
      "id": "entrance",
      "name": "Entrance Hall",
      "description": "A grand entrance hall with marble floors...",
      "exits": {"north": "library", "east": "kitchen"},
      "objects": ["chandelier", "coat_rack"]
    }
  ],
  "objects": [
    {
      "id": "brass_key",
      "name": "brass key",
      "adjectives": ["brass", "small", "ornate"],
      "description": "A small brass key with an ornate handle.",
      "location": "entrance",
      "attributes": {"takeable": true, "examined": false},
      "actions": {
        "examine": "The key has tiny engravings of roses.",
        "use_with:locked_door": {
          "condition": "locked_door.locked",
          "effect": "The door clicks open!",
          "state_change": {"locked_door.locked": false}
        }
      }
    }
  ],
  "verbs": [
    {"verb": "take", "aliases": ["get", "grab"], "requires_object": true},
    {"verb": "examine", "aliases": ["look at", "x"], "requires_object": true}
  ],
  "initial_state": {
    "current_room": "entrance",
    "inventory": [],
    "flags": {}
  },
  "win_condition": {"type": "reach_room", "room": "treasure_room"}
}
```
<!-- USER CONTENT END: architecture -->

---

<!-- SECTION: WORKFLOWS -->
<!-- CONDITIONAL: project_type = web-app OR project_type = mobile -->
## Manual UI Testing (CRITICAL)

**TypeScript/compilation passing is NOT sufficient.** Before committing any UI changes:

1. **Start the app(s)** and manually test every feature you touched
2. **Click every button** - verify handlers are actually connected
3. **Test complete user flows** - Create -> Read -> Update -> Delete
4. **Test affected platforms** if changes touch shared code

**UI Testing Checklist:**
```
For each new/modified feature:
[ ] Started the app(s)
[ ] Clicked through the UI - buttons, forms, modals
[ ] Verified data persists - created item appears in list
[ ] Verified actions work - edit updates, delete removes
[ ] Checked console for errors - no red errors in DevTools
[ ] Tested on affected platforms
```

**Common issues this catches:**
- Event handlers not connected (button does nothing)
- Navigation missing required parameters
- Drag-and-drop listeners blocking click handlers
- Missing CSS/styles for new components
- State not updating after mutations

**Root cause of missed bugs:** Assuming "code compiles" means "feature works."
<!-- END CONDITIONAL -->

<!-- USER CONTENT START: workflows -->
### CLI Command Structure

```bash
# Game generation
text-adventure generate                    # Interactive generation
text-adventure generate --theme "haunted house" --rooms 10
text-adventure generate --from-outline outline.txt

# Playing games
text-adventure play game.json              # Human plays
text-adventure play game.json --debug      # Show game state after each turn
text-adventure ai-play game.json           # AI plays
text-adventure ai-play game.json --model ollama/mistral

# Game management
text-adventure validate game.json          # Check game JSON is valid
text-adventure edit game.json              # Open in editor with validation
text-adventure list                        # List saved games

# Configuration
text-adventure config show                 # Show current configuration
text-adventure config set llm.provider anthropic
text-adventure config set llm.model claude-sonnet-4-20250514
```

### Planning Workflow Compliance (CRITICAL)

**The /plan commands are GATES that require user approval before proceeding:**

| Command | Purpose | STOP Point |
|---------|---------|------------|
| `/plan-1a-explore` | Research only | **STOP** - Output findings, wait for user |
| `/plan-1b-specify` | Create specification | **STOP** - Wait for user review |
| `/plan-2-clarify` | Ask clarifying questions | **STOP** - Wait for answers |
| `/plan-3-architect` | Create implementation plan | **STOP** - Wait for approval |
| `/plan-6-implement-phase` | Implement ONE phase | **STOP** - Wait before next phase |

**Rules:**
- **NEVER** proceed from research to implementation without explicit user approval
- **NEVER** implement multiple phases without pausing for feedback
- **NEVER** treat a plan with "READY FOR APPROVAL" status as approved
- When in doubt, ask: "Should I proceed with [next step]?"

**Why this matters:** The user owns the direction. Planning gates exist so they can course-correct before significant work happens. Bypassing gates removes user agency and risks building the wrong thing.

### Commit Cadence

**For small changes (CS-1, CS-2):**
- Commit when the user requests, or ask if you should commit

**For multi-phase implementations (CS-3+):**
- **Default: Commit after each phase** with tests passing
- At minimum, commit at natural boundaries (every 2-3 phases)
- Ask upfront if unclear: "Should I commit after each phase?"

**Why this matters:** Small, focused commits enable `git bisect`, make code review possible, and preserve the narrative of how the system evolved. A single 12k-line commit defeats the purpose of version control.

**Anti-pattern:** Accumulating all work and committing only when asked "is this committed?"

### Handling Delayed/Timed Requests

**When user asks "wait N minutes, then do X":**

Use a **blocking** approach, not background execution:

```python
# CORRECT: Blocking wait - continues automatically after timer
Bash: sleep 2400  # with timeout=2400000 (40 min)
# Then continue with the work immediately

# WRONG: Background wait - does NOT auto-continue
Bash: sleep 2400  # with run_in_background=true
# Timer completes but nothing triggers follow-up
```

**Why blocking works:** A blocking call keeps the conversation "turn" open. When the command completes, execution continues naturally with the follow-up work.

**Why background fails:** Background tasks return immediately and mark the task as complete later, but there's no callback mechanism. You must explicitly poll with `TaskOutput` to check completion.

**Correct pattern:**
```bash
# Set appropriate timeout (ms) for the wait duration
sleep 2400  # timeout=2400000, then continue with work
```

**If the wait is very long (>10 min)**, consider:
1. Asking user if they want to wait or return later
2. Using `TaskOutput` with `block=true` to wait for a background task
3. Breaking work into "set timer" and "when you return, say 'continue'"

**Anti-pattern:** Using `run_in_background` for a timer and assuming work happens automatically.

### Development Workflow

1. **TDD Cycle:**
   - Write failing test for parser/engine behavior
   - Implement minimum code to pass
   - Refactor with tests green
   - Commit with descriptive message

2. **Adding a New Verb:**
   - Add to Verb enum in `models/command.py`
   - Add parser tests in `tests/unit/parser/`
   - Implement handler in `engine/actions.py`
   - Add to default verb list in generator schemas

3. **Adding LLM Backend:**
   - Create client in `llm/` implementing base interface
   - Add to backend registry
   - Add integration tests with recorded responses

### Environment Configuration

```bash
# .env (not committed)
ANTHROPIC_API_KEY=xxx         # For Claude
OLLAMA_HOST=http://localhost:11434  # For local models
TEXT_ADVENTURE_DATA_DIR=~/.text-adventure/
LOG_LEVEL=INFO

# OpenTelemetry (optional)
TEXT_ADVENTURE_OTEL_ENABLED=true              # Enable tracing
TEXT_ADVENTURE_OTEL_SERVICE_NAME=text-adventure  # Service name for traces
TEXT_ADVENTURE_OTEL_ENDPOINT=http://localhost:4317  # OTLP endpoint (omit for console only)
```
<!-- USER CONTENT END: workflows -->

---

<!-- SECTION: LEARNING_REFLECTION -->
<!-- REQUIRED -->
## Learning & Reflection

### Recent Learnings

<!--
After completing each phase or significant task, capture learnings here.
This section is prompted by /plan-6-implement-phase completion.

Entry Format:
## [DATE] - [TOPIC TITLE]

**Context:** [What were you working on?]

**Discovery:** [What did you learn? What surprised you?]

**Impact:** [How does this affect future work?]

**References:** [Related files, PRs, ADRs]

**Tags:** #gotcha | #pattern | #antipattern | #performance | #security | #ux
-->

<!-- USER CONTENT START: learnings -->
*No learnings yet - greenfield project*
<!-- USER CONTENT END: learnings -->

### Known Issues & Technical Debt

<!-- USER CONTENT START: tech_debt -->
| Issue | Severity | Context | Remediation |
|-------|----------|---------|-------------|
| LLM state consistency | Med | LLMs simulate state incorrectly ~40% of time | Server-side state authority |
| Ambiguity resolution | Low | "GET LAMP" when multiple lamps exist | Implement resolver with clarification prompts |
<!-- USER CONTENT END: tech_debt -->

### Post-Implementation Notes

<!-- USER CONTENT START: post_impl -->
### 2026-01-30 - Project Initialization

- CLAUDE.md customized for text adventure domain
- Architecture planned with LLM generation + traditional parser hybrid
<!-- USER CONTENT END: post_impl -->

---

<!-- SECTION: APPENDICES -->
## Appendices

### Appendix A: Commit Format Standards

```
<type>(<scope>): <description>

[optional body]

Co-Authored-By: Claude <noreply@anthropic.com>
```

**Types:**
| Type | When to Use |
|------|-------------|
| `feat` | New feature |
| `fix` | Bug fix |
| `refactor` | Code change that neither fixes nor adds |
| `docs` | Documentation only |
| `test` | Adding/updating tests |
| `chore` | Maintenance tasks |
| `ci` | CI/CD changes |

**Scope:** Use the most specific relevant area (component, package, feature)

**Examples:**
```
feat(fetcher): add Alpha Vantage stock data client
feat(analysis): implement momentum crossover strategy
fix(ib-client): handle connection timeout gracefully
refactor(store): extract repository pattern for stocks
test(backtest): add edge cases for market holidays
docs(readme): document IB Gateway setup
```

**Scopes for this project:**
`cli`, `parser`, `engine`, `generator`, `player`, `llm`, `ui`, `models`, `config`

### Appendix B: Complexity Scoring Reference

Use CS 1-5 instead of time estimates:

| Score | Scope | Risk | Examples |
|-------|-------|------|----------|
| **CS-1** | Single file, isolated change | Minimal | Fix typo, update constant, add log |
| **CS-2** | Few files, minimal integration | Low | Add simple endpoint, new utility function |
| **CS-3** | Multiple components, moderate complexity | Some | New feature with tests, refactor module |
| **CS-4** | Cross-cutting concerns, significant integration | Notable | Authentication system, major refactor |
| **CS-5** | System-wide impact, high uncertainty | Significant | Architecture change, new core abstraction |

**Usage in Plans:**
```markdown
## Tasks
- [ ] Add user endpoint (CS-2)
- [ ] Implement caching layer (CS-4)
- [ ] Update config constant (CS-1)
```

### Appendix C: Extension Points by Project Type

<!-- CONDITIONAL: project_type = web-app -->
**Web App Extensions:**
- Component library documentation
- State management patterns
- API client conventions
- Styling/theming approach
<!-- END CONDITIONAL -->

<!-- CONDITIONAL: project_type = cli -->
**CLI Extensions:**
- Command structure and naming
- Flag conventions
- Output formatting (human vs machine)
- Configuration file handling
<!-- END CONDITIONAL -->

<!-- CONDITIONAL: project_type = backend -->
**Backend Extensions:**
- API versioning strategy
- Database migration approach
- Authentication/authorization patterns
- Logging and monitoring conventions
<!-- END CONDITIONAL -->

<!-- CONDITIONAL: project_type = library -->
**Library Extensions:**
- Public API design principles
- Versioning and changelog conventions
- Documentation generation
- Example maintenance
<!-- END CONDITIONAL -->

<!-- USER CONTENT START: extensions -->
**CLI Output Conventions:**
- Game text in plain prose, commands in `monospace`
- Room names in bold when entering
- Inventory displayed as bullet list
- Verbose mode (`-v`) shows LLM token usage
- Debug mode (`--debug`) shows game state JSON after each turn

**Configuration Hierarchy:**
1. CLI flags (highest priority)
2. Environment variables
3. Config file (`~/.text-adventure/config.toml`)
4. Defaults (lowest priority)

**Text Adventure Conventions:**
- Room descriptions: 2-4 sentences, vivid but concise
- Object descriptions: 1-2 sentences
- Parser messages: Zork-style ("I don't understand that." / "You can't see any X here.")
- Win/lose messages: Celebratory or sympathetic, never abrupt
<!-- USER CONTENT END: extensions -->

---

<!-- SECTION: META -->
## Template Maintenance

This template follows progressive disclosure:
- **Lines 1-50:** Quick Start - essential info for immediate productivity
- **Lines 51-150:** Core Guidance - universal principles for all projects
- **Lines 151-250:** Documentation Requirements - keeping docs in sync
- **Lines 251-350:** Project-Specific - customizable architecture details
- **Lines 351-450:** Workflows - conditional by project type
- **Lines 451+:** Learning & Appendices - reference material

**Bootstrap:** Run `/plan-0-constitution` to customize this template for your project type.

**User Content:** Sections between `<!-- USER CONTENT START -->` and `<!-- USER CONTENT END -->` are preserved during template updates.

**Conditional Sections:** Sections marked with `<!-- CONDITIONAL: ... -->` are shown/hidden based on project configuration.
