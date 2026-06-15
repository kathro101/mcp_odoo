"""Tests for src/shared/types.py — all dataclasses."""

from __future__ import annotations

from datetime import datetime


class TestFieldInfo:
    """Tests for FieldInfo dataclass."""

    def test_field_info_creation_defaults(self):
        """FieldInfo should create with sensible defaults."""
        from src.shared.types import FieldInfo

        fi = FieldInfo(name="test_field", field_type="char", string="Test Field")

        assert fi.name == "test_field"
        assert fi.field_type == "char"
        assert fi.string == "Test Field"
        assert fi.required is False
        assert fi.readonly is False
        assert fi.store is True
        assert fi.computed is False
        assert fi.related == ""
        assert fi.relation == ""
        assert fi.selection == []
        assert fi.depends == []
        assert fi.usage_frequency == 0

    def test_field_info_with_computed_flags(self):
        """FieldInfo should accept computed/related/depends."""
        from src.shared.types import FieldInfo

        fi = FieldInfo(
            name="display_name",
            field_type="char",
            string="Display Name",
            computed=True,
            store=False,
            depends=["name", "email"],
        )

        assert fi.computed is True
        assert fi.store is False
        assert fi.depends == ["name", "email"]

    def test_field_info_with_selection(self):
        """FieldInfo should accept selection options."""
        from src.shared.types import FieldInfo

        fi = FieldInfo(
            name="state",
            field_type="selection",
            string="State",
            selection=[("draft", "Draft"), ("done", "Done")],
            required=True,
        )

        assert fi.selection == [("draft", "Draft"), ("done", "Done")]
        assert fi.required is True


class TestSubModelSchema:
    """Tests for SubModelSchema dataclass."""

    def test_sub_model_schema_creation(self):
        """SubModelSchema should hold related model info."""
        from src.shared.types import SubModelSchema

        sub = SubModelSchema(
            field_name="order_line",
            related_model="sale.order.line",
            relation_field="order_id",
            is_one_to_many=True,
        )

        assert sub.field_name == "order_line"
        assert sub.related_model == "sale.order.line"
        assert sub.relation_field == "order_id"
        assert sub.is_one_to_many is True

    def test_sub_model_schema_defaults(self):
        """SubModelSchema defaults should be sensible."""
        from src.shared.types import SubModelSchema

        sub = SubModelSchema(field_name="partner_id", related_model="res.partner")

        assert sub.relation_field == ""
        assert sub.is_one_to_many is False


class TestModelSchema:
    """Tests for ModelSchema dataclass."""

    def test_model_schema_creation_minimal(self):
        """ModelSchema should create with minimal fields."""
        from src.shared.types import ModelSchema

        schema = ModelSchema(
            key="stock_picking",
            label="Transfers",
            odoo_model="stock.picking",
            all_fields={},
        )

        assert schema.key == "stock_picking"
        assert schema.label == "Transfers"
        assert schema.odoo_model == "stock.picking"
        assert schema.summary == ""
        assert schema.all_fields == {}
        assert schema.create_fields == []
        assert schema.search_fields == []
        assert schema.required_fields == []
        assert schema.field_aliases == {}
        assert schema.match_keywords == []
        assert schema.sub_models == []
        assert schema.usage_frequency_total == 0

    def test_model_schema_with_fields(self):
        """ModelSchema should store and classify fields."""
        from src.shared.types import FieldInfo, ModelSchema

        fields = {
            "name": FieldInfo(
                name="name", field_type="char", string="Name", required=True, usage_frequency=5
            ),
            "date": FieldInfo(name="date", field_type="date", string="Date", usage_frequency=3),
            "internal_note": FieldInfo(
                name="internal_note", field_type="text", string="Internal Note", usage_frequency=0
            ),
        }

        schema = ModelSchema(
            key="test_model",
            label="Test Model",
            odoo_model="test.model",
            all_fields=fields,
            create_fields=["name", "date"],
            search_fields=["name"],
            required_fields=["name"],
            field_aliases={"customer": "partner_id"},
            match_keywords=["test", "model"],
            usage_frequency_total=8,
        )

        assert len(schema.all_fields) == 3
        assert schema.create_fields == ["name", "date"]
        assert schema.search_fields == ["name"]
        assert schema.required_fields == ["name"]
        assert schema.field_aliases == {"customer": "partner_id"}
        assert schema.match_keywords == ["test", "model"]
        assert schema.usage_frequency_total == 8

    def test_model_schema_get_required_fields(self):
        """ModelSchema.required_fields should only list required fields."""
        from src.shared.types import FieldInfo, ModelSchema

        fields = {
            "name": FieldInfo(name="name", field_type="char", string="Name", required=True),
            "email": FieldInfo(name="email", field_type="char", string="Email", required=False),
        }
        schema = ModelSchema(
            key="test",
            label="Test",
            odoo_model="test.model",
            all_fields=fields,
            required_fields=["name"],
        )

        assert schema.required_fields == ["name"]


