# Investigation: Universal Schema & Preview Failures

**Date:** 2026-06-25
**Severity:** HIGH — affects ALL models
**Status:** Superseded by [universal-schema-fix-plan-2026-06-25.md](universal-schema-fix-plan-2026-06-25.md)

> **Note:** This document was originally scoped to `ops_logistics.shipment` only. The root causes are actually universal — affecting every Odoo model equally. See the linked document for the model-agnostic analysis and fix plan.

---

## Original Analysis (Preserved for Reference)

---

## Root Cause Analysis

### Root Cause #1 (CRITICAL): Missing Schema Files for Logistics Models

**The logistics agent routes to `ops_logistics_shipment`, but NO schema file exists for it.**

In `config/agents.json`:
```json
"logistics": {
    "default_model": "ops_logistics_shipment",
    "models": ["ops_logistics_shipment", "stock.picking", "stock.move", "stock.quant"]
}
```

In `config/schemas/`, only 3 files exist:
- `res_partner.json`
- `sale_order.json`
- `stock_picking.json`

**There is NO `ops_logistics_shipment.json` schema file.**

#### The Full Failure Chain:

```
User: "Create a shipment for me"
    │
    ▼
chat_odoo(message="Create a shipment for me")
    │
    ▼
route_message("Create a shipment for me", agents)
  → "shipment" matches logistics agent keywords → score > 0
  → Returns: RouteResult(agent_key="logistics", model_key="ops_logistics_shipment", score=8)
    │
    ▼
schema_store.get("ops_logistics_shipment")
  → KeyError("Model schema not found: ops_logistics_shipment")  ← CRITICAL FAILURE
    │
    ▼
chat_odoo_handler falls back to:
  "Model: ops_logistics_shipment"   ← NO field info, NO aliases, NO required fields
```

Claude receives **nothing useful** — just a model name with zero context. Claude then has to guess what fields exist, what's required, and what questions to ask. This is the **root cause of both symptoms**.

#### Why this happens:

The schema discovery tool (`scripts/run_schema_discovery.py`) was never run against the user's Odoo instance to discover `ops_logistics.*` models. Without running discovery, the `stock_picking` schema exists as a hand-curated example, but the custom `ops_logistics.shipment` model has no schema.

---

### Root Cause #2 (HIGH): Silent KeyError When Schema Is Missing — No Useful Error for Claude

The keyword router correctly returns `ops_logistics_shipment` as the model. But `chat_odoo_handler` silently swallows the schema lookup failure:

```python
# tools.py lines 201-208
if route.model_key:
    try:
        schema = _get_schema_store().get(route.model_key)
        parts.extend(_format_schema_for_claude(schema))
    except KeyError:
        parts.append(f"Model: {route.model_key}")  # <-- Just prints the key, no diagnostic
```

Claude receives just `"Model: ops_logistics_shipment"` — a bare string with zero context. Claude has no way to know this is an error condition vs a valid response. The system gives Claude no information about WHAT went wrong or HOW to recover.

**Important clarification**: `stock.picking` and `ops_logistics.shipment` are **completely different models**. Falling back to `stock.picking` would route to the wrong model (core Odoo "Transfers" vs the custom shipment module). The correct fix is to give Claude actionable diagnostic information, not silently substitute a different model.

**Fix**: When a schema is missing, return a clear diagnostic telling Claude:
- The model `ops_logistics_shipment` has no schema loaded
- This means schema discovery has not been run for this model
- Claude should tell the user to run `python scripts/run_schema_discovery.py`
- Or Claude can ask the user to manually describe what fields the shipment should have

---

### Root Cause #3 (MEDIUM): Preview Doesn't Validate Field Values, Only Presence

The `preview_record` function only checks whether required fields have **any** value set:

```python
# create.py line 47-49
filled = [f for f in schema.create_fields if f in params and params[f]]
missing = [f for f in schema.required_fields if f not in params or not params.get(f)]
```

This means:
- `params = {"partner_id": 0}` → "filled" (but 0 is an invalid partner ID!)
- `params = {"partner_id": "some random text"}` → "filled" (but should be an integer!)
- `params = {"picking_type_id": 9999}` → "filled" (but 9999 may not exist!)

