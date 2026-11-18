"""
Transform Rules — CRUD operations for dataset-level transform rules.
Part of Phase 4 — Transform Management.
"""

import os
import json
import uuid
import hashlib
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import logging

logger = logging.getLogger("uvicorn.trace")

from .crud import get_user_id_from_token, get_current_language, can_edit_dataset
from src.utils.translation import t
from .translations import TRANSFORMS
from .validation import (
    validate_operations,
    VALID_OPERATION_TYPES,
    FILL_MISSING_METHODS,
    ENCODING_TYPES,
    TARGET_TYPES,
)

router = APIRouter()
security = HTTPBearer()

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ============================================================
# REQUEST MODELS
# ============================================================

class TransformOperation(BaseModel):
    """A single transform operation."""
    type: str  # "filter", "fill_missing", "convert_type", "normalize", "standardize", "encode", "drop_duplicates", "drop_columns", "rename_column"
    column: Optional[str] = None
    columns: Optional[List[str]] = None
    operator: Optional[str] = None
    value: Optional[Any] = None
    method: Optional[str] = None  # "mean", "median", "mode", "constant", "drop"
    target_type: Optional[str] = None  # "numeric", "datetime", "string", "boolean"
    new_name: Optional[str] = None
    encoding: Optional[str] = None  # "one_hot", "label"


class CreateTransformRequest(BaseModel):
    """Request model for creating a transform."""
    name: str
    description: Optional[str] = None
    operations: List[TransformOperation]
    shared: bool = False
    ruleGroup: str = "00"


class UpdateTransformRequest(BaseModel):
    """Request model for updating a transform."""
    name: Optional[str] = None
    description: Optional[str] = None
    operations: Optional[List[TransformOperation]] = None
    shared: Optional[bool] = None
    ruleGroup: Optional[str] = None


# Validation constants and function are shared with preparation.py
# via backend/src/routers/datasets/validation.py


# ============================================================
# HELPER: Content hash
# ============================================================

def compute_content_hash(operations: list) -> str:
    """Compute SHA256 hash of serialised operations for change detection."""
    ops_json = json.dumps(operations, sort_keys=True, default=str)
    return hashlib.sha256(ops_json.encode("utf-8")).hexdigest()


# ============================================================
# SHARED CRUD (used by both the HTTP endpoints and the AI tools)
# ============================================================
# Each function raises HTTPException on domain errors (translated) so the
# HTTP endpoints below can let them propagate, and the AI tools in
# recipes/ai_recipe_tools.py can catch them into {"error": detail}. The
# endpoints delegate here; the tools call the same functions — no logic
# is re-implemented.

async def fetch_dataset_transforms(
    dataset_id: str, user_id: str, language: str
) -> dict:
    """List transforms for a dataset (own or shared-group accessible)."""
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
            detail=await t(_db_pool, language, TRANSFORMS["datasets.transforms.not_accessible"], id=dataset_id)
        )

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
        transform = dict(row)
        transform["isOwn"] = transform["userId"] == user_id
        transform["contentHash"] = compute_content_hash(transform["operations"])
        result.append(transform)
    return {"transforms": result}


async def fetch_transform(
    dataset_id: str, transform_id: str, user_id: str, language: str
) -> dict:
    """Get a single transform (own or shared-group accessible)."""
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
            transform_id, dataset_id, user_id
        )
    if row is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, TRANSFORMS["datasets.transforms.not_found"], id=transform_id)
        )
    result = dict(row)
    result["isOwn"] = result["userId"] == user_id
    result["contentHash"] = compute_content_hash(result["operations"])
    return {"transform": result}


