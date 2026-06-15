# Feature: MCP Tools (chat_odoo, list_models, list_agents)

**Implemented:** 2026-06-15  
**Files:** `src/mcp_server/tools.py`, `src/mcp_server/server.py`  
**Tests:** `tests/test_mcp_server.py` (8 tests)

## What It Does

Exposes 3 MCP tools to Claude Desktop:

### chat_odoo

- **Input:** `message` (str), optional `session_id` (str)
- **Process:** Routes message via keyword matching → looks up model schema → stores session state
- **Output:** Text block with routing info, model name, required fields, and model summary
- **No LLM calls** — returns structured data for Claude to interpret

### list_models

- **Input:** none
- **Output:** Markdown-formatted list of all available Odoo models with fields and descriptions

### list_agents

- **Input:** none
- **Output:** Markdown-formatted list of all agent personas with keywords and models

## Design Decisions

- Only 3 tools (vs 6+ in the old codebase) because Claude handles intent parsing
- `chat_odoo` is the single entry point — no separate `search_odoo`, `analytics_odoo`, etc.
- Lazy initialization of service singletons (schema store, agents, session store)
- All handlers are async (MCP SDK requirement)

## Usage Example

```
User: "Create a shipment for ACME Corp"
Claude: calls chat_odoo(message="Create a shipment for ACME Corp")
Server: "Routed to: Logistics Agent
         Model: Transfers (stock.picking)
         Required fields: name, partner_id, picking_type_id
         Available fields: name, partner_id, picking_type_id, scheduled_date, ..."
Claude: "I need to know: which operation type, and what's the scheduled date?"
```
