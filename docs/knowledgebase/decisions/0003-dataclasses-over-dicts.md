# ADR-0003: Dataclasses Over Dicts

**Date:** 2026-06-15  
**Status:** Accepted

## Context

The old codebase used plain dicts extensively for cross-module data (field metadata, model configs, agent configs). This led to:

- No type checking — misspelled keys silently returned None
- No IDE autocomplete
- Hard to document expected structure
- Defensive `.get()` calls everywhere

## Decision

**Use `dataclasses.dataclass` for all structured data that crosses module boundaries.** Seven dataclasses defined in `src/shared/types.py`:

- `FieldInfo`, `ModelSchema`, `SubModelSchema`, `AgentConfig`, `SessionState`, `RouteResult`

## Consequences

### Positive

- **Type safety** — mypy/IDE catches misspelled fields
- **Self-documenting** — class definition IS the documentation
- **Default values** — no `.get(key, default)` boilerplate
- **`field(default_factory=list)`** — safe mutable defaults
- **Serializable** — `dataclasses.asdict()` for JSON serialization

### Negative

- Slightly more verbose than dict literals
- Need to convert back from JSON when loading (handled in `schema_store._load_one()`)

### Rules

- `from __future__ import annotations` in every file using these types
- Selection tuples: `list[tuple[str, str]]` in dataclass, serialized as `list[list[str, str]]`
- Datetimes: `datetime.datetime` with UTC timezone
- No `Any` — use `str | None`, `int | None`, etc.
