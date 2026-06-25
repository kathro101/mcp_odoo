"""Stateless Odoo analytics operations.

Pure functions for read_group aggregation.  No classes, no state.
"""

from __future__ import annotations

from src.odoo_service.odoo_client import OdooClient
from src.shared.types import ModelSchema


def aggregate(
    odoo: OdooClient,
    schema: ModelSchema,
    group_by: str,
    metric: str = "count",
    domain: list | None = None,
) -> dict:
    """Aggregate records using Odoo's read_group.

    Args:
        odoo: OdooClient instance.
        schema: ModelSchema for the target model.
        group_by: Field to group by (e.g. 'state', 'partner_id').
        metric: Aggregation metric.
            - 'count': record count per group (default)
            - 'sum:<field>': sum of a numeric field
            - 'avg:<field>': average of a numeric field
        domain: Optional Odoo domain filter.

    Returns:
        {"status": "success", "groups": [{"key": "draft", "value": 15}, ...]}
        or {"status": "error", "message": "..."}
    """
    # Parse metric
    aggregate_spec: str
    if metric == "count":
        aggregate_spec = f"{group_by}:count"
    elif metric.startswith("sum:"):
        field = metric[4:]
        aggregate_spec = f"{field}:sum"
    elif metric.startswith("avg:"):
        field = metric[4:]
        aggregate_spec = f"{field}:avg"
    else:
        aggregate_spec = f"{group_by}:count"

    # read_group expects a list of domains (AND-ed)
    domain_list = list(domain) if domain else []

    result = odoo.execute_kw(
        schema.odoo_model,
        "read_group",
        [domain_list, [aggregate_spec], [group_by]],
    )

    if isinstance(result, dict) and result.get("status") == "error":
        return result

    groups: list[dict] = []
    for row in result or []:
        key = row.get(group_by, "")
        if isinstance(key, list | tuple):
            key = key[1] if len(key) > 1 else str(key)

        if metric == "count":
            suffix = f"{group_by}_count"
        elif metric.startswith("sum:") or metric.startswith("avg:"):
            suffix = field
        else:
            suffix = f"{group_by}_count"

        raw_value = row.get(suffix, 0)
        if metric.startswith("avg:") and "__count" in row:
            try:
                value = float(raw_value) / float(row["__count"])
            except (ZeroDivisionError, ValueError, TypeError):
                value = float(raw_value)
        else:
            value = raw_value

        groups.append({"key": str(key), "value": value})

    return {"status": "success", "groups": groups}


def count_by_state(odoo: OdooClient, schema: ModelSchema) -> dict:
    """Convenience: count records grouped by the 'state' field.

    Args:
        odoo: OdooClient instance.
        schema: ModelSchema for the target model.

    Returns:
        {"status": "success", "counts": {"draft": 15, "done": 42}}
        or {"status": "error", "message": "..."}
    """
    if "state" not in schema.all_fields:
        return {
            "status": "error",
            "message": f"Model {schema.odoo_model} has no 'state' field",
        }

    result = aggregate(odoo, schema, group_by="state", metric="count")

    if result["status"] == "error":
        return result

    counts = {g["key"]: g["value"] for g in result["groups"]}
    return {"status": "success", "counts": counts}
