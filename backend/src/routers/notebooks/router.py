"""
Notebooks router — API endpoints for notebook import.
"""

import json
import uuid
import traceback
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, Form
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.utils.translation import t
from src.utils.encryption import decrypt_field
from src.postgres_data_manager import DATA_DB_NAME
from src.routers.datasets.crud import (
    get_user_id_from_token,
    get_connection_row,
)
from src.routers.datasets.translations import DATASETS
from .translations import NOTEBOOKS
from .parser import NotebookParser, MAX_NOTEBOOK_FILE_SIZE
from .storage import get_notebook_storage, NotebookStorage
from src.utils.timestamps import iso_utc

router = APIRouter()
security = HTTPBearer()
_db_pool = None
_parser = NotebookParser()
_storage = None

# How many rows of each DataFrame the preview carries. The client draws the sample in
# a two-axis scroller, so this number is what bounds that box: raised from 5 on
# 2026-09-25, because the whole corpus Item 12 observes is 14 rows and cannot be
# seen through a five-row window. It is a response-size decision — these rows travel
# to the browser in full — so it stays a number rather than "every row".
_PREVIEW_SAMPLE_ROWS = 20


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ============================================================
# Preview endpoint
# ============================================================

@router.post("/preview")
async def preview_notebook(
    file: UploadFile = File(...),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    req: Request = None,
):
    """Parse a notebook file and return a preview of its contents."""
    user_id = await get_user_id_from_token(credentials)
    language = req.headers.get("X-Language", "en") if req else "en"

    # Validate file type
    if not file.filename or not file.filename.endswith(".ipynb"):
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, NOTEBOOKS["notebooks.invalid_format_2"]),
        )

    # Read file
    raw_bytes = await file.read()

    # Parse
    result = _parser.parse(raw_bytes)
    if not result["valid"]:
        err = result.get("error") or NOTEBOOKS["notebooks.unknown_error"]
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, err, **result.get("error_params", {})),
        )

    # Build preview
    dataframes_info = []
    for i, df in enumerate(result["dataframes"]):
        dataframes_info.append({
            "index": i,
            "columns": list(df["columns"]),
            "rows": len(df["rows"]),
            "cols": len(df["columns"]),
            "sample": df["rows"][:_PREVIEW_SAMPLE_ROWS],
        })

    preview = {
        "valid": True,
        "metadata": result["metadata"],
        "dataframes": dataframes_info,
        "dataframe_count": len(dataframes_info),
        "markdown_preview": result["markdown_content"][:500] if result["markdown_content"] else "",
        "cell_count": len(result["cells"]),
        "file_size_kb": round(len(raw_bytes) / 1024, 1),
    }

    return preview


# ============================================================
# Import endpoint
# ============================================================

async def _check_example_user(user_id: str) -> bool:
    """Check if a user is an example user. Returns True if blocked."""
    try:
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT "isExampleUser" FROM "User" WHERE id = $1',
                user_id,
            )
        return row and row["isExampleUser"] is True
    except Exception:
        return False


