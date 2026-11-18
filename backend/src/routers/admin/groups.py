"""
Admin Groups Router — P2 Group 1, item 2 (Prisma-removal plan).

Drop-in replacement for the frontend Prisma handlers:
  frontend/app/api/admin/groups/route.ts            (GET list)
  frontend/app/api/admin/groups/promote/route.ts    (POST promote · DELETE demote)
  frontend/app/api/admin/groups/shared/route.ts     (GET group stats)
  frontend/app/api/admin/groups/user/route.ts       (PUT a user's group)
  frontend/app/api/admin/groups/user/[id]/route.ts  (GET one user)
  frontend/app/api/admin/groups/users/route.ts      (GET list · PATCH · DELETE soft)
  frontend/app/api/admin/groups/description/route.ts (PUT description)

Contract parity: same paths, request/response JSON keys, status codes and
{error, message} envelope — mirrored from the layer-2 handlers including
their quirks:
  - PUT /user body is snake_case {user_id, user_group}.
  - GET /user/[id] returns a FLAT user object (no {user} wrapper).
  - DELETE /users is a SOFT delete (deletedAt=now) — unlike admin/users.
  - PUT /description on a missing group -> 500 update_error (Prisma throws;
    no 404) — strict parity, flagged in the item-2 proposal.
  - PATCH /users requires the caller's group == target's group, even for
    full admins.
  - Promote/demote success messages are inline templates (no translation
    pair exists on the frontend either).

Auth helpers (_auth, role checks, _error, _can_manage) are shared
from admin.users.py; the pool is wired via set_db_pool in main.py.
"""

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from src.routers.datasets.crud import get_current_language
from src.routers.admin.translations import ADMIN
from src.utils.translation import t
from src.routers.admin.users import (
    _auth,
    _can_manage,
    _error,
    _is_admin,
    _is_example,
    _is_group_admin,
    _user_group,
    current_demo_mode,
)
from src.utils.timestamps import iso_utc

