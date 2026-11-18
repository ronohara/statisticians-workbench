"""
Dataset data-fetch layer — high-level "load a dataset's rows" helper.

Bridges to datasets.virtual (materialize_virtual_dataset) for the virtual source
type, and to data_access for external-connection row helpers. Kept separate from
data_access so the dependency graph stays acyclic.
"""
from typing import Tuple, List, Dict, Any
import asyncpg

from src.utils.translation import t
from src.utils.encryption import decrypt_field
from src.routers.common.translations import (
    error_connection_decryption_failed,
    error_connection_failed,
    error_connection_query_failed,
    error_connection_type_not_supported_3,
    error_dataset_load_failed_2,
    error_dataset_load_failed_3,
    error_dataset_load_failed_4,
    error_dataset_not_found_2,
    error_dataset_table_missing,
    error_dataset_unknown_source,
    error_define_connection_not_found,
)
from src.routers.datasets.crud import get_connection_row
from src.routers.datasets.data_access import _asyncpg_columns
from src.routers.datasets.virtual import materialize_virtual_dataset
from src.postgres_data_manager import (
    get_full_table,
    get_table_preview,
    get_table_schema,
    table_exists,
)

async def get_dataset_data(
    db_pool: asyncpg.Pool,
    user_id: str,
    dataset_id: str,
    language: str = "en",
    limit: int = 0
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Fetch dataset data from PostgreSQL (upload/notebook) or an external database.

    Args:
        db_pool: Database connection pool
        user_id: The user ID
        dataset_id: The dataset ID to fetch
        language: User's language for error messages
        limit: If > 0, fetch only this many rows (for preview/sampling)

    Returns:
        ``(columns, rows)`` — a list of column-name strings and a list of
        plain row dicts (no pandas).

    Raises:
        ValueError: If dataset not found or data cannot be loaded
    """
    # Get dataset information
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT "sourceType", "storageType", "sourceConnectionId", "databaseName", "tableName", "virtualSql"
            FROM "UserDataset"
            WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (SELECT "userGroup" FROM "User" WHERE id = $2)))
            """,
            dataset_id, user_id
        )

    if row is None:
        raise ValueError(
            await t(db_pool, language, error_dataset_not_found_2,
                id=dataset_id
            )
        )

    source_type = row["sourceType"]
    storage_type = row["storageType"]
    source_connection_id = row["sourceConnectionId"]
    table_name = row["tableName"]

    if source_type in ("upload", "notebook") and storage_type == "postgresql":
        # Get data from workbench_data
        try:
            if not await table_exists(table_name):
                raise ValueError(
                    await t(db_pool, language, error_dataset_table_missing,
                        table=table_name
                    )
                )
            if limit > 0:
                rows = await get_table_preview(table_name, limit)
            else:
                rows = await get_full_table(table_name)
            if rows:
                return list(rows[0].keys()), rows
            schema = await get_table_schema(table_name)
            return [c["name"] for c in schema], []
        except Exception as e:
            raise ValueError(
                await t(db_pool, language, error_dataset_load_failed_2,
                    error=str(e)
                )
            )
    
    elif source_type in ["table", "view"] and source_connection_id:
        # Get data from external database connection
        return await _get_external_dataset_data(
            db_pool, user_id, dataset_id, row, language
        )
    
    elif source_type == "virtual":
        # Materialise the virtual dataset into PostgreSQL and read its table.
        virtual_sql_raw = row.get("virtualSql")
        if not virtual_sql_raw:
            raise ValueError(
                await t(db_pool, language, error_dataset_load_failed_3,
                    id=dataset_id
                )
            )
        import json as _json
        virtual_sql = _json.loads(virtual_sql_raw) if isinstance(virtual_sql_raw, str) else virtual_sql_raw
        try:
            table_name, columns, _row_count = await materialize_virtual_dataset(
                dataset_id, virtual_sql, user_id, db_pool, language
            )
            rows = await get_table_preview(table_name, limit) if limit > 0 else await get_full_table(table_name)
            return columns, rows
        except Exception as e:
            raise ValueError(
                await t(db_pool, language, error_dataset_load_failed_4,
                    id=dataset_id,
                    error=str(e)
                )
            )
    
    elif source_type in ("postgresql", "mysql", "mssql", "access"):
        return await _get_external_dataset_data(db_pool, user_id, dataset_id, row, language)

    else:
        raise ValueError(
            await t(db_pool, language, error_dataset_unknown_source,
                source_type=source_type
            )
        )




