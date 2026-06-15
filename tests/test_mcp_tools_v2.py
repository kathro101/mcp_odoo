"""Tests for enhanced chat_odoo handler — rich schema + action dispatch."""

from __future__ import annotations

import json
from unittest.mock import MagicMock, patch

from src.shared.types import (
    AgentConfig,
    FieldInfo,
    ModelSchema,
    RouteResult,
    SubModelSchema,
)


def _make_schema() -> ModelSchema:
    """Create a realistic stock.picking schema with aliases."""
    return ModelSchema(
        key="stock_picking",
        label="Transfers",
        odoo_model="stock.picking",
        summary="Stock transfer for moving inventory between locations.",
        all_fields={
            "name": FieldInfo(
                name="name",
                field_type="char",
                string="Reference",
                required=True,
                usage_frequency=15,
            ),
            "partner_id": FieldInfo(
                name="partner_id",
                field_type="many2one",
                string="Contact",
                required=True,
                relation="res.partner",
                usage_frequency=10,
            ),
            "picking_type_id": FieldInfo(
                name="picking_type_id",
                field_type="many2one",
                string="Operation Type",
                required=True,
                relation="stock.picking.type",
                usage_frequency=10,
            ),
            "scheduled_date": FieldInfo(
                name="scheduled_date",
                field_type="datetime",
                string="Scheduled Date",
                usage_frequency=5,
            ),
            "state": FieldInfo(
                name="state",
                field_type="selection",
                string="Status",
                selection=[("draft", "Draft"), ("done", "Done"), ("cancel", "Cancelled")],
                usage_frequency=8,
            ),
            "origin": FieldInfo(
                name="origin", field_type="char", string="Source Document", usage_frequency=3
            ),
        },
        create_fields=["name", "partner_id", "picking_type_id", "scheduled_date", "origin"],
        search_fields=["name", "partner_id", "state", "origin"],
        required_fields=["name", "partner_id", "picking_type_id"],
        field_aliases={
            "customer": "partner_id",
            "contact": "partner_id",
            "date": "scheduled_date",
            "status": "state",
            "reference": "name",
            "source": "origin",
            "type": "picking_type_id",
        },
        match_keywords=["shipment", "delivery", "transfer"],
        sub_models=[
            SubModelSchema(
                field_name="move_line_ids", related_model="stock.move.line", is_one_to_many=True
            ),
        ],
        usage_frequency_total=51,
    )


# ── Tests: Enriched Schema Response ─────────────────────────────────────


class TestChatOdooEnrichedResponse:
    """Tests that chat_odoo returns rich schema data for Claude to use."""

    @patch("src.mcp_server.tools._get_agents")
    @patch("src.mcp_server.tools._get_schema_store")
    @patch("src.mcp_server.tools.route_message")
    async def test_response_includes_field_aliases(self, mock_route, mock_store, mock_agents):
        """chat_odoo response should include field_aliases for smart mapping."""
        from src.mcp_server.tools import chat_odoo_handler

        mock_agents.return_value = {
            "logistics": AgentConfig(
                key="logistics",
                name="Logistics Agent",
                description="",
                keywords=["shipment"],
                models=[],
                default_model="stock_picking",
            ),
        }
        mock_route.return_value = RouteResult(
            agent_key="logistics",
            model_key="stock_picking",
            score=8,
        )
        mock_schema = _make_schema()
        mock_store.return_value.get.return_value = mock_schema

        result = await chat_odoo_handler(message="Create a shipment")

        text = result[0]["text"]
        assert "FIELD ALIASES" in text
        # Aliases show field_name → alias mapping; deduplicated by field
        assert "partner_id" in text
        assert "contact" in text
        assert "type" in text
        assert "picking_type_id" in text

    @patch("src.mcp_server.tools._get_agents")
    @patch("src.mcp_server.tools._get_schema_store")
    @patch("src.mcp_server.tools.route_message")
    async def test_response_includes_field_details(self, mock_route, mock_store, mock_agents):
        """chat_odoo response should include field types and relations."""
        from src.mcp_server.tools import chat_odoo_handler

        mock_agents.return_value = {
            "logistics": AgentConfig(
                key="logistics",
                name="Logistics Agent",
                description="",
                keywords=["shipment"],
                models=[],
                default_model="stock_picking",
            ),
        }
        mock_route.return_value = RouteResult(
            agent_key="logistics",
            model_key="stock_picking",
            score=8,
        )
        mock_schema = _make_schema()
        mock_store.return_value.get.return_value = mock_schema

        result = await chat_odoo_handler(message="shipment")

        text = result[0]["text"]
        # Field details: types and relations shown
        assert "partner_id" in text
        assert "res.partner" in text
        assert "Contact" in text
        assert "picking_type_id" in text
        assert "stock.picking.type" in text
        # Selection fields shown when in create_fields
        assert "scheduled_date" in text
        assert "origin" in text

    @patch("src.mcp_server.tools._get_agents")
    @patch("src.mcp_server.tools._get_schema_store")
    @patch("src.mcp_server.tools.route_message")
    async def test_response_includes_sub_models(self, mock_route, mock_store, mock_agents):
        """chat_odoo response should mention one2many sub-models."""
        from src.mcp_server.tools import chat_odoo_handler

        mock_agents.return_value = {
            "logistics": AgentConfig(
                key="logistics",
                name="Logistics Agent",
                description="",
                keywords=["shipment"],
                models=[],
                default_model="stock_picking",
            ),
        }
        mock_route.return_value = RouteResult(
            agent_key="logistics",
            model_key="stock_picking",
            score=8,
        )
        mock_schema = _make_schema()
        mock_store.return_value.get.return_value = mock_schema

        result = await chat_odoo_handler(message="shipment")

        text = result[0]["text"]
        assert "move_line_ids" in text
        assert "stock.move.line" in text


