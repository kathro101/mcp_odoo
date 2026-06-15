"""Tests for src/odoo_service/router.py — keyword-based routing."""

from __future__ import annotations

from src.shared.types import AgentConfig, RouteResult


class TestRouteMessage:
    """Tests for route_message function."""

    def test_exact_keyword_match(self):
        """Should route to the agent with the matching keyword."""
        from src.odoo_service.router import route_message

        agents = {
            "logistics": AgentConfig(
                key="logistics",
                name="Logistics Agent",
                description="Handles shipments",
                keywords=["shipment", "delivery", "stock"],
                models=["stock.picking"],
                default_model="stock_picking",
            ),
            "salesman": AgentConfig(
                key="salesman",
                name="Sales Agent",
                description="Handles sales",
                keywords=["sale", "order", "quotation"],
                models=["sale.order"],
                default_model="sale_order",
            ),
        }

        result = route_message("Create a shipment for ACME Corp", agents)

        assert result.agent_key == "logistics"
        assert result.score > 0

    def test_partial_keyword_match(self):
        """Should match when keyword is part of a word."""
        from src.odoo_service.router import route_message

        agents = {
            "logistics": AgentConfig(
                key="logistics",
                name="Logistics",
                description="",
                keywords=["ship"],
                models=["stock.picking"],
                default_model="stock_picking",
            ),
        }

        result = route_message("I need to create a shipment", agents)

        assert result.agent_key == "logistics"
        assert result.score > 0

    def test_multiple_matches_returns_highest_score(self):
        """Should return the agent with the most keyword matches."""
        from src.odoo_service.router import route_message

        agents = {
            "logistics": AgentConfig(
                key="logistics",
                name="Logistics",
                description="",
                keywords=["shipment", "delivery"],
                models=["stock.picking"],
                default_model="stock_picking",
            ),
            "salesman": AgentConfig(
                key="salesman",
                name="Sales",
                description="",
                keywords=["shipment", "sale", "order"],
                models=["sale.order"],
                default_model="sale_order",
            ),
        }

        result = route_message("shipment order sale delivery", agents)

        # salesman has 2 matches (shipment, sale, order) vs logistics 2 matches (shipment, delivery)
        # Both have 2 — sale length 4 > delivery length 8? No, we score by keyword length
        # shipment(8) + delivery(8) = 16 for logistics vs shipment(8) + sale(4) + order(5) = 17 for salesman
        assert result.agent_key == "salesman"

    def test_no_keyword_match_returns_no_match(self):
        """Should return RouteResult with agent_key=None when no keywords match."""
        from src.odoo_service.router import route_message

        agents = {
            "logistics": AgentConfig(
                key="logistics",
                name="Logistics",
                description="",
                keywords=["shipment"],
                models=["stock.picking"],
                default_model="stock_picking",
            ),
        }

        result = route_message("What is the weather?", agents)

        assert result.agent_key is None
        assert result.model_key is None
        assert result.score == 0

    def test_empty_message_returns_no_match(self):
        """Should handle empty message gracefully."""
        from src.odoo_service.router import route_message

        agents = {
            "logistics": AgentConfig(
                key="logistics",
                name="Logistics",
                description="",
                keywords=["shipment"],
                models=["stock.picking"],
                default_model="stock_picking",
            ),
        }

        result = route_message("", agents)

        assert result.agent_key is None
        assert result.score == 0

    def test_empty_agents_returns_no_match(self):
        """Should handle empty agents dict."""
        from src.odoo_service.router import route_message

        result = route_message("Create a shipment", {})

        assert result.agent_key is None
        assert result.score == 0

    def test_case_insensitive_matching(self):
        """Keyword matching should be case-insensitive."""
        from src.odoo_service.router import route_message

        agents = {
            "logistics": AgentConfig(
                key="logistics",
                name="Logistics",
                description="",
                keywords=["Shipment", "DELIVERY"],
                models=["stock.picking"],
                default_model="stock_picking",
            ),
        }

        result = route_message("create a SHIPMENT for delivery", agents)

        assert result.agent_key == "logistics"
        assert result.score > 0

    def test_unicode_message(self):
        """Should handle unicode/emoji in messages."""
        from src.odoo_service.router import route_message

        agents = {
            "logistics": AgentConfig(
                key="logistics",
                name="Logistics",
                description="",
                keywords=["shipment"],
                models=["stock.picking"],
                default_model="stock_picking",
            ),
        }

        result = route_message("📦 Create a shipment for ACME 🚚", agents)

        assert result.agent_key == "logistics"
        assert result.score > 0

    def test_very_long_message(self):
        """Should handle very long messages without issues."""
        from src.odoo_service.router import route_message

        agents = {
            "logistics": AgentConfig(
                key="logistics",
                name="Logistics",
                description="",
                keywords=["shipment"],
                models=["stock.picking"],
                default_model="stock_picking",
            ),
        }

        long_message = "lorem ipsum " * 200 + " shipment " + "dolor sit " * 100
        result = route_message(long_message, agents)

        assert result.agent_key == "logistics"

    def test_tie_break_uses_alphabetical_order(self):
        """When scores are equal, the agent key determines the winner alphabetically."""
        from src.odoo_service.router import route_message

        agents = {
            "z_agent": AgentConfig(
                key="z_agent", name="Z Agent", description="",
                keywords=["shipment"], models=[], default_model="z_model",
            ),
            "a_agent": AgentConfig(
                key="a_agent", name="A Agent", description="",
                keywords=["shipment"], models=[], default_model="a_model",
            ),
        }

        # Both have the same keyword "shipment" — same score
        result = route_message("shipment", agents)

        # a_agent should win because 'a' < 'z'
        assert result.agent_key == "a_agent"
