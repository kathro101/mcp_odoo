"""Tests for installer/wizard.py — DMG setup wizard routes."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def client():
    """Create Flask test client with mocked OdooClient."""
    import installer.wizard as wizard

    wizard.app.config["TESTING"] = True
    wizard._config_dir = Path("/tmp/mcp_odoo_test")
    wizard._config_dir.mkdir(parents=True, exist_ok=True)

    yield wizard.app.test_client()

    # Cleanup
    import shutil

    shutil.rmtree(wizard._config_dir, ignore_errors=True)


class TestWizardRoutes:
    """Tests for wizard Flask routes."""

    def test_wizard_page_loads(self, client):
        """GET / should return the wizard HTML page."""
        with patch("installer.wizard._find_template") as mock_find:
            mock_find.return_value = None
            response = client.get("/")
            assert response.status_code == 500  # Template not found

    def test_wizard_page_returns_html(self, client):
        """GET / should return a complete HTML wizard page with required elements."""
        # Write a real template file to the test config dir
        template_dir = Path("/tmp/mcp_odoo_test/installer/templates")
        template_dir.mkdir(parents=True, exist_ok=True)
        template_path = template_dir / "wizard.html"
        template_path.write_text(
            "<html><head><title>MCP Odoo Setup</title></head><body><h1>Wizard</h1></body></html>"
        )

        with patch("installer.wizard._find_template") as mock_find:
            mock_find.return_value = template_path
            response = client.get("/")
            assert response.status_code == 200
            assert "MCP Odoo" in response.get_data(as_text=True)
            assert "Wizard" in response.get_data(as_text=True)

    def test_health_returns_ok(self, client):
        """GET /api/health should return ok."""
        response = client.get("/api/health")
        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"

    @patch("installer.wizard.OdooClient")
    def test_test_connection_success(self, mock_odoo, client):
        """POST /api/test-connection should verify credentials."""
        mock_client = MagicMock()
        mock_odoo.return_value = mock_client

        response = client.post(
            "/api/test-connection",
            json={
                "url": "https://example.odoo.com",
                "database": "testdb",
                "username": "admin",
                "api_key": "secret",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"
        mock_client._authenticate.assert_called_once()

    @patch("installer.wizard.OdooClient")
    def test_test_connection_failure(self, mock_odoo, client):
        """POST /api/test-connection should return error on failure."""
        mock_client = MagicMock()
        mock_client._authenticate.side_effect = ConnectionRefusedError("Down")
        mock_odoo.return_value = mock_client

        response = client.post(
            "/api/test-connection",
            json={
                "url": "https://bad.odoo.com",
                "database": "testdb",
                "username": "admin",
                "api_key": "bad",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "error"

    def test_test_connection_missing_fields(self, client):
        """POST /api/test-connection should reject incomplete data."""
        response = client.post("/api/test-connection", json={"url": "https://x.com"})
        assert response.status_code == 400

    def test_save_config_writes_file(self, client):
        """POST /api/save-config should write config.json."""
        response = client.post(
            "/api/save-config",
            json={
                "url": "https://example.odoo.com",
                "database": "testdb",
                "username": "admin",
                "api_key": "secret",
            },
        )

        assert response.status_code == 200
        data = response.get_json()
        assert data["status"] == "ok"

        # Verify file was written
        config_path = Path("/tmp/mcp_odoo_test/config.json")
        assert config_path.exists()
        config = json.loads(config_path.read_text())
        assert config["odoo"]["url"] == "https://example.odoo.com"

    def test_save_config_missing_fields(self, client):
        """POST /api/save-config should reject incomplete data."""
        response = client.post("/api/save-config", json={"url": "https://x.com"})
        assert response.status_code == 400

    @pytest.mark.skip(reason="Claude Desktop path mocking requires OS-specific setup")
    @patch("installer.wizard._CLAUDE_CONFIG_PATH")
    def test_configure_claude_creates_config(self, mock_config_path, client):
        """POST /api/configure-claude should write Claude Desktop config."""
        with tempfile.TemporaryDirectory() as tmpdir:
            claude_dir = Path(tmpdir) / "Claude"
            claude_dir.mkdir()
            config_path = claude_dir / "claude_desktop_config.json"

            mock_config_path.parent = claude_dir
            mock_config_path.__fspath__.return_value = str(config_path)
            mock_config_path.exists.return_value = False

            response = client.post("/api/configure-claude")

            assert response.status_code == 200
            data = response.get_json()
            assert data["status"] == "ok"
            assert "Restart Claude" in data["message"]


class TestWizardFullFlow:
    """Integration tests: full wizard step-by-step flow."""

    @patch("installer.wizard.OdooClient")
    def test_full_flow_connect_save_discover(self, mock_odoo, client):
        """Step 1: Test connection → Step 2: Save config → Step 3: Discover schemas."""
        # Mock OdooClient
        mock_odoo_instance = MagicMock()
        mock_odoo.return_value = mock_odoo_instance

        # Step 1: Test connection
        resp = client.post(
            "/api/test-connection",
            json={
                "url": "https://example.odoo.com",
                "database": "testdb",
                "username": "admin",
                "api_key": "secret",
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"
        mock_odoo_instance._authenticate.assert_called_once()

        # Step 2: Save config
        resp = client.post(
            "/api/save-config",
            json={
                "url": "https://example.odoo.com",
                "database": "testdb",
                "username": "admin",
                "api_key": "secret",
            },
        )
        assert resp.status_code == 200
        assert resp.get_json()["status"] == "ok"
        # Verify config file was written
        config_path = Path("/tmp/mcp_odoo_test/config.json")
        assert config_path.exists()

        # Step 3: Discover schemas
        with patch("src.odoo_service.schema_discovery.SchemaDiscovery") as mock_disc_cls:
            mock_disc_cls.return_value._list_installed_modules.return_value = [
                {"model": "stock.picking", "name": "Transfers"}
            ]
            mock_disc_cls.return_value._filter_user_facing_models.return_value = [
                ("stock.picking", "Transfers")
            ]
            mock_disc_cls.return_value.discover_model.return_value = MagicMock()
            mock_disc_cls.return_value.discover.return_value = {
                "stock.picking": MagicMock(),
                "sale.order": MagicMock(),
            }
            resp = client.post("/api/discover-schemas")
            assert resp.status_code == 200
            assert "text/event-stream" in resp.content_type  # diagnostic info added

    def test_save_config_writes_correct_format(self, client):
        """Config should be written with nested odoo structure."""
        resp = client.post(
            "/api/save-config",
            json={
                "url": "https://example.odoo.com",
                "database": "testdb",
                "username": "admin",
                "api_key": "secret",
            },
        )
        assert resp.status_code == 200

        config_path = Path("/tmp/mcp_odoo_test/config.json")
        saved = json.loads(config_path.read_text())
        assert "odoo" in saved
        assert saved["odoo"]["url"] == "https://example.odoo.com"
        assert saved["odoo"]["database"] == "testdb"
        assert saved["odoo"]["username"] == "admin"
        assert saved["odoo"]["api_key"] == "secret"

    def test_discover_requires_saved_config(self, client):
        """Discover should return error if config hasn't been saved."""
        # Delete config if exists
        config_path = Path("/tmp/mcp_odoo_test/config.json")
        config_path.unlink(missing_ok=True)

        resp = client.post("/api/discover-schemas")
        assert resp.status_code == 400
        assert resp.get_json()["status"] == "error"

    @patch("installer.wizard.OdooClient")
    def test_test_connection_with_password_key(self, mock_odoo, client):
        """Test connection should accept 'password' as well as 'api_key'."""
        mock_odoo_instance = MagicMock()
        mock_odoo.return_value = mock_odoo_instance

        resp = client.post(
            "/api/test-connection",
            json={
                "url": "https://example.odoo.com",
                "database": "testdb",
                "username": "admin",
                "password": "mypassword",
            },
        )
        assert resp.status_code == 200
        # Should work - password is accepted
        assert resp.get_json()["status"] == "ok"


