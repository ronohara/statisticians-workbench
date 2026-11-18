"""
Execution history endpoints for recipes.
Handles listing and retrieving recipe executions.
"""

from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncpg
import jwt
import os

from .models import ExecutionResponse
from src.utils.translation import t
from src.routers.datasets.crud import get_current_language, get_user_id_from_token
from .translations import (
    error_database_pool_not_initialized,
    recipes_execution_not_found,
)

router = APIRouter()
security = HTTPBearer()

_db_pool = None
SECRET_KEY = os.getenv("NEXTAUTH_SECRET")


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


@router.get("/executions")
async def list_executions(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
    limit: int = 10,
    offset: int = 0
):
    """
    List recipe executions for the current user.
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized)
        )

    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, "recipeId", status, progress, "startedAt", "completedAt", "createdAt"
            FROM "RecipeExecution"
            WHERE "userId" = $1
            ORDER BY "createdAt" DESC
            LIMIT $2 OFFSET $3
            """,
            user_id, limit, offset
        )

    return {"executions": [dict(row) for row in rows]}


@router.get("/executions/{execution_id}")
async def get_execution(
    execution_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Get a specific recipe execution by ID.
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized)
        )

    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, "recipeId", status, progress, result, error, "startedAt", "completedAt", "createdAt"
            FROM "RecipeExecution"
            WHERE id = $1 AND "userId" = $2
            """,
            execution_id, user_id
        )
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, recipes_execution_not_found, id=execution_id)
            )

        result = dict(row)
        return result