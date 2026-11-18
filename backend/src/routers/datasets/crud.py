"""
CRUD operations for datasets.
Part of the 0.0.10 "Statistical Foundation" milestone.
"""

import os
import jwt
import asyncio
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional, List

from src.utils.translation import t
from .translations import DATASETS
from src.postgres_data_manager import drop_table, user_schema_name
from src.routers.common.feature_gate import require_db_feature
from src.routers.common.relations import VISIBLE_RELATIONS
from src.utils.timestamps import iso_utc

router = APIRouter()
security = HTTPBearer()

_db_pool = None
SECRET_KEY = os.getenv("NEXTAUTH_SECRET")

# The dataset source types that hold data the user brought in — an uploaded file
# or an imported notebook — as opposed to a table registered from a connection or
# a virtual join built from one. The upload quota counts these (datasets/upload.py);
# the same pair is the idiom the local-PostgreSQL readers already use to recognise
# a dataset whose rows live as a table of our own.
UPLOAD_SOURCE_TYPES = ("upload", "notebook")

def set_db_pool(pool):
    global _db_pool
    _db_pool = pool

async def get_user_id_from_token(credentials: HTTPAuthorizationCredentials, db_pool=None, language: str = "en") -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("id")
        if not user_id:
            detail = await t(db_pool, language, DATASETS["auth.invalid_token_missing_user_id"]) if db_pool else "Invalid token: missing user id"
            raise HTTPException(status_code=401, detail=detail)
        return user_id
    except jwt.PyJWTError as e:
        detail = await t(db_pool, language, DATASETS["auth.invalid_token_error"], error=str(e)) if db_pool else f"Invalid token: {str(e)}"
        raise HTTPException(status_code=401, detail=detail)

async def get_current_language(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Dependency to get the current user's language."""
    from src.utils.language import get_user_language
    return await get_user_language(request, credentials, _db_pool)

async def get_connection_row(connection_id: int, user_id: str, language: str = "en"):
    """Fetch a connection's raw row with ownership check and feature gate.

    The single consolidated fetch for connection credentials. Returns the row
    (name, type, host, port, database, username, password, canCreateDatabase,
    canCreateTables) or None when the connection is not found or not owned.

    Raises 403 when the connection type's licence feature is disabled, and 500
    when the pool is not initialised. Does NOT decrypt the password — each
    caller decrypts with its own raise-vs-keep-original behaviour.
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"])
        )

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT name, type, host, port, database, username, password,
                   "canCreateDatabase", "canCreateTables"
            FROM "UserDatabaseConnection"
            WHERE "connectionId" = $1 AND ("userId" = $2 OR ("isShared" = true AND "dbConnectionGroup" IN (SELECT "userGroup" FROM "User" WHERE id = $2)))
            """,
            connection_id, user_id
        )

    if row is None:
        return None

    await require_db_feature(_db_pool, row["type"], language)

    return dict(row)


async def can_edit_dataset(db_pool, dataset_id: str, user_id: str) -> bool:
    """May this caller change this dataset?

    Its owner — or an administrator, when the dataset is shared to the group that
    administrator belongs to. This is the rule the AI and database connections have
    enforced since 2026-09-19 (routers/user/ai_connections.py), stated once here so
    that every dataset write path asks one question instead of composing its own
    predicate. Sharing is not part of editing: this decides content, never whether a
    row is shared, and it deliberately says nothing about the group field changing.

    The admin flag and the caller's group are read in the same query rather than
    through admin.users._is_admin/_user_group: admin.users imports this module
    (get_current_language), so importing it back would close a cycle — and a
    function-body import to dodge that is against the porting rules (imports stay
    static, at module top). The rule is identical either way.

    False covers both "no such row" and "not yours to change", so a caller who may
    not touch a dataset cannot learn that it exists.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT ("userId" = $2) AS is_owner,
                   "isShared",
                   "datasetGroup",
                   EXISTS (SELECT 1 FROM "User" WHERE id = $2 AND "isAdmin" = true) AS caller_is_admin,
                   COALESCE((SELECT "userGroup" FROM "User" WHERE id = $2), '00') AS caller_group
            FROM "UserDataset"
            WHERE id = $1
            """,
            dataset_id, user_id,
        )

    if row is None:
        return False
    if row["is_owner"]:
        return True

    return bool(
        row["isShared"]
        and row["caller_is_admin"]
        and row["datasetGroup"] == row["caller_group"]
    )


