# CLAUDE.md — Odoo AI Agent (mcp_odoo)

## Project Overview

MCP server that connects Claude Desktop to Odoo ERP. Claude is the AI — the server
is a thin bridge that provides Odoo data access and CRUD operations.

## Architecture

```
src/
├── mcp_server/       # MCP protocol layer (tools, server, transport)
│   ├── server.py     # MCP SDK-based server (~80 lines)
│   ├── tools.py      # Tool definitions + handlers (~200 lines)
│   └── transport.py  # stdio/HTTP transport helpers
├── odoo_service/     # Business logic layer (no AI)
│   ├── router.py     # Keyword-based agent/model dispatch
│   ├── odoo_client.py # XML-RPC wrapper
│   ├── schema_store.py # Schema cache + lookup
│   ├── schema_discovery.py # Model introspection
│   ├── schema_enrichment.py # AI-powered alias/keyword generation (one-time)
│   └── session_store.py # Session state management
├── operations/       # Stateless CRUD operations
│   ├── search.py
│   ├── create.py
│   ├── update.py
│   ├── delete.py
│   └── analytics.py
└── shared/           # Types, config, utilities
    ├── types.py      # Dataclasses
    ├── config.py     # Config loader
    └── date_utils.py # Date helpers
```

## Key Rules (Non-Negotiable)

1. **No LLM calls in runtime code** — Claude Desktop IS the LLM. The MCP server
   never calls an LLM during tool execution (only during one-time schema enrichment
   at setup time).
2. **No internal conversation state** — use `session_id` for statelessness.
   Session state is a simple key-value store.
3. **All Odoo calls go through `odoo_client.py`** — never import `xmlrpc.client`
   outside of this module.
4. **Schema enrichment is a one-time setup step**, not runtime.
5. **TDD is mandatory** — write a failing test FIRST, then implement.
6. **Python 3.10+** — use `X | Y` unions, `match/case`, `from __future__ import annotations`.
7. **Dataclasses over dicts** for structured data crossing module boundaries.
8. **Structured result dicts** for all operation returns: `{"status": "...", "message": "..."}`.
9. **No `Any`** except at system boundaries (XML-RPC returns, raw JSON from LLM).

## Coding Standards

- Functions do one thing. Max ~60 lines.
- Files max ~600 lines.
- Early returns over nested ifs.
- No silent exception swallows — log or return error dict.
- `from __future__ import annotations` at the top of every module.
- Type annotations on all public functions and class attributes.

## Testing

```bash
pytest tests/ -v           # Run all unit tests
pytest tests/ --cov=src    # With coverage
```

- Framework: pytest
- Mock Odoo in unit tests — never hit live Odoo
- Test categories: happy path, null/missing, fuzzy, Odoo failure, multi-turn

## Tech Stack

- Python 3.10+
- MCP Python SDK (`mcp`) for protocol
- `xmlrpc.client` (stdlib) for Odoo RPC
- `anthropic` SDK for one-time schema enrichment only
- Flask for setup wizard
- pytest for testing
