# Changelog

All notable changes to the mcp_odoo project.

## [2.2.0] — 2026-06-16

### ⚡ Parallel Schema Discovery

- **ThreadPoolExecutor** — schema discovery now runs 10 parallel workers by default. 576 models discovered in ~6 minutes (down from ~60 minutes sequential).
- **Odoo 17+ compatibility** — `allow_none=True` on `ServerProxy`, auto-detect `authenticate()` return type (bool→uid).
- **Config backward compat** — supports both `"password"` and `"api_key"` keys in `config.json` (auto-mapped).
- **`fields_get` optimization** — requests only needed attributes, reducing Odoo server None serialization errors.

### Stats

- **201 tests** passing, 2 skipped
- 576 models discoverable in ~6 minutes
- Zero internal LLM calls in runtime code

## [2.1.0] — 2026-06-15

### ✨ Smart Schema Pipeline

- **Enhanced `list_models`** — semantic model scoring (zero tokens). Pass a user message to get models sorted by relevance using keyword, label, and summary matching.
- **Richer schema output** — `help_text` on every field (captured from Odoo's `fields_get()`), selection labels show both key and display name (`draft (Draft)` instead of just `draft`).
- **Workflow hints** — AI-generated domain knowledge for custom models. Generated once during enrichment, cached forever. Tells Claude how fields interact ("dates on parent apply to sub-model lines"), common user phrases ("road direct" → template lookup), and cross-model workflows ("from SO123" → link to sale_order_id).
- **DMG wizard installer** — Flask-based 3-step setup wizard packaged as macOS .app/.dmg. Tests connection, saves config, auto-configures Claude Desktop, optional schema discovery.
- **Integration tests** — 5 end-to-end tests simulating full pipeline: message → route → schema → field alias mapping → preview → create.

### Stats

- **199 tests** (+22 from baseline)
- **~2,500 lines** of production code across 16 modules
- Zero internal LLM calls in runtime code
- All pre-commit hooks green (ruff, ruff-format, vulture)

## [2.0.0] — 2026-06-15

### ✨ Initial Release — Complete Rewrite

Full rewrite of `agentic_tool_odoo` (~15,000 lines) into a clean MCP-first architecture (~2,500 lines, ~83% reduction).

### Architecture

- **No internal LLM** — Claude Desktop IS the AI brain. All LLM calls removed from runtime.
- **Thin MCP server** — 3 tools: `chat_odoo`, `list_models`, `list_agents`
- **Complete CRUD** — search, create, update, delete, analytics
- **Keyword-based routing** — no LLM needed for agent dispatch
- **Flat config** — single `config.json`, schemas split per model
- **Date utilities** — natural language date parsing (stdlib only)

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
| `src/mcp_server/tools.py`               | 300   | 15    | Smart chat_odoo: routing + rich schema + action dispatch (preview/search/update/delete)        |
| `src/mcp_server/transport.py`           | 44    | 4     | stdio + HTTP/SSE transport modes                                                               |
| `src/operations/search.py`              | 55    | 5     | Search records                                                                                 |
| `src/operations/create.py`              | 73    | 4     | Create + preview records                                                                       |
| `src/operations/update.py`              | 72    | 8     | Update records + preview changes                                                               |
| `src/operations/delete.py`              | 63    | 5     | Delete records + confirmation                                                                  |
| `src/operations/analytics.py`           | 102   | 8     | read_group aggregation + count_by_state                                                        |
| `src/shared/date_utils.py`              | 164   | 15    | Natural language date parsing (stdlib only)                                                    |

### Test Suite

- **151 tests** across 15 test files
- All unit tests mocked — never hit live Odoo
- Framework: pytest with pytest-asyncio

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