router = APIRouter(prefix="/api/admin", tags=["admin-groups"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ============================================================
# FRONTEND ERROR-CODE CONTRACT (stable API surface — do not rename)
# ============================================================

E_UNAUTHORIZED = "api.auth.unauthorized"
E_INSUFFICIENT = "api.admin.insufficient_permissions"
E_EXAMPLE_BLOCKED = "api.admin.example_blocked"
E_ONLY_FULL_ADMIN = "api.admin.only_full_admin"
E_MISSING_USER_ID = "api.admin.missing_user_id"
E_USER_NOT_FOUND = "api.admin.user_not_found"
E_INVALID_GROUP_ID = "api.admin.invalid_group_id"
E_MISSING_GROUP_ID = "api.admin.missing_group_id"
E_DESCRIPTION_REQUIRED = "api.admin.description_required"
E_ALREADY_FULL_ADMIN = "api.admin.already_full_admin"
E_CANNOT_PROMOTE_EXAMPLE = "api.admin.cannot_promote_example"
E_ALREADY_GROUP_ADMIN = "api.admin.already_group_admin"
E_CANNOT_DEMOTE_SELF = "api.admin.cannot_demote_self"
E_CANNOT_DEMOTE_FULL_ADMIN = "api.admin.cannot_demote_full_admin"
E_NOT_GROUP_ADMIN = "api.admin.not_group_admin"
E_PROMOTE_ERROR = "api.admin.promote_error"
E_DEMOTE_ERROR = "api.admin.demote_error"
E_NO_GROUP = "api.admin.no_group"
E_GROUPS_LOAD_ERROR = "api.admin.groups_load_error"
E_GROUPS_STATS_ERROR = "api.admin.groups_stats_error"
E_GROUP_USERS_LOAD_ERROR = "api.admin.group_users_load_error"
E_USER_LOAD_ERROR = "api.admin.user_load_error"
E_UPDATE_ERROR = "api.admin.update_error"
E_DELETE_ERROR = "api.admin.delete_error"
E_NO_FIELDS = "api.admin.no_fields"
E_CANNOT_DELETE_SELF = "api.admin.cannot_delete_self"
E_INVALID_UPLOAD_SIZE = "api.admin.invalid_upload_size"
E_INVALID_UPLOAD_COUNT = "api.admin.invalid_upload_count"
E_DEMO_USER_UPLOAD_SIZE_LIMIT = "api.admin.users_demo_upload_size_limit"
E_DEMO_USER_UPLOAD_COUNT_LIMIT = "api.admin.users_demo_upload_count_limit"

# Prisma select clauses, mirrored exactly.
_GROUP_SELECT = ("groupId", "groupDescription")
_USERS_LIST_SELECT = ("id", "email", "name", "isAdmin", "isGroupAdmin",
                      "isExampleUser", "emailVerified", "bccRegistrations",
                      "createdAt", "deletedAt", "userGroup", "maxUploadSizeMB",
                      "maxUploadCount", "emailNotifications", "darkMode",
                      "language")
_USER_DETAIL_SELECT = ("id", "email", "name", "userGroup", "isAdmin",
                       "isGroupAdmin", "isExampleUser", "emailVerified",
                       "createdAt", "deletedAt", "maxUploadSizeMB",
                       "maxUploadCount", "emailNotifications", "darkMode",
                       "language", "defaultAIConnectionId")
_PROMOTE_SELECT = ("id", "email", "name", "isAdmin", "isGroupAdmin",
                   "isExampleUser", "userGroup")


# ============================================================
# HELPERS
# ============================================================

def _cols(select):
    return ", ".join(f'"{c}"' for c in select)


def _public(row, select):
    """Format a DB row for the wire: datetime → ISO Z string."""
    out: Dict[str, Any] = {}
    for col in select:
        v = row[col]
        out[col] = iso_utc(v) if hasattr(v, "isoformat") else v
    return out


async def _get_user_row(user_id: str, select=_USER_DETAIL_SELECT):
    async with _db_pool.acquire() as conn:
        return await conn.fetchrow(
            f'SELECT {_cols(select)} FROM "User" WHERE id = $1', user_id
        )


async def _get_group_description(group_id: str) -> Optional[str]:
    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT "groupDescription" FROM "UserGroup" WHERE "groupId" = $1',
            group_id,
        )
    return row["groupDescription"] if row else None


async def _can_manage_group_users(uid: str) -> bool:
    """lib/admin.ts canManageGroupUsers: example -> false; full -> true;
    group admin -> true; regular -> false."""
    if await _is_example(uid):
        return False
    if await _is_admin(uid):
        return True
    return await _is_group_admin(uid)


async def _can_promote(uid: str, target_id: str) -> bool:
    """lib/admin.ts canPromoteGroupAdmin: example -> false; full -> true;
    group admin -> target in own group; regular -> false."""
    if await _is_example(uid):
        return False
    if await _is_admin(uid):
        return True
    if await _is_group_admin(uid):
        target_group = await _user_group(target_id)
        return target_group is not None and target_group == await _user_group(uid)
    return False


# ============================================================
# REQUEST MODELS
# ============================================================

class PromoteRequest(BaseModel):
    userId: Optional[str] = None


class GroupUserUpdateRequest(BaseModel):
    # snake_case — mirrors the frontend PUT /api/admin/groups/user body.
    user_id: Optional[str] = None
    user_group: Optional[str] = None


class GroupUsersPatchRequest(BaseModel):
    userId: Optional[str] = None
    name: Optional[str] = None
    emailNotifications: Optional[bool] = None
    darkMode: Optional[bool] = None
    language: Optional[str] = None
    maxUploadSizeMB: Optional[Any] = None
    maxUploadCount: Optional[Any] = None
    isGroupAdmin: Optional[bool] = None


class GroupDescriptionRequest(BaseModel):
    group_id: Optional[str] = None
    description: Optional[str] = None


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/groups")
async def list_groups(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if (not await _is_admin(uid) and not await _is_group_admin(uid)
                and not await _is_example(uid)):
            return await _error(403, E_INSUFFICIENT, language)

        if await _is_admin(uid):
            async with _db_pool.acquire() as conn:
                rows = await conn.fetch(
                    f'SELECT {_cols(_GROUP_SELECT)} FROM "UserGroup" ORDER BY "groupId" ASC'
                )
            return {"groups": [_public(r, _GROUP_SELECT) for r in rows]}

        group_id = await _user_group(uid)
        if not group_id:
            return {"groups": []}
        desc = await _get_group_description(group_id)
        if desc is None:
            return {"groups": []}
        return {"groups": [{"groupId": group_id, "groupDescription": desc}]}
    except Exception:
        return await _error(500, E_GROUPS_LOAD_ERROR, language)


@router.post("/groups/promote")
async def promote_user(
    body: PromoteRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if await _is_example(uid):
            return await _error(403, E_EXAMPLE_BLOCKED, language)

        target = body.userId
        if not target:
            return await _error(400, E_MISSING_USER_ID, language)

        if not await _can_promote(uid, target):
            return await _error(403, E_INSUFFICIENT, language)

        row = await _get_user_row(target, _PROMOTE_SELECT)
        if row is None:
            return await _error(404, E_USER_NOT_FOUND, language)
        if row["isAdmin"] is True:
            return await _error(400, E_ALREADY_FULL_ADMIN, language)
        if row["isExampleUser"] is True:
            return await _error(400, E_CANNOT_PROMOTE_EXAMPLE, language)
        if row["isGroupAdmin"] is True:
            return await _error(400, E_ALREADY_GROUP_ADMIN, language)

        async with _db_pool.acquire() as conn:
            updated = await conn.fetchrow(
                f'UPDATE "User" SET "isGroupAdmin" = true, "updatedAt" = NOW() '
                f'WHERE id = $1 RETURNING {_cols(_PROMOTE_SELECT)}',
                target,
            )
        name = updated["name"] or updated["email"]
        return {
            "success": True,
            "message": await t(_db_pool, language, ADMIN["api.admin.promote_success"], name=name),
            "user": _public(updated, _PROMOTE_SELECT),
        }
    except Exception:
        return await _error(500, E_PROMOTE_ERROR, language)


@router.delete("/groups/promote")
async def demote_user(
    req: Request,
    userId: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if await _is_example(uid):
            return await _error(403, E_EXAMPLE_BLOCKED, language)

        if not userId:
            return await _error(400, E_MISSING_USER_ID, language)
        if uid == userId:
            return await _error(400, E_CANNOT_DEMOTE_SELF, language)

        if not await _can_promote(uid, userId):
            return await _error(403, E_INSUFFICIENT, language)

        row = await _get_user_row(userId, _PROMOTE_SELECT)
        if row is None:
            return await _error(404, E_USER_NOT_FOUND, language)
        if row["isAdmin"] is True:
            return await _error(400, E_CANNOT_DEMOTE_FULL_ADMIN, language)
        if row["isGroupAdmin"] is not True:
            return await _error(400, E_NOT_GROUP_ADMIN, language)

        async with _db_pool.acquire() as conn:
            updated = await conn.fetchrow(
                f'UPDATE "User" SET "isGroupAdmin" = false, "updatedAt" = NOW() '
                f'WHERE id = $1 RETURNING {_cols(_PROMOTE_SELECT)}',
                userId,
            )
        name = updated["name"] or updated["email"]
        return {
            "success": True,
            "message": await t(_db_pool, language, ADMIN["api.admin.demote_success"], name=name),
            "user": _public(updated, _PROMOTE_SELECT),
        }
    except Exception:
        return await _error(500, E_DEMOTE_ERROR, language)


@router.get("/groups/shared")
async def group_stats(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if not await _is_admin(uid):
            return await _error(403, E_ONLY_FULL_ADMIN, language)

        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                f'SELECT {_cols(_GROUP_SELECT)} FROM "UserGroup" ORDER BY "groupId" ASC'
            )
            result = []
            for group in rows:
                gid = group["groupId"]
                counts = {}
                for table, col in (
                    ("UserAIConnection", "aiConnectionGroup"),
                    ("UserDatabaseConnection", "dbConnectionGroup"),
                    ("Recipe", "recipeGroup"),
                    ("UserDataset", "datasetGroup"),
                    ("User", "userGroup"),
                ):
                    counts[col] = await conn.fetchval(
                        f'SELECT COUNT(*) FROM "{table}" WHERE "{col}" = $1', gid
                    )
                result.append({
                    "groupId": group["groupId"],
                    "groupDescription": group["groupDescription"],
                    "stats": {
                        "users": counts["userGroup"],
                        "aiConnections": counts["aiConnectionGroup"],
                        "dbConnections": counts["dbConnectionGroup"],
                        "recipes": counts["recipeGroup"],
                        "datasets": counts["datasetGroup"],
                    },
                })
        return {"groups": result}
    except Exception:
        return await _error(500, E_GROUPS_STATS_ERROR, language)


@router.put("/groups/user")
async def update_user_group(
    body: GroupUserUpdateRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if await _is_example(uid):
            return await _error(403, E_EXAMPLE_BLOCKED, language)
        if not await _is_admin(uid):
            return await _error(403, E_ONLY_FULL_ADMIN, language)

        if not body.user_id:
            return await _error(400, E_MISSING_USER_ID, language)
        if body.user_group is None:
            # Frontend: comparing undefined user_group throws -> 500 update_error.
            return await _error(500, E_UPDATE_ERROR, language)
        if body.user_group < "00" or body.user_group > "99":
            return await _error(400, E_INVALID_GROUP_ID, language)

        row = await _get_user_row(body.user_id, ("id",))
        if row is None:
            return await _error(404, E_USER_NOT_FOUND, language)

        async with _db_pool.acquire() as conn:
            await conn.execute(
                'UPDATE "User" SET "userGroup" = $1, "updatedAt" = NOW() WHERE id = $2',
                body.user_group, body.user_id,
            )
        return {"success": True, "user_id": body.user_id, "user_group": body.user_group}
    except Exception:
        return await _error(500, E_UPDATE_ERROR, language)


@router.get("/groups/user/{user_id}")
async def get_group_user(
    user_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)

        full = await _is_admin(uid)
        if (not full and not await _is_group_admin(uid)
                and not await _is_example(uid)):
            return await _error(403, E_INSUFFICIENT, language)

        if not full:
            caller_group = await _user_group(uid)
            target_group = await _user_group(user_id)
            if (caller_group is None or target_group is None
                    or target_group != caller_group):
                return await _error(403, E_INSUFFICIENT, language)

        row = await _get_user_row(user_id, _USER_DETAIL_SELECT)
        if row is None:
            return await _error(404, E_USER_NOT_FOUND, language)

        group_description = await _get_group_description(row["userGroup"])
        return {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
            "userGroup": row["userGroup"],
            "groupDescription": group_description or "Unknown",
            "isAdmin": row["isAdmin"],
            "isGroupAdmin": row["isGroupAdmin"],
            "isExampleUser": row["isExampleUser"],
            "emailVerified": iso_utc(row["emailVerified"]),
            "createdAt": iso_utc(row["createdAt"]),
            "deletedAt": iso_utc(row["deletedAt"]),
            "maxUploadSizeMB": row["maxUploadSizeMB"],
            "maxUploadCount": row["maxUploadCount"],
            "emailNotifications": row["emailNotifications"],
            "darkMode": row["darkMode"],
            "language": row["language"],
            "defaultAIConnectionId": row["defaultAIConnectionId"],
        }
    except Exception:
        return await _error(500, E_USER_LOAD_ERROR, language)


@router.get("/groups/users")
async def list_group_users(
    req: Request,
    groupId: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if not await _can_manage_group_users(uid):
            return await _error(403, E_INSUFFICIENT, language)

        if await _is_admin(uid) and groupId:
            user_group = groupId
        else:
            user_group = await _user_group(uid)
            if not user_group:
                return await _error(400, E_NO_GROUP, language)

        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                f'SELECT {_cols(_USERS_LIST_SELECT)} FROM "User" '
                f'WHERE "userGroup" = $1 ORDER BY "createdAt" DESC',
                user_group,
            )
        group_description = await _get_group_description(user_group)
        return {
            "groupId": user_group,
            "groupDescription": group_description or "Unknown",
            "users": [_public(r, _USERS_LIST_SELECT) for r in rows],
        }
    except Exception:
        return await _error(500, E_GROUP_USERS_LOAD_ERROR, language)


@router.patch("/groups/users")
async def patch_group_user(
    body: GroupUsersPatchRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if await _is_example(uid):
            return await _error(403, E_EXAMPLE_BLOCKED, language)
        if not await _can_manage_group_users(uid):
            return await _error(403, E_INSUFFICIENT, language)

        target = body.userId
        if not target:
            return await _error(400, E_MISSING_USER_ID, language)
        if not await _can_manage(uid, target):
            return await _error(403, E_INSUFFICIENT, language)

        target_row = await _get_user_row(target, ("userGroup", "isAdmin"))
        if target_row is None:
            return await _error(404, E_USER_NOT_FOUND, language)

        full = await _is_admin(uid)

        caller_group = await _user_group(uid)
        if caller_group != target_row["userGroup"] and not full:
            return await _error(403, E_INSUFFICIENT, language)

        if target_row["isAdmin"] is True and not full:
            return await _error(403, E_INSUFFICIENT, language)

        data = body.model_dump(exclude_unset=True)

        size = data.get("maxUploadSizeMB")
        if size is not None and (isinstance(size, bool) or not isinstance(size, int) or size < 0):
            return await _error(400, E_INVALID_UPLOAD_SIZE, language)
        count = data.get("maxUploadCount")
        if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < 0):
            return await _error(400, E_INVALID_UPLOAD_COUNT, language)

        # Demo-mode constraint (mirrors global settings): same per-user columns
        # as /api/admin/users/{id}, reached via the group-admin route.
        if (size is not None or count is not None) and await current_demo_mode():
            if size is not None and (size == 0 or size > 5):
                return await _error(400, E_DEMO_USER_UPLOAD_SIZE_LIMIT, language)
            if count is not None and (count == 0 or count > 5):
                return await _error(400, E_DEMO_USER_UPLOAD_COUNT_LIMIT, language)

        if "isGroupAdmin" in data and target_row["isAdmin"] is True and not full:
            return await _error(403, E_INSUFFICIENT, language)

        updatable = ("name", "emailNotifications", "darkMode", "language",
                     "maxUploadSizeMB", "maxUploadCount", "isGroupAdmin")
        updates = {k: data[k] for k in updatable if k in data}
        if not updates:
            return await _error(400, E_NO_FIELDS, language)

        sets = ", ".join(f'"{k}" = ${i}' for i, k in enumerate(updates, start=2))
        async with _db_pool.acquire() as conn:
            updated = await conn.fetchrow(
                f'UPDATE "User" SET {sets} WHERE id = $1 '
                f'RETURNING {_cols(_USERS_LIST_SELECT)}',
                target, *updates.values(),
            )
        return {"success": True, "user": _public(updated, _USERS_LIST_SELECT)}
    except Exception:
        return await _error(500, E_UPDATE_ERROR, language)


@router.delete("/groups/users")
async def delete_group_user(
    req: Request,
    userId: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if await _is_example(uid):
            return await _error(403, E_EXAMPLE_BLOCKED, language)
        if not await _can_manage_group_users(uid):
            return await _error(403, E_INSUFFICIENT, language)

        if not userId:
            return await _error(400, E_MISSING_USER_ID, language)
        if uid == userId:
            return await _error(400, E_CANNOT_DELETE_SELF, language)
        if not await _can_manage(uid, userId):
            return await _error(403, E_INSUFFICIENT, language)

        target_row = await _get_user_row(userId, ("userGroup", "isAdmin"))
        if target_row is None:
            return await _error(404, E_USER_NOT_FOUND, language)

        caller_group = await _user_group(uid)
        if caller_group != target_row["userGroup"]:
            return await _error(403, E_INSUFFICIENT, language)

        full = await _is_admin(uid)
        if target_row["isAdmin"] is True and not full:
            return await _error(403, E_INSUFFICIENT, language)

        # SOFT delete — mirrors the frontend (deletedAt=now), unlike
        # admin/users DELETE which hard-deletes.
        async with _db_pool.acquire() as conn:
            await conn.execute(
                'UPDATE "User" SET "deletedAt" = NOW(), "updatedAt" = NOW() WHERE id = $1',
                userId,
            )
        return {"success": True}
    except Exception:
        return await _error(500, E_DELETE_ERROR, language)


@router.put("/groups/description")
async def update_group_description(
    body: GroupDescriptionRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if await _is_example(uid):
            return await _error(403, E_EXAMPLE_BLOCKED, language)
        if not await _is_admin(uid):
            return await _error(403, E_ONLY_FULL_ADMIN, language)

        if not body.group_id:
            return await _error(400, E_MISSING_GROUP_ID, language)
        if body.group_id < "00" or body.group_id > "99":
            return await _error(400, E_INVALID_GROUP_ID, language)
        if not body.description or body.description.strip() == "":
            return await _error(400, E_DESCRIPTION_REQUIRED, language)

        description = body.description.strip()
        async with _db_pool.acquire() as conn:
            result = await conn.execute(
                'UPDATE "UserGroup" SET "groupDescription" = $1, "updatedAt" = NOW() '
                'WHERE "groupId" = $2',
                description, body.group_id,
            )
        if result == "UPDATE 0":
            # Frontend: prisma.userGroup.update throws on a missing group ->
            # caught -> 500 update_error. Strict parity: mirror the 500.
            return await _error(500, E_UPDATE_ERROR, language)
        return {"success": True, "group_id": body.group_id, "description": description}
    except Exception:
        return await _error(500, E_UPDATE_ERROR, language)
