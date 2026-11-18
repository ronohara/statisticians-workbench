"""
User Database Connections Router — P2 Group 4, item 18 (Prisma-removal plan).

Drop-in replacement for the frontend Prisma handler:
  frontend/app/api/user/database-connections/route.ts   (GET · POST · PATCH · DELETE)

Contract parity:

  - GET: any authenticated user (no example block) lists their OWN rows plus
    rows shared to their group (isShared=true AND dbConnectionGroup = the
    user's group). A missing user row (ghost session) reads group "00" — a
    ghost GET therefore returns the shared-"00" rows, NOT a 404. password is
    AES-256-GCM decrypted (null when absent or corrupt); the numeric
    connectionId is mirrored as id (string) alongside the Prisma spread; each
    row carries userName (owner's name, "Unknown User" when the owner row is
    missing) and isOwn. Rows order by createdAt ASC. The connection shape is
    the full Prisma spread + id/userName/isOwn (NOT the POST/PATCH curated
    shape).

  - POST: example users blocked (403) BEFORE the body is read. name/type/host/
    port/database/username/password JS-falsy -> 400 missing_fields; duplicate
    (userId, name) -> 400 connection_name_exists (with the empty-object
    no-op-filter quirk mirroring item 12); password AES-encrypted on store;
    port clean-validated (non-integer -> 400 invalid_port); dbConnectionGroup || "00";
    isShared = shared || false (truthy non-bool -> 500); canCreate* === true.
    auto_create_tables/auto_create_views truthy: create the row, then POST
    /api/datasets/auto-create forwarding the user's bearer token (the endpoint
    requires HTTPBearer); on any non-ok response delete the row and return 502
    auto_create_failed with the extracted detail. Body quirks: null body -> 500 (destructuring throws);
    a non-object body -> 400 (destructuring yields all-undefined); truthy
    non-strings hit Prisma validation -> 500 (String/Boolean/Int columns).

  - PATCH: id JS-falsy -> 400 connection_id_required; id strict-validated as
    a decimal-digit string -> 400 invalid_connection_id (item 11); the row
    lookup is the caller's own row, or — for an administrator — a row shared
    to the caller's group (404 connection_not_found otherwise, so a caller who
    may not act on the row cannot probe its existence); updateData uses !== undefined (key-present), so null
    is passed through and hits Prisma validation -> 500 for String/Boolean
    columns, while "" is stored; port clean-validated (non-integer -> 400); password re-encrypted
    (null/non-string -> 500); shared maps to isShared RAW (no || false here);
    absent fields are untouched; a fully empty update is a 200 no-op. P2025 ->
    500.

  - DELETE: query-param id (strict-validated as PATCH); the caller's own row,
    or — for an administrator — a row shared to the caller's group (404
    otherwise); plain delete (no defaultAI-equivalent back-reference on User).
    200 success:true.

Error shape: the CODED envelope {error: code, message: msg} — the same shape
as item 12's parent route. Option b: the code is the literal frontend code
string (stable API surface), and the message is routed through t() with a
TranslationKey whose English fallback is the frontend's exact string. The two
genuinely-dynamic cases mirror the frontend's passthrough: auto_create_failed's
message is the live auto-create detail (default detail goes through t()), and
the POST catch's message is the raw exception string.

Auth: HTTPBearer(auto_error=False) + _auth (JWT decode) shared from
admin.users.py; the no-token 401 {"detail": "Not authenticated"} comes from
the get_current_language dependency (crud.py security=HTTPBearer()). The
invalid-token coded 401 {error: "api.auth.unauthorized"} comes from _auth
returning None.

Encryption: utils/encryption.encrypt_field / decrypt_field_or_null
(AES-256-GCM iv:authTag:ciphertext base64, byte-compatible with @/lib/encryption).
"""

import json
import os

import httpx

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth, _is_example, _is_admin, _user_group
from src.routers.user.ai_connections import (
    _js_truthy,
)
from src.utils.encryption import encrypt_field, decrypt_field_or_null
from src.routers.user.translations import USER
from src.utils.translation import t
from src.routers.common.feature_gate import require_db_feature
from src.utils.timestamps import iso_utc

