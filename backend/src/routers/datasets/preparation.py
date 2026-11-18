"""
Data Preparation Rules – CRUD operations for dataset preparation rules.
Part of the 0.0.10 "Statistical Foundation" milestone.
"""

import os
import math
import uuid
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any, Literal
import logging

logger = logging.getLogger("uvicorn.trace")


def _sanitize_json(records: list) -> list:
    """Replace NaN/Inf with None so the data is JSON-serializable."""
    for record in records:
        for k, v in record.items():
            if isinstance(v, float) and (math.isnan(v) or math.isinf(v)):
                record[k] = None
    return records

from .crud import get_user_id_from_token, get_current_language, can_edit_dataset
from src.routers.datasets.data_fetch import get_dataset_data
from src.routers.datasets.data_access import (
    preview_preparation_rule,
    _is_missing,
    _is_numeric_value,
    _is_datetime_value,
    _to_numeric,
    _to_datetime,
    _sort_key,
    _one_hot_encode,
    _fill_value,
    execute_compiled_sql_rows,
)
from src.routers.datasets.sql_dialect import compile_sql, split_operations
from src.utils.translation import t
from src.routers.common.translations import (
    error_dataset_load_failed_3,
    error_dataset_load_failed_4,
)
from .translations import PREPARATION, DATASETS
from .validation import (
    validate_operations,
    VALID_OPERATION_TYPES,
    FILL_MISSING_METHODS,
    ENCODING_TYPES,
    TARGET_TYPES,
)
from .transforms import (
    compute_content_hash,
    fetch_transform,
    fetch_dataset_transforms,
)
from src.postgres_data_manager import json_safe, create_table_from_rows, DATA_DB_NAME, user_schema_name
from src.routers.datasets.virtual import materialize_virtual_dataset

router = APIRouter()
security = HTTPBearer()

_db_pool = None

# How many rows of the before/after preview the cleaning endpoints carry. Raised
# from 10 on 2026-09-25 for the same reason the notebook preview and the join
# preview were: the corpus Item 12 observes is fourteen rows, and a ten-row window
# cannot show its last four. The panel draws everything it is sent, inside a
# bounded scroller.
_PREVIEW_SAMPLE_ROWS = 20

def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ============================================================
# REQUEST MODELS
# ============================================================

class PreparationOperation(BaseModel):
    """A single preparation operation."""
    type: str  # "filter", "fill_missing", "convert_type", "normalize", "standardize", "encode", "drop_duplicates", "drop_columns", "rename_column"
    column: Optional[str] = None
    columns: Optional[List[str]] = None
    operator: Optional[str] = None
    value: Optional[Any] = None
    method: Optional[str] = None  # "mean", "median", "mode", "constant", "drop"
    target_type: Optional[str] = None  # "numeric", "datetime", "string", "boolean"
    new_name: Optional[str] = None
    encoding: Optional[str] = None  # "one_hot", "label"


class CreatePreparationRuleRequest(BaseModel):
    """Request model for creating a preparation rule."""
    name: str
    description: Optional[str] = None
    operations: List[PreparationOperation]
    shared: bool = False
    ruleGroup: str = "00"


class UpdatePreparationRuleRequest(BaseModel):
    """Request model for updating a preparation rule."""
    name: Optional[str] = None
    description: Optional[str] = None
    operations: Optional[List[PreparationOperation]] = None
    shared: Optional[bool] = None
    ruleGroup: Optional[str] = None


class PreviewPreparationRuleRequest(BaseModel):
    """Request model for previewing a preparation rule."""
    rule_id: Optional[str] = None
    operations: Optional[List[dict]] = None
    limit: int = _PREVIEW_SAMPLE_ROWS


class CleanRequest(BaseModel):
    """Request model for cleaning a dataset (copy or in-place)."""
    mode: Literal["copy", "in_place"] = "copy"
    name: Optional[str] = None
    rule_ids: Optional[List[str]] = None
    description: Optional[str] = None
    shared: bool = False


# Validation constants and function are shared with transforms.py
# via backend/src/routers/datasets/validation.py


def _label_encode_column(rows, col):
    """In-place label encode a column (sorted unique values; missing stays None)."""
    unique = sorted({r.get(col) for r in rows if not _is_missing(r.get(col))}, key=_sort_key)
    code = {v: i for i, v in enumerate(unique)}
    for r in rows:
        v = r.get(col)
        r[col] = code[v] if not _is_missing(v) else None


