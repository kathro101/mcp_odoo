"""MCP tool definitions and handlers.

Tools:
- chat_odoo: Smart router — routes messages, returns rich schema data,
  and executes actions (preview, create, search, update, delete).
- list_models: Enumerate available Odoo models.
- list_agents: Enumerate available agent personas.

Handlers delegate to the service layer. No LLM calls.
"""

from __future__ import annotations

import json

from mcp.types import Tool

from src.odoo_service.router import route_message
from src.odoo_service.schema_store import SchemaStore
from src.odoo_service.session_store import SessionStore
from src.operations.create import create_record, preview_record
from src.operations.delete import confirm_delete, delete_record
from src.operations.search import search_records
from src.operations.update import preview_update, update_record
from src.shared.config import load_agents, load_config

# ── Tool Definitions ────────────────────────────────────────────────────

TOOLS: list[Tool] = [
    Tool(
        name="chat_odoo",
        description=(
            "THE main tool for all Odoo interactions. Two modes:\n\n"
            "1. ROUTING MODE (message= set): Send user message → returns "
            "routing info + detailed schema with field_aliases, selection "
            "options, and required fields. Use field_aliases to map user "
            "words to field names (e.g., 'customer' → partner_id).\n\n"
            "2. ACTION MODE (action= set): Execute operations directly.\n"
            "   - action='preview': Validate params against schema, return "
            "what's missing. ALWAYS preview before creating.\n"
            "   - action='search': Search records by field values.\n"
            "   - action='update': Update an existing record.\n"
            "   - action='delete': Delete a record (returns confirmation)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "User's message — triggers routing mode",
                },
                "action": {
                    "type": "string",
                    "description": "Action to execute: preview, search, update, delete",
                },
                "model": {
                    "type": "string",
                    "description": "Odoo model key (e.g., stock_picking). Required for action mode.",
                },
                "params": {
                    "type": "object",
                    "description": "Field values as {field_name: value}. Use aliases from routing mode.",
                },
                "record_id": {
                    "type": "integer",
                    "description": "Record ID for update/delete actions.",
                },
                "session_id": {
                    "type": "string",
                    "description": "Conversation session ID for multi-turn continuity",
                },
            },
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
    """Dispatch a tool call to the appropriate handler."""
    if name == "chat_odoo":
        return await chat_odoo_handler(**arguments)
    elif name == "list_models":
        return await list_models_handler()
    elif name == "list_agents":
        return await list_agents_handler()
    else:
        return [{"type": "text", "text": f"Unknown tool: {name}"}]


# ── chat_odoo Handler ──────────────────────────────────────────────────


async def chat_odoo_handler(
    message: str = "",
    action: str = "",
    model: str = "",
    params: dict | None = None,
    record_id: int = 0,
    session_id: str = "",
) -> list[dict]:
    """Two-mode handler: routing (message) or action execution.

    ROUTING MODE (message is set):
        Routes the message to an agent, returns enriched schema data
        including field_aliases, types, selection options, and sub-models.

    ACTION MODE (action is set):
        Executes the specified operation directly.
        - preview: Validates params, returns what's provided vs missing.
        - search: Searches records by field values.
        - update: Updates an existing record.
        - delete: Confirms then deletes a record.
    """
    # ── ACTION MODE ──────────────────────────────────────────────────
    if action:
        return await _handle_action(action, model, params or {}, record_id)

    # ── ROUTING MODE ─────────────────────────────────────────────────
    if not message.strip():
        return [{"type": "text", "text": "Please provide a message or an action."}]

    agents = _get_agents()
    route = route_message(message, agents)
    parts: list[str] = []

    if route.agent_key and route.score > 0:
        agent = agents.get(route.agent_key)
        if agent:
            parts.append(f"## Routed to: {agent.name}")

        if route.model_key:
            try:
                schema = _get_schema_store().get(route.model_key)
                parts.extend(_format_schema_for_claude(schema))
            except KeyError:
                parts.append(f"Model: {route.model_key}")

        if session_id:
            _session_store.set_last_agent(session_id, route.agent_key)
    else:
        parts.append("No specific agent matched. Available agents:\n")
        for a in agents.values():
            parts.append(f"- **{a.name}** ({a.key}): {a.description}")

    return [{"type": "text", "text": "\n".join(parts)}]


# ── Action Dispatcher ──────────────────────────────────────────────────


async def _handle_action(
    action: str, model: str, params: dict, record_id: int
) -> list[dict]:
    """Execute an action against an Odoo model."""
    if not model:
        return [{"type": "text", "text": "Error: model is required for actions."}]

    try:
        schema = _get_schema_store().get(model)
    except KeyError:
        return [{"type": "text", "text": f"Unknown model: {model}"}]

    result: dict

    match action:
        case "preview":
            result = preview_record(schema, params)
            result["field_aliases"] = schema.field_aliases
        case "search":
            odoo = _get_odoo_client()
            result = search_records(odoo, schema, params)
        case "update":
            odoo = _get_odoo_client()
            result = update_record(odoo, schema, record_id, params)
        case "delete":
            if record_id:
                odoo = _get_odoo_client()
                result = delete_record(odoo, schema, record_id)
            else:
                result = confirm_delete(schema, params)
        case _:
            return [{"type": "text", "text": f"Unknown action: {action}. "
                      "Valid: preview, search, update, delete."}]

    return [{"type": "text", "text": json.dumps(result, default=str)}]


_odoo_client = None


def _get_odoo_client():
    """Lazy-initialize the OdooClient singleton."""
    global _odoo_client
    if _odoo_client is None:
        from src.odoo_service.odoo_client import OdooClient

        cfg = load_config("config/config.json")
        odoo_cfg = cfg.get("odoo", {})
        _odoo_client = OdooClient(
            url=odoo_cfg.get("url", ""),
            database=odoo_cfg.get("database", ""),
            username=odoo_cfg.get("username", ""),
            api_key=odoo_cfg.get("api_key", ""),
        )
    return _odoo_client


# ── Schema Formatting Helpers ──────────────────────────────────────────


def _format_schema_for_claude(schema) -> list[str]:
    """Format a ModelSchema into Claude-friendly text with aliases + details."""
    lines: list[str] = []

    # Header
    lines.append(f"## Model: {schema.label} (`{schema.odoo_model}`)")
    if schema.summary:
        lines.append(f"{schema.summary}")
    lines.append("")

    # Field aliases (CRITICAL for Claude to map user words → field names)
    if schema.field_aliases:
        lines.append("### FIELD ALIASES")
        lines.append("Map user words to field names using these:")
        seen = set()
        for alias, field in sorted(schema.field_aliases.items()):
            if field not in seen:
                lines.append(f'  "{alias}" → `{field}`')
                seen.add(field)
        lines.append("")

    # Required fields with details
    if schema.required_fields:
        lines.append("### REQUIRED FIELDS")
        for fname in schema.required_fields:
            fi = schema.all_fields.get(fname)
            if fi:
                detail = _format_field_detail(fi)
                lines.append(f"  - {detail}")
        lines.append("")

    # Top optional fields (by usage frequency)
    optional_fields = [
        fn for fn in schema.create_fields
        if fn not in schema.required_fields and fn in schema.all_fields
    ]
    top_fields = sorted(
        optional_fields,
        key=lambda fn: schema.all_fields[fn].usage_frequency,
        reverse=True,
    )[:15]

    if top_fields:
        lines.append(f"### OPTIONAL FIELDS (top {len(top_fields)} by usage)")
        for fname in top_fields:
            fi = schema.all_fields.get(fname)
            if fi:
                detail = _format_field_detail(fi)
                lines.append(f"  - {detail}")
        lines.append("")

    # Sub-models (one-to-many)
    if schema.sub_models:
        lines.append("### SUB-MODELS (one-to-many)")
        for sub in schema.sub_models:
            lines.append(
                f"  - `{sub.field_name}` → {sub.related_model}"
            )
        lines.append("")

    # Match keywords
    if schema.match_keywords:
        lines.append(f"Keywords: {', '.join(schema.match_keywords[:10])}")

    return lines


def _format_field_detail(fi) -> str:
    """Format a single FieldInfo as a human-readable description."""
    parts = [f"`{fi.name}` ({fi.field_type}"]
    if fi.relation:
        parts.append(f" → {fi.relation}")
    parts.append(f"): {fi.string}")

    if fi.selection:
        options = [s[0] for s in fi.selection]
        parts.append(f" [options: {', '.join(options)}]")

    if fi.required:
        parts.append(" *REQUIRED*")
    if fi.computed:
        parts.append(" (computed)")
    if fi.related:
        parts.append(f" (related to {fi.related})")

    return "".join(parts)


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
