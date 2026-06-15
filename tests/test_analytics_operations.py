"""Tests for src/operations/analytics.py — aggregation operations."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.shared.types import FieldInfo, ModelSchema


def _make_schema() -> ModelSchema:
    fields = {
        "name": FieldInfo(name="name", field_type="char", string="Name", required=True),
        "state": FieldInfo(name="state", field_type="selection", string="Status"),
        "amount_total": FieldInfo(name="amount_total", field_type="monetary", string="Total"),
    }
    return ModelSchema(
        key="sale_order",
        label="Sales Orders",
        odoo_model="sale.order",
        all_fields=fields,
        create_fields=["name"],
    )


class TestAggregate:
    """Tests for aggregate()."""

    def test_aggregate_count_by_state(self):
        """Should count records grouped by state field."""
        from src.operations.analytics import aggregate

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = [
            {"state": "draft", "state_count": 5},
            {"state": "done", "state_count": 12},
        ]
        schema = _make_schema()

        result = aggregate(mock_odoo, schema, group_by="state")

        assert result["status"] == "success"
        groups = {g["key"]: g["value"] for g in result["groups"]}
        assert groups["draft"] == 5
        assert groups["done"] == 12

    def test_aggregate_sum_metric(self):
        """Should sum a numeric field grouped by another field."""
        from src.operations.analytics import aggregate

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = [
            {"state": "done", "amount_total": 1500.0},
            {"state": "draft", "amount_total": 300.0},
        ]
        schema = _make_schema()

        result = aggregate(mock_odoo, schema, group_by="state", metric="sum:amount_total")

        assert result["status"] == "success"
        groups = {g["key"]: g["value"] for g in result["groups"]}
        assert groups["done"] == 1500.0
        assert groups["draft"] == 300.0

    def test_aggregate_avg_metric(self):
        """Should average a numeric field."""
        from src.operations.analytics import aggregate

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = [
            {"state": "done", "amount_total": 100.0, "__count": 4},
        ]
        schema = _make_schema()

        result = aggregate(mock_odoo, schema, group_by="state", metric="avg:amount_total")

        assert result["status"] == "success"
        assert result["groups"][0]["value"] == 25.0  # 100/4

    def test_aggregate_with_domain_filter(self):
        """Should apply domain filter to aggregation."""
        from src.operations.analytics import aggregate

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = [{"state": "done", "state_count": 3}]
        schema = _make_schema()

        result = aggregate(
            mock_odoo, schema, group_by="state",
            domain=[("partner_id", "=", 42)]
        )

        assert result["status"] == "success"
        # Domain should be passed to execute_kw
        call_args = mock_odoo.execute_kw.call_args
        args_list = call_args[0]
        # args_list[1] is the method, args_list[2] is the args list to read_group
        read_group_args = args_list[2]
        # read_group_args[0] is the domain
        domain_arg = read_group_args[0]
        assert [("partner_id", "=", 42)] == domain_arg

    def test_aggregate_empty_results(self):
        """Should return empty groups when no records match."""
        from src.operations.analytics import aggregate

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = []
        schema = _make_schema()

        result = aggregate(mock_odoo, schema, group_by="state")

        assert result["status"] == "success"
        assert result["groups"] == []

    def test_aggregate_odoo_error(self):
        """Should return error dict on Odoo failure."""
        from src.operations.analytics import aggregate

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = {"status": "error", "message": "Connection refused"}
        schema = _make_schema()

        result = aggregate(mock_odoo, schema, group_by="state")

        assert result["status"] == "error"


class TestCountByState:
    """Tests for count_by_state()."""

    def test_count_by_state_returns_counts(self):
        """Should return count per state value."""
        from src.operations.analytics import count_by_state

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = [
            {"state": "draft", "state_count": 3},
            {"state": "done", "state_count": 7},
            {"state": "cancel", "state_count": 1},
        ]
        schema = _make_schema()

        result = count_by_state(mock_odoo, schema)

        assert result["status"] == "success"
        assert result["counts"] == {"draft": 3, "done": 7, "cancel": 1}

    def test_count_by_state_no_state_field(self):
        """Should return error when model has no state field."""
        from src.operations.analytics import count_by_state

        mock_odoo = MagicMock()
        fields = {"name": FieldInfo(name="name", field_type="char", string="Name")}
        schema = ModelSchema(
            key="test", label="Test", odoo_model="test.model",
            all_fields=fields,
        )

        result = count_by_state(mock_odoo, schema)

        assert result["status"] == "error"
        assert "no" in result["message"].lower() and "state" in result["message"].lower()
