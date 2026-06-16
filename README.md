# MCP Odoo — AI Agent for Odoo ERP

MCP server that connects **Claude Desktop** to **Odoo ERP**. Claude is the AI brain — the server is a thin, stateless bridge that provides Odoo data access and CRUD operations.

## Architecture

```
Claude Desktop (MCP Client) ← THE AI BRAIN
        │
        ▼
MCP Server (thin JSON-RPC bridge)
  ├── chat_odoo     — route + lookup
  ├── list_models   — enumerate schemas
  └── list_agents   — enumerate personas
        │
        ▼
Odoo Service Layer (pure Python, no AI)
  ├── Router        — keyword-based dispatch
  ├── SchemaStore   — cached model metadata
  ├── OdooClient    — XML-RPC wrapper
  └── SessionStore  — per-session state
        │
        ▼
Odoo XML-RPC
```

## Key Principles

- **No internal LLM** — Claude Desktop IS the AI. The MCP server never calls an LLM during runtime.
- **Stateless tools** — Each MCP tool call is independent. Session state via `session_id`.
- **Keyword routing** — No LLM-based intent classification. Simple keyword scoring.
- **Flat config** — One `config.json`. Schemas in `config/schemas/*.json`.
- **TDD mandatory** — Tests written before implementation.

## Quick Start

```bash
# Clone and setup
git clone <repo-url> mcp_odoo
cd mcp_odoo
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Configure
cp config/config.template.json config/config.json
# Edit config/config.json with your Odoo credentials

# Run tests
pytest tests/ -v

# Run MCP server (for Claude Desktop)
python -m src.mcp_server.server

# Build the DMG installer
bash scripts/build_dmg.sh

# Discover schemas from your Odoo instance (6 min with 10 workers)
python scripts/run_schema_discovery.py

# Discover specific models (fast)
python scripts/run_schema_discovery.py --models stock.picking,sale.order,res.partner

# Preview without saving
python scripts/run_schema_discovery.py --dry-run

# Preview without saving:
python scripts/run_schema_discovery.py --dry-run

# Show all field details:
python scripts/run_schema_discovery.py --verbose

# Discover specific models:
python scripts/run_schema_discovery.py --models stock.picking,sale.order

# Save to custom directory:
python scripts/run_schema_discovery.py --output /tmp/my_schemas
```

## Configuration

### config/config.json

```json
{
  "odoo": {
    "url": "https://your-odoo.odoo.com",
    "database": "your-database",
    "username": "your-username",
    "api_key": "your-api-key"
  },
  "mcp": {
    "transport": "stdio"
  },
  "schema": {
    "cache_dir": "config/schemas"
  }
}
```

### Claude Desktop Setup

Add to your `claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "python",
      "args": ["-m", "src.mcp_server.server"],
      "cwd": "/path/to/mcp_odoo"
    }
  }
}
```

## Project Structure

```
mcp_odoo/
├── src/
│   ├── mcp_server/       # MCP protocol layer
│   │   ├── server.py     # MCP SDK-based server
│   │   └── tools.py      # Tool definitions + handlers (3 tools)
│   ├── odoo_service/     # Business logic (no AI)
│   │   ├── router.py     # Keyword-based agent routing
│   │   ├── odoo_client.py # XML-RPC wrapper
│   │   ├── schema_store.py # Schema cache + lookup
│   │   └── session_store.py # Session state
│   ├── operations/       # Stateless CRUD
│   │   ├── search.py
│   │   └── create.py
│   └── shared/           # Types, config, utilities
│       ├── types.py      # Dataclasses
│       └── config.py     # Config loader
├── config/
│   ├── config.template.json
│   ├── agents.json
│   └── schemas/          # One JSON per Odoo model
├── tests/
├── CLAUDE.md
└── pyproject.toml
```

## MCP Tools

| Tool          | Description                                                        |
| ------------- | ------------------------------------------------------------------ |
| `chat_odoo`   | Send a user message — routes to agent, returns model schema + data |
| `list_models` | List all available Odoo models and their fields                    |
| `list_agents` | List all agent personas (logistics, sales, accounting, etc.)       |

## Agents

| Agent      | Keywords                             | Default Model    |
| ---------- | ------------------------------------ | ---------------- |
| Logistics  | shipment, delivery, stock, warehouse | `stock.picking`  |
| Sales      | sale, order, quotation, customer     | `sale.order`     |
| Accounting | invoice, payment, bill, journal      | `account.move`   |
| Purchasing | purchase, PO, vendor, supplier       | `purchase.order` |
| CS         | hello, help, menu                    | (routing only)   |

## Testing

```bash
pytest tests/ -v              # All unit tests
pytest tests/ --cov=src       # With coverage
pytest tests/ -k "test_router" # Specific module
```

## License

MIT