async def _get_external_dataset_data(
    db_pool: asyncpg.Pool,
    user_id: str,
    dataset_id: str,
    dataset_row: Dict[str, Any],
    language: str
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Fetch data from an external database connection (table or view).
    """
    source_connection_id = dataset_row["sourceConnectionId"]
    table_name = dataset_row["tableName"]
    database_name = dataset_row["databaseName"]
    
    # Get connection details
    conn_details = await get_connection_row(source_connection_id, user_id, language)
    if conn_details is None:
        raise ValueError(
            await t(db_pool, language, error_define_connection_not_found
            )
        )

    # Decrypt password
    try:
        decrypted_password = decrypt_field(conn_details["password"])
    except Exception as e:
        raise ValueError(
            await t(db_pool, language, error_connection_decryption_failed,
                error=str(e)
            )
        )
    
    # Connect to external database
    if conn_details["type"] == "postgresql":
        conn_str = (
            f"postgresql://{conn_details['username']}:{decrypted_password}"
            f"@{conn_details['host']}:{conn_details['port']}/{conn_details['database']}"
        )
        ext_conn = await asyncpg.connect(conn_str)
        try:
            query = f'SELECT * FROM "{table_name}"'
            result = await ext_conn.fetch(query)
            rows = [dict(row) for row in result]
            columns = list(rows[0].keys()) if rows else await _asyncpg_columns(ext_conn, query, result)
            await ext_conn.close()
            return columns, rows
        except Exception as e:
            await ext_conn.close()
            raise ValueError(
                await t(db_pool, language, error_connection_query_failed,
                    table=table_name,
                    error=str(e)
                )
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
            raise ValueError(
                await t(db_pool, language, error_connection_failed,
                    error=str(e)
                )
            )
        try:
            async with mysql_conn.cursor(aiomysql.DictCursor) as cur:
                await cur.execute(f"SELECT * FROM `{table_name}`")
                result = await cur.fetchall()
                description = cur.description
            rows = result
            columns = list(rows[0].keys()) if rows else [d[0] for d in (description or [])]
            mysql_conn.close()
            return columns, rows
        except Exception as e:
            mysql_conn.close()
            raise ValueError(
                await t(db_pool, language, error_connection_query_failed,
                    table=table_name,
                    error=str(e)
                )
            )
    elif conn_details["type"] == "mssql":
        import pymssql
        import asyncio
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
            cursor.execute(f"SELECT * FROM [{table_name}]")
            rows = cursor.fetchall()
            columns = list(rows[0].keys()) if rows else [d[0] for d in (cursor.description or [])]
        finally:
            conn.close()
        return columns, rows
    elif conn_details["type"] == "access":
        import psycopg2
        import asyncio
        def _connect():
            return psycopg2.connect(
                host=conn_details["host"],
                port=conn_details["port"],
                user=conn_details["username"],
                password=decrypted_password,
                dbname=conn_details["database"],
                connect_timeout=15,
            )
        conn = await asyncio.to_thread(_connect)
        try:
            cursor = conn.cursor()
            # Jet/DAO is single-threaded — keep row count small for Access
            cursor.execute(f"SELECT TOP 200 * FROM [{table_name}]")
            rows = cursor.fetchall()
            columns = [d[0] for d in (cursor.description or [])]
        finally:
            conn.close()
        return columns, rows
    else:
        raise ValueError(
            await t(db_pool, language, error_connection_type_not_supported_3,
                type=conn_details["type"]
            )
        )
