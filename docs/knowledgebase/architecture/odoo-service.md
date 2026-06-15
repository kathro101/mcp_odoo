# Architecture: Odoo Service Layer

**Files:** `src/odoo_service/` — 6 modules, ~874 lines total
**Tests:** 6 test files, 65 tests
**Dependencies:** `xmlrpc.client` (stdlib), `src/shared/`

## Purpose

The brain of the operation — but NOT an AI brain. Pure Python business logic with zero LLM calls. Handles Odoo communication, schema management, routing, and session state.

## Modules

### odoo_client.py (130 lines, 6 tests)

**SINGLE** module that talks to Odoo via XML-RPC. No other module imports `xmlrpc.client`.

```python
class OdooClient:
    def execute_kw(model, method, args, kwargs) → list|dict|int|bool
    def search_read(model, domain, fields, limit, offset, order) → list[dict]
    def search(model, domain, limit) → list[int]
    def fields_get(model, attributes) → dict[str, dict]
```

- Lazy authentication on first call
- All errors caught → returned as `{"status": "error", "message": "..."}`
- ConnectionRefusedError → error dict (never raised)

### router.py (49 lines, 9 tests)

Pure function: `route_message(message, agents) → RouteResult`

- Case-insensitive keyword substring matching
- Scores agents by cumulative keyword length
- Returns highest-scoring agent (or None if no match)
- No LLM, no state, no side effects

### schema_store.py (130 lines, 7 tests)

`SchemaStore` — in-memory cache of `ModelSchema` instances.

- Loads from `config/schemas/*.json` at init
- `get(key)` → ModelSchema (raises KeyError if missing)
- `list_all()` → list of all schemas
- `search(keyword)` → list of matching schemas (case-insensitive keyword match)
- Invalid JSON files are skipped with a warning

### schema_discovery.py (341 lines, 20 tests)

`SchemaDiscovery` — deterministic model introspection from live Odoo.

Four phases (ALL zero AI tokens):

1. **Deterministic extraction**: `ir.model.fields` → computed/required/store/depends, `fields_get()` → type/string/readonly/relation
2. **View frequency analysis**: Parse `ir.ui.view` XML, count field occurrences weighted by view type (form=3, tree=2, kanban=1)
3. **Field classification**: Separate into create_fields, search_fields, required_fields
4. **Sub-model discovery**: Find one2many fields → SubModelSchema

Key methods:

- `discover() → dict[str, ModelSchema]`
- `discover_model(model_name, label) → ModelSchema`
- `_query_ir_model_fields(model_name) → dict` — ir.model.fields metadata
- `_analyze_views(model_name) → dict[str, int]` — usage frequency
- `_classify_fields(fields) → tuple[list, list, list]` — create/search/required
- `_discover_sub_models(model_name, fields) → list[SubModelSchema]`
- `_save_schemas(schemas)` — write to disk
- `_filter_user_facing_models(modules)` — exclude ir._, base._, transient models

### schema_enrichment.py (147 lines, 13 tests)

**ONLY place LLMs are called** — one-time, offline, cached.

- `enrich_custom_models(schemas, llm, cache_dir)` — 2-sentence summary for custom models only (standard models skipped)
- `enrich_aliases(schemas, llm)` — field aliases (e.g. "customer" → "partner_id") and match keywords
- `_is_standard_model(model_name)` — checks against known prefixes (sale., res., account., etc.)
- Results cached to disk, never regenerated
- Errors caught gracefully (log warning, don't crash)

### session_store.py (77 lines, 10 tests)

`SessionStore` — simple dict-based session state.

- `get_state(session_id)` → SessionState (creates if new)
- `set_state(session_id, state)` → stores state
- `get_last_agent(session_id)` → current agent key
- `set_last_agent(session_id, agent_key)` → update agent
- `reset_state(session_id)` → clear session
- Multiple sessions are independent
- In-memory only — no persistence between restarts
