"""
Auto-create datasets for a database connection.

POST /api/datasets/auto-create

Accepts a saved database connection ID and auto-creates UserDataset
records for all discovered tables (and optionally views). Supports PG,
MySQL, MSSQL, and Access — each using the appropriate driver from the
existing define/schema modules.
"""

import uuid
import logging
from fastapi import APIRouter, HTTPException, Request, Depends
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.utils.translation import t
from src.utils.encryption import decrypt_field_or_null
from src.routers.common.feature_gate import require_db_feature
from src.routers.common.relations import VISIBLE_RELATIONS
from .translations import DATASETS
from .crud import get_user_id_from_token, get_current_language

router = APIRouter()
security = HTTPBearer()
_pool = None


def set_db_pool(pool):
    global _pool
    _pool = pool


@router.post("/auto-create")
async def auto_create_datasets(
    request: Request,
    body: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Auto-create datasets for a connection."""
    if _pool is None:
        raise HTTPException(status_code=500, detail=await t(_pool, language, DATASETS["database.pool_not_initialized"]))

    connection_id = body.get("connectionId")
    auto_tables = body.get("autoCreateTables", True)
    auto_views = body.get("autoCreateViews", True)

    if not connection_id:
        raise HTTPException(status_code=400, detail=await t(_pool, language, DATASETS["datasets.auto_create.connection_id_required"]))

    user_id = await get_user_id_from_token(credentials)

    async with _pool.acquire() as conn:
        # The connection must be one the caller can *see* — their own, or one shared to
        # their group; that is the predicate every connection read uses. Gap B: the
        # caller's identity is never replaced by the row's owner, so the datasets
        # created below are the caller's own (Decision 3's ownership rule).
        row = await conn.fetchrow(
            """SELECT "connectionId", name, type, database, host,
                      port, username, password
               FROM "UserDatabaseConnection"
               WHERE "connectionId" = $1 AND ("userId" = $2 OR ("isShared" = true AND "dbConnectionGroup" IN (
                   SELECT "userGroup" FROM "User" WHERE id = $2
               )))""",
            int(connection_id), user_id,
        )
        if not row:
            raise HTTPException(status_code=404, detail=await t(_pool, language, DATASETS["datasets.auto_create.connection_not_found"]))

        conn_type = row["type"]
        await require_db_feature(_pool, conn_type, language)
        conn_name = row["name"]
        database = row["database"]
        host = row["host"]
        port = row["port"]
        username = row["username"]
        password = row["password"]  # encrypted
        decrypted_password = decrypt_field_or_null(password)

        table_names = []
        warnings = []

        if auto_tables:
            try:
                tables = await _discover_tables(conn, conn_type, host, port, database, username, decrypted_password, "table")
                table_names.extend((t, False) for t in tables)
            except Exception as e:
                logging.warning("Table discovery failed for connection %d: %s", connection_id, e)
                warnings.append(f"Table discovery failed: {e}")

        if auto_views:
            try:
                views = await _discover_tables(conn, conn_type, host, port, database, username, decrypted_password, "view")
                table_names.extend((t, True) for t in views)
            except Exception as e:
                logging.warning("View discovery failed for connection %d: %s", connection_id, e)
                warnings.append(f"View discovery failed: {e}")

        # If discovery was requested but produced no results, fail hard
        if (auto_tables or auto_views) and len(table_names) == 0:
            detail = await t(_pool, language, DATASETS["datasets.auto_create.no_tables_discovered"])
            if warnings:
                detail += " " + warnings[0]
            raise HTTPException(status_code=502, detail=detail)

        created = 0
        async with conn.transaction():
            for tbl_name, is_view in table_names:
                existing = await conn.fetchrow(
                    """SELECT id FROM "UserDataset"
                       WHERE "userId" = $1 AND "sourceConnectionId" = $2
                       AND "tableName" = $3""",
                    user_id, int(connection_id), tbl_name,
                )
                if existing:
                    continue

                await conn.execute(
                    """INSERT INTO "UserDataset"
                       (id, "userId", name, "sourceType", "storageType",
                        "sourceConnectionId", "databaseName", "tableName",
                        "isView", "datasetGroup", status, "createdAt", "updatedAt")
                       VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, $10, 'active', NOW(), NOW())""",
                    str(uuid.uuid4()), user_id, tbl_name, conn_type, conn_type,
                    int(connection_id), database, tbl_name, is_view, conn_name,
                )
                created += 1

    return {"message": await t(_pool, language, DATASETS["datasets.auto_create.created"]), "datasetsCreated": created, "warnings": warnings}


async def _discover_tables(conn, conn_type: str, host: str, port: int,
                           database: str, username: str, password: str,
                           kind: str) -> list[str]:
    """Discover tables (kind='table') or views (kind='view') for a connection."""

    table_type = "BASE TABLE" if kind == "table" else "VIEW"

    if conn_type == "postgresql":
        import asyncpg
        try:
            c = await asyncpg.connect(
                host=host, port=port or 5432, database=database,
                user=username, password=password, timeout=10,
            )
            rows = await c.fetch(VISIBLE_RELATIONS)
            await c.close()
            return [r["table_name"] for r in rows if r["table_type"] == table_type]
        except Exception as e:
            logging.warning("PG discovery failed: %s", e)
            return []

    if conn_type == "mysql":
        import aiomysql
        try:
            c = await aiomysql.connect(
                host=host, port=port or 3306, db=database,
                user=username, password=password,
            )
            cursor = await c.cursor()
            await cursor.execute(
                "SELECT TABLE_NAME FROM information_schema.tables "
                "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE = %s "
                "ORDER BY TABLE_NAME",
                (database, table_type),
            )
            rows = await cursor.fetchall()
            c.close()
            return [r[0] for r in rows]
        except Exception as e:
            logging.warning("MySQL discovery failed: %s", e)
            return []

    if conn_type == "mssql":
        import pymssql
        try:
            c = pymssql.connect(
                server=host, port=port or 1433, database=database,
                user=username, password=password,
                login_timeout=10,
            )
            cursor = c.cursor()
            cursor.execute(
                "SELECT TABLE_NAME FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = %s ORDER BY TABLE_NAME",
                (table_type,),
            )
            rows = cursor.fetchall()
            c.close()
            return [r[0] for r in rows]
        except Exception as e:
            logging.warning("MSSQL discovery failed: %s", e)
            return []

    if conn_type == "access":
        import psycopg2
        try:
            c = psycopg2.connect(
                host=host, port=port or 9432, user=username,
                password=password, dbname=database,
                connect_timeout=15,
            )
            cur = c.cursor()
            cur.execute(VISIBLE_RELATIONS)
            rows = cur.fetchall()
            cur.close()
            c.close()
            # Keep the kind the caller asked for, and drop MSys system tables.
            return [
                name
                for _schema, name, kind in rows
                if kind == table_type and not name.startswith("MSys")
            ]
        except Exception as e:
            logging.warning("Access discovery failed: %s", e)
            return []

    return []
