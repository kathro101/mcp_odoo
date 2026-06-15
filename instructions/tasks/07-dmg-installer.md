# Task: DMG Wizard Installer

**Created:** 2026-06-15
**Status:** 🔴 Not started
**Priority:** MEDIUM — needed for end-user distribution on macOS
**Depends on:** All core modules, webapp.py, transport.py

---

## Problem

Users must manually edit `config/config.json` and `claude_desktop_config.json` to set up the MCP Odoo agent. This is error-prone and requires technical knowledge. We need a friendly macOS installer that:

1. Collects Odoo credentials through a GUI wizard
2. Tests the connection
3. Auto-configures Claude Desktop
4. Optionally discovers schemas from the Odoo instance

## Architecture

```
installer/
├── wizard.py          # Flask-based setup wizard (~200 lines)
├── templates/
│   └── wizard.html    # Setup UI: form steps + progress
└── setup.py           # PyInstaller hook / setup config

build/
└── build_dmg.sh       # Build script: PyInstaller → .app → .dmg
```

## Wizard Flow (3 Steps)

### Step 1: Odoo Connection
```
┌─────────────────────────────────────┐
│  MCP Odoo Setup Wizard              │
│                                     │
│  Odoo URL: [https://my.odoo.com   ] │
│  Database: [my-database            ] │
│  Username: [admin                  ] │
│  API Key:  [••••••••••••••••••••• ] │
│                                     │
│  [ Test Connection ]                │
│  ✅ Connection successful!          │
│                                     │
│  [ Next → ]                         │
└─────────────────────────────────────┘
```

### Step 2: Claude Desktop Setup
```
┌─────────────────────────────────────┐
│  Claude Desktop Configuration       │
│                                     │
│  We found Claude Desktop at:        │
│  ~/Library/Application Support/     │
│    Claude/claude_desktop_config.json│
│                                     │
│  [✓] Auto-configure Claude Desktop  │
│  [ ] Skip (configure manually)      │
│                                     │
│  [ Back ]          [ Next → ]       │
└─────────────────────────────────────┘
```

### Step 3: Schema Discovery (Optional)
```
┌─────────────────────────────────────┐
│  Schema Discovery                   │
│                                     │
│  Discover Odoo models to enable     │
│  smart AI responses?                │
│                                     │
│  [✓] Discover schemas now (~30s)    │
│  [ ] Skip (use defaults)            │
│                                     │
│  Progress: ████████░░ 80%           │
│  Discovered 47 models               │
│                                     │
│  [ Back ]          [ Finish ]       │
└─────────────────────────────────────┘
```

## Technical Implementation

### wizard.py (Flask app)

```python
"""Setup wizard for MCP Odoo — Flask-based GUI installer."""

from flask import Flask, jsonify, render_template, request

app = Flask(__name__)

@app.route("/")
def wizard():
    return render_template("wizard.html")

@app.route("/api/test-connection", methods=["POST"])
def test_connection():
    """Test Odoo connection with provided credentials."""
    data = request.get_json()
    try:
        # Try authenticating
        client = OdooClient(data["url"], data["database"],
                           data["username"], data["api_key"])
        client._authenticate()
        return jsonify({"status": "ok", "message": "Connected!"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)})

@app.route("/api/save-config", methods=["POST"])
def save_config():
    """Save config.json from wizard input."""
    data = request.get_json()
    config = {
        "odoo": {
            "url": data["url"],
            "database": data["database"],
            "username": data["username"],
            "api_key": data["api_key"],
        },
        "mcp": {"transport": "stdio"},
        "schema": {"cache_dir": "config/schemas"},
    }
    # Save to ~/Library/Application Support/MCP Odoo/config.json
    app_dir = Path.home() / "Library/Application Support/MCP Odoo"
    app_dir.mkdir(parents=True, exist_ok=True)
    (app_dir / "config.json").write_text(json.dumps(config, indent=2))
    return jsonify({"status": "ok"})

@app.route("/api/configure-claude", methods=["POST"])
def configure_claude():
    """Add MCP Odoo entry to Claude Desktop config."""
    claude_config_path = (
        Path.home() / "Library/Application Support/Claude/"
        "claude_desktop_config.json"
    )
    # Read existing or create new
    ...
    return jsonify({"status": "ok"})

@app.route("/api/discover-schemas", methods=["POST"])
def discover_schemas():
    """Run schema discovery against the configured Odoo instance."""
    ...
    return jsonify({"status": "ok", "count": len(schemas)})
```

### PyInstaller Build

```python
# PyInstaller spec: build/OdooAIAgent.spec
# -*- mode: python ; coding: utf-8 -*-

a = Analysis(
    ['installer/wizard.py'],
    pathex=[],
    binaries=[],
    datas=[
        ('config/', 'config'),
        ('templates/', 'templates'),
        ('static/', 'static'),
    ],
    hiddenimports=['xmlrpc.client', 'mcp', 'flask', 'src'],
    ...
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    name='MCP Odoo Setup',
    icon='build/icon.icns',
    console=False,  # Windowed — no terminal
    ...
)

app = BUNDLE(
    exe,
    name='MCP Odoo Setup.app',
    icon='build/icon.icns',
    bundle_identifier='com.kathro101.mcp-odoo',
)
```

### Build Commands

```bash
# Build the .app bundle
pyinstaller build/OdooAIAgent.spec

# Create the .dmg
hdiutil create -volname "MCP Odoo" \
    -srcfolder dist/"MCP Odoo Setup.app" \
    -ov -format UDZO \
    dist/MCP-Odoo-Installer.dmg
```

## Acceptance Criteria

- [ ] Wizard opens on double-click (no terminal visible)
- [ ] Test Connection verifies Odoo credentials
- [ ] Saves `config.json` to correct location
- [ ] Auto-configures `claude_desktop_config.json` (merges with existing)
- [ ] Optional schema discovery with progress bar
- [ ] Creates .dmg for distribution
- [ ] Works on macOS 13+ (Ventura and newer)
