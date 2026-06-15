# ADR-0002: Keyword-Based Routing (Not LLM)

**Date:** 2026-06-15
**Status:** Accepted

## Context

The old codebase used LLM-based intent classification in `agent_council.py` (585 lines) and `cs_orchestrator.py` (982 lines) to route user messages to specialist agents. This was:

- Slow (LLM call on every message)
- Expensive (tokens per routing decision)
- Non-deterministic (same message could route differently)

## Decision

**Use keyword substring matching instead of LLM for agent routing.** Pure Python function (`router.py`, 49 lines). No API calls, no tokens, deterministic.

## Algorithm

1. Lowercase the user message
2. For each agent, count how many keywords appear as substrings
3. Score = sum of matched keyword lengths
4. Return highest-scoring agent

## Consequences

### Positive

- **Instant** — no API call, no latency
- **Free** — zero tokens
- **Deterministic** — same message always routes the same way
- **Testable** — pure function, trivially unit-tested
- **49 lines** vs 1,567 lines (97% reduction)

### Negative

- No semantic understanding ("I need to move stuff" won't match "shipment")
- Requires well-chosen keywords in `agents.json`
- Can't handle ambiguous multi-domain messages as well as an LLM

### Mitigation

- Claude Desktop handles the initial routing ambiguity through the `chat_odoo` tool
- Keywords in `agents.json` are AI-generated during schema enrichment (one-time)
- If no keywords match, `chat_odoo` returns all agent descriptions for Claude to pick
