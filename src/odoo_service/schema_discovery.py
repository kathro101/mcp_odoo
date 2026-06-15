"""Schema discovery — deterministic Odoo model introspection.

Phase 1: Deterministic extraction (ZERO AI TOKENS)
  - ir.model.fields → computed, required, related, store, depends
  - ir.ui.view → field usage frequency per view type
  - fields_get() → type, string, readonly, relation

Phase 2: View frequency analysis (ZERO AI TOKENS)
  - Parse form/tree/kanban/search view XML
  - Count field occurrences with view-type weighting

This module does NOT use AI — enrichment is in schema_enrichment.py.
"""

from __future__ import annotations

import json
import logging
import re
from pathlib import Path

from src.odoo_service.odoo_client import OdooClient
from src.shared.types import FieldInfo, ModelSchema, SubModelSchema

logger = logging.getLogger(__name__)

# ── Regex for extracting field names from view XML ─────────────────────

_FIELD_NAME_RE = re.compile(r'name="([a-z_][a-z0-9_]*)"')

# ── View type weights: form views are most important ───────────────────

_VIEW_WEIGHTS: dict[str, int] = {
    "form": 3,
    "tree": 2,
    "kanban": 1,
    "search": 1,
    "calendar": 1,
    "graph": 1,
    "pivot": 1,
}

# ── Technical model prefixes to exclude ─────────────────────────────────

_TECHNICAL_PREFIXES: tuple[str, ...] = (
    "ir.",
    "base.",
    "web.",
    "bus.",
    "iap.",
    "mail.tracking",
    "base_import.",
    "base_module_",
    "base.language.",
    "change_",
    "fetchmail.",
    "ir_",
    "test_",
)