# ── Tests: Action Dispatch ──────────────────────────────────────────────


class TestChatOdooActionDispatch:
    """Tests that chat_odoo action= parameter dispatches to operations."""

    @patch("src.mcp_server.tools._get_schema_store")
    async def test_action_preview_returns_preview(self, mock_store):
        """action=preview should call preview_record and return result."""
        from src.mcp_server.tools import chat_odoo_handler

        mock_schema = _make_schema()
        mock_store.return_value.get.return_value = mock_schema

        result = await chat_odoo_handler(
            action="preview",
            model="stock_picking",
            params={"name": "TEST001", "partner_id": 42},
        )

        text = result[0]["text"]
        data = json.loads(text)
        assert data["status"] == "needs_input"
        assert "picking_type_id" in data["missing"]
        assert "name" in data["filled"]

    @patch("src.mcp_server.tools._get_schema_store")
    @patch("src.mcp_server.tools._get_odoo_client")
    async def test_action_search_returns_results(self, mock_odoo, mock_store):
        """action=search should call search_records and return results."""
        from src.mcp_server.tools import chat_odoo_handler

        mock_schema = _make_schema()
        mock_store.return_value.get.return_value = mock_schema
        mock_odoo.return_value = MagicMock()

        with patch("src.mcp_server.tools.search_records") as mock_search:
            mock_search.return_value = {
                "status": "success",
                "records": [{"id": 1, "name": "TEST"}],
                "count": 1,
            }

            result = await chat_odoo_handler(
                action="search",
                model="stock_picking",
                params={"name": "TEST"},
            )

        text = result[0]["text"]
        data = json.loads(text)
        assert data["status"] == "success"
        assert data["count"] == 1

    @patch("src.mcp_server.tools._get_schema_store")
    async def test_action_unknown_returns_error(self, mock_store):
        """Unknown action should return error."""
        from src.mcp_server.tools import chat_odoo_handler

        mock_schema = _make_schema()
        mock_store.return_value.get.return_value = mock_schema

        result = await chat_odoo_handler(
            action="unknown_action",
            model="stock_picking",
        )

        text = result[0]["text"]
        assert "Unknown action" in text

    @patch("src.mcp_server.tools._get_schema_store")
    async def test_action_without_model_returns_error(self, mock_store):
        """Action without model should return error."""
        from src.mcp_server.tools import chat_odoo_handler

        result = await chat_odoo_handler(action="preview")

        text = result[0]["text"]
        assert "model is required" in text.lower()


# ── Tests: Enhanced list_models ────────────────────────────────────────


def _make_schema_list() -> list:
    """Create multiple schemas for testing list_models."""
    from src.shared.types import FieldInfo, ModelSchema

    return [
        ModelSchema(
            key="stock_picking",
            label="Transfers",
            odoo_model="stock.picking",
            summary="Stock transfer document for moving inventory between locations.",
            all_fields={
                "name": FieldInfo(
                    name="name", field_type="char", string="Reference", required=True
                ),
                "partner_id": FieldInfo(
                    name="partner_id", field_type="many2one", string="Contact", required=True
                ),
            },
            required_fields=["name", "partner_id"],
            match_keywords=["shipment", "delivery", "transfer", "picking", "stock move"],
        ),
        ModelSchema(
            key="sale_order",
            label="Sales Orders",
            odoo_model="sale.order",
            summary="Sales order for managing customer orders and quotations.",
            all_fields={
                "name": FieldInfo(name="name", field_type="char", string="Order Reference"),
            },
            required_fields=["partner_id"],
            match_keywords=["sale", "order", "quotation", "SO"],
        ),
        ModelSchema(
            key="account_move",
            label="Journal Entries",
            odoo_model="account.move",
            summary="Journal entries for invoices, bills, and payments.",
            all_fields={
                "name": FieldInfo(name="name", field_type="char", string="Reference"),
            },
            required_fields=["date"],
            match_keywords=["invoice", "bill", "payment", "journal"],
        ),
    ]


