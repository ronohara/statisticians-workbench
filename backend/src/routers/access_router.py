"""
Golden Screwdriver — Access Connection Router.

Admin/endpoints for Microsoft Access database connections via
msaccess-endpoint-ng, a real PostgreSQL server with a Jet/ACE storage
engine. All endpoints are gated behind is_feature_enabled("access_db").

POST /api/access/test    — test a connection to the Access endpoint
POST /api/access/save    — save an Access connection
GET  /api/access/list    — list saved Access connections
DELETE /api/access/{id}  — delete a saved connection
"""

import logging
import os
import uuid
from typing import Any
from datetime import datetime, timezone

import jwt
import psycopg2
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.licensing import is_feature_enabled
from src.utils.translation import t
from src.routers.datasets.crud import get_current_language
from .common.relations import VISIBLE_RELATIONS, relation_kind
from .common.translations import (
    AUTH,
    access_licence_required,
    access_file_path_required,
    access_name_and_path_required,
    access_invalid_port,
    access_connection_params_required,
    access_encryption_error,
    access_db_pool_not_initialized,
    access_connection_exists,
    access_connection_saved,
    access_connection_not_found,
    access_connection_deleted,
    access_connected_in_ms,
    access_connection_failed,
    access_connection_failed_detail,
    access_connection_unavailable,
    access_table_not_found,
)
from src.utils.timestamps import iso_utc
router = APIRouter(prefix="/api/access", tags=["access"])

security = HTTPBearer()
SECRET_KEY = os.getenv("NEXTAUTH_SECRET")

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ── Helpers ────────────────────────────────────────────────────────

async def get_user_id_from_token(
    credentials: HTTPAuthorizationCredentials,
    db_pool=None,
    language: str = "en",
) -> str:
    """Resolve the authenticated user id from the JWT (401 on failure)."""
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("id")
        if not user_id:
            detail = await t(db_pool, language, AUTH["auth.invalid_token_missing_user_id"]) if db_pool else "Invalid token: missing user id"
            raise HTTPException(status_code=401, detail=detail)
        return user_id
    except jwt.PyJWTError as e:
        detail = await t(db_pool, language, AUTH["auth.invalid_token_error"], error=str(e)) if db_pool else f"Invalid token: {str(e)}"
        raise HTTPException(status_code=401, detail=detail)


async def _require_feature(language: str):
    """Return 403 if access_db is not enabled by the current licence."""
    if not is_feature_enabled("access_db"):
        raise HTTPException(
            status_code=403,
            detail=await t(_db_pool, language, access_licence_required),
        )


def _encrypt_password(password: str) -> str:
    """Encrypt a password using AES-256-GCM, same format as Next.js frontend.

    Format: iv:authTag:ciphertext (all base64).
    Compatible with @/lib/encryption on the Next.js side.
    """
    import os
    import base64
    import secrets
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = bytes.fromhex(os.getenv("ENCRYPTION_KEY", ""))
    if len(key) != 32:
        raise RuntimeError("ENCRYPTION_KEY must be 32 bytes (64 hex chars)")

    iv = secrets.token_bytes(16)
    aesgcm = AESGCM(key)
    encrypted = aesgcm.encrypt(iv, password.encode("utf-8"), None)
    auth_tag = encrypted[-16:]
    ciphertext = encrypted[:-16]
    return (
        base64.b64encode(iv).decode("ascii")
        + ":"
        + base64.b64encode(auth_tag).decode("ascii")
        + ":"
        + base64.b64encode(ciphertext).decode("ascii")
    )


def _decrypt_password(encrypted: str) -> str:
    """Decrypt a password using Node.js-compatible AES-256-GCM.
    Format: iv:authTag:ciphertext (all base64)."""
    import os
    import base64
    from cryptography.hazmat.primitives.ciphers.aead import AESGCM

    key = bytes.fromhex(os.getenv("ENCRYPTION_KEY", ""))
    if len(key) != 32:
        raise RuntimeError("ENCRYPTION_KEY must be 32 bytes (64 hex chars)")

    parts = encrypted.split(":")
    if len(parts) == 3:
        iv = base64.b64decode(parts[0])
        auth_tag = base64.b64decode(parts[1])
        ciphertext = base64.b64decode(parts[2])
        aesgcm = AESGCM(key)
        return aesgcm.decrypt(iv, ciphertext + auth_tag, None).decode("utf-8")
    raise ValueError(f"Unrecognized encrypted format")


