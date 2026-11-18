"""
Admin Users Router — P2 Group 1, item 1 (Prisma-removal plan).

Drop-in replacement for the frontend Prisma handlers:
  frontend/app/api/admin/users/route.ts       (GET list · PATCH batch admin actions · DELETE by body userId)
  frontend/app/api/admin/users/[id]/route.ts  (GET one · PATCH field update · DELETE by URL id)

Contract parity: same paths, same request/response JSON keys, same status
codes, same error envelope {error: <code>, message: <text>} — the frontend
admin UI must work unchanged when the rewrites point here.

Note: error responses use JSONResponse (not HTTPException) so the wire
shape matches the frontend handlers exactly ({error, message} at top
level, not FastAPI's {detail} wrapper). This is a deliberate, flagged
deviation from the backend's other routers — drop-in parity is the point.
"""

import os
import re
import uuid

import bcrypt
import jwt
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from src.utils.translation import t
from src.utils.password_validation import validate_password
from src.routers.datasets.crud import get_current_language
from src.routers.admin.translations import ADMIN
from src.postgres_data_manager import DATA_DB_NAME, drop_manifest_objects, user_schema_name
from src.utils.timestamps import iso_utc

router = APIRouter(prefix="/api/admin", tags=["admin-users"])
security = HTTPBearer(auto_error=False)

_db_pool = None

def set_db_pool(pool):
    global _db_pool
    _db_pool = pool

SECRET_KEY = os.getenv("NEXTAUTH_SECRET")
if not SECRET_KEY:
    print("WARNING: NEXTAUTH_SECRET not set")


# ============================================================
# FRONTEND ERROR-CODE CONTRACT (stable API surface — do not rename)
# ============================================================

E_UNAUTHORIZED = "api.auth.unauthorized"
E_INSUFFICIENT = "api.admin.insufficient_permissions"
E_ONLY_FULL_ADMIN = "api.admin.only_full_admin"
E_USER_NOT_FOUND = "api.admin.user_not_found"
E_CANNOT_DELETE_SELF = "api.admin.cannot_delete_self"
E_CANNOT_DEMOTE_SELF = "api.admin.cannot_demote_self"
E_MISSING_USER_ID = "api.admin.missing_user_id"
E_EXAMPLE_BLOCKED = "api.admin.example_blocked"
E_NO_FIELDS = "api.admin.no_fields"
E_INVALID_UPLOAD_SIZE = "api.admin.invalid_upload_size"
E_INVALID_UPLOAD_COUNT = "api.admin.invalid_upload_count"
E_DEMO_USER_UPLOAD_SIZE_LIMIT = "api.admin.users_demo_upload_size_limit"
E_DEMO_USER_UPLOAD_COUNT_LIMIT = "api.admin.users_demo_upload_count_limit"
E_INVALID_GROUP_ID = "api.admin.invalid_group_id"
E_DELETE_ERROR = "api.admin.delete_error"
E_USERS_LOAD_ERROR = "api.admin.users_load_error"
E_UPDATE_ERROR = "api.admin.update_error"
E_USER_LOAD_ERROR = "api.admin.user_load_error"
E_INVALID_EMAIL = "api.admin.invalid_email"
E_MISSING_FIELDS = "api.admin.missing_fields"
E_EMAIL_EXISTS = "api.admin.email_exists"
E_SETTINGS_NOT_FOUND = "api.admin.settings_not_found"
E_PASSWORD_VALIDATION_FAILED = "api.admin.password_validation_failed"
E_CREATE_USER_ERROR = "api.admin.create_user_error"
E_INVALID_ADMIN_PASSWORD = "api.admin.invalid_admin_password"
E_EXAMPLE_USER_PASSWORD_BLOCKED = "api.admin.example_user_password_blocked"

_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Prisma `select` clauses, mirrored exactly.
_LIST_SELECT = ("id", "email", "name", "isAdmin", "isGroupAdmin", "isExampleUser",
                "emailVerified", "bccRegistrations", "createdAt", "deletedAt", "userGroup")
