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
from src.odoo_service.service_locator import (
    get_agents as _svc_get_agents,
)
from src.odoo_service.service_locator import (
    get_odoo_client as _svc_get_odoo_client,
)
from src.odoo_service.service_locator import (
    get_schema_store as _svc_get_schema_store,
)
from src.odoo_service.service_locator import (
    get_session_store as _svc_get_session_store,
)
from src.operations.create import create_record, preview_record
from src.operations.delete import confirm_delete, delete_record
from src.operations.search import search_records
from src.operations.update import update_record

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
            "   - action='create': Create a new record (preview MUST pass first).\n"
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
                    "description": "Action to execute: preview, create, search, update, delete",
                },
                "model": {
                    "type": "string",
                    "description": (
                        "Odoo model key (e.g., stock_picking). Required for action mode."
                    ),
                },
                "params": {
                    "type": "object",
                    "description": (
                        "Field values as {field_name: value}. Use aliases from routing mode."
                    ),
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
            "List available Odoo models. Use this to discover what data "
            "is available. Optionally pass a user message to get models "
            "sorted by relevance to the message (for semantic matching "
            "when the keyword router fails)."
        ),
        inputSchema={
            "type": "object",
            "properties": {
                "message": {
                    "type": "string",
                    "description": "Optional user message for relevance scoring",
                },
            },
        },
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
# All path resolution is delegated to service_locator, which resolves
# paths relative to _project_root (with sys._MEIPASS support for
# PyInstaller DMG builds). This prevents "file not found" errors
# when Claude Desktop spawns the server with a non-project CWD.


def _get_schema_store():
    """Get the SchemaStore singleton via service_locator.

    Delegates to service_locator which resolves config/schemas/
    relative to the project root (works with PyInstaller DMG builds).
    """
    return _svc_get_schema_store()


def _get_agents():
    """Get the agents config dict via service_locator.

    Delegates to service_locator which resolves config/agents.json
    relative to the project root.
    """
    return _svc_get_agents()


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
                parts.extend(
                    _format_missing_schema_diagnostic(
                        route.model_key, route.agent_key, agent, agents
                    )
                )

        if session_id:
            _svc_get_session_store().set_last_agent(session_id, route.agent_key)
    else:
        parts.append("No specific agent matched. Available agents:\n")
        for a in agents.values():
            parts.append(f"- **{a.name}** ({a.key}): {a.description}")

    return [{"type": "text", "text": "\n".join(parts)}]


# ── Action Dispatcher ──────────────────────────────────────────────────


async def _handle_action(action: str, model: str, params: dict, record_id: int) -> list[dict]:
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
        case "create":
            odoo = _get_odoo_client()
            result = create_record(odoo, schema, params)
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
            return [
                {
                    "type": "text",
                    "text": (
                        f"Unknown action: {action}. Valid: preview, create, search, update, delete."
                    ),
                }
            ]

    return [{"type": "text", "text": json.dumps(result, default=str)}]


_odoo_client = None


