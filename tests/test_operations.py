"""Tests for src/operations/ — CRUD operations."""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from src.shared.types import FieldInfo, ModelSchema


class TestSearchOperations:
    """Tests for search_records function."""

    def test_search_returns_records(self):
        """search_records should return matching records from Odoo."""
        from src.operations.search import search_records

        mock_odoo = MagicMock()
        mock_odoo.search_read.return_value = [{"id": 1, "name": "Test Record"}]

        schema = ModelSchema(
            key="stock_picking",
            label="Transfers",
            odoo_model="stock.picking",
            all_fields={},
            search_fields=["name"],
        )

        result = search_records(
            odoo=mock_odoo,
            schema=schema,
            filters={"name": "Test"},
        )

        assert result["status"] == "success"
        assert len(result["records"]) == 1
        assert result["records"][0]["name"] == "Test Record"

    def test_search_no_results(self):
        """search_records should return empty list when no matches."""
        from src.operations.search import search_records

        mock_odoo = MagicMock()
        mock_odoo.search_read.return_value = []

        schema = ModelSchema(
            key="stock_picking",
            label="Transfers",
            odoo_model="stock.picking",
            all_fields={},
            search_fields=["name"],
        )

        result = search_records(odoo=mock_odoo, schema=schema, filters={"name": "Nope"})

        assert result["status"] == "success"
        assert result["records"] == []

    def test_search_odoo_error(self):
        """search_records should return error dict on Odoo failure."""
        from src.operations.search import search_records

        mock_odoo = MagicMock()
        mock_odoo.search_read.return_value = {"status": "error", "message": "Connection refused"}

        schema = ModelSchema(
            key="stock_picking",
            label="Transfers",
            odoo_model="stock.picking",
            all_fields={},
        )

        result = search_records(odoo=mock_odoo, schema=schema, filters={})

        assert result["status"] == "error"
        assert "Connection refused" in result["message"]

    def test_search_with_empty_filters(self):
        """search_records should handle empty filters gracefully."""
        from src.operations.search import search_records

        mock_odoo = MagicMock()
        mock_odoo.search_read.return_value = []

        schema = ModelSchema(
            key="stock_picking",
            label="Transfers",
            odoo_model="stock.picking",
            all_fields={},
        )

        result = search_records(odoo=mock_odoo, schema=schema, filters={})

        assert result["status"] == "success"

    def test_search_builds_domain_from_filters(self):
        """search_records should convert filters dict to Odoo domain."""
        from src.operations.search import search_records

        mock_odoo = MagicMock()
        mock_odoo.search_read.return_value = []

        schema = ModelSchema(
            key="res_partner",
            label="Contacts",
            odoo_model="res.partner",
            all_fields={},
            search_fields=["name", "email"],
        )

        result = search_records(
            odoo=mock_odoo,
            schema=schema,
            filters={"name": "ACME", "email": "test@acme.com"},
        )

        mock_odoo.search_read.assert_called_once()
        domain = mock_odoo.search_read.call_args[0][1]
        assert len(domain) == 2
        assert ("name", "ilike", "ACME") in domain
        assert ("email", "ilike", "test@acme.com") in domain


class TestCreateOperations:
    """Tests for create_record and preview_record functions."""

    def test_preview_record_returns_fields(self):
        """preview_record should return which fields will be populated."""
        from src.operations.create import preview_record

        fields = {
            "name": FieldInfo(name="name", field_type="char", string="Name", required=True),
            "partner_id": FieldInfo(name="partner_id", field_type="many2one", string="Customer", required=True),
            "date": FieldInfo(name="date", field_type="date", string="Date"),
        }

        schema = ModelSchema(
            key="stock_picking",
            label="Transfers",
            odoo_model="stock.picking",
            all_fields=fields,
            create_fields=["name", "partner_id", "date"],
            required_fields=["name", "partner_id"],
        )

        result = preview_record(schema, {"name": "TEST001"})

        assert result["status"] == "needs_input"
        assert "name" in result["filled"]
        assert "partner_id" in result["missing"]
        # date is a create_field but not required and not provided
        # it should appear as missing since it's not filled
        assert "date" not in result["filled"]

    def test_preview_missing_required(self):
        """preview_record should list missing required fields."""
        from src.operations.create import preview_record

        fields = {
            "name": FieldInfo(name="name", field_type="char", string="Name", required=True),
            "partner_id": FieldInfo(name="partner_id", field_type="many2one", string="Customer", required=True),
        }

        schema = ModelSchema(
            key="test",
            label="Test",
            odoo_model="test.model",
            all_fields=fields,
            create_fields=["name", "partner_id"],
            required_fields=["name", "partner_id"],
        )

        result = preview_record(schema, {})

        assert result["status"] == "needs_input"
        assert "name" in result["missing"]
        assert "partner_id" in result["missing"]

    def test_create_record_success(self):
        """create_record should create via Odoo and return the new ID."""
        from src.operations.create import create_record

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = 42

        fields = {
            "name": FieldInfo(name="name", field_type="char", string="Name", required=True),
        }

        schema = ModelSchema(
            key="test",
            label="Test",
            odoo_model="test.model",
            all_fields=fields,
            create_fields=["name"],
            required_fields=["name"],
        )

        result = create_record(mock_odoo, schema, {"name": "New Record"})

        assert result["status"] == "success"
        assert result["record_id"] == 42

    def test_create_odoo_error(self):
        """create_record should return error dict on failure."""
        from src.operations.create import create_record

        mock_odoo = MagicMock()
        mock_odoo.execute_kw.return_value = {"status": "error", "message": "Access Denied"}

        fields = {"name": FieldInfo(name="name", field_type="char", string="Name")}
        schema = ModelSchema(
            key="test", label="Test", odoo_model="test.model",
            all_fields=fields, create_fields=["name"],
        )

        result = create_record(mock_odoo, schema, {"name": "Test"})

        assert result["status"] == "error"
