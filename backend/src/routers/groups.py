"""
Groups Router – User Group Management
Part of the 0.0.10 "User Groups" feature.
"""

import json
import jwt
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import os

from src.utils.translation import t
from src.routers.datasets.crud import get_current_language
from .common.translations import GROUPS

router = APIRouter(prefix="/api/groups", tags=["groups"])
security = HTTPBearer()

_db_pool = None

def set_db_pool(pool):
    global _db_pool
    _db_pool = pool

SECRET_KEY = os.getenv("NEXTAUTH_SECRET")
if not SECRET_KEY:
    print("WARNING: NEXTAUTH_SECRET not set")

async def get_user_id_from_token(credentials: HTTPAuthorizationCredentials, db_pool=None, language: str = "en") -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail=await t(db_pool, language, GROUPS["auth.invalid_token_missing_user_id"]) if db_pool else "Invalid token: missing user id")
        return user_id
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=await t(db_pool, language, GROUPS["auth.invalid_token_error"], error=str(e)) if db_pool else f"Invalid token: {str(e)}")

async def is_admin(user_id: str) -> bool:
    """Check if the user is an admin."""
    if _db_pool is None:
        return False
    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT "isAdmin" FROM "User" WHERE id = $1',
            user_id
        )
        return row["isAdmin"] if row else False


# ============================================================
# REQUEST MODELS
# ============================================================

class GroupDescriptionUpdate(BaseModel):
    group_id: str
    description: str

class UserGroupUpdate(BaseModel):
    user_id: str
    user_group: str


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/")
async def list_groups(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """List all user groups with descriptions."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, GROUPS["error.database.pool_not_initialized"])
        )

    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    if not await is_admin(user_id):
        raise HTTPException(
            status_code=403,
            detail=await t(_db_pool, language, GROUPS["groups.admin_required"])
        )

    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT "groupId", "groupDescription"
            FROM "UserGroup"
            ORDER BY "groupId"
            """
        )

    return {"groups": [{"groupId": row["groupId"], "groupDescription": row["groupDescription"]} for row in rows]}

@router.put("/description")
async def update_group_description(
    request: GroupDescriptionUpdate,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Update a group description (admin only)."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, GROUPS["error.database.pool_not_initialized"])
        )

    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    if not await is_admin(user_id):
        raise HTTPException(
            status_code=403,
            detail=await t(_db_pool, language, GROUPS["groups.admin_required"])
        )

    if request.group_id < "00" or request.group_id > "99":
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, GROUPS["error.groups.invalid_group_id"])
        )

    async with _db_pool.acquire() as conn:
        result = await conn.execute(
            """
            UPDATE "UserGroup"
            SET "groupDescription" = $1, "updatedAt" = NOW()
            WHERE "groupId" = $2
            """,
            request.description, request.group_id
        )

        if result == "UPDATE 0":
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, GROUPS["groups.not_found"], id=request.group_id)
            )

    return {
        "success": True,
        "group_id": request.group_id,
        "description": request.description,
        "message": await t(_db_pool, language, GROUPS["groups.update_success"], id=request.group_id)
    }

@router.get("/user/me")
async def get_my_group(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Get the current user's group."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, GROUPS["error.database.pool_not_initialized"])
        )

    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u."userGroup", g."groupDescription"
            FROM "User" u
            LEFT JOIN "UserGroup" g ON u."userGroup" = g."groupId"
            WHERE u.id = $1
            """,
            user_id
        )

        if row is None:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, GROUPS["groups.user_not_found"])
            )

        return {
            "user_id": user_id,
            "user_group": row["userGroup"],
            "group_description": row["groupDescription"] or await t(_db_pool, language, GROUPS["common.unknown"])
        }

@router.get("/user/{user_id}")
async def get_user_group(
    user_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Get a user's group (user can see their own, admin can see any)."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, GROUPS["error.database.pool_not_initialized"])
        )

    current_user_id = await get_user_id_from_token(credentials, _db_pool, language)
    is_admin_user = await is_admin(current_user_id)

    if not is_admin_user and current_user_id != user_id:
        raise HTTPException(
            status_code=403,
            detail=await t(_db_pool, language, GROUPS["groups.not_authorized"])
        )

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT u."userGroup", g."groupDescription"
            FROM "User" u
            LEFT JOIN "UserGroup" g ON u."userGroup" = g."groupId"
            WHERE u.id = $1
            """,
            user_id
        )

        if row is None:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, GROUPS["groups.user_not_found"])
            )

        return {
            "user_id": user_id,
            "user_group": row["userGroup"],
            "group_description": row["groupDescription"] or await t(_db_pool, language, GROUPS["common.unknown"])
        }

