"""Tests for src/odoo_service/schema_discovery.py — model introspection.

All tests use mocks — never hit live Odoo.
"""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

# ── Helpers ────────────────────────────────────────────────────────────────


def _make_odoo_mock(
    fields_get: dict | None = None,
    ir_fields: list[dict] | None = None,
    views: list[dict] | None = None,
    installed_modules: list[str] | None = None,
    ir_model_data: list[dict] | None = None,
) -> MagicMock:
    """Build a mock OdooClient with configurable responses."""
    mock = MagicMock()

    if fields_get is not None:
        mock.fields_get.return_value = fields_get
    else:
        mock.fields_get.return_value = {}

    # search_read for ir.model.fields
    def search_read_side_effect(model, domain, **kwargs):
        if model == "ir.model.fields":
            if ir_fields is not None:
                return ir_fields
            return _default_ir_fields()
        elif model == "ir.ui.view":
            if views is not None:
                return views
            return _default_views()
        elif model == "ir.model":
            result = []
            for mod_name in installed_modules or _default_modules():
                result.append(
                    {
                        "id": hash(mod_name) % 10000,
                        "model": mod_name,
                        "name": mod_name.replace(".", " ").title(),
                        "state": "base",
                    }
                )
            return result
        elif model == "ir.model.data":
            if ir_model_data is not None:
                return ir_model_data
            return _default_ir_model_data()
        return []

    mock.search_read.side_effect = search_read_side_effect

    # search for ir.model (to get model_id) and list installed modules
    def search_side_effect(model, domain, **kwargs):
        results = []
        if model == "ir.model":
            # _list_installed_modules: search([("state","=","base")])
            # Always return the installed_modules list
            mods = installed_modules if installed_modules else _default_modules()
            if any(
                isinstance(item, (list, tuple))
                and len(item) >= 3
                and item[0] == "state"
                and item[2] == "base"
                for item in (domain or [])
            ):
                # Return fake IDs for each model
                return [hash(m) % 10000 for m in mods]
            # _query_ir_model_fields: search([("model","=", model_name)])
            for item in domain or []:
                if isinstance(item, (list, tuple)) and len(item) >= 3 and item[0] == "model":
                    results.append(hash(item[2]) % 10000)
        return results[:1] if results else []

    mock.search.side_effect = search_side_effect

    return mock


def _default_modules() -> list[str]:
    return [
        "res.partner",
        "res.company",
        "res.users",
        "sale.order",
        "stock.picking",
        "account.move",
        "purchase.order",
        "product.product",
    ]


def _default_ir_fields() -> list[dict]:
    """Default ir.model.fields data for stock.picking."""
    return [
        {
            "name": "name",
            "compute": "",
            "related": "",
            "depends": [],
            "store": True,
            "required": True,
        },
        {
            "name": "partner_id",
            "compute": "",
            "related": "",
            "depends": [],
            "store": True,
            "required": False,
        },
        {
            "name": "display_name",
            "compute": "_compute_display_name",
            "related": "",
            "depends": ["name"],
            "store": False,
            "required": False,
        },
        {
            "name": "state",
            "compute": "",
            "related": "",
            "depends": [],
            "store": True,
            "required": False,
        },
    ]


def _default_views() -> list[dict]:
    """Default ir.ui.view data."""
    return [
        {
            "arch_db": (
                "<form><sheet><group>"
                '<field name="name"/>'
                '<field name="partner_id"/>'
                '<field name="state"/>'
                "</group></sheet></form>"
            ),
            "type": "form",
        },
        {
            "arch_db": ('<tree><field name="name"/><field name="state"/></tree>'),
            "type": "tree",
        },
    ]


def _default_ir_model_data() -> list[dict]:
    return [{"module": "stock", "name": "model_stock_picking"}]


# ── Tests ──────────────────────────────────────────────────────────────────


class TestSchemaDiscoveryInit:
    """Tests for SchemaDiscovery initialization."""

    def test_init_stores_odoo_client_and_cache_dir(self):
        """Should store odoo client and optional cache dir."""
        from src.odoo_service.schema_discovery import SchemaDiscovery

        mock_odoo = _make_odoo_mock()
        disc = SchemaDiscovery(mock_odoo, cache_dir="/tmp/schemas")

        assert disc.odoo is mock_odoo
        assert disc.cache_dir == Path("/tmp/schemas")

    def test_init_default_cache_dir(self):
        """Should default cache_dir to config/schemas."""
        from src.odoo_service.schema_discovery import SchemaDiscovery

        mock_odoo = _make_odoo_mock()
        disc = SchemaDiscovery(mock_odoo)

        assert disc.cache_dir == Path("config/schemas")


