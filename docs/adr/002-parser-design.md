# ADR-002: Parser Design

## Status

Accepted

## Context

Text adventure games require interpreting player input. We had several options:

1. **Conversational AI**: Use an LLM to interpret natural language commands
2. **Simple verb-noun**: Basic parser handling "VERB NOUN" only (GET LAMP)
3. **Full Infocom-style**: Rich parser supporting prepositions and indirect objects (PUT THE BRASS KEY IN THE WOODEN BOX)

Considerations:
- Classic text adventures used sophisticated parsers
- LLM interpretation would add latency and cost to every command
- Parser determinism is important for testing and debugging
- Supporting adjectives helps with disambiguation

## Decision

We implemented a **full Infocom-style parser** that handles:

```
COMMAND := VERB [DIRECT_OBJ] [PREPOSITION INDIRECT_OBJ]
DIRECT_OBJ := [ARTICLE] [ADJECTIVE*] NOUN
INDIRECT_OBJ := [ARTICLE] [ADJECTIVE*] NOUN
```

Examples:
- `GET LAMP` → Command(verb=TAKE, direct=lamp)
- `PUT THE BRASS KEY IN THE WOODEN BOX` → Command(verb=PUT, direct=brass_key, indirect=wooden_box, prep=IN)
- `UNLOCK DOOR WITH KEY` → Command(verb=UNLOCK, direct=door, indirect=key, prep=WITH)

The parser includes:
- **Lexer**: Tokenizes input, handles articles
- **Parser**: Converts tokens to structured Command objects
- **Resolver**: Resolves text references to object IDs using adjective matching

## Consequences

### Positive

- **Zero latency**: Parsing is instant, no API calls needed
- **Deterministic**: Same input always produces same parse result
- **Testable**: Parser behavior can be unit tested exhaustively
- **Authentic feel**: Matches classic text adventure experience
- **Disambiguation**: Adjectives help distinguish "brass key" from "silver key"

### Negative

- **More complex implementation**: ~400 lines of parser code vs ~50 for simple verb-noun
- **Learning curve**: Players need to learn valid command syntax
- **Vocabulary limits**: Only predefined verbs are recognized

### Neutral

- Error messages follow classic text adventure conventions ("I don't understand that.")
- Multi-word verbs supported (PICK UP, LOOK AT)

## References

- [Zork Parser History](https://en.wikipedia.org/wiki/Zork#Parser)
- `src/text_adventure/parser/lexer.py` - Tokenization
- `src/text_adventure/parser/parser.py` - Command parsing
- `src/text_adventure/parser/resolver.py` - Object resolution