def _drop_duplicates(rows, subset):
    """Drop duplicate rows (optionally on a column subset), preserving first occurrence."""
    seen = set()
    out = []
    for r in rows:
        if subset:
            key = tuple(repr(r.get(c)) for c in subset)
        else:
            key = tuple((k, repr(r.get(k))) for k in sorted(r.keys()))
        if key not in seen:
            seen.add(key)
            out.append(r)
    return out


def _null_counts(columns, rows):
    """Count missing values per column."""
    return {col: sum(1 for r in rows if _is_missing(r.get(col))) for col in columns}


def _apply_operation_in_memory(columns, rows, op: dict):
    """Apply a single operation to a table of rows in-memory (no pandas)."""
    op_type = op.get("type", "")
    col = op.get("column", None)

    if op_type == "filter" and col:
        operator = op.get("operator", "=")
        value = op.get("value", None)
        if value is not None and col in columns:
            if operator == ">":
                rows = [r for r in rows if not _is_missing(r.get(col)) and r[col] > float(value)]
            elif operator == "<":
                rows = [r for r in rows if not _is_missing(r.get(col)) and r[col] < float(value)]
            elif operator == "=":
                rows = [r for r in rows if r.get(col) == value]
            elif operator == "!=":
                rows = [r for r in rows if r.get(col) != value]
            elif operator == "contains":
                rows = [r for r in rows if not _is_missing(r.get(col)) and str(value) in str(r[col])]
            elif operator == "is_null":
                rows = [r for r in rows if _is_missing(r.get(col))]
            elif operator == "is_not_null":
                rows = [r for r in rows if not _is_missing(r.get(col))]

    elif op_type == "fill_missing" and col:
        strategy = op.get("method", "median")
        if col in columns:
            if strategy == "drop":
                rows = [r for r in rows if not _is_missing(r.get(col))]
            else:
                fill = op.get("value", 0) if strategy == "constant" else _fill_value(rows, col, strategy, op)
                if fill is None:
                    fill = 0
                for r in rows:
                    if _is_missing(r.get(col)):
                        r[col] = fill

    elif op_type == "drop_column" and col and col in columns:
        columns = [c for c in columns if c != col]
        for r in rows:
            r.pop(col, None)

    elif op_type == "drop_columns":
        existing_cols = [c for c in (op.get("columns") or []) if c in columns]
        if existing_cols:
            columns = [c for c in columns if c not in existing_cols]
            for r in rows:
                for c in existing_cols:
                    r.pop(c, None)

    elif op_type == "convert_type" and col and col in columns:
        target = op.get("target_type", "numeric")
        if target == "numeric":
            for r in rows:
                r[col] = _to_numeric(r.get(col))
        elif target == "datetime":
            for r in rows:
                r[col] = _to_datetime(r.get(col))
        elif target == "string":
            for r in rows:
                v = r.get(col)
                r[col] = str(v) if not _is_missing(v) else None

    elif op_type in ("normalize", "standardize"):
        for c in (op.get("columns") or []):
            if c in columns:
                numeric = [r[c] for r in rows if not _is_missing(r.get(c))]
                if not numeric or not all(_is_numeric_value(v) for v in numeric):
                    continue
                if op_type == "normalize":
                    min_val = min(numeric)
                    max_val = max(numeric)
                    for r in rows:
                        if not _is_missing(r.get(c)):
                            r[c] = (r[c] - min_val) / (max_val - min_val) if max_val > min_val else 0
                else:
                    mean = sum(numeric) / len(numeric)
                    variance = sum((v - mean) ** 2 for v in numeric) / (len(numeric) - 1) if len(numeric) > 1 else 0
                    std = math.sqrt(variance)
                    for r in rows:
                        if not _is_missing(r.get(c)):
                            r[c] = (r[c] - mean) / std if std > 0 else 0

    elif op_type == "rename_column" and col and col in columns:
        new_name = op.get("new_name", None)
        if new_name:
            columns = [new_name if c == col else c for c in columns]
            for r in rows:
                r[new_name] = r.pop(col)

    elif op_type == "drop_duplicates":
        rows = _drop_duplicates(rows, op.get("columns", None))

    elif op_type in ("encode", "encode_category") and col and col in columns:
        encoding = op.get("encoding", "one_hot")
        if encoding == "label":
            _label_encode_column(rows, col)
        elif encoding == "one_hot":
            columns, rows = _one_hot_encode(columns, rows, col)

    return columns, rows


# ── data-cleaning helpers (moved from dataclean_tools.py) ─────

def _sanitize_snapshot(rows, limit=10):
    """Return JSON-safe row dicts, matching upload's dataSnapshot (json_safe)."""
    return [json_safe(r) for r in rows[:limit]]