@router.put("/user")
async def update_user_group(
    request: UserGroupUpdate,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Update a user's group (admin only)."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, GROUPS["error.database.pool_not_initialized"])
        )

    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    if not await is_admin(user_id):
        raise HTTPException(
            status_code=403,
            detail=await t(_db_pool, language, GROUPS["groups.admin_required"])
        )

    if request.user_group < "00" or request.user_group > "99":
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, GROUPS["groups.invalid_group_id"])
        )

    async with _db_pool.acquire() as conn:
        user_row = await conn.fetchrow(
            'SELECT id FROM "User" WHERE id = $1',
            request.user_id
        )
        if user_row is None:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, GROUPS["groups.user_not_found"])
            )

        await conn.execute(
            """
            UPDATE "User"
            SET "userGroup" = $1, "updatedAt" = NOW()
            WHERE id = $2
            """,
            request.user_group, request.user_id
        )

    return {
        "success": True,
        "user_id": request.user_id,
        "user_group": request.user_group,
        "message": await t(_db_pool, language, GROUPS["groups.user_updated"])
    }

# ── Admin: update resource group and isShared ──────────────────

@router.put("/resource/dataset")
async def update_dataset_group(
    body: dict,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Admin: set dataset group and isShared flag."""
    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    if not await is_admin(user_id):
        raise HTTPException(status_code=403, detail=await t(_db_pool, language, GROUPS["groups.admin_required"]))
    if "id" not in body:
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, GROUPS["groups.missing_id"]))
    async with _db_pool.acquire() as conn:
        result = await conn.execute(
            'UPDATE "UserDataset" SET "datasetGroup" = $1, "isShared" = $2, "updatedAt" = NOW() WHERE id = $3',
            body.get("group", "00"), body.get("isShared", False), body["id"]
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail=await t(_db_pool, language, GROUPS["groups.resource_not_found"]))
    return {"success": True, "id": body["id"]}

@router.put("/resource/db-connection")
async def update_db_connection_group(
    body: dict,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Admin: set database connection group and isShared flag."""
    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    if not await is_admin(user_id):
        raise HTTPException(status_code=403, detail=await t(_db_pool, language, GROUPS["groups.admin_required"]))
    if "connectionId" not in body:
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, GROUPS["groups.missing_id"]))
    async with _db_pool.acquire() as conn:
        result = await conn.execute(
            'UPDATE "UserDatabaseConnection" SET "dbConnectionGroup" = $1, "isShared" = $2, "updatedAt" = NOW() WHERE "connectionId" = $3',
            body.get("group", "00"), body.get("isShared", False), body["connectionId"]
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail=await t(_db_pool, language, GROUPS["groups.resource_not_found"]))
    return {"success": True, "connectionId": body["connectionId"]}

