# Task: Shared Utilities — Date Parsing

**Created:** 2026-06-15  
**Status:** 🔴 Not started  
**Priority:** LOW — needed for natural language date handling in chat  
**Depends on:** None

---

## Problem

Users express dates in natural language: "next Monday", "end of this month", "yesterday". The `chat_odoo` tool needs flexible date parsing to convert these to Odoo-compatible date strings.

## Files to Create

| File                       | Purpose                                                 |
| -------------------------- | ------------------------------------------------------- |
| `src/shared/date_utils.py` | `parse_date_flexible()`, `date_range_from_expression()` |
| `tests/test_date_utils.py` | 10+ tests                                               |

## Specifications

```python
def parse_date_flexible(text: str, tz: timezone | None = None) -> datetime | None:
    """Parse natural language date expressions.

    Supports:
    - "today", "tomorrow", "yesterday"
    - "next Monday", "last Friday"
    - "end of this month", "start of next month"
    - ISO: "2026-01-15"
    - Relative: "3 days ago", "in 2 weeks"

    Returns datetime or None if unparseable.
    """

def date_range_from_expression(text: str) -> tuple[datetime, datetime] | None:
    """Parse date range expressions.

    Supports:
    - "this week" → (Monday 00:00, Sunday 23:59)
    - "this month" → (1st 00:00, last day 23:59)
    - "last 30 days" → (30 days ago, now)
    - "from 2026-01-01 to 2026-01-31"
    """
```

## Test Categories

1. "today" → today's date
2. "tomorrow" → today + 1
3. "next Monday" → correct date
4. "end of this month" → last day of month
5. ISO date "2026-01-15"
6. "3 days ago" → today - 3
7. Empty string → None
8. Gibberish → None
9. "this week" range
10. "this month" range

## Acceptance Criteria

- [ ] All tests pass
- [ ] Timezone-aware (defaults to UTC)
- [ ] No external dependencies beyond stdlib `datetime`
