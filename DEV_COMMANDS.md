# Developer Commands Reference

## Setup

```bash
# Clone
git clone https://github.com/kathro101/mcp_odoo.git
cd mcp_odoo

# Create virtual environment
python3 -m venv .venv
source .venv/bin/activate

# Install dependencies
pip install -e ".[dev]"
pip install pyinstaller

# Configure
cp config/config.template.json config/config.json
# Edit config/config.json with your Odoo credentials

# Enable pre-commit hooks
pre-commit install
```

## Run the Application

```bash
# Activate venv
source .venv/bin/activate

# Run MCP server (stdio — for Claude Desktop)
python -m src.mcp_server.server

# Run MCP server (HTTP dev mode — for testing)
python -c "
from src.mcp_server.server import server
from src.mcp_server.transport import run_http
run_http(server, port=8080)
"

# Run Web UI (Flask chat — for standalone use)
python webapp.py
# → http://localhost:5000
```

## Testing

```bash
source .venv/bin/activate

# All tests
pytest tests/ -v

# Quick test
pytest tests/ -q

# With coverage
pytest tests/ --cov=src --cov-report=html

# Specific module
pytest tests/test_router.py -v
pytest tests/ -k "test_search"

# Single test
pytest tests/test_router.py::TestRouteMessage::test_exact_keyword_match -v

# Verbose with short tracebacks
pytest tests/ -v --tb=short

# Test count check
pytest tests/ --collect-only -q | tail -1
```

## Linting & Formatting

```bash
source .venv/bin/activate

# Run all pre-commit hooks
pre-commit run --all-files

# Ruff check
ruff check src/ tests/

# Ruff auto-fix
ruff check src/ tests/ --fix

# Ruff format
ruff format src/ tests/

# Dead code check
vulture src/ --min-confidence 80
```

## Schema Discovery (one-time setup)

```bash
source .venv/bin/activate

# Discover schemas from a live Odoo instance
python -c "
from src.odoo_service.odoo_client import OdooClient
from src.odoo_service.schema_discovery import SchemaDiscovery
from src.shared.config import load_config

cfg = load_config('config/config.json')
odoo = OdooClient(
    url=cfg['odoo']['url'],
    database=cfg['odoo']['database'],
    username=cfg['odoo']['username'],
    api_key=cfg['odoo']['api_key'],
)

discovery = SchemaDiscovery(odoo, cache_dir='config/schemas')
schemas = discovery.discover()
print(f'Discovered {len(schemas)} models')

# Save to config/schemas/
discovery._save_schemas(schemas)
print('Saved to config/schemas/')
"
```

## Build & Package

```bash
source .venv/bin/activate

# === PyInstaller — Standalone Executable ===

# Build the MCP server binary
pyinstaller --onefile \
    --name mcp-odoo-server \
    --add-data "config:config" \
    --add-data "config/schemas:config/schemas" \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --hidden-import xmlrpc.client \
    --hidden-import mcp \
    --hidden-import flask \
    src/mcp_server/server.py

# Build the Web UI binary
pyinstaller --onefile \
    --name mcp-odoo-webui \
    --add-data "config:config" \
    --add-data "config/schemas:config/schemas" \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --hidden-import flask \
    --hidden-import xmlrpc.client \
    webapp.py

# Output in dist/

# === DMG Installer (macOS only) ===

# 1. Build the PyInstaller app bundle first
pyinstaller --windowed \
    --name "MCP Odoo Setup" \
    --add-data "config:config" \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --hidden-import flask \
    --hidden-import xmlrpc.client \
    --hidden-import mcp \
    --osx-bundle-identifier com.kathro101.mcp-odoo \
    installer/wizard.py

# 2. Create DMG
hdiutil create -volname "MCP Odoo" \
    -srcfolder dist/"MCP Odoo Setup.app" \
    -ov -format UDZO \
    dist/MCP-Odoo-Installer.dmg

# 3. Test the DMG
open dist/MCP-Odoo-Installer.dmg

# === Clean Build Artifacts ===

rm -rf build/ dist/ *.spec
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null
find . -type f -name "*.pyc" -delete
```

## Git Commands

```bash
# Status overview
git status --short

# Commit with pre-commit (runs automatically if installed)
git add -A
git commit -m "type: description"

# Push
git push

# View commit log
git log --oneline -10

# Diff last commit
git diff HEAD~1
```

## Environment Variables

```bash
# Optional: override config paths
export MCP_ODOO_CONFIG=/path/to/config.json
export MCP_ODOO_AGENTS=/path/to/agents.json
export MCP_ODOO_SCHEMAS=/path/to/config/schemas

# Debug mode
export MCP_ODOO_DEBUG=1
```

## File Locations (macOS)

```bash
# Claude Desktop config
~/Library/Application Support/Claude/claude_desktop_config.json

# MCP logs
~/Library/Logs/Claude/mcp*.log

# App data (if bundled)
~/Library/Application Support/MCP Odoo/
```
