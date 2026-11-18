"""
Upload Dataset – File upload and PostgreSQL (workbench_data) storage
Part of the 0.0.10 "Statistical Foundation" milestone.
"""

import os
import uuid
import traceback
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from .crud import get_user_id_from_token, get_current_language, UPLOAD_SOURCE_TYPES
from src.utils.translation import t
from src.postgres_data_manager import (
    DATA_DB_NAME,
    DbfFieldTypeUnsupportedError,
    DbfMemoUnsupportedError,
    UPLOAD_FORMATS,
    create_table_from_rows,
    drop_table,
    generate_table_name,
    json_safe,
    user_schema_name,
)
from .translations import UPLOAD

router = APIRouter()
security = HTTPBearer()
_db_pool = None

def set_db_pool(pool):
    global _db_pool
    _db_pool = pool

@router.post("/upload")
async def upload_dataset(
    file: UploadFile = File(...),
    name: str = Form(...),
    description: Optional[str] = Form(None),
    shared: Optional[bool] = Form(False),
    request: Request = None,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, UPLOAD["error.database.pool_not_initialized"])
        )
    
    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        user_row = await conn.fetchrow(
            'SELECT "maxUploadCount", "maxUploadSizeMB", "userGroup" FROM "User" WHERE id = $1',
            user_id
        )
        if user_row is None:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, UPLOAD["datasets.upload.user_not_found"])
            )
        max_count = user_row["maxUploadCount"]
        max_size_mb = user_row["maxUploadSizeMB"]
        user_group = user_row["userGroup"] or "00"

    if max_count != 0:
        async with _db_pool.acquire() as conn:
            # The quota counts the datasets that hold data the user brought in —
            # uploads and notebook imports. Tables registered from a connection and
            # virtual joins are not uploads, and the user spent no quota on them.
            count = await conn.fetchval(
                'SELECT COUNT(*) FROM "UserDataset" WHERE "userId" = $1 AND "sourceType" = ANY($2::text[])',
                user_id, list(UPLOAD_SOURCE_TYPES)
            )
            if count >= max_count:
                raise HTTPException(
                    status_code=403,
                    detail=await t(_db_pool, language, UPLOAD["datasets.upload.limit_reached_count"], count=max_count)
                )

    contents = await file.read()
    file_size_bytes = len(contents)
    original_filename = file.filename or "unknown"

    if max_size_mb != 0:
        async with _db_pool.acquire() as conn:
            total_bytes = await conn.fetchval(
                'SELECT COALESCE(SUM("fileSize"), 0) FROM "UserDataset" WHERE "userId" = $1',
                user_id
            )
            total_mb = (total_bytes + file_size_bytes) / (1024 * 1024)
            if total_mb > max_size_mb:
                raise HTTPException(
                    status_code=403,
                    detail=await t(_db_pool, language, UPLOAD["datasets.upload.limit_reached_size"], size=max_size_mb)
                )

    table_name = None
    rows = []
    
    try:
        # The upload is created inside the account's own schema, and the
        # schema-qualified name is what the dataset row records (Option B).
        table_name = f"{user_schema_name(user_id)}.{generate_table_name(user_id)}"
        
        # One list, matched case-insensitively. The accepted set lives in
        # UPLOAD_FORMATS, so it cannot drift from the refusal message below,
        # which names that same set. The already-normalised filename is used,
        # so a nameless upload takes the same path here as in the Go port.
        extension = os.path.splitext(original_filename)[1].lower()
        parser = UPLOAD_FORMATS.get(extension)
        if parser is None:
            raise HTTPException(
                status_code=400,
                detail=await t(
                    _db_pool,
                    language,
                    UPLOAD["datasets.upload.unsupported_file"],
                    extensions=", ".join(sorted(UPLOAD_FORMATS)),
                )
            )
        # A .dbf this reader will not take is a decision, not a failure: it is
        # reported as the refusal it is, rather than falling through to the
        # generic "failed to process file" below.
        try:
            columns, rows = parser(contents)
        except DbfMemoUnsupportedError as e:
            raise HTTPException(
                status_code=400,
                detail=await t(
                    _db_pool,
                    language,
                    UPLOAD["datasets.upload.dbf_memo_unsupported"],
                ),
            ) from e
        except DbfFieldTypeUnsupportedError as e:
            raise HTTPException(
                status_code=400,
                detail=await t(
                    _db_pool,
                    language,
                    UPLOAD["datasets.upload.dbf_field_unsupported"],
                    types=str(e),
                ),
            ) from e
        
        await create_table_from_rows(columns, rows, table_name)
        data_snapshot = [json_safe(row) for row in rows[:10]]
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"Error processing file: {traceback.format_exc()}")
        if table_name:
            try:
                await drop_table(table_name)
            except:
                pass
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, UPLOAD["datasets.upload.file_processing_failed"], error=str(e))
        )

    is_shared = shared
    dataset_group = user_group if shared else '00'

    dataset_id = str(uuid.uuid4())
    
    try:
        async with _db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO "UserDataset" (
                    id, "userId", name, description, "sourceType", 
                    "storageType", "sourceConnectionId", "databaseName", "tableName", 
                    "originalFileName", "fileSize", "filePath", 
                    "dataSnapshot", "datasetGroup", "isShared", "createdAt", "updatedAt"
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, NOW(), NOW())
                """,
                dataset_id, 
                user_id, 
                name, 
                description, 
                "upload", 
                "postgresql",
                None,
                DATA_DB_NAME,
                table_name,
                original_filename, 
                file_size_bytes, 
                original_filename,
                data_snapshot, 
                dataset_group, 
                is_shared
            )
    except Exception as e:
        print(f"Database insert error: {traceback.format_exc()}")
        if table_name:
            try:
                await drop_table(table_name)
            except:
                pass
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, UPLOAD["error.database.insert_failed"], error=str(e))
        )

    return {
        "dataset": {
            "id": dataset_id, 
            "name": name, 
            "originalFileName": original_filename,
            "fileSize": file_size_bytes,
            "sourceType": "upload",
            "storageType": "postgresql",
            "tableName": table_name,
            "rowCount": len(rows),
            "description": description, 
            "datasetGroup": "00",
            "isShared": is_shared
        },
        "message": await t(_db_pool, language, UPLOAD["datasets.upload.success"], name=name)
    }