async def _apply_operations_to_dataset(db_pool, user_id, dataset_id, operations, language):
    """Apply transform operations to a dataset's data → (columns, rows).

    Mirrors the preparation preview endpoint: SQL pushdown for ops the backend
    can execute natively, in-memory for the rest.
    """
    storage_type = "postgresql"
    table_name = "data"
    all_columns = []
    async with db_pool.acquire() as conn:
        # The dataset must be one the caller can *see* — their own, or one shared to
        # their group; the operations are applied to that dataset's data (Gap C).
        ds_row = await conn.fetchrow(
            """
            SELECT "sourceType", "storageType", "tableName", "dataSnapshot", "virtualSql"
            FROM "UserDataset"
            WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                SELECT "userGroup" FROM "User" WHERE id = $2
            )))
            """,
            dataset_id, user_id,
        )
    if ds_row:
        storage_type = ds_row["storageType"] or "postgresql"
        table_name = ds_row["tableName"] or "data"
        snapshot = ds_row["dataSnapshot"]
        all_columns = snapshot.get("columns", []) if isinstance(snapshot, dict) else []

    # Virtual datasets have no native SQL backend — materialise the join into a
    # local PG table (virtual_{id}) and push down against it, matching the recipe
    # data-selection stream in recipes/execute.py.
    if ds_row and ds_row["sourceType"] == "virtual":
        import json as _json
        virtual_sql = ds_row["virtualSql"]
        virtual_sql = _json.loads(virtual_sql) if isinstance(virtual_sql, str) else virtual_sql
        if not virtual_sql:
            raise ValueError(
                await t(db_pool, language, error_dataset_load_failed_3, id=dataset_id)
            )
        try:
            table_name, all_columns, _ = await materialize_virtual_dataset(
                dataset_id, virtual_sql, user_id, db_pool, language
            )
        except Exception as e:
            raise ValueError(
                await t(db_pool, language, error_dataset_load_failed_4, id=dataset_id, error=str(e))
            )
        storage_type = "postgresql"

    sql_ops, python_ops = split_operations(operations, storage_type)

    if sql_ops:
        compiled_sql = compile_sql(sql_ops, storage_type, table_name, all_columns)
        columns, rows, _ = await execute_compiled_sql_rows(
            compiled_sql, db_pool, user_id, dataset_id, language
        )
    else:
        columns, rows = await get_dataset_data(db_pool, user_id, dataset_id, language)

    for op in python_ops:
        columns, rows = _apply_operation_in_memory(columns, rows, op)

    return columns, rows


async def _materialise_cleaned_table(
    db_pool, user_id, dataset_id, rule_ids, operations, language
):
    """Apply the dataset's rules (or the given rule_ids/operations) and
    materialise the cleaned rows into a NEW workbench_data table.

    Shared by "Clean copy" (INSERT a new UserDataset row) and "Clean in place"
    (UPDATE the existing row's tableName/dataSnapshot).

    Returns ``(columns, rows, table_name, ops)``, where ``table_name`` is the
    schema-qualified name of the materialised table.
    """
    ops = list(operations or [])
    if rule_ids:
        for rid in rule_ids:
            rule = await fetch_transform(dataset_id, rid, user_id, language)
            ops.extend(rule.get("transform", {}).get("operations") or [])
    elif not ops:
        result = await fetch_dataset_transforms(dataset_id, user_id, language)
        for tr in result.get("transforms", []):
            ops.extend(tr.get("operations") or [])

    if not ops:
        raise ValueError(await t(db_pool, language, DATASETS["dataclean_tools.no_rules_to_apply"]))

    columns, rows = await _apply_operations_to_dataset(
        db_pool, user_id, dataset_id, ops, language
    )

    # Materialise into a NEW workbench_data table — the source is never written.
    # It lands in the owning account's schema, like every other object the
    # application creates there, and that qualified name is what the dataset row
    # records.
    table_name = f"{user_schema_name(user_id)}.clean_{uuid.uuid4().hex[:12]}"
    await create_table_from_rows(columns, rows, table_name)

    return columns, rows, table_name, ops


