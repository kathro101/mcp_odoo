"""Schema enrichment — one-time AI-powered alias and keyword generation.

This is the ONLY place in the codebase where an LLM is called.  It runs
OFFLINE, during setup, and results are cached to disk.  Never called at
runtime during tool execution.

Standard Odoo models (sale.order, res.partner, account.move, etc.) are
SKIPPED — LLMs already understand them from training data.  Only custom
models (x_*, ops_logistics.*, etc.) get AI enrichment.
"""

from __future__ import annotations

import logging
from pathlib import Path

from src.shared.types import ModelSchema

logger = logging.getLogger(__name__)

# ── Standard model prefixes that LLMs already know ──────────────────────

_STANDARD_PREFIXES: tuple[str, ...] = (
    "res.",
    "sale.",
    "purchase.",
    "account.",
    "stock.",
    "crm.",
    "hr.",
    "project.",
    "mrp.",
    "product.",
    "mail.",
    "calendar.",
    "fleet.",
    "event.",
    "website.",
    "survey.",
    "base.",
    "uom.",
    "decimal.precision",
    "ir.",
)


def _is_standard_model(model_name: str) -> bool:
    """Check if a model is a standard Odoo model known to LLMs.

    Args:
        model_name: Odoo technical model name.

    Returns:
        True if standard (skip AI enrichment), False if custom.
    """
    if not model_name:
        return False
    return any(model_name.startswith(prefix) for prefix in _STANDARD_PREFIXES)


# ── Deterministic heuristic enrichment (ZERO AI TOKENS) ────────────────

# Fields that are commonly required at the business-logic level
# even when ir.model.fields reports required=False.
# Promoted to required for models where they exist and are used in views.
_IMPORTANT_FIELDS: set[str] = {
    "partner_id",  # Customer/Vendor/Contact — always conceptually required
    "name",  # Display name / reference
}


def apply_heuristics(schemas: dict[str, ModelSchema]) -> dict[str, ModelSchema]:
    """Apply deterministic heuristics to improve schema quality.

    Zero AI tokens.  Zero API calls.  Pure Python rules.

    Rules applied:
    1. Promote important fields to required if they exist in the model
       and are in create_fields.  (e.g. partner_id is often required
       at the business-logic level but not at the database level.)
    2. Generate default workflow_hints when none exist.
    3. Add standard field aliases for common patterns.

    Args:
        schemas: Dict of model_name → ModelSchema (mutated in place).

    Returns:
        The same schemas dict (for chaining).
    """
    for _key, schema in schemas.items():
        # Rule 1: Promote important fields to required
        for field_name in _IMPORTANT_FIELDS:
            if (
                field_name in schema.all_fields
                and field_name in schema.create_fields
                and field_name not in schema.required_fields
            ):
                schema.required_fields.append(field_name)
                # Also mark the FieldInfo
                schema.all_fields[field_name].required = True

        # Sort required_fields for stable ordering
        schema.required_fields.sort()

        # Rule 2: Default workflow_hints for models that have none
        if not schema.workflow_hints:
            hints: list[str] = []
            # Template pattern: if a sub-model name hints at templates
            template_subs = [
                s.field_name for s in schema.sub_models if "template" in s.related_model.lower()
            ]
            if template_subs:
                hints.append(
                    f"This model may support templates ({', '.join(template_subs)}). "
                    "Ask the user if they want to load a template before creating."
                )
            # Required field reminder
            if len(schema.required_fields) >= 3:
                hints.append(
                    "All required fields must be filled. "
                    "Use preview action to check what's missing."
                )
            # Partner reminder
            if "partner_id" in schema.required_fields:
                hints.append(
                    "partner_id is required — always confirm the customer/vendor before creating."
                )

            if hints:
                schema.workflow_hints = "\n".join(f"- {h}" for h in hints)

    return schemas


# ── Custom model summarization ──────────────────────────────────────────


