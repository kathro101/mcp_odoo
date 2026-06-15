# Task: Update + Delete Operations

**Created:** 2026-06-15  
**Status:** 🔴 Not started  
**Priority:** HIGH — completes the CRUD layer  
**Depends on:** Phase 1 (odoo_client.py), Phase 2 (schema_store.py)

---

## Problem

`src/operations/` currently has `search.py` and `create.py` but no update or delete operations. The `chat_odoo` MCP tool needs a complete CRUD surface to be useful for real workflows.

## Files to Create

| File                              | Purpose                               |
| --------------------------------- | ------------------------------------- |
| `src/operations/update.py`        | `update_record()`, `preview_update()` |
| `src/operations/delete.py`        | `delete_record()`, `confirm_delete()` |
| `tests/test_update_operations.py` | 8+ tests                              |
| `tests/test_delete_operations.py` | 6+ tests                              |

## Specifications

### update.py

```python
def update_record(odoo: OdooClient, schema: ModelSchema,
                  record_id: int, params: dict) -> dict:
    """Update an existing Odoo record.
    Returns: {"status": "success", "record_id": <int>}
            or {"status": "error", "message": "..."}
    """

def preview_update(schema: ModelSchema, current_values: dict,
                   params: dict) -> dict:
    """Show what will change.
    Returns: {"status": "success", "changes": {field: {old, new}}, "unchanged": [...]}
    """
```

### delete.py

```python
def delete_record(odoo: OdooClient, schema: ModelSchema,
                  record_id: int) -> dict:
    """Delete an Odoo record.
    Returns: {"status": "success"}
            or {"status": "error", "message": "..."}
    """

def confirm_delete(schema: ModelSchema, record_data: dict) -> dict:
    """Return a confirmation summary before deletion.
    Returns: {"status": "confirm", "record_summary": "...",
              "record_id": <int>}
    """
```

## Test Categories (TDD Required)

### update_record

1. Happy path: update name field, returns success
2. Update multiple fields at once
3. Empty params dict → returns warning
4. Odoo Fault (permission error) → returns error dict
5. ConnectionRefusedError → returns error dict

### preview_update

6. Shows changes: old vs new values
7. Shows unchanged fields
8. Fields not in create_fields → warning

### delete_record

9. Happy path: delete existing record
10. Non-existent ID → returns error
11. Odoo permission error → returns error dict

### confirm_delete

12. Returns formatted summary with key fields

## Acceptance Criteria

- [ ] All tests pass (104 → ~120+)
- [ ] No regression in existing tests
- [ ] Structured result dicts for all returns
- [ ] Error handling for all Odoo failure modes
