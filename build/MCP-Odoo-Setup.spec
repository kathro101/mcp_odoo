# -*- mode: python ; coding: utf-8 -*-
"""PyInstaller spec for MCP Odoo Setup Wizard — macOS .app bundle."""

from pathlib import Path

ROOT = Path('/Users/kath/personal_projects/odoo/mcp_odoo')

block_cipher = None

a = Analysis(
    [str(ROOT / 'installer' / 'wizard.py')],
    pathex=[str(ROOT)],
    binaries=[],
    datas=[
        (str(ROOT / 'config' / 'config.template.json'), 'config'),
        (str(ROOT / 'config' / 'agents.json'), 'config'),
        (str(ROOT / 'config' / 'schemas'), 'config/schemas'),
        (str(ROOT / 'installer' / 'templates'), 'installer/templates'),
    ],
    hiddenimports=[
        'src',
        'src.shared',
        'src.shared.types',
        'src.shared.config',
        'src.odoo_service',
        'src.odoo_service.odoo_client',
        'src.odoo_service.schema_store',
        'src.odoo_service.schema_discovery',
        'src.odoo_service.schema_enrichment',
        'src.odoo_service.router',
        'src.odoo_service.session_store',
        'src.odoo_service.service_locator',
        'src.operations',
        'src.operations.create',
        'src.operations.search',
        'src.operations.update',
        'src.operations.delete',
        'src.operations.analytics',
        'flask',
        'xmlrpc.client',
    ],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        'tkinter', 'matplotlib', 'numpy', 'pandas', 'scipy', 'PIL', 'cv2',
    ],
    win_no_prefer_redirects=False,
    win_private_assemblies=False,
    cipher=block_cipher,
    noarchive=False,
)

pyz = PYZ(a.pure, a.zipped_data, cipher=block_cipher)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name='MCP Odoo Setup',
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.zipfiles,
    a.datas,
    strip=False,
    upx=True,
    upx_exclude=[],
    name='MCP Odoo Setup',
)

app = BUNDLE(
    coll,
    name='MCP Odoo Setup.app',
    bundle_identifier='com.mcp-odoo.setup',
    info_plist={
        'CFBundleName': 'MCP Odoo Setup',
        'CFBundleDisplayName': 'MCP Odoo Setup',
        'CFBundleShortVersionString': '2.3.0',
        'CFBundleVersion': '2.3.0',
        'NSHighResolutionCapable': True,
        'LSBackgroundOnly': False,
        'LSMinimumSystemVersion': '11.0',
    },
)