class TestDiscover:
    """Tests for the discover() method."""

    def test_discover_returns_model_schemas(self):
        """discover() should return a dict of ModelSchema keyed by model name."""
        from src.odoo_service.schema_discovery import SchemaDiscovery

        mock = _make_odoo_mock(
            fields_get={
                "name": {"type": "char", "string": "Name", "required": True},
                "partner_id": {"type": "many2one", "string": "Contact", "relation": "res.partner"},
            },
        )

        disc = SchemaDiscovery(mock)
        schemas = disc.discover()

        assert isinstance(schemas, dict)
        assert len(schemas) > 0

        # Check first schema structure
        first = next(iter(schemas.values()))
        assert first.odoo_model
        assert first.label
        assert len(first.all_fields) > 0
        assert first.key == first.odoo_model.replace(".", "_")

    def test_discover_fields_have_correct_types(self):
        """Discovered fields should map to correct FieldInfo attributes."""
        from src.odoo_service.schema_discovery import SchemaDiscovery

        mock = _make_odoo_mock(
            fields_get={
                "name": {
                    "type": "char",
                    "string": "Reference",
                    "required": True,
                    "readonly": False,
                },
                "date_done": {"type": "datetime", "string": "Date Done", "readonly": True},
            },
            installed_modules=["stock.picking"],
        )

        disc = SchemaDiscovery(mock)
        schemas = disc.discover()

        # Key is model name with dots → underscores
        schema = schemas["stock.picking"]
        assert schema.all_fields["name"].field_type == "char"
        assert schema.all_fields["name"].required is True
        assert schema.all_fields["name"].readonly is False
        assert schema.all_fields["date_done"].field_type == "datetime"
        assert schema.all_fields["date_done"].readonly is True

    def test_discover_empty_odoo_returns_empty(self):
        """discover() should return empty dict when Odoo has no models."""
        from src.odoo_service.schema_discovery import SchemaDiscovery

        mock = _make_odoo_mock(
            installed_modules=[],
            ir_model_data=[],
        )
        mock.search_read.side_effect = lambda model, domain, **kw: []

        disc = SchemaDiscovery(mock)
        schemas = disc.discover()

        assert schemas == {}

    def test_discover_odoo_error_propagates(self):
        """discover() should propagate connection errors from Odoo."""
        from src.odoo_service.schema_discovery import SchemaDiscovery

        mock = MagicMock()
        mock.search_read.side_effect = ConnectionRefusedError("Odoo is down")

        disc = SchemaDiscovery(mock)
        with pytest.raises(ConnectionRefusedError):
            disc.discover()


class TestQueryIrModelFields:
    """Tests for _query_ir_model_fields()."""

    @pytest.fixture
    def discovery(self):
        from src.odoo_service.schema_discovery import SchemaDiscovery

        return SchemaDiscovery(_make_odoo_mock())

    def test_extracts_computed_field(self, discovery):
        """Should detect computed fields from ir.model.fields."""
        mock = _make_odoo_mock(
            ir_fields=[
                {
                    "name": "display_name",
                    "compute": "_compute_display_name",
                    "related": "",
                    "depends": ["name"],
                    "store": False,
                    "required": False,
                },
                {
                    "name": "name",
                    "compute": "",
                    "related": "",
                    "depends": [],
                    "store": True,
                    "required": True,
                },
            ],
        )
        discovery.odoo = mock

        result = discovery._query_ir_model_fields("stock.picking")

        assert result["display_name"]["compute"] == "_compute_display_name"
        assert result["display_name"]["store"] is False
        assert result["name"]["required"] is True
        assert result["name"]["store"] is True

    def test_returns_empty_for_unknown_model(self, discovery):
        """Should return empty dict when model not found in ir.model."""
        mock = _make_odoo_mock()
        mock.search.return_value = []  # No matching ir.model
        # Also ensure search_read for ir.model.fields returns empty
        mock.search_read.side_effect = None
        mock.search_read.return_value = []
        discovery.odoo = mock

        result = discovery._query_ir_model_fields("nonexistent.model")

        assert result == {}

    def test_handles_odoo_error_gracefully(self, discovery):
        """Should return empty dict on Odoo error."""
        mock = _make_odoo_mock()
        mock.search.side_effect = ConnectionRefusedError("Down")
        discovery.odoo = mock

        result = discovery._query_ir_model_fields("stock.picking")

        assert result == {}