async def _save_cleaned_copy(
    db_pool, user_id, dataset_id, name, rule_ids, operations, description, shared, language
):
    """Materialise a cleaned copy as a NEW derived dataset (never in-place)."""
    columns, rows, table_name, ops = await _materialise_cleaned_table(
        db_pool, user_id, dataset_id, rule_ids, operations, language
    )

    # Provenance: record the original source type and the parent dataset id.
    async with db_pool.acquire() as conn:
        # Same visibility rule as the read above: an invisible dataset has no readable
        # provenance, and the caller falls back to "upload" only when the row is gone
        # (Gap C).
        src = await conn.fetchrow(
            """
            SELECT "sourceType", "sourceOrigin"
            FROM "UserDataset"
            WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                SELECT "userGroup" FROM "User" WHERE id = $2
            )))
            """,
            dataset_id, user_id,
        )
    # Inherit the root origin: cleaning an already-cleaned dataset keeps the
    # original source type, not "upload".
    source_origin = src["sourceOrigin"] if src and src["sourceOrigin"] else (src["sourceType"] if src else "upload")

    async with db_pool.acquire() as conn:
        ug = await conn.fetchrow('SELECT "userGroup" FROM "User" WHERE id = $1', user_id)
    user_group = ug["userGroup"] if ug else "00"
    dataset_group = user_group if shared else "00"
    new_id = str(uuid.uuid4())

    async with db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO "UserDataset" (
                id, "userId", name, description, "sourceType",
                "storageType", "sourceConnectionId", "databaseName", "tableName",
                "originalFileName", "fileSize", "filePath",
                "dataSnapshot", "datasetGroup", "isShared", "createdAt", "updatedAt",
                "sourceOrigin", "sourceDatasetId"
            ) VALUES ($1, $2, $3, $4, 'upload', 'postgresql', NULL, $5, $6,
                      NULL, NULL, NULL, $7, $8, $9, NOW(), NOW(),
                      $10, $11)
            """,
            new_id, user_id, name, description, DATA_DB_NAME, table_name,
            _sanitize_snapshot(rows), dataset_group, shared,
            source_origin, dataset_id,
        )

    return {
        "id": new_id,
        "name": name,
        "rowCount": len(rows),
        "columnCount": len(columns),
        "appliedRules": len(ops),
    }


async def _clean_in_place(
    db_pool, user_id, dataset_id, name, rule_ids, operations, language
):
    """Replace this dataset's data with the cleaned result, keeping its id/name.

    Only for local PostgreSQL tables (upload/notebook). The caller decides the
    in-place gate; the previous table survives un-referenced (recoverable).
    """
    columns, rows, table_name, ops = await _materialise_cleaned_table(
        db_pool, user_id, dataset_id, rule_ids, operations, language
    )

    async with db_pool.acquire() as conn:
        await conn.execute(
            '''
            UPDATE "UserDataset"
            SET "tableName" = $1, "dataSnapshot" = $2, "updatedAt" = NOW()
            WHERE id = $3
            ''',
            table_name, _sanitize_snapshot(rows), dataset_id,
        )

    return {
        "id": dataset_id,
        "name": name,
        "rowCount": len(rows),
        "columnCount": len(columns),
        "appliedRules": len(ops),
    }


# ============================================================
# CRUD ENDPOINTS
# ============================================================

@router.get("/{dataset_id}/preparation")
async def list_preparation_rules(
    dataset_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    List all preparation rules for a dataset.
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, PREPARATION["error.database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials)
    
    # Check dataset exists and is accessible
    async with _db_pool.acquire() as conn:
        dataset_row = await conn.fetchrow(
            """
            SELECT id FROM "UserDataset"
            WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (SELECT "userGroup" FROM "User" WHERE id = $2)))
            """,
            dataset_id, user_id
        )
    
    if dataset_row is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, PREPARATION["error.dataset.not_found_4"], id=dataset_id)
        )
    
    # Fetch preparation rules
    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT r.id, r.name, r.description, r.operations, r."ruleGroup", r."userId", r."isShared", r."createdAt", r."updatedAt",
                   u.name as user_name
            FROM "DataPreparationRule" r
            LEFT JOIN "User" u ON r."userId" = u.id
            WHERE r."datasetId" = $1
            ORDER BY r."createdAt" DESC
            """,
            dataset_id
        )
    
    result = []
    for row in rows:
        rule = dict(row)
        rule["isOwn"] = rule["userId"] == user_id
        result.append(rule)
    
    return {"preparation_rules": result}


