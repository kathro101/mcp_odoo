# Architecture: MCP Server Layer

**Files:** `src/mcp_server/server.py` (50 lines), `src/mcp_server/tools.py` (180 lines)  
**Tests:** `tests/test_mcp_server.py` (8 tests)  
**Dependencies:** `mcp` SDK, `src/odoo_service/`, `src/shared/`

## Purpose

Thin JSON-RPC bridge between Claude Desktop and the Odoo service layer. The MCP server has **zero business logic** — it only:

1. Registers tools with the MCP client
2. Dispatches tool calls to handlers
3. Returns structured results

## Components

### server.py

- Creates an `mcp.server.Server("odoo-agent")` instance
- Registers `list_tools()` and `call_tool()` decorators
- Provides `main()` entry point for stdio transport
- ~50 lines — intentionally minimal

### tools.py

Defines exactly 3 MCP tools:

| Tool          | Purpose                                                   | Required Args  |
| ------------- | --------------------------------------------------------- | -------------- |
| `chat_odoo`   | Route user message to agent, return routing + schema info | `message: str` |
| `list_models` | Enumerate all available Odoo models with fields           | none           |
| `list_agents` | Enumerate agent personas with keywords and models         | none           |

All handlers delegate to `src/odoo_service/` — no LLM calls, no business logic.

Lazy-initialized singletons:

- `_schema_store` — `SchemaStore` from `config/schemas/`
- `_agents` — dict of `AgentConfig` from `config/agents.json`
- `_session_store` — `SessionStore` (in-memory)

## Data Flow

```
Claude Desktop
    │ tool call: chat_odoo(message="Create a shipment", session_id="abc")
    ▼
handle_tool_call("chat_odoo", {...})
    │
    ▼
chat_odoo_handler(message, session_id)
    ├── route_message(message, agents) → RouteResult
    ├── _get_schema_store().get(model_key) → ModelSchema
    ├── _session_store.set_last_agent(session_id, agent_key)
    └── return [{"type": "text", "text": "Routed to: Logistics Agent\nModel: Transfers (stock.picking)\nRequired fields: name, partner_id, picking_type_id"}]
```

## Key Rules

- Handlers are `async` — MCP SDK requires it
- All handlers return `list[dict]` with `{"type": "text", "text": "..."}` blocks
- Unknown tool names return error text (not exceptions)
- Service references are lazy-initialized on first call
- No config is loaded at import time — only when first tool is called
