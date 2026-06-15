# Architecture: Shared Layer

**Files:** `src/shared/types.py` (95 lines), `src/shared/config.py` (74 lines)
**Tests:** `tests/test_types.py` (14 tests), `tests/test_config.py` (8 tests)
**Dependencies:** stdlib only

## Purpose

Foundation types and configuration loading used by all other layers. Zero external dependencies. Zero side effects (config loading excepted).

## types.py

Seven dataclasses that define the data model:

| Dataclass        | Fields                                                                                                                                                       | Purpose                    |
| ---------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------- |
| `FieldInfo`      | name, field_type, string, required, readonly, store, computed, related, relation, selection, depends, usage_frequency                                        | Single Odoo field metadata |
| `SubModelSchema` | field_name, related_model, relation_field, is_one_to_many                                                                                                    | one2many relationship      |
| `ModelSchema`    | key, label, odoo_model, all_fields, summary, create_fields, search_fields, required_fields, field_aliases, match_keywords, sub_models, usage_frequency_total | Complete model schema      |
| `AgentConfig`    | key, name, description, keywords, models, default_model                                                                                                      | Agent persona config       |
| `SessionState`   | session_id, current_agent, current_model, pending_operation, context, created_at                                                                             | Per-session state          |
| `RouteResult`    | agent_key, model_key, score                                                                                                                                  | Routing result             |

All use `dataclasses.dataclass` with `field(default_factory=...)` for mutable defaults. All use `from __future__ import annotations` for forward references.

## config.py

Two functions:

```python
def load_config(path: str) → dict
def load_agents(path: str) → dict[str, AgentConfig]
```

- `load_config`: validates required `odoo` section and non-empty `odoo.url`
- `load_agents`: parses `agents.json` into `AgentConfig` instances
- Both raise `FileNotFoundError` or `ValueError` on invalid input

## Key Rules

- Dataclasses only — no plain dicts for cross-module data
- No `Any` type — use `str | None` etc.
- `from __future__ import annotations` in every file
- `FieldInfo.selection` is `list[tuple[str, str]]` (serialization handles this)
