# Task: Analytics Operations

**Created:** 2026-06-15  
**Status:** ✅ Complete  
**Priority:** MEDIUM — needed for dashboard/reporting queries  
**Depends on:** Phase 1 (odoo_client.py), Phase 2 (schema_store.py)

---

## Problem

Users frequently ask "how many shipments are in draft?", "total sales this month", "average order value". These require Odoo's `read_group` API for aggregation. No analytics operation exists yet.

## Files to Create

| File                                 | Purpose                           |
| ------------------------------------ | --------------------------------- |
| `src/operations/analytics.py`        | `aggregate()`, `count_by_state()` |
| `tests/test_analytics_operations.py` | 8+ tests                          |

## Specifications

```python
def aggregate(odoo: OdooClient, schema: ModelSchema,
              group_by: str, metric: str = "count",
              domain: list | None = None) -> dict:
    """Aggregate records using Odoo's read_group.

    Args:
        group_by: Field to group by (e.g. 'state', 'partner_id')
        metric: 'count', 'sum:<field>', 'avg:<field>'
        domain: Optional Odoo domain filter

    Returns:
        {"status": "success", "groups": [{"key": "draft", "value": 15}, ...]}
    """

def count_by_state(odoo: OdooClient, schema: ModelSchema) -> dict:
    """Convenience: count records grouped by state field.

    Returns:
        {"status": "success", "counts": {"draft": 15, "done": 42, "cancel": 3}}
    """
```

## Test Categories (TDD Required)

1. Happy path: count records grouped by state
2. Sum aggregation: sum of monetary field
3. Average aggregation: avg of numeric field
4. With domain filter: only shipped orders
5. Empty results: no matching records
6. Invalid group_by field: returns error
7. Model without state field: graceful fallback
8. Odoo connection error: returns error dict

## Acceptance Criteria

- [ ] All tests pass (target: ~130+ total)
- [ ] Structured result dicts
- [ ] Handles Odoo models without `state` field gracefully
- [ ] Domain filter support
