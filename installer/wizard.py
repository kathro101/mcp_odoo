"""Setup wizard for MCP Odoo — Flask-based GUI installer.

Provides API endpoints for:
- Testing Odoo connection
- Saving configuration
- Auto-configuring Claude Desktop
- Running schema discovery

Designed to be packaged with PyInstaller into a macOS .app bundle.
"""

from __future__ import annotations

import json
import logging
import os
import sys
import webbrowser
from pathlib import Path

from flask import Flask, jsonify, render_template_string, request

from src.odoo_service.odoo_client import OdooClient
from src.odoo_service.schema_enrichment import apply_heuristics

logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── Configuration paths ────────────────────────────────────────────────

_config_dir: Path = Path.home() / "Library" / "Application Support" / "MCP Odoo"

_CLAUDE_CONFIG_PATH = (
    Path.home() / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
)

_EXECUTABLE_PATH = Path(
    os.environ.get(
        "MCP_ODOO_EXECUTABLE",
        str(Path(__file__).resolve().parent.parent / "src" / "mcp_server" / "server.py"),
    )
)


def _find_project_root() -> Path:
    """Find the mcp_odoo project root (where src/ and config/ live)."""
    # In PyInstaller bundle, look relative to the executable
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        if (base / "src").is_dir():
            return base
    # In development, look relative to this file
    candidate = Path(__file__).resolve().parent.parent
    if (candidate / "src").is_dir():
        return candidate
    # Fallback
    return Path.cwd()


def _find_template() -> Path | None:
    """Find wizard.html in PyInstaller bundle or development paths."""
    # PyInstaller bundle path
    if getattr(sys, "frozen", False):
        base = Path(sys._MEIPASS)  # type: ignore[attr-defined]
        candidate = base / "installer" / "templates" / "wizard.html"
        if candidate.exists():
            return candidate
        # Fallback: try root of bundle
        candidate = base / "wizard.html"
        if candidate.exists():
            return candidate

    # Development paths
    candidates = [
        Path(__file__).parent / "templates" / "wizard.html",
        Path("installer/templates/wizard.html"),
    ]
    for c in candidates:
        if c.exists():
            return c

    return None


# ── Routes ─────────────────────────────────────────────────────────────


@app.route("/")
def wizard():
    """Serve the setup wizard page."""
    template_path = _find_template()
    if template_path:
        return render_template_string(template_path.read_text())
    return "<h1>Error: wizard.html not found</h1>", 500


