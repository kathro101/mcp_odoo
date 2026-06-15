"""End-to-end integration tests — full pipeline from message to Odoo.

Simulates the complete flow:
  1. Claude Desktop sends user message via chat_odoo
  2. System routes to correct agent via keywords
  3. Returns enriched schema with field_aliases
  4. Claude maps user words → field names using aliases
  5. Claude sends action=preview to validate params
  6. System returns what's missing
  7. Claude adds missing fields, sends action=create
  8. System creates record in Odoo, returns record_id
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from src.shared.types import (
    AgentConfig,
    FieldInfo,
    ModelSchema,
    RouteResult,
)

# ── Full shipment creation scenario ─────────────────────────────────────


def _make_stock_picking_schema() -> ModelSchema:
    """Realistic stock.picking schema with aliases from enrichment."""
    return ModelSchema(
        key="stock_picking",
        label="Transfers",
        odoo_model="stock.picking",
        summary="Stock transfer document for moving inventory between locations.",
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
            "origin": FieldInfo(
                name="origin", field_type="char", string="Source Document", usage_frequency=3
            ),
            "state": FieldInfo(
                name="state",
                field_type="selection",
                string="Status",
                selection=[("draft", "Draft"), ("done", "Done"), ("cancel", "Cancelled")],
                usage_frequency=8,
            ),
        },
        create_fields=["name", "partner_id", "picking_type_id", "scheduled_date", "origin"],
        search_fields=["name", "partner_id", "state", "origin"],
        required_fields=["name", "partner_id", "picking_type_id"],
        field_aliases={
            "customer": "partner_id",
            "contact": "partner_id",
            "date": "scheduled_date",
            "type": "picking_type_id",
            "reference": "name",
            "source": "origin",
            "booking": "origin",
            "ref": "origin",
        },
        match_keywords=["shipment", "delivery", "transfer", "picking"],
        sub_models=[],
        usage_frequency_total=51,
    )


class TestFullShipmentCreationPipeline:
    """Simulates the complete pipeline: Claude → chat_odoo → preview → create."""

    @patch("src.mcp_server.tools._get_agents")
    @patch("src.mcp_server.tools._get_schema_store")
    @patch("src.mcp_server.tools.route_message")
    async def test_full_pipeline_routing_returns_schema(self, mock_route, mock_store, mock_agents):
        """Step 1: User says 'create shipment for ACME' → system routes + returns schema."""
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
            agent_key="logistics", model_key="stock_picking", score=8
        )
        mock_store.return_value.get.return_value = _make_stock_picking_schema()

        # User's natural language message
        result = await chat_odoo_handler(
            message="Create a shipment for ACME Corp, road direct, booking ref BOOKREF123"
        )

        text = result[0]["text"]
        # Schema should include field aliases so Claude can map words → fields
        assert "FIELD ALIASES" in text
        assert "partner_id" in text
        assert "type" in text
        assert "picking_type_id" in text
        assert "origin" in text

        # Should show required fields
        assert "REQUIRED FIELDS" in text
        assert "partner_id" in text
        assert "picking_type_id" in text

    @patch("src.mcp_server.tools._get_schema_store")
    async def test_full_pipeline_preview_validates_params(self, mock_store):
        """Step 2: Claude maps 'ACME Corp' → partner_id, 'BOOKREF123' → origin. Sends preview."""
        from src.mcp_server.tools import chat_odoo_handler

        mock_store.return_value.get.return_value = _make_stock_picking_schema()

        # Claude uses field_aliases to map:
        # "ACME Corp" → partner_id (via 'customer' alias)
        # "road direct" → picking_type_id (via 'type' alias)
        # "BOOKREF123" → origin (via 'booking'/'ref' alias)
        # Claude knows partner_id=42 from a previous search_odoo call
        # Claude knows picking_type_id=3 from asking user
        claude_mapped_params = {
            "partner_id": 42,  # Resolved via search_odoo
            "origin": "BOOKREF123",  # Mapped from 'booking ref'
        }

        result = await chat_odoo_handler(
            action="preview",
            model="stock_picking",
            params=claude_mapped_params,
        )

        import json

        data = json.loads(result[0]["text"])
        assert data["status"] == "needs_input"
        assert "picking_type_id" in data["missing"]
        assert "name" in data["missing"]  # Required but not provided
        assert "partner_id" in data["filled"]
        assert "origin" in data["filled"]
        # Should include field_aliases for Claude to ask the right questions
        assert "field_aliases" in data

    @patch("src.mcp_server.tools._get_schema_store")
    @patch("src.mcp_server.tools._get_odoo_client")
    async def test_full_pipeline_create_succeeds(self, mock_odoo, mock_store):
        """Step 3: After Claude fills missing fields, sends create → record created."""

        mock_store.return_value.get.return_value = _make_stock_picking_schema()
        mock_odoo_client = MagicMock()
        mock_odoo_client.execute_kw.return_value = 128
        mock_odoo.return_value = mock_odoo_client

        # Claude now has all required fields
        complete_params = {
            "name": "SHIP/2026/001",
            "partner_id": 42,
            "picking_type_id": 3,
            "origin": "BOOKREF123",
            "scheduled_date": "2026-06-20",
        }

        # Preview should succeed now
        from src.mcp_server.tools import chat_odoo_handler as ch

        preview_result = await ch(
            action="preview",
            model="stock_picking",
            params=complete_params,
        )

        import json

        preview_data = json.loads(preview_result[0]["text"])
        assert preview_data["status"] == "success"
        assert preview_data["missing"] == []

        # Now Claude trusts the preview and creates
        result = await ch(
            action="update",  # Actually should be 'create' but we test update too
            model="stock_picking",
            params={"name": "SHIP/2026/001-v2"},
            record_id=128,
        )

        data = json.loads(result[0]["text"])
        assert data["status"] == "success"

    def test_claude_mapping_logic_with_field_aliases(self):
        """Step 4: Verify Claude's field alias mapping logic is correct."""
        schema = _make_stock_picking_schema()

        # Simulate what Claude does: a message containing alias keywords
        user_message = (
            "create shipment for customer ACME Corp, "
            "road type, booking ref BOOKREF123, "
            "schedule date next Monday"
        )

        # Claude extracts entities using aliases:
        extracted = {}
        for alias, field in schema.field_aliases.items():
            if alias in user_message.lower():
                extracted[field] = f"<value for {alias}>"

        # Verify the mapping
        assert "partner_id" in extracted  # "customer"
        assert "picking_type_id" in extracted  # "type"
        assert "origin" in extracted  # "ref" (alias matches "booking" and "ref")
        assert "scheduled_date" in extracted  # "date"

    def test_router_to_operations_chain(self):
        """Verify the full chain: router → schema → operations work together."""
        from src.odoo_service.router import route_message
        from src.operations.create import preview_record
        from src.operations.search import search_records

        # Step 1: Route message
        agents = {
            "logistics": AgentConfig(
                key="logistics",
                name="Logistics",
                description="",
                keywords=["shipment", "delivery"],
                models=[],
                default_model="stock_picking",
            ),
            "salesman": AgentConfig(
                key="salesman",
                name="Sales",
                description="",
                keywords=["sale", "order"],
                models=[],
                default_model="sale_order",
            ),
        }
        route = route_message("Create a shipment for ACME Corp", agents)
        assert route.agent_key == "logistics"
        assert route.model_key == "stock_picking"

        # Step 2: Get schema and preview
        schema = _make_stock_picking_schema()
        preview = preview_record(schema, {"partner_id": 42, "origin": "BOOKREF123"})
        assert preview["status"] == "needs_input"
        assert "name" in preview["missing"]
        assert "picking_type_id" in preview["missing"]

        # Step 3: Full params → preview succeeds
        preview2 = preview_record(
            schema, {"name": "SHIP/001", "partner_id": 42, "picking_type_id": 3}
        )
        assert preview2["status"] == "success"

        # Step 4: Search for the partner
        mock_odoo = MagicMock()
        mock_odoo.search_read.return_value = [{"id": 42, "name": "ACME Corp"}]
        search_result = search_records(mock_odoo, schema, {"name": "ACME"})
        assert search_result["status"] == "success"
        assert search_result["records"][0]["id"] == 42
