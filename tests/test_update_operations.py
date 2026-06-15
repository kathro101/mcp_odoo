"""Tests for src/operations/update.py — record update operations."""

from __future__ import annotations

from unittest.mock import MagicMock

from src.shared.types import FieldInfo, ModelSchema


def _make_schema() -> ModelSchema:
    """Helper: create a test schema."""
    fields = {
        "name": FieldInfo(name="name", field_type="char", string="Name", required=True),
        "partner_id": FieldInfo(name="partner_id", field_type="many2one", string="Customer"),
        "state": FieldInfo(name="state", field_type="selection", string="Status", readonly=True),
    }
    return ModelSchema(
        key="stock_picking",
        label="Transfers",
        odoo_model="stock.picking",
        all_fields=fields,
        create_fields=["name", "partner_id"],
        required_fields=["name"],
    )


class TestUpdateRecord:
    """Tests for update_record()."""

    def test_update_record_success(self):
        """Should update record and return success with record_id."""
        from src.operations.update import update_record

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = True
        schema = _make_schema()

        result = update_record(mock_odoo, schema, 42, {"name": "New Name"})

        assert result["status"] == "success"
        assert result["record_id"] == 42
        mock_odoo.execute_kw.assert_called_once_with(
            "stock.picking", "write", [[42], {"name": "New Name"}]
        )

    def test_update_record_multiple_fields(self):
        """Should update multiple fields at once."""
        from src.operations.update import update_record

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = True
        schema = _make_schema()

        result = update_record(mock_odoo, schema, 1, {"name": "X", "partner_id": 5})

        assert result["status"] == "success"
        mock_odoo.execute_kw.assert_called_once_with(
            "stock.picking", "write", [[1], {"name": "X", "partner_id": 5}]
        )

    def test_update_record_empty_params_returns_warning(self):
        """Should return warning when no params provided."""
        from src.operations.update import update_record

        mock_odoo = MagicMock()
        schema = _make_schema()

        result = update_record(mock_odoo, schema, 42, {})

        assert result["status"] == "warning"
        assert "nothing to update" in result["message"].lower()
        mock_odoo.execute_kw.assert_not_called()

    def test_update_record_odoo_fault_returns_error(self):
        """Should return error dict on xmlrpc.client.Fault."""
        from src.operations.update import update_record

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = {"status": "error", "message": "Access Denied"}
        schema = _make_schema()

        result = update_record(mock_odoo, schema, 42, {"name": "X"})

        assert result["status"] == "error"
        assert "Access Denied" in result["message"]

    def test_update_record_connection_refused_returns_error(self):
        """Should return error dict when Odoo unreachable."""
        from src.operations.update import update_record

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = {"status": "error", "message": "Connection refused"}
        schema = _make_schema()

        result = update_record(mock_odoo, schema, 42, {"name": "X"})

        assert result["status"] == "error"
        assert "Connection refused" in result["message"]


class TestPreviewUpdate:
    """Tests for preview_update()."""

    def test_preview_update_shows_changes(self):
        """Should show old vs new for changed fields."""
        from src.operations.update import preview_update

        schema = _make_schema()
        current = {"name": "Old Name", "partner_id": 1, "state": "draft"}

        result = preview_update(schema, current, {"name": "New Name"})

        assert result["status"] == "success"
        assert "name" in result["changes"]
        assert result["changes"]["name"] == {"old": "Old Name", "new": "New Name"}

    def test_preview_update_shows_unchanged(self):
        """Should list fields that are NOT being changed."""
        from src.operations.update import preview_update

        schema = _make_schema()
        current = {"name": "Old Name", "partner_id": 1}

        result = preview_update(schema, current, {"name": "New Name"})

        assert "partner_id" in result["unchanged"]

    def test_preview_update_field_not_in_create(self):
        """Should flag params that reference non-creatable fields."""
        from src.operations.update import preview_update

        schema = _make_schema()
        current = {"name": "Old", "state": "draft"}

        result = preview_update(schema, current, {"state": "done"})

        assert len(result["warnings"]) > 0
        assert any("state" in w for w in result["warnings"])
