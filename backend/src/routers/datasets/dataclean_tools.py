"""
AI data-cleaning tools — thin wrappers over existing backend functions.

Each executor calls existing code (``datasets.schema.fetch_dataset_overview``,
``datasets.data_fetch.get_dataset_data``, and the ``datasets.transforms`` CRUD
helpers); no validation or storage logic is re-implemented. The data-cleaning
concierge manages the same ``DataPreparationRule`` rows the manual transform
editor uses.

Still deferred: ``preview_rule`` (needs a plain preview helper extracted
from ``preparation.py``).
"""

import re

from fastapi import HTTPException

from src.chat.tool_agent import register_tool, tool_error
from src.routers.datasets.schema import fetch_dataset_overview, fetch_dataset_schema
from src.utils.translation import t
from .translations import DATASETS
from .preparation import _apply_operations_to_dataset, _sanitize_snapshot, _null_counts
from src.routers.datasets.transforms import (
    TransformOperation,
    create_transform_record,
    delete_transform_record,
    fetch_dataset_transforms,
    fetch_transform,
    update_transform_record,
)
from src.routers.datasets.data_fetch import get_dataset_data


def _as_operations(ops: list) -> list:
    """Convert the LLM's operation dicts into TransformOperation models."""
    return [TransformOperation(**op) for op in (ops or [])]


# ── get_schema ──────────────────────────────────────────────────

async def _exec_get_schema(agent, dataset_id: str, **args) -> dict:
    try:
        return await fetch_dataset_overview(dataset_id, agent.user_id, agent.language)
    except HTTPException as e:
        return tool_error("get_schema", e, agent=agent)


# ── sample_rows ─────────────────────────────────────────────────

async def _exec_sample_rows(agent, dataset_id: str, limit: int = 5, **args) -> dict:
    try:
        columns, rows = await get_dataset_data(
            agent.db_pool, agent.user_id, dataset_id, agent.language, limit=int(limit)
        )
        return {"columns": columns, "rows": rows, "row_count": len(rows)}
    except ValueError as e:
        return tool_error("sample_rows", e, agent=agent)


# ── list_rules ──────────────────────────────────────────────────

async def _exec_list_rules(agent, dataset_id: str, **args) -> dict:
    try:
        return await fetch_dataset_transforms(dataset_id, agent.user_id, agent.language)
    except HTTPException as e:
        return tool_error("list_rules", e, agent=agent)


# ── add_rule ────────────────────────────────────────────────────

async def _exec_add_rule(
    agent, dataset_id: str, name: str, operations: list,
    description: str = None, shared: bool = False, **args
) -> dict:
    try:
        return await create_transform_record(
            dataset_id, agent.user_id, name, description,
            _as_operations(operations), shared, agent.language,
        )
    except HTTPException as e:
        return tool_error("add_rule", e, agent=agent)


# ── update_rule ─────────────────────────────────────────────────

async def _exec_update_rule(
    agent, dataset_id: str, rule_id: str,
    name: str = None, description: str = None, operations: list = None,
    rule_group: str = None, **args
) -> dict:
    try:
        return await update_transform_record(
            dataset_id, rule_id, agent.user_id,
            name, description,
            _as_operations(operations) if operations is not None else None,
            rule_group, agent.language,
        )
    except HTTPException as e:
        return tool_error("update_rule", e, agent=agent)


# ── delete_rule ─────────────────────────────────────────────────

async def _exec_delete_rule(agent, dataset_id: str, rule_id: str, **args) -> dict:
    try:
        return await delete_transform_record(dataset_id, rule_id, agent.user_id, agent.language)
    except HTTPException as e:
        return tool_error("delete_rule", e, agent=agent)


# ── detect_issues (profiling — the one genuinely new computation) ──

_DATE_RE = re.compile(
    r"^\d{4}-\d{1,2}-\d{1,2}([ T]\d{1,2}:\d{2})?"
    r"|^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$"
)


def _as_float(value):
    if value is None or isinstance(value, bool):
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _is_numeric(value):
    return _as_float(value) is not None


def _quantile(sorted_vals, q):
    if not sorted_vals:
        return 0.0
    n = len(sorted_vals)
    idx = q * (n - 1)
    lo = int(idx)
    hi = min(lo + 1, n - 1)
    frac = idx - lo
    return sorted_vals[lo] * (1.0 - frac) + sorted_vals[hi] * frac


def _row_key(row, columns):
    import json
    return json.dumps({c: row.get(c) for c in columns}, sort_keys=True, default=str)