@router.put("/resource/ai-connection")
async def update_ai_connection_group(
    body: dict,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Admin: set AI connection group and isShared flag."""
    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    if not await is_admin(user_id):
        raise HTTPException(status_code=403, detail=await t(_db_pool, language, GROUPS["groups.admin_required"]))
    if "connectionId" not in body:
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, GROUPS["groups.missing_id"]))
    async with _db_pool.acquire() as conn:
        result = await conn.execute(
            'UPDATE "UserAIConnection" SET "aiConnectionGroup" = $1, "isShared" = $2, "updatedAt" = NOW() WHERE "connectionId" = $3',
            body.get("group", "00"), body.get("isShared", False), body["connectionId"]
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail=await t(_db_pool, language, GROUPS["groups.resource_not_found"]))
    return {"success": True, "connectionId": body["connectionId"]}

@router.put("/resource/recipe")
async def update_recipe_group(
    body: dict,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Admin: set recipe group and isShared flag."""
    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    if not await is_admin(user_id):
        raise HTTPException(status_code=403, detail=await t(_db_pool, language, GROUPS["groups.admin_required"]))
    if "id" not in body:
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, GROUPS["groups.missing_id"]))
    async with _db_pool.acquire() as conn:
        result = await conn.execute(
            'UPDATE "Recipe" SET "recipeGroup" = $1, "isShared" = $2, "updatedAt" = NOW() WHERE id = $3',
            body.get("group", "00"), body.get("isShared", False), body["id"]
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail=await t(_db_pool, language, GROUPS["groups.resource_not_found"]))
    return {"success": True, "id": body["id"]}

@router.put("/resource/notebook")
async def update_notebook_group(
    body: dict,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Admin: set notebook group and isShared flag."""
    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    if not await is_admin(user_id):
        raise HTTPException(status_code=403, detail=await t(_db_pool, language, GROUPS["groups.admin_required"]))
    if "id" not in body:
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, GROUPS["groups.missing_id"]))
    async with _db_pool.acquire() as conn:
        result = await conn.execute(
            'UPDATE "NotebookImport" SET "notebookGroup" = $1, "isShared" = $2 WHERE id = $3',
            body.get("group", "00"), body.get("isShared", False), body["id"]
        )
        if result == "UPDATE 0":
            raise HTTPException(status_code=404, detail=await t(_db_pool, language, GROUPS["groups.resource_not_found"]))
    return {"success": True, "id": body["id"]}

@router.get("/shared")
async def get_shared_resources(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Get shared resources visible to the current user's group.
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, GROUPS["error.database.pool_not_initialized"])
        )

    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    async with _db_pool.acquire() as conn:
        user_row = await conn.fetchrow(
            'SELECT "userGroup" FROM "User" WHERE id = $1',
            user_id
        )
        if user_row is None:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, GROUPS["groups.user_not_found"])
            )

        user_group = user_row["userGroup"]

        ai_rows = await conn.fetch(
            """
            SELECT c.*, u.name as user_name
            FROM "UserAIConnection" c
            JOIN "User" u ON c."userId" = u.id
            WHERE c."isShared" = true
            AND c."aiConnectionGroup" = $1
            AND c."userId" != $2
            """,
            user_group, user_id
        )

        db_rows = await conn.fetch(
            """
            SELECT c.*, u.name as user_name
            FROM "UserDatabaseConnection" c
            JOIN "User" u ON c."userId" = u.id
            WHERE c."isShared" = true
            AND c."dbConnectionGroup" = $1
            AND c."userId" != $2
            """,
            user_group, user_id
        )

        recipe_rows = await conn.fetch(
            """
            SELECT r.*, u.name as user_name
            FROM "Recipe" r
            JOIN "User" u ON r."userId" = u.id
            WHERE r."isShared" = true
            AND r."recipeGroup" = $1
            AND r."userId" != $2
            """,
            user_group, user_id
        )

        dataset_rows = await conn.fetch(
            """
            SELECT d.*, u.name as user_name
            FROM "UserDataset" d
            JOIN "User" u ON d."userId" = u.id
            WHERE d."isShared" = true
            AND d."datasetGroup" = $1
            AND d."userId" != $2
            """,
            user_group, user_id
        )

        return {
            "ai_connections": [dict(row) for row in ai_rows],
            "db_connections": [dict(row) for row in db_rows],
            "recipes": [dict(row) for row in recipe_rows],
            "datasets": [dict(row) for row in dataset_rows]
        }