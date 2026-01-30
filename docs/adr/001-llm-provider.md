# ADR-001: LLM Provider Selection

## Status

Accepted

## Context

The text adventure system requires LLM capabilities for two primary functions:

1. **Game Generation**: Creating complete game worlds (rooms, objects, puzzles) from high-level themes
2. **AI Player**: Making decisions about what commands to issue during gameplay

We needed to choose which LLM provider(s) to support, considering:
- Quality of structured output generation
- API reliability and documentation
- Cost considerations
- Local/offline capability requirements

## Decision

We chose **Anthropic Claude** as the primary LLM provider, with an architecture that supports adding additional providers (like Ollama for local models) in the future.

Specifically:
- `claude-sonnet-4-20250514` as the default model
- Use Claude's **tool use** feature for guaranteed structured JSON output during game generation
- Abstract `LLMClient` protocol to enable future provider additions

## Consequences

### Positive

- **Reliable structured output**: Claude's tool use feature guarantees valid JSON matching our schema, eliminating parsing failures
- **High-quality generation**: Claude produces creative, coherent game content with good puzzle design
- **Well-documented API**: The Anthropic SDK is stable and well-maintained
- **Future flexibility**: The abstract `LLMClient` protocol allows adding Ollama, OpenAI, or other providers without changing consumer code

### Negative

- **API key required**: Users must have an Anthropic API key to use generation and AI play features
- **Cost**: API calls incur costs (though game generation is typically a one-time operation)
- **Network dependency**: Requires internet connection for LLM features

### Neutral

- Local model support (Ollama) is deferred but architecturally supported
- The `anthropic` SDK adds a dependency but is well-maintained

## References

- [Anthropic Claude Documentation](https://docs.anthropic.com/)
- [Tool Use Guide](https://docs.anthropic.com/en/docs/build-with-claude/tool-use)
- `src/text_adventure/llm/client.py` - Abstract LLM client protocol
- `src/text_adventure/llm/anthropic.py` - Anthropic implementation