_SINGLE_SELECT = ("id", "email", "name", "isAdmin", "isGroupAdmin", "isExampleUser",
                  "emailVerified", "bccRegistrations", "createdAt",
                  "maxUploadSizeMB", "maxUploadCount", "userGroup",
                  "emailNotifications", "darkMode", "language", "defaultAIConnectionId")


# ============================================================
# HELPERS
# ============================================================


def _public(row, select):
    """Format a DB row for the wire: datetime → ISO Z string (like toISOString)."""
    out: Dict[str, Any] = {}
    for col in select:
        v = row[col]
        out[col] = iso_utc(v) if isinstance(v, datetime) else v
    return out


async def _error(status: int, code: str, language: str, **kwargs) -> JSONResponse:
    message = await t(_db_pool, language, ADMIN[code], **kwargs)
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def _raw_error(status: int, code: str, message: str) -> JSONResponse:
    """Composed-message passthrough (password validation), mirroring register."""
    return JSONResponse(status_code=status, content={"error": code, "message": message})


async def current_demo_mode() -> bool:
    """True when the running system is in demo mode (backend mirror of the
    frontend isDemoSystem()); a missing settings row reads as not-demo."""
    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow('SELECT "demoMode" FROM "GlobalSettings" WHERE id = 1')
    return bool(row["demoMode"]) if row is not None else False


