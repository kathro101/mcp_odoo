# MCP Odoo — AI Agent for Odoo ERP

Talk to your Odoo ERP through Claude Desktop. Ask questions, search records, create shipments, manage sales orders — all in natural language.

## What It Does

Connect Claude Desktop to your Odoo instance and you can:

- **"Show me 5 sale orders from December 2025"** → lists matching orders
- **"Create a shipment from Rotterdam to Amsterdam for ACME Corp"** → creates a logistics shipment
- **"How many invoices are overdue?"** → searches and counts invoices
- **"Update the price on quotation SO-0042"** → modifies a sales order

Claude handles all the conversation and reasoning. The MCP server is just a bridge — it gives Claude access to your Odoo data and lets it perform CRUD operations.

## Quick Start (macOS)

### 1. Install

```bash
# Clone the repo
git clone https://github.com/kathro101/mcp_odoo.git
cd mcp_odoo

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install
pip install -e .
```

### 2. Configure

```bash
# Copy the template
cp config/config.template.json config/config.json
```

Edit `config/config.json` with your Odoo credentials:

```json
{
  "odoo": {
    "url": "https://your-company.odoo.com",
    "database": "your-database-name",
    "username": "your-email@example.com",
    "api_key": "your-api-key-or-password"
  }
}
```

> **API Key:** In Odoo, go to Preferences → Account Security → API Keys to generate one (recommended over password).

### 3. Connect Claude Desktop

Edit `~/Library/Application Support/Claude/claude_desktop_config.json`:

```json
{
  "mcpServers": {
    "odoo": {
      "command": "/path/to/mcp_odoo/.venv/bin/mcp-odoo",
      "cwd": "/path/to/mcp_odoo"
    }
  }
}
```

> Replace `/path/to/mcp_odoo` with the actual path. Use `pwd` in the terminal to find it.

### 4. Restart Claude Desktop and Start Talking

Quit Claude Desktop completely (Cmd+Q), reopen it, and try:

> "What can you do with Odoo?"

You should see the list of available agents and models.

## Available Commands in Claude

| What You Say                               | What Happens                               |
| ------------------------------------------ | ------------------------------------------ |
| "Show me sale orders from last month"      | Searches `sale.order` records              |
| "Create a shipment to Berlin for Client X" | Previews then creates a logistics shipment |
| "Update invoice INV-0042 to paid"          | Updates `account.move` record              |
| "How many POs are in draft?"               | Analytics: counts by state                 |
| "List all available models"                | Lists all Odoo models                      |
| "What agents are available?"               | Shows logistics, sales, accounting, etc.   |

## How It Works

```
You → Claude Desktop → MCP Server → Odoo (XML-RPC) → Back to Claude → You
```

- **Claude is the brain** — it understands your intent, plans multi-step actions, and generates responses
- **MCP Server is the bridge** — thin, stateless, no AI. It routes keywords, looks up schemas, calls Odoo
- **Your Odoo data stays private** — everything runs locally, nothing is sent to external services

## Customizing Agents and Models

Edit `config/agents.json` to add your own agents or change keywords. For example, to add a "Shipping" agent for your custom `x_shipping_order` model:

```json
"shipping": {
  "key": "shipping",
  "name": "Shipping Agent",
  "description": "Handles custom shipping orders",
  "default_model": "x_shipping_order",
  "keywords": ["shipping", "container", "vessel", "port"],
  "models": ["x_shipping_order"]
}
```

## Troubleshooting

### "Agents file not found" or "Schema directory not found"

Make sure you run the server from the project root. If using a PyInstaller DMG build, the server automatically resolves paths relative to the `.app` bundle.

### "No module named 'src'"

Run `pip install -e .` from the project root to install in development mode.

### Claude says "Unknown model"

Your Odoo instance may have custom models not yet discovered. Run the setup wizard or schema discovery script to populate `config/schemas/`.

## Developing

See [DEV_COMMANDS.md](DEV_COMMANDS.md) for development setup, testing, linting, and build instructions. See [CLAUDE.md](CLAUDE.md) for project architecture and coding standards.

```bash
# Run tests
pytest tests/ -v

# Run linting
ruff check src/ tests/

# Build the DMG installer
bash scripts/build_dmg.sh
```

## License

MIT
