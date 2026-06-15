# Task: Codebase Audit Fixes — 6 Findings

**Created:** 2026-06-15  
**Status:** ✅ Complete  
**Priority:** HIGH — fixes crash risk, deduplication, and edge cases  
**Source:** Full codebase audit of all 4 layers  
**Target tests:** 151 → ~162

---

## Finding #1 🔴 CRITICAL — `_get_schema_store()` crashes without config

### Problem
`src/mcp_server/tools.py::_get_schema_store()` calls `load_config("config/config.json")` unconditionally. If the config file doesn't exist, it crashes with `FileNotFoundError`, breaking `chat_odoo` routing mode entirely.

### Root Cause
No try/except around `load_config()`. The function assumes the config always exists.

### Fix
Wrap `load_config` in try/except. Fall back to hardcoded `"config/schemas"` default directory when config is missing.

```python
# src/mcp_server/tools.py — _get_schema_store()

# Before:
def _get_schema_store(config_path: str = "config/config.json") -> SchemaStore:
    global _schema_store
    if _schema_store is None:
        config = load_config(config_path)
        schema_dir = config.get("schema", {}).get("cache_dir", "config/schemas")
        _schema_store = SchemaStore(schema_dir)
    return _schema_store

# After:
def _get_schema_store() -> SchemaStore:
    global _schema_store
    if _schema_store is None:
        try:
            config = load_config("config/config.json")
            schema_dir = config.get("schema", {}).get("cache_dir", "config/schemas")
        except FileNotFoundError:
            schema_dir = "config/schemas"
        _schema_store = SchemaStore(schema_dir)
    return _schema_store
```

### Tests to Add (2 new)
- `test_get_schema_store_falls_back_when_config_missing` — Verify SchemaStore is created with default dir
- `test_get_schema_store_loads_from_config_when_present` — Verify config path is used when available

### Files Changed
- `src/mcp_server/tools.py` — `_get_schema_store()`

---

## Finding #2 🟡 HIGH — `_handle_action` creates OdooClient with empty config

### Problem
`_get_odoo_client()` creates `OdooClient(url="", database="", ...)` if config is missing or has empty values. The resulting Odoo call fails with an unhelpful connection error instead of a clear "config not set up" message.

### Root Cause
No validation that `odoo.url` is non-empty before creating the client.

### Fix
Validate config before creating OdooClient. Catch `RuntimeError` in `_handle_action` and return a clear error message through the MCP response (never raise — MCP tools must return content blocks).

```python
# src/mcp_server/tools.py — _get_odoo_client()

def _get_odoo_client():
    global _odoo_client
    if _odoo_client is None:
        try:
            cfg = load_config("config/config.json")
        except FileNotFoundError:
            raise RuntimeError(
                "Odoo not configured. Create config/config.json first."
            )
        odoo_cfg = cfg.get("odoo", {})
        if not odoo_cfg.get("url"):
            raise RuntimeError(
                "Odoo URL not set. Edit config/config.json and add odoo.url."
            )
        from src.odoo_service.odoo_client import OdooClient
        _odoo_client = OdooClient(
            url=odoo_cfg["url"],
            database=odoo_cfg.get("database", ""),
            username=odoo_cfg.get("username", ""),
            api_key=odoo_cfg.get("api_key", ""),
        )
    return _odoo_client
```

Then in `_handle_action`, wrap OdooClient access:
```python
case "search":
    try:
        odoo = _get_odoo_client()
    except RuntimeError as e:
        return [{"type": "text", "text": str(e)}]
    result = search_records(odoo, schema, params)
```

### Tests to Add (2 new)
- `test_action_search_returns_error_when_config_missing` — Mock config missing, verify clear error
- `test_action_search_returns_error_when_url_empty` — Mock empty url, verify clear error

### Files Changed
- `src/mcp_server/tools.py` — `_get_odoo_client()`, `_handle_action()`

---

## Finding #3 🟡 HIGH — `search_records` uses `ilike` for all fields

### Problem
`src/operations/search.py::search_records()` applies `("field", "ilike", value)` to EVERY filter. Odoo rejects `ilike` on integer, float, and many2one fields. Searching for `partner_id=5` becomes `("partner_id", "ilike", 5)` → Odoo error.

### Root Cause
No field-type-aware operator selection. The `schema.all_fields` metadata is available but not used.

### Fix
Look up each filter field's type in `schema.all_fields`. Use `=` for numeric/relational types, `ilike` for text types.

```python
# src/operations/search.py — search_records()

# Before:
domain.append((field, "ilike", value))

# After:
fi = schema.all_fields.get(field)
if fi and fi.field_type in ("integer", "float", "monetary", "many2one"):
    try:
        value = int(value)
    except (ValueError, TypeError):
        pass
    domain.append((field, "=", value))
else:
    domain.append((field, "ilike", str(value)))
```

