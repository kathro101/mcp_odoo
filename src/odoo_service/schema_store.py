"""Schema cache and lookup.

Loads model schemas from config/schemas/*.json.  Each file is a single
ModelSchema serialized as JSON.  Provides get(), list_all(), and search()
operations — all O(1) or O(n) dictionary operations, no vector DB needed.
"""

from __future__ import annotations

import json
import logging
from pathlib import Path

from src.shared.types import FieldInfo, ModelSchema, SubModelSchema

logger = logging.getLogger(__name__)


class SchemaStore:
    """In-memory cache of all Odoo model schemas.

    Loaded once at startup from config/schemas/*.json.  Each JSON file
    contains exactly one model's schema.  No AI, no embeddings, no RAG.
    """

    def __init__(self, schema_dir: str):
        self._schemas: dict[str, ModelSchema] = {}
        self._load_all(schema_dir)

    # ── Public API ──────────────────────────────────────────────────────

    def get(self, model_key: str) -> ModelSchema:
        """Get a single model schema by key.

        Args:
            model_key: The schema key (e.g. 'stock_picking').

        Returns:
            The ModelSchema instance.

        Raises:
            KeyError: If the model key is not found.
        """
        if model_key not in self._schemas:
            raise KeyError(f"Model schema not found: {model_key}")
        return self._schemas[model_key]

    def list_all(self) -> list[ModelSchema]:
        """Return all loaded model schemas."""
        return list(self._schemas.values())

    def search(self, keyword: str) -> list[ModelSchema]:
        """Find models whose match_keywords contain the given keyword.

        Case-insensitive substring matching against each model's
        match_keywords list.

        Args:
            keyword: A search term (e.g. 'shipment', 'invoice').

        Returns:
            List of matching ModelSchema instances (may be empty).
        """
        keyword_lower = keyword.lower()
        results = []
        for schema in self._schemas.values():
            for kw in schema.match_keywords:
                if keyword_lower in kw.lower():
                    results.append(schema)
                    break
        return results

    # ── Private loading ─────────────────────────────────────────────────

    def _load_all(self, schema_dir: str) -> None:
        """Load all .json files from the schema directory."""
        dir_path = Path(schema_dir)
        if not dir_path.is_dir():
            logger.warning("Schema directory not found: %s", schema_dir)
            return

        for file_path in sorted(dir_path.glob("*.json")):
            try:
                schema = self._load_one(file_path)
                self._schemas[schema.key] = schema
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning("Skipping invalid schema file %s: %s", file_path.name, exc)

    def _load_one(self, file_path: Path) -> ModelSchema:
        """Parse a single schema JSON file into a ModelSchema."""
        raw = json.loads(file_path.read_text())

        # Reconstruct FieldInfo objects from serialized dicts
        all_fields: dict[str, FieldInfo] = {}
        for fname, fdata in raw.get("all_fields", {}).items():
            all_fields[fname] = FieldInfo(
                name=fdata.get("name", fname),
                field_type=fdata.get("field_type", ""),
                string=fdata.get("string", fname),
                required=fdata.get("required", False),
                readonly=fdata.get("readonly", False),
                store=fdata.get("store", True),
                computed=fdata.get("computed", False),
                related=fdata.get("related", ""),
                relation=fdata.get("relation", ""),
                selection=[tuple(s) for s in fdata.get("selection", [])],
                depends=fdata.get("depends", []),
                usage_frequency=fdata.get("usage_frequency", 0),
                help_text=fdata.get("help_text", ""),
            )

        sub_models = [
            SubModelSchema(
                field_name=s.get("field_name", ""),
                related_model=s.get("related_model", ""),
                relation_field=s.get("relation_field", ""),
                is_one_to_many=s.get("is_one_to_many", False),
            )
            for s in raw.get("sub_models", [])
        ]

        return ModelSchema(
            key=raw["key"],
            label=raw.get("label", raw["key"]),
            odoo_model=raw.get("odoo_model", raw["key"]),
            all_fields=all_fields,
            summary=raw.get("summary", ""),
            create_fields=raw.get("create_fields", []),
            search_fields=raw.get("search_fields", []),
            required_fields=raw.get("required_fields", []),
            field_aliases=raw.get("field_aliases", {}),
            match_keywords=raw.get("match_keywords", []),
            sub_models=sub_models,
            usage_frequency_total=raw.get("usage_frequency_total", 0),
            workflow_hints=raw.get("workflow_hints", ""),
        )
