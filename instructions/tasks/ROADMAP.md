# mcp_odoo — Task Roadmap

> **Date:** 2026-06-15  
> **Source:** `rewrite_of_agentic_tool_odoo.md` §8 Implementation Roadmap  
> **Current:** 104 tests passing, Phases 1-4 largely complete

---

## Phase 1: Foundation ✅ COMPLETE

- [x] Directory structure (`src/`, `config/`, `tests/`, `docs/`, `installer/`)
- [x] `pyproject.toml` with minimal dependencies
- [x] `src/shared/types.py` — 7 dataclasses (FieldInfo, ModelSchema, SubModelSchema, AgentConfig, SessionState, RouteResult)
- [x] `src/shared/config.py` — load_config(), load_agents()
- [x] `src/odoo_service/odoo_client.py` — XML-RPC wrapper with error handling
- [x] Tests: 28 (test_types, test_config, test_odoo_client)
- [x] `CLAUDE.md`, `README.md`, `.gitignore`, `config/config.template.json`

---

## Phase 2: Schema & Discovery ✅ COMPLETE

- [x] `src/odoo_service/schema_store.py` — load/save/lookup from `config/schemas/*.json`
- [x] `src/odoo_service/schema_discovery.py` — deterministic introspection (ir.model.fields + ir.ui.view + fields_get)
- [x] `src/odoo_service/schema_enrichment.py` — one-time AI aliases/keywords (custom models only)
- [x] Sample schemas: `config/schemas/stock_picking.json`, `config/schemas/sale_order.json`
- [x] Tests: 33 (test_schema_store, test_schema_discovery, test_schema_enrichment)

---

## Phase 3: Operations (Remaining) 🔴 IN PROGRESS

### 3A. Update Operations

**File:** `src/operations/update.py`  
**Tests:** `tests/test_update_operations.py`

- [ ] `update_record(odoo, schema, record_id, params) → dict`
  - Happy path: update existing record, return success
  - Missing `record_id`: return error
  - Odoo error (Fault, ConnectionRefused): return error dict
  - No params provided: return warning (nothing to update)
- [ ] `preview_update(schema, current_values, params) → dict`
  - Show what will change vs what stays same
  - Flag fields not in create_fields

### 3B. Delete Operations

**File:** `src/operations/delete.py`  
**Tests:** `tests/test_delete_operations.py`

- [ ] `delete_record(odoo, schema, record_id) → dict`
  - Happy path: delete existing record
  - Non-existent ID: return error
  - Odoo permission error: return error dict
- [ ] `confirm_delete(schema, record_data) → dict`
  - Return a human-readable summary for confirmation

### 3C. Analytics Operations

**File:** `src/operations/analytics.py`  
**Tests:** `tests/test_analytics_operations.py`

- [ ] `aggregate(odoo, schema, group_by, metric) → dict`
  - read_group wrapper: count, sum, avg by field
  - Empty results: return empty aggregation
  - Invalid group_by field: return error
- [ ] `count_by_state(odoo, schema) → dict`
  - Convenience: count records grouped by `state` field

---

## Phase 4: MCP Server (Remaining) 🔴

### 4A. Transport Layer

**File:** `src/mcp_server/transport.py`  
**Tests:** `tests/test_transport.py`

- [ ] `run_stdio(server)` — stdio transport helper
- [ ] `run_http(server, port)` — HTTP transport for dev/testing
- [ ] Tests: mock stdio streams, verify server starts

### 4B. Enhanced Tools

**File:** `src/mcp_server/tools.py` (enhance existing)

- [ ] `chat_odoo` — integrate with operations layer (search, create)
- [ ] `chat_odoo` — return structured previews for pending operations
- [ ] Add `search_odoo` helper tool (explicit search vs chat-based search)

---

## Phase 5: Routing & Agents 🔴

### 5A. Complete Agent Routing

**File:** `src/odoo_service/router.py` (enhance)