def enrich_custom_models(
    schemas: dict[str, ModelSchema],
    llm,
    cache_dir: str = "config/schemas",
) -> None:
    """Generate a 2-sentence summary ONLY for custom models.

    Standard models are skipped.  Results cached to disk — never
    regenerated once cached.

    Args:
        schemas: Dict of model_name → ModelSchema (mutated in place).
        llm: LLM client with an `ask(prompt, max_tokens)` method.
        cache_dir: Directory for caching summaries.
    """
    cache_path = Path(cache_dir)

    for _key, schema in schemas.items():
        if _is_standard_model(schema.odoo_model):
            continue

        # Check cache
        cache_file = cache_path / f"{schema.key}_summary.txt"
        if cache_file.exists():
            schema.summary = cache_file.read_text().strip()
            continue

        # Build prompt from top-used fields
        field_lines = []
        for fname, fi in schema.all_fields.items():
            if fi.usage_frequency > 0 or fi.required:
                field_lines.append(
                    f"  - {fname} ({fi.field_type}) [{fi.string}]"
                    f"{' REQUIRED' if fi.required else ''}"
                )
        top_fields = field_lines[:30]  # cap at 30

        prompt = (
            f"Model: {schema.odoo_model} ({schema.label})\n"
            f"Fields:\n" + "\n".join(top_fields) + "\n\n"
            "In one sentence, describe what this Odoo model stores or manages."
        )

        try:
            summary = llm.ask(prompt, max_tokens=100).strip()
            schema.summary = summary
            cache_file.parent.mkdir(parents=True, exist_ok=True)
            cache_file.write_text(schema.summary)
        except Exception as exc:
            logger.warning("Failed to enrich summary for %s: %s", schema.odoo_model, exc)


# ── Field alias and keyword enrichment ──────────────────────────────────


def enrich_aliases(
    schemas: dict[str, ModelSchema],
    llm,
) -> None:
    """Generate field aliases and match keywords via AI.

    One-time enrichment for all models.  Skips models that already
    have aliases and keywords populated.

    Args:
        schemas: Dict of model_name → ModelSchema (mutated in place).
        llm: LLM client with an `ask_json(prompt)` method.
    """
    for _key, schema in schemas.items():
        # Skip if already enriched
        if schema.field_aliases and schema.match_keywords:
            continue

        # Build prompt from fields
        field_desc = []
        for fname, fi in schema.all_fields.items():
            desc = f"  - {fname} ({fi.field_type}): {fi.string}"
            if fi.required:
                desc += " [REQUIRED]"
            if fi.relation:
                desc += f" → {fi.relation}"
            field_desc.append(desc)

        prompt = (
            f"Odoo model: {schema.odoo_model} ({schema.label})\n\n"
            "Fields:\n" + "\n".join(field_desc[:50]) + "\n\n"
            "Return a JSON object with:\n"
            '  "field_aliases": dict mapping common names to field names '
            '(e.g. "customer" → "partner_id")\n'
            '  "match_keywords": list of 5-10 keywords users might type '
            'to refer to this model (e.g. ["shipment", "delivery", "transfer"])\n'
        )

        try:
            result = llm.ask_json(prompt)
            schema.field_aliases = result.get("field_aliases", {})
            schema.match_keywords = result.get("match_keywords", [])
        except Exception as exc:
            logger.warning("Failed to enrich aliases for %s: %s", schema.odoo_model, exc)


# ── Workflow hints enrichment ───────────────────────────────────────


def enrich_workflow_hints(schemas: dict[str, ModelSchema], llm) -> None:
    """Generate domain-specific workflow hints via AI for custom models.

    Standard Odoo models are skipped (LLMs already know them).
    Results cached to schema.workflow_hints — never regenerated.
    """
    for _key, schema in schemas.items():
        if _is_standard_model(schema.odoo_model):
            continue
        if schema.workflow_hints:
            continue

        field_lines = []
        for fname, fi in schema.all_fields.items():
            if fi.usage_frequency > 0 or fi.required:
                line = f"  - {fname} ({fi.field_type}): {fi.string}"
                if fi.required:
                    line += " [REQUIRED]"
                if fi.relation:
                    line += f" \u2192 {fi.relation}"
                field_lines.append(line)

        sub_lines = []
        for sub in schema.sub_models:
            sub_lines.append(f"  - {sub.field_name} (one2many \u2192 {sub.related_model})")

        prompt = (
            f"Model: {schema.odoo_model} ({schema.label})\n"
            f"Summary: {schema.summary}\n\n"
            "Fields:\n" + "\n".join(field_lines[:40]) + "\n\n"
            "Sub-models:\n" + ("\n".join(sub_lines) if sub_lines else "  (none)") + "\n\n"
            "Based on this model, write 2-4 workflow hints for an AI assistant. "
            "Include: which fields work together, common phrases beyond aliases, "
            "cross-model workflows, template/wizard-driven field population.\n"
            'Return JSON: {"workflow_hints": ["hint 1.", "hint 2.", ...]}\n'
        )

        try:
            result = llm.ask_json(prompt)
            hints = result.get("workflow_hints", [])
            if hints:
                schema.workflow_hints = "\n".join(f"- {h}" for h in hints)
        except Exception as exc:
            logger.warning(
                "Failed to enrich workflow hints for %s: %s",
                schema.odoo_model,
                exc,
            )