@router.post("/{dataset_id}/preparation")
async def create_preparation_rule(
    dataset_id: str,
    request: CreatePreparationRuleRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Create a new preparation rule for a dataset.
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, PREPARATION["error.database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials)
    
    # Get user's group
    async with _db_pool.acquire() as conn:
        user_row = await conn.fetchrow(
            'SELECT "userGroup" FROM "User" WHERE id = $1',
            user_id
        )
        user_group = user_row["userGroup"] if user_row else "00"
    
    # A rule belongs to its dataset, so who may add one is decided by who may edit the
    # dataset: its owner, or an administrator when the dataset is shared to their group
    # (can_edit_dataset). A caller who may see the dataset but not change it is refused
    # with the same answer a missing dataset gives.
    may_edit = await can_edit_dataset(_db_pool, dataset_id, user_id)
    if not may_edit:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, PREPARATION["error.dataset.not_found_or_not_owned"], id=dataset_id)
        )
    
    # Validate operations
    try:
        await validate_operations(request.operations, language, _db_pool)
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )
    
    operations = [op.dict() for op in request.operations]
    content_hash = compute_content_hash(operations)

    # Hard de-dup on operations (name/description are decorative): if a rule
    # with identical operations already exists for this dataset, return it
    # idempotently instead of inserting a duplicate.
    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(
            '''
            SELECT id, name, description, operations, "ruleGroup", "isShared"
            FROM "DataPreparationRule"
            WHERE "datasetId" = $1
            ORDER BY "createdAt" ASC
            ''',
            dataset_id,
        )
    for erow in rows:
        existing_ops = erow["operations"]
        if existing_ops is not None and compute_content_hash(existing_ops) == content_hash:
            return {
                "success": True,
                "rule_id": erow["id"],
                "name": erow["name"],
                "description": erow["description"],
                "ruleGroup": erow["ruleGroup"],
                "isShared": erow["isShared"],
                "alreadyExisted": True,
                "message": await t(_db_pool, language, PREPARATION["datasets.preparation.already_exists"], name=erow["name"]),
            }

    rule_id = str(uuid.uuid4())
    is_shared = request.shared
     
    async with _db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO "DataPreparationRule" (
                id, "datasetId", name, description, operations, "ruleGroup", "isShared", "userId", "createdAt", "updatedAt"
            ) VALUES ($1, $2, $3, $4, $5, '00', $6, $7, NOW(), NOW())
            """,
            rule_id, dataset_id, request.name, request.description, operations, is_shared, user_id
        )
    
    return {
        "success": True,
        "rule_id": rule_id,
        "name": request.name,
        "description": request.description,
        "ruleGroup": "00",
        "isShared": is_shared,
        "message": await t(_db_pool, language, PREPARATION["datasets.preparation.rule_created"], name=request.name)
    }


@router.get("/{dataset_id}/preparation/schema")
async def get_dataset_schema(
    dataset_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Get column metadata for a dataset (AI agent and UI column picker)."""
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, PREPARATION["error.database.pool_not_initialized"]))
    user_id = await get_user_id_from_token(credentials)
    async with _db_pool.acquire() as conn:
        ug_row = await conn.fetchrow('SELECT "userGroup" FROM "User" WHERE id = $1', user_id)
    user_group = ug_row["userGroup"] if ug_row else "00"
    try:
        columns, rows = await get_dataset_data(_db_pool, user_id, dataset_id, language)
    except Exception:
        return {"columns": [], "row_count": 0, "column_count": 0}
    if not columns or not rows:
        return {"columns": [], "row_count": 0, "column_count": 0}
    result = []
    for col_name in columns:
        values = [r.get(col_name) for r in rows if not _is_missing(r.get(col_name))]
        null_count = len(rows) - len(values)
        null_percent = round((null_count / len(rows)) * 100, 1) if len(rows) > 0 else 0
        if values and all(isinstance(v, bool) for v in values):
            dtype, is_numeric, is_categorical, is_datetime = "boolean", False, False, False
        elif values and all(isinstance(v, int) and not isinstance(v, bool) for v in values):
            dtype, is_numeric, is_categorical, is_datetime = "integer", True, False, False
        elif values and all(_is_numeric_value(v) for v in values):
            dtype, is_numeric, is_categorical, is_datetime = "number", True, False, False
        elif values and all(_is_datetime_value(v) for v in values):
            dtype, is_numeric, is_categorical, is_datetime = "datetime", False, False, True
        else:
            dtype, is_numeric, is_categorical, is_datetime = "string", False, bool(values), False
        min_val = float(min(values)) if is_numeric else None
        max_val = float(max(values)) if is_numeric else None
        unique = []
        _seen = set()
        for v in values:
            if v not in _seen:
                _seen.add(v)
                unique.append(v)
        sample_values = [str(v) if not isinstance(v, (bytes, memoryview)) else str(v)[:40] for v in unique[:5]]
        result.append({"name": col_name, "dtype": dtype, "is_numeric": is_numeric, "is_categorical": is_categorical, "is_datetime": is_datetime, "null_count": null_count, "null_percent": null_percent, "unique_count": len(unique), "min_value": min_val, "max_value": max_val, "sample_values": sample_values})
    return {"columns": result, "row_count": int(len(rows)), "column_count": len(result)}
# ============================================================
# PREVIEW ENDPOINT
# ============================================================

