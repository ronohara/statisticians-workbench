"""
Recipe-Transform Association Endpoints — Phase 4.5.1

Manages the many-to-many relationship between recipes and transform rules
via the RecipePreparationRule intersect table.

Endpoints:
  GET    /api/recipes/{recipeId}/transforms           — list connected transforms
  POST   /api/recipes/{recipeId}/transforms           — connect a transform
  DELETE /api/recipes/{recipeId}/transforms/{transformId} — disconnect
"""

import uuid
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import logging

logger = logging.getLogger("uvicorn.trace")

from src.routers.datasets.crud import get_user_id_from_token, get_current_language
from src.utils.translation import t
from .translations import (
    error_database_pool_not_initialized,
    recipes_not_found,
    recipes_not_owned,
    recipes_transforms_connect_success,
    recipes_transforms_dataset_mismatch,
    recipes_transforms_disconnect_success,
    recipes_transforms_not_found,
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

class ConnectTransformRequest(BaseModel):
    """Request model for connecting a transform to a recipe."""
    transformId: str


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/{recipe_id}/transforms")
async def list_recipe_transforms(
    recipe_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """List all transforms connected to a recipe."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized)
        )

    user_id = await get_user_id_from_token(credentials)

    # Verify recipe exists and user has access (own or shared)
    async with _db_pool.acquire() as conn:
        recipe_row = await conn.fetchrow(
            """
            SELECT id, "datasetId", "userId"
            FROM "Recipe"
            WHERE id = $1
              AND ("userId" = $2 OR ("isShared" = true AND "recipeGroup" IN (SELECT "userGroup" FROM "User" WHERE id = $2)))
            """,
            recipe_id, user_id
        )

    if recipe_row is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_not_found, id=recipe_id)
        )

    # Fetch connected transforms with metadata
    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT rpr."ruleId" as id, rpr."order", dr.name, dr.description,
                   dr.operations
            FROM "RecipePreparationRule" rpr
            JOIN "DataPreparationRule" dr ON rpr."ruleId" = dr.id
            WHERE rpr."recipeId" = $1
            ORDER BY rpr."order" ASC
            """,
            recipe_id
        )

    transforms = []
    for row in rows:
        operations = row["operations"]
        operations_count = len(operations) if isinstance(operations, list) else 0

        transforms.append({
            "id": row["id"],
            "name": row["name"],
            "description": row["description"],
            "operations_count": operations_count,
            "order": row["order"],
        })

    return {"transforms": transforms}


@router.post("/{recipe_id}/transforms")
async def connect_transform(
    recipe_id: str,
    body: ConnectTransformRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Connect a transform to a recipe (adds a row to RecipePreparationRule)."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized)
        )

    user_id = await get_user_id_from_token(credentials)
    transform_id = body.transformId

    # Verify recipe exists, is owned by user, and get its dataset
    async with _db_pool.acquire() as conn:
        recipe_row = await conn.fetchrow(
            """
            SELECT id, "datasetId"
            FROM "Recipe"
            WHERE id = $1 AND "userId" = $2
            """,
            recipe_id, user_id
        )

    if recipe_row is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_not_owned, id=recipe_id)
        )

    dataset_id = recipe_row["datasetId"]

    # Validate transform exists and belongs to the recipe's dataset
    async with _db_pool.acquire() as conn:
        transform_row = await conn.fetchrow(
            """
            SELECT id, "datasetId"
            FROM "DataPreparationRule"
            WHERE id = $1
            """,
            transform_id
        )

    if transform_row is None:
        raise HTTPException(
            status_code=404,
            detail=await t(
                _db_pool, language,
                recipes_transforms_not_found,
                id=transform_id
            )
        )

    if dataset_id and str(transform_row["datasetId"]) != str(dataset_id):
        raise HTTPException(
            status_code=400,
            detail=await t(
                _db_pool, language,
                recipes_transforms_dataset_mismatch,
                id=transform_id,
                dataset_id=dataset_id
            )
        )

    # Check if already connected (idempotent)
    async with _db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            """
            SELECT id FROM "RecipePreparationRule"
            WHERE "recipeId" = $1 AND "ruleId" = $2
            """,
            recipe_id, transform_id
        )

    if existing is not None:
        # Already connected — return success without duplicate
        return {
            "success": True,
            "ruleId": existing["id"],
            "message": await t(
                _db_pool, language,
                recipes_transforms_connect_success
            )
        }

    # Determine next order value
    async with _db_pool.acquire() as conn:
        max_order = await conn.fetchval(
            """
            SELECT COALESCE(MAX("order"), -1)
            FROM "RecipePreparationRule"
            WHERE "recipeId" = $1
            """,
            recipe_id
        )
    next_order = max_order + 1

    # Insert join row in a transaction
    rule_id = str(uuid.uuid4())
    async with _db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO "RecipePreparationRule" (id, "recipeId", "ruleId", "order", "createdAt", "updatedAt")
                VALUES ($1, $2, $3, $4, NOW(), NOW())
                """,
                rule_id, recipe_id, transform_id, next_order
            )

    return {
        "success": True,
        "ruleId": rule_id,
        "message": await t(
            _db_pool, language,
            recipes_transforms_connect_success
        )
    }


@router.delete("/{recipe_id}/transforms/{transform_id}")
async def disconnect_transform(
    recipe_id: str,
    transform_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Disconnect a transform from a recipe (removes the join row)."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized)
        )

    user_id = await get_user_id_from_token(credentials)

    # Verify recipe is owned by user
    async with _db_pool.acquire() as conn:
        recipe_row = await conn.fetchrow(
            """
            SELECT id FROM "Recipe"
            WHERE id = $1 AND "userId" = $2
            """,
            recipe_id, user_id
        )

    if recipe_row is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_not_owned, id=recipe_id)
        )

    # Delete the join row
    async with _db_pool.acquire() as conn:
        result = await conn.execute(
            """
            DELETE FROM "RecipePreparationRule"
            WHERE "recipeId" = $1 AND "ruleId" = $2
            """,
            recipe_id, transform_id
        )

    # DELETE 0 means it wasn't connected — still return success (idempotent)
    return {
        "success": True,
        "message": await t(
            _db_pool, language,
            recipes_transforms_disconnect_success
        )
    }
