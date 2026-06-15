"""Tests for src/odoo_service/session_store.py — session state management."""

from __future__ import annotations

from datetime import datetime, timezone

from src.shared.types import SessionState


class TestSessionStore:
    """Tests for SessionStore class."""

    def test_get_state_new_session(self):
        """Should return a fresh SessionState for a new session."""
        from src.odoo_service.session_store import SessionStore

        store = SessionStore()
        state = store.get_state("abc123")

        assert isinstance(state, SessionState)
        assert state.session_id == "abc123"
        assert state.current_agent == ""
        assert state.current_model == ""
        assert state.context == {}

    def test_get_state_existing_session(self):
        """Should return the existing state for a known session."""
        from src.odoo_service.session_store import SessionStore

        store = SessionStore()
        store.set_state("abc123", SessionState(session_id="abc123", current_agent="logistics"))

        state = store.get_state("abc123")

        assert state.current_agent == "logistics"

    def test_set_state_stores_values(self):
        """set_state should store and retrieve all fields."""
        from src.odoo_service.session_store import SessionStore

        store = SessionStore()
        store.set_state(
            "xyz",
            SessionState(
                session_id="xyz",
                current_agent="salesman",
                current_model="sale_order",
                pending_operation="create_quotation",
                context={"partner_id": 42},
            ),
        )

        state = store.get_state("xyz")
        assert state.current_agent == "salesman"
        assert state.current_model == "sale_order"
        assert state.pending_operation == "create_quotation"
        assert state.context == {"partner_id": 42}

    def test_get_last_agent_default(self):
        """get_last_agent should return empty string for new session."""
        from src.odoo_service.session_store import SessionStore

        store = SessionStore()
        assert store.get_last_agent("new_session") == ""

    def test_get_last_agent_after_set(self):
        """get_last_agent should return the last set agent."""
        from src.odoo_service.session_store import SessionStore

        store = SessionStore()
        store.set_last_agent("sess1", "logistics")
        assert store.get_last_agent("sess1") == "logistics"

    def test_set_last_agent_updates_existing(self):
        """set_last_agent should update the agent for an existing session."""
        from src.odoo_service.session_store import SessionStore

        store = SessionStore()
        store.set_last_agent("sess1", "logistics")
        store.set_last_agent("sess1", "salesman")
        assert store.get_last_agent("sess1") == "salesman"

    def test_multiple_sessions_independent(self):
        """Sessions should not interfere with each other."""
        from src.odoo_service.session_store import SessionStore

        store = SessionStore()
        store.set_last_agent("sess1", "logistics")
        store.set_last_agent("sess2", "salesman")

        assert store.get_last_agent("sess1") == "logistics"
        assert store.get_last_agent("sess2") == "salesman"

    def test_reset_state(self):
        """reset_state should clear a session's state."""
        from src.odoo_service.session_store import SessionStore

        store = SessionStore()
        store.set_last_agent("sess1", "logistics")
        store.reset_state("sess1")

        assert store.get_last_agent("sess1") == ""

    def test_reset_nonexistent_session(self):
        """reset_state should not error on unknown session."""
        from src.odoo_service.session_store import SessionStore

        store = SessionStore()
        store.reset_state("nonexistent")  # Should not raise

    def test_created_at_is_set(self):
        """SessionState should have a created_at timestamp."""
        from src.odoo_service.session_store import SessionStore

        store = SessionStore()
        state = store.get_state("abc")

        assert state.created_at is not None
        assert isinstance(state.created_at, datetime)
        # Should be recent (within last 5 seconds)
        delta = datetime.now(tz=timezone.utc) - state.created_at
        assert delta.total_seconds() < 5
