"""MCP tool definitions and handlers.

Only 3 tools needed:
- chat_odoo: The main entry point for all user messages
- list_models: Enumerate available Odoo models
- list_agents: Enumerate available agent personas

Handlers are thin — they delegate to the service layer.
No LLM calls in any handler.
"""

from __future__ import annotations

import json

from mcp.types import Tool

from src.odoo_service.router import route_message
from src.odoo_service.schema_store import SchemaStore
from src.odoo_service.session_store import SessionStore
from src.shared.config import load_agents, load_config

# ── Tool Definitions ────────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="chat_odoo",
        description=(
            "Send a message to the Odoo AI agent. ALWAYS use this tool for "
            "user messages about Odoo operations (shipments, sales, invoices, "
            "purchases, etc.). The agent will route the message to the "
            "appropriate specialist."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "The user's message verbatim",
                },
                "session_id": {
                    "type": "string",
                    "description": "Conversation session ID for multi-turn continuity",
                },
            },
            "required": ["message"],
        },
    ),
    Tool(
        name="list_models",
        description=(
            "List all available Odoo models and their fields. Use this to "
            "discover what data is available before constructing a chat_odoo "
            "request."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
    Tool(
        name="list_agents",
        description=(
            "List all available agent personas (logistics, sales, accounting, "
            "purchasing, customer service). Each agent specializes in certain "
            "Odoo operations."
        ),
        inputSchema={"type": "object", "properties": {}},
    ),
]

# ── Lazy-initialized service references ─────────────────────────────────

_schema_store: SchemaStore | None = None
_agents: dict | None = None
_session_store: SessionStore = SessionStore()


def _get_schema_store(config_path: str = "config/config.json") -> SchemaStore:
    global _schema_store
    if _schema_store is None:
        config = load_config(config_path)
        schema_dir = config.get("schema", {}).get("cache_dir", "config/schemas")
        _schema_store = SchemaStore(schema_dir)
    return _schema_store


def _get_agents(agents_path: str = "config/agents.json") -> dict:
    global _agents
    if _agents is None:
        _agents = load_agents(agents_path)
    return _agents


# ── Tool Call Dispatch ──────────────────────────────────────────────────


async def handle_tool_call(name: str, arguments: dict) -> list[dict]:
    """Dispatch a tool call to the appropriate handler.

    Args:
        name: Tool name (chat_odoo, list_models, list_agents).
        arguments: Tool arguments from the MCP client.

    Returns:
        List of content blocks (text or other MCP content types).
    """
    if name == "chat_odoo":
        return await chat_odoo_handler(**arguments)
    elif name == "list_models":
        return await list_models_handler()
    elif name == "list_agents":
        return await list_agents_handler()
    else:
        return [{"type": "text", "text": f"Unknown tool: {name}"}]


# ── Individual Handlers ─────────────────────────────────────────────────


async def chat_odoo_handler(message: str, session_id: str = "") -> list[dict]:
    """Handle chat_odoo: route message, return routing info + available data.

    This handler does NOT call an internal LLM. It routes the message to
    the appropriate agent/schema and returns structured information for
    the MCP client (Claude) to use in formulating a response.
    """
    agents = _get_agents()
    route = route_message(message, agents)

    result_parts: list[str] = []

    if route.agent_key and route.score > 0:
        agent = agents.get(route.agent_key)
        if agent:
            result_parts.append(f"Routed to: {agent.name}")

        if route.model_key:
            try:
                schema = _get_schema_store().get(route.model_key)
                required = schema.required_fields
                create = schema.create_fields
                result_parts.append(f"Model: {schema.label} ({schema.odoo_model})")
                if required:
                    result_parts.append(f"Required fields: {', '.join(required)}")
                if create:
                    result_parts.append(f"Available fields: {', '.join(create[:20])}")
                if schema.summary:
                    result_parts.append(f"Summary: {schema.summary}")
            except KeyError:
                result_parts.append(f"Model: {route.model_key}")

        # Update session state
        if session_id:
            _session_store.set_last_agent(session_id, route.agent_key)

    else:
        result_parts.append(
            "No specific agent matched. Available agents:\n" +
            "\n".join(f"  - {a.name}: {a.description}" for a in agents.values())
        )

    return [{"type": "text", "text": "\n".join(result_parts)}]


async def list_models_handler() -> list[dict]:
    """Handle list_models: return all available model schemas."""
    store = _get_schema_store()
    schemas = store.list_all()

    lines = [f"Available Odoo Models ({len(schemas)}):", ""]
    for schema in sorted(schemas, key=lambda s: s.label):
        lines.append(f"### {schema.label} (`{schema.odoo_model}`)")
        if schema.summary:
            lines.append(f"  {schema.summary}")
        lines.append(f"  Key: `{schema.key}`")
        create_fields = schema.create_fields[:10]
        if create_fields:
            lines.append(f"  Fields: {', '.join(create_fields)}")
        lines.append("")

    return [{"type": "text", "text": "\n".join(lines)}]


async def list_agents_handler() -> list[dict]:
    """Handle list_agents: return all agent personas."""
    agents = _get_agents()

    lines = [f"Available Agents ({len(agents)}):", ""]
    for agent in agents.values():
        lines.append(f"### {agent.name} (`{agent.key}`)")
        lines.append(f"  {agent.description}")
        if agent.keywords:
            lines.append(f"  Keywords: {', '.join(agent.keywords[:10])}")
        if agent.models:
            lines.append(f"  Models: {', '.join(agent.models)}")
        lines.append("")

    return [{"type": "text", "text": "\n".join(lines)}]
