# Contributing

## Development Setup

```bash
git clone https://github.com/kathro101/mcp_odoo.git
cd mcp_odoo
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

## TDD Workflow (Mandatory)

```
1. Write a FAILING test         ← defines the contract
2. Run it — confirm it FAILS    ← red
3. Write MINIMAL code to pass   ← green
4. Run ALL tests — all green    ← refactor if needed
5. Commit
6. UPDATE docs/knowledgebase/   ← document what changed
```

**Never write implementation before the test.** The test IS the specification.

## Architecture Rules

1. **No internal LLM runtime calls** — Claude Desktop IS the AI. Only `schema_enrichment.py` calls AI (one-time, offline).
2. **Dependency direction:** `mcp_server → odoo_service → operations → odoo_client → Odoo`
3. **No circular imports**
4. **All Odoo calls through `odoo_client.py`** — no `xmlrpc.client` imports elsewhere
5. **Dataclasses over dicts** for cross-module data

## Coding Standards

- Python 3.10+ with `from __future__ import annotations`
- Type annotations on all public functions
- Functions max ~60 lines, files max ~600 lines
- Structured result dicts: `{"status": "...", "message": "..."}`
- No silent exception swallows

## Testing

```bash
pytest tests/ -v              # All unit tests (144)
pytest tests/ --cov=src       # With coverage
pytest tests/ -k "test_router" # Specific module
```

## Knowledgebase

After every change, update `docs/knowledgebase/`:

| Change              | What to Update                |
| ------------------- | ----------------------------- |
| New feature         | `features/<name>.md`          |
| Bug fix             | `bugs/<name>.md`              |
| Refactor            | `architecture/<component>.md` |
| Architecture change | New ADR in `decisions/`       |
| **Always**          | `CHANGELOG.md`                |

## PR Process

1. Fork → branch → TDD → commit
2. Run full test suite (`pytest tests/`)
3. Update knowledgebase
4. Open PR with summary of changes and test results
