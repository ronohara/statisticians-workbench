"""
AI Description Generation – Generate descriptions for datasets
Part of the 0.0.10 "Statistical Foundation" milestone.
"""

import os
import uuid
import asyncio
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import Optional
from .crud import get_connection_row, get_current_language, get_user_id_from_token
from src.utils.translation import t
from src.utils.connection_timeouts import resolve_connection_timeouts
from src.utils.ai_limits import (
    is_timeout_error,
    apply_timeout_override,
    MAX_TIMEOUT_SECONDS,
    resolve_ai_limits_for_model,
)
from src.utils.llm_connection import create_llm
from src.utils.dataset_description_generator import generate_dataset_description
from .translations import DESCRIBE, DATASETS
from src.postgres_data_manager import get_table_preview, table_exists

router = APIRouter()
security = HTTPBearer()
_db_pool = None

def set_db_pool(pool):
    global _db_pool
    _db_pool = pool

class DescribeRequest(BaseModel):
    connectionId: int
    model: Optional[str] = None
    # Per-request escalation (AI limits plan, Item 12). Absent means "use the resolved
    # value"; present means "this one attempt gets this long". Never stored — the next
    # request starts from the resolved default again.
    timeoutSeconds: Optional[int] = None

@router.post("/{dataset_id}/describe")
async def describe_dataset(
    dataset_id: str,
    request: DescribeRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DESCRIBE["error.database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT "dataSnapshot", name, "sourceType", "storageType", "sourceConnectionId", 
                   "tableName"
            FROM "UserDataset"
            WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                SELECT "userGroup" FROM "User" WHERE id = $2
            )))
            """,
            dataset_id, user_id
        )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, DATASETS["error.dataset.not_found_2"], id=dataset_id)
        )

    async with _db_pool.acquire() as conn:
        language_row = await conn.fetchrow(
            'SELECT language, "userGroup" FROM "User" WHERE id = $1',
            user_id
        )
        user_language = language_row["language"] if language_row else "en"

    data_snapshot = row["dataSnapshot"]
    dataset_name = row["name"]
    source_type = row["sourceType"]
    storage_type = row["storageType"]
    source_connection_id = row["sourceConnectionId"]
    table_name = row["tableName"]
    
    if not data_snapshot or len(data_snapshot) == 0:
        if source_type in ("upload", "notebook") and storage_type == "postgresql" and table_name:
            try:
                if await table_exists(table_name):
                    preview_rows = await get_table_preview(table_name, limit=10)
                    if preview_rows:
                        data_snapshot = preview_rows
            except Exception as e:
                print(f"Error fetching preview from workbench_data: {e}")
        elif source_type in ["table", "view"] and source_connection_id and table_name:
            try:
                conn_details = await get_connection_row(source_connection_id, user_id, language)
                if conn_details is None:
                    raise HTTPException(
                        status_code=404,
                        detail=await t(_db_pool, language, DESCRIBE["error.define.connection_not_found"])
                    )
                
                from src.utils.encryption import decrypt_field
                try:
                    decrypted_password = decrypt_field(conn_details["password"])
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=await t(_db_pool, language, DESCRIBE["error.connection.decryption_failed"], error=str(e))
                    )
                
                if conn_details["type"] == "postgresql":
                    conn_str = f"postgresql://{conn_details['username']}:{decrypted_password}@{conn_details['host']}:{conn_details['port']}/{conn_details['database']}"
                    try:
                        ext_conn = await asyncpg.connect(conn_str)
                    except Exception as e:
                        raise HTTPException(
                            status_code=400,
                            detail=await t(_db_pool, language, DESCRIBE["error.connection.failed"], error=str(e))
                        )
                    
                    try:
                        preview_query = f'SELECT * FROM "{table_name}" LIMIT 10'
                        preview_result = await ext_conn.fetch(preview_query)
                        data_snapshot = [dict(row) for row in preview_result]
                        
                        for row in data_snapshot:
                            for key, value in row.items():
                                if isinstance(value, bytes):
                                    row[key] = value.decode('utf-8', errors='replace')
                                elif isinstance(value, memoryview):
                                    row[key] = bytes(value).decode('utf-8', errors='replace')
                        
                        await ext_conn.close()
                    except Exception as e:
                        await ext_conn.close()
                        raise HTTPException(
                            status_code=400,
                            detail=await t(_db_pool, language, DESCRIBE["error.connection.query_failed_7"], error=str(e))
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
                            detail=await t(_db_pool, language, DESCRIBE["error.connection.failed"], error=str(e))
                        )
                    try:
                        async with mysql_conn.cursor(aiomysql.DictCursor) as cur:
                            await cur.execute(f"SELECT * FROM `{table_name}` LIMIT 10")
                            result = await cur.fetchall()
                        data_snapshot = list(result)
                        for row in data_snapshot:
                            for key, value in list(row.items()):
                                if isinstance(value, bytes):
                                    row[key] = value.decode('utf-8', errors='replace')
                        mysql_conn.close()
                    except Exception as e:
                        mysql_conn.close()
                        raise HTTPException(
                            status_code=400,
                            detail=await t(_db_pool, language, DESCRIBE["error.connection.query_failed_7"], error=str(e))
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
                        )
                    conn = await asyncio.to_thread(_connect)
                    try:
                        cursor = conn.cursor(as_dict=True)
                        cursor.execute(f"SELECT TOP 10 * FROM [{table_name}]")
                        result = cursor.fetchall()
                        data_snapshot = list(result)
                        for row in data_snapshot:
                            for key, value in list(row.items()):
                                if isinstance(value, bytes):
                                    row[key] = value.decode('utf-8', errors='replace')
                        conn.close()
                    except Exception as e:
                        conn.close()
                        raise HTTPException(
                            status_code=400,
                            detail=await t(_db_pool, language, DESCRIBE["error.connection.query_failed_7"], error=str(e))
                        )
            except HTTPException:
                raise
            except Exception as e:
                print(f"Error fetching preview for description: {e}")

    # Normalise the snapshot to a list of row dicts (the pandas DataFrame
    # construction used to absorb None / a single dict / an empty value).
    if not data_snapshot:
        data_snapshot = []
    elif isinstance(data_snapshot, dict):
        data_snapshot = [data_snapshot]

    try:
        lm = await create_llm(
            db_pool=_db_pool,
            user_id=user_id,
            connection_id=request.connectionId,
            model_name=request.model
        )
    except ValueError as e:
        error_msg = str(e)
        if "DSPY_NO_CONNECTION" in error_msg:
            detail = await t(_db_pool, language, DESCRIBE["error.describe.ai_connection_error"])
        elif "DSPY_DECRYPTION_FAILED" in error_msg:
            detail = await t(_db_pool, language, DESCRIBE["error.describe.ai_connection_error_2"])
        else:
            detail = await t(_db_pool, language, DESCRIBE["datasets.describe.ai_connection_error"], error=error_msg)
        raise HTTPException(
            status_code=400,
            detail=detail
        )
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DESCRIBE["datasets.describe.ai_connection_error"], error=str(e))
        )

    try:
        # The limits in force for this pair, resolved here rather than inside the
        # generator so the generator stays a pure "build a prompt and call" function
        # and one place owns the database read. This is where the 60-second Ollama
        # defect is fixed: a pair tuned for a slow local model gets its own bound,
        # while a cloud endpoint keeps a short one.
        async with _db_pool.acquire() as limits_conn:
            limits = await resolve_ai_limits_for_model(
                limits_conn, request.connectionId, lm.model
            )
            # The connection's connect budget (plan Item 4a), resolved on the same
            # connection as the pair limits: one acquire, two reads.
            conn_timeouts = await resolve_connection_timeouts(limits_conn, request.connectionId)

        # The per-request tier, above the resolved ones. Refused here rather than
        # silently clamped: a caller who asked for 5000 deserves to be told the
        # ceiling, not to have their number quietly changed.
        try:
            limits = apply_timeout_override(limits, request.timeoutSeconds)
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DESCRIBE["datasets.describe.timeout_out_of_range"],
                               max_seconds=MAX_TIMEOUT_SECONDS),
            )

        description = await generate_dataset_description(
            lm=lm,
            limits=limits,
            datasets={dataset_name: data_snapshot},
            existing_description="",
            dataset_names=[dataset_name],
            language=user_language,
            connect_timeout=float(conn_timeouts.connect_seconds),
        )
        if not description or not description.strip():
            raise ValueError(await t(_db_pool, language, DESCRIBE["datasets.describe.empty_description"]))
    except HTTPException:
        # Raised by this handler itself — the ceiling refusal above is a 400 that has
        # already been translated. Without this clause the broad catch below re-wraps
        # it as a 402 "failed", which tells the caller the wrong thing and loses the
        # status. Caught by testing: a 1201-second override answered 402/failed.
        raise
    except Exception as e:
        # A timeout is the one failure a retry can fix, and only with more time. The
        # response says so machine-readably, in the BODY rather than a header: a client
        # reading a JSON error should not have to make a second call to read headers,
        # and `detail` stays the user-facing sentence it already was.
        #
        # `timeoutSecondsUsed` is the value that actually failed, so the retry preset
        # is computed from what happened rather than from a guess — and it stays
        # correct if the pair was retuned between the two calls.
        timed_out = is_timeout_error(e)
        return JSONResponse(
            status_code=402,
            content={
                "detail": await t(
                    _db_pool, language, DESCRIBE["datasets.describe.generation_failed"], error=str(e)
                ),
                "reason": "timeout" if timed_out else "failed",
                "timeoutSecondsUsed": limits.timeout_seconds,
            },
        )

    return {
        "description": description,
        "message": await t(_db_pool, language, DESCRIBE["datasets.describe.description_generated"], name=dataset_name)
    }