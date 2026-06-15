# Feature: Workflow Hints — AI-Generated Domain Knowledge

**Implemented:** 2026-06-15
**Files:** `src/shared/types.py` (workflow_hints on ModelSchema), `src/odoo_service/schema_enrichment.py` (enrich_workflow_hints)
**Tests:** Implicit — tested through integration + enrichment tests

## What It Does

`workflow_hints` is a free-text field on `ModelSchema` that contains domain-specific knowledge about how fields interact, common user phrases, and cross-model workflows.

Generated once during AI enrichment, cached to `config/schemas/<key>.json`, and rendered in both `chat_odoo` and `list_models` responses. Standard Odoo models (`sale.order`, `stock.picking`, etc.) are skipped — LLMs already understand them from training data.

### Where It Appears

In `chat_odoo` response (between FIELD ALIASES and REQUIRED FIELDS):

```
### WORKFLOW HINTS
- When user says 'from [date] to [date]', set dates on milestone lines
- 'road direct' → template where transport_type='road', service_type='direct'
- Container numbers, vessel names → milestone lines, not header
```

### What It Helps Claude Understand

| Without workflow_hints                                                   | With workflow_hints                                      |
| ------------------------------------------------------------------------ | -------------------------------------------------------- |
| "Shipment from Nov 10 to Dec 10" → sets dates on shipment header (wrong) | Sets dates on milestone lines (correct)                  |
| "Road direct" → asks user to pick a template                             | Looks up template by transport_type + service_type       |
| "From SO123" → asks user to explain                                      | Links via sale_order_id, populates from sale order lines |

### Design Decisions

- **AI-generated, not user-configured** — user just runs the wizard
- **Cached forever** — never regenerated once in `config/schemas/`
- **Standard models skipped** — Claude already knows `sale.order`, `res.partner`, etc.
- **User can override** — just edit the JSON file