@router.post("/import")
async def import_notebook(
    file: UploadFile = File(...),
    shared: bool = Form(False),
    create_dataset: bool = Form(False),
    storage_type: str = Form("postgresql"),
    connection_id: int = Form(0),
    create_database: bool = Form(False),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    req: Request = None,
):
    """Parse and import a notebook file. Supports workbench_data (PostgreSQL), external PostgreSQL, MySQL, MSSQL."""
    global _storage
    if _storage is None:
        _storage = get_notebook_storage()

    user_id = await get_user_id_from_token(credentials)
    language = req.headers.get("X-Language", "en") if req else "en"

    # G2: Example user guard
    if await _check_example_user(user_id):
        raise HTTPException(
            status_code=403,
            detail=await t(_db_pool, language, NOTEBOOKS["notebooks.example_blocked"]),
        )

    # Validate file type
    if not file.filename or not file.filename.endswith(".ipynb"):
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, NOTEBOOKS["notebooks.invalid_format_2"]),
        )

    # Read file
    raw_bytes = await file.read()

    # Parse
    result = _parser.parse(raw_bytes)
    if not result["valid"]:
        err = result.get("error") or NOTEBOOKS["notebooks.unknown_error"]
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, err, **result.get("error_params", {})),
        )

    if not result["dataframes"]:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, NOTEBOOKS["notebooks.no_dataframes"]),
        )

    # Generate unique import ID
    import_id = str(uuid.uuid4())

    # Resolve external connection details if needed. `postgresql` with no
    # connection_id targets the internal workbench_data database.
    conn_details = None
    if storage_type == "postgresql" and not connection_id:
        pass  # workbench_data — no external connection
    elif storage_type in ("postgresql", "mysql", "mssql"):
        if not connection_id:
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, NOTEBOOKS["notebooks.no_connection"]),
            )
        try:
            conn_details = await get_connection_row(connection_id, user_id, language)
        except HTTPException:
            raise
        if conn_details is None:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, DATASETS["database.connection_not_found"])
            )
        # Decrypt password (get_connection_row returns a mutable dict)
        conn_details["password"] = decrypt_field(conn_details["password"])
        # Permission check
        if not conn_details.get("canCreateTables"):
            raise HTTPException(
                status_code=403,
                detail=await t(_db_pool, language, NOTEBOOKS["notebooks.no_table_rights"]),
            )
        if create_database and not conn_details.get("canCreateDatabase"):
            raise HTTPException(
                status_code=403,
                detail=await t(_db_pool, language, NOTEBOOKS["notebooks.no_db_rights"]),
            )
        # Guard against importing into system databases
        if not create_database:
            db_name = conn_details.get("database", "")
            db_type = conn_details.get("type", storage_type)
            if NotebookStorage._is_system_db(db_name, db_type):
                raise HTTPException(
                    status_code=400,
                    detail=await t(_db_pool, language, NOTEBOOKS["notebooks.system_db_blocked"], db=db_name),
                )

    # Internal workbench_data imports don't use an external connection.
    if conn_details is None:
        connection_id = None

    # R3: Atomic import. The storage engine returns
    # {"success": False, "error": ...} rather than raising.
    storage_result = await _storage.import_notebook(
        import_id, result["dataframes"],
        storage_type=storage_type,
        conn_details=conn_details,
        create_database=create_database,
        db_pool=_db_pool,
        language=language,
    )

    if not storage_result["success"]:
        storage_error = storage_result.get("error")
        if storage_error is None:
            storage_error = await t(_db_pool, language, NOTEBOOKS["notebooks.unknown_error"])
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, NOTEBOOKS["notebooks.import_failed"], error=storage_error),
        )

    # Determine notebook group for sharing
    notebook_group = "00"
    if shared:
        try:
            async with _db_pool.acquire() as conn:
                ug = await conn.fetchrow(
                    'SELECT "userGroup" FROM "User" WHERE id = $1',
                    user_id,
                )
            if ug and ug["userGroup"]:
                notebook_group = ug["userGroup"]
        except Exception:
            pass

    # Store import record in PostgreSQL via asyncpg
    sanitised_json = _parser.get_sanitised_notebook_json(raw_bytes)
    notebook_content_json = json.loads(sanitised_json) if sanitised_json else {}

    try:
        async with _db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO "NotebookImport" (
                    id, "userId", "notebookName", "notebookContent",
                    status, "tablesCreated", "storageType",
                    "notebookGroup", "connectionId", "createDatabase", "isShared", "importedAt", metadata, "markdownContent"
                ) VALUES ($1, $2, $3, $4::jsonb, $5, $6, $7, $8, $9, $10, $11, $12, $13::jsonb, $14)
                """,
                import_id,
                user_id,
                file.filename or "untitled.ipynb",
                notebook_content_json,
                "success",
                [t["name"] for t in storage_result["tables"]],
                storage_type,
                notebook_group,
                connection_id,
                create_database,
                shared,
                datetime.now(timezone.utc),
                result["metadata"],
                result["markdown_content"][:10000] if result["markdown_content"] else None,
            )
    except Exception as e:
        # R3: Rollback storage if PostgreSQL record fails
        await _storage.delete_import(import_id, db_pool=_db_pool, language=language)
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, NOTEBOOKS["notebooks.import_failed"], error=str(e)),
        )

    # If create_dataset is true, auto-create one UserDataset per imported table.
    dataset_ids = []
    if create_dataset and storage_result["tables"]:
        base_name = result["metadata"].get("title")
        if base_name is None:
            base_name = file.filename or await t(_db_pool, language, NOTEBOOKS["notebooks.untitled"])
        base_name = base_name[:100]

        for idx, table_info in enumerate(storage_result["tables"], start=1):
            try:
                dataset_id = str(uuid.uuid4())
                dataset_name = f"{base_name} — Table {idx}"

                # Record where the data actually lives so the read path
                # (get_dataset_data / schema / describe) can locate it. Internal
                # workbench_data imports store the schema-qualified table name
                # (nb_<import_id>.df_N) plus the workbench_data database name;
                # external notebook imports (currently unreachable via the UI)
                # leave these NULL as before.
                table_name_val = None
                database_name_val = None
                if storage_type == "postgresql" and connection_id is None:
                    table_name_val = table_info["name"]
                    database_name_val = DATA_DB_NAME

                async with _db_pool.acquire() as conn:
                    await conn.execute(
                        """
                        INSERT INTO "UserDataset" (
                            id, name, "originalFileName", "filePath", "fileSize",
                            "datasetGroup", "isShared",
                            "sourceType", "storageType", "userId",
                            "databaseName", "tableName", "notebookImportId",
                            description, "createdAt", "updatedAt"
                        ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, $13, $14, $15, $16)
                        """,
                        dataset_id,
                        dataset_name,
                        file.filename or "untitled.ipynb",
                        f"{storage_type}://{table_info['name']}",
                        0,
                        notebook_group,
                        shared,
                        "notebook",
                        storage_type,
                        user_id,
                        database_name_val,
                        table_name_val,
                        import_id,
                        result.get("markdown_content", "")[:500] if result.get("markdown_content") else None,
                        datetime.now(timezone.utc),
                        datetime.now(timezone.utc),
                    )
                dataset_ids.append(dataset_id)
            except Exception as e:
                logger = __import__("logging").getLogger(__name__)
                logger.warning(f"Failed to create UserDataset for import {import_id}: {e}")

    return {
        "success": True,
        "import_id": import_id,
        "notebook_name": file.filename,
        "metadata": result["metadata"],
        "tables": storage_result["tables"],
        "table_count": len(storage_result["tables"]),
        "imported_at": iso_utc(datetime.now(timezone.utc)),
        "storage_type": storage_type,
        "dataset_ids": dataset_ids,
    }


# ============================================================
# List imports
# ============================================================

@router.get("/imports")
async def list_imports(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    req: Request = None,
):
    """List all notebook imports for the current user."""
    user_id = await get_user_id_from_token(credentials)
    language = req.headers.get("X-Language", "en") if req else "en"

    try:
        # Get user's group for the sharing filter (group '00' is an ordinary group)
        user_group = "00"
        async with _db_pool.acquire() as conn:
            ug = await conn.fetchrow(
                'SELECT "userGroup" FROM "User" WHERE id = $1',
                user_id,
            )
            if ug and ug["userGroup"]:
                user_group = ug["userGroup"]

        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, "notebookName", "importedAt", status,
                       "tablesCreated", "storageType", metadata, "notebookGroup", "isShared", "userId"
                FROM "NotebookImport"
                WHERE "userId" = $1 OR ("isShared" = true AND "notebookGroup" = $2)
                ORDER BY "importedAt" DESC
                """,
                user_id, user_group,
            )

        imports = []
        for row in rows:
            metadata = row["metadata"] or {}
            imports.append({
                "id": row["id"],
                "notebook_name": row["notebookName"],
                "imported_at": iso_utc(row["importedAt"]),
                "status": row["status"],
                "tables_created": row["tablesCreated"] or [],
                "storage_type": row["storageType"],
                "title": metadata.get("title", row["notebookName"]),
                "table_count": len(row["tablesCreated"]) if row["tablesCreated"] else 0,
                "notebook_group": row["notebookGroup"] or "00",
                "isShared": row["isShared"],
                "is_owner": row["userId"] == user_id,
            })

        return {"imports": imports}
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, NOTEBOOKS["notebooks.import_failed_2"], error=str(e)),
        )


