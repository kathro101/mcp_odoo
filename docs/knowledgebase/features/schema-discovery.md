# Feature: Schema Discovery & Enrichment

**Implemented:** 2026-06-15
**Updated:** 2026-06-16 (parallel discovery)
**Files:** `src/odoo_service/schema_discovery.py` (440 lines), `src/odoo_service/schema_enrichment.py` (217 lines)
**Tests:** `tests/test_schema_discovery.py` (20 tests), `tests/test_schema_enrichment.py` (13 tests)

## What It Does

Discovers Odoo model schemas through deterministic introspection (no AI) with optional one-time AI enrichment (cached).

### Discovery Pipeline (Zero AI Tokens, Parallel)

1. **List installed modules** → `ir.model` with `state=base`
2. **Filter user-facing models** → exclude `ir.*`, `base.*`, `web.*`, transient
3. **Parallel discovery** → `ThreadPoolExecutor` with 10 workers discovers models concurrently
   a. `fields_get()` → type, string, readonly, relation, selection (+ help text)
   b. `_query_ir_model_fields()` → computed, required, store, depends from `ir.model.fields`
   c. `_analyze_views()` → parse `ir.ui.view` XML, count field occurrences weighted by view type
   d. `_classify_fields()` → separate into create, search, required
   e. `_discover_sub_models()` → find one2many relationships
4. **Save** each schema to `config/schemas/<key>.json`

### Performance

| Workers          | ~576 models | Command                                  |
| ---------------- | ----------- | ---------------------------------------- |
| 1 (sequential)   | ~60 min     | `--workers 1`                            |
| **10 (default)** | **~6 min**  | `python scripts/run_schema_discovery.py` |
| 20 (aggressive)  | ~3 min      | `--workers 20`                           |

### Enrichment Pipeline (One-Time, Cached)

1. **Custom models only** → standard models (sale.order, res.partner, etc.) are skipped (LLMs already know them)
2. **Summary** → 2-sentence description of what the model stores/manages, cached to `<key>_summary.txt`
3. **Aliases** → field aliases (e.g. "customer" → "partner_id") and match keywords (e.g. ["shipment", "delivery"])
4. **Cached forever** → once generated, never re-generated

### View Frequency Weighting

- form views: weight 3 (most important)
- tree views: weight 2
- kanban, search, calendar, graph, pivot: weight 1

## Design Decisions

- **Deterministic-first**: 95% of schema data comes from Odoo ORM (zero AI tokens)
- **Standard model skip**: LLMs trained on Odoo already understand `sale.order`, `res.partner`, etc.
- **Cache-first enrichment**: AI results cached to disk, never regenerated
- **View-based relevance**: Fields appearing more often in views = more important = higher `usage_frequency`
- **~98% token reduction** vs old approach (3,000 vs 150,000 tokens for 200 models)