### Tests to Add (3 new)
- `test_search_uses_ilike_for_char_fields` — Verify text field gets ilike
- `test_search_uses_equals_for_integer_fields` — Verify integer field gets =
- `test_search_uses_equals_for_many2one_fields` — Verify many2one field gets =

### Files Changed
- `src/operations/search.py` — `search_records()`

---

## Finding #4 🟡 HIGH — Duplicated lazy-singletons

### Problem
`src/mcp_server/tools.py` and `webapp.py` both implement identical `_get_schema_store()`, `_get_agents()`, and session store patterns. ~60 lines duplicated across two files. Any fix to one must be mirrored in the other.

### Root Cause
No shared service locator module. Each entry point creates its own singletons.

### Fix
Create `src/odoo_service/service_locator.py` with three functions:
- `get_schema_store() → SchemaStore`
- `get_agents() → dict[str, AgentConfig]`
- `get_session_store() → SessionStore`

Both `tools.py` and `webapp.py` import from here.

```python
# New file: src/odoo_service/service_locator.py

from __future__ import annotations

from src.odoo_service.schema_store import SchemaStore
from src.odoo_service.session_store import SessionStore
from src.shared.config import load_agents, load_config

_schema_store: SchemaStore | None = None
_agents: dict | None = None
_session_store: SessionStore = SessionStore()


def get_schema_store() -> SchemaStore:
    global _schema_store
    if _schema_store is None:
        try:
            config = load_config("config/config.json")
            schema_dir = config.get("schema", {}).get("cache_dir", "config/schemas")
        except FileNotFoundError:
            schema_dir = "config/schemas"
        _schema_store = SchemaStore(schema_dir)
    return _schema_store


def get_agents(agents_path: str = "config/agents.json") -> dict:
    global _agents
    if _agents is None:
        _agents = load_agents(agents_path)
    return _agents


def get_session_store() -> SessionStore:
    return _session_store
```

### Migration
- `tools.py`: Replace `_get_schema_store()`, `_get_agents()`, `_session_store` with imports from `service_locator`
- `webapp.py`: Same replacement
- `tools.py`: Move `_get_odoo_client()` to `service_locator` and add validation

### Tests to Add (3 new)
- `test_get_schema_store_singleton` — Verify same instance returned on multiple calls
- `test_get_agents_singleton` — Verify same dict returned
- `test_get_session_store_singleton` — Verify same instance

### Files Changed
- **New:** `src/odoo_service/service_locator.py`
- `src/mcp_server/tools.py` — Remove `_get_schema_store`, `_get_agents`, `_get_odoo_client`, `_session_store`
- `webapp.py` — Remove `_get_schema_store`, `_get_agents`, `_session_store`

---

## Finding #5 🟢 LOW — `date_utils.py` unused `now` variable

### Problem
`src/shared/date_utils.py:54`: `now = datetime.now(tz=tz)` is computed but never referenced. The function only uses `today = date.today()`.

### Fix
Delete line 54. No functional change.

```python
# Before:
today = date.today()
now = datetime.now(tz=tz)  # ← unused

# After:
today = date.today()
```

### Tests
Existing tests cover this — no new tests needed. Run `tests/test_date_utils.py` to verify no regressions.

### Files Changed
- `src/shared/date_utils.py` — `parse_date_flexible()`

---

## Finding #6 🟢 LOW — `router.py` non-deterministic tie-breaking

### Problem
When two agents have the same keyword score, the winner depends on Python dict iteration order. While Python 3.7+ preserves insertion order (dicts are ordered), the outcome depends on the order of keys in `agents.json` — which is not a documented contract.

### Fix
When scores are equal, prefer the agent whose key sorts first alphabetically. This makes routing fully deterministic regardless of dict order.

```python
# src/odoo_service/router.py — route_message()

# Before:
if score > best.score:
    best = RouteResult(...)

# After:
if score > best.score or (
    score == best.score
    and best.agent_key is not None
    and agent.key < best.agent_key
):
    best = RouteResult(...)
```

### Tests to Add (1 new)
- `test_tie_break_uses_alphabetical_order` — Two agents with same score, verify alphabetical key wins

### Files Changed
- `src/odoo_service/router.py` — `route_message()`

---

## Implementation Order

| Step | Finding | Tests | Risk |
|------|---------|-------|------|
| 1 | #5 (unused var) | 0 | None — pure cleanup |
| 2 | #3 (ilike fix) | +3 | Low — search behavior changes |
| 3 | #6 (tie-break) | +1 | Low — router becomes deterministic |
| 4 | #4 (service locator) | +3 | Medium — restructures imports in 3 files |
| 5 | #1 (config fallback) | +2 | Low — handled in service locator |
| 6 | #2 (odoo client validation) | +2 | Low — handled in service locator |

## Acceptance Criteria

- [ ] All 6 findings fixed
- [ ] 11 new tests added (~162 total)
- [ ] Full test suite green
- [ ] `docs/knowledgebase/CHANGELOG.md` updated
- [ ] `docs/knowledgebase/bugs/` created for findings #1-3