- [ ] Multi-keyword scoring improvements (exact match bonus, position weighting)
- [ ] Agent-to-model resolution (route to best model within agent's scope)
- [ ] Fallback routing: when no keywords match, route to CS orchestrator

### 5B. Agent Configuration

**File:** `config/agents.json` (enhance)

- [ ] Add HR agent (hr.employee, hr.department, hr.contract)
- [ ] Add per-agent instructions/behavior hints
- [ ] Add model-to-agent mapping validation

### 5C. Integration Tests

**File:** `tests/test_integration.py`

- [ ] Full pipeline: message → route → schema lookup → operation
- [ ] Multi-turn conversation: session state continuity
- [ ] Error propagation: Odoo down → graceful error to MCP client

---

## Phase 6: Web UI & Installer 🔴

### 6A. Web Interface

**File:** `webapp.py` (new)  
**Templates:** `templates/index.html`  
**Static:** `static/app.js`, `static/styles.css`

- [ ] Flask chat UI (single-page, minimal)
- [ ] Message input → POST /api/chat → stream response
- [ ] Session management (cookies or localStorage)
- [ ] Schema viewer tab (list models, show fields)

### 6B. Setup Wizard

**File:** `installer/wizard.py`  
**Templates:** `installer/templates/`

- [ ] Web-based Odoo connection setup (url, db, credentials)
- [ ] Test connection button
- [ ] Schema discovery trigger (run discovery + enrichment)
- [ ] Claude Desktop config auto-generation

### 6C. Packaging

**File:** `build/OdooAIAgent.spec`

- [ ] PyInstaller spec for macOS .app bundle
- [ ] Include web UI static files
- [ ] Auto-launch browser on startup

---

## Phase 7: Polish & Documentation 🔴

### 7A. Documentation

- [ ] `docs/ARCHITECTURE.md` — system design, data flow, key decisions
- [ ] `docs/MCP_SETUP.md` — Claude Desktop configuration guide
- [ ] `docs/MODEL_SCHEMAS.md` — schema discovery process
- [ ] `docs/CONTRIBUTING.md` — dev setup, TDD workflow, PR process
- [ ] `docs/CHANGELOG.md` — version history

### 7B. Agent Configs

- [ ] `.github/agents/coder-tester.agent.md` (already exists, review)
- [ ] `.github/agents/qa.agent.md` — adversarial testing agent
- [ ] `.github/agents/maintainer.agent.md` — architecture review agent

### 7C. Shared Utilities

**File:** `src/shared/date_utils.py`

- [ ] `parse_date_flexible(text) → datetime` — natural language date parsing
- [ ] Tests: "today", "next Monday", "2026-01-15", empty, invalid

### 7D. Final Testing

- [ ] Integration test against live Odoo staging
- [ ] Claude Desktop end-to-end: real message → real response
- [ ] Performance: schema discovery speed, tool call latency
- [ ] Edge cases: very large schemas, unicode model names

---

## Summary

| Phase | Name                                 | Status  | Tests |
| ----- | ------------------------------------ | ------- | ----- |
| 1     | Foundation                           | ✅ Done | 28    |
| 2     | Schema & Discovery                   | ✅ Done | 33    |
| 3     | Operations (update/delete/analytics) | 🔴      | 0     |
| 4     | MCP Server (transport)               | 🔴      | 0     |
| 5     | Routing & Agents                     | 🔴      | 0     |
| 6     | Web UI & Installer                   | 🔴      | 0     |
| 7     | Polish & Documentation               | 🔴      | 0     |

**Current test count: 104**

---

## Next Up (Priority Order)

1. **Update + Delete operations** (Phase 3) — completes the CRUD layer, unblocks end-to-end flows
2. **Analytics operations** (Phase 3) — read_group aggregation, needed for dashboard queries
3. **Transport layer** (Phase 4) — HTTP transport for dev mode, needed for web UI
4. **Web UI** (Phase 6) — Flask chat interface, makes the whole thing usable
5. **Shared utilities** (Phase 7C) — date_utils, needed by chat_odoo