class TestAnalyzeViews:
    """Tests for _analyze_views()."""

    @pytest.fixture
    def discovery(self):
        from src.odoo_service.schema_discovery import SchemaDiscovery

        return SchemaDiscovery(_make_odoo_mock())

    def test_counts_field_usage_from_views(self, discovery):
        """Should count field occurrences weighted by view type."""
        mock = _make_odoo_mock(
            views=[
                {
                    "arch_db": '<form><field name="name"/><field name="name"/>'
                    '<field name="partner_id"/></form>',
                    "type": "form",
                },
                {"arch_db": '<tree><field name="name"/></tree>', "type": "tree"},
            ],
        )
        discovery.odoo = mock

        result = discovery._analyze_views("stock.picking")

        # name: 2 occurrences in form (weight 3 each) + 1 in tree (weight 2) = 8
        # partner_id: 1 occurrence in form (weight 3) = 3
        assert result["name"] == 8
        assert result["partner_id"] == 3

    def test_form_views_higher_weight(self, discovery):
        """Form views should have higher weight than tree/kanban."""
        mock = _make_odoo_mock(
            views=[
                {"arch_db": '<form><field name="f1"/></form>', "type": "form"},
                {"arch_db": '<tree><field name="f1"/></tree>', "type": "tree"},
            ],
        )
        discovery.odoo = mock

        result = discovery._analyze_views("stock.picking")

        # form weight 3 + tree weight 2 = 5
        assert result["f1"] == 5

    def test_empty_views_returns_empty(self, discovery):
        """Should return empty dict when no views found."""
        mock = _make_odoo_mock(views=[])
        discovery.odoo = mock

        result = discovery._analyze_views("stock.picking")

        assert result == {}

    def test_parse_field_with_attrs(self, discovery):
        """Should extract field name even with extra attributes."""
        mock = _make_odoo_mock(
            views=[
                {
                    "arch_db": '<field name="state" widget="statusbar" '
                    'invisible="1" readonly="1"/>',
                    "type": "form",
                }
            ],
        )
        discovery.odoo = mock

        result = discovery._analyze_views("stock.picking")

        assert "state" in result
        assert result["state"] == 3  # form weight

    def test_handles_non_xml_arch_gracefully(self, discovery):
        """Should not crash on empty or None arch_db."""
        mock = _make_odoo_mock(
            views=[{"arch_db": "", "type": "form"}, {"arch_db": None, "type": "tree"}],
        )
        discovery.odoo = mock

        result = discovery._analyze_views("stock.picking")

        # Should not crash, may return empty
        assert isinstance(result, dict)


class TestClassifyFields:
    """Tests for _classify_fields()."""

    @pytest.fixture
    def discovery(self):
        from src.odoo_service.schema_discovery import SchemaDiscovery

        return SchemaDiscovery(_make_odoo_mock())

    def test_classify_separates_create_search_required(self, discovery):
        """Should separate fields into create, search, and required lists."""
        from src.shared.types import FieldInfo

        fields = {
            "name": FieldInfo(
                name="name", field_type="char", string="Name", required=True, usage_frequency=10
            ),
            "partner_id": FieldInfo(
                name="partner_id",
                field_type="many2one",
                string="Contact",
                required=True,
                usage_frequency=5,
            ),
            "internal_note": FieldInfo(
                name="internal_note", field_type="text", string="Notes", usage_frequency=1
            ),
            "id": FieldInfo(
                name="id", field_type="integer", string="ID", readonly=True, usage_frequency=0
            ),
            "display_name": FieldInfo(
                name="display_name",
                field_type="char",
                string="Display Name",
                computed=True,
                store=False,
                usage_frequency=3,
            ),
        }

        create_f, search_f, required_f = discovery._classify_fields(fields)

        assert "name" in create_f
        assert "partner_id" in create_f
        assert "internal_note" in create_f
        # Computed fields should not be in create
        assert "display_name" not in create_f
        # Readonly fields should not be in create
        assert "id" not in create_f
        # Required fields
        assert "name" in required_f
        assert "partner_id" in required_f
        # Search fields: high-usage char/m2o/selection
        assert "name" in search_f

    def test_computed_fields_excluded_from_create(self, discovery):
        """Computed fields should never be in create_fields."""
        from src.shared.types import FieldInfo

        fields = {
            "computed_x": FieldInfo(
                name="computed_x", field_type="char", string="X", computed=True, usage_frequency=5
            ),
        }

        create_f, _, _ = discovery._classify_fields(fields)
        assert "computed_x" not in create_f

    def test_related_fields_excluded_from_create(self, discovery):
        """Related fields should be excluded from create_fields."""
        from src.shared.types import FieldInfo

        fields = {
            "related_x": FieldInfo(
                name="related_x",
                field_type="char",
                string="X",
                related="partner_id.name",
                usage_frequency=3,
            ),
        }

        create_f, _, _ = discovery._classify_fields(fields)
        assert "related_x" not in create_f


