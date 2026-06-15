"""Tests for src/odoo_service/service_locator.py."""

from __future__ import annotations

from unittest.mock import patch

import pytest


class TestGetSchemaStore:
    """Tests for get_schema_store()."""

    def test_returns_singleton(self):
        """Multiple calls should return the same instance."""
        from src.odoo_service.service_locator import get_schema_store

        s1 = get_schema_store()
        s2 = get_schema_store()

        assert s1 is s2

    @patch("src.odoo_service.service_locator.load_config")
    def test_falls_back_when_config_missing(self, mock_load):
        """Should use default path when config.json doesn't exist."""
        # Reset singleton
        import src.odoo_service.service_locator as sl
        from src.odoo_service.service_locator import (
            get_schema_store,
        )

        sl._schema_store = None

        mock_load.side_effect = FileNotFoundError()

        store = get_schema_store()
        assert store is not None
        # Reset after test
        sl._schema_store = None


class TestGetOdooClient:
    """Tests for get_odoo_client()."""

    @patch("src.odoo_service.service_locator.load_config")
    def test_raises_when_config_missing(self, mock_load):
        """Should raise RuntimeError when config.json doesn't exist."""
        import src.odoo_service.service_locator as sl
        from src.odoo_service.service_locator import get_odoo_client

        sl._odoo_client = None

        mock_load.side_effect = FileNotFoundError()

        with pytest.raises(RuntimeError, match="not configured"):
            get_odoo_client()

        sl._odoo_client = None

    @patch("src.odoo_service.service_locator.load_config")
    def test_raises_when_url_empty(self, mock_load):
        """Should raise RuntimeError when odoo.url is empty."""
        import src.odoo_service.service_locator as sl
        from src.odoo_service.service_locator import get_odoo_client

        sl._odoo_client = None

        mock_load.return_value = {"odoo": {"url": ""}}

        with pytest.raises(RuntimeError, match="URL not set"):
            get_odoo_client()

        sl._odoo_client = None


class TestGetAgents:
    """Tests for get_agents()."""

    def test_returns_singleton(self):
        """Multiple calls should return the same dict."""
        import src.odoo_service.service_locator as sl
        from src.odoo_service.service_locator import get_agents

        sl._agents = None

        a1 = get_agents()
        a2 = get_agents()

        assert a1 is a2
        # Reset
        sl._agents = None


class TestGetSessionStore:
    """Tests for get_session_store()."""

    def test_returns_singleton(self):
        """Multiple calls should return the same instance."""
        from src.odoo_service.service_locator import get_session_store

        s1 = get_session_store()
        s2 = get_session_store()

        assert s1 is s2
