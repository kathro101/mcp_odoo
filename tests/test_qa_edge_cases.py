"""QA adversarial tests — edge cases per QA agent checklist.

Tests added from QA review findings:
- Crash safety: None/empty inputs across all operations
- Data integrity: special chars, injection attacks, boundary values
- Edge cases: empty params, zero IDs, negative IDs
"""

from __future__ import annotations

from unittest.mock import MagicMock

from src.shared.types import FieldInfo, ModelSchema


def _make_schema() -> ModelSchema:
    return ModelSchema(
        key="stock_picking",
        label="Transfers",
        odoo_model="stock.picking",
        all_fields={
            "name": FieldInfo(name="name", field_type="char", string="Reference", required=True),
            "partner_id": FieldInfo(
                name="partner_id", field_type="many2one", string="Customer", relation="res.partner"
            ),
            "state": FieldInfo(
                name="state",
                field_type="selection",
                string="Status",
                selection=[("draft", "Draft"), ("done", "Done")],
            ),
        },
        create_fields=["name", "partner_id"],
        search_fields=["name", "partner_id", "state"],
        required_fields=["name"],
    )


class TestQACrashSafety:
    """QA Checklist §1 — Crash Safety."""

    def test_search_handles_none_filters(self):
        """search_records should not crash with None filters (AttributeError)."""
        from src.operations.search import search_records

        mock_odoo = MagicMock()
        mock_odoo.search_read.return_value = []

        result = search_records(odoo=mock_odoo, schema=_make_schema(), filters=None)
        assert result["status"] == "success"
        assert result["count"] == 0

    def test_preview_handles_none_params(self):
        """preview_record should not crash with None params (TypeError)."""
        from src.operations.create import preview_record

        result = preview_record(_make_schema(), None)
        assert result["status"] == "needs_input"
        assert "name" in result["missing"]

    def test_create_handles_none_params(self):
        """create_record should handle None params gracefully."""
        from src.operations.create import create_record

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = 1

        result = create_record(odoo=mock_odoo, schema=_make_schema(), params=None)
        assert result["status"] == "error" or result["status"] == "success"

    def test_delete_handles_negative_id(self):
        """delete_record should handle negative record IDs."""
        from src.operations.delete import delete_record

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = True

        result = delete_record(odoo=mock_odoo, schema=_make_schema(), record_id=-1)
        assert result["status"] == "success"

    def test_confirm_delete_handles_empty_record(self):
        """confirm_delete should handle records with no id field."""
        from src.operations.delete import confirm_delete

        result = confirm_delete(_make_schema(), {})
        assert result["record_id"] == "unknown"


class TestQADataIntegrity:
    """QA Checklist §2 — Data Integrity."""

    def test_search_handles_sql_injection(self):
        """search_records should safely handle SQL injection strings."""
        from src.operations.search import search_records

        mock_odoo = MagicMock()
        mock_odoo.search_read.return_value = []

        result = search_records(
            odoo=mock_odoo,
            schema=_make_schema(),
            filters={"name": "'; DROP TABLE res_partner; --"},
        )
        assert result["status"] == "success"

    def test_search_handles_unicode_emoji(self):
        """search_records should handle unicode and emoji in search values."""
        from src.operations.search import search_records

        mock_odoo = MagicMock()
        mock_odoo.search_read.return_value = []

        result = search_records(
            odoo=mock_odoo,
            schema=_make_schema(),
            filters={"name": "🚀 テスト тест café"},
        )
        assert result["status"] == "success"

    def test_search_handles_very_long_filter(self):
        """search_records should handle very long filter values."""
        from src.operations.search import search_records

        mock_odoo = MagicMock()
        mock_odoo.search_read.return_value = []

        result = search_records(
            odoo=mock_odoo,
            schema=_make_schema(),
            filters={"name": "A" * 5000},
        )
        assert result["status"] == "success"


class TestQAEdgeCases:
    """QA Checklist — General edge cases."""

    def test_update_handles_zero_record_id(self):
        """update_record should handle record_id=0."""
        from src.operations.update import update_record

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = True

        result = update_record(
            odoo=mock_odoo, schema=_make_schema(), record_id=0, params={"name": "X"}
        )
        assert result["status"] == "success"

    def test_update_handles_none_params(self):
        """update_record should handle None params."""
        from src.operations.update import update_record

        mock_odoo = MagicMock()
        schema = _make_schema()

        result = update_record(odoo=mock_odoo, schema=schema, record_id=42, params=None)
        assert result["status"] == "warning"
        assert "nothing to update" in result["message"].lower()

    def test_analytics_handles_none_domain(self):
        """aggregate should handle None domain."""
        from src.operations.analytics import aggregate

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = []

        result = aggregate(mock_odoo, _make_schema(), "state", domain=None)
        assert result["status"] == "success"

    def test_analytics_handles_empty_result(self):
        """aggregate should handle empty results from Odoo."""
        from src.operations.analytics import aggregate

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = []

        result = aggregate(mock_odoo, _make_schema(), "state")
        assert result["status"] == "success"
        assert result["groups"] == []