class TestFilterUserFacingModels:
    """Tests for _filter_user_facing_models()."""

    @pytest.fixture
    def discovery(self):
        from src.odoo_service.schema_discovery import SchemaDiscovery

        return SchemaDiscovery(_make_odoo_mock())

    def test_filters_technical_models(self, discovery):
        """Should exclude ir.*, base_*, and other technical models."""
        models = [
            {"model": "res.partner", "name": "Contact"},
            {"model": "ir.model", "name": "Models"},
            {"model": "ir.ui.view", "name": "Views"},
            {"model": "base.language.install", "name": "Language Install"},
            {"model": "res.groups", "name": "Groups"},
            {"model": "mail.message", "name": "Message"},
        ]

        filtered = discovery._filter_user_facing_models(models)

        filtered_names = [m[0] for m in filtered]
        assert "res.partner" in filtered_names
        assert "ir.model" not in filtered_names
        assert "ir.ui.view" not in filtered_names
        assert "base.language.install" not in filtered_names


class TestDiscoverSubModels:
    """Tests for _discover_sub_models()."""

    @pytest.fixture
    def discovery(self):
        from src.odoo_service.schema_discovery import SchemaDiscovery

        return SchemaDiscovery(_make_odoo_mock())

    def test_discovers_one2many_fields(self, discovery):
        """Should find one2many fields and create SubModelSchema."""
        from src.shared.types import FieldInfo

        fields = {
            "order_line": FieldInfo(
                name="order_line",
                field_type="one2many",
                string="Order Lines",
                relation="sale.order.line",
            ),
            "partner_id": FieldInfo(
                name="partner_id",
                field_type="many2one",
                string="Customer",
                relation="res.partner",
            ),
            "name": FieldInfo(
                name="name",
                field_type="char",
                string="Name",
            ),
        }

        sub_models = discovery._discover_sub_models("sale.order", fields)

        # Only one2many fields become sub-models
        assert len(sub_models) == 1
        assert sub_models[0].field_name == "order_line"
        assert sub_models[0].related_model == "sale.order.line"
        assert sub_models[0].is_one_to_many is True

    def test_no_one2many_returns_empty(self, discovery):
        """Should return empty list when no one2many fields exist."""
        from src.shared.types import FieldInfo

        fields = {
            "name": FieldInfo(name="name", field_type="char", string="Name"),
            "partner_id": FieldInfo(
                name="partner_id", field_type="many2one", string="Partner", relation="res.partner"
            ),
        }

        sub_models = discovery._discover_sub_models("res.partner", fields)
        assert sub_models == []


class TestSaveSchemas:
    """Tests for _save_schemas()."""

    def test_saves_schemas_to_disk(self):
        """Should write each schema as a JSON file."""
        from src.odoo_service.schema_discovery import SchemaDiscovery
        from src.shared.types import FieldInfo, ModelSchema

        with tempfile.TemporaryDirectory() as tmpdir:
            disc = SchemaDiscovery(_make_odoo_mock(), cache_dir=tmpdir)

            schema = ModelSchema(
                key="test_model",
                label="Test Model",
                odoo_model="test.model",
                all_fields={
                    "name": FieldInfo(name="name", field_type="char", string="Name"),
                },
                create_fields=["name"],
                required_fields=["name"],
            )
            schemas = {"test_model": schema}

            disc._save_schemas(schemas)

            # Verify file was written
            filepath = Path(tmpdir) / "test_model.json"
            assert filepath.exists()

            raw = json.loads(filepath.read_text())
            assert raw["key"] == "test_model"
            assert raw["odoo_model"] == "test.model"
            assert "name" in raw["all_fields"]
