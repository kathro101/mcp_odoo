"""Natural language date parsing utilities.

Stdlib only — no external dependencies.  Converts human date expressions
like "next Monday", "3 days ago", "this month" to datetime objects.
"""

from __future__ import annotations

import calendar
import re
from datetime import date, datetime, timedelta, timezone

# ── Patterns ─────────────────────────────────────────────────────────────

_ISO_DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

_RELATIVE_RE = re.compile(
    r"(?:last|past|next|in)?\s*(\d+)\s+(day|week|month|year)s?\s*(?:ago)?",
    re.IGNORECASE,
)

_WEEKDAY_MAP: dict[str, int] = {
    "monday": 0, "tuesday": 1, "wednesday": 2, "thursday": 3,
    "friday": 4, "saturday": 5, "sunday": 6,
}


def parse_date_flexible(text: str, tz: timezone | None = None) -> datetime | None:
    """Parse a natural language date expression into a datetime.

    Supports:
    - "today", "tomorrow", "yesterday"
    - "next Monday", "last Friday"
    - "end of this month", "start of next month"
    - ISO format: "2026-01-15"
    - Relative: "3 days ago", "in 2 weeks"

    Args:
        text: Natural language date string.
        tz: Timezone for the result (default: UTC).

    Returns:
        datetime or None if unparseable.
    """
    if not text or not text.strip():
        return None

    text = text.strip().lower()
    tz = tz or timezone.utc
    today = date.today()
    now = datetime.now(tz=tz)

    # ── Absolute dates ──────────────────────────────────────────────

    if text == "today":
        return datetime(today.year, today.month, today.day, tzinfo=tz)

    if text == "tomorrow":
        d = today + timedelta(days=1)
        return datetime(d.year, d.month, d.day, tzinfo=tz)

    if text == "yesterday":
        d = today - timedelta(days=1)
        return datetime(d.year, d.month, d.day, tzinfo=tz)

    # ── ISO date ────────────────────────────────────────────────────

    if _ISO_DATE_RE.match(text):
        try:
            parsed = date.fromisoformat(text)
            return datetime(parsed.year, parsed.month, parsed.day, tzinfo=tz)
        except ValueError:
            pass

    # ── Relative days/weeks/months ──────────────────────────────────

    rel_match = _RELATIVE_RE.search(text)
    if rel_match:
        num = int(rel_match.group(1))
        unit = rel_match.group(2).lower()

        if "ago" not in text and "last" not in text and "past" not in text:
            if "next" in text or "in" in text:
                sign = 1
            else:
                sign = 1  # "in 2 weeks" is positive
        else:
            sign = -1

        if unit == "day":
            target = today + timedelta(days=sign * num)
        elif unit == "week":
            target = today + timedelta(weeks=sign * num)
        elif unit == "month":
            target = _add_months(today, sign * num)
        elif unit == "year":
            target = _add_months(today, sign * num * 12)
        else:
            return None

        return datetime(target.year, target.month, target.day, tzinfo=tz)

    # ── Weekday navigation ──────────────────────────────────────────

    for weekday_name, weekday_num in _WEEKDAY_MAP.items():
        if weekday_name in text:
            days_ahead = weekday_num - today.weekday()
            if "next" in text:
                if days_ahead <= 0:
                    days_ahead += 7
            elif "last" in text:
                if days_ahead >= 0:
                    days_ahead -= 7
            else:
                if days_ahead < 0:
                    days_ahead += 7

            target = today + timedelta(days=days_ahead)
            return datetime(target.year, target.month, target.day, tzinfo=tz)

    # ── Month boundaries ────────────────────────────────────────────

    if "end of this month" in text or "end of month" in text:
        last_day = calendar.monthrange(today.year, today.month)[1]
        return datetime(today.year, today.month, last_day, tzinfo=tz)

    if "start of this month" in text or "start of month" in text:
        return datetime(today.year, today.month, 1, tzinfo=tz)

    if "end of next month" in text:
        target = _add_months(today, 1)
        last_day = calendar.monthrange(target.year, target.month)[1]
        return datetime(target.year, target.month, last_day, tzinfo=tz)

    if "start of next month" in text:
        target = _add_months(today, 1)
        return datetime(target.year, target.month, 1, tzinfo=tz)

    return None


def date_range_from_expression(text: str) -> tuple[datetime, datetime] | None:
    """Parse a date range expression.

    Supports:
    - "this week" → (Monday 00:00, Sunday 23:59)
    - "this month" → (1st 00:00, last day 23:59)
    - "last 30 days" → (30 days ago, now)
    - "last N days" → (N days ago, now)

    Args:
        text: Natural language range expression.

    Returns:
        (start_datetime, end_datetime) or None if unparseable.
    """
    if not text or not text.strip():
        return None

    text = text.strip().lower()
    tz = timezone.utc
    today = date.today()

    # "this week"
    if text == "this week":
        monday = today - timedelta(days=today.weekday())
        sunday = monday + timedelta(days=6)
        return (
            datetime(monday.year, monday.month, monday.day, tzinfo=tz),
            datetime(sunday.year, sunday.month, sunday.day, 23, 59, 59, tzinfo=tz),
        )

    # "this month"
    if text == "this month":
        last_day = calendar.monthrange(today.year, today.month)[1]
        return (
            datetime(today.year, today.month, 1, tzinfo=tz),
            datetime(today.year, today.month, last_day, 23, 59, 59, tzinfo=tz),
        )

    # "last N days"
    last_n_match = re.match(r"last\s+(\d+)\s+days?", text)
    if last_n_match:
        num = int(last_n_match.group(1))
        start = today - timedelta(days=num)
        return (
            datetime(start.year, start.month, start.day, tzinfo=tz),
            datetime(today.year, today.month, today.day, 23, 59, 59, tzinfo=tz),
        )

    return None


# ── Helpers ──────────────────────────────────────────────────────────────


def _add_months(d: date, months: int) -> date:
    """Add a number of months to a date (handling month overflow)."""
    total_months = d.month - 1 + months
    year = d.year + total_months // 12
    month = total_months % 12 + 1
    last_day = calendar.monthrange(year, month)[1]
    day = min(d.day, last_day)
    return date(year, month, day)