@app.route("/api/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


@app.route("/api/list-agents")
def list_agents():
    """List available agent personas."""
    from src.shared.config import load_agents

    agents_path = _find_project_root() / "config" / "agents.json"
    try:
        agents = load_agents(str(agents_path))
        return jsonify(
            {
                "status": "ok",
                "agents": {
                    k: {"name": a.name, "description": a.description} for k, a in agents.items()
                },
            }
        )
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


@app.route("/api/test-connection", methods=["POST"])
def test_connection():
    """Test Odoo connection with provided credentials."""
    data = request.get_json(silent=True) or {}
    # Accept both 'password' and 'api_key' keys
    if "password" in data and "api_key" not in data:
        data["api_key"] = data["password"]
    required = ["url", "database", "username", "api_key"]
    missing = [f for f in required if not data.get(f)]

    if missing:
        return (
            jsonify({"status": "error", "message": f"Missing fields: {missing}"}),
            400,
        )

    try:
        client = OdooClient(
            url=data["url"],
            database=data["database"],
            username=data["username"],
            api_key=data["api_key"],
        )
        client._authenticate()
        return jsonify({"status": "ok", "message": "Connected successfully!"})
    except Exception as exc:
        return jsonify({"status": "error", "message": str(exc)})


@app.route("/api/save-config", methods=["POST"])
def save_config():
    """Save config.json from wizard input."""
    data = request.get_json(silent=True) or {}
    required = ["url", "database", "username", "api_key"]
    missing = [f for f in required if not data.get(f)]

    if missing:
        return (
            jsonify({"status": "error", "message": f"Missing fields: {missing}"}),
            400,
        )

    config = {
        "odoo": {
            "url": data["url"],
            "database": data["database"],
            "username": data["username"],
            "api_key": data["api_key"],
        },
        "mcp": {"transport": "stdio"},
        "schema": {"cache_dir": str(_config_dir / "schemas")},
    }

    try:
        _config_dir.mkdir(parents=True, exist_ok=True)
        config_path = _config_dir / "config.json"
        config_path.write_text(json.dumps(config, indent=2))
        return jsonify({"status": "ok", "path": str(config_path)})
    except OSError as exc:
        return jsonify({"status": "error", "message": str(exc)})


@app.route("/api/configure-claude", methods=["POST"])
def configure_claude():
    """Add MCP Odoo entry to Claude Desktop config.

    Merges with existing config if present. Creates a backup
    of the existing config before writing.

    Uses sys.executable (the Python running THIS wizard) as the
    Claude Desktop command — this ensures the same Python with
    all installed packages (mcp, etc.) is used.
    """
    try:
        existing: dict = {"mcpServers": {}}
        claude_dir = _CLAUDE_CONFIG_PATH.parent
        claude_dir.mkdir(parents=True, exist_ok=True)

        if _CLAUDE_CONFIG_PATH.exists():
            existing = json.loads(_CLAUDE_CONFIG_PATH.read_text())
            # Backup
            backup_path = _CLAUDE_CONFIG_PATH.with_suffix(".json.bak")
            backup_path.write_text(_CLAUDE_CONFIG_PATH.read_text())

        if "mcpServers" not in existing:
            existing["mcpServers"] = {}

        # Use the Python that's running RIGHT NOW — it has all needed packages
        python_cmd = sys.executable
        project_root = _find_project_root()
        if str(project_root) == "/":
            project_root = Path.home()

        existing["mcpServers"]["odoo"] = {
            "command": python_cmd,
            "args": ["-m", "src.mcp_server.server"],
            "cwd": str(project_root),
            "env": {
                "PYTHONPATH": str(project_root),
            },
        }

        _CLAUDE_CONFIG_PATH.write_text(json.dumps(existing, indent=2))

        return jsonify(
            {
                "status": "ok",
                "message": "Claude Desktop configured! Restart Claude to use the Odoo tools.",
                "path": str(_CLAUDE_CONFIG_PATH),
            }
        )
    except OSError as exc:
        return jsonify({"status": "error", "message": str(exc)})


@app.route("/api/discover-schemas", methods=["POST"])
def discover_schemas():
    """Run schema discovery against the configured Odoo instance.

    Streams progress via Server-Sent Events so the frontend can
    show real-time model discovery progress.
    """
    from flask import Response

    config_path = _config_dir / "config.json"
    if not config_path.exists():
        return jsonify({"status": "error", "message": "Save config first"}), 400

    def generate():
        try:
            from src.odoo_service.schema_discovery import SchemaDiscovery
            from src.shared.config import load_config

            cfg = load_config(str(config_path))
            odoo = OdooClient(
                url=cfg["odoo"]["url"],
                database=cfg["odoo"]["database"],
                username=cfg["odoo"]["username"],
                api_key=cfg["odoo"]["api_key"],
            )

            discovery = SchemaDiscovery(odoo, cache_dir=str(_config_dir / "schemas"))

            # Yield progress as models are discovered
            modules = discovery._list_installed_modules()
            models = discovery._filter_user_facing_models(modules)
            total = len(models)

            yield f"data: {json.dumps({'event': 'start', 'total': total})}\n\n"

            schemas = {}
            for i, (model_name, label) in enumerate(models):
                try:
                    schema = discovery.discover_model(model_name, label)
                    schemas[model_name] = schema
                    progress = {
                        "event": "progress",
                        "current": i + 1,
                        "total": total,
                        "model": model_name,
                        "label": label,
                    }
                    yield f"data: {json.dumps(progress)}\n\n"
                except Exception as exc:
                    skip = {
                        "event": "skip",
                        "current": i + 1,
                        "total": total,
                        "model": model_name,
                        "error": str(exc)[:100],
                    }
                    yield f"data: {json.dumps(skip)}\n\n"

            # Apply deterministic heuristics (promote important fields, add hints)
            apply_heuristics(schemas)

            # Save
            discovery.cache_dir.mkdir(parents=True, exist_ok=True)
            discovery._save_schemas(schemas)

            done = {
                "event": "done",
                "count": len(schemas),
                "models": list(schemas.keys())[:10],
            }
            yield f"data: {json.dumps(done)}\n\n"

        except Exception as exc:
            logger.exception("Schema discovery failed")
            yield f"data: {json.dumps({'event': 'error', 'message': str(exc)})}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.route("/api/open-webui", methods=["POST"])
def open_webui():
    """Launch the web UI in the default browser."""
    port = int(os.environ.get("PORT", "5000"))
    webbrowser.open(f"http://127.0.0.1:{port}")
    return jsonify({"status": "ok"})


# ── Entry point ────────────────────────────────────────────────────────


def main():
    """Run the setup wizard, or if -m src.mcp_server.server is passed,
    act as the MCP server entry point (for DMG-built Claude Desktop config).

    In a PyInstaller bundle, sys.executable points to THIS binary.
    Claude Desktop will call this binary with -m src.mcp_server.server.
    We detect the -m flag and route to the MCP server instead of Flask.
    """
    # ── MCP Server mode: -m src.mcp_server.server ──────────────────────
    if "-m" in sys.argv and "src.mcp_server.server" in sys.argv:
        import asyncio

        # Suppress Flask banner and other stdout noise for MCP protocol
        import logging as _logging

        _logging.getLogger("werkzeug").setLevel(_logging.ERROR)

        from mcp.server.stdio import stdio_server

        from src.mcp_server.server import server

        async def _run_mcp():
            async with stdio_server() as (read_stream, write_stream):
                await server.run(read_stream, write_stream, server.create_initialization_options())

        asyncio.run(_run_mcp())
        return

    # ── Wizard mode: start Flask and open browser ─────────────────────
    import subprocess
    import threading
    import time

    port = int(os.environ.get("PORT", "8080"))
    url = f"http://127.0.0.1:{port}"

    def open_browser():
        """Wait for Flask, then try multiple ways to open the browser."""
        time.sleep(2.0)
        # Try multiple approaches in order
        for cmd in [
            ["open", url],
            ["/usr/bin/open", url],
        ]:
            try:
                subprocess.run(cmd, timeout=5, capture_output=True)
                return
            except Exception:
                continue
        # Last resort: write URL to a file the user can click
        url_file = Path.home() / "Desktop" / "MCP Odoo Setup.url"
        url_file.write_text(f"[InternetShortcut]\nURL={url}\n")

    threading.Thread(target=open_browser, daemon=True).start()
    app.run(host="127.0.0.1", port=port, debug=False)


if __name__ == "__main__":
    main()
