"""Tests for src/operations/delete.py — record delete operations."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.shared.types import FieldInfo, ModelSchema


def _make_schema() -> ModelSchema:
    """Helper: create a test schema."""
    fields = {
        "name": FieldInfo(name="name", field_type="char", string="Name", required=True),
        "partner_id": FieldInfo(name="partner_id", field_type="many2one", string="Customer"),
    }
    return ModelSchema(
        key="stock_picking",
        label="Transfers",
        odoo_model="stock.picking",
        all_fields=fields,
        search_fields=["name"],
        required_fields=["name"],
    )


class TestDeleteRecord:
    """Tests for delete_record()."""

    def test_delete_record_success(self):
        """Should delete record and return success."""
        from src.operations.delete import delete_record

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = True
        schema = _make_schema()

        result = delete_record(mock_odoo, schema, 42)

        assert result["status"] == "success"
        assert result["record_id"] == 42
        mock_odoo.execute_kw.assert_called_once_with("stock.picking", "unlink", [[42]])

    def test_delete_record_odoo_fault_returns_error(self):
        """Should return error dict on Odoo permission error."""
        from src.operations.delete import delete_record

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = {
            "status": "error",
            "message": "Access Denied: Cannot delete",
        }
        schema = _make_schema()

        result = delete_record(mock_odoo, schema, 42)

        assert result["status"] == "error"
        assert "Access Denied" in result["message"]

    def test_delete_record_connection_refused_returns_error(self):
        """Should return error dict when Odoo unreachable."""
        from src.operations.delete import delete_record

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = {"status": "error", "message": "Connection refused"}
        schema = _make_schema()

        result = delete_record(mock_odoo, schema, 42)

        assert result["status"] == "error"
        assert "Connection refused" in result["message"]


class TestConfirmDelete:
    """Tests for confirm_delete()."""

    def test_confirm_delete_returns_summary(self):
        """Should return a human-readable confirmation summary."""
        from src.operations.delete import confirm_delete

        schema = _make_schema()
        record = {"id": 42, "name": "TEST/001", "partner_id": ("ACME Corp", 5)}

        result = confirm_delete(schema, record)

        assert result["status"] == "confirm"
        assert result["record_id"] == 42
        assert "TEST/001" in result["record_summary"]

    def test_confirm_delete_missing_name_field(self):
        """Should handle records without a 'name' field gracefully."""
        from src.operations.delete import confirm_delete

        schema = _make_schema()
        record = {"id": 99}

        result = confirm_delete(schema, record)

        assert result["status"] == "confirm"
        assert result["record_id"] == 99
        # Should still work — uses id as fallback identifier
        assert "99" in result["record_summary"]