# The four timestamp columns a UserDataset row carries, and the one form they are
# rendered in. Kept as one list beside one function so a fifth timestamp column added
# later has an obvious home, rather than being emitted raw by whichever route happened
# to serialise it first — which is how this response came to return FastAPI's default
# `+00:00` with six digits while every other route returned `Z` with three.
_DATASET_TIMESTAMPS = ("createdAt", "updatedAt", "materializedAt")


def _dataset_row(row) -> dict:
    """A UserDataset row as the API sends it, with every timestamp in the wire form."""
    out = dict(row)
    for key in _DATASET_TIMESTAMPS:
        if key in out:
            out[key] = iso_utc(out[key])
    return out


async def list_user_datasets(db_pool, user_id: str) -> list:
    """Plain helper: the datasets a user can see — their own plus those shared
    to their group, newest first. Shared by the GET /api/datasets endpoint and
    the AI recipe concierge's list_datasets tool (the "peer of the manual
    editor" rule — one query, two callers). Returns the raw rows as dicts."""
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, name, description, "sourceType", "storageType", "sourceConnectionId",
                   "databaseName", "tableName", "originalFileName", "fileSize", "filePath",
                   "sourceOrigin", "sourceDatasetId",
                   "datasetGroup", "userId", "isShared", status, "createdAt", "updatedAt",
                   -- The list is where a failed materialisation has to be visible:
                   -- an error shown only at save time is invisible by the next
                   -- morning, and the dataset then looks like an ordinary one with
                   -- no table.
                   "materialized", "materializedAt", "materializeError"
            FROM "UserDataset"
            WHERE "userId" = $1 OR ("isShared" = true AND "datasetGroup" IN (SELECT "userGroup" FROM "User" WHERE id = $1))
            ORDER BY "createdAt" DESC
            """,
            user_id,
        )
    return [_dataset_row(r) for r in rows]


@router.get("/")
async def list_datasets(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    if _db_pool is None:
        raise HTTPException(
            status_code=500, 
            detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    rows = await list_user_datasets(_db_pool, user_id)

    result = []
    for ds in rows:
        if ds["userId"] != user_id:
            async with _db_pool.acquire() as conn:
                user_row = await conn.fetchrow(
                    'SELECT name FROM "User" WHERE id = $1',
                    ds["userId"]
                )
                ds["userName"] = user_row["name"] if user_row else await t(_db_pool, language, DATASETS["common.unknown"])
                ds["isOwn"] = False
        else:
            ds["userName"] = None
            ds["isOwn"] = True
        result.append(ds)

    return {"datasets": result}

@router.get("/{dataset_id}")
async def get_dataset(
    dataset_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Get a single dataset by ID with preparation rules."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500, 
            detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, description, "sourceType", "storageType", "sourceConnectionId",
                   "databaseName", "tableName", "originalFileName", "fileSize", "filePath", 
                   "sourceOrigin", "sourceDatasetId",
                   "dataSnapshot", "datasetGroup", "userId", "createdAt", "updatedAt",
                   -- The materialisation state. Without it the detail page cannot
                   -- say which kind of dataset it is looking at, nor whether the
                   -- build succeeded: measured 2026-11-06 on vd_d31158c13fc04527,
                   -- which was materialised and rendered as though it were not.
                   "materialized", "materializedAt", "materializeError"
            FROM "UserDataset"
            WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (SELECT "userGroup" FROM "User" WHERE id = $2)))
            """,
            dataset_id, user_id
        )

    if row is None:
        raise HTTPException(
            status_code=404, 
            detail=await t(_db_pool, language, DATASETS["error.dataset.not_found_2"], id=dataset_id)
        )

    result = _dataset_row(row)
    
    result["isOwn"] = result["userId"] == user_id

    # Resolve the parent name for derived (cleaned) datasets.
    result["sourceDatasetName"] = None
    if result.get("sourceDatasetId"):
        async with _db_pool.acquire() as conn:
            parent_row = await conn.fetchrow(
                'SELECT name FROM "UserDataset" WHERE id = $1',
                result["sourceDatasetId"],
            )
        result["sourceDatasetName"] = parent_row["name"] if parent_row else None

    if not result["isOwn"]:
        async with _db_pool.acquire() as conn:
            user_row = await conn.fetchrow(
                'SELECT name FROM "User" WHERE id = $1',
                result["userId"]
            )
            result["userName"] = user_row["name"] if user_row else await t(_db_pool, language, DATASETS["common.unknown"])

    async with _db_pool.acquire() as conn:
        desc_rows = await conn.fetch(
            """
            SELECT id, description, "generatedAt", "usedModel"
            FROM "DatasetDescription"
            WHERE "datasetId" = $1
            ORDER BY "generatedAt" DESC
            """,
            dataset_id
        )
        result["descriptions"] = [dict(row) for row in desc_rows]
    
    async with _db_pool.acquire() as conn:
        rule_rows = await conn.fetch(
            """
            SELECT r.id, r.name, r.description, r."ruleGroup", r."userId", r."isShared"
            FROM "DataPreparationRule" r
            WHERE r."datasetId" = $1 AND (r."userId" = $2 OR ("isShared" = true AND r."ruleGroup" IN (SELECT "userGroup" FROM "User" WHERE id = $2)))
            ORDER BY r."createdAt" DESC
            """,
            dataset_id, user_id
        )
    
    result["preparation_rules"] = []
    for rule in rule_rows:
        rule_dict = dict(rule)
        rule_dict["isOwn"] = rule_dict["userId"] == user_id
        result["preparation_rules"].append(rule_dict)

    return {"dataset": result}

