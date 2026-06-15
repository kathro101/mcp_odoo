# Changelog

All notable changes to the mcp_odoo project.

## [2.0.0] — 2026-06-15

### ✨ Initial Release — Complete Rewrite

Full rewrite of `agentic_tool_odoo` (~15,000 lines) into a clean MCP-first architecture (~2,000 lines, ~83% reduction).

### Architecture

- **No internal LLM** — Claude Desktop IS the AI brain. All LLM calls removed from runtime.
- **Thin MCP server** — 3 tools: `chat_odoo`, `list_models`, `list_agents`
- **Stateless operations** — search, create (update/delete/analytics pending)
- **Keyword-based routing** — no LLM needed for agent dispatch
- **Flat config** — single `config.json`, schemas split per model

### Modules Implemented

| Module                                  | Lines | Tests | Description                                                                                    |
| --------------------------------------- | ----- | ----- | ---------------------------------------------------------------------------------------------- |
| `src/shared/types.py`                   | 95    | 14    | 7 dataclasses (FieldInfo, ModelSchema, SubModelSchema, AgentConfig, SessionState, RouteResult) |
| `src/shared/config.py`                  | 74    | 8     | Config + agents loader                                                                         |
| `src/odoo_service/odoo_client.py`       | 130   | 6     | XML-RPC wrapper with error handling                                                            |
| `src/odoo_service/router.py`            | 49    | 9     | Keyword-based agent dispatch                                                                   |
| `src/odoo_service/schema_store.py`      | 130   | 7     | Schema cache from JSON files                                                                   |
| `src/odoo_service/schema_discovery.py`  | 341   | 20    | Deterministic model introspection                                                              |
| `src/odoo_service/schema_enrichment.py` | 147   | 13    | One-time AI alias/keyword generation                                                           |
| `src/odoo_service/session_store.py`     | 77    | 10    | Per-session state                                                                              |
| `src/mcp_server/server.py`              | 50    | —     | MCP SDK server                                                                                 |
| `src/mcp_server/tools.py`               | 180   | 8     | 3 tool definitions + handlers                                                                  |
| `src/operations/search.py`              | 55    | 5     | Search records                                                                                 |
| `src/operations/create.py`              | 73    | 4     | Create + preview records                                                                       |

### Removed (vs old codebase)

- `conversation.py` (1,383 lines) — God class, replaced by operations
- `prompt_builder.py` (506 lines) — no internal LLM
- `context_provider.py` (157 lines) — replaced by schema lookups
- `cs_orchestrator.py` (982 lines) — simplified to router
- `agent_council.py` (585 lines) — simplified to router
- `crew_council.py` (195 lines) — merged into router
- `create_engine.py`, `search_engine.py`, `update_engine.py`, `delete_engine.py` — replaced by operations
- `plugins/` (1,442 lines) — domain logic merged into operations
- `rag/`, `memory/`, `baseline/` — no longer needed
- `synthesis.py`, `learned_hints.py`, `relational_query.py`, `model_guide.py`, `bootstrap.py`, `tracing.py`
- `model_configs/model_configs.json` (30K lines) — split into `config/schemas/*.json`

### Test Suite

- **104 tests** across 10 test files
- All unit tests mocked — never hit live Odoo
- Framework: pytest with pytest-asyncio