class SchemaDiscovery:
    """Discovers Odoo model schemas via deterministic introspection.

    Uses Odoo's ORM (fields_get, ir.model.fields, ir.ui.view) to build
    complete ModelSchema instances without any AI calls.
    """

    def __init__(self, odoo: OdooClient, cache_dir: str = "config/schemas"):
        self.odoo = odoo
        self.cache_dir = Path(cache_dir)

    # ── Public API ──────────────────────────────────────────────────────

    def discover(self) -> dict[str, ModelSchema]:
        """Discover all user-facing Odoo models and return their schemas.

        Returns:
            Dict mapping model technical names to ModelSchema instances.
        """
        modules = self._list_installed_modules()
        models = self._filter_user_facing_models(modules)

        schemas: dict[str, ModelSchema] = {}
        for model_name, label in models:
            try:
                schema = self.discover_model(model_name, label)
                schemas[model_name] = schema
            except Exception as exc:
                logger.warning("Failed to discover model %s: %s", model_name, exc)

        return schemas

    def discover_model(self, model_name: str, label: str = "") -> ModelSchema:
        """Discover the schema for a single Odoo model.

        Args:
            model_name: Odoo technical model name (e.g. 'stock.picking').
            label: Human-readable label (optional, fetched if empty).

        Returns:
            A complete ModelSchema for the model.
        """
        # Phase 1: Deterministic field extraction
        raw_fields = self.odoo.fields_get(model_name)
        if isinstance(raw_fields, dict) and raw_fields.get("status") == "error":
            raise RuntimeError(f"Odoo error for {model_name}: {raw_fields['message']}")

        code_meta = self._query_ir_model_fields(model_name)
        view_freqs = self._analyze_views(model_name)

        # Build FieldInfo for each field
        all_fields: dict[str, FieldInfo] = {}
        for fname, meta in (raw_fields or {}).items():
            ir_data = code_meta.get(fname, {})
            all_fields[fname] = FieldInfo(
                name=fname,
                field_type=meta.get("type", ""),
                string=meta.get("string", fname),
                required=ir_data.get("required", meta.get("required", False)),
                readonly=meta.get("readonly", False),
                store=ir_data.get("store", meta.get("store", True)),
                computed=bool(ir_data.get("compute")),
                related=ir_data.get("related", meta.get("related", "")),
                relation=meta.get("relation", ""),
                selection=meta.get("selection", []),
                depends=ir_data.get("depends", []),
                usage_frequency=view_freqs.get(fname, 0),
                help_text=meta.get("help", ""),
            )

        # Classify fields
        create_f, search_f, required_f = self._classify_fields(all_fields)

        # Discover sub-models (one2many relationships)
        sub_models = self._discover_sub_models(model_name, all_fields)

        key = model_name.replace(".", "_")
        return ModelSchema(
            key=key,
            label=label or model_name,
            odoo_model=model_name,
            all_fields=all_fields,
            create_fields=create_f,
            search_fields=search_f,
            required_fields=required_f,
            sub_models=sub_models,
            usage_frequency_total=sum(f.usage_frequency for f in all_fields.values()),
        )

    # ── Module listing ──────────────────────────────────────────────────

    def _list_installed_modules(self) -> list[dict]:
        """Fetch all installed model records from ir.model."""
        return self.odoo.search_read(
            "ir.model",
            [("state", "=", "base")],
            fields=["model", "name"],
            limit=5000,
        )

    def _filter_user_facing_models(self, modules: list[dict]) -> list[tuple[str, str]]:
        """Filter out technical/transient models, keep user-facing ones.

        Args:
            modules: Raw ir.model records with 'model' and 'name' fields.

        Returns:
            List of (model_name, label) tuples for user-facing models.
        """
        result: list[tuple[str, str]] = []
        for mod in modules or []:
            name = mod.get("model", "")
            if isinstance(name, dict) and name.get("status") == "error":
                continue
            if not name or not isinstance(name, str):
                continue

            # Skip transient models
            label = mod.get("name", name)
            if isinstance(label, dict):
                label = name
            if not isinstance(label, str):
                label = name

            if name.startswith(_TECHNICAL_PREFIXES):
                continue
            if name.startswith("_"):
                continue

            result.append((name, label))

        return result

    # ── ir.model.fields introspection ────────────────────────────────────

    def _query_ir_model_fields(self, model_name: str) -> dict[str, dict]:
        """Fetch computed/required/depends/store from ir.model.fields.

        This is deterministic metadata from Odoo's ORM — zero AI tokens.

        Args:
            model_name: Odoo model technical name.

        Returns:
            Dict mapping field name to metadata dict with keys:
            compute, related, depends, store, required.
        """
        try:
            model_id = self.odoo.search("ir.model", [("model", "=", model_name)], limit=1)
        except (ConnectionRefusedError, OSError):
            return {}

        if isinstance(model_id, dict) and model_id.get("status") == "error":
            return {}
        if not model_id:
            return {}

        mid = model_id[0] if isinstance(model_id, list) else model_id
        raw = self.odoo.search_read(
            "ir.model.fields",
            [("model_id", "=", mid)],
            fields=["name", "compute", "related", "depends", "store", "required"],
            limit=5000,
        )

        if isinstance(raw, dict) and raw.get("status") == "error":
            return {}

        result: dict[str, dict] = {}
        for r in raw or []:
            if isinstance(r, dict) and "name" in r:
                result[r["name"]] = {
                    "compute": r.get("compute", "") or "",
                    "related": r.get("related", "") or "",
                    "depends": r.get("depends", []) or [],
                    "store": r.get("store", True),
                    "required": r.get("required", False),
                }
        return result

    # ── View frequency analysis ─────────────────────────────────────────

    def _analyze_views(self, model_name: str) -> dict[str, int]:
        """Parse ir.ui.view XML to count field usage frequency.

        Counts how many times each field name appears in form, tree,
        kanban, and search views.  Higher frequency = more important.

        Costs ZERO AI tokens.

        Args:
            model_name: Odoo model technical name.

        Returns:
            Dict mapping field name to weighted usage count.
        """
        views = self.odoo.search_read(
            "ir.ui.view",
            [("model", "=", model_name)],
            fields=["arch_db", "type"],
            limit=200,
        )

        if isinstance(views, dict) and views.get("status") == "error":
            return {}

        freq: dict[str, int] = {}
        for view in views or []:
            arch = view.get("arch_db", "") or ""
            if not arch:
                continue
            view_type = view.get("type", "") or ""
            weight = _VIEW_WEIGHTS.get(view_type, 1)

            for match in _FIELD_NAME_RE.finditer(arch):
                fname = match.group(1)
                freq[fname] = freq.get(fname, 0) + weight

        return freq

    # ── Field classification ────────────────────────────────────────────

    @staticmethod
    def _classify_fields(fields: dict[str, FieldInfo]) -> tuple[list[str], list[str], list[str]]:
        """Classify fields into create, search, and required lists.

        - create_fields: settable during creation (not computed, not related,
          not readonly)
        - search_fields: commonly searched (higher usage, char/m2o/selection)
        - required_fields: required for creation

        Args:
            fields: Dict of field_name → FieldInfo.

        Returns:
            Tuple of (create_fields, search_fields, required_fields).
        """
        create: list[str] = []
        search: list[str] = []
        required: list[str] = []

        for fname, fi in fields.items():
            # Required
            if fi.required:
                required.append(fname)

            # Creatable: not computed, not related, not readonly, store=True
            if not fi.computed and not fi.related and not fi.readonly and fi.store:
                create.append(fname)

            # Searchable: higher usage, common search types
            if fi.usage_frequency >= 2 and fi.field_type in (
                "char",
                "many2one",
                "selection",
                "many2many",
            ):
                search.append(fname)

        return create, search, required

    # ── Sub-model discovery ─────────────────────────────────────────────

    @staticmethod
    def _discover_sub_models(model_name: str, fields: dict[str, FieldInfo]) -> list[SubModelSchema]:
        """Find one2many fields and create SubModelSchema entries.

        Args:
            model_name: Parent Odoo model name.
            fields: Dict of field_name → FieldInfo.

        Returns:
            List of SubModelSchema for one2many fields.
        """
        sub_models: list[SubModelSchema] = []
        for fname, fi in fields.items():
            if fi.field_type == "one2many" and fi.relation:
                sub_models.append(
                    SubModelSchema(
                        field_name=fname,
                        related_model=fi.relation,
                        relation_field=model_name.replace(".", "_") + "_id",
                        is_one_to_many=True,
                    )
                )
        return sub_models

    # ── Persistence ─────────────────────────────────────────────────────

    def _save_schemas(self, schemas: dict[str, ModelSchema]) -> None:
        """Write schemas to disk as individual JSON files.

        Each schema is written to cache_dir/<key>.json.  Existing files
        are overwritten.

        Args:
            schemas: Dict of model_name → ModelSchema.
        """
        self.cache_dir.mkdir(parents=True, exist_ok=True)

        for _model_name, schema in schemas.items():
            file_path = self.cache_dir / f"{schema.key}.json"
            serialized = self._serialize_schema(schema)
            file_path.write_text(json.dumps(serialized, indent=2, default=str))

    @staticmethod
    def _serialize_schema(schema: ModelSchema) -> dict:
        """Convert a ModelSchema to a JSON-serializable dict."""
        all_fields_serialized: dict[str, dict] = {}
        for fname, fi in schema.all_fields.items():
            all_fields_serialized[fname] = {
                "name": fi.name,
                "field_type": fi.field_type,
                "string": fi.string,
                "required": fi.required,
                "readonly": fi.readonly,
                "store": fi.store,
                "computed": fi.computed,
                "related": fi.related,
                "relation": fi.relation,
                "selection": fi.selection,
                "depends": fi.depends,
                "usage_frequency": fi.usage_frequency,
                "help_text": fi.help_text,
            }

        return {
            "key": schema.key,
            "label": schema.label,
            "odoo_model": schema.odoo_model,
            "summary": schema.summary,
            "all_fields": all_fields_serialized,
            "create_fields": schema.create_fields,
            "search_fields": schema.search_fields,
            "required_fields": schema.required_fields,
            "field_aliases": schema.field_aliases,
            "match_keywords": schema.match_keywords,
            "sub_models": [
                {
                    "field_name": s.field_name,
                    "related_model": s.related_model,
                    "relation_field": s.relation_field,
                    "is_one_to_many": s.is_one_to_many,
                }
                for s in schema.sub_models
            ],
            "usage_frequency_total": schema.usage_frequency_total,
            "workflow_hints": schema.workflow_hints,
        }