@router.get("/connection/{connection_id}/tables")
async def list_tables(
    connection_id: int,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """List all tables in the database connection."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500, 
            detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    
    try:
        conn_details = await get_connection_row(connection_id, user_id, language)
    except HTTPException:
        raise
    
    if conn_details is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, DATASETS["database.connection_not_found"])
        )
    
    from src.utils.encryption import decrypt_field
    try:
        decrypted_password = decrypt_field(conn_details["password"])
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=await t(_db_pool, language, DATASETS["database.decryption_failed"], error=str(e))
        )
    
    if conn_details["type"] == "postgresql":
        conn_str = f"postgresql://{conn_details['username']}:{decrypted_password}@{conn_details['host']}:{conn_details['port']}/{conn_details['database']}"
        try:
            ext_conn = await asyncpg.connect(conn_str)
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=await t(_db_pool, language, DATASETS["database.connection_failed"], error=str(e))
            )
        
        try:
            # Relations this session can name by bare name — see common/relations.py.
            query = VISIBLE_RELATIONS
            result = await ext_conn.fetch(query)
            tables = [row["table_name"] for row in result if row["table_type"] == "BASE TABLE"]
            await ext_conn.close()
            return {"sources": tables}
        except Exception as e:
            await ext_conn.close()
            raise HTTPException(
                status_code=400, 
                detail=await t(_db_pool, language, DATASETS["database.query_failed"], error=str(e))
            )
    elif conn_details["type"] == "mysql":
        import aiomysql
        try:
            mysql_conn = await aiomysql.connect(
                host=conn_details["host"],
                port=conn_details["port"],
                db=conn_details["database"],
                user=conn_details["username"],
                password=decrypted_password,
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DATASETS["database.connection_failed"], error=str(e))
            )
        try:
            async with mysql_conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT TABLE_NAME FROM information_schema.TABLES "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' "
                    "ORDER BY TABLE_NAME",
                    (conn_details["database"],)
                )
                rows = await cur.fetchall()
                tables = [row["TABLE_NAME"] for row in rows]
            mysql_conn.close()
            return {"sources": tables}
        except Exception as e:
            mysql_conn.close()
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DATASETS["database.query_failed"], error=str(e))
            )
    elif conn_details["type"] == "mssql":
        import pymssql
        def _connect():
            return pymssql.connect(
                host=conn_details["host"],
                port=conn_details["port"],
                database=conn_details["database"],
                user=conn_details["username"],
                password=decrypted_password,
                login_timeout=15,
            )
        try:
            conn = await asyncio.to_thread(_connect)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DATASETS["database.connection_failed"], error=str(e))
            )
        try:
            cursor = conn.cursor(as_dict=True)
            cursor.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY TABLE_NAME",
                (conn_details.get("schema", "dbo"),)
            )
            rows = cursor.fetchall()
            tables = [row["TABLE_NAME"] for row in rows]
            conn.close()
            return {"sources": tables}
        except Exception as e:
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DATASETS["database.query_failed"], error=str(e))
            )
    elif conn_details["type"] == "access":
        import psycopg2
        def _connect_access():
            return psycopg2.connect(
                host=conn_details["host"],
                port=conn_details["port"],
                user=conn_details["username"],
                password=decrypted_password,
                dbname=conn_details["database"],
                connect_timeout=15,
            )
        try:
            pg_conn = await asyncio.to_thread(_connect_access)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DATASETS["database.connection_failed"], error=str(e))
            )
        try:
            cur = pg_conn.cursor()
            cur.execute(VISIBLE_RELATIONS)
            rows = cur.fetchall()
            tables = [r[1] for r in rows if r[2] == "BASE TABLE" and not r[1].startswith("MSys")]
            cur.close()
            pg_conn.close()
            return {"sources": tables}
        except Exception as e:
            pg_conn.close()
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DATASETS["database.query_failed"], error=str(e))
            )
    else:
        raise HTTPException(
            status_code=501, 
            detail=await t(_db_pool, language, DATASETS["database.type_not_supported"], type=conn_details["type"])
        )

@router.get("/connection/{connection_id}/views")
async def list_views(
    connection_id: int,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """List all views in the database connection."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500, 
            detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    
    try:
        conn_details = await get_connection_row(connection_id, user_id, language)
    except HTTPException:
        raise
    
    if conn_details is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, DATASETS["database.connection_not_found"])
        )
    
    from src.utils.encryption import decrypt_field
    try:
        decrypted_password = decrypt_field(conn_details["password"])
    except Exception as e:
        raise HTTPException(
            status_code=500, 
            detail=await t(_db_pool, language, DATASETS["database.decryption_failed"], error=str(e))
        )
    
    if conn_details["type"] == "postgresql":
        conn_str = f"postgresql://{conn_details['username']}:{decrypted_password}@{conn_details['host']}:{conn_details['port']}/{conn_details['database']}"
        try:
            ext_conn = await asyncpg.connect(conn_str)
        except Exception as e:
            raise HTTPException(
                status_code=400, 
                detail=await t(_db_pool, language, DATASETS["database.connection_failed"], error=str(e))
            )
        
        try:
            # No longer `information_schema.views`, which names one schema: this asks for
            # every relation the session can name and keeps the views.
            query = VISIBLE_RELATIONS
            result = await ext_conn.fetch(query)
            views = [row["table_name"] for row in result if row["table_type"] == "VIEW"]
            await ext_conn.close()
            return {"sources": views}
        except Exception as e:
            await ext_conn.close()
            raise HTTPException(
                status_code=400, 
                detail=await t(_db_pool, language, DATASETS["database.query_failed"], error=str(e))
            )
    elif conn_details["type"] == "mysql":
        import aiomysql
        try:
            mysql_conn = await aiomysql.connect(
                host=conn_details["host"],
                port=conn_details["port"],
                db=conn_details["database"],
                user=conn_details["username"],
                password=decrypted_password,
            )
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DATASETS["database.connection_failed"], error=str(e))
            )
        try:
            async with mysql_conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(
                    "SELECT TABLE_NAME FROM information_schema.VIEWS "
                    "WHERE TABLE_SCHEMA = %s "
                    "ORDER BY TABLE_NAME",
                    (conn_details["database"],)
                )
                rows = await cur.fetchall()
                views = [row["TABLE_NAME"] for row in rows]
            mysql_conn.close()
            return {"sources": views}
        except Exception as e:
            mysql_conn.close()
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DATASETS["database.query_failed"], error=str(e))
            )
    elif conn_details["type"] == "mssql":
        import pymssql
        def _connect():
            return pymssql.connect(
                host=conn_details["host"],
                port=conn_details["port"],
                database=conn_details["database"],
                user=conn_details["username"],
                password=decrypted_password,
                login_timeout=15,
            )
        try:
            conn = await asyncio.to_thread(_connect)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DATASETS["database.connection_failed"], error=str(e))
            )
        try:
            cursor = conn.cursor(as_dict=True)
            cursor.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.VIEWS "
                "WHERE TABLE_SCHEMA = %s "
                "ORDER BY TABLE_NAME",
                (conn_details.get("schema", "dbo"),)
            )
            rows = cursor.fetchall()
            views = [row["TABLE_NAME"] for row in rows]
            conn.close()
            return {"sources": views}
        except Exception as e:
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DATASETS["database.query_failed"], error=str(e))
            )
    elif conn_details["type"] == "access":
        import psycopg2
        def _connect_access():
            return psycopg2.connect(
                host=conn_details["host"],
                port=conn_details["port"],
                user=conn_details["username"],
                password=decrypted_password,
                dbname=conn_details["database"],
                connect_timeout=15,
            )
        try:
            pg_conn = await asyncio.to_thread(_connect_access)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DATASETS["database.connection_failed"], error=str(e))
            )
        try:
            cur = pg_conn.cursor()
            cur.execute(VISIBLE_RELATIONS)
            rows = cur.fetchall()
            views = [r[1] for r in rows if r[2] == "VIEW" and not r[1].startswith("MSys")]
            cur.close()
            pg_conn.close()
            return {"sources": views}
        except Exception as e:
            pg_conn.close()
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DATASETS["database.query_failed"], error=str(e))
            )
    else:
        raise HTTPException(
            status_code=501, 
            detail=await t(_db_pool, language, DATASETS["database.type_not_supported"], type=conn_details["type"])
        )

