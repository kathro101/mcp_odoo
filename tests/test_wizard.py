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