router = APIRouter(prefix="/api/user/database-connections",
                   tags=["user-database-connections"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ============================================================
# FRONTEND ERROR-CODE CONTRACT (stable API surface — do not rename)
# ============================================================

E_UNAUTHORIZED = "api.auth.unauthorized"
E_EXAMPLE_BLOCKED = "api.user.example_blocked"
E_MISSING_FIELDS = "api.user.missing_fields"
E_CONNECTION_NAME_EXISTS = "api.user.connection_name_exists"
E_AUTO_CREATE_FAILED = "api.user.auto_create_failed"
E_CONNECTION_NOT_FOUND = "api.user.connection_not_found"
E_INTERNAL_ERROR = "api.user.internal_error"
E_INVALID_PORT = "api.user.invalid_port"
E_INVALID_CONNECTION_ID = "api.user.invalid_connection_id"


async def _error(status: int, code: str, language: str, **kwargs) -> JSONResponse:
    """Coded-envelope error routed through t() (option b): the English
    fallback matches the frontend's exact string, so parity holds for English;
    the message is translatable once extracted/imported."""
    message = await t(_db_pool, language, USER[code], **kwargs)
    return JSONResponse(status_code=status,
                        content={"error": code, "message": message})


def _raw_error(status: int, code: str, message: str) -> JSONResponse:
    """Dynamic-message passthrough (the POST catch mirrors the frontend's raw
    error.message — no t() lookup, the message is runtime data)."""
    return JSONResponse(status_code=status,
                        content={"error": code, "message": message})


async def _t_error(status_code: int, key: str, language: str, **kwargs) -> JSONResponse:
    """Bare-string error routed through t() (option b) — the item-19 /available
    sub-route uses the item-13/14/15 bare-string shape {"error": "<string>"}
    (no code/message), unlike the item-18 parent route's coded envelope. The
    English fallback matches the frontend's exact string."""
    message = await t(_db_pool, language, USER[key], **kwargs)
    return JSONResponse(status_code=status_code, content={"error": message})


def _conn_body(row):
    """The POST/PATCH response shape: the full Prisma row with password nulled
    and dbConnectionGroup defaulted. NO id string, NO userName, NO isOwn."""
    return {
        "connectionId": row["connectionId"],
        "userId": row["userId"],
        "name": row["name"],
        "type": row["type"],
        "host": row["host"],
        "port": row["port"],
        "database": row["database"],
        "username": row["username"],
        "password": None,
        "createdAt": iso_utc(row["createdAt"]),
        "updatedAt": iso_utc(row["updatedAt"]),
        "dbConnectionGroup": row["dbConnectionGroup"] or "00",
        "isShared": row["isShared"],
        "canCreateDatabase": row["canCreateDatabase"],
        "canCreateTables": row["canCreateTables"],
    }


def _get_body(row, user_map, session_uid):
    """The GET response shape: the full Prisma spread + id (string) +
    decrypted password + userName + isOwn."""
    return {
        "connectionId": row["connectionId"],
        "userId": row["userId"],
        "name": row["name"],
        "type": row["type"],
        "host": row["host"],
        "port": row["port"],
        "database": row["database"],
        "username": row["username"],
        "password": decrypt_field_or_null(row["password"]),
        "createdAt": iso_utc(row["createdAt"]),
        "updatedAt": iso_utc(row["updatedAt"]),
        "dbConnectionGroup": row["dbConnectionGroup"] or "00",
        "isShared": row["isShared"],
        "canCreateDatabase": row["canCreateDatabase"] is True,
        "canCreateTables": row["canCreateTables"] is True,
        "id": str(row["connectionId"]),
        "userName": (user_map.get(row["userId"]) or {}).get("name") or "Unknown User",
        "isOwn": row["userId"] == session_uid,
        # The probe's stored result, so the connection page can show it.
        #
        # These four columns were already read — the query is `SELECT *` — and
        # then dropped here, because this dict is written by hand. Measured
        # 2026-11-06: the probe state existed on every row and no surface could
        # display it, so a user had no way to know a connection had ever been
        # checked, when, or with what answer.
        #
        # Both timestamps are sent, and they are not duplicates: `probedAt` is
        # when the last probe ran (success or failure), `probeSuccessAt` is when
        # it last *succeeded* and is untouched by a failure. A connection that
        # failed a minute ago but worked for three days is a different situation
        # from one that has never worked, and one timestamp cannot say which.
        "probeState": row.get("probeState"),
        "probeDetail": row.get("probeDetail"),
        # `iso_utc` already returns None for a null timestamp, so the guard only
        # protects against a row that predates the columns.
        "probedAt": iso_utc(row.get("probedAt")),
        "probeSuccessAt": iso_utc(row.get("probeSuccessAt")),
    }


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("")
async def get_database_connections(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)

        async with _db_pool.acquire() as conn:
            user = await conn.fetchrow(
                'SELECT "userGroup" FROM "User" WHERE id = $1', uid
            )
            user_group = (user["userGroup"] if user else None) or "00"

            rows = await conn.fetch(
                'SELECT * FROM "UserDatabaseConnection" '
                'WHERE "userId" = $1 OR ("isShared" = true AND "dbConnectionGroup" = $2) '
                'ORDER BY "createdAt" ASC',
                uid, user_group,
            )
            user_ids = sorted({r["userId"] for r in rows})
            if user_ids:
                user_rows = await conn.fetch(
                    'SELECT id, name, email FROM "User" WHERE id = ANY($1::text[])',
                    user_ids,
                )
            else:
                user_rows = []

        user_map = {u["id"]: {"name": u["name"], "email": u["email"]}
                    for u in user_rows}
        return {"connections": [_get_body(r, user_map, uid) for r in rows]}
    except Exception:
        return await _error(500, E_INTERNAL_ERROR, language)


@router.post("")
async def post_database_connections(
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

        # req.json() throws on empty/malformed body -> 500.
        try:
            body = json.loads(await req.body() or b"")
        except Exception:
            return await _error(500, E_INTERNAL_ERROR, language)
        if body is None:
            # Destructuring null throws in the frontend -> 500.
            return await _error(500, E_INTERNAL_ERROR, language)
        if not isinstance(body, dict):
            # Destructuring an array/string/number yields all-undefined.
            body = {}

        name = body.get("name")
        type_ = body.get("type")
        host = body.get("host")
        port = body.get("port")
        database = body.get("database")
        username = body.get("username")
        password = body.get("password")
        shared = body.get("shared")
        db_connection_group = body.get("dbConnectionGroup")
        can_create_database = body.get("canCreateDatabase")
        can_create_tables = body.get("canCreateTables")
        auto_create_tables = body.get("auto_create_tables")
        auto_create_views = body.get("auto_create_views")

        if (not _js_truthy(name) or not _js_truthy(type_) or not _js_truthy(host)
                or not _js_truthy(port) or not _js_truthy(database)
                or not _js_truthy(username) or not _js_truthy(password)):
            return await _error(400, E_MISSING_FIELDS, language)

        # Duplicate check: findFirst({userId, name}) — the name quirks mirror
        # item 12's Prisma findFirst behaviour.
        if isinstance(name, dict) and len(name) == 0:
            # Empty-object String filter is a NO-OP -> matches the user's first
            # row (any name) -> 400 name_exists; with zero rows it falls through
            # to create, where the non-string name throws -> 500.
            async with _db_pool.acquire() as conn:
                existing = await conn.fetchrow(
                    'SELECT "connectionId" FROM "UserDatabaseConnection" '
                    'WHERE "userId" = $1 LIMIT 1',
                    uid,
                )
            if existing is not None:
                return await _error(400, E_CONNECTION_NAME_EXISTS, language)
            return await _error(500, E_INTERNAL_ERROR, language)
        if not isinstance(name, str):
            # Prisma String where-name rejects truthy non-strings -> 500.
            return await _error(500, E_INTERNAL_ERROR, language)

        async with _db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                'SELECT "connectionId" FROM "UserDatabaseConnection" '
                'WHERE "userId" = $1 AND name = $2',
                uid, name,
            )
        if existing is not None:
            return await _error(400, E_CONNECTION_NAME_EXISTS, language)

        # String columns: truthy non-string -> Prisma throws -> 500.
        if (not isinstance(type_, str) or not isinstance(host, str)
                or not isinstance(database, str) or not isinstance(username, str)):
            return await _error(500, E_INTERNAL_ERROR, language)
        if not isinstance(password, str):
            # encrypt(password) throws on non-string -> 500.
            return await _error(500, E_INTERNAL_ERROR, language)
        encrypted = encrypt_field(password)
        await require_db_feature(_db_pool, type_, language)

        # port: Int column — clean validation, no JS Number() coercion. Any
        # non-integer (float/string/bool/array/null) is a client error -> 400;
        # an Int field must never silently truncate a float (the Prisma
        # float->int bug this port refuses to mirror).
        if isinstance(port, bool) or not isinstance(port, int):
            return await _error(400, E_INVALID_PORT, language)
        port_int = port

        # dbConnectionGroup || "00" — truthy non-string -> 500.
        group_value = db_connection_group if _js_truthy(db_connection_group) else "00"
        if not isinstance(group_value, str):
            return await _error(500, E_INTERNAL_ERROR, language)

        # isShared = shared || false — truthy non-bool -> 500.
        shared_value = shared if _js_truthy(shared) else False
        if not isinstance(shared_value, bool):
            return await _error(500, E_INTERNAL_ERROR, language)

        can_db = can_create_database is True
        can_tbl = can_create_tables is True

        async with _db_pool.acquire() as conn:
            connection = await conn.fetchrow(
                'INSERT INTO "UserDatabaseConnection" '
                '("userId", name, type, host, port, database, username, password, '
                '"dbConnectionGroup", "isShared", "canCreateDatabase", "canCreateTables", "updatedAt") '
                'VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, NOW()) '
                'RETURNING *',
                uid, name, type_, host, port_int, database, username, encrypted,
                group_value, shared_value, can_db, can_tbl,
            )

        datasets_created = 0
        if _js_truthy(auto_create_tables) or _js_truthy(auto_create_views):
            # Forward the user's own bearer token so auto-create authenticates
            # (its endpoint requires HTTPBearer). On any other non-ok, delete
            # the row and 502 the detail.
            backend_url = os.getenv("NEXT_PUBLIC_BACKEND_URL", "http://127.0.0.1:8000")
            async with httpx.AsyncClient(timeout=httpx.Timeout(30.0)) as client:
                auto_res = await client.post(
                    f"{backend_url}/api/datasets/auto-create",
                    json={
                        "connectionId": connection["connectionId"],
                        "autoCreateTables": auto_create_tables,
                        "autoCreateViews": auto_create_views,
                    },
                    headers={"Authorization": f"Bearer {credentials.credentials}"},
                )

            if auto_res.status_code in range(200, 300):
                try:
                    data = auto_res.json()
                except Exception:
                    data = {}
                datasets_created = data.get("datasetsCreated") or 0
            else:
                detail = await t(_db_pool, language, USER["user.auto_create_default_detail"])
                try:
                    err = auto_res.json()
                except Exception:
                    err = {}
                if err.get("detail"):
                    detail = err["detail"]
                elif err.get("message"):
                    detail = err["message"]
                async with _db_pool.acquire() as conn:
                    await conn.execute(
                        'DELETE FROM "UserDatabaseConnection" WHERE "connectionId" = $1',
                        connection["connectionId"],
                    )
                return _raw_error(502, E_AUTO_CREATE_FAILED, detail)

        return {
            "datasetsCreated": datasets_created,
            "success": True,
            "connection": _conn_body(connection),
        }
    except HTTPException:
        raise
    except Exception as e:
        # The POST catch is dynamic: message = error.message (raw passthrough),
        # status 502 when it mentions auto-creation/discover, else 500.
        message = str(e)
        if not message:
            message = await t(_db_pool, language, USER["api.user.internal_error"])
        status = 502 if ("Dataset auto-creation failed" in message
                         or "discover" in message) else 500
        return _raw_error(status, E_INTERNAL_ERROR, message)


@router.patch("")
async def patch_database_connections(
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

        try:
            body = json.loads(await req.body() or b"")
        except Exception:
            return await _error(500, E_INTERNAL_ERROR, language)
        if body is None:
            return await _error(500, E_INTERNAL_ERROR, language)
        if not isinstance(body, dict):
            body = {}

        raw_id = body.get("id")
        if not _js_truthy(raw_id):
            return await _error(400, E_MISSING_FIELDS, language)

        # Strict id validation (no JS parseInt/String coercion — item 11).
        if not isinstance(raw_id, str) or not raw_id.isdigit():
            return await _error(400, E_INVALID_CONNECTION_ID, language)
        parsed_id = int(raw_id)

        # An administrator may also act on a connection shared to their group —
        # the rows GET returns with isOwn=false. Everyone else is confined to
        # their own rows, and a miss is the same 404 either way, so a row's
        # existence is never disclosed to an unauthorised caller.
        admin_group = None
        if await _is_admin(uid):
            admin_group = (await _user_group(uid)) or "00"

        async with _db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                'SELECT * FROM "UserDatabaseConnection" '
                'WHERE "connectionId" = $1 AND "userId" = $2',
                parsed_id, uid,
            )
            if existing is None and admin_group is not None:
                existing = await conn.fetchrow(
                    'SELECT * FROM "UserDatabaseConnection" '
                    'WHERE "connectionId" = $1 AND "isShared" = true '
                    'AND "dbConnectionGroup" = $2',
                    parsed_id, admin_group,
                )
        if existing is None:
            return await _error(404, E_CONNECTION_NOT_FOUND, language)

        update = {}
        if "name" in body:
            if not isinstance(body["name"], str):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["name"] = body["name"]
        if "type" in body:
            if not isinstance(body["type"], str):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["type"] = body["type"]
            await require_db_feature(_db_pool, body["type"], language)
        if "host" in body:
            if not isinstance(body["host"], str):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["host"] = body["host"]
        if "port" in body:
            port_value = body["port"]
            if isinstance(port_value, bool) or not isinstance(port_value, int):
                return await _error(400, E_INVALID_PORT, language)
            update["port"] = port_value
        if "database" in body:
            if not isinstance(body["database"], str):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["database"] = body["database"]
        if "username" in body:
            if not isinstance(body["username"], str):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["username"] = body["username"]
        if "password" in body:
            if not isinstance(body["password"], str):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["password"] = encrypt_field(body["password"])
        if "dbConnectionGroup" in body:
            if not isinstance(body["dbConnectionGroup"], str):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["dbConnectionGroup"] = body["dbConnectionGroup"]
        if "shared" in body:
            if not isinstance(body["shared"], bool):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["isShared"] = body["shared"]
        if "canCreateDatabase" in body:
            if not isinstance(body["canCreateDatabase"], bool):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["canCreateDatabase"] = body["canCreateDatabase"]
        if "canCreateTables" in body:
            if not isinstance(body["canCreateTables"], bool):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["canCreateTables"] = body["canCreateTables"]

        async with _db_pool.acquire() as conn:
            if update:
                sets = ", ".join(f'"{c}" = ${i + 1}' for i, c in enumerate(update))
                values = list(update.values())
                updated = await conn.fetchrow(
                    f'UPDATE "UserDatabaseConnection" SET {sets}, "updatedAt" = NOW() '
                    f'WHERE "connectionId" = ${len(values) + 1} RETURNING *',
                    *values, parsed_id,
                )
            else:
                # Prisma data {} — no-op update returns the row, 200.
                updated = await conn.fetchrow(
                    'SELECT * FROM "UserDatabaseConnection" WHERE "connectionId" = $1',
                    parsed_id,
                )
        if updated is None:
            # Row vanished between existence check and UPDATE → 404.
            return await _error(404, E_CONNECTION_NOT_FOUND, language)

        return {"success": True, "connection": _conn_body(updated)}
    except HTTPException:
        raise
    except Exception:
        return await _error(500, E_INTERNAL_ERROR, language)


@router.delete("")
async def delete_database_connections(
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

        raw_id = req.query_params.get("id")
        if not raw_id:
            return await _error(400, E_MISSING_FIELDS, language)

        # Strict id validation (no JS parseInt coercion — item 11).
        if not raw_id.isdigit():
            return await _error(400, E_INVALID_CONNECTION_ID, language)
        parsed_id = int(raw_id)

        # An administrator may also delete a connection shared to their group —
        # the rows GET returns with isOwn=false. Everyone else is confined to
        # their own rows, and a miss is the same 404 either way, so a row's
        # existence is never disclosed to an unauthorised caller.
        admin_group = None
        if await _is_admin(uid):
            admin_group = (await _user_group(uid)) or "00"

        async with _db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                'SELECT "connectionId" FROM "UserDatabaseConnection" '
                'WHERE "connectionId" = $1 AND "userId" = $2',
                parsed_id, uid,
            )
            if existing is None and admin_group is not None:
                existing = await conn.fetchrow(
                    'SELECT "connectionId" FROM "UserDatabaseConnection" '
                    'WHERE "connectionId" = $1 AND "isShared" = true '
                    'AND "dbConnectionGroup" = $2',
                    parsed_id, admin_group,
                )
            if existing is None:
                return await _error(404, E_CONNECTION_NOT_FOUND, language)

            await conn.execute(
                'DELETE FROM "UserDatabaseConnection" WHERE "connectionId" = $1',
                parsed_id,
            )

        return {"success": True}
    except Exception:
        return await _error(500, E_INTERNAL_ERROR, language)


# ============================================================
# ITEM 19 — GET /available (connections usable in the dataset/chat UI)
# ============================================================
#
# Frontend source:
#   frontend/app/api/user/database-connections/available/route.ts
#
# Contract parity:
#   - GET only. Lists a user's OWN rows plus rows shared to their group
#     (isShared=true AND dbConnectionGroup = the user's group). No example-user
#     block. Ordered by createdAt ASC.
#   - DIVERGENCE from the item-18 GET: a missing user row (ghost session)
#     returns 404 {"error": "User not found"} here — the item-18 GET falls
#     through to userGroup "00" and returns 200. Mirrored exactly.
#   - Response is the item-18 GET curated shape ({connections: [...], userGroup});
#     the connection body is _get_body (id string mirror, decrypted password,
#     group "00" default, userName + isOwn) — byte-identical to the item-18 GET
#     connection shape. Adds the top-level userGroup the parent GET omits.
#
# Error shape: bare string {"error": "<string>"} (no code/message) — the same
# divergence as items 13/14/15. Routed through t() (option b).


@router.post("/{connection_id}/probe")
async def probe_database_connection(
    connection_id: int,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Re-probe one connection now, and return the result that was recorded.

    Its own route because the swept state is not on a clock the user controls: the
    probe runs when a virtual-chat session lists sources, so a connection page can
    show an answer from days ago with no way to refresh it. `Check now` needs
    something to call.

    `force=True`, deliberately: the point of pressing the button is to ask again
    now, not to be handed the cached answer from inside the TTL.

    The write goes through `probe_one`, the same function the chat path uses, so
    the state the panel then renders and the state the concierge reads are one
    answer recorded once — not two outcomes of two probes.
    """
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if _db_pool is None:
            return await _error(500, E_INTERNAL_ERROR, language)

        # Ownership, asked the same way the rest of this module asks it: the row
        # must be the caller's, or shared to their group and they an administrator.
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT "userId", "isShared", "dbConnectionGroup" FROM "UserDatabaseConnection" '
                'WHERE "connectionId" = $1', connection_id,
            )
        if row is None:
            return await _error(404, E_CONNECTION_NOT_FOUND, language)
        if row["userId"] != uid:
            admin_group = (await _user_group(uid)) or "00"
            if not (row["isShared"] and row["dbConnectionGroup"] == admin_group and await _is_admin(uid)):
                # The same answer a missing row gives, so a caller who may not
                # read this row cannot learn that it exists.
                return await _error(404, E_CONNECTION_NOT_FOUND, language)

        from src.routers.datasets.connection_probe import probe_one

        result = await probe_one(_db_pool, uid, language, connection_id, force=True)
        if result is None:
            return await _error(404, E_CONNECTION_NOT_FOUND, language)

        # `ProbeResult` carries the state and why, not the timestamps — the probe
        # records those to the row. Read them back, so the answer this returns is
        # the row's own answer rather than a second construction of it.
        async with _db_pool.acquire() as conn:
            stored = await conn.fetchrow(
                'SELECT "probedAt", "probeSuccessAt" FROM "UserDatabaseConnection" '
                'WHERE "connectionId" = $1', connection_id,
            )
        return JSONResponse({
            "connectionId": connection_id,
            "probeState": result.state,
            "probeDetail": result.detail,
            "probedAt": iso_utc(stored["probedAt"]) if stored else None,
            "probeSuccessAt": iso_utc(stored["probeSuccessAt"]) if stored else None,
        })
    except HTTPException:
        raise
    except Exception:
        return await _error(500, E_INTERNAL_ERROR, language)


@router.get("/available")
async def get_available_database_connections(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(401, "api.auth.unauthorized", language)

        async with _db_pool.acquire() as conn:
            user = await conn.fetchrow(
                'SELECT "userGroup" FROM "User" WHERE id = $1', uid
            )
        user_group = (user["userGroup"] if user else None) or "00"

        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT * FROM "UserDatabaseConnection" '
                'WHERE "userId" = $1 OR ("isShared" = true AND "dbConnectionGroup" = $2) '
                'ORDER BY "createdAt" ASC',
                uid, user_group,
            )
            user_ids = sorted({r["userId"] for r in rows})
            if user_ids:
                user_rows = await conn.fetch(
                    'SELECT id, name, email FROM "User" WHERE id = ANY($1::text[])',
                    user_ids,
                )
            else:
                user_rows = []

        user_map = {u["id"]: {"name": u["name"], "email": u["email"]}
                    for u in user_rows}

        return {
            "connections": [_get_body(r, user_map, uid) for r in rows],
            "userGroup": user_group,
        }
    except Exception:
        return await _t_error(500, "api.user.internal_error", language)
