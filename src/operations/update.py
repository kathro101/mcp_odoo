"""Stateless Odoo update operations.

Pure functions for record update and preview.  No classes, no state.
"""

from __future__ import annotations

from src.odoo_service.odoo_client import OdooClient
from src.shared.types import ModelSchema


def update_record(
    odoo: OdooClient,
    schema: ModelSchema,
    record_id: int,
    params: dict,
) -> dict:
    """Update an existing Odoo record.

    Args:
        odoo: OdooClient instance.
        schema: ModelSchema for the target model.
        record_id: ID of the record to update.
        params: Dict of field_name -> new_value.

    Returns:
        {"status": "success", "record_id": <int>}
        or {"status": "warning", "message": "..."}
        or {"status": "error", "message": "..."}
    """
    if not params:
        return {
            "status": "warning",
            "message": "No fields provided — nothing to update",
        }

    result = odoo.execute_kw(schema.odoo_model, "write", [[record_id], params])

    if isinstance(result, dict) and result.get("status") == "error":
        return result

    return {
        "status": "success",
        "record_id": record_id,
    }


def preview_update(
    schema: ModelSchema,
    current_values: dict,
    params: dict,
) -> dict:
    """Preview what an update would change.

    Does NOT call Odoo.  Compares current values with proposed params.

    Args:
        schema: ModelSchema for the target model.
        current_values: Dict of field_name -> current value.
        params: Dict of field_name -> proposed new value.

    Returns:
        {"status": "success", "changes": {field: {old, new}}, "unchanged": [...], "warnings": [...]}
    """
    changes: dict[str, dict[str, object]] = {}
    unchanged: list[str] = []
    warnings: list[str] = []

    for field, new_value in params.items():
        old_value = current_values.get(field)

        if field not in schema.create_fields:
            warnings.append(
                f"'{field}' is not a writable field for {schema.odoo_model}"
            )
            continue

        if old_value != new_value:
            changes[field] = {"old": old_value, "new": new_value}
        else:
            unchanged.append(field)

    # Fields in current_values but NOT in params are unchanged
    for field in current_values:
        if field not in params and field not in unchanged:
            unchanged.append(field)

    return {
        "status": "success",
        "changes": changes,
        "unchanged": unchanged,
        "warnings": warnings,
    }
