#!/bin/bash
# Build MCP Odoo DMG installer
# Usage: bash scripts/build_dmg.sh
set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_DIR"

echo "=== MCP Odoo DMG Builder ==="
echo ""

# ── Activate venv ──────────────────────────────────────────────────────
if [ -f .venv/bin/activate ]; then
    source .venv/bin/activate
else
    echo "ERROR: .venv not found."
    echo "Run: python3 -m venv .venv && source .venv/bin/activate && pip install -e '.[dev]'"
    exit 1
fi

# Ensure pyinstaller is available
if ! command -v pyinstaller &> /dev/null; then
    echo "Installing pyinstaller..."
    pip install pyinstaller
fi

# ── Clean previous builds ──────────────────────────────────────────────
echo "1. Cleaning previous builds..."
rm -rf build/ dist/ *.spec
echo "   Done."

# ── Verify dependencies ────────────────────────────────────────────────
echo "2. Verifying dependencies..."
python -c "import flask; import xmlrpc.client; import mcp; print('   OK')"

# ── Build with PyInstaller ─────────────────────────────────────────────
echo "3. Building .app bundle..."
pyinstaller \
    --windowed \
    --name "MCP Odoo Setup" \
    --paths . \
    --add-data "installer/templates/wizard.html:installer/templates" \
    --add-data "config/config.template.json:config" \
    --add-data "config/agents.json:config" \
    --add-data "config/schemas:config/schemas" \
    --add-data "templates:templates" \
    --add-data "static:static" \
    --collect-all src \
    --hidden-import flask \
    --hidden-import xmlrpc.client \
    --hidden-import xmlrpc \
    --hidden-import mcp \
    --hidden-import mcp.server \
    --hidden-import src \
    --hidden-import src.odoo_service \
    --hidden-import src.odoo_service.odoo_client \
    --hidden-import src.odoo_service.schema_discovery \
    --hidden-import src.odoo_service.schema_store \
    --hidden-import src.odoo_service.router \
    --hidden-import src.odoo_service.session_store \
    --hidden-import src.odoo_service.schema_enrichment \
    --hidden-import src.odoo_service.service_locator \
    --hidden-import src.shared \
    --hidden-import src.shared.config \
    --hidden-import src.shared.types \
    --hidden-import src.shared.date_utils \
    --hidden-import src.operations \
    --hidden-import src.operations.search \
    --hidden-import src.operations.create \
    --hidden-import src.operations.update \
    --hidden-import src.operations.delete \
    --hidden-import src.operations.analytics \
    --hidden-import src.mcp_server \
    --hidden-import src.mcp_server.server \
    --hidden-import src.mcp_server.tools \
    --hidden-import src.mcp_server.transport \
    --osx-bundle-identifier com.kathro101.mcp-odoo \
    installer/wizard.py

echo "   .app built: dist/MCP Odoo Setup.app"

# ── Create DMG ─────────────────────────────────────────────────────────
echo "4. Creating DMG..."
DMG_NAME="MCP-Odoo-Installer.dmg"
rm -f "dist/$DMG_NAME"

# Remove quarantine so Gatekeeper doesn't block the app
xattr -cr "dist/MCP Odoo Setup.app" 2>/dev/null || true
# Also remove quarantine from the dist folder
xattr -cr dist/ 2>/dev/null || true

hdiutil create \
    -volname "MCP Odoo" \
    -srcfolder "dist/MCP Odoo Setup.app" \
    -ov \
    -format UDZO \
    "dist/$DMG_NAME"

echo ""
echo "=== Build Complete ==="
echo "  .app: dist/MCP Odoo Setup.app"
echo "  .dmg: dist/$DMG_NAME"
echo ""
echo "Test:  open dist/$DMG_NAME"
echo ""
echo "NOTE: If the app won't open, right-click → Open (Gatekeeper bypass)"
echo "      Or run: xattr -cr dist/'MCP Odoo Setup.app'"
