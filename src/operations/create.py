"""Stateless Odoo create operations.

Pure functions for record creation and preview.  No classes, no state.
"""

from __future__ import annotations

from src.odoo_service.odoo_client import OdooClient
from src.shared.types import ModelSchema


def preview_record(schema: ModelSchema, params: dict) -> dict:
    """Preview what a record creation would look like.

    Checks which required fields are provided vs missing, and which
    optional fields are filled.  Does NOT call Odoo.

    Args:
        schema: ModelSchema for the target model.
        params: Dict of field_name -> value for the new record.

    Returns:
        {"status": "success"|"needs_input", "filled": [...], "missing": [...],
         "optional": [...]}
    """
    params = params or {}
    filled = [f for f in schema.create_fields if f in params and params[f]]
    missing = [f for f in schema.required_fields if f not in params or not params.get(f)]
    optional = [f for f in schema.create_fields if f in params and f not in schema.required_fields]

    if missing:
        return {
            "status": "needs_input",
            "filled": filled,
            "missing": missing,
            "optional": optional,
            "message": f"Missing required fields: {', '.join(missing)}",
        }

    return {
        "status": "success",
        "filled": filled,
        "missing": [],
        "optional": optional,
        "message": "All required fields provided",
    }


def create_record(odoo: OdooClient, schema: ModelSchema, params: dict) -> dict:
    """Create a new record in Odoo.

    Args:
        odoo: OdooClient instance.
        schema: ModelSchema for the target model.
        params: Dict of field_name -> value for the new record.

    Returns:
        {"status": "success", "record_id": <int>}
        or {"status": "error", "message": "..."}
    """
    result = odoo.execute_kw(schema.odoo_model, "create", [params])

    if isinstance(result, dict) and result.get("status") == "error":
        return result

    return {
        "status": "success",
        "record_id": result,
    }