# ============================================================
# Get import detail
# ============================================================

@router.get("/imports/{import_id}")
async def get_import(
    import_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    req: Request = None,
):
    """Get details of a specific notebook import."""
    user_id = await get_user_id_from_token(credentials)
    language = req.headers.get("X-Language", "en") if req else "en"

    try:
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT id, "notebookName", "importedAt", status,
                       "tablesCreated", "storageType", metadata, "markdownContent"
                FROM "NotebookImport"
                WHERE id = $1 AND "userId" = $2
                """,
                import_id, user_id,
            )

        if not row:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, NOTEBOOKS["notebooks.import_failed_3"]),
            )

        metadata = row["metadata"] or {}
        return {
            "id": row["id"],
            "notebook_name": row["notebookName"],
            "imported_at": iso_utc(row["importedAt"]),
            "status": row["status"],
            "tables_created": row["tablesCreated"] or [],
            "storage_type": row["storageType"],
            "metadata": metadata,
            "markdown_content": row["markdownContent"],
        }
    except HTTPException:
        raise
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, NOTEBOOKS["notebooks.import_failed_4"], error=str(e)),
        )


# ============================================================
# Share toggle (PATCH)
# ============================================================

@router.patch("/imports/{import_id}")
async def toggle_share(
    import_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
):
    """Toggle notebook sharing. Only the owner can modify."""
    user_id = await get_user_id_from_token(credentials)
    language = request.headers.get("X-Language", "en")

    # G2: Example user guard
    if await _check_example_user(user_id):
        raise HTTPException(
            status_code=403,
            detail=await t(_db_pool, language, NOTEBOOKS["notebooks.example_blocked_2"]),
        )

    body = await request.json()
    shared = body.get("shared", False)

    try:
        async with _db_pool.acquire() as conn:
            # Verify ownership
            row = await conn.fetchrow(
                'SELECT "userId" FROM "NotebookImport" WHERE id = $1',
                import_id,
            )
            if not row:
                raise HTTPException(
                    status_code=404,
                    detail=await t(_db_pool, language, NOTEBOOKS["notebooks.import_failed_3"]),
                )
            if row["userId"] != user_id:
                raise HTTPException(
                    status_code=403,
                    detail=await t(_db_pool, language, NOTEBOOKS["notebooks.share_error"]),
                )

            await conn.execute(
                'UPDATE "NotebookImport" SET "isShared" = $1 WHERE id = $2',
                shared, import_id,
            )

        return {"success": True, "isShared": shared}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, NOTEBOOKS["notebooks.share_error_2"], error=str(e)),
        )


# ============================================================
# Delete import
# ============================================================

@router.delete("/imports/{import_id}")
async def delete_import(
    import_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    req: Request = None,
):
    """Delete a notebook import and its stored tables."""
    global _storage
    if _storage is None:
        _storage = get_notebook_storage()

    user_id = await get_user_id_from_token(credentials)
    language = req.headers.get("X-Language", "en") if req else "en"

    # G2: Example user guard
    if await _check_example_user(user_id):
        raise HTTPException(
            status_code=403,
            detail=await t(_db_pool, language, NOTEBOOKS["notebooks.example_blocked_3"]),
        )

    # Verify ownership
    try:
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT id FROM "NotebookImport" WHERE id = $1 AND "userId" = $2',
                import_id, user_id,
            )
        if not row:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, NOTEBOOKS["notebooks.import_failed_3"]),
            )
    except HTTPException:
        raise

    # Fetch import record to get storage details
    storage_type = "postgresql"
    conn_id = None
    try:
        async with _db_pool.acquire() as conn:
            imp = await conn.fetchrow(
                'SELECT "storageType", "connectionId", "createDatabase" FROM "NotebookImport" WHERE id = $1',
                import_id,
            )
            if imp:
                storage_type = imp["storageType"] or "postgresql"
                conn_id = imp["connectionId"]
                create_db_flag = imp["createDatabase"] or False
    except Exception:
        pass

    # R3: Delete storage tables
    conn_details = None
    if storage_type in ("postgresql", "mysql", "mssql") and conn_id:
        try:
            conn_details = await get_connection_row(conn_id, user_id, language)
            if conn_details is not None:
                conn_details["password"] = decrypt_field(conn_details["password"])
        except Exception as e:
            logger = __import__("logging").getLogger(__name__)
            logger.warning(f"Failed to fetch connection details for import {import_id}: {e}")

    try:
        await _storage.delete_import(import_id, storage_type=storage_type, conn_details=conn_details, create_database=create_db_flag, db_pool=_db_pool, language=language)
    except Exception as e:
        logger = __import__("logging").getLogger(__name__)
        logger.warning(f"Failed to drop {storage_type} schema for import {import_id}: {e}")

    # Delete the import record — the ON DELETE CASCADE FK removes its datasets
    try:
        async with _db_pool.acquire() as conn:
            await conn.execute(
                'DELETE FROM "NotebookImport" WHERE id = $1',
                import_id,
            )
    except Exception as e:
        traceback.print_exc()
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, NOTEBOOKS["notebooks.delete_error"], error=str(e)),
        )

    return {"success": True}
