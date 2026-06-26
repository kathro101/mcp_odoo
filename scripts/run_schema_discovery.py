#!/usr/bin/env python3
"""Run schema discovery against a live Odoo instance.

Usage:
    python scripts/run_schema_discovery.py
    python scripts/run_schema_discovery.py --output /tmp/schemas
    python scripts/run_schema_discovery.py --models stock.picking,sale.order

Reads credentials from config/config.json.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.odoo_service.odoo_client import OdooClient
from src.odoo_service.schema_discovery import SchemaDiscovery
from src.shared.config import load_config


def main():
    parser = argparse.ArgumentParser(description="Schema Discovery for MCP Odoo")
    parser.add_argument(
        "--output",
        default="config/schemas",
        help="Directory to save schema JSON files (default: config/schemas)",
    )
    parser.add_argument(
        "--models",
        default="",
        help="Comma-separated list of specific models to discover (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print discovered models without saving",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Print detailed field info for each model",
    )
    parser.add_argument(
        "--workers",
        type=int,
        default=3,
        help="Number of parallel discovery threads (default: 3, use 10 for production)",
    )
    parser.add_argument(
        "--quick",
        action="store_true",
        help="Only discover models listed in config/agents.json (fast, for staging/testing)",
    )
    args = parser.parse_args()

    # ── Load config ──────────────────────────────────────────────────
    config_path = Path("config/config.json")
    if not config_path.exists():
        print("❌ config/config.json not found.")
        print("   Copy config/config.template.json → config/config.json")
        print("   and fill in your Odoo credentials.")
        sys.exit(1)

    try:
        cfg = load_config(str(config_path))
    except Exception as e:
        print(f"❌ Failed to load config: {e}")
        sys.exit(1)

    odoo_cfg = cfg.get("odoo", {})
    if not odoo_cfg.get("url"):
        print("❌ Odoo URL not set in config/config.json")
        sys.exit(1)

    print(f"🔌 Connecting to {odoo_cfg['url']}...")

    # ── Connect ──────────────────────────────────────────────────────
    try:
        odoo = OdooClient(
            url=odoo_cfg["url"],
            database=odoo_cfg.get("database", ""),
            username=odoo_cfg.get("username", ""),
            api_key=odoo_cfg.get("api_key", ""),
        )
        # Test connection
        odoo._authenticate()
        print(f"   ✅ Connected (uid: {odoo._uid})")
    except Exception as e:
        print(f"   ❌ Connection failed: {e}")
        sys.exit(1)

    # ── Discover ─────────────────────────────────────────────────────
    output_dir = Path(args.output)
    discovery = SchemaDiscovery(odoo, cache_dir=str(output_dir))

    print("🔍 Discovering models...")
    try:
        specific_models = [m.strip() for m in args.models.split(",") if m.strip()]

        # --quick mode: only discover models listed in agents.json
        if args.quick and not specific_models:
            import json

            agents_path = Path("config/agents.json")
            if agents_path.exists():
                agents = json.loads(agents_path.read_text())
                for _key, agent in agents.items():
                    for model in agent.get("models", []):
                        if model not in specific_models:
                            specific_models.append(model)
                if specific_models:
                    print(f"   Quick mode: only discovering {len(specific_models)} agent models")

        if specific_models:
            schemas = {}
            for model_name in specific_models:
                print(f"   → {model_name}...", end=" ")
                try:
                    schema = discovery.discover_model(model_name)
                    schemas[model_name] = schema
                    print(f"✅ {len(schema.all_fields)} fields")
                except Exception as e:
                    print(f"❌ {e}")
        else:
            schemas = discovery.discover(workers=args.workers)
            print(f"   ✅ Discovered {len(schemas)} models\n")
    except Exception as e:
        print(f"   ❌ Discovery failed: {e}")
        sys.exit(1)

    # ── Report ───────────────────────────────────────────────────────
    print(f"\n{'=' * 60}")
    print(f"Discovered {len(schemas)} models:")
    print(f"{'=' * 60}")

    for _key, schema in sorted(schemas.items(), key=lambda x: x[1].label):
        field_count = len(schema.all_fields)
        req_count = len(schema.required_fields)
        alias_count = len(schema.field_aliases)
        kw_count = len(schema.match_keywords)
        print(f"\n📦 {schema.label} ({schema.odoo_model})")
        print(f"   Key: {schema.key}")
        print(f"   Fields: {field_count} total, {req_count} required")
        print(f"   Aliases: {alias_count}")
        print(f"   Keywords: {kw_count}")
        if schema.summary:
            print(f"   Summary: {schema.summary}")

        if args.verbose:
            print("\n   Fields:")
            for fname, fi in sorted(
                schema.all_fields.items(), key=lambda x: x[1].usage_frequency, reverse=True
            ):
                meta = []
                if fi.required:
                    meta.append("REQUIRED")
                if fi.computed:
                    meta.append("computed")
                if fi.related:
                    meta.append(f"related→{fi.related}")
                if not fi.store:
                    meta.append("not stored")
                meta_str = f" [{', '.join(meta)}]" if meta else ""
                print(
                    f"     {fname} ({fi.field_type}): {fi.string}{meta_str}"
                    f" (freq:{fi.usage_frequency})"
                )

    # ── Save ─────────────────────────────────────────────────────────
    if not args.dry_run:
        output_dir.mkdir(parents=True, exist_ok=True)
        discovery._save_schemas(schemas)
        print(f"\n💾 Saved {len(schemas)} schemas to {output_dir}/")

        # Also copy to config/schemas/ if different
        if str(output_dir) != "config/schemas":
            import shutil

            config_schemas = Path("config/schemas")
            config_schemas.mkdir(parents=True, exist_ok=True)
            for json_file in output_dir.glob("*.json"):
                shutil.copy2(json_file, config_schemas / json_file.name)
            print("   Also copied to config/schemas/")
    else:
        print("\n📝 Dry run — not saving (use without --dry-run to save)")


if __name__ == "__main__":
    main()