@router.post("/{dataset_id}/preparation/preview")
async def preview_preparation_rule_endpoint(
    dataset_id: str,
    request: PreviewPreparationRuleRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Preview the effect of a preparation rule on a dataset.
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, PREPARATION["error.database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials)
    
    # Get the user's group
    async with _db_pool.acquire() as conn:
        user_row = await conn.fetchrow(
            'SELECT "userGroup" FROM "User" WHERE id = $1',
            user_id
        )
        user_group = user_row["userGroup"] if user_row else "00"
    
    # Phase 5.7 — SQL pushdown: fetch dataset metadata for compilation
    storage_type = "postgresql"
    table_name = "data"
    all_columns = []
    async with _db_pool.acquire() as conn:
        # The dataset must be one the caller can *see* — their own, or one shared to
        # their group: the preview compiles SQL against the dataset's own table and
        # reads it, so an invisible dataset must read as missing (Gap C).
        ds_row = await conn.fetchrow(
            """
            SELECT "sourceType", "storageType", "tableName", "dataSnapshot", "virtualSql"
            FROM "UserDataset"
            WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                SELECT "userGroup" FROM "User" WHERE id = $2
            )))
            """,
            dataset_id, user_id
        )
    if ds_row:
        storage_type = ds_row["storageType"] or "postgresql"
        table_name = ds_row["tableName"] or "data"
        snapshot = ds_row["dataSnapshot"]
        all_columns = snapshot.get("columns", []) if isinstance(snapshot, dict) else []

    # Virtual datasets have no native SQL backend — materialise the join into a
    # local PG table (virtual_{id}) and push down against it.
    if ds_row and ds_row["sourceType"] == "virtual":
        import json as _json
        virtual_sql = ds_row["virtualSql"]
        virtual_sql = _json.loads(virtual_sql) if isinstance(virtual_sql, str) else virtual_sql
        if not virtual_sql:
            raise ValueError(
                await t(_db_pool, language, error_dataset_load_failed_3, id=dataset_id)
            )
        try:
            table_name, all_columns, _ = await materialize_virtual_dataset(
                dataset_id, virtual_sql, user_id, _db_pool, language
            )
        except Exception as e:
            raise ValueError(
                await t(_db_pool, language, error_dataset_load_failed_4, id=dataset_id, error=str(e))
            )
        storage_type = "postgresql"
    
    # Preview the preparation rule
    try:
        if request.operations and len(request.operations) > 0 and request.rule_id is None:
            # Phase 5.7 — SQL pushdown for direct operations mode
            sql_ops, python_ops = split_operations(request.operations, storage_type)

            if sql_ops:
                compiled_sql = compile_sql(sql_ops, storage_type, table_name, all_columns)
                columns, rows, _ = await execute_compiled_sql_rows(
                    compiled_sql, _db_pool, user_id, dataset_id, language
                )
            else:
                try:
                    columns, rows = await get_dataset_data(_db_pool, user_id, dataset_id, language)
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, PREPARATION["error.dataset.load_failed"], error=str(e))
                    )

            before_rows = len(rows)
            before_nulls = _null_counts(columns, rows)

            if python_ops:
                for op in python_ops:
                    columns, rows = _apply_operation_in_memory(columns, rows, op)

            after_nulls = _null_counts(columns, rows)
            preview_sample = _sanitize_json(rows[:_PREVIEW_SAMPLE_ROWS])
            result = {
                "before_rows": before_rows,
                "after_rows": len(rows),
                "before_nulls": before_nulls,
                "after_nulls": after_nulls,
                "sample": preview_sample,
                "sql_pushdown": bool(sql_ops),
            }
        else:
            # Phase 5.7 — SQL pushdown for rule-based mode

            # Fetch rule operations first
            async with _db_pool.acquire() as conn:
                rule_row = await conn.fetchrow(
                    'SELECT name, operations FROM "DataPreparationRule" WHERE id = $1',
                    request.rule_id
                )
            rule_operations = []
            if rule_row and rule_row["operations"]:
                ops = rule_row["operations"]
                rule_operations = ops if isinstance(ops, list) else []

            if rule_operations:
                sql_ops, python_ops = split_operations(rule_operations, storage_type)

                if sql_ops:
                    compiled_sql = compile_sql(sql_ops, storage_type, table_name, all_columns)
                    columns, rows, _ = await execute_compiled_sql_rows(
                        compiled_sql, _db_pool, user_id, dataset_id, language
                    )
                else:
                    try:
                        columns, rows = await get_dataset_data(_db_pool, user_id, dataset_id, language)
                    except Exception as e:
                        raise HTTPException(
                            status_code=400,
                            detail=await t(_db_pool, language, PREPARATION["error.dataset.load_failed"], error=str(e))
                        )

                before_rows = len(rows)
                before_nulls = _null_counts(columns, rows)

                if python_ops:
                    for op in python_ops:
                        columns, rows = _apply_operation_in_memory(columns, rows, op)

                after_nulls = _null_counts(columns, rows)
                preview_sample = _sanitize_json(rows[:_PREVIEW_SAMPLE_ROWS])
                result = {
                    "before_rows": before_rows,
                    "after_rows": len(rows),
                    "before_nulls": before_nulls,
                    "after_nulls": after_nulls,
                    "sample": preview_sample,
                    "sql_pushdown": bool(sql_ops),
                }
            else:
                # No operations at all — load full dataset and use existing helper
                try:
                    columns, rows = await get_dataset_data(_db_pool, user_id, dataset_id, language)
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, PREPARATION["error.dataset.load_failed"], error=str(e))
                    )
                result = await preview_preparation_rule(
                    _db_pool,
                    request.rule_id,
                    columns,
                    rows,
                    request.limit,
                    language
                )
    except HTTPException:
        raise
    except ValueError as e:
        logger.warning("[TRACE] Preview ValueError: %s", e)
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, PREPARATION["datasets.preparation.preview_failed"], error=str(e))
        )
    except Exception as e:
        logger.error("[TRACE] Preview exception: %s", e, exc_info=True)
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, PREPARATION["datasets.preparation.preview_failed"], error=str(e))
        )
    
    return result

