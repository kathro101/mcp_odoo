"""Stateless Odoo delete operations.

Pure functions for record deletion and confirmation.  No classes, no state.
"""

from __future__ import annotations

from src.odoo_service.odoo_client import OdooClient
from src.shared.types import ModelSchema


def delete_record(
    odoo: OdooClient,
    schema: ModelSchema,
    record_id: int,
) -> dict:
    """Delete an Odoo record by ID.

    Args:
        odoo: OdooClient instance.
        schema: ModelSchema for the target model.
        record_id: ID of the record to delete.

    Returns:
        {"status": "success", "record_id": <int>}
        or {"status": "error", "message": "..."}
    """
    result = odoo.execute_kw(schema.odoo_model, "unlink", [[record_id]])

    if isinstance(result, dict) and result.get("status") == "error":
        return result

    return {
        "status": "success",
        "record_id": record_id,
    }


def confirm_delete(
    schema: ModelSchema,
    record_data: dict,
) -> dict:
    """Generate a human-readable confirmation summary before deletion.

    Does NOT call Odoo.

    Args:
        schema: ModelSchema for the target model.
        record_data: Dict of the record's current field values.

    Returns:
        {"status": "confirm", "record_summary": "...", "record_id": <int>}
    """
    record_id = record_data.get("id", "unknown")

    # Build a descriptive identifier from the record data
    name = record_data.get("name", "")
    if isinstance(name, (list, tuple)):
        name = name[0] if name else ""

    identifier = f"{name} (ID: {record_id})" if name else f"Record ID: {record_id}"

    summary = (
        f"Delete {schema.label}: {identifier}\n"
        f"Model: {schema.odoo_model}\n"
        f"This action cannot be undone."
    )

    return {
        "status": "confirm",
        "record_summary": summary,
        "record_id": record_id,
    }
