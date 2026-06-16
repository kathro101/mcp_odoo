"""MCP Odoo Web UI — Flask chat interface.

Provides a standalone web chat for interacting with the Odoo AI agent.
Routes user messages through the same service layer used by the MCP server.
"""

from __future__ import annotations

import logging

from flask import Flask, jsonify, render_template, request

from src.odoo_service.router import route_message
from src.odoo_service.service_locator import (
    get_agents as _svc_get_agents,
)
from src.odoo_service.service_locator import (
    get_schema_store as _svc_get_schema_store,
)
from src.odoo_service.service_locator import (
    get_session_store as _svc_get_session_store,
)

logger = logging.getLogger(__name__)

app = Flask(__name__)

# ── Lazy service singletons ────────────────────────────────────────────
# All path resolution is delegated to service_locator, which resolves
# paths relative to _project_root (with sys._MEIPASS support for
# PyInstaller DMG builds).


def _get_schema_store():
    """Get the SchemaStore singleton via service_locator."""
    return _svc_get_schema_store()


def _get_agents():
    """Get the agents config dict via service_locator."""
    return _svc_get_agents()


# ── Routes ─────────────────────────────────────────────────────────────


@app.route("/")
def index():
    """Serve the chat interface."""
    return render_template("index.html")


@app.route("/api/health")
def health():
    """Health check endpoint."""
    return jsonify({"status": "ok"})


@app.route("/api/chat", methods=["POST"])
def chat():
    """Handle a chat message.

    Request: {"message": "Create a shipment", "session_id": "abc123"}
    Response: {"status": "success", "agent": "logistics", "model": "stock.picking", ...}
    """
    data = request.get_json(silent=True) or {}
    message = data.get("message", "").strip()
    session_id = data.get("session_id", "")

    if not message:
        return jsonify({"status": "error", "message": "Message is required"}), 400

    agents = _get_agents()
    route = route_message(message, agents)

    result: dict = {
        "status": "success",
        "message": message,
    }

    if route.agent_key and route.score > 0:
        agent = agents.get(route.agent_key)
        result["agent"] = route.agent_key
        result["agent_name"] = agent.name if agent else route.agent_key
        result["model"] = route.model_key

        if route.model_key:
            try:
                schema = _get_schema_store().get(route.model_key)
                result["model_label"] = schema.label
                result["required_fields"] = schema.required_fields
                result["available_fields"] = schema.create_fields[:10]
                if schema.summary:
                    result["model_summary"] = schema.summary
            except KeyError:
                pass

        if session_id:
            _svc_get_session_store().set_last_agent(session_id, route.agent_key)

    else:
        result["status"] = "needs_input"
        result["available_agents"] = [
            {"key": a.key, "name": a.name, "description": a.description} for a in agents.values()
        ]

    return jsonify(result)


@app.route("/api/models")
def list_models_api():
    """List available models."""
    store = _get_schema_store()
    schemas = store.list_all()
    return jsonify(
        [
            {
                "key": s.key,
                "label": s.label,
                "model": s.odoo_model,
                "summary": s.summary,
                "required_fields": s.required_fields,
                "create_fields": s.create_fields,
            }
            for s in sorted(schemas, key=lambda s2: s2.label)
        ]
    )


@app.route("/api/agents")
def list_agents_api():
    """List available agents."""
    agents = _get_agents()
    return jsonify(
        {
            key: {
                "key": a.key,
                "name": a.name,
                "description": a.description,
                "keywords": a.keywords,
                "models": a.models,
            }
            for key, a in agents.items()
        }
    )


# ── Entry point ────────────────────────────────────────────────────────


def main():
    """Run the web app."""
    app.run(host="127.0.0.1", port=5000, debug=True)


if __name__ == "__main__":
    main()