class TestScoreModelRelevance:
    """Tests for score_model_relevance()."""

    def test_keyword_match_adds_length(self):
        """Keyword 'shipment' (len=8) in message should add 8 to score."""
        from src.mcp_server.tools import score_model_relevance

        schema = _make_schema_list()[0]  # stock_picking with keyword "shipment"
        score = score_model_relevance(schema, "Create a shipment for ACME Corp")
        assert score >= 8  # "shipment" match = 8

    def test_no_match_returns_zero(self):
        """Irrelevant message should return 0."""
        from src.mcp_server.tools import score_model_relevance

        schema = _make_schema_list()[0]  # stock_picking
        score = score_model_relevance(schema, "What is the weather today?")
        assert score == 0

    def test_label_match_adds_score(self):
        """Label 'Transfers' in message should add 5."""
        from src.mcp_server.tools import score_model_relevance

        schema = _make_schema_list()[0]  # label: "Transfers"
        score = score_model_relevance(schema, "Show me all Transfers")
        assert score >= 5  # label match = 5

    def test_multiple_keywords_summed(self):
        """Multiple keyword matches should sum their lengths."""
        from src.mcp_server.tools import score_model_relevance

        schema = _make_schema_list()[0]  # keywords: shipment(8) + delivery(8) + transfer(8)
        score = score_model_relevance(schema, "shipment delivery transfer")
        assert score >= 24  # 8 + 8 + 8 = 24

    def test_schema_with_more_keywords_scores_higher(self):
        """stock_picking should score higher than sale_order for 'shipment' message."""
        from src.mcp_server.tools import score_model_relevance

        stock = _make_schema_list()[0]  # keywords include "shipment"
        sale = _make_schema_list()[1]  # keywords don't include "shipment"

        stock_score = score_model_relevance(stock, "Create a shipment")
        sale_score = score_model_relevance(sale, "Create a shipment")

        assert stock_score > sale_score


class TestEnhancedListModels:
    """Tests for enhanced list_models_handler with message parameter."""

    @patch("src.mcp_server.tools._get_schema_store")
    async def test_list_models_with_message_returns_top_scored(self, mock_store):
        """Passing a message should return models sorted by relevance."""
        from src.mcp_server.tools import list_models_handler

        mock_store.return_value.list_all.return_value = _make_schema_list()

        result = await list_models_handler(message="Create a shipment")

        text = result[0]["text"]
        # stock_picking should appear first (has "shipment" keyword)
        assert "stock.picking" in text
        assert "relevance" in text.lower() or "top" in text.lower()

    @patch("src.mcp_server.tools._get_schema_store")
    async def test_list_models_without_message_returns_all(self, mock_store):
        """No message should return all models (backward compatible)."""
        from src.mcp_server.tools import list_models_handler

        mock_store.return_value.list_all.return_value = _make_schema_list()

        result = await list_models_handler()

        text = result[0]["text"]
        assert "stock.picking" in text
        assert "sale.order" in text
        assert "account.move" in text

    @patch("src.mcp_server.tools._get_schema_store")
    async def test_list_models_includes_keywords_and_fields(self, mock_store):
        """Response should include keywords and field info."""
        from src.mcp_server.tools import list_models_handler

        mock_store.return_value.list_all.return_value = _make_schema_list()

        result = await list_models_handler(message="shipment")

        text = result[0]["text"]
        assert "shipment" in text
        assert "delivery" in text
        assert "required" in text.lower()


# ── Tests: Richer Schema Output (Task 09) ─────────────────────────────


class TestFormatFieldDetail:
    """Tests for _format_field_detail() with help_text and selection labels."""

    def test_selection_shows_labels(self):
        """Selection should show both key and display label."""
        from src.mcp_server.tools import _format_field_detail

        fi = FieldInfo(
            name="state",
            field_type="selection",
            string="Status",
            selection=[("draft", "Draft"), ("done", "Done")],
        )
        result = _format_field_detail(fi)
        assert "draft (Draft)" in result
        assert "done (Done)" in result

    def test_help_text_rendered(self):
        """Field with help_text should include it."""
        from src.mcp_server.tools import _format_field_detail

        fi = FieldInfo(
            name="origin",
            field_type="char",
            string="Source Document",
            help_text="Reference of the document",
        )
        result = _format_field_detail(fi)
        assert "Reference of the document" in result

    def test_no_help_text_no_dash(self):
        """Field without help_text should not have stray formatting."""
        from src.mcp_server.tools import _format_field_detail

        fi = FieldInfo(name="name", field_type="char", string="Name")
        result = _format_field_detail(fi)
        # Should not end with stray spacing or dash
        assert not result.rstrip().endswith("—")
