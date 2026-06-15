# Architecture: Operations Layer

**Files:** `src/operations/search.py` (55 lines), `src/operations/create.py` (73 lines)
**Tests:** `tests/test_operations.py` (9 tests)
**Dependencies:** `src/odoo_service/odoo_client.py`, `src/shared/types.py`

## Purpose

Stateless, pure functions for Odoo CRUD operations. Each function takes `OdooClient` + `ModelSchema` + parameters → returns structured result dict. No classes, no state, no AI.

## Modules

### search.py

```python
def search_records(odoo, schema, filters, limit=20, offset=0) → dict
```

- Converts `filters` dict to Odoo domain with `ilike` matching
- Returns `{"status": "success", "records": [...], "count": N}`
- Odoo error → `{"status": "error", "message": "..."}`

### create.py

```python
def preview_record(schema, params) → dict
def create_record(odoo, schema, params) → dict
```

- `preview_record`: checks required vs provided fields, no Odoo call
  - Returns `{"status": "success"|"needs_input", "filled": [...], "missing": [...], "optional": [...]}`
- `create_record`: calls Odoo's `create` method
  - Returns `{"status": "success", "record_id": <int>}`
  - Error → `{"status": "error", "message": "..."}`

## Pending Operations (see tasks/)

- `src/operations/update.py` — `update_record()`, `preview_update()`
- `src/operations/delete.py` — `delete_record()`, `confirm_delete()`
- `src/operations/analytics.py` — `aggregate()`, `count_by_state()`

## Result Dict Contract

All operations return one of:

```python
# Success
{"status": "success", ...specific fields...}

# Needs more input
{"status": "needs_input", "missing": [...], "message": "..."}

# Error
{"status": "error", "message": "..."}
```

## Key Rules

- Pure functions — no class instances
- No Odoo dependency except through `OdooClient` parameter
- No LLM calls
- Always check `isinstance(result, dict) and result.get("status") == "error"` after Odoo calls