@router.delete("/{dataset_id}")
async def delete_dataset(
    dataset_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    if _db_pool is None:
        raise HTTPException(
            status_code=500, 
            detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    # Who may delete: the dataset's owner, or an administrator when it is shared to
    # theirs — the rule every other dataset write asks (can_edit_dataset). A caller
    # who is neither gets the same answer as one asking for a row that does not
    # exist, so the row's existence is not disclosed.
    if not await can_edit_dataset(_db_pool, dataset_id, user_id):
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, DATASETS["datasets.not_owned"], id=dataset_id)
        )

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT "sourceType", "tableName", "materialized", "userId" FROM "UserDataset" WHERE id = $1',
            dataset_id
        )
        if row is None:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, DATASETS["datasets.not_owned"], id=dataset_id)
            )

        source_type = row["sourceType"]
        table_name = row["tableName"]
        materialized = row.get("materialized", False)
        # The row's owner, not the caller: an administrator deleting a shared dataset
        # must still drop that dataset's materialised table.
        owner_id = row["userId"]

    if source_type == "upload" and table_name:
        try:
            await drop_table(table_name)
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=await t(_db_pool, language, DATASETS["error.dataset.delete_failed_2"], error=str(e))
            )

    # For virtual datasets: drop the materialised PostgreSQL table. Step B1 puts
    # it in the owner's schema; the bare name is where it lived before that, and
    # the tables created back then stay there until the mover of Step B3 has been
    # applied — so both are dropped while the two conventions coexist. The public
    # drop goes once the move is behind us.
    if source_type == "virtual" and materialized:
        for name in (f"{user_schema_name(owner_id)}.virtual_{dataset_id}", f"virtual_{dataset_id}"):
            try:
                await drop_table(name)
            except Exception:
                pass

    async with _db_pool.acquire() as conn:
        result = await conn.execute(
            'DELETE FROM "UserDataset" WHERE id = $1',
            dataset_id
        )
        if result == "DELETE 0":
            raise HTTPException(
                status_code=404, 
                detail=await t(_db_pool, language, DATASETS["datasets.not_owned"], id=dataset_id)
            )
    
    return {
        "success": True, 
        "message": await t(_db_pool, language, DATASETS["datasets.delete.success"], id=dataset_id)
    }