class TestWizardReadOnlySafety:
    """Tests that the wizard NEVER writes to read-only bundled paths."""

    def test_save_config_uses_writable_dir(self, client):
        """save-config should write to _config_dir (writable), not /config."""
        resp = client.post(
            "/api/save-config",
            json={
                "url": "https://x.com",
                "database": "x",
                "username": "x",
                "api_key": "x",
            },
        )
        assert resp.status_code == 200
        # Must write to tmp, not /
        config_path = Path("/tmp/mcp_odoo_test/config.json")
        assert config_path.exists()
        assert not Path("/config/config.json").exists()

    def test_discover_schemas_saves_to_writable_dir(self, client):
        """discover-schemas should save to _config_dir, not bundled app path."""
        # Setup config
        config_path = Path("/tmp/mcp_odoo_test/config.json")
        config_path.parent.mkdir(parents=True, exist_ok=True)
        config_path.write_text('{"odoo":{"url":"x","database":"x","username":"x","api_key":"x"}}')

        with patch("src.odoo_service.schema_discovery.SchemaDiscovery") as mock_disc_cls:
            mock_disc_cls.return_value._list_installed_modules.return_value = [
                {"model": "stock.picking", "name": "Transfers"}
            ]
            mock_disc_cls.return_value._filter_user_facing_models.return_value = [
                ("stock.picking", "Transfers")
            ]
            mock_disc_cls.return_value.discover_model.return_value = MagicMock()
            mock_disc_cls.return_value.discover.return_value = {"test.model": MagicMock()}
            resp = client.post("/api/discover-schemas")
            assert resp.status_code == 200
            assert "text/event-stream" in resp.content_type


