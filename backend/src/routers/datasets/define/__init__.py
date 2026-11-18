"""
Define Dataset — type-specific schema extraction and dataset definition.

This package replaces the monolithic if/elif chain in the original
define.py. Each database type has its own module exporting two functions:
  - get_schema(conn_details, table_name, decrypted_password, _db_pool, language, t) → dict
  - define_dataset(conn_details, table_name, decrypted_password, _db_pool, language, t) → tuple

Adding a new database type means creating one new module and adding one
entry to SCHEMA_EXTRACTORS / DEFINE_HANDLERS below. No changes to the
router or dispatch logic.
"""

import os
import uuid
import traceback
import asyncio
import asyncpg
import math
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional
from datetime import datetime, date, time
from pydantic import BaseModel

from ..crud import get_user_id_from_token, get_current_language, get_connection_row
from src.utils.translation import t
from ..translations import DATASETS, DEFINE
from src.routers.common.feature_gate import require_db_feature

from . import postgresql
from . import mysql
from . import mssql
from . import access
from src.utils.timestamps import iso_utc

# ── Router setup (same as original define.py) ────────────────────────

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


router = APIRouter()
security = HTTPBearer()


def json_serializable(value):
    """Convert a value to JSON-serializable format."""
    if value is None:
        return None
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, datetime):
        return iso_utc(value)
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode('utf-8', errors='replace')
    if isinstance(value, memoryview):
        return bytes(value).decode('utf-8', errors='replace')
    if isinstance(value, (int, float, str, bool)):
        return value
    if isinstance(value, dict):
        return {k: json_serializable(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_serializable(v) for v in value]
    return str(value)


# ── Type dispatch ────────────────────────────────────────────────────

SCHEMA_EXTRACTORS = {
    "postgresql": postgresql,
    "mysql": mysql,
    "mssql": mssql,
    "access": access,
}

DEFINE_HANDLERS = {
    "postgresql": postgresql,
    "mysql": mysql,
    "mssql": mssql,
    "access": access,
}


async def extract_schema(conn_details: dict, table_name: str,
                          decrypted_password: str, language: str) -> dict:
    """Dispatch schema extraction to the correct type module."""
    db_type = conn_details["type"]
    module = SCHEMA_EXTRACTORS.get(db_type)
    if module is None:
        raise HTTPException(
            status_code=501,
            detail=await t(_db_pool, language, DEFINE["error.connection.type_not_supported"],
                type=db_type),
        )
    return await module.get_schema(
        conn_details, table_name, decrypted_password, _db_pool, language, t)


async def extract_define(conn_details: dict, table_name: str,
                          decrypted_password: str, language: str) -> tuple:
    """Dispatch dataset definition to the correct type module."""
    db_type = conn_details["type"]
    module = DEFINE_HANDLERS.get(db_type)
    if module is None:
        raise HTTPException(
            status_code=501,
            detail=await t(_db_pool, language, DEFINE["error.connection.type_not_supported"],
                type=db_type),
        )
    return await module.define_dataset(
        conn_details, table_name, decrypted_password, _db_pool, language, t)


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/connection/{connection_id}/schema/{table_name}")
async def get_table_schema(
    connection_id: int,
    table_name: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Get schema and preview data for a table/view from a database connection."""
    global _db_pool

    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DEFINE["error.database.pool_not_initialized"]),
        )

    user_id = await get_user_id_from_token(credentials)

    try:
        conn_details = await get_connection_row(connection_id, user_id, language)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DEFINE["datasets.define.connection_not_found"]),
        )

    if conn_details is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, DATASETS["database.connection_not_found"]),
        )

    from src.utils.encryption import decrypt_field
    try:
        decrypted_password = decrypt_field(conn_details["password"])
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DEFINE["error.connection.decryption_failed"], error=str(e)),
        )

    return await extract_schema(conn_details, table_name, decrypted_password, language)


@router.post("/define")
async def define_dataset(
    request: dict,
    request_obj: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Define a dataset from a database connection (table or view)."""
    global _db_pool

    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DEFINE["error.database.pool_not_initialized"]),
        )

    user_id = await get_user_id_from_token(credentials)

    name = request.get("name")
    if not name or not name.strip():
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DEFINE["datasets.define.name_required"]),
        )

    shared = request.get("shared", False)
    connection_id = request.get("connectionId")
    table_name = request.get("tableName")

    try:
        conn_details = await get_connection_row(connection_id, user_id, language)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DEFINE["datasets.define.connection_not_found"]),
        )

    if conn_details is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, DATASETS["database.connection_not_found"]),
        )

    from src.utils.encryption import decrypt_field
    try:
        decrypted_password = decrypt_field(conn_details["password"])
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DEFINE["error.connection.decryption_failed"], error=str(e)),
        )

    try:
        columns, data_snapshot, count_result = await extract_define(
            conn_details, table_name, decrypted_password, language)
    except HTTPException:
        raise
    except Exception as e:
        print(f"[DEBUG] Unexpected error: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DEFINE["datasets.define.database_connection_failed"], error=str(e)),
        )

    is_shared = shared
    dataset_id = str(uuid.uuid4())
    database_name = conn_details["database"]
    conn_type = conn_details["type"]
    storage_type = conn_type

    try:
        async with _db_pool.acquire() as conn:
            await conn.execute(
                """INSERT INTO "UserDataset"
                   (id, name, description, "userId", "sourceType", "storageType",
                    "sourceConnectionId", "tableName", "databaseName",
                    "dataSnapshot", "outputSchema", "createdAt", "updatedAt")
                   VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, NOW(), NOW())""",
                dataset_id, name, request.get("description", "") or "",
                user_id, storage_type, storage_type, connection_id,
                table_name, database_name, data_snapshot, columns,
            )

    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DEFINE["error.define.dataset_creation_failed"], error=str(e)),
        )

    return {
        "message": await t(_db_pool, language, DEFINE["datasets.define.dataset_created"], name=name),
        "dataset": {
            "id": dataset_id,
            "name": name,
            "sourceType": storage_type,
            "columnCount": len(columns),
            "rowCount": count_result,
            "preview": data_snapshot,
        },
    }