@router.post("/{dataset_id}/preparation/clean")
async def clean_dataset_endpoint(
    dataset_id: str,
    request: CleanRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Apply the dataset's preparation rules and land the result as a copy or
    in-place (replacing this dataset's data).
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, PREPARATION["error.database.pool_not_initialized"])
        )

    user_id = await get_user_id_from_token(credentials)

    # The caller must be able to *see* the dataset — their own, or one shared to their
    # group. Cleaning is a read, not an edit: case 3 may clean a shared dataset, whose
    # rules are readable to them, and the result is always a new dataset of their own
    # (the copy branch below). So this is the visibility predicate, not
    # can_edit_dataset; the name and type are fetched for the in-place gate.
    async with _db_pool.acquire() as conn:
        ds = await conn.fetchrow(
            '''
            SELECT name, "sourceType", "storageType", "userId" FROM "UserDataset"
            WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                SELECT "userGroup" FROM "User" WHERE id = $2
            )))
            ''',
            dataset_id, user_id
        )
    if ds is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, PREPARATION["error.dataset.not_found_or_not_owned"], id=dataset_id)
        )

    source_name = ds["name"]
    is_owned = ds["userId"] == user_id
    is_local_pg = (ds["sourceType"] in ("upload", "notebook")) and (ds["storageType"] == "postgresql")

    try:
        # In place writes the caller's *own* row and nothing else. A dataset shared to
        # the caller — or to an administrator's group — is cleaned as a copy: the shared
        # row is never the target, and the materialised table lands in the caller's
        # schema.
        if request.mode == "in_place" and is_local_pg and is_owned:
            result = await _clean_in_place(
                _db_pool, user_id, dataset_id, source_name,
                request.rule_ids, None, language
            )
            result["mode"] = "in_place"
        else:
            # copy — explicit mode=copy, or "in_place" on a non-local
            # (virtual/external) dataset or one the caller does not own silently
            # falls back to copy.
            copy_name = request.name or f"{source_name} - cleaned"
            result = await _save_cleaned_copy(
                _db_pool, user_id, dataset_id, copy_name,
                request.rule_ids, None, request.description, request.shared, language
            )
            result["mode"] = "copy"
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return result

