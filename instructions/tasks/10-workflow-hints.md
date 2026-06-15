# Task: Workflow Hints — AI-Generated Domain Knowledge for Custom Models

**Created:** 2026-06-15
**Status:** 🔴 Not started
**Priority:** HIGH — enables Claude to understand custom Odoo modules without training data
**Depends on:** Phase 2 (schema_discovery, schema_enrichment), Task 09 (help text)
**Impact:** ~30-line change to `schema_enrichment.py`, massive improvement for custom module understanding

---

## Problem

Standard Odoo models (`sale.order`, `stock.picking`, `account.move`) are well-understood by LLMs from training data. But **custom modules** (`ops_logistics.shipment`, `x_custom_manufacturing`) are completely unknown to Claude.

Currently, Claude sees field-level data (names, types, aliases) but has **no understanding of how fields work together**:

```
User: "Shipment from Nov 10 to Dec 10, road direct"
       ↓
Claude sees: shipment has date_from, date_to, template_id, milestone_ids
Claude thinks: date_from=Nov 10, date_to=Dec 10 on the shipment header
Claude is WRONG: dates belong on milestone lines, not the header
```

Claude needs **workflow hints** — domain-specific knowledge about how fields interact, common phrases, and cross-model workflows.

## Solution

Add a `workflow_hints` field to `ModelSchema`. Generate it during one-time AI enrichment (cached forever). Render it in `_format_schema_for_claude()`.

### Data Flow

```
Schema Discovery (deterministic)
  → extracts fields, relations, sub-models, types
  → zero tokens
       │
       ▼
Schema Enrichment (one-time AI, cached)
  → for custom models only:
    1. generate field_aliases     ✅ already built
    2. generate match_keywords    ✅ already built
    3. generate summary           ✅ already built
    4. generate workflow_hints    🔴 NEW — this task
  → cached to config/schemas/<key>.json
  → never regenerated
       │
       ▼
chat_odoo / list_models response
  → _format_schema_for_claude() renders workflow_hints
  → Claude reads them alongside field schemas
```

### AI Prompt for Workflow Hints

```python
prompt = (
    f"Model: {schema.odoo_model} ({schema.label})\n"
    f"Summary: {schema.summary}\n\n"
    f"Fields:\n" + "\n".join(field_lines[:40]) + "\n\n"
    f"Sub-models (one-to-many):\n" + "\n".join(sub_lines) + "\n\n"
    "Based on this model's fields and relationships, write 3-5 "
    "workflow hints to help an AI assistant understand:\n"
    "1. Which fields work together (e.g., dates on parent apply to sub-model lines)\n"
    "2. Common user phrases and what they map to beyond field aliases\n"
    "3. Cross-model workflows (e.g., 'from SO123' → link to sale_order_id)\n"
    "4. Template/wizard-driven fields and how they're populated\n"
    "5. Multi-line relationships and how to resolve ambiguity\n\n"
    "Return a JSON object with: {\"workflow_hints\": [\"hint 1\", \"hint 2\", ...]}"
)
```

### Example AI Output

```json
{
    "workflow_hints": [
        "When user says 'from [date] to [date]', set these dates on the milestone lines (milestone_ids), not the shipment header date_from/date_to fields.",
        "When user provides a location sequence like 'Shanghai → Rotterdam → Berlin', match each location to a milestone line by position. The first location is the first milestone's origin, the last location is the last milestone's destination.",
        "'road direct' means select a template where transport_type='road' AND service_type='direct'. The template populates milestones, carriers, and routing automatically.",
        "When user says 'from SO0042' or 'based on sale order', link via sale_order_id and populate stock moves from the sale order's picking operations.",
        "Container numbers, vessel names, BL/AWB numbers, and ETD/ETA dates belong on individual milestone lines, not the shipment header. Each milestone can have its own transport details."
    ]
}
```

### What Claude Would Then See

```
## Model: Shipment (`ops_logistics.shipment`)
Freight shipment with milestone-based routing and template population.

### WORKFLOW HINTS
- When user says 'from [date] to [date]', set dates on milestone lines
  (milestone_ids), not the shipment header.
- 'road direct' → template where transport_type='road', service_type='direct'
- Container numbers, vessel names → milestone lines, not header
- 'from SO123' → link via sale_order_id, populate from sale order lines
- Location sequence 'A → B → C' → match to milestones by position

### FIELD ALIASES
  "customer" → `partner_id`
  "road direct" → `template_id` (look up by transport_type + service_type)
  ...

### REQUIRED FIELDS
  - `partner_id` (many2one → res.partner): Customer *REQUIRED*
  ...
```

## Files to Modify

| File | Change | Lines |
|------|--------|-------|
| `src/shared/types.py` | Add `workflow_hints: str = ""` to `ModelSchema` | +1 |
| `src/odoo_service/schema_enrichment.py` | Add `enrich_workflow_hints()` function | +40 |
| `src/odoo_service/schema_enrichment.py` | Call `enrich_workflow_hints()` in enrichment pipeline | +1 |
| `src/odoo_service/schema_store.py` | Serialize/deserialize `workflow_hints` in `_load_one()` and `_serialize_schema()` | +2 |
| `src/mcp_server/tools.py` | Render `workflow_hints` in `_format_schema_for_claude()` | +6 |
| `src/mcp_server/tools.py` | Render `workflow_hints` in `_format_model_entry()` (list_models) | +4 |

## Tests (TDD Required)

### `ModelSchema.workflow_hints`
1. **`test_model_schema_workflow_hints_defaults_to_empty`** — Defaults to `""`

### Schema Store round-trip
2. **`test_schema_store_roundtrips_workflow_hints`** — Save → reload → hints preserved

### Enrichment
3. **`test_enrich_workflow_hints_generates_hints`** — Mock LLM returns hints → schema has them
4. **`test_enrich_workflow_hints_skips_standard_models`** — Standard models skipped (same as other enrichment)
5. **`test_enrich_workflow_hints_cached_not_regenerated`** — Cache hit → no LLM call
6. **`test_enrich_workflow_hints_handles_llm_error`** — LLM fails → graceful, hints stay empty

### Formatting
7. **`test_format_schema_includes_workflow_hints`** — Schema with hints → output contains "WORKFLOW HINTS"
8. **`test_format_schema_no_workflow_hints`** — Schema without hints → output does NOT contain "WORKFLOW HINTS"

### Integration
9. **`test_chat_odoo_returns_workflow_hints`** — Full routing + schema response includes hints section

## Implementation Steps

1. Add `workflow_hints: str = ""` to `ModelSchema` (1 line)
2. Add `enrich_workflow_hints()` to `schema_enrichment.py` with AI prompt (40 lines)
3. Wire it into the enrichment pipeline (1 line)
4. Update `schema_store` serialization (4 lines)
5. Update `_format_schema_for_claude()` to render hints (6 lines)
6. Update `_format_model_entry()` to render hints (4 lines)
7. Write 9 tests (TDD)
8. Run full suite (~201 tests)

## Acceptance Criteria

- [ ] `ModelSchema.workflow_hints` defaults to `""`
- [ ] `enrich_workflow_hints()` generates hints via AI for custom models
- [ ] Standard models skipped (same logic as other enrichment)
- [ ] Results cached to disk, never regenerated
- [ ] `_format_schema_for_claude()` renders hints as `### WORKFLOW HINTS` section
- [ ] Schema store round-trips `workflow_hints` correctly
- [ ] 192 → ~201 tests
- [ ] Hints appear in `chat_odoo` response between field aliases and required fields