@router.patch("/{dataset_id}/share")
async def toggle_dataset_share(
    dataset_id: str,
    request: dict,
    request_obj: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Toggle sharing for a dataset (own datasets only)."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500, 
            detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    shared = request.get("shared", False)

    async with _db_pool.acquire() as conn:
        user_row = await conn.fetchrow(
            'SELECT "userGroup" FROM "User" WHERE id = $1',
            user_id
        )
        user_group = user_row["userGroup"] if user_row else "00"

    async with _db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            'SELECT id FROM "UserDataset" WHERE id = $1 AND "userId" = $2',
            dataset_id, user_id
        )
        if existing is None:
            raise HTTPException(
                status_code=404, 
                detail=await t(_db_pool, language, DATASETS["datasets.not_owned"], id=dataset_id)
            )

    is_shared = shared

    async with _db_pool.acquire() as conn:
        await conn.execute(
            'UPDATE "UserDataset" SET "datasetGroup" = $3, "isShared" = $1, "updatedAt" = NOW() WHERE id = $2',
            is_shared, dataset_id, user_group if is_shared else '00'
        )

    return {
        "success": True, 
        "dataset_id": dataset_id, 
        "datasetGroup": user_group if is_shared else '00',
        "isShared": is_shared,
        "message": await t(_db_pool, language, DATASETS["datasets.share.toggled"], id=dataset_id)
    }