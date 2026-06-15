# MCP Setup — Claude Desktop Configuration

Connect the MCP Odoo server to Claude Desktop in 3 steps.

## 1. Install & Configure

```bash
cd mcp_odoo
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"

# Create your config
cp config/config.template.json config/config.json
# Edit config/config.json with your Odoo credentials
```

## 2. Configure Claude Desktop

Add to your `claude_desktop_config.json`:

**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`  
**Windows:** `%APPDATA%/Claude/claude_desktop_config.json`

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

## 3. Restart Claude Desktop

The MCP server starts automatically when Claude Desktop launches. You'll see a "tools" icon (🔨) indicating the odoo tools are available.

## Available Tools

| Tool          | What Claude Can Do                                   |
| ------------- | ---------------------------------------------------- |
| `chat_odoo`   | Query Odoo — Claude routes and interprets            |
| `list_models` | Browse available Odoo models and their fields        |
| `list_agents` | See agent personas (logistics, sales, accounting...) |

## Example Conversation

```
You: Create a shipment for ACME Corp

Claude: [calls chat_odoo]

Server: Routed to Logistics Agent. Model: Transfers (stock.picking).
        Required: name, partner_id, picking_type_id.

Claude: I can help create that shipment. I need:
        - What type of operation? (delivery, receipt, internal?)
        - When should it be scheduled?
```

## Troubleshooting

| Problem             | Solution                                                                             |
| ------------------- | ------------------------------------------------------------------------------------ |
| Tools not appearing | Check Claude Desktop logs: `~/Library/Logs/Claude/mcp*.log`                          |
| Connection refused  | Verify Odoo URL in `config/config.json`                                              |
| Schema not loading  | Run `python -c "from src.odoo_service.schema_discovery import SchemaDiscovery; ..."` |
| Permission denied   | Ensure `api_key` is correct in config                                                |
