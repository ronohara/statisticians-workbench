"""
PostgreSQL schema extraction for dataset define wizard.
"""

import asyncpg
from fastapi import HTTPException
from ..translations import DEFINE
from ...common.relations import columns_of_visible_relation


async def get_schema(
    conn_details: dict,
    table_name: str,
    decrypted_password: str,
    _db_pool,
    language: str,
    t,
) -> dict:
    """Get schema and preview data for a PostgreSQL table."""
    conn_str = (
        f"postgresql://{conn_details['username']}:{decrypted_password}"
        f"@{conn_details['host']}:{conn_details['port']}/{conn_details['database']}"
    )
    try:
        ext_conn = await asyncpg.connect(conn_str)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DEFINE["datasets.define.database_connection_failed"], error=str(e)),
        )

    try:
        try:
            count_result = await ext_conn.fetchval(f'SELECT COUNT(*) FROM "{table_name}"')
        except Exception as e:
            await ext_conn.close()
            error_msg = str(e)
            if "permission denied" in error_msg.lower():
                raise HTTPException(
                    status_code=403,
                    detail=await t(_db_pool, language, DEFINE["datasets.define.permission_denied"],
                        user=conn_details['username'], table=table_name),
                )
            elif "does not exist" in error_msg.lower():
                raise HTTPException(
                    status_code=404,
                    detail=await t(_db_pool, language, DEFINE["datasets.define.table_not_found"],
                        table=table_name, database=conn_details['database']),
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=await t(_db_pool, language, DEFINE["datasets.define.table_access_failed"],
                        table=table_name, error=error_msg),
                )

        try:
            columns_result = await ext_conn.fetch(
                columns_of_visible_relation("$1"),
                table_name,
            )
            schema = [
                {"name": col["column_name"], "type": col["data_type"],
                 "nullable": col["is_nullable"] == "YES"}
                for col in columns_result
            ]

            preview_result = await ext_conn.fetch(f'SELECT * FROM "{table_name}" LIMIT 10')
            preview_data = [dict(row) for row in preview_result]
            from . import json_serializable
            preview_data_serializable = [json_serializable(row) for row in preview_data]

            preview = {
                "columns": list(preview_data_serializable[0].keys()) if preview_data_serializable else [],
                "rows": [[row.get(col) for col in (preview_data_serializable[0].keys() if preview_data_serializable else [])]
                         for row in preview_data_serializable],
            }

            await ext_conn.close()
            return {
                "schema": schema,
                "preview": preview,
                "row_count": count_result,
                "column_count": len(schema),
            }
        except HTTPException:
            await ext_conn.close()
            raise
        except Exception as e:
            await ext_conn.close()
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DEFINE["datasets.define.preview_failed"],
                    table=table_name, error=str(e)),
            )
    except HTTPException:
        await ext_conn.close()
        raise
    except Exception as e:
        await ext_conn.close()
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DEFINE["datasets.define.verification_failed"], error=str(e)),
        )


async def define_dataset(
    conn_details: dict,
    table_name: str,
    decrypted_password: str,
    _db_pool,
    language: str,
    t,
) -> tuple:
    """Collect preview data and column metadata for dataset definition."""
    conn_str = (
        f"postgresql://{conn_details['username']}:{decrypted_password}"
        f"@{conn_details['host']}:{conn_details['port']}/{conn_details['database']}"
    )
    try:
        ext_conn = await asyncpg.connect(conn_str)
    except Exception as e:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DEFINE["datasets.define.database_connection_failed"], error=str(e)),
        )

    try:
        try:
            count_result = await ext_conn.fetchval(f'SELECT COUNT(*) FROM "{table_name}"')
        except Exception as e:
            await ext_conn.close()
            error_msg = str(e)
            if "permission denied" in error_msg.lower():
                raise HTTPException(
                    status_code=403,
                    detail=await t(_db_pool, language, DEFINE["datasets.define.permission_denied"],
                        user=conn_details['username'], table=table_name),
                )
            elif "does not exist" in error_msg.lower():
                raise HTTPException(
                    status_code=404,
                    detail=await t(_db_pool, language, DEFINE["datasets.define.table_not_found"],
                        table=table_name, database=conn_details['database']),
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=await t(_db_pool, language, DEFINE["datasets.define.table_access_failed"],
                        table=table_name, error=error_msg),
                )

        try:
            preview_result = await ext_conn.fetch(f'SELECT * FROM "{table_name}" LIMIT 10')
            preview_data = [dict(row) for row in preview_result]
            from . import json_serializable
            preview_data_serializable = [json_serializable(row) for row in preview_data]

            columns = []
            if preview_data_serializable:
                for col_name, col_value in preview_data_serializable[0].items():
                    col_type = type(col_value).__name__
                    columns.append({
                        "name": col_name,
                        "dtype": col_type,
                        "nullable": True,
                        "is_numeric": col_type in ["int", "float", "long", "decimal"],
                        "is_categorical": col_type in ["str", "text"],
                        "is_datetime": col_type in ["datetime", "date", "time", "timestamp"] or "iso" in col_type,
                    })

            data_snapshot = preview_data_serializable[:10] if preview_data_serializable else []

            await ext_conn.close()
            return columns, data_snapshot, count_result
        except HTTPException:
            await ext_conn.close()
            raise
        except Exception as e:
            await ext_conn.close()
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DEFINE["datasets.define.verification_failed"], error=str(e)),
            )
    except HTTPException:
        await ext_conn.close()
        raise
    except Exception as e:
        await ext_conn.close()
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DEFINE["datasets.define.verification_failed"], error=str(e)),
        )