async def create_transform_record(
    dataset_id: str,
    user_id: str,
    name: str,
    description: Optional[str],
    operations: List[TransformOperation],
    shared: bool,
    language: str,
) -> dict:
    """Create a transform for a dataset (its owner, or an administrator when the dataset
    is shared to their group)."""
    # Who may add a transform to a dataset is decided by who may edit the dataset
    # (can_edit_dataset). A caller who may see the dataset but not change it is refused
    # with the same answer a missing dataset gives.
    if not await can_edit_dataset(_db_pool, dataset_id, user_id):
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, TRANSFORMS["datasets.transforms.not_owned"], id=dataset_id)
        )

    try:
        await validate_operations(operations, language, _db_pool)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    ops = [op.dict() for op in operations]
    content_hash = compute_content_hash(ops)

    # Hard de-duplication on operations (name/description are decorative): if a
    # rule with identical operations already exists for this dataset, return it
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
                "transform_id": erow["id"],
                "name": erow["name"],
                "description": erow["description"],
                "ruleGroup": erow["ruleGroup"],
                "isShared": erow["isShared"],
                "contentHash": content_hash,
                "alreadyExisted": True,
                "message": await t(_db_pool, language, TRANSFORMS["datasets.transforms.already_exists"], name=erow["name"]),
            }

    transform_id = str(uuid.uuid4())

    async with _db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO "DataPreparationRule" (
                id, "datasetId", name, description, operations, "ruleGroup", "isShared", "userId", "createdAt", "updatedAt"
            ) VALUES ($1, $2, $3, $4, $5, '00', $6, $7, NOW(), NOW())
            """,
            transform_id, dataset_id, name, description, ops, shared, user_id
        )

    return {
        "success": True,
        "transform_id": transform_id,
        "name": name,
        "description": description,
        "ruleGroup": "00",
        "isShared": shared,
        "contentHash": content_hash,
        "message": await t(_db_pool, language, TRANSFORMS["datasets.transforms.created"], name=name)
    }


async def update_transform_record(
    dataset_id: str,
    transform_id: str,
    user_id: str,
    name: Optional[str],
    description: Optional[str],
    operations: Optional[List[TransformOperation]],
    rule_group: Optional[str],
    language: str,
) -> dict:
    """Update a transform (its owner, or an administrator when its dataset is shared to
    their group). None = no change for each field."""
    # The transform's dataset decides who may change it: its owner, or an administrator
    # when the dataset is shared to their group (can_edit_dataset) — the transform must
    # also belong to the dataset named in the path.
    may_edit = await can_edit_dataset(_db_pool, dataset_id, user_id)

    async with _db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id, name FROM "DataPreparationRule"
            WHERE id = $1 AND "datasetId" = $2
            """,
            transform_id, dataset_id
        )
    if existing is None or not may_edit:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, TRANSFORMS["datasets.transforms.not_found_or_not_owned"])
        )

    ops = None
    if operations is not None:
        try:
            await validate_operations(operations, language, _db_pool)
        except ValueError as e:
            raise HTTPException(status_code=400, detail=str(e))
        ops = [op.dict() for op in operations]
        new_hash = compute_content_hash(ops)

        # De-dup on operations (name is decorative): reject if the update would
        # make this rule's operations identical to another rule in the dataset.
        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                '''
                SELECT id, name, operations FROM "DataPreparationRule"
                WHERE "datasetId" = $1 AND id != $2
                ''',
                dataset_id, transform_id,
            )
        for erow in rows:
            existing_ops = erow["operations"]
            if existing_ops is not None and compute_content_hash(existing_ops) == new_hash:
                raise HTTPException(
                    status_code=409,
                    detail=await t(_db_pool, language, TRANSFORMS["datasets.transforms.already_exists"], name=erow["name"]),
                )

    updates = []
    params = []
    param_counter = 3  # Start after transform_id and dataset_id ($1..$2)

    if name is not None:
        updates.append(f'name = ${param_counter}')
        params.append(name)
        param_counter += 1
    if description is not None:
        updates.append(f'description = ${param_counter}')
        params.append(description)
        param_counter += 1
    if operations is not None:
        updates.append(f'operations = ${param_counter}')
        params.append(ops)
        param_counter += 1
    if rule_group is not None:
        updates.append(f'"ruleGroup" = ${param_counter}')
        params.append(rule_group)
        param_counter += 1

    if not updates:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, TRANSFORMS["datasets.transforms.no_updates"])
        )

    updates.append('"updatedAt" = NOW()')
    query = f"""
        UPDATE "DataPreparationRule"
        SET {', '.join(updates)}
        WHERE id = $1 AND "datasetId" = $2
    """

    async with _db_pool.acquire() as conn:
        result = await conn.execute(query, transform_id, dataset_id, *params)
        if result == "UPDATE 0":
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, TRANSFORMS["datasets.transforms.not_found_or_not_owned"])
            )

    resp = {
        "success": True,
        "transform_id": transform_id,
        "message": await t(_db_pool, language, TRANSFORMS["datasets.transforms.updated"])
    }
    if operations is not None:
        resp["contentHash"] = compute_content_hash([op.dict() for op in operations])
    return resp


