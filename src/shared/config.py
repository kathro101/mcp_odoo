"""Configuration loader.

Loads config.json and agents.json.  Flat, simple, no merging logic
(the old 3-layer baseline+discovered+curated merge is gone).
"""

from __future__ import annotations

import json
from pathlib import Path

from .types import AgentConfig


def load_config(path: str) -> dict:
    """Load and validate the main config.json file.

    Args:
        path: Absolute or relative path to config.json.

    Returns:
        Parsed config dict with odoo, mcp, and schema sections.

    Raises:
        FileNotFoundError: If the config file does not exist.
        ValueError: If the JSON is malformed or required sections are missing.
    """
    config_path = Path(path)
    if not config_path.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    try:
        raw = json.loads(config_path.read_text())
    except json.JSONDecodeError as exc:
        raise ValueError(f"Invalid JSON in config file: {path}") from exc

    if "odoo" not in raw:
        raise ValueError("Config missing required 'odoo' section")

    odoo = raw["odoo"]
    if not odoo.get("url"):
        raise ValueError("Config 'odoo.url' is required and must not be empty")

    return raw


def load_agents(path: str) -> dict[str, AgentConfig]:
    """Load agent configurations from agents.json.

    Args:
        path: Path to agents.json.

    Returns:
        Dict mapping agent keys to AgentConfig instances.

    Raises:
        FileNotFoundError: If the agents file does not exist.
    """
    agents_path = Path(path)
    if not agents_path.exists():
        raise FileNotFoundError(f"Agents file not found: {path}")

    raw = json.loads(agents_path.read_text())

    result: dict[str, AgentConfig] = {}
    for key, data in raw.items():
        result[key] = AgentConfig(
            key=data.get("key", key),
            name=data.get("name", key),
            description=data.get("description", ""),
            keywords=data.get("keywords", []),
            models=data.get("models", []),
            default_model=data.get("default_model", data.get("models", [None])[0] if data.get("models") else None),
        )

    return result
