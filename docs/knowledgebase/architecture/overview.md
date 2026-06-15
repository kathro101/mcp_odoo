# Architecture Overview

> **Last updated:** 2026-06-15
> **See also:** `CLAUDE.md`, `README.md`, `rewrite_of_agentic_tool_odoo.md`

## System Design

```
Claude Desktop (MCP Client) ← THE AI BRAIN
        │  JSON-RPC (stdio)
        ▼
┌──────────────────────────────────────────┐
│  MCP Server Layer (src/mcp_server/)       │
│  ┌────────────────────────────────────┐  │
│  │ server.py  — MCP SDK wrapper       │  │
│  │ tools.py   — 3 tool handlers       │  │
│  │   chat_odoo | list_models | list_agents │
│  └────────────────────────────────────┘  │
├──────────────────────────────────────────┤
│  Odoo Service Layer (src/odoo_service/)   │
│  ┌────────────────────────────────────┐  │
│  │ router.py         — keyword dispatch│  │
│  │ odoo_client.py    — XML-RPC wrapper │  │
│  │ schema_store.py   — schema cache    │  │
│  │ schema_discovery.py — introspection │  │
│  │ schema_enrichment.py — AI enrichment│  │
│  │ session_store.py  — per-session state│  │
│  └────────────────────────────────────┘  │
├──────────────────────────────────────────┤
│  Operations Layer (src/operations/)       │
│  ┌────────────────────────────────────┐  │
│  │ search.py  | create.py             │  │
│  └────────────────────────────────────┘  │
├──────────────────────────────────────────┤
│  Shared Layer (src/shared/)              │
│  ┌────────────────────────────────────┐  │
│  │ types.py   — 7 dataclasses         │  │
│  │ config.py  — config loader         │  │
│  └────────────────────────────────────┘  │
└──────────────────────────────────────────┘
        │  XML-RPC
        ▼
    Odoo ERP
```

## Dependency Direction

```
mcp_server → odoo_service → operations → odoo_client → Odoo XML-RPC
     │            │
     └────────────┴──→ shared (types, config)
```

**No circular imports.** Dependencies flow one way: server → service → operations → Odoo.

## Key Design Decisions

| Decision                  | Rationale                                                | ADR                                                  |
| ------------------------- | -------------------------------------------------------- | ---------------------------------------------------- |
| No internal LLM           | Claude Desktop is the AI; two brains = confusion + cost  | [ADR-0001](decisions/0001-no-internal-llm.md)        |
| Keyword routing (not LLM) | Keywords faster, cheaper, deterministic                  | [ADR-0002](decisions/0002-keyword-routing.md)        |
| Dataclasses over dicts    | Type safety, IDE support, self-documenting               | [ADR-0003](decisions/0003-dataclasses-over-dicts.md) |
| Flat config               | One `config.json`, schemas per file in `config/schemas/` |                                                      |
| MCP SDK (not hand-rolled) | Spec compliance, less code                               |                                                      |
| Stateless operations      | Pure functions, easier to test                           |                                                      |

## Module Map

| Module            | File                                    | Lines | Tests | Purpose                 |
| ----------------- | --------------------------------------- | ----- | ----- | ----------------------- |
| Types             | `src/shared/types.py`                   | 95    | 14    | 7 dataclasses           |
| Config            | `src/shared/config.py`                  | 74    | 8     | Config + agents loader  |
| Odoo Client       | `src/odoo_service/odoo_client.py`       | 130   | 6     | XML-RPC wrapper         |
| Router            | `src/odoo_service/router.py`            | 49    | 9     | Keyword dispatch        |
| Schema Store      | `src/odoo_service/schema_store.py`      | 130   | 7     | Schema cache            |
| Schema Discovery  | `src/odoo_service/schema_discovery.py`  | 341   | 20    | Model introspection     |
| Schema Enrichment | `src/odoo_service/schema_enrichment.py` | 147   | 13    | AI aliases/keywords     |
| Session Store     | `src/odoo_service/session_store.py`     | 77    | 10    | Session state           |
| MCP Server        | `src/mcp_server/server.py`              | 50    | —     | MCP SDK wrapper         |
| MCP Tools         | `src/mcp_server/tools.py`               | 180   | 8     | 3 tool handlers         |
| Search Operations | `src/operations/search.py`              | 55    | 5     | Record search           |
| Create Operations | `src/operations/create.py`              | 73    | 4     | Record create + preview |