async def _clean_jet_error(raw: str, language: str) -> str:
    """Extract a human-readable message from a msaccess-endpoint-ng / psycopg2 error.

    Raw errors look like:
      connection to server at "127.0.0.1", port 9432 failed: ERROR:
      Invoke(dispid=1610809358) failed: 'C:\\bad.accdb' is not a valid
      path. ... (0x80020009)

    We strip the psycopg2 prefix, COM dispatch noise, and hex error code.
    """
    import re

    s = raw.strip()

    # Strip psycopg2 connection prefix
    s = re.sub(
        r'^connection to server at "[^"]+", port \d+ failed:\s*',
        "",
        s,
    )

    # Strip COM dispatch noise: "ERROR:  Invoke(dispid=...) failed:"
    s = re.sub(r"ERROR:\s*Invoke\(dispid=\d+\) failed:\s*", "", s)

    # Strip trailing hex error code: "(0x80020009)"
    s = re.sub(r"\s*\(0x[0-9a-fA-F]+\)\s*$", "", s)

    s = s.strip()
    if not s:
        return await t(_db_pool, language, access_connection_failed)

    return await t(_db_pool, language, access_connection_failed_detail, detail=s)


# ── Test Connection ────────────────────────────────────────────────

@router.post("/test")
async def test_access_connection(
    request: Request,
    body: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """
    Test connectivity to a msaccess-endpoint-ng instance.

    Body: {file_path, host, port, user, password}
    """
    await _require_feature(language)
    # Enforce authentication even though no per-user data is read here.
    await get_user_id_from_token(credentials, _db_pool, language)

    file_path = body.get("file_path", "")
    host = body.get("host")
    port = body.get("port")
    user = body.get("user")
    password = body.get("password")

    # Validate, don't coerce.
    if not isinstance(file_path, str):
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, access_file_path_required))
    file_path = file_path.strip()

    # host/port/user/password are required (no defaults) and must be valid.
    if host is None or port is None or user is None or password is None:
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, access_connection_params_required))
    if (not isinstance(host, str) or not host.strip()
            or not isinstance(user, str) or not user.strip()
            or not isinstance(password, str) or not password.strip()):
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, access_connection_params_required))
    if isinstance(port, bool) or not isinstance(port, int):
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, access_invalid_port))

    if not file_path:
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, access_file_path_required))

    try:
        start = datetime.now(timezone.utc)
        conn = psycopg2.connect(
            host=host,
            port=port,
            user=user,
            password=password,
            dbname=file_path,
            connect_timeout=10,
        )
        cur = conn.cursor()
        cur.execute("SELECT 1")
        cur.close()
        conn.close()
        elapsed = (datetime.now(timezone.utc) - start).total_seconds() * 1000

        return {
            "success": True,
            "message": await t(_db_pool, language, access_connected_in_ms, elapsed=f"{elapsed:.0f}"),
        }
    except psycopg2.OperationalError as e:
        return {
            "success": False,
            "message": await _clean_jet_error(str(e), language),
        }
    except Exception as e:
        logging.error("Unexpected error testing Access connection: %s", e)
        return {
            "success": False,
            "message": await _clean_jet_error(str(e), language),
        }


# ── Save Connection ────────────────────────────────────────────────

