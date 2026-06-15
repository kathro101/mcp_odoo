# Task: Richer Schema Output — Field Help Text + Selection Labels

**Created:** 2026-06-15
**Status:** 🔴 Not started
**Priority:** HIGH — Claude currently guesses field purpose from labels alone
**Depends on:** Phase 2 (schema_discovery), Phase 4 (tools.py formatting)
**Impact:** 20-line change, massive semantic improvement for Claude

---

## Problem

When Claude receives a schema from `chat_odoo` or `list_models`, it sees:

```
- `origin` (char): Source Document
- `state` (selection): Status [options: draft, done, cancel]
```

Claude doesn't know:

- **What `origin` is really for** — Odoo's `help` text says "Reference of the document that generated this picking request" which would tell Claude this is where booking references go
- **What selection labels mean** — `draft` vs `Draft` vs `done` vs `Done` — Claude has to guess
- **Default values** — Claude doesn't know `state` defaults to `draft`, so it asks unnecessarily
- **Which model a relation points to in human terms** — `partner_id → res.partner` is a Contact, but Claude doesn't know it's searchable by name

## Root Cause

`schema_discovery.py::discover_model()` calls `fields_get()` but only captures `type`, `string`, `readonly`, `relation`, and `selection`. It ignores `help` and doesn't format selection labels.

`FieldInfo` dataclass has no `help_text` field.

`_format_field_detail()` in `tools.py` doesn't render help text or selection labels.

## Solution

### 1. Add `help_text` to `FieldInfo` dataclass

```python
# src/shared/types.py
@dataclass
class FieldInfo:
    # ... existing fields ...
    help_text: str = ""  # NEW — from Odoo's fields_get() help attribute
```

### 2. Extract `help` during schema discovery

```python
# src/odoo_service/schema_discovery.py — discover_model()
raw_fields = self.odoo.fields_get(model_name)  # Already called
# Just capture help from the response:
help_text = meta.get("help", "")
```

### 3. Format selection labels (not just keys)

```python
# src/mcp_server/tools.py — _format_field_detail()

# Before:
if fi.selection:
    options = [s[0] for s in fi.selection]
    parts.append(f" [options: {', '.join(options)}]")

# After:
if fi.selection:
    options = [f"{s[0]} ({s[1]})" for s in fi.selection]
    parts.append(f" [options: {', '.join(options)}]")
```

### 4. Render help text in field detail

```python
# src/mcp_server/tools.py — _format_field_detail()
if fi.help_text:
    parts.append(f" — {fi.help_text}")
```

## What Claude Would Then See

### Before (current)

```
### REQUIRED FIELDS
  - `partner_id` (many2one → res.partner): Contact *REQUIRED*
  - `picking_type_id` (many2one → stock.picking.type): Operation Type *REQUIRED*

### OPTIONAL FIELDS
  - `scheduled_date` (datetime): Scheduled Date
  - `origin` (char): Source Document
  - `state` (selection [options: draft, done, cancel]): Status
```

### After (proposed)

```
### REQUIRED FIELDS
  - `partner_id` (many2one → res.partner): Contact *REQUIRED*
    — The partner this operation is destined for
  - `picking_type_id` (many2one → stock.picking.type): Operation Type *REQUIRED*
    — Type of operation: delivery, receipt, or internal transfer
    [options: delivery (Delivery Orders), receipt (Receipts), internal (Internal Transfers)]

### OPTIONAL FIELDS
  - `scheduled_date` (datetime): Scheduled Date
    — Scheduled date for the processing of this transfer
  - `origin` (char): Source Document
    — Reference of the document that generated this picking request
  - `state` (selection): Status
    [options: draft (Draft), waiting (Waiting Another Operation), ready (Ready),
     done (Done), cancel (Cancelled)]
```

## Impact on Claude's Decision Quality

| Scenario                           | Before                                                                                                 | After                                                                                |
| ---------------------------------- | ------------------------------------------------------------------------------------------------------ | ------------------------------------------------------------------------------------ |
| User says "mark as done"           | Claude sees `[options: draft, done, cancel]`, guesses `done`                                           | Claude sees `done (Done)`, confirms: "Set to Done?"                                  |
| User says "booking ref BOOKREF123" | Claude maps to `origin` via alias but doesn't know `origin` is where booking refs go — might still ask | Claude reads help text: "Reference of the document..." — immediately maps correctly  |
| User doesn't mention state         | Claude asks "What status?" unnecessarily                                                               | Claude sees `[draft (Draft)]` is the first option, infers it's default — doesn't ask |

## Files to Modify

| File                                   | Change                                                                       | Lines |
| -------------------------------------- | ---------------------------------------------------------------------------- | ----- |
| `src/shared/types.py`                  | Add `help_text: str = ""` to `FieldInfo`                                     | +1    |
| `src/odoo_service/schema_discovery.py` | Capture `help` from `fields_get()` in `discover_model()`                     | +1    |
| `src/odoo_service/schema_store.py`     | Serialize/deserialize `help_text` in `_load_one()` and `_serialize_schema()` | +2    |
| `src/mcp_server/tools.py`              | Format selection labels in `_format_field_detail()`                          | ~5    |
| `src/mcp_server/tools.py`              | Render help text in `_format_field_detail()`                                 | +2    |
| `tests/test_mcp_tools_v2.py`           | Add test for help text in formatted output                                   | +10   |
| `tests/test_types.py`                  | Add test for `help_text` default                                             | +3    |
| `tests/test_schema_discovery.py`       | Verify `help` is captured from mocked `fields_get`                           | +5    |

## Tests (TDD Required)

### `FieldInfo.help_text`

1. **`test_field_info_help_text_defaults_to_empty`** — `help_text` defaults to `""`

### Schema Discovery

2. **`test_discover_captures_help_text`** — Mocked `fields_get` with `help` key → `FieldInfo.help_text` populated

### Schema Formatting

3. **`test_format_field_detail_includes_help_text`** — Field with `help_text="Foo"` → output contains "— Foo"
4. **`test_format_field_detail_no_help_text`** — Field without help → no "—" in output
5. **`test_format_field_detail_selection_shows_labels`** — Selection with `[("draft", "Draft")]` → output contains "draft (Draft)"

### Schema Store

6. **`test_schema_store_roundtrips_help_text`** — Schema saved to JSON → reloaded → `help_text` preserved

## Implementation Steps

1. Add `help_text` to `FieldInfo` (1 line)
2. Capture `help` in `schema_discovery.discover_model()` (1 line)
3. Update `schema_store._serialize_schema()` and `_load_one()` (4 lines)
4. Update `_format_field_detail()` — selection labels + help text (7 lines)
5. Write 6 tests (TDD)
6. Run full suite (~198 tests)

## Acceptance Criteria

- [ ] `FieldInfo.help_text` defaults to `""`
- [ ] Schema discovery captures `help` from Odoo's `fields_get()`
- [ ] Schema JSON files include `help_text` for each field
- [ ] `_format_field_detail()` renders selection labels like `draft (Draft)`
- [ ] `_format_field_detail()` appends `— help text` when `help_text` is set
- [ ] Schema store round-trips `help_text` correctly
- [ ] 192 → ~198 tests
- [ ] Zero additional tokens — all changes are deterministic