The preview says "All required fields provided" and returns `status: "success"`, so Claude proceeds to create. But the values are garbage. Odoo either rejects the create (and Claude doesn't understand why) or worse, Odoo accepts it with default values, ignoring the user's specified fields.

**Fix**: Enhance preview to validate field types and provide field-specific guidance for each missing/incorrect field.

---

### Root Cause #4 (MEDIUM): Claude Gets Schema Info But No "Questions to Ask" Guidance

Even when a schema IS found (for `stock_picking`), the `_format_schema_for_claude` output is descriptive but not **prescriptive**:

```
### REQUIRED FIELDS
  - `name` (char): Reference *REQUIRED*
  - `partner_id` (many2one → res.partner): Contact *REQUIRED*
  - `picking_type_id` (many2one → stock.picking.type): Operation Type *REQUIRED*
```

This tells Claude WHAT is required, but not HOW to ask the user. Claude needs to interpret this and generate questions. A better output would be:

```
### REQUIRED FIELDS — Ask the user for these:
  - `name` (char): Reference — "What reference number should this shipment have?"
  - `partner_id` (many2one → res.partner): Contact — "Which customer is this shipment for?"
  - `picking_type_id` (many2one → stock.picking.type): Operation Type — "What type of operation? (delivery, receipt, internal transfer?)"
```

**Fix**: Generate "ask prompts" from field metadata (type, string, selection options, relation) in the schema formatting.

---

## Additional Findings

### Finding #5: Field Aliases Work But Are Under-Promoted

The field aliases system works correctly (e.g., "customer" → "partner_id", "type" → "picking_type_id"). But when the schema is missing (RC #1), no aliases are available at all.

### Finding #6: Workflow Hints Are Heuristic-Only for Missing Schemas

The `apply_heuristics` function generates useful hints like:
```
- **Sub-records**: After creating the parent record, create sub-records via the sub-model fields.
- **Template flow**: After creating the parent record, search for templates...
```

But this only works if a schema exists. With no schema → no hints.

### Finding #7: No Session-Context Carryover

When Claude asks "Which customer?" and the user responds "ACME Corp", Claude needs to:
1. Search for ACME Corp → gets `partner_id: 42`
2. Call preview with `partner_id: 42`
3. Get back what's still missing
4. Ask the user what's still missing

This multi-turn workflow IS supported by `session_id` in `SessionStore`, but the schema formatting doesn't tell Claude to use session state for accumulating params.

---

## Fix Plan

### Phase 1: Immediate Fix (Must Do — Addresses RC #1, #2)

**A. Create schema for `ops_logistics.shipment`**

Run schema discovery against the user's Odoo instance:
```bash
python scripts/run_schema_discovery.py
```
This will auto-discover `ops_logistics.shipment`, `ops_logistics.shipment_template`, `ops_logistics.reference`, `ops_logistics.milestone`, and all other custom models, generating the needed JSON schema files in `config/schemas/`.

If discovery can't be run (no Odoo access), manually create `config/schemas/ops_logistics_shipment.json` with the minimum required fields for the shipment model.

**B. Return actionable diagnostic when schema is missing**

When `schema_store.get(route.model_key)` raises `KeyError`, instead of silently printing just the model key, return a clear diagnostic explaining:
1. Which model has a missing schema
2. Why this happened (schema discovery not run for this model)
3. What the user/Claude can do about it (run discovery or describe fields manually)

**Files to change:**
- `src/mcp_server/tools.py` — `chat_odoo_handler` error handling

### Phase 2: Enhanced Preview & Guidance (Should Do — Addresses RC #3, #4)

**C. Generate "ask prompts" from field metadata**

Enhance `_format_field_detail` to produce user-facing questions:
- `many2one` fields → "Which [relation]?" + suggestion to search
- `selection` fields → list options as choices
- `char` fields → "What [string]?"
- `datetime` fields → "When?"

**Files to change:**
- `src/mcp_server/tools.py` — `_format_field_detail` and `_format_schema_for_claude`
- `src/operations/create.py` — `preview_record` to include field-level guidance

**D. Add `preview_record` field-type validation hints**

When a value is provided for a many2one field that's an integer, include a hint like:
```
"partner_id is set to 42. You may want to verify this customer exists by searching res.partner."
```

When a value is missing for a selection field, show the options:
```
"picking_type_id is missing. Valid options: delivery, receipt, internal_transfer."
```

**Files to change:**
- `src/operations/create.py` — `preview_record`

### Phase 3: Robustness & UX (Nice to Do)

**E. Add routing-level model ranking in `router.py`**

Instead of just returning `default_model`, the router could return all matching agent models sorted by keyword relevance. Claude could then present the user with a choice: "I found these relevant models: shipment (ops_logistics.shipment), stock transfer (stock.picking). Which one did you mean?" This gives users agency rather than silently guessing.

**F. Add session-context hints in routing response**

When a session_id is present and has prior context, include a summary of what's already known:
```
Session context: partner_id=42 (ACME Corp), origin=BOOKREF123
```

**Files to change:**
- `src/mcp_server/tools.py` — `chat_odoo_handler`
- `src/odoo_service/session_store.py` — enhanced context storage

**G. Schema discovery as part of setup wizard**

Ensure the DMG wizard and setup flow make it clear that schema discovery must be run after connecting to Odoo. Add a warning if schemas directory has fewer than N files.

**Files to change:**
- `installer/wizard.py`

---

## Implementation Priority

| Priority | Item                                          | Effort | Impact | Depends On           |
| -------- | --------------------------------------------- | ------ | ------ | -------------------- |
| 🔴 P0    | Run schema discovery for ops_logistics models | 5 min  | HUGE   | Odoo access          |
| 🔴 P0    | Actionable diagnostic when schema missing     | 15 min | HIGH   | None                 |
| 🟡 P1    | "Ask prompts" in schema formatting            | 30 min | HIGH   | P0 complete          |
| 🟡 P1    | Field-type validation in preview              | 30 min | HIGH   | P0 complete          |
| 🟢 P2    | Router multi-model ranking (user choice)      | 20 min | MEDIUM | None                 |
| 🟢 P2    | Session-context hints                         | 20 min | MEDIUM | P0 complete          |
| 🟢 P2    | Setup wizard schema discovery warning         | 15 min | LOW    | None                 |

---

## Verification Steps

After implementing fixes:

1. **Test "Create a shipment" flow:**
   - Claude should route to an agent with a valid schema
   - Schema should show required fields with ask-prompts
   - Claude should ask specific questions about each required field
   - Claude should use field aliases to map user words to fields

2. **Test preview before create:**
   - Preview with partial params → returns `needs_input` with field-level guidance
   - Preview with complete params → returns `success`
   - Preview with invalid values → returns warnings

3. **Test field filling on create:**
   - Create with all required fields → record created with all values set
   - Verify in Odoo that the created record has the correct field values

4. **Test schema fallback:**
   - Remove a schema file → system falls back to alternate model in agent's list
   - Remove all schemas → system gracefully reports no schemas available