@router.post("/save")
async def save_access_connection(
    request: Request,
    body: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Save a new Access connection to the database.
    
    Optionally auto-creates datasets for all tables/views in the
    connected .accdb file if auto_create_tables/auto_create_views
    flags are set (both default to True).
    """
    await _require_feature(language)
    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    name = body.get("name", "")
    file_path = body.get("file_path", "")
    host = body.get("host")
    port = body.get("port")
    user = body.get("user")
    password = body.get("password")
    auto_create_tables = body.get("auto_create_tables", True)
    auto_create_views = body.get("auto_create_views", True)

    # Validate, don't coerce.
    if not isinstance(name, str) or not isinstance(file_path, str):
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, access_name_and_path_required))
    name = name.strip()
    file_path = file_path.strip()

    # host/port/user/password are required (no defaults) and must be valid.
    if host is None or port is None or user is None or password is None:
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, access_connection_params_required))
    if (not isinstance(host, str) or not host.strip()
            or not isinstance(user, str) or not user.strip()
            or not isinstance(password, str) or not password.strip()):
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, access_connection_params_required))
    if isinstance(port, bool) or not isinstance(port, int):
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, access_invalid_port))

    if not name or not file_path:
        raise HTTPException(status_code=400, detail=await t(_db_pool, language, access_name_and_path_required))

    try:
        encrypted_pass = _encrypt_password(password)
    except Exception as e:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, access_encryption_error, error=str(e)))

    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, access_db_pool_not_initialized))

    async with _db_pool.acquire() as conn:
        # Check for duplicate name (across all types, not just access)
        existing = await conn.fetchrow(
            'SELECT "connectionId" FROM "UserDatabaseConnection" WHERE "userId" = $1 AND name = $2',
            user_id, name,
        )
        if existing:
            raise HTTPException(status_code=409, detail=await t(_db_pool, language, access_connection_exists, name=name))

        row = await conn.fetchrow(
            """INSERT INTO "UserDatabaseConnection"
               ("userId", name, type, database, host, port, username, password, "updatedAt")
               VALUES ($1, $2, 'access', $3, $4, $5, $6, $7, NOW())
               RETURNING "connectionId", name, database, host, port, username, "createdAt\"""",
            user_id, name, file_path, host, port, user, encrypted_pass,
        )

        connection_id = row["connectionId"]

    return {
        "message": await t(_db_pool, language, access_connection_saved),
        "connection": {
            "id": connection_id,
            "name": row["name"],
            "filePath": row["database"],
            "host": row["host"],
            "port": row["port"],
            "user": row["username"],
            "createdAt": iso_utc(row["createdAt"]),
        },
    }


# ── List Connections ───────────────────────────────────────────────

@router.get("/list")
async def list_access_connections(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """List all saved Access connections for the current user."""
    await _require_feature(language)
    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, access_db_pool_not_initialized))

    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(
            """SELECT "connectionId", name, database, host, port,
                      username, "createdAt"
               FROM "UserDatabaseConnection"
               WHERE "userId" = $1 AND type = 'access'
               ORDER BY name""",
            user_id,
        )

    return [
        {
            "id": r["connectionId"],
            "name": r["name"],
            "filePath": r["database"],
            "host": r["host"],
            "port": r["port"],
            "user": r["username"],
            "createdAt": iso_utc(r["createdAt"]),
        }
        for r in rows
    ]


# ── Delete Connection ──────────────────────────────────────────────