async def _auth(credentials: HTTPAuthorizationCredentials) -> Optional[str]:
    """NextAuth JWT → user id, or None (mirrors groups.py/statistics.py)."""
    if credentials is None:
        return None
    try:
        payload = jwt.decode(credentials.credentials, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("id")
        return user_id if user_id else None
    except jwt.PyJWTError:
        return None


async def _get_user(user_id: str, select=("isAdmin", "isGroupAdmin", "isExampleUser", "userGroup")):
    cols = ", ".join(f'"{c}"' for c in select)
    async with _db_pool.acquire() as conn:
        return await conn.fetchrow(f'SELECT {cols} FROM "User" WHERE id = $1', user_id)


async def _is_admin(uid: str) -> bool:
    row = await _get_user(uid, ("isAdmin",))
    return bool(row) and row["isAdmin"] is True


async def _is_group_admin(uid: str) -> bool:
    row = await _get_user(uid, ("isGroupAdmin",))
    return bool(row) and row["isGroupAdmin"] is True


async def _is_example(uid: str) -> bool:
    row = await _get_user(uid, ("isExampleUser",))
    return bool(row) and row["isExampleUser"] is True


async def _user_group(uid: str) -> Optional[str]:
    row = await _get_user(uid, ("userGroup",))
    return row["userGroup"] if row else None


async def _can_manage(admin_id: str, target_id: str) -> bool:
    """lib/admin.ts canManageUser: full admins anyone; group admins same group; examples no."""
    admin = await _get_user(admin_id)
    if not admin or admin["isExampleUser"] is True:
        return False
    if admin["isAdmin"] is True:
        return True
    if admin["isGroupAdmin"] is True:
        target = await _get_user(target_id, ("userGroup",))
        return bool(target) and target["userGroup"] == admin["userGroup"]
    return False


async def _visible_users(uid: str):
    """lib/admin.ts getVisibleUsers: role-scoped user list, createdAt DESC."""
    admin = await _get_user(uid)
    if admin is None:
        return []
    if admin["isAdmin"] is True or admin["isExampleUser"] is True:
        where, params = "", []
    elif admin["isGroupAdmin"] is True:
        where, params = 'WHERE "userGroup" = $1', [admin["userGroup"]]
    else:
        where, params = "WHERE id = $1", [uid]
    cols = ", ".join(f'"{c}"' for c in _LIST_SELECT)
    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(
            f'SELECT {cols} FROM "User" {where} ORDER BY "createdAt" DESC', *params
        )
    return [_public(r, _LIST_SELECT) for r in rows]


async def _objects_to_drop(conn, user_id: str) -> list:
    """What the account still owns in `workbench_data`, as manifest entries.

    One entry for the account's own schema — `u_<user_id>` — which is where every
    object a write path creates now lives, and whose removal is a single
    `DROP SCHEMA … CASCADE`. Then one entry per object still sitting in
    `public`: the tables written before Step B1, which stay there until the
    mover of Step B3 has been applied, and a materialised virtual dataset's
    `virtual_<id>` table. Then one entry per notebook import the account still has
    in `workbench_data`.

    Notebook imports are read from `NotebookImport`, not from `UserDataset`, and
    neither of the other two statements can see them: the import writes a dataset
    row only when `create_dataset` is set, and its schema is named for the import
    (`nb_<import_id>`, the naming `notebooks/storage.py` gives it) rather than for
    the account, so nothing about it is traceable once the rows that name it are
    gone. `storageType = 'postgresql'` with no external connection is the pair the
    import endpoint branches on for the internal `workbench_data` database; an
    import into a connection of the account's own keeps its schema in that
    database, where this cleanup does not reach and must not. One `NotebookImport`
    row covers the whole import, so its schema is named once however many `df_N`
    tables the import created.

    Objects no dataset row names belong to no account, so they are not this
    function's business — Step 7 disposes of them.

    `DROP … IF EXISTS` runs on the other side of these entries, so an entry for
    an object that is not there is a no-op rather than an error.
    """
    entries = [("user_schema", user_schema_name(user_id))]
    rows = await conn.fetch(
        'SELECT id, "sourceType", "databaseName", "tableName" FROM "UserDataset" WHERE "userId" = $1',
        user_id,
    )
    for row in rows:
        table = row["tableName"] or ""
        if row["sourceType"] == "virtual":
            entries.append(("virtual", f"virtual_{row['id']}"))
        elif table and "." not in table and row["databaseName"] == DATA_DB_NAME:
            entries.append(("clean" if table.startswith("clean_") else "upload", table))

    imports = await conn.fetch(
        'SELECT id FROM "NotebookImport" WHERE "userId" = $1 '
        'AND "storageType" = $2 AND ("connectionId" IS NULL OR "connectionId" = 0)',
        user_id,
        "postgresql",
    )
    for row in imports:
        entries.append(("notebook_schema", f"nb_{row['id'].replace('-', '_')}"))
    return entries


async def _delete_user(user_id: str) -> list:
    """Delete the account, recording what it still owns in `workbench_data` first.

    The capture and the delete share one transaction deliberately: the cascade
    takes the `UserDataset` rows that name the account's objects, so a manifest
    written separately could be lost to a crash and leave an account deleted with
    nothing to say what had to be dropped from the data database. The manifest
    table carries no foreign key to "User" for the same reason — this row has to
    outlive the delete it describes.

    An account with no objects still gets its schema entry, whose drop is a
    no-op, so the capture never has to read the data database to decide.

    Returns the manifest entries it wrote, for the caller to act on once this
    transaction has committed — nothing may be dropped before it has.
    """
    entries: list = []
    async with _db_pool.acquire() as conn:
        async with conn.transaction():
            for object_kind, object_name in await _objects_to_drop(conn, user_id):
                row = await conn.fetchrow(
                    'INSERT INTO "DataCleanupManifest" ("userId", "objectKind", "objectName") '
                    "VALUES ($1, $2, $3) RETURNING id",
                    user_id,
                    object_kind,
                    object_name,
                )
                entries.append({
                    "id": row["id"],
                    "userId": user_id,
                    "objectKind": object_kind,
                    "objectName": object_name,
                })
            await conn.execute('DELETE FROM "User" WHERE id = $1', user_id)
    return entries


async def _drop_after_commit(entries: list) -> Dict[str, list]:
    """Drop what the account owned, then clear the manifest rows that succeeded.

    By the time this runs the account is already gone. Its objects are in another
    database, so no transaction can span the two — each manifest row is therefore
    removed only once its object is really gone, which is what makes the cleanup
    retryable rather than best-effort: a row left behind is an object still to
    drop, and Step 5's sweep is what finishes it.
    """
    if not entries:
        return {"dropped": [], "failed": []}

    dropped: list = []
    failed: list = []
    results = await drop_manifest_objects(entries)
    async with _db_pool.acquire() as conn:
        for result in results:
            if result["dropped"]:
                await conn.execute(
                    'DELETE FROM "DataCleanupManifest" WHERE id = $1', result["id"]
                )
                dropped.append({
                    "objectKind": result["objectKind"],
                    "objectName": result["objectName"],
                })
            else:
                failed.append({
                    "objectKind": result["objectKind"],
                    "objectName": result["objectName"],
                    "error": result["error"],
                })
    return {"dropped": dropped, "failed": failed}


async def _update_user(user_id: str, updates: Dict[str, Any]):
    sets = ", ".join(f'"{k}" = ${i}' for i, k in enumerate(updates, start=2))
    sql = f'UPDATE "User" SET {sets} WHERE id = $1'
    async with _db_pool.acquire() as conn:
        await conn.execute(sql, user_id, *updates.values())


async def _update_user_returning(user_id: str, updates: Dict[str, Any]):
    sets = ", ".join(f'"{k}" = ${i}' for i, k in enumerate(updates, start=2))
    cols = ", ".join(f'"{c}"' for c in _SINGLE_SELECT)
    sql = f'UPDATE "User" SET {sets} WHERE id = $1 RETURNING {cols}'
    async with _db_pool.acquire() as conn:
        return await conn.fetchrow(sql, user_id, *updates.values())


async def _delete_flow(uid: str, target_id: str, language: str):
    """Shared logic for both DELETE variants (URL id + body userId)."""
    if await _is_example(uid):
        return await _error(403, E_EXAMPLE_BLOCKED, language)
    if uid == target_id:
        return await _error(400, E_CANNOT_DELETE_SELF, language)
    full = await _is_admin(uid)
    group_admin = await _is_group_admin(uid)
    if not full and not group_admin:
        return await _error(403, E_INSUFFICIENT, language)
    if not full and group_admin:
        target_group = await _user_group(target_id)
        if target_group is None:
            return await _error(404, E_USER_NOT_FOUND, language)
        if target_group != await _user_group(uid):
            return await _error(403, E_INSUFFICIENT, language)
    entries = await _delete_user(target_id)
    return {"success": True, "dataCleanup": await _drop_after_commit(entries)}


# ============================================================
# REQUEST MODELS
# ============================================================

class AdminActionRequest(BaseModel):
    userId: Optional[str] = None
    isAdmin: Optional[bool] = None
    isGroupAdmin: Optional[bool] = None
    bccRegistrations: Optional[bool] = None
    verify: Optional[bool] = None
    restore: Optional[bool] = None
    hardDelete: Optional[bool] = None


class AdminUserUpdateRequest(BaseModel):
    emailNotifications: Optional[bool] = None
    darkMode: Optional[bool] = None
    language: Optional[str] = None
    maxUploadSizeMB: Optional[Any] = None
    maxUploadCount: Optional[Any] = None
    userGroup: Optional[str] = None
    isGroupAdmin: Optional[bool] = None


class AdminDeleteRequest(BaseModel):
    userId: Optional[str] = None


class AdminCreateUserRequest(BaseModel):
    name: Optional[Any] = None
    email: Optional[Any] = None
    password: Optional[Any] = None
    language: Optional[Any] = None


# ============================================================
# ENDPOINTS
# ============================================================

@router.post("/users")
async def create_user(
    body: AdminCreateUserRequest,
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

        data = body.model_dump()

        email = data.get("email")
        if not isinstance(email, str) or not _EMAIL_RE.fullmatch(email):
            return await _error(400, E_INVALID_EMAIL, language)

        password = data.get("password")
        if not isinstance(password, str) or not password:
            return await _error(400, E_MISSING_FIELDS, language)

        name = data.get("name")
        user_language = data.get("language")
        if not isinstance(user_language, str) or not user_language:
            user_language = "en"

        async with _db_pool.acquire() as conn:
            settings = await conn.fetchrow(
                'SELECT "passwordPolicy", "passwordPolicyCustom", '
                '"defaultMaxUploadSizeMB", "defaultMaxUploadCount" '
                'FROM "GlobalSettings" WHERE id = 1'
            )
        if settings is None:
            return await _error(500, E_SETTINGS_NOT_FOUND, language)

        policy_name = settings["passwordPolicy"] or "medium"
        custom = settings["passwordPolicyCustom"]
        if not isinstance(custom, dict):
            custom = None

        errors = validate_password(password, policy_name, custom)
        if errors:
            messages = [await t(_db_pool, user_language, key, **kwargs) for key, kwargs in errors]
            return _raw_error(400, E_PASSWORD_VALIDATION_FAILED, " ".join(messages))

        async with _db_pool.acquire() as conn:
            existing = await conn.fetchrow('SELECT id FROM "User" WHERE email = $1', email)
        if existing is not None:
            return await _error(400, E_EMAIL_EXISTS, language)

        hashed = bcrypt.hashpw(password.encode("utf-8"),
                               bcrypt.gensalt(rounds=10)).decode("utf-8")
        user_id = str(uuid.uuid4())

        cols = ", ".join(f'"{c}"' for c in _SINGLE_SELECT)
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'INSERT INTO "User" '
                '(id, email, password, name, "emailVerified", "maxUploadSizeMB", '
                '"maxUploadCount", language, "emailNotifications", "darkMode", "updatedAt") '
                f'VALUES ($1, $2, $3, $4, $5, $6, $7, $8, false, false, NOW()) RETURNING {cols}',
                user_id, email, hashed, name, datetime.now(timezone.utc),
                settings["defaultMaxUploadSizeMB"] or 0,
                settings["defaultMaxUploadCount"] or 0,
                user_language,
            )

        return {"success": True, "user": _public(row, _SINGLE_SELECT)}
    except Exception:
        return await _error(500, E_CREATE_USER_ERROR, language)


@router.get("/users")
async def list_users(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        user_id = await _auth(credentials)
        if user_id is None:
            return await _error(401, E_UNAUTHORIZED, language)
        # canModifyAdminResources: full admin only; example users pass through read-only.
        if not await _is_admin(user_id) and not await _is_example(user_id):
            return await _error(403, E_INSUFFICIENT, language)
        return {"users": await _visible_users(user_id)}
    except Exception:
        return await _error(500, E_USERS_LOAD_ERROR, language)


@router.get("/users/{user_id}")
async def get_user(
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
        example = await _is_example(uid)
        if not full and not example:
            if await _is_group_admin(uid):
                target_group = await _user_group(user_id)
                if target_group is None or target_group != await _user_group(uid):
                    return await _error(403, E_INSUFFICIENT, language)
            elif uid != user_id:
                return await _error(403, E_INSUFFICIENT, language)
        row = await _get_user(user_id, _SINGLE_SELECT)
        if row is None:
            return await _error(404, E_USER_NOT_FOUND, language)
        return {"user": _public(row, _SINGLE_SELECT)}
    except Exception:
        return await _error(500, E_USER_LOAD_ERROR, language)


@router.patch("/users")
async def admin_action(
    body: AdminActionRequest,
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

        data = body.model_dump(exclude_unset=True)
        target = data.get("userId")
        if not target:
            return await _error(400, E_MISSING_USER_ID, language)
        if not await _can_manage(uid, target):
            return await _error(403, E_INSUFFICIENT, language)

        # Self-demotion guard: a user cannot remove their own admin or
        # group-admin status (mirrors the frontend PATCH guard; DELETE has its
        # own self-guard).
        if target == uid and (
            data.get("isAdmin") is False or data.get("isGroupAdmin") is False
        ):
            return await _error(400, E_CANNOT_DEMOTE_SELF, language)

        full = await _is_admin(uid)

        if data.get("hardDelete"):
            if not full:
                return await _error(403, E_ONLY_FULL_ADMIN, language)
            entries = await _delete_user(target)
            return {"success": True, "dataCleanup": await _drop_after_commit(entries)}

        if "isAdmin" in data and not full:
            return await _error(403, E_ONLY_FULL_ADMIN, language)

        updates: Dict[str, Any] = {}
        if "isAdmin" in data:
            updates["isAdmin"] = data["isAdmin"]
        if "isGroupAdmin" in data:
            target_row = await _get_user(target, ("userGroup",))
            if target_row is None:
                return await _error(404, E_USER_NOT_FOUND, language)
            if not full:
                admin_row = await _get_user(uid, ("userGroup",))
                if admin_row["userGroup"] != target_row["userGroup"]:
                    return await _error(403, E_INSUFFICIENT, language)
            updates["isGroupAdmin"] = data["isGroupAdmin"]
        if "bccRegistrations" in data:
            updates["bccRegistrations"] = data["bccRegistrations"]
        # Frontend semantics: verify=false → no change; verify=true → emailVerified=now.
        if data.get("verify"):
            updates["emailVerified"] = datetime.now(timezone.utc)
        # restore=false → no change; restore=true → deletedAt=null.
        if data.get("restore"):
            updates["deletedAt"] = None

        if not updates:
            return await _error(400, E_NO_FIELDS, language)

        await _update_user(target, updates)
        return {"success": True}
    except Exception:
        return await _error(500, E_UPDATE_ERROR, language)


@router.patch("/users/{user_id}")
async def update_user_fields(
    user_id: str,
    body: AdminUserUpdateRequest,
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

        data = body.model_dump(exclude_unset=True)
        if not await _can_manage(uid, user_id):
            return await _error(403, E_INSUFFICIENT, language)

        full = await _is_admin(uid)

        size = data.get("maxUploadSizeMB")
        if size is not None and (isinstance(size, bool) or not isinstance(size, int) or size < 0):
            return await _error(400, E_INVALID_UPLOAD_SIZE, language)
        count = data.get("maxUploadCount")
        if count is not None and (isinstance(count, bool) or not isinstance(count, int) or count < 0):
            return await _error(400, E_INVALID_UPLOAD_COUNT, language)

        # Demo-mode constraint (mirrors global settings): this endpoint cannot
        # toggle demoMode, so the current value is the effective value.
        if (size is not None or count is not None) and await current_demo_mode():
            if size is not None and (size == 0 or size > 5):
                return await _error(400, E_DEMO_USER_UPLOAD_SIZE_LIMIT, language)
            if count is not None and (count == 0 or count > 5):
                return await _error(400, E_DEMO_USER_UPLOAD_COUNT_LIMIT, language)

        if "userGroup" in data:
            if not full:
                return await _error(403, E_ONLY_FULL_ADMIN, language)
            if not ("00" <= data["userGroup"] <= "99"):
                return await _error(400, E_INVALID_GROUP_ID, language)

        if "isGroupAdmin" in data and not full:
            target_row = await _get_user(user_id, ("userGroup",))
            admin_row = await _get_user(uid, ("userGroup",))
            if target_row is None or target_row["userGroup"] != admin_row["userGroup"]:
                return await _error(403, E_INSUFFICIENT, language)

        updatable = {"emailNotifications", "darkMode", "language", "maxUploadSizeMB",
                     "maxUploadCount", "userGroup", "isGroupAdmin"}
        updates = {k: data[k] for k in updatable if k in data}

        updated = await _update_user_returning(user_id, updates)
        if updated is None:
            # Record not found -> 404, not the P2025 -> 500 mirror (item 16).
            return await _error(404, E_USER_NOT_FOUND, language)
        return {"success": True, "user": _public(updated, _SINGLE_SELECT)}
    except Exception:
        return await _error(500, E_UPDATE_ERROR, language)


@router.delete("/users")
async def delete_user_by_body(
    body: AdminDeleteRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    uid = await _auth(credentials)
    if uid is None:
        return await _error(401, E_UNAUTHORIZED, language)
    if not body.userId:
        return await _error(400, E_MISSING_USER_ID, language)
    try:
        return await _delete_flow(uid, body.userId, language)
    except Exception:
        return await _error(500, E_DELETE_ERROR, language)


@router.delete("/users/{user_id}")
async def delete_user_by_id(
    user_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    uid = await _auth(credentials)
    if uid is None:
        return await _error(401, E_UNAUTHORIZED, language)
    try:
        return await _delete_flow(uid, user_id, language)
    except Exception:
        return await _error(500, E_DELETE_ERROR, language)


# ============================================================
# SET PASSWORD (admin sets another user's password)
# ============================================================

class AdminSetPasswordRequest(BaseModel):
    # Deliberately `Optional[Any]`: every field is type-gated in the handler so a
    # malformed body is this route's own coded 400, not a framework 422 — the
    # house style in this module.
    adminPassword: Optional[Any] = None
    userEmail: Optional[Any] = None
    newPassword: Optional[Any] = None


@router.post("/set-password")
async def set_user_password(
    body: AdminSetPasswordRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Set another account's password, confirmed by the caller's own password.

    Contract:
      - The caller is identified by the bearer token ONLY. The token's `id` claim
        is the single claim read; the admin's email is looked up from it, and
        `isAdmin` comes from the database — never from the token's `isAdmin` claim,
        which tool-minted tokens do not carry at all and which is client-supplied.
      - The admin's own password is re-verified against the stored hash. This is a
        re-authentication step, not an identity input.
      - The new password is validated against the global password policy in the
        caller's language, before the credential is compared (change-password's
        ordering).
      - Example accounts are refused: an administrator may not set an example
        user's password, mirroring the block self-service change-password applies
        in the other direction.
      - No restriction on the target: another admin, or the caller themselves.

    Ordering: gate → policy → target → example block → credential → write.
    """
    try:
        # 1. The caller, from the token (401 when absent/invalid).
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)

        # 2. Authorisation, before the body is read — every route in this module
        #    does this, and isAdmin is the database's answer, not the token's.
        caller = await _get_user(uid, ("email", "isAdmin", "password"))
        if caller is None or caller["isAdmin"] is not True:
            return await _error(403, E_ONLY_FULL_ADMIN, language)

        data = body.model_dump()

        # 3. Input gate — non-empty strings, no coercion.
        admin_password = data.get("adminPassword")
        user_email = data.get("userEmail")
        new_password = data.get("newPassword")
        if (not isinstance(admin_password, str) or not admin_password
                or not isinstance(user_email, str) or not user_email
                or not isinstance(new_password, str) or not new_password):
            return await _error(400, E_MISSING_FIELDS, language)

        # 4. The new password's policy, in the caller's language.
        async with _db_pool.acquire() as conn:
            settings = await conn.fetchrow(
                'SELECT "passwordPolicy", "passwordPolicyCustom" '
                'FROM "GlobalSettings" WHERE id = 1'
            )
        policy_name = (settings["passwordPolicy"] or "medium") if settings is not None else "medium"
        custom = settings["passwordPolicyCustom"] if settings is not None else None
        if not isinstance(custom, dict):
            custom = None

        errors = validate_password(new_password, policy_name, custom)
        if errors:
            messages = [await t(_db_pool, language, key, **kwargs) for key, kwargs in errors]
            return _raw_error(400, E_PASSWORD_VALIDATION_FAILED, " ".join(messages))

        # 5. The target.
        if not _EMAIL_RE.fullmatch(user_email):
            return await _error(400, E_INVALID_EMAIL, language)

        async with _db_pool.acquire() as conn:
            target = await conn.fetchrow(
                'SELECT id, "isExampleUser" FROM "User" '
                'WHERE email = $1 AND "deletedAt" IS NULL',
                user_email,
            )
        if target is None:
            return await _error(404, E_USER_NOT_FOUND, language)

        # 6. Example accounts are not settable, by anyone.
        if target["isExampleUser"] is True:
            return await _error(403, E_EXAMPLE_USER_PASSWORD_BLOCKED, language)

        # 7. The admin's own password. A NULL stored hash cannot be compared and is
        #    an account anomaly, not a wrong password, so it is a 500 like the
        #    bcrypt failures; only a genuine mismatch is a 400.
        if caller["password"] is None:
            return await _error(500, E_UPDATE_ERROR, language)
        try:
            valid = bcrypt.checkpw(
                admin_password.encode("utf-8"), caller["password"].encode("utf-8")
            )
        except (TypeError, ValueError):
            return await _error(500, E_UPDATE_ERROR, language)
        if not valid:
            return await _error(400, E_INVALID_ADMIN_PASSWORD, language)

        # 8. Hash and write. Same cost factor as account creation.
        hashed = bcrypt.hashpw(new_password.encode("utf-8"),
                               bcrypt.gensalt(rounds=10)).decode("utf-8")
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'UPDATE "User" SET password = $1, "updatedAt" = NOW() '
                'WHERE id = $2 RETURNING id',
                hashed, target["id"],
            )
        if row is None:
            return await _error(500, E_UPDATE_ERROR, language)
        return {"success": True}
    except Exception:
        return await _error(500, E_UPDATE_ERROR, language)