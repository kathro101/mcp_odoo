"""Tests for src/odoo_service/schema_enrichment.py — AI-powered schema enrichment.

One-time, offline enrichment. Results cached to disk.
Only custom models get AI summary (standard models skip).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

from src.shared.types import FieldInfo, ModelSchema


def _make_schema(key: str, odoo_model: str, fields: dict | None = None) -> ModelSchema:
    """Helper: create a minimal ModelSchema."""
    return ModelSchema(
        key=key,
        label=key.replace("_", " ").title(),
        odoo_model=odoo_model,
        all_fields=fields or {},
    )


def _make_schema_with_fields(odoo_model: str) -> ModelSchema:
    """Helper: create a schema with realistic fields."""
    fields = {
        "name": FieldInfo(
            name="name", field_type="char", string="Name", required=True, usage_frequency=10
        ),
        "partner_id": FieldInfo(
            name="partner_id", field_type="many2one", string="Customer", usage_frequency=5
        ),
        "state": FieldInfo(
            name="state", field_type="selection", string="Status", usage_frequency=3
        ),
    }
    return ModelSchema(
        key=odoo_model.replace(".", "_"),
        label=odoo_model.replace(".", " ").title(),
        odoo_model=odoo_model,
        all_fields=fields,
        create_fields=["name", "partner_id"],
        required_fields=["name"],
    )


class TestIsStandardModel:
    """Tests for _is_standard_model()."""

    def test_standard_models_identified(self):
        """sale.order, res.partner etc should be flagged as standard."""
        from src.odoo_service.schema_enrichment import _is_standard_model

        assert _is_standard_model("sale.order") is True
        assert _is_standard_model("res.partner") is True
        assert _is_standard_model("account.move") is True
        assert _is_standard_model("stock.picking") is True
        assert _is_standard_model("purchase.order") is True
        assert _is_standard_model("crm.lead") is True
        assert _is_standard_model("hr.employee") is True
        assert _is_standard_model("product.product") is True
        assert _is_standard_model("mail.message") is True

    def test_custom_models_not_standard(self):
        """x_* and custom module models should not be flagged."""
        from src.odoo_service.schema_enrichment import _is_standard_model

        assert _is_standard_model("x_custom_model") is False
        assert _is_standard_model("ops_logistics.shipment") is False
        assert _is_standard_model("my_module.my_model") is False

    def test_empty_model_name(self):
        """Empty model name should not be standard."""
        from src.odoo_service.schema_enrichment import _is_standard_model

        assert _is_standard_model("") is False


class TestEnrichCustomModels:
    """Tests for enrich_custom_models() — one-time AI summary."""

    def test_skips_standard_models(self):
        """Should not call LLM for standard Odoo models."""
        from src.odoo_service.schema_enrichment import enrich_custom_models

        mock_llm = MagicMock()
        schemas = {
            "sale_order": _make_schema("sale_order", "sale.order"),
            "res_partner": _make_schema("res_partner", "res.partner"),
            "stock_picking": _make_schema("stock_picking", "stock.picking"),
        }

        with tempfile.TemporaryDirectory() as tmpdir:
            enrich_custom_models(schemas, mock_llm, cache_dir=tmpdir)

            # LLM should NOT be called for standard models
            mock_llm.ask.assert_not_called()

    def test_enriches_custom_models(self):
        """Should call LLM for custom model and cache the result."""
        from src.odoo_service.schema_enrichment import enrich_custom_models

        mock_llm = MagicMock()
        mock_llm.ask.return_value = "This is a custom shipment tracking model."

        schema = _make_schema_with_fields("ops_logistics.shipment")
        schemas = {"shipment": schema}

        with tempfile.TemporaryDirectory() as tmpdir:
            enrich_custom_models(schemas, mock_llm, cache_dir=tmpdir)

            mock_llm.ask.assert_called_once()
            assert schema.summary == "This is a custom shipment tracking model."

    def test_cached_summary_not_regenerated(self):
        """Should use cached summary if it exists on disk."""
        from src.odoo_service.schema_enrichment import enrich_custom_models

        mock_llm = MagicMock()
        schema = _make_schema_with_fields("x_custom_model")
        schemas = {"x_custom_model": schema}

        with tempfile.TemporaryDirectory() as tmpdir:
            # Pre-create a cache file
            cache_path = Path(tmpdir) / "x_custom_model_summary.txt"
            cache_path.write_text("Cached summary text")

            enrich_custom_models(schemas, mock_llm, cache_dir=tmpdir)

            # LLM should NOT be called — cache hit
            mock_llm.ask.assert_not_called()
            assert schema.summary == "Cached summary text"

    def test_no_custom_models_no_calls(self):
        """Should not call LLM when there are no custom models."""
        from src.odoo_service.schema_enrichment import enrich_custom_models

        mock_llm = MagicMock()
        schemas = {}

        with tempfile.TemporaryDirectory() as tmpdir:
            enrich_custom_models(schemas, mock_llm, cache_dir=tmpdir)
            mock_llm.ask.assert_not_called()

    def test_llm_error_does_not_crash(self):
        """Should handle LLM errors gracefully without crashing."""
        from src.odoo_service.schema_enrichment import enrich_custom_models

        mock_llm = MagicMock()
        mock_llm.ask.side_effect = RuntimeError("LLM timeout")

        schema = _make_schema_with_fields("x_custom_model")
        schemas = {"x_custom_model": schema}

        with tempfile.TemporaryDirectory() as tmpdir:
            # Should not raise
            enrich_custom_models(schemas, mock_llm, cache_dir=tmpdir)
            # Summary should remain empty/default
            assert schema.summary == ""


class TestEnrichAliases:
    """Tests for enrich_aliases() — one-time AI alias/keyword generation."""

    def test_generates_aliases_and_keywords(self):
        """Should call LLM and populate field_aliases and match_keywords."""
        from src.odoo_service.schema_enrichment import enrich_aliases

        mock_llm = MagicMock()
        mock_llm.ask_json.return_value = {
            "field_aliases": {"customer": "partner_id", "date": "scheduled_date"},
            "match_keywords": ["shipment", "delivery", "transfer"],
        }

        schema = _make_schema_with_fields("stock.picking")
        schemas = {"stock_picking": schema}

        enrich_aliases(schemas, mock_llm)

        assert schema.field_aliases == {"customer": "partner_id", "date": "scheduled_date"}
        assert schema.match_keywords == ["shipment", "delivery", "transfer"]
        mock_llm.ask_json.assert_called_once()

    def test_empty_schemas_does_nothing(self):
        """Should handle empty schema dict without error."""
        from src.odoo_service.schema_enrichment import enrich_aliases

        mock_llm = MagicMock()
        enrich_aliases({}, mock_llm)

        mock_llm.ask_json.assert_not_called()

    def test_llm_error_does_not_crash(self):
        """Should handle LLM errors gracefully."""
        from src.odoo_service.schema_enrichment import enrich_aliases

        mock_llm = MagicMock()
        mock_llm.ask_json.side_effect = RuntimeError("LLM timeout")

        schema = _make_schema_with_fields("stock.picking")
        schemas = {"stock_picking": schema}

        enrich_aliases(schemas, mock_llm)

        # Should not crash, aliases remain empty
        assert schema.field_aliases == {}
        assert schema.match_keywords == []

    def test_skips_enriched_schemas(self):
        """Should skip schemas that already have aliases and keywords."""
        from src.odoo_service.schema_enrichment import enrich_aliases

        mock_llm = MagicMock()
        schema = _make_schema_with_fields("stock.picking")
        schema.field_aliases = {"existing": "field"}
        schema.match_keywords = ["existing_kw"]
        schemas = {"stock_picking": schema}

        enrich_aliases(schemas, mock_llm)

        # Should NOT call LLM — already enriched
        mock_llm.ask_json.assert_not_called()
