"""Tests for src/odoo_service/odoo_client.py — XML-RPC wrapper."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


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

    def test_authenticate_with_user_agent_env(self):
        """authenticate should pass user_agent_env for Odoo 16+ compatibility."""
        import xmlrpc.client

        from src.odoo_service.odoo_client import OdooClient

        mock_common = MagicMock()
        # First call raises Fault (simulating old Odoo rejecting 4th arg)
        # Second call succeeds (3-arg fallback)
        mock_common.authenticate.side_effect = [
            xmlrpc.client.Fault(1, "missing user_agent_env"),
            1,
        ]
        mock_object = MagicMock()

        with patch("xmlrpc.client.ServerProxy") as mock_proxy:
            mock_proxy.side_effect = (
                lambda url, **kw: mock_common if "common" in url else mock_object
            )
            client = OdooClient("url", "db", "user", "key")
            client._authenticate()

        # Should have been called twice — 4-arg failed, 3-arg succeeded
        assert mock_common.authenticate.call_count == 2

    @patch("xmlrpc.client.ServerProxy")
    def test_execute_kw_calls_odoo(self, mock_server_proxy):
        """execute_kw should delegate to xmlrpc.client with correct params."""
        from src.odoo_service.odoo_client import OdooClient

        mock_object = MagicMock()
        mock_object.execute_kw.return_value = [42]
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1

        def server_proxy_side_effect(url, **kw):
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

        def server_proxy_side_effect(url, **kw):
            if "common" in url:
                return mock_common
            return mock_object

        mock_server_proxy.side_effect = server_proxy_side_effect

        client = OdooClient("url", "db", "user", "key")

        result = client.search_read("res.partner", [("name", "=", "Test")], fields=["name"])

        assert result == [{"id": 1, "name": "Test"}]
        mock_object.execute_kw.assert_called_once_with(
            "db",
            1,
            "key",
            "res.partner",
            "search_read",
            [[("name", "=", "Test")]],
            {"fields": ["name"]},
        )

    @patch("xmlrpc.client.ServerProxy")
    def test_fields_get_calls_odoo(self, mock_server_proxy):
        """fields_get should return field metadata."""
        from src.odoo_service.odoo_client import OdooClient

        mock_object = MagicMock()
        mock_object.execute_kw.return_value = {"name": {"type": "char", "string": "Name"}}
        mock_common = MagicMock()
        mock_common.authenticate.return_value = 1

        def server_proxy_side_effect(url, **kw):
            if "common" in url:
                return mock_common
            return mock_object

        mock_server_proxy.side_effect = server_proxy_side_effect

        client = OdooClient("url", "db", "user", "key")

        result = client.fields_get("res.partner")

        assert result == {"name": {"type": "char", "string": "Name"}}
        # Verify execute_kw was called — allow_none=True changes the call pattern
        mock_object.execute_kw.assert_called()

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

        def server_proxy_side_effect(url, **kw):
            if "common" in url:
                return mock_common
            return mock_object

        mock_server_proxy.side_effect = server_proxy_side_effect

        client = OdooClient("url", "db", "user", "key")

        result = client.execute_kw("res.partner", "read", [[42]])

        assert result["status"] == "error"
        assert "Access Denied" in result["message"]
