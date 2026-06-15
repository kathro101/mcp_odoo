"""Tests for src/shared/config.py — configuration loader."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest


class TestLoadConfig:
    """Tests for load_config()."""

    def test_load_config_valid_json(self):
        """Should load and parse a valid JSON config file."""
        from src.shared.config import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "odoo": {
                        "url": "https://example.odoo.com",
                        "database": "testdb",
                        "username": "admin",
                        "api_key": "secret",
                    },
                    "mcp": {"transport": "stdio", "http_port": 8080},
                    "schema": {"cache_dir": "config/schemas", "enrichment": {"enabled": True}},
                },
                f,
            )
            temp_path = f.name

        try:
            config = load_config(temp_path)
            assert config["odoo"]["url"] == "https://example.odoo.com"
            assert config["odoo"]["database"] == "testdb"
            assert config["mcp"]["transport"] == "stdio"
        finally:
            Path(temp_path).unlink()

    def test_load_config_file_not_found(self):
        """Should raise FileNotFoundError for missing config file."""
        from src.shared.config import load_config

        with pytest.raises(FileNotFoundError):
            load_config("/nonexistent/path/config.json")

    def test_load_config_invalid_json(self):
        """Should raise ValueError for malformed JSON."""
        from src.shared.config import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            f.write("{invalid json")
            temp_path = f.name

        try:
            with pytest.raises(ValueError):
                load_config(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_config_missing_odoo_section(self):
        """Should raise ValueError when odoo section is absent."""
        from src.shared.config import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"mcp": {"transport": "stdio"}}, f)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="odoo"):
                load_config(temp_path)
        finally:
            Path(temp_path).unlink()

    def test_load_config_empty_url(self):
        """Should raise ValueError when odoo.url is empty."""
        from src.shared.config import load_config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({"odoo": {"url": "", "database": "db", "username": "u", "api_key": "k"}}, f)
            temp_path = f.name

        try:
            with pytest.raises(ValueError, match="url"):
                load_config(temp_path)
        finally:
            Path(temp_path).unlink()


class TestLoadAgents:
    """Tests for load_agents()."""

    def test_load_agents_valid(self):
        """Should load agents from a valid agents.json file."""
        from src.shared.config import load_agents

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump(
                {
                    "logistics": {
                        "key": "logistics",
                        "name": "Logistics Agent",
                        "description": "Handles shipments",
                        "keywords": ["shipment", "delivery"],
                        "models": ["stock.picking"],
                    },
                },
                f,
            )
            temp_path = f.name

        try:
            agents = load_agents(temp_path)
            assert "logistics" in agents
            assert agents["logistics"].key == "logistics"
            assert agents["logistics"].name == "Logistics Agent"
            assert agents["logistics"].keywords == ["shipment", "delivery"]
            assert agents["logistics"].default_model == "stock.picking"
        finally:
            Path(temp_path).unlink()

    def test_load_agents_file_not_found(self):
        """Should raise FileNotFoundError when agents file missing."""
        from src.shared.config import load_agents

        with pytest.raises(FileNotFoundError):
            load_agents("/nonexistent/agents.json")

    def test_load_agents_empty(self):
        """Should handle empty agents dict gracefully."""
        from src.shared.config import load_agents

        with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
            json.dump({}, f)
            temp_path = f.name

        try:
            agents = load_agents(temp_path)
            assert agents == {}
        finally:
            Path(temp_path).unlink()
