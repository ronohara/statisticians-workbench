"""
MSSQL schema extraction for dataset define wizard.
"""

import asyncio
import pymssql
from fastapi import HTTPException
from ..translations import DEFINE


async def get_schema(
    conn_details: dict,
    table_name: str,
    decrypted_password: str,
    _db_pool,
    language: str,
    t,
) -> dict:
    """Get schema and preview data for an MSSQL table."""
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
        try:
            cursor.execute(f"SELECT COUNT(*) AS cnt FROM [{table_name}]")
            row = cursor.fetchone()
            count_result = row["cnt"]
        except Exception as e:
            conn.close()
            error_msg = str(e)
            if "Invalid object name" in error_msg or "does not exist" in error_msg.lower():
                raise HTTPException(
                    status_code=404,
                    detail=await t(_db_pool, language, DEFINE["datasets.define.table_not_found"], table=table_name, database=conn_details['database'])
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=await t(_db_pool, language, DEFINE["datasets.define.table_access_failed"], table=table_name, error=error_msg)
                )
        try:
            cursor.execute(
                "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE "
                "FROM INFORMATION_SCHEMA.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                "ORDER BY ORDINAL_POSITION",
                (conn_details.get("schema", "dbo"), table_name)
            )
            columns_result = cursor.fetchall()
            schema = []
            for col in columns_result:
                schema.append({
                    "name": col["COLUMN_NAME"],
                    "type": col["DATA_TYPE"],
                    "nullable": col["IS_NULLABLE"] == "YES"
                })
            cursor.execute(f"SELECT TOP 10 * FROM [{table_name}]")
            preview_result = cursor.fetchall()
            preview_data = [dict(row) for row in preview_result]
            from . import json_serializable
            preview_data_serializable = [json_serializable(row) for row in preview_data]
            preview = {
                "columns": list(preview_data_serializable[0].keys()) if preview_data_serializable else [],
                "rows": [[row.get(col) for col in (preview_data_serializable[0].keys() if preview_data_serializable else [])] for row in preview_data_serializable]
            }
            conn.close()
            return {
                "schema": schema,
                "preview": preview,
                "row_count": count_result,
                "column_count": len(schema)
            }
        except HTTPException:
            conn.close()
            raise
        except Exception as e:
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DEFINE["datasets.define.preview_failed"], table=table_name, error=str(e))
            )
    except HTTPException:
        conn.close()
        raise
    except Exception as e:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DEFINE["datasets.define.verification_failed"], error=str(e))
        )


async def define_dataset(
    conn_details: dict,
    table_name: str,
    decrypted_password: str,
    _db_pool,
    language: str,
    t,
) -> tuple:
    """Define a dataset from an MSSQL table — test connection, count rows, preview data."""
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
    data_snapshot = "[]"
    preview_data_serializable = []
    try:
        cursor = conn.cursor(as_dict=True)
        try:
            cursor.execute("SELECT 1 AS test")
            row = cursor.fetchone()
            if row["test"] != 1:
                conn.close()
                raise HTTPException(
                    status_code=400,
                    detail=await t(_db_pool, language, DEFINE["datasets.define.connection_test_failed"])
                )
        except Exception as e:
            conn.close()
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DEFINE["datasets.define.database_connection_failed"], error=str(e))
            )
        try:
            cursor.execute(f"SELECT COUNT(*) AS cnt FROM [{table_name}]")
            row = cursor.fetchone()
            count_result = row["cnt"]
        except Exception as e:
            conn.close()
            error_msg = str(e)
            if "Invalid object name" in error_msg or "does not exist" in error_msg.lower():
                raise HTTPException(
                    status_code=404,
                    detail=await t(_db_pool, language, DEFINE["datasets.define.table_not_found"], table=table_name, database=conn_details['database'])
                )
            else:
                raise HTTPException(
                    status_code=400,
                    detail=await t(_db_pool, language, DEFINE["datasets.define.table_access_failed"], table=table_name, error=error_msg)
                )
        cursor.execute(f"SELECT TOP 10 * FROM [{table_name}]")
        preview_result = cursor.fetchall()
        preview_data = [dict(row) for row in preview_result]
        from . import json_serializable
        preview_data_serializable = [json_serializable(row) for row in preview_data]
        if preview_data_serializable and len(preview_data_serializable) > 0:
            columns = []
            for col_name, col_value in preview_data_serializable[0].items():
                col_type = type(col_value).__name__
                columns.append({
                    "name": col_name,
                    "dtype": col_type,
                    "nullable": True,
                    "is_numeric": col_type in ["int", "float", "long", "decimal"],
                    "is_categorical": col_type in ["str", "text"],
                    "is_datetime": col_type in ["datetime", "date", "time", "timestamp"] or "iso" in col_type
                })
        else:
            columns = []
        conn.close()
        data_snapshot = preview_data_serializable[:10] if preview_data_serializable else []
    except HTTPException:
        conn.close()
        raise
    except Exception as e:
        conn.close()
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DEFINE["datasets.define.verification_failed"], error=str(e))
        )

    return columns, data_snapshot, count_result
