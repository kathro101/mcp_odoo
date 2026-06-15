# Task: Enhanced `list_models` — Semantic Model Discovery for Claude

**Created:** 2026-06-15
**Status:** 🔴 Not started
**Priority:** HIGH — replaces need for vector DB, enables semantic model matching
**Depends on:** Phase 2 (schema_discovery, schema_enrichment), Phase 4 (tools.py)

---

## Problem

When the keyword router fails (no matching keywords in `agents.json`), Claude has no way to discover which Odoo model handles the user's request. Currently:

```
User: "I need to track containers on vessels"
  → router.py: no keyword match → returns no-match
  → chat_odoo returns: "No agent matched. Available agents: logistics, sales..."
  → Claude guesses logistics → calls chat_odoo → gets stock_picking schema
  → stock_picking has no container/vessel fields → dead end
```

Claude needs a way to **semantically search** across all models using its own LLM reasoning — without us building a vector DB.

## Solution: Enhanced `list_models` Tool

Make `list_models` Claude-friendly so Claude can do the semantic matching itself:

### Current `list_models` Response

```
Available Odoo Models (5):
### Transfers (stock.picking)
  Stock transfer document for moving inventory between locations.
  Key: stock_picking
  Fields: name, partner_id, picking_type_id, scheduled_date
...
```

### Proposed `list_models` Response

```
Available Odoo Models (47) — top 10 by relevance:
### Transfers (stock.picking) [score: 15]
  Stock transfer document for moving inventory between locations.
  Match keywords: shipment, delivery, transfer, picking, stock move, receipt, warehouse
  Fields: 25 (required: name, partner_id, picking_type_id)
  Key: stock_picking

### Sales Orders (sale.order) [score: 12]
  Sales order document for managing customer orders, quotations, and revenue.
  Match keywords: sale, order, quotation, quote, SO, revenue, sales
  Fields: 30 (required: partner_id)
  Key: sale_order
...
```

## Design

### 1. Scoring Algorithm (Zero Tokens)

Score each model by relevance using weighted criteria:

```python
def score_model_relevance(model: ModelSchema, user_message: str) -> int:
    score = 0

    # 1. Keyword matches (weight: len(match) — longer keywords = better)
    for kw in model.match_keywords:
        if kw.lower() in user_message.lower():
            score += len(kw)  # "shipment" = 8, "del" = 3

    # 2. Label match (weight: 5 if exact)
    if model.label.lower() in user_message.lower():
        score += 5

    # 3. Model name match (weight: 3)
    if model.odoo_model.replace(".", " ") in user_message.lower():
        score += 3

    # 4. Summary match (weight: 1 per word)
    summary_words = model.summary.lower().split()
    msg_words = set(user_message.lower().split())
    score += len(set(summary_words) & msg_words)

    return score
```

### 2. Response Format

```python
def _format_models_for_claude(
    schemas: list[ModelSchema],
    user_message: str = "",
    top_n: int = 10,
) -> str:
    """Format models sorted by relevance for Claude to semantically match."""

    # Score and sort
    scored = [(score_model_relevance(s, user_message), s) for s in schemas]
    scored.sort(key=lambda x: x[0], reverse=True)

    lines = [f"Available Odoo Models ({len(schemas)}) — top {top_n}:"]

    for score, schema in scored[:top_n]:
        lines.append(f"\n### {schema.label} (`{schema.odoo_model}`) [relevance: {score}]")
        if schema.summary:
            lines.append(f"  {schema.summary}")
        if schema.match_keywords:
            kws = schema.match_keywords[:8]
            lines.append(f"  Keywords: {', '.join(kws)}")
        field_count = len(schema.all_fields)
        req = schema.required_fields[:5]
        req_str = f" (required: {', '.join(req)})" if req else ""
        lines.append(f"  Fields: {field_count}{req_str}")
        lines.append(f"  Key: `{schema.key}`")

    return "\n".join(lines)
```

### 3. How Claude Uses This

```
Turn 1:
  User: "Track containers on vessels"
  Claude calls: list_models(message="Track containers on vessels")
  Server returns: 47 models, top 10 by keyword/name/summary relevance
  Claude reads summaries and keywords:
    - stock.picking: keywords ["shipment", "delivery"] — no "container"
    - x_container.tracking: summary "Tracks shipping containers on vessels" ← MATCH!
  Claude: "I see a model called x_container.tracking. Let me look at its fields."

Turn 2:
  Claude calls: chat_odoo(message="container tracking", ...)
  (or calls chat_odoo with action="preview", model="x_container_tracking", params={...})
```

## Files to Create/Modify

| File                         | Action | Description                                                                                        |
| ---------------------------- | ------ | -------------------------------------------------------------------------------------------------- |
| `src/mcp_server/tools.py`    | Modify | Update `list_models_handler` to accept optional `message` param and return scored/filtered results |
| `src/mcp_server/tools.py`    | Add    | `score_model_relevance()` function                                                                 |
| `src/mcp_server/tools.py`    | Add    | `_format_models_for_claude()` function                                                             |
| `tests/test_mcp_tools_v2.py` | Add    | 5 new tests for enhanced list_models                                                               |

## Tests (TDD Required)

### `list_models` with message

1. **`test_list_models_with_message_returns_scored`** — Passing a message returns models sorted by relevance score
2. **`test_list_models_relevance_scores_keywords`** — Keyword matches contribute to score
3. **`test_list_models_relevance_scores_label`** — Label matches contribute to score
4. **`test_list_models_without_message_returns_all`** — No message → all models unsorted (backward compatible)
5. **`test_list_models_limits_to_top_n`** — Only returns top N by default

### Scoring function

6. **`test_score_model_relevance_keyword_match`** — "shipment" message scores stock_picking higher than sale_order
7. **`test_score_model_relevance_no_match_returns_zero`** — Irrelevant message returns 0
8. **`test_score_model_relevance_label_exact_match`** — "Transfers" matches stock_picking label

## Implementation Steps

1. Add `score_model_relevance()` to `tools.py` (zero tokens, pure Python)
2. Add `_format_models_for_claude()` to `tools.py`
3. Update `list_models_handler(message: str = "")` to accept optional message
4. Update TOOLS definition for `list_models` to include optional `message` param
5. Write 8 tests (TDD)
6. Run full suite

## Acceptance Criteria

- [ ] `list_models` works without message (backward compatible)
- [ ] `list_models(message="shipment")` returns models sorted by relevance
- [ ] Response includes keywords, field count, required fields, summary
- [ ] Claude can semantically match a model that has no keyword routing entry
- [ ] 184 → ~192 tests
- [ ] Zero additional tokens used (pure scoring algorithm, no LLM calls)