@router.get("/{dataset_id}/preparation/{rule_id}")
async def get_preparation_rule(
    dataset_id: str,
    rule_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Get a specific preparation rule by ID.
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, PREPARATION["error.database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials)
    
    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT r.id, r.name, r.description, r.operations, r."ruleGroup", r."userId", r."createdAt", r."updatedAt",
                   u.name as user_name
            FROM "DataPreparationRule" r
            JOIN "UserDataset" d ON d.id = r."datasetId"
            LEFT JOIN "User" u ON r."userId" = u.id
            WHERE r.id = $1 AND r."datasetId" = $2 AND (
                d."userId" = $3 OR (d."isShared" = true AND d."datasetGroup" IN (
                    SELECT "userGroup" FROM "User" WHERE id = $3
                ))
            )
            """,
            rule_id, dataset_id, user_id
        )
    
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, PREPARATION["datasets.preparation.rule_not_found"], id=rule_id)
        )
    
    result = dict(row)
    result["isOwn"] = result["userId"] == user_id
    
    return {"preparation_rule": result}


@router.put("/{dataset_id}/preparation/{rule_id}")
async def update_preparation_rule(
    dataset_id: str,
    rule_id: str,
    request: UpdatePreparationRuleRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Update an existing preparation rule (own rules only).
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, PREPARATION["error.database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials)
    
    # The rule's dataset decides who may change it: its owner, or an administrator when
    # the dataset is shared to their group (can_edit_dataset) — the rule must also belong
    # to the dataset named in the path.
    may_edit = await can_edit_dataset(_db_pool, dataset_id, user_id)

    async with _db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id, name FROM "DataPreparationRule"
            WHERE id = $1 AND "datasetId" = $2
            """,
            rule_id, dataset_id
        )
        if existing is None or not may_edit:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, PREPARATION["datasets.preparation.rule_not_found_or_not_owned"])
            )
    
    # Validate operations if provided
    operations = None
    if request.operations is not None:
        try:
            await validate_operations(request.operations, language, _db_pool)
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )
        operations = [op.dict() for op in request.operations]
        new_hash = compute_content_hash(operations)

        # De-dup on operations (name is decorative): reject if the update would
        # make this rule's operations identical to another rule in the dataset.
        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                '''
                SELECT id, name, operations FROM "DataPreparationRule"
                WHERE "datasetId" = $1 AND id != $2
                ''',
                dataset_id, rule_id,
            )
        for erow in rows:
            existing_ops = erow["operations"]
            if existing_ops is not None and compute_content_hash(existing_ops) == new_hash:
                raise HTTPException(
                    status_code=409,
                    detail=await t(_db_pool, language, PREPARATION["datasets.preparation.already_exists"], name=erow["name"]),
                )
    
    updates = []
    params = []
    param_counter = 3  # Start after rule_id and dataset_id ($1..$2)
    
    if request.name is not None:
        updates.append(f'name = ${param_counter}')
        params.append(request.name)
        param_counter += 1
    
    if request.description is not None:
        updates.append(f'description = ${param_counter}')
        params.append(request.description)
        param_counter += 1
    
    if request.operations is not None:
        updates.append(f'operations = ${param_counter}')
        params.append(operations)
        param_counter += 1
    
    if request.ruleGroup is not None:
        updates.append(f'"ruleGroup" = ${param_counter}')
        params.append(request.ruleGroup)
        param_counter += 1
    
    if not updates:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, PREPARATION["datasets.preparation.no_updates"])
        )
    
    updates.append('"updatedAt" = NOW()')
    
    query = f"""
        UPDATE "DataPreparationRule"
        SET {', '.join(updates)}
        WHERE id = $1 AND "datasetId" = $2
    """
    
    async with _db_pool.acquire() as conn:
        result = await conn.execute(query, rule_id, dataset_id, *params)
        if result == "UPDATE 0":
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, PREPARATION["datasets.preparation.rule_not_found_or_not_owned"])
            )
    
    return {
        "success": True,
        "rule_id": rule_id,
        "message": await t(_db_pool, language, PREPARATION["datasets.preparation.rule_updated"])
    }


@router.delete("/{dataset_id}/preparation/{rule_id}")
async def delete_preparation_rule(
    dataset_id: str,
    rule_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Delete a preparation rule (own rules only).
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, PREPARATION["error.database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials)

    # The rule's dataset decides who may delete it: its owner, or an administrator when
    # the dataset is shared to their group (can_edit_dataset).
    if not await can_edit_dataset(_db_pool, dataset_id, user_id):
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, PREPARATION["datasets.preparation.rule_not_found_or_not_owned"])
        )

    # Check if any recipes use this rule
    async with _db_pool.acquire() as conn:
        recipes = await conn.fetch(
            """
            SELECT r.id, r.name
            FROM "Recipe" r
            JOIN "RecipePreparationRule" rpr ON r.id = rpr."recipeId"
            WHERE rpr."ruleId" = $1
            """,
            rule_id
        )
        
        if recipes:
            recipe_names = [r["name"] for r in recipes]
            raise HTTPException(
                status_code=409,
                detail=await t(
                    _db_pool, language,
                    PREPARATION["datasets.preparation.rule_in_use"],
                    count=len(recipes),
                    names=", ".join(recipe_names)
                )
            )
    
    # Delete the rule
    async with _db_pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM "DataPreparationRule"
            WHERE id = $1 AND "datasetId" = $2
            """,
            rule_id, dataset_id
        )
        if result == "DELETE 0":
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, PREPARATION["datasets.preparation.rule_not_found_or_not_owned"])
            )
    
    return {"success": True}