def _profile_dataset(schema: dict, columns: list, rows: list) -> dict:
    """Profile a dataset: nulls, duplicate rows, numeric outliers (IQR), type issues."""
    total_rows = len(rows)
    col_meta = {c.get("name"): c for c in (schema.get("columns") or [])}

    null_counts = {c: 0 for c in columns}
    for r in rows:
        for c in columns:
            if r.get(c) is None:
                null_counts[c] += 1

    seen = set()
    duplicate_rows = 0
    for r in rows:
        key = _row_key(r, columns)
        if key in seen:
            duplicate_rows += 1
        else:
            seen.add(key)

    numeric_types = {
        "integer", "bigint", "smallint", "decimal", "numeric", "real",
        "double precision", "float", "int", "double",
    }
    outliers = {}
    for c in columns:
        meta = col_meta.get(c, {})
        if not (meta.get("is_numeric") or (meta.get("type") or "").lower() in numeric_types):
            continue
        vals = [v for v in (_as_float(r.get(c)) for r in rows) if v is not None]
        if len(vals) < 4:
            continue
        svals = sorted(vals)
        q1 = _quantile(svals, 0.25)
        q3 = _quantile(svals, 0.75)
        iqr = q3 - q1
        if iqr <= 0:
            continue
        lo = q1 - 1.5 * iqr
        hi = q3 + 1.5 * iqr
        out = [v for v in vals if v < lo or v > hi]
        if out:
            outliers[c] = {
                "count": len(out),
                "low": round(lo, 6),
                "high": round(hi, 6),
                "values": out[:20],
            }

    type_inconsistencies = []
    for c in columns:
        meta = col_meta.get(c, {})
        non_null = [r.get(c) for r in rows if r.get(c) is not None]
        if meta.get("is_numeric"):
            bad = sum(1 for v in non_null if not _is_numeric(v))
            if bad:
                type_inconsistencies.append({
                    "column": c, "issue": "non_numeric_value_in_numeric_column", "count": bad,
                })
        else:
            if meta.get("is_datetime"):
                continue  # a real date column is not "date stored as text"
            strs = [str(v) for v in non_null]
            date_like = sum(1 for v in strs if _DATE_RE.match(v))
            if strs and date_like >= len(strs) * 0.5:
                type_inconsistencies.append({
                    "column": c, "issue": "date_like_values_in_text_column", "count": date_like,
                })

    return {
        "total_rows": total_rows,
        "total_columns": len(columns),
        "null_counts": null_counts,
        "duplicate_rows": duplicate_rows,
        "outliers": outliers,
        "type_inconsistencies": type_inconsistencies,
    }


async def _exec_detect_issues(agent, dataset_id: str, **args) -> dict:
    try:
        # Columns only. `_profile_dataset` counts the rows it fetched
        # (`total_rows = len(rows)`), so the overview's COUNT(*) would be a
        # second count of the same table, discarded.
        schema = await fetch_dataset_schema(dataset_id, agent.user_id, agent.language)
        columns, rows = await get_dataset_data(
            agent.db_pool, agent.user_id, dataset_id, agent.language, limit=0
        )
        return _profile_dataset(schema, columns, rows)
    except (HTTPException, ValueError) as e:
        return tool_error("detect_issues", e, agent=agent)


# ── preview_rule (see a rule's effect without materialising) ───


async def _exec_preview_rule(
    agent, dataset_id, rule_ids=None, operations=None, limit=10, **args
) -> dict:
    try:
        ops = list(operations or [])
        if rule_ids:
            for rid in rule_ids:
                rule = await fetch_transform(dataset_id, rid, agent.user_id, agent.language)
                ops.extend(rule.get("transform", {}).get("operations") or [])
        if not ops:
            return {"error": await t(agent.db_pool, agent.language, DATASETS["dataclean_tools.no_rules_to_preview"])}

        before_columns, before_rows = await get_dataset_data(
            agent.db_pool, agent.user_id, dataset_id, agent.language
        )
        columns, rows = await _apply_operations_to_dataset(
            agent.db_pool, agent.user_id, dataset_id, ops, agent.language
        )

        return {
            "before_rows": len(before_rows),
            "after_rows": len(rows),
            "before_nulls": _null_counts(before_columns, before_rows),
            "after_nulls": _null_counts(columns, rows),
            "columns": columns,
            "sample": _sanitize_snapshot(rows, int(limit)),
        }
    except (HTTPException, ValueError) as e:
        return tool_error("preview_rule", e, agent=agent)


# ── Tool schemas (OpenAI function format) ───────────────────────
#
# Registered and scoped in Item 7. Names intentionally differ from the recipe
# concierge's (get_dataset_transforms / create_transform / …) to avoid registry
# collisions while wrapping the same helpers.

_OPERATIONS_DESCRIPTION = (
    "A list of steps; each step has a type and type-specific fields. "
    "Valid types: filter (column, operator, value), "
    "fill_missing (column, method: mean|median|mode|constant|drop, value), "
    "convert_type (column, target_type: numeric|datetime|string|boolean), "
    "normalize (columns), standardize (columns), "
    "encode (column, encoding: one_hot|label), "
    "drop_duplicates (columns), drop_columns (columns), rename_column (column, new_name)."
)