class TestAgentConfig:
    """Tests for AgentConfig dataclass."""

    def test_agent_config_creation(self):
        """AgentConfig should hold agent metadata."""
        from src.shared.types import AgentConfig

        agent = AgentConfig(
            key="logistics",
            name="Logistics Agent",
            description="Handles shipments and deliveries",
            default_model="stock_picking",
            keywords=["shipment", "delivery", "stock"],
            models=["stock.picking", "stock.move"],
        )

        assert agent.key == "logistics"
        assert agent.name == "Logistics Agent"
        assert agent.description == "Handles shipments and deliveries"
        assert agent.default_model == "stock_picking"
        assert agent.keywords == ["shipment", "delivery", "stock"]
        assert agent.models == ["stock.picking", "stock.move"]

    def test_agent_config_no_default_model(self):
        """AgentConfig default_model can be None for orchestrator."""
        from src.shared.types import AgentConfig

        agent = AgentConfig(
            key="cs",
            name="CS Orchestrator",
            description="Routes requests",
            keywords=["help"],
            models=[],
        )

        assert agent.default_model is None
        assert agent.models == []


class TestSessionState:
    """Tests for SessionState dataclass."""

    def test_session_state_defaults(self):
        """SessionState should initialize with empty defaults."""
        from src.shared.types import SessionState

        state = SessionState()

        assert state.session_id == ""
        assert state.current_agent == ""
        assert state.current_model == ""
        assert state.pending_operation == ""
        assert state.context == {}
        assert state.created_at is not None
        assert isinstance(state.created_at, datetime)

    def test_session_state_with_values(self):
        """SessionState should accept all fields."""
        from src.shared.types import SessionState

        now = datetime.now()
        state = SessionState(
            session_id="abc123",
            current_agent="logistics",
            current_model="stock_picking",
            pending_operation="create_shipment",
            context={"partner_id": 42},
            created_at=now,
        )

        assert state.session_id == "abc123"
        assert state.current_agent == "logistics"
        assert state.current_model == "stock_picking"
        assert state.pending_operation == "create_shipment"
        assert state.context == {"partner_id": 42}
        assert state.created_at is now


class TestRouteResult:
    """Tests for RouteResult dataclass."""

    def test_route_result_match(self):
        """RouteResult should represent a successful route match."""
        from src.shared.types import RouteResult

        result = RouteResult(agent_key="logistics", model_key="stock_picking", score=3)

        assert result.agent_key == "logistics"
        assert result.model_key == "stock_picking"
        assert result.score == 3

    def test_route_result_no_match(self):
        """RouteResult should represent no match found."""
        from src.shared.types import RouteResult

        result = RouteResult(agent_key=None, model_key=None, score=0)

        assert result.agent_key is None
        assert result.model_key is None
        assert result.score == 0
