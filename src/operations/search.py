"""Stateless Odoo search operations.

Pure functions that take OdooClient + ModelSchema + parameters →
return structured result dicts.  No classes, no state, no AI.
"""

from __future__ import annotations

import contextlib

from src.odoo_service.odoo_client import OdooClient
from src.shared.types import ModelSchema


def search_records(
    odoo: OdooClient,
    schema: ModelSchema,
    filters: dict[str, str],
    limit: int = 20,
    offset: int = 0,
) -> dict:
    """Search for records in an Odoo model.

    Args:
        odoo: OdooClient instance.
        schema: ModelSchema for the target model.
        filters: Dict of field_name -> search_value. Uses ilike matching.
        limit: Max records to return.
        offset: Number of records to skip.

    Returns:
        {"status": "success", "records": [...], "count": N}
        or {"status": "error", "message": "..."}
    """
    domain = []
    for field, value in (filters or {}).items():
        if not value:
            continue
        fi = schema.all_fields.get(field)
        if fi and fi.field_type in ("integer", "float", "monetary", "many2one"):
            with contextlib.suppress(ValueError, TypeError):
                value = int(value)
            domain.append((field, "=", value))
        else:
            domain.append((field, "ilike", str(value)))

    result = odoo.search_read(
        schema.odoo_model,
        domain,
        fields=schema.search_fields or None,
        limit=limit,
        offset=offset,
    )

    if isinstance(result, dict) and result.get("status") == "error":
        return result

    return {
        "status": "success",
        "records": result,
        "count": len(result),
    }
