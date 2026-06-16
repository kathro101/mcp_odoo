"""Service locator — singleton access to shared services.

Provides lazy-initialized singletons for SchemaStore, agents config,
SessionStore, and OdooClient.  Used by both the MCP server (tools.py)
and the web UI (webapp.py).

All paths are resolved relative to the project root, which is:
- In dev: Path(__file__).resolve().parent.parent.parent
- In PyInstaller DMG: sys._MEIPASS (the unpacked .app bundle)
This ensures the server works regardless of cwd.
"""

from __future__ import annotations

import sys
from pathlib import Path

from src.odoo_service.odoo_client import OdooClient
from src.odoo_service.schema_store import SchemaStore
from src.odoo_service.session_store import SessionStore
from src.shared.config import load_agents, load_config

# ── Project root (resolved once, works regardless of cwd or PyInstaller) ──

if getattr(sys, "frozen", False):
    # PyInstaller bundle: all files under sys._MEIPASS
    _project_root = Path(sys._MEIPASS)  # type: ignore[attr-defined]
else:
    # Development: resolve from this file's location
    _project_root = Path(__file__).resolve().parent.parent.parent

# ── Singletons ─────────────────────────────────────────────────────────

_schema_store: SchemaStore | None = None
_agents: dict | None = None
_session_store: SessionStore | None = None
_odoo_client: OdooClient | None = None


def get_schema_store() -> SchemaStore:
    """Get the SchemaStore singleton.

    Loads schemas from config/schemas/ (or from config if available).
    Gracefully falls back to user's Application Support directory
    when schemas were discovered via the DMG wizard.
    """
    global _schema_store
    if _schema_store is None:
        schema_dir = str(_project_root / "config" / "schemas")
        try:
            config = load_config(str(_project_root / "config" / "config.json"))
            configured = config.get("schema", {}).get("cache_dir", "")
            if configured:
                # Resolve relative paths against project root
                configured_path = Path(configured)
                if not configured_path.is_absolute():
                    configured_path = _project_root / configured_path
                schema_dir = str(configured_path)
        except FileNotFoundError:
            pass
        _schema_store = SchemaStore(schema_dir)
        # Also merge schemas from the DMG wizard's save location
        user_schemas = Path.home() / "Library" / "Application Support" / "MCP Odoo" / "schemas"
        if user_schemas.is_dir():
            try:
                user_store = SchemaStore(str(user_schemas))
                existing_keys = {s.key for s in _schema_store.list_all()}
                for s in user_store.list_all():
                    if s.key not in existing_keys:
                        _schema_store._schemas[s.key] = s
            except Exception:
                pass
    return _schema_store


def get_agents(agents_path: str | None = None) -> dict:
    """Get the agents configuration singleton."""
    global _agents
    if _agents is None:
        if agents_path is None:
            agents_path = str(_project_root / "config" / "agents.json")
        _agents = load_agents(agents_path)
    return _agents


def get_session_store() -> SessionStore:
    """Get the SessionStore singleton."""
    global _session_store
    if _session_store is None:
        _session_store = SessionStore()
    return _session_store


def get_odoo_client() -> OdooClient:
    """Get the OdooClient singleton.

    Validates that Odoo URL is configured before creating the client.
    Raises RuntimeError with a clear message if config is missing or
    incomplete.
    """
    global _odoo_client
    if _odoo_client is None:
        try:
            cfg = load_config(str(_project_root / "config" / "config.json"))
        except FileNotFoundError:
            raise RuntimeError(
                "Odoo not configured. Create config/config.json first. "
                "Copy from config/config.template.json and fill in your Odoo credentials."
            ) from None
        odoo_cfg = cfg.get("odoo", {})
        if not odoo_cfg.get("url"):
            raise RuntimeError("Odoo URL not set. Edit config/config.json and add your Odoo URL.")
        _odoo_client = OdooClient(
            url=odoo_cfg["url"],
            database=odoo_cfg.get("database", ""),
            username=odoo_cfg.get("username", ""),
            api_key=odoo_cfg.get("api_key", ""),
        )
    return _odoo_client
