# Architecture

> Full details in `docs/knowledgebase/architecture/overview.md`

## System Design

```
Claude Desktop (MCP Client) ← THE AI BRAIN
        │  JSON-RPC (stdio) or HTTP+SSE
        ▼
┌──────────────────────────────────────────┐
│  MCP Server Layer (src/mcp_server/)       │
│  ├── server.py   — MCP SDK wrapper       │
│  ├── tools.py    — 3 tool handlers       │
│  └── transport.py — stdio + HTTP modes   │
├──────────────────────────────────────────┤
│  Odoo Service Layer (src/odoo_service/)   │
│  ├── router.py          — keyword dispatch│
│  ├── odoo_client.py     — XML-RPC wrapper │
│  ├── schema_store.py    — schema cache    │
│  ├── schema_discovery.py — introspection  │
│  ├── schema_enrichment.py — AI labels     │
│  └── session_store.py   — session state   │
├──────────────────────────────────────────┤
│  Operations Layer (src/operations/)       │
│  ├── search.py    ├── create.py           │
│  ├── update.py    ├── delete.py           │
│  └── analytics.py                         │
├──────────────────────────────────────────┤
│  Shared Layer (src/shared/)               │
│  ├── types.py     — 7 dataclasses         │
│  ├── config.py    — config/agents loader  │
│  └── date_utils.py — date parsing         │
└──────────────────────────────────────────┘
        │  XML-RPC
        ▼
    Odoo ERP
```

## Dependency Direction

```
mcp_server → odoo_service → operations → odoo_client → Odoo
     │            │
     └────────────┴──→ shared (types, config, date_utils)
```

**No circular imports.**

## Key Design Decisions

| Decision               | Rationale                                                   |
| ---------------------- | ----------------------------------------------------------- |
| No internal LLM        | Claude Desktop IS the AI; two brains = confusion + cost     |
| Keyword routing        | Faster, cheaper, deterministic — no LLM needed for dispatch |
| Dataclasses over dicts | Type safety, IDE support, self-documenting                  |
| Flat config            | One `config.json`, schemas in `config/schemas/*.json`       |
| MCP SDK                | Spec compliance, less hand-rolled JSON-RPC                  |
| Stateless operations   | Pure functions, trivially testable                          |

## Module Map

| Module                 | Lines | Tests | Purpose                 |
| ---------------------- | ----- | ----- | ----------------------- |
| `types.py`             | 95    | 14    | 7 dataclasses           |
| `config.py`            | 74    | 8     | Config + agents loader  |
| `odoo_client.py`       | 130   | 6     | XML-RPC wrapper         |
| `router.py`            | 49    | 9     | Keyword dispatch        |
| `schema_store.py`      | 130   | 7     | Schema cache            |
| `schema_discovery.py`  | 341   | 20    | Model introspection     |
| `schema_enrichment.py` | 147   | 13    | AI aliases/keywords     |
| `session_store.py`     | 77    | 10    | Session state           |
| `server.py`            | 50    | —     | MCP SDK wrapper         |
| `tools.py`             | 180   | 8     | 3 tool handlers         |
| `transport.py`         | 44    | 4     | stdio + HTTP modes      |
| `search.py`            | 55    | 5     | Record search           |
| `create.py`            | 73    | 4     | Record create + preview |
| `update.py`            | 72    | 8     | Record update + preview |
| `delete.py`            | 63    | 5     | Record delete + confirm |
| `analytics.py`         | 102   | 8     | read_group aggregation  |
| `date_utils.py`        | 164   | 15    | Date parsing            |

**Total: ~1,800 lines of production code, 144 tests**
