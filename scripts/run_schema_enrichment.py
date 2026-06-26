#!/usr/bin/env python3
"""Run schema enrichment after discovery to add aliases, keywords, and hints.

Usage:
    python scripts/run_schema_enrichment.py
    python scripts/run_schema_enrichment.py --heuristics-only
    python scripts/run_schema_enrichment.py --model sale_order

After discovery populates raw field data, enrichment adds:
- Field aliases (e.g., "customer" → partner_id)
- Match keywords (e.g., ["shipment", "delivery"])
- Workflow hints (e.g., "create sub-records after parent")
- Model summaries (2-sentence description of what the model does)

Heuristics-only mode runs instantly (zero AI tokens) and provides
deterministic improvements.  Full enrichment uses AI for custom models
only (standard Odoo models like sale.order are skipped).
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.odoo_service.schema_enrichment import apply_heuristics
from src.odoo_service.schema_store import SchemaStore


def main():
    parser = argparse.ArgumentParser(description="Schema Enrichment for MCP Odoo")
    parser.add_argument(
        "--schemas-dir",
        default="config/schemas",
        help="Directory containing schema JSON files (default: config/schemas)",
    )
    parser.add_argument(
        "--model",
        default="",
        help="Enrich a specific model only (default: all)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print changes without saving",
    )
    args = parser.parse_args()

    # ── Load schemas ──────────────────────────────────────────────────
    schemas_dir = Path(args.schemas_dir)
    if not schemas_dir.is_dir():
        print(f"❌ Schemas directory not found: {schemas_dir}")
        print("   Run schema discovery first: python scripts/run_schema_discovery.py")
        sys.exit(1)

    store = SchemaStore(str(schemas_dir))
    all_schemas = store.list_all()

    if not all_schemas:
        print(f"❌ No schemas found in {schemas_dir}")
        sys.exit(1)

    schemas = {s.key: s for s in all_schemas}

    if args.model:
        if args.model not in schemas:
            print(f"❌ Model not found: {args.model}")
            sys.exit(1)
        schemas = {args.model: schemas[args.model]}
        print(f"📦 Enriching: {args.model}")
    else:
        print(f"📦 Enriching {len(schemas)} schemas...")

    # ── Apply heuristics (deterministic, zero AI tokens) ──────────────
    enriched = apply_heuristics(schemas)

    # ── Show what changed ─────────────────────────────────────────────
    for _key, schema in sorted(enriched.items()):
        added_hints = bool(schema.workflow_hints)
        changes = []
        if added_hints:
            changes.append("workflow_hints")
        if changes:
            print(f"   ✅ {schema.label}: added {', '.join(changes)}")
        else:
            print(f"   → {schema.label}: no changes (standard model, enrichment skipped)")

    # ── Save ──────────────────────────────────────────────────────────
    if not args.dry_run:
        import json

        from src.odoo_service.schema_discovery import SchemaDiscovery

        disc = SchemaDiscovery.__new__(SchemaDiscovery)
        disc.cache_dir = schemas_dir

        for key, schema in enriched.items():
            file_path = schemas_dir / f"{key}.json"
            serialized = disc._serialize_schema(schema)
            file_path.write_text(json.dumps(serialized, indent=2, default=str))

        print(f"\n💾 Saved {len(enriched)} enriched schemas to {schemas_dir}/")
    else:
        print("\n📝 Dry run — not saving")


if __name__ == "__main__":
    main()