# ── Test endpoints (unchanged from original define.py) ───────────────

class PostgresTestRequest(BaseModel):
    host: str
    port: int
    database: str
    username: str
    password: str


@router.post("/test-postgres")
async def test_postgres_connection(
    request_body: PostgresTestRequest,
    language: str = Depends(get_current_language),
):
    """Test a connection to a PostgreSQL database."""
    await require_db_feature(_db_pool, "postgresql", language)
    conn_str = (
        f"postgresql://{request_body.username}:{request_body.password}"
        f"@{request_body.host}:{request_body.port}/{request_body.database}"
    )
    try:
        test_conn = await asyncpg.connect(conn_str)
        await test_conn.close()
        return {"success": True, "message": await t(_db_pool, language, DEFINE["datasets.define.connection_successful"])}
    except Exception as e:
        msg = str(e)
        # PostgreSQL says "does not exist" for both missing databases
        # and permission-denied — add a hint
        if "does not exist" in msg.lower():
            msg += "\n\n" + await t(_db_pool, language, DEFINE["datasets.define.connection_missing_db_note"])
        return {"success": False, "message": msg}


class MySQLTestRequest(BaseModel):
    host: str
    port: int
    database: str
    username: str
    password: str


@router.post("/test-mysql")
async def test_mysql_connection(
    request_body: MySQLTestRequest,
    language: str = Depends(get_current_language),
):
    """Test a connection to a MySQL database."""
    await require_db_feature(_db_pool, "mysql", language)
    import aiomysql
    try:
        mysql_conn = await aiomysql.connect(
            host=request_body.host,
            port=request_body.port,
            db=request_body.database,
            user=request_body.username,
            password=request_body.password,
            connect_timeout=10,
        )
        mysql_conn.close()
        return {"success": True, "message": await t(_db_pool, language, DEFINE["datasets.define.connection_successful"])}
    except Exception as e:
        msg = str(e)
        # PostgreSQL says "does not exist" for both missing databases
        # and permission-denied — add a hint
        if "does not exist" in msg.lower():
            msg += "\n\n" + await t(_db_pool, language, DEFINE["datasets.define.connection_missing_db_note"])
        return {"success": False, "message": msg}


class MSSQLTestRequest(BaseModel):
    host: str
    port: int
    database: str
    username: str
    password: str


@router.post("/test-mssql")
async def test_mssql_connection(
    request_body: MSSQLTestRequest,
    req: Request,
    language: str = Depends(get_current_language),
):
    """Test a connection to an MS SQL Server database."""
    await require_db_feature(_db_pool, "mssql", language)
    import pymssql
    import asyncio

    def _try_connect():
        return pymssql.connect(
            host=request_body.host,
            port=request_body.port,
            database=request_body.database,
            user=request_body.username,
            password=request_body.password,
            login_timeout=10,
            tds_version="7.3",
        )

    try:
        conn = await asyncio.wait_for(asyncio.to_thread(_try_connect), timeout=15.0)
        conn.close()
        return {"success": True, "message": await t(_db_pool, language, DEFINE["datasets.define.connection_successful"])}
    except asyncio.TimeoutError:
        return {"success": False, "message": await t(_db_pool, language, DEFINE["datasets.define.connection_timed_out"])}
    except Exception as e:
        msg = str(e)
        # PostgreSQL says "does not exist" for both missing databases
        # and permission-denied — add a hint
        if "does not exist" in msg.lower():
            msg += "\n\n" + await t(_db_pool, language, DEFINE["datasets.define.connection_missing_db_note"])
        return {"success": False, "message": msg}
