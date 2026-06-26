"""Stateless Odoo create operations.

Pure functions for record creation and preview.  No classes, no state.
"""

from __future__ import annotations

from src.odoo_service.odoo_client import OdooClient
from src.shared.types import ModelSchema


def _build_odoo_url(url: str, database: str, model: str, record_id: int) -> str:
    """Build a clickable Odoo record URL.

    Uses Odoo's /web#id=X&model=Y&view_type=form format which works
    across Odoo versions and doesn't require knowing the menu/action ID.

    Args:
        url: Base Odoo URL (e.g. https://example.odoo.com).
        database: Odoo database name.
        model: Odoo model technical name (e.g. sale.order).
        record_id: Record ID.

    Returns:
        Full Odoo record URL string, or empty string if url/model/record_id missing.
    """
    if not url or not model or not record_id:
        return ""
    base = url.rstrip("/")
    return f"{base}/web#id={record_id}&model={model}&view_type=form"


def preview_record(schema: ModelSchema, params: dict) -> dict:
    """Preview what a record creation would look like.

    Checks which required fields are provided vs missing, validates field
    types where possible, and provides per-field guidance for any issues.
    Does NOT call Odoo.

    Args:
        schema: ModelSchema for the target model.
        params: Dict of field_name -> value for the new record.

    Returns:
        {"status": "success"|"needs_input", "filled": [...], "missing": [...],
         "optional": [...], "guidance": {field_name: str}, "warnings": [...]}
    """
    params = params or {}
    filled: list[str] = []
    missing: list[str] = []
    optional: list[str] = []
    guidance: dict[str, str] = {}
    warnings: list[str] = []

    for f in schema.required_fields:
        fi = schema.all_fields.get(f)
        value = params.get(f)

        if value is None or value == "":
            missing.append(f)
            guidance[f] = _field_missing_guidance(fi)
        elif fi and not _is_valid_value(fi, value):
            warnings.append(
                f"`{f}` has value `{value}` but expects type `{fi.field_type}`. "
                f"Value will be passed to Odoo but may be rejected."
            )
            filled.append(f)
        else:
            filled.append(f)

    for f in schema.create_fields:
        if f not in schema.required_fields and f in params and params[f]:
            optional.append(f)

    if missing or warnings:
        return {
            "status": "needs_input",
            "filled": filled,
            "missing": missing,
            "optional": optional,
            "guidance": guidance,
            "warnings": warnings,
            "message": _build_preview_message(missing, warnings),
        }

    return {
        "status": "success",
        "filled": filled,
        "missing": [],
        "optional": optional,
        "guidance": {},
        "warnings": [],
        "message": "All required fields provided with valid values",
    }


def _is_valid_value(fi, value) -> bool:
    """Check if a value is plausible for the given field type.

    This is a soft check — Odoo does the final validation. We just
    flag obviously wrong types (string for integer field, etc.).
    """
    if fi is None:
        return True  # Can't validate, let Odoo decide

    if fi.field_type in ("many2one", "many2many", "one2many"):
        # Should be an integer ID, or a list of IDs
        if isinstance(value, int):
            return True
        if isinstance(value, list):
            return all(isinstance(v, int) for v in value)
        # String might be a name — Odoo can try name_search, so allow it
        return isinstance(value, str)

    if fi.field_type in ("integer",):
        return isinstance(value, int) or (isinstance(value, str) and value.isdigit())

    if fi.field_type in ("float", "monetary"):
        return isinstance(value, int | float) or (isinstance(value, str) and _is_numeric(value))

    if fi.field_type == "boolean":
        return isinstance(value, bool) or value in (0, 1, "0", "1", "true", "false")

    # char, text, date, datetime, selection, binary, html — accept as-is
    return True


def _is_numeric(s: str) -> bool:
    """Check if a string represents a numeric value."""
    try:
        float(s)
        return True
    except (ValueError, TypeError):
        return False


def _field_missing_guidance(fi) -> str:
    """Generate guidance text for a missing required field."""
    if fi is None:
        return "This field is required."
    label = fi.string or fi.name
    ftype = fi.field_type
    if fi.selection:
        options = ", ".join(s[0] for s in fi.selection)
        return f"{label}: choose from [{options}]"
    if ftype == "many2one":
        target = fi.relation or "record"
        return f"{label}: search for a {target} record to link"
    if ftype == "many2many":
        target = fi.relation or "records"
        return f"{label}: search for {target} records to link"
    if ftype in ("integer", "float", "monetary"):
        return f"{label}: provide a numeric value"
    if ftype in ("date", "datetime"):
        return f"{label}: provide a date"
    if ftype == "boolean":
        return f"{label}: specify yes or no"
    return f"{label}: provide a value (type: {ftype})"


def _build_preview_message(missing: list[str], warnings: list[str]) -> str:
    """Build a human-readable message summarizing preview issues."""
    parts: list[str] = []
    if missing:
        parts.append(f"Missing required fields: {', '.join(missing)}")
    if warnings:
        parts.append("Warnings: " + "; ".join(warnings))
    return ". ".join(parts)


def create_record(odoo: OdooClient, schema: ModelSchema, params: dict) -> dict:
    """Create a new record in Odoo.

    Args:
        odoo: OdooClient instance.
        schema: ModelSchema for the target model.
        params: Dict of field_name -> value for the new record.

    Returns:
        {"status": "success", "record_id": <int>, "odoo_url": "<url>"}
        or {"status": "error", "message": "..."}
    """
    result = odoo.execute_kw(schema.odoo_model, "create", [params])

    if isinstance(result, dict) and result.get("status") == "error":
        return result

    return {
        "status": "success",
        "record_id": result,
        "odoo_url": _build_odoo_url(
            url=odoo.url,
            database=odoo.database,
            model=schema.odoo_model,
            record_id=result,
        ),
    }
