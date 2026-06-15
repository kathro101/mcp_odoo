# Feature: Keyword-Based Agent Routing

**Implemented:** 2026-06-15  
**Files:** `src/odoo_service/router.py` (49 lines)  
**Tests:** `tests/test_router.py` (9 tests)

## What It Does

Routes user messages to the correct agent using keyword substring matching — no LLM needed.

### Algorithm

1. Lowercase the message
2. For each agent, count how many of its keywords appear as substrings in the message
3. Score = sum of matched keyword lengths (longer keywords = better matches)
4. Return the agent with the highest score (or None if no match)

### Example

```
Message: "Create a shipment for ACME Corp"
Agents:
  - logistics: keywords=["shipment", "delivery", "stock"] → "shipment" matches → score=8
  - salesman:  keywords=["sale", "order", "quotation"] → no match → score=0
  - accountant: keywords=["invoice", "payment"] → no match → score=0
Result: RouteResult(agent_key="logistics", model_key="stock_picking", score=8)
```

## Design Decisions

- **Keyword length scoring** rewards specific matches over generic ones
- **Case-insensitive** matching
- **Substring matching** catches partial words ("ship" matches "shipment")
- **Pure function** — no state, no I/O, trivially testable
- **49 lines total** — vs the old `agent_council.py` (585 lines) + `cs_orchestrator.py` (982 lines)

## Edge Cases Handled

- Empty message → no match
- Empty agents dict → no match
- Unicode/emoji in message → works (only affects matching, not crashed)
- Very long messages (>1000 chars) → handled efficiently
- Multiple matching agents → highest score wins (ties broken by dict iteration order)