_GET_SCHEMA_SCHEMA = {
    "type": "function",
    "function": {
        "name": "get_schema",
        "description": "Return the schema of a dataset (columns, types, counts, source/storage).",
        "parameters": {
            "type": "object",
            "properties": {"dataset_id": {"type": "string", "description": "Dataset id"}},
            "required": ["dataset_id"],
        },
    },
}

_SAMPLE_ROWS_SCHEMA = {
    "type": "function",
    "function": {
        "name": "sample_rows",
        "description": "Return a small sample of a dataset's rows (default 5).",
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset id"},
                "limit": {"type": "integer", "description": "Max rows to return (default 5)."},
            },
            "required": ["dataset_id"],
        },
    },
}

_LIST_RULES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "list_rules",
        "description": "List the transforms (preparation rules) for a dataset, with ids, names, descriptions and operations.",
        "parameters": {
            "type": "object",
            "properties": {"dataset_id": {"type": "string", "description": "Dataset id"}},
            "required": ["dataset_id"],
        },
    },
}

_ADD_RULE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "add_rule",
        "description": "Create a new transform (preparation rule) for a dataset. " + _OPERATIONS_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset id"},
                "name": {"type": "string", "description": "Rule name"},
                "operations": {"type": "array", "description": _OPERATIONS_DESCRIPTION},
                "description": {"type": "string", "description": "Optional description"},
                "shared": {"type": "boolean", "description": "Share with the user's group"},
            },
            "required": ["dataset_id", "name", "operations"],
        },
    },
}

_UPDATE_RULE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "update_rule",
        "description": "Update an existing transform (preparation rule); omit a field to leave it unchanged. " + _OPERATIONS_DESCRIPTION,
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset id"},
                "rule_id": {"type": "string", "description": "Rule id"},
                "name": {"type": "string", "description": "New name (optional)"},
                "description": {"type": "string", "description": "New description (optional)"},
                "operations": {"type": "array", "description": _OPERATIONS_DESCRIPTION},
                "rule_group": {"type": "string", "description": "Group (optional)"},
            },
            "required": ["dataset_id", "rule_id"],
        },
    },
}

_DELETE_RULE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "delete_rule",
        "description": "Delete a transform (preparation rule) from a dataset.",
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset id"},
                "rule_id": {"type": "string", "description": "Rule id"},
            },
            "required": ["dataset_id", "rule_id"],
        },
    },
}

_DETECT_ISSUES_SCHEMA = {
    "type": "function",
    "function": {
        "name": "detect_issues",
        "description": (
            "Profile a dataset and report data-quality issues: null counts, "
            "duplicate rows, numeric outliers (IQR), and type inconsistencies."
        ),
        "parameters": {
            "type": "object",
            "properties": {"dataset_id": {"type": "string", "description": "Dataset id"}},
            "required": ["dataset_id"],
        },
    },
}

_PREVIEW_RULE_SCHEMA = {
    "type": "function",
    "function": {
        "name": "preview_rule",
        "description": (
            "Preview the effect of preparation rules (or the given operations) "
            "on a dataset: before/after row and null counts plus a sample of the result."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "dataset_id": {"type": "string", "description": "Dataset id"},
                "rule_ids": {"type": "array", "items": {"type": "string"}, "description": "Optional rule ids to preview"},
                "operations": {"type": "array", "description": "Optional inline operations to preview"},
                "limit": {"type": "integer", "description": "Sample size (default 10)"},
            },
            "required": ["dataset_id"],
        },
    },
}


# ── Registration (scoped allow-list) ─────────────────────────

_DATACLEAN_TOOLS = [
    ("get_schema", _GET_SCHEMA_SCHEMA, _exec_get_schema),
    ("sample_rows", _SAMPLE_ROWS_SCHEMA, _exec_sample_rows),
    ("list_rules", _LIST_RULES_SCHEMA, _exec_list_rules),
    ("add_rule", _ADD_RULE_SCHEMA, _exec_add_rule),
    ("update_rule", _UPDATE_RULE_SCHEMA, _exec_update_rule),
    ("delete_rule", _DELETE_RULE_SCHEMA, _exec_delete_rule),
    ("detect_issues", _DETECT_ISSUES_SCHEMA, _exec_detect_issues),
    ("preview_rule", _PREVIEW_RULE_SCHEMA, _exec_preview_rule),
]

# Allow-list passed to run_tool_loop so the dataclean concierge only sees its own tools.
DATACLEAN_TOOL_NAMES = [name for name, _, _ in _DATACLEAN_TOOLS] + ["report_unsupported"]


# The data-cleaning concierge's own registry.
DATACLEAN_REGISTRY = "dataclean"


def register_all_tools() -> None:
    """Register the data-cleaning tools into the shared tool registry."""
    for name, schema, executor in _DATACLEAN_TOOLS:
        register_tool(DATACLEAN_REGISTRY, name, schema, executor)
