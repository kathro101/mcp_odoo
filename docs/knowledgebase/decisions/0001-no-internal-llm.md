# ADR-0001: No Internal LLM

**Date:** 2026-06-15
**Status:** Accepted

## Context

The old `agentic_tool_odoo` codebase had its own LLM pipeline (Anthropic Claude Haiku) running inside `AgentConversation` for intent parsing, response synthesis, and clarification. Meanwhile, the MCP client (Claude Desktop) also has a powerful LLM.

## Decision

**Remove all internal LLM calls from runtime code.** Claude Desktop is the ONLY AI brain. The MCP server is a thin data bridge — it provides schemas, executes Odoo operations, and returns structured results. Claude handles all NLP, intent parsing, clarification, and response generation.

## Consequences

### Positive

- **No token waste** — one AI instead of two processing the same message
- **Simpler code** — removed `PromptBuilder` (506 lines), `ContextProvider` (157 lines), `MemoryManager`, `Synthesis`, `LearnedHints`
- **~83% code reduction** — 15,000 → 2,000 lines
- **Faster** — no serial LLM calls
- **Cheaper** — one API call instead of two

### Negative

- Schema enrichment still needs AI (one-time, offline, cached)
- Claude must understand Odoo schemas (mitigated by `list_models` tool and detailed tool descriptions)
- No fallback if Claude misinterprets (mitigated by providing structured data, not raw Odoo output)

## Exceptions

Schema enrichment (`schema_enrichment.py`) uses AI for:

- Custom model summaries (one-time, cached)
- Field aliases and match keywords (one-time, cached)

These run offline during setup, never at runtime.