def _get_odoo_client():
    """Get the OdooClient singleton via service_locator.

    Delegates to service_locator which resolves config/config.json
    relative to the project root (works with PyInstaller DMG builds).
    """
    return _svc_get_odoo_client()


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

    # Workflow hints (AI-generated domain knowledge for custom models)
    if schema.workflow_hints:
        lines.append("### WORKFLOW HINTS")
        lines.append(schema.workflow_hints)
        lines.append("")

    # Required fields with details + ask-prompts
    if schema.required_fields:
        lines.append("### REQUIRED FIELDS — Ask the user for each of these:")
        for i, fname in enumerate(schema.required_fields, 1):
            fi = schema.all_fields.get(fname)
            if fi:
                lines.append(_format_field_ask(fi, i))
        lines.append("")

    # Auto-generated fields (WARN Claude not to set these)
    auto_gen = [
        fn
        for fn in schema.create_fields
        if schema.all_fields.get(fn) and schema.all_fields[fn].auto_generated
    ]
    if auto_gen:
        lines.append("### AUTO-GENERATED FIELDS (DO NOT SET)")
        lines.append(
            "These fields are system-generated — setting them manually will have no effect:"
        )
        for fname in auto_gen:
            fi = schema.all_fields[fname]
            lines.append(f"  - `{fname}`: {fi.string} — system-generated sequence number")
        lines.append("")

    # Top optional fields (by usage frequency)
    optional_fields = [
        fn
        for fn in schema.create_fields
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
            line = f"  - `{sub.field_name}` → {sub.related_model}"
            if sub.target_fields:
                tf = sub.target_fields[:8]
                line += f"\n    Fields: {', '.join(tf)}"
            if sub.target_required_fields:
                trf = sub.target_required_fields
                line += f"\n    Required: {', '.join(trf)}"
            lines.append(line)
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

    if fi.auto_generated:
        parts.append(" ⚠️ AUTO-GENERATED — do NOT set manually")
    if fi.selection:
        options = [f"{s[0]} ({s[1]})" for s in fi.selection]
        parts.append(f" [options: {', '.join(options)}]")

    if fi.required:
        parts.append(" *REQUIRED*")
    if fi.computed:
        parts.append(" (computed)")
    if fi.related:
        parts.append(f" (related to {fi.related})")
    if fi.help_text:
        parts.append(f" — {fi.help_text}")

    return "".join(parts)


def _generate_ask_prompt(fi) -> str:
    """Generate a natural-language question for a required field.

    Uses field type, string, relation, selection, and help_text to produce
    a specific question Claude can ask the user. Works for ANY model.
    """
    label = fi.string or fi.name

    if fi.selection:
        options = [f"{s[0]} ({s[1]})" for s in fi.selection]
        return f"What should the {label} be? Options: {', '.join(options)}"

    if fi.field_type == "many2one":
        target = fi.relation or "record"
        return f"Which {label} ({target}) should this be linked to? Search for it first."

    if fi.field_type == "many2many":
        target = fi.relation or "records"
        return f"Which {label} ({target}) should be linked?"

    if fi.field_type in ("integer", "float", "monetary"):
        return f"What value should {label} have? (numeric)"

    if fi.field_type in ("date", "datetime"):
        return f"When should {label} be? (date)"

    if fi.field_type == "boolean":
        return f"Should {label} be enabled? (yes/no)"

    if fi.field_type == "text":
        return f"What {label} should be entered?"

    return f"What should the {label} be?"


def _format_field_ask(fi, index: int) -> str:
    """Format a single required field as a numbered ask-prompt for Claude."""
    prompt = _generate_ask_prompt(fi)
    label = fi.string or fi.name
    line = f"  {index}. **{label}** (`{fi.name}` — {fi.field_type}"
    if fi.relation:
        line += f" → {fi.relation}"
    line += ")"

    if fi.help_text:
        line += f"  \n     Help: {fi.help_text}"
    if fi.selection:
        options = ", ".join(f"{s[0]}" for s in fi.selection)
        line += f"  \n     Valid choices: {options}"

    line += f'  \n     → ASK: "{prompt}"'
    return line


def _format_missing_schema_diagnostic(
    model_key: str,
    agent_key: str | None,
    agent,
    agents: dict,
) -> list[str]:
    """Return an actionable diagnostic when a model's schema is missing.

    Instead of silently printing just the model key, this gives Claude
    enough information to help the user recover — regardless of which
    model is missing.
    """
    lines: list[str] = []

    lines.append("### ⚠️ SCHEMA NOT AVAILABLE")
    lines.append(f"The model `{model_key}` has no schema loaded.")
    lines.append("")
    lines.append("**Why this happened:** Schema discovery has not been run for this model. ")
    lines.append(
        "Only models that have been discovered (via `python scripts/run_schema_discovery.py`) "
        "or manually created in `config/schemas/` are available."
    )
    lines.append("")

    # List alternative models from the same agent that DO have schemas
    if agent and agent.models:
        store = _get_schema_store()
        available = []
        for m in agent.models:
            try:
                s = store.get(m)
                available.append(f"  - **{s.label}** (`{s.odoo_model}`) — key: `{m}`")
            except KeyError:
                pass
        if available:
            lines.append("**Models in this agent that DO have schemas:**")
            lines.extend(available)
            lines.append("")
            lines.append("Consider asking the user if one of these is what they meant.")

    # List ALL available models across all agents
    store = _get_schema_store()
    all_schemas = store.list_all()
    if all_schemas:
        lines.append("")
        lines.append(
            f"**All {len(all_schemas)} available models** (use `list_models` for details):"
        )
        for s in sorted(all_schemas, key=lambda x: x.label)[:10]:
            lines.append(f"  - {s.label} (`{s.odoo_model}`) → key: `{s.key}`")
        if len(all_schemas) > 10:
            lines.append(f"  ... and {len(all_schemas) - 10} more")

    lines.append("")
    lines.append("**To fix:** Run `python scripts/run_schema_discovery.py` to discover all models.")
    lines.append(
        "Or, to proceed manually: ask the user what fields their record needs, "
        "then use `action=preview` with a model key you choose."
    )

    return lines


async def list_models_handler(message: str = "", top_n: int = 10) -> list[dict]:
    """Handle list_models: return available model schemas.

    When message is provided, models are scored by relevance
    and sorted with the best matches first.  Claude can use this
    to semantically discover models when keyword routing fails.

    Args:
        message: Optional user message for relevance scoring.
        top_n: Max models to return when scoring (default 10).
    """
    store = _get_schema_store()
    schemas = store.list_all()

    if message:
        scored = [(score_model_relevance(s, message), s) for s in schemas]
        scored.sort(key=lambda x: x[0], reverse=True)
        top = scored[:top_n]

        lines = [
            f"Available Odoo Models ({len(schemas)}) — "
            f"top {len(top)} by relevance to: {message[:80]}",
            "",
        ]
        for score, schema in top:
            lines.extend(_format_model_entry(schema, score))
    else:
        lines = [f"Available Odoo Models ({len(schemas)}):", ""]
        for schema in sorted(schemas, key=lambda s: s.label):
            lines.extend(_format_model_entry(schema))

    return [{"type": "text", "text": "\n".join(lines)}]


def score_model_relevance(schema, message: str) -> int:
    """Score a model's relevance to a user message.

    Pure Python — zero tokens, zero API calls.

    Scoring criteria (weighted):
    1. match_keywords substring matches — weight = keyword length
    2. Label exact match — weight = 5
    3. Model name words match — weight = 3 per word
    4. Summary word overlap — weight = 1 per matching word
    """
    msg = message.lower()
    score = 0

    # Keyword matches (longer keywords = better match)
    for kw in schema.match_keywords:
        if kw.lower() in msg:
            score += len(kw)

    # Label match
    if schema.label.lower() in msg:
        score += 5

    # Model name words match
    model_words = schema.odoo_model.replace(".", " ").lower().split()
    msg_words = set(msg.split())
    for word in model_words:
        if word in msg_words:
            score += 3

    # Summary word overlap
    if schema.summary:
        summary_words = set(schema.summary.lower().split())
        score += len(summary_words & msg_words)

    return score


def _format_model_entry(schema, score: int | None = None) -> list[str]:
    """Format a single model entry for Claude."""
    lines = [
        f"### {schema.label} (`{schema.odoo_model}`)"
        + (f" [relevance: {score}]" if score is not None else ""),
    ]
    if schema.summary:
        lines.append(f"  {schema.summary}")
    if schema.workflow_hints:
        lines.append("  Hints:")
        for hint_line in schema.workflow_hints.split("\n"):
            if hint_line.strip():
                lines.append(f"    {hint_line.strip()}")
    if schema.match_keywords:
        kws = schema.match_keywords[:8]
        lines.append(f"  Keywords: {', '.join(kws)}")
    field_count = len(schema.all_fields)
    req = schema.required_fields[:5]
    req_str = f" (required: {', '.join(req)})" if req else ""
    lines.append(f"  Fields: {field_count}{req_str}")
    lines.append(f"  Key: `{schema.key}`")
    lines.append("")
    return lines


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