async def delete_transform_record(
    dataset_id: str, transform_id: str, user_id: str, language: str
) -> dict:
    """Delete a transform (its owner, or an administrator when its dataset is shared to
    their group; blocks when in use by a recipe)."""
    # The transform's dataset decides who may delete it: its owner, or an administrator
    # when the dataset is shared to their group (can_edit_dataset).
    if not await can_edit_dataset(_db_pool, dataset_id, user_id):
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, TRANSFORMS["datasets.transforms.not_found_or_not_owned"])
        )

    async with _db_pool.acquire() as conn:
        recipes = await conn.fetch(
            """
            SELECT r.id, r.name
            FROM "Recipe" r
            JOIN "RecipePreparationRule" rpr ON r.id = rpr."recipeId"
            WHERE rpr."ruleId" = $1
            """,
            transform_id
        )
    if recipes:
        recipe_names = [r["name"] for r in recipes]
        raise HTTPException(
            status_code=409,
            detail=await t(
                _db_pool, language,
                TRANSFORMS["datasets.transforms.in_use"],
                count=len(recipes),
                names=", ".join(recipe_names)
            )
        )

    async with _db_pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM "DataPreparationRule"
            WHERE id = $1 AND "datasetId" = $2
            """,
            transform_id, dataset_id
        )
        if result == "DELETE 0":
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, TRANSFORMS["datasets.transforms.not_found_or_not_owned"])
            )

    return {
        "success": True,
        "message": await t(_db_pool, language, TRANSFORMS["datasets.transforms.deleted"])
    }


# ============================================================
# CRUD ENDPOINTS
# ============================================================

@router.get("/{dataset_id}/transforms")
async def list_transforms(
    dataset_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    List all transforms for a dataset.
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, TRANSFORMS["error.database.pool_not_initialized"])
        )

    user_id = await get_user_id_from_token(credentials)
    return await fetch_dataset_transforms(dataset_id, user_id, language)


@router.post("/{dataset_id}/transforms")
async def create_transform(
    dataset_id: str,
    request: CreateTransformRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Create a new transform for a dataset (its owner, or an administrator when the dataset is
    shared to their group, with content hash).
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, TRANSFORMS["error.database.pool_not_initialized"])
        )

    user_id = await get_user_id_from_token(credentials)
    return await create_transform_record(
        dataset_id, user_id, request.name, request.description,
        request.operations, request.shared, language,
    )


@router.get("/{dataset_id}/transforms/{transform_id}")
async def get_transform(
    dataset_id: str,
    transform_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Get a specific transform by ID.
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, TRANSFORMS["error.database.pool_not_initialized"])
        )

    user_id = await get_user_id_from_token(credentials)
    return await fetch_transform(dataset_id, transform_id, user_id, language)


@router.put("/{dataset_id}/transforms/{transform_id}")
async def update_transform(
    dataset_id: str,
    transform_id: str,
    request: UpdateTransformRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Update an existing transform (own transforms only).
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, TRANSFORMS["error.database.pool_not_initialized"])
        )

    user_id = await get_user_id_from_token(credentials)
    return await update_transform_record(
        dataset_id, transform_id, user_id,
        request.name, request.description, request.operations, request.ruleGroup,
        language,
    )


@router.delete("/{dataset_id}/transforms/{transform_id}")
async def delete_transform(
    dataset_id: str,
    transform_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Delete a transform (own transforms only).
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, TRANSFORMS["error.database.pool_not_initialized"])
        )

    user_id = await get_user_id_from_token(credentials)
    return await delete_transform_record(dataset_id, transform_id, user_id, language)


# ============================================================
# CLONE ENDPOINT
# ============================================================

@router.post("/{dataset_id}/transforms/{transform_id}/clone")
async def clone_transform(
    dataset_id: str,
    transform_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Clone a transform into a new one owned by the cloning user.

    Cloning writes a transform into the dataset, so it is a *create* and asks the
    create rule (can_edit_dataset) — the owner, or an administrator when the dataset
    is shared to their group. A caller who may only see the dataset cannot add a row
    to it by this route.
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, TRANSFORMS["error.database.pool_not_initialized"])
        )

    user_id = await get_user_id_from_token(credentials)

    # Who may clone into this dataset: its owner, or an administrator when it is shared
    # to their group — the create rule, asked first, so a caller who may not write to
    # the dataset learns nothing about its rules. The refusal is the one
    # create_transform_record gives, so the two paths agree.
    if not await can_edit_dataset(_db_pool, dataset_id, user_id):
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, TRANSFORMS["datasets.transforms.not_owned"], id=dataset_id)
        )

    # Verify the source transform is accessible
    async with _db_pool.acquire() as conn:
        source = await conn.fetchrow(
            """
            SELECT r.id, r.name, r.description, r.operations, r."ruleGroup", r."userId"
            FROM "DataPreparationRule" r
            JOIN "UserDataset" d ON d.id = r."datasetId"
            WHERE r.id = $1 AND r."datasetId" = $2 AND (
                d."userId" = $3 OR (d."isShared" = true AND d."datasetGroup" IN (
                    SELECT "userGroup" FROM "User" WHERE id = $3
                ))
            )
            """,
            transform_id, dataset_id, user_id
        )

    if source is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, TRANSFORMS["datasets.transforms.not_found"], id=transform_id)
        )

    # Generate a unique name for the clone
    source_name = source["name"]
    clone_base = f"{source_name} (copy)"

    # Ensure unique name for this user's dataset transforms
    async with _db_pool.acquire() as conn:
        existing_names = await conn.fetch(
            """
            SELECT name FROM "DataPreparationRule"
            WHERE "datasetId" = $1 AND "userId" = $2 AND name LIKE $3
            """,
            dataset_id, user_id, f"{source_name} (copy)%"
        )
        existing_set = {r["name"] for r in existing_names}

    clone_name = clone_base
    counter = 2
    while clone_name in existing_set:
        clone_name = f"{source_name} (copy {counter})"
        counter += 1

    new_id = str(uuid.uuid4())

    async with _db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO "DataPreparationRule" (
                id, "datasetId", name, description, operations, "ruleGroup", "isShared", "userId", "createdAt", "updatedAt"
            ) VALUES ($1, $2, $3, $4, $5, '00', false, $6, NOW(), NOW())
            """,
            new_id, dataset_id, clone_name, source["description"], source["operations"], user_id
        )

    # Compute content hash
    ops = source["operations"]
    content_hash = compute_content_hash(ops)

    return {
        "success": True,
        "transform_id": new_id,
        "name": clone_name,
        "contentHash": content_hash,
        "message": await t(_db_pool, language, TRANSFORMS["datasets.transforms.cloned"], name=clone_name)
    }