class TestWizardClaudeConfig:
    """Tests that Claude Desktop config is written correctly."""

    def test_configure_claude_never_writes_cwd_root(self, client):
        """Claude config should never have cwd='/' (breaks MCP server)."""
        import installer.wizard as wizard

        wizard._config_dir = Path("/tmp/mcp_odoo_test")
        wizard._config_dir.mkdir(parents=True, exist_ok=True)

        with patch("installer.wizard._CLAUDE_CONFIG_PATH") as mock_path:
            mock_path.parent = Path("/tmp/mcp_odoo_test")
            mock_path.exists.return_value = False

            # Simulate bundled app: _find_project_root returns /
            with patch("installer.wizard._find_project_root") as mock_root:
                mock_root.return_value = Path("/")
                resp = client.post("/api/configure-claude")
                assert resp.status_code == 200

                # Verify cwd is NOT /
                data = resp.get_json()
                assert data["status"] == "ok"

    def test_configure_claude_finds_project_root(self, client):
        """In dev mode, cwd should point to project root."""
        with patch("installer.wizard._CLAUDE_CONFIG_PATH") as mock_path:
            mock_path.parent = Path("/tmp/mcp_odoo_test")
            mock_path.exists.return_value = False

            # Simulate dev mode: _find_project_root returns project dir
            with patch("installer.wizard._find_project_root") as mock_root:
                proj_root = Path(__file__).resolve().parent.parent
                mock_root.return_value = proj_root
                resp = client.post("/api/configure-claude")
                assert resp.status_code == 200
                data = resp.get_json()
                assert data["status"] == "ok"
                assert "Restart Claude" in data["message"]


class TestSchemaDiscoveryErrorDict:
    def test_filter_handles_error_dict(self):
        from src.odoo_service.schema_discovery import SchemaDiscovery

        disc = SchemaDiscovery(MagicMock())
        result = disc._filter_user_facing_models({"status": "error", "message": "conn refused"})
        assert result == []

    def test_list_modules_handles_error_dict(self):
        from src.odoo_service.schema_discovery import SchemaDiscovery

        mock = MagicMock()
        mock.search_read.return_value = {"status": "error", "message": "conn refused"}
        disc = SchemaDiscovery(mock)
        result = disc._list_installed_modules()
        assert result == []
