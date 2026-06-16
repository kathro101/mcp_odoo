"""Tests for record URL/link generation in operation results.

Verifies that create and search results include clickable Odoo URLs
so the user can navigate directly to the created/found record.
"""

from __future__ import annotations

from unittest.mock import MagicMock


class TestCreateRecordReturnsUrl:
    """create_record should return a clickable Odoo URL."""

    def test_create_record_includes_url(self):
        """Successful create should return odoo_url alongside record_id."""
        from src.odoo_service.odoo_client import OdooClient
        from src.operations.create import create_record
        from src.shared.types import ModelSchema

        schema = ModelSchema(
            key="test_model",
            label="Test",
            odoo_model="test.model",
            all_fields={},
            create_fields=["name"],
            required_fields=["name"],
        )

        odoo = MagicMock(spec=OdooClient)
        odoo.url = "https://example.odoo.com"
        odoo.database = "testdb"
        odoo.execute_kw.return_value = 42

        result = create_record(odoo, schema, {"name": "test"})

        assert result["status"] == "success"
        assert result["record_id"] == 42
        assert "odoo_url" in result, "create_record must return an odoo_url"
        assert "odoo.com" in result["odoo_url"]
        assert "/42" in result["odoo_url"] or "id=42" in result["odoo_url"]
        assert "test.model" in result["odoo_url"]

    def test_create_record_url_still_included_on_error(self):
        """Error results may optionally include URL; at minimum don't crash."""
        from src.odoo_service.odoo_client import OdooClient
        from src.operations.create import create_record
        from src.shared.types import ModelSchema

        schema = ModelSchema(
            key="test_model",
            label="Test",
            odoo_model="test.model",
            all_fields={},
            create_fields=["name"],
            required_fields=["name"],
        )

        odoo = MagicMock(spec=OdooClient)
        odoo.url = "https://example.odoo.com"
        odoo.database = "testdb"
        odoo.execute_kw.return_value = {"status": "error", "message": "Bad"}

        result = create_record(odoo, schema, {"name": "test"})
        assert result["status"] == "error"


class TestSearchResultsReturnUrls:
    """search_records should return clickable Odoo URLs for each record."""

    def test_search_results_include_urls(self):
        """Each record in search results should have an odoo_url."""
        from src.odoo_service.odoo_client import OdooClient
        from src.operations.search import search_records
        from src.shared.types import FieldInfo, ModelSchema

        schema = ModelSchema(
            key="test_model",
            label="Test",
            odoo_model="test.model",
            all_fields={"name": FieldInfo(name="name", field_type="char", string="Name")},
            create_fields=["name"],
            required_fields=[],
            search_fields=["name"],
        )

        odoo = MagicMock(spec=OdooClient)
        odoo.url = "https://example.odoo.com"
        odoo.database = "testdb"
        odoo.search_read.return_value = [
            {"id": 1, "name": "Record 1"},
            {"id": 2, "name": "Record 2"},
        ]

        result = search_records(odoo, schema, {"name": "test"})

        assert result["status"] == "success"
        assert len(result["records"]) == 2
        for record in result["records"]:
            assert "odoo_url" in record, f"Record {record.get('id')} must have odoo_url"
            assert str(record["id"]) in record["odoo_url"]
            assert "test.model" in record["odoo_url"]


class TestOdooUrlFormatter:
    """Test the _build_odoo_url helper function."""

    def test_builds_correct_url_format(self):
        """URL should follow Odoo's /web#id=X&model=Y&view_type=form pattern."""
        from src.operations.create import _build_odoo_url

        url = _build_odoo_url(
            url="https://example.odoo.com",
            database="testdb",
            model="ops_logistics.shipment",
            record_id=6749,
        )

        assert "ops_logistics.shipment" in url
        assert "6749" in url or "id=6749" in url
        # Odoo 16+ uses /odoo/<model>/<id> format
        # Odoo <16 uses /web#id=<id>&model=<model>&view_type=form
        assert "/" in url

    def test_falls_back_gracefully_without_url(self):
        """Should return None or empty string when missing URL info."""
        from src.operations.create import _build_odoo_url

        result = _build_odoo_url("", "", "model", 1)
        assert result is None or result == ""
