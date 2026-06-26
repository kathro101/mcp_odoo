# Root Cause Fix: Universal Schema-Missing & Preview Guidance

**Date:** 2026-06-25
**Severity:** HIGH — affects ALL models
**Scope:** All 4 layers: MCP Server → Odoo Service → Operations → Shared

---

## The Problem (Model-Agnostic)

For **any** Odoo model — whether `ops_logistics.shipment`, `purchase.order`, `hr.expense`, or a custom `x_custom.model` — if the schema is missing or incomplete, the system fails in the same two ways:

1. **Claude doesn't ask the right follow-up questions** because it receives no field metadata to guide questioning.
2. **Even when users specify field values, the system may not fill them correctly** because preview doesn't validate value types, and Claude has no per-field guidance.

The `ops_logistics.shipment` case is just the most visible example. The root causes are architectural.

---

## Root Causes (Universal)

### RC1 🔴: Missing Schema = Silent Failure (ANY model)

**Current behavior** (`tools.py:201-208`):
```python
except KeyError:
    parts.append(f"Model: {route.model_key}")  # ← bare string, zero context
```

Claude receives just `"Model: x_y_z"` — no field info, no aliases, no hints, no error indication. This applies to **every** model without a schema file.

**Fix**: Return an actionable diagnostic block telling Claude:
- The model has no schema loaded
- This means `schema_discovery` has not been run (or the model is new)
- Suggest running `list_models` to find models that DO have schemas
- Suggest running `python scripts/run_schema_discovery.py`

### RC2 🟡: `preview_record()` Only Checks Presence, Not Validity (ANY model)

**Current behavior** (`create.py:47-49`):
```python
filled = [f for f in schema.create_fields if f in params and params[f]]
missing = [f for f in schema.required_fields if f not in params or not params.get(f)]
```

`params[f]` is truthy for `0`, `""`, `[]`, etc. — so `partner_id: 0` counts as "filled". A `many2one` field with garbage text passes. This affects **every** model.

**Fix**: Add per-field-type guidance in preview output. For each missing field, include how to ask for it and what format is expected.

### RC3 🟡: Schema Output Is Descriptive, Not Prescriptive (ANY model)

**Current behavior** (`tools.py:_format_schema_for_claude`):
```
- `partner_id` (many2one → res.partner): Contact *REQUIRED*
```
Tells Claude WHAT, not HOW to ask. Claude must interpret raw schema into conversational follow-up questions. Works for standard models (LLMs know `res.partner`) but fails for custom models.

**Fix**: Generate "ask prompts" from field metadata — type-aware, selection-aware, relation-aware.

### RC4 🟢: No Session-Context Accumulation (ANY model)

Multi-turn workflows (ask → answer → ask) are unsupported because the session store isn't exposed to Claude in responses.

**Fix**: Include accumulated session context in routing responses when `session_id` is present.

---

## Fix Plan (Model-Agnostic)

### Phase 1: Immediate — Diagnostics & Preview (P0)

| Item | What | File | Effort |
|------|------|------|--------|
| **A** | Actionable diagnostic when any schema is missing | `tools.py` | 15 min |
| **B** | Per-field guidance in preview (type-aware hints) | `create.py` | 30 min |
| **C** | "Ask prompts" in schema formatting for all models | `tools.py` | 30 min |

### Phase 2: Schema Coverage (P1)

| Item | What | File | Effort |
|------|------|------|--------|
| **D** | Run schema discovery for all models in agents.json | `scripts/` | runtime |
| **E** | Schema discovery warning in setup wizard | `wizard.py` | 15 min |

### Phase 3: UX (P2)

| Item | What | File | Effort |
|------|------|------|--------|
| **F** | Multi-model ranking in router (user selects) | `router.py` | 20 min |
| **G** | Session-context hints in responses | `tools.py`, `session_store.py` | 20 min |

---

## Verification (Applies to ANY model)

1. Route to a model WITH schema → rich output with ask-prompts, aliases, hints
2. Route to a model WITHOUT schema → clear diagnostic, not bare string
3. Preview partial params → `needs_input` with per-field type guidance
4. Preview invalid params (wrong types) → warnings, not silent "success"
5. Multi-turn session → accumulated context visible in responses
6. Test with 3 different models across different agents (logistics, sales, accounting)
