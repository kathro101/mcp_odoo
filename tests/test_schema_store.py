"""Tests for src/odoo_service/schema_store.py — schema cache + lookup."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


class TestSchemaStore:
    """Tests for SchemaStore class."""

    def _make_schema_dir(self, schemas: dict[str, dict]) -> str:
        """Helper: create a temp directory with schema JSON files."""
        tmpdir = tempfile.mkdtemp()
        for key, data in schemas.items():
            filepath = Path(tmpdir) / f"{key}.json"
            filepath.write_text(json.dumps(data))
        return tmpdir

    def test_load_schemas_from_dir(self):
        """SchemaStore should load all JSON files from the schema directory."""
        from src.odoo_service.schema_store import SchemaStore

        schema_dir = self._make_schema_dir(
            {
                "stock_picking": {
                    "key": "stock_picking",
                    "label": "Transfers",
                    "odoo_model": "stock.picking",
                    "all_fields": {},
                    "create_fields": ["partner_id"],
                    "search_fields": ["name"],
                    "required_fields": ["partner_id"],
                    "match_keywords": ["shipment", "delivery"],
                },
                "sale_order": {
                    "key": "sale_order",
                    "label": "Sales Orders",
                    "odoo_model": "sale.order",
                    "all_fields": {},
                    "create_fields": ["partner_id"],
                    "search_fields": ["name"],
                    "required_fields": ["partner_id"],
                    "match_keywords": ["sale", "order", "quotation"],
                },
            }
        )

        try:
            store = SchemaStore(schema_dir)
            assert len(store.list_all()) == 2
            assert store.get("stock_picking").key == "stock_picking"
            assert store.get("sale_order").key == "sale_order"
        finally:
            import shutil

            shutil.rmtree(schema_dir)

    def test_get_missing_schema_raises_key_error(self):
        """SchemaStore.get should raise KeyError for unknown models."""
        from src.odoo_service.schema_store import SchemaStore

        schema_dir = self._make_schema_dir({})
        try:
            store = SchemaStore(schema_dir)
            with pytest.raises(KeyError):
                store.get("nonexistent")
        finally:
            import shutil

            shutil.rmtree(schema_dir)

    def test_search_by_keyword_finds_match(self):
        """SchemaStore.search should find models by keyword."""
        from src.odoo_service.schema_store import SchemaStore

        schema_dir = self._make_schema_dir(
            {
                "stock_picking": {
                    "key": "stock_picking",
                    "label": "Transfers",
                    "odoo_model": "stock.picking",
                    "all_fields": {},
                    "match_keywords": ["shipment", "delivery", "stock"],
                },
                "sale_order": {
                    "key": "sale_order",
                    "label": "Sales Orders",
                    "odoo_model": "sale.order",
                    "all_fields": {},
                    "match_keywords": ["sale", "order"],
                },
            }
        )

        try:
            store = SchemaStore(schema_dir)
            results = store.search("shipment")
            assert len(results) == 1
            assert results[0].key == "stock_picking"
        finally:
            import shutil

            shutil.rmtree(schema_dir)

    def test_search_no_match_returns_empty(self):
        """SchemaStore.search should return empty list when no keyword matches."""
        from src.odoo_service.schema_store import SchemaStore

        schema_dir = self._make_schema_dir(
            {
                "stock_picking": {
                    "key": "stock_picking",
                    "label": "Transfers",
                    "odoo_model": "stock.picking",
                    "all_fields": {},
                    "match_keywords": ["shipment"],
                },
            }
        )

        try:
            store = SchemaStore(schema_dir)
            results = store.search("accounting")
            assert results == []
        finally:
            import shutil

            shutil.rmtree(schema_dir)

    def test_list_all_returns_all_schemas(self):
        """SchemaStore.list_all should return a list of all ModelSchema."""
        from src.odoo_service.schema_store import SchemaStore

        schema_dir = self._make_schema_dir(
            {
                "a": {"key": "a", "label": "A", "odoo_model": "a.model", "all_fields": {}},
                "b": {"key": "b", "label": "B", "odoo_model": "b.model", "all_fields": {}},
            }
        )

        try:
            store = SchemaStore(schema_dir)
            all_schemas = store.list_all()
            assert len(all_schemas) == 2
            keys = {s.key for s in all_schemas}
            assert keys == {"a", "b"}
        finally:
            import shutil

            shutil.rmtree(schema_dir)

    def test_empty_schema_dir(self):
        """SchemaStore should handle empty directory gracefully."""
        from src.odoo_service.schema_store import SchemaStore

        schema_dir = self._make_schema_dir({})
        try:
            store = SchemaStore(schema_dir)
            assert store.list_all() == []
        finally:
            import shutil

            shutil.rmtree(schema_dir)

    def test_invalid_json_skipped(self):
        """SchemaStore should skip invalid JSON files gracefully."""
        from src.odoo_service.schema_store import SchemaStore

        tmpdir = tempfile.mkdtemp()
        (Path(tmpdir) / "invalid.json").write_text("{not valid json")

        try:
            store = SchemaStore(tmpdir)
            # Should not crash; invalid file is skipped
            assert store.list_all() == []
        finally:
            import shutil

            shutil.rmtree(tmpdir)


class TestSchemaStoreNewFields:
    """Tests for new FieldInfo/SubModelSchema fields in schema store."""

    def test_auto_generated_roundtrips(self):
        """auto_generated flag should survive save → reload."""
        import json
        import tempfile
        from pathlib import Path

        from src.odoo_service.schema_store import SchemaStore
        from src.shared.types import FieldInfo, ModelSchema

        fields = {
            "number": FieldInfo(
                name="number",
                field_type="char",
                string="Number",
                auto_generated=True,
            ),
        }
        schema = ModelSchema(
            key="test_model",
            label="Test",
            odoo_model="test.model",
            all_fields=fields,
            create_fields=["number"],
        )

        tmpdir = tempfile.mkdtemp()
        schema_path = Path(tmpdir) / "test_model.json"
        # Manually serialize
        data = {
            "key": schema.key,
            "label": schema.label,
            "odoo_model": schema.odoo_model,
            "all_fields": {
                "number": {
                    "name": "number",
                    "field_type": "char",
                    "string": "Number",
                    "auto_generated": True,
                }
            },
            "create_fields": ["number"],
        }
        schema_path.write_text(json.dumps(data))

        try:
            store = SchemaStore(tmpdir)
            loaded = store.get("test_model")
            assert loaded.all_fields["number"].auto_generated is True
        finally:
            import shutil

            shutil.rmtree(tmpdir)

    def test_sub_model_target_fields_roundtrip(self):
        """SubModelSchema target_fields should survive save → reload."""
        import json
        import tempfile
        from pathlib import Path

        from src.odoo_service.schema_store import SchemaStore

        tmpdir = tempfile.mkdtemp()
        schema_path = Path(tmpdir) / "test_model.json"
        data = {
            "key": "test_model",
            "label": "Test",
            "odoo_model": "test.model",
            "all_fields": {},
            "sub_models": [
                {
                    "field_name": "reference_ids",
                    "related_model": "ops_logistics.reference",
                    "target_fields": ["name", "type"],
                    "target_required_fields": ["name"],
                }
            ],
        }
        schema_path.write_text(json.dumps(data))

        try:
            store = SchemaStore(tmpdir)
            loaded = store.get("test_model")
            sub = loaded.sub_models[0]
            assert sub.target_fields == ["name", "type"]
            assert sub.target_required_fields == ["name"]
        finally:
            import shutil

            shutil.rmtree(tmpdir)