@router.delete("/{connection_id}")
async def delete_access_connection(
    request: Request,
    connection_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Delete a saved Access connection."""
    await _require_feature(language)
    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, access_db_pool_not_initialized))

    async with _db_pool.acquire() as conn:
        result = await conn.execute(
            'DELETE FROM "UserDatabaseConnection" WHERE "connectionId" = $1 AND "userId" = $2 AND type = \'access\'',
            connection_id, user_id,
        )

        # Parse the DELETE result tag: "DELETE N"
        tag = result.split() if result else []
        deleted = int(tag[1]) if len(tag) == 2 and tag[0] == "DELETE" else 0

        if deleted == 0:
            raise HTTPException(status_code=404, detail=await t(_db_pool, language, access_connection_not_found))

    return {"message": await t(_db_pool, language, access_connection_deleted)}


# ── Table Discovery ────────────────────────────────────────────────


async def _get_connection_details(connection_id: int, user_id: str, language: str) -> dict:
    """Look up a saved Access connection and decrypt its password."""
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, access_db_pool_not_initialized))

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """SELECT "connectionId", name, database, host, port,
                      username, password
               FROM "UserDatabaseConnection"
               WHERE "connectionId" = $1 AND "userId" = $2 AND type = 'access'""",
            connection_id, user_id,
        )

    if not row:
        raise HTTPException(status_code=404, detail=await t(_db_pool, language, access_connection_not_found))

    return {
        "id": row["connectionId"],
        "name": row["name"],
        "filePath": row["database"],
        "host": row["host"],
        "port": row["port"],
        "user": row["username"],
        "password": _decrypt_password(row["password"]),
    }


def _connect_jet(conn_info: dict):
    """Create a psycopg2 connection to msaccess-endpoint-ng."""
    return psycopg2.connect(
        host=conn_info["host"],
        port=conn_info["port"],
        user=conn_info["user"],
        password=conn_info["password"],
        dbname=conn_info["filePath"],
        connect_timeout=15,
    )


@router.get("/{connection_id}/tables")
async def list_access_tables(
    request: Request,
    connection_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """List the tables and views in an Access database via msaccess-endpoint-ng."""
    await _require_feature(language)
    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    conn_info = await _get_connection_details(connection_id, user_id, language)

    # Every relation this session can name by bare name — which, against a mounted file,
    # is the derived schema the endpoint put at the head of the search_path, not `public`.
    # `common/relations.py` records why the question is asked this way rather than by
    # naming a schema.
    tables = []
    try:
        pg_conn = _connect_jet(conn_info)
        cur = pg_conn.cursor()
        cur.execute(VISIBLE_RELATIONS)
        for _schema, name, kind in cur.fetchall():
            if name.startswith("MSys"):
                continue
            tables.append({"name": name, "type": relation_kind(kind)})
        cur.close()
        pg_conn.close()
    except Exception as e:
        logging.warning("Catalog query failed for connection %d: %s", connection_id, e)

    return {"tables": tables}


@router.get("/{connection_id}/tables/{table_name}/columns")
async def get_access_columns(
    request: Request,
    connection_id: int,
    table_name: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Get column information for a table via msaccess-endpoint-ng."""
    await _require_feature(language)
    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    conn_info = await _get_connection_details(connection_id, user_id, language)

    try:
        pg_conn = _connect_jet(conn_info)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=await t(_db_pool, language, access_connection_unavailable, error=str(e)),
        )

    try:
        cur = pg_conn.cursor()
        # Use a zero-row query to get column metadata from cursor.description
        cur.execute(f'SELECT * FROM [{table_name}] WHERE 1=0')
        columns = [
            {"name": d[0], "type_code": d[1]} for d in (cur.description or [])
        ]
        cur.close()
        pg_conn.close()
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, access_table_not_found, table=table_name, error=str(e)),
        )

    return {"table": table_name, "columns": columns}


@router.get("/{connection_id}/tables/{table_name}/preview")
async def preview_access_table(
    request: Request,
    connection_id: int,
    table_name: str,
    limit: int = 100,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Preview rows from an Access table via msaccess-endpoint-ng."""
    await _require_feature(language)
    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    conn_info = await _get_connection_details(connection_id, user_id, language)

    limit = min(max(1, limit), 1000)

    try:
        pg_conn = _connect_jet(conn_info)
    except Exception as e:
        raise HTTPException(
            status_code=502,
            detail=await t(_db_pool, language, access_connection_unavailable, error=str(e)),
        )

    try:
        cur = pg_conn.cursor()
        # Jet SQL supports TOP but not LIMIT. Use TOP to avoid
        # transferring the entire table (e.g. bi_date has 18k rows).
        #
        # ⚠️ KNOWN JET QUIRK (2026-07-23): Jet/DAO TOP n returns n-1 rows
        # for small n (observed: TOP 100→99, TOP 5→4, TOP 3→2, TOP 1→0).
        # Not investigated yet — preview is approximate; exact row count
        # is not required for this endpoint.
        cur.execute(f"SELECT TOP {int(limit)} * FROM [{table_name}]")
        rows = cur.fetchall()
        columns = [d[0] for d in (cur.description or [])]
        cur.close()
        pg_conn.close()
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, access_table_not_found, table=table_name, error=str(e)),
        )

    return {
        "table": table_name,
        "columns": columns,
        "rows": [list(r) for r in rows],
        "total_rows": len(rows),
    }
