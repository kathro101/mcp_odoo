"""Tests for src/odoo_service/odoo_client.py — XML-RPC wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest


class TestOdooClient:
    """Tests for OdooClient class."""

    def test_client_creation_stores_config(self):
        """OdooClient should store connection parameters."""
        from src.odoo_service.odoo_client import OdooClient

        client = OdooClient(
            url="https://example.odoo.com",
            database="testdb",
            username="admin",
            api_key="secret",
        )

        assert client.url == "https://example.odoo.com"
        assert client.database == "testdb"
        assert client.username == "admin"
        assert client.api_key == "secret"

    @patch("xmlrpc.client.ServerProxy")
    def test_execute_kw_calls_odoo(self, mock_server_proxy):
        """execute_kw should delegate to xmlrpc.client with correct params."""
        from src.odoo_service.odoo_client import OdooClient

        mock_object = MagicMock()
        mock_object.execute_kw.return_value = [42]
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1

        def server_proxy_side_effect(url):
            if "common" in url:
                return mock_common
            return mock_object

        mock_server_proxy.side_effect = server_proxy_side_effect

        client = OdooClient("url", "db", "user", "key")

        result = client.execute_kw("res.partner", "search", [[("name", "=", "Test")]])

        assert result == [42]
        mock_object.execute_kw.assert_called_once_with(
            "db", 1, "key", "res.partner", "search", [[("name", "=", "Test")]], {}
        )

    @patch("xmlrpc.client.ServerProxy")
    def test_search_read_calls_odoo(self, mock_server_proxy):
        """search_read should call execute_kw with search_read method."""
        from src.odoo_service.odoo_client import OdooClient

        mock_object = MagicMock()
        mock_object.execute_kw.return_value = [{"id": 1, "name": "Test"}]
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1

        def server_proxy_side_effect(url):
            if "common" in url:
                return mock_common
            return mock_object

        mock_server_proxy.side_effect = server_proxy_side_effect

        client = OdooClient("url", "db", "user", "key")

        result = client.search_read("res.partner", [("name", "=", "Test")], fields=["name"])

        assert result == [{"id": 1, "name": "Test"}]
        mock_object.execute_kw.assert_called_once_with(
            "db", 1, "key", "res.partner", "search_read",
            [[("name", "=", "Test")]], {"fields": ["name"]}
        )

    @patch("xmlrpc.client.ServerProxy")
    def test_fields_get_calls_odoo(self, mock_server_proxy):
        """fields_get should return field metadata."""
        from src.odoo_service.odoo_client import OdooClient

        mock_object = MagicMock()
        mock_object.execute_kw.return_value = {"name": {"type": "char", "string": "Name"}}
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1

        def server_proxy_side_effect(url):
            if "common" in url:
                return mock_common
            return mock_object

        mock_server_proxy.side_effect = server_proxy_side_effect

        client = OdooClient("url", "db", "user", "key")

        result = client.fields_get("res.partner")

        assert result == {"name": {"type": "char", "string": "Name"}}

    @patch("xmlrpc.client.ServerProxy")
    def test_connection_refused_returns_error(self, mock_server_proxy):
        """Should return error dict when Odoo is unreachable."""
        from src.odoo_service.odoo_client import OdooClient

        mock_server_proxy.side_effect = ConnectionRefusedError("Connection refused")

        client = OdooClient("url", "db", "user", "key")
        result = client.execute_kw("res.partner", "search", [[]])

        assert result["status"] == "error"
        assert "Connection refused" in result["message"]

    @patch("xmlrpc.client.ServerProxy")
    def test_xmlrpc_fault_returns_error(self, mock_server_proxy):
        """Should return error dict on xmlrpc.client.Fault."""
        import xmlrpc.client

        from src.odoo_service.odoo_client import OdooClient

        mock_object = MagicMock()
        mock_object.execute_kw.side_effect = xmlrpc.client.Fault(1, "Access Denied")
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1

        def server_proxy_side_effect(url):
            if "common" in url:
                return mock_common
            return mock_object

        mock_server_proxy.side_effect = server_proxy_side_effect

        client = OdooClient("url", "db", "user", "key")

        result = client.execute_kw("res.partner", "read", [[42]])

        assert result["status"] == "error"
        assert "Access Denied" in result["message"]
