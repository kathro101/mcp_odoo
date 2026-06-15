"""Tests for src/shared/date_utils.py — natural language date parsing."""

from __future__ import annotations

from datetime import date, timedelta


class TestParseDateFlexible:
    """Tests for parse_date_flexible()."""

    def test_today(self):
        """'today' should return today's date."""
        from src.shared.date_utils import parse_date_flexible

        result = parse_date_flexible("today")
        today = date.today()

        assert result is not None
        assert result.date() == today

    def test_tomorrow(self):
        """'tomorrow' should return today + 1."""
        from src.shared.date_utils import parse_date_flexible

        result = parse_date_flexible("tomorrow")
        expected = date.today() + timedelta(days=1)

        assert result is not None
        assert result.date() == expected

    def test_yesterday(self):
        """'yesterday' should return today - 1."""
        from src.shared.date_utils import parse_date_flexible

        result = parse_date_flexible("yesterday")
        expected = date.today() - timedelta(days=1)

        assert result is not None
        assert result.date() == expected

    def test_iso_date(self):
        """Should parse ISO format dates."""
        from src.shared.date_utils import parse_date_flexible

        result = parse_date_flexible("2026-01-15")
        assert result is not None
        assert result.date() == date(2026, 1, 15)

    def test_relative_days_ago(self):
        """'3 days ago' should return today - 3."""
        from src.shared.date_utils import parse_date_flexible

        result = parse_date_flexible("3 days ago")
        expected = date.today() - timedelta(days=3)

        assert result is not None
        assert result.date() == expected

    def test_in_n_days(self):
        """'in 2 weeks' should return today + 14."""
        from src.shared.date_utils import parse_date_flexible

        result = parse_date_flexible("in 2 weeks")
        expected = date.today() + timedelta(weeks=2)

        assert result is not None
        assert result.date() == expected

    def test_empty_string_returns_none(self):
        """Empty string should return None."""
        from src.shared.date_utils import parse_date_flexible

        assert parse_date_flexible("") is None

    def test_whitespace_returns_none(self):
        """Whitespace-only should return None."""
        from src.shared.date_utils import parse_date_flexible

        assert parse_date_flexible("   ") is None

    def test_gibberish_returns_none(self):
        """Unparseable text should return None."""
        from src.shared.date_utils import parse_date_flexible

        assert parse_date_flexible("not a date at all") is None

    def test_case_insensitive(self):
        """Should be case-insensitive."""
        from src.shared.date_utils import parse_date_flexible

        result = parse_date_flexible("TODAY")
        assert result is not None
        assert result.date() == date.today()


class TestDateRangeFromExpression:
    """Tests for date_range_from_expression()."""

    def test_this_week(self):
        """'this week' should return Monday-Sunday range."""
        from src.shared.date_utils import date_range_from_expression

        result = date_range_from_expression("this week")
        assert result is not None

        start, end = result
        today = date.today()
        # start should be Monday of this week
        monday = today - timedelta(days=today.weekday())
        assert start.date() == monday
        # end should be Sunday
        assert end.date() == monday + timedelta(days=6)

    def test_this_month(self):
        """'this month' should return 1st to last day of month."""
        from src.shared.date_utils import date_range_from_expression

        result = date_range_from_expression("this month")
        assert result is not None

        start, end = result
        assert start.day == 1
        # end should be the last day of this month
        assert end.day >= 28

    def test_last_n_days(self):
        """'last 30 days' should return (30 days ago, today)."""
        from src.shared.date_utils import date_range_from_expression

        result = date_range_from_expression("last 30 days")
        assert result is not None

        start, end = result
        expected_start = date.today() - timedelta(days=30)
        assert start.date() == expected_start

    def test_unparseable_returns_none(self):
        """Unparseable range should return None."""
        from src.shared.date_utils import date_range_from_expression

        assert date_range_from_expression("gibberish") is None

    def test_empty_returns_none(self):
        """Empty string should return None."""
        from src.shared.date_utils import date_range_from_expression

        assert date_range_from_expression("") is None
