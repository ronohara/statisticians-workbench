"""
Access (Jet/ODBC) schema extraction for dataset define wizard.
"""

import asyncio
import psycopg2
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
    """Get schema and preview data for an Access/Jet-Server table."""
    import psycopg2

    def _connect():
        return psycopg2.connect(
            host=conn_details["host"],
            port=conn_details["port"],
            user=conn_details["username"],
            password=decrypted_password,
            dbname=conn_details["database"],
            connect_timeout=15,
        )

    pg_conn = await asyncio.to_thread(_connect)
    try:
        cur = pg_conn.cursor()
        # Jet SQL: COUNT(*) returns 0 rows (not 1 row with 0). Handle gracefully.
        cur.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        row = cur.fetchone()
        count_result = row[0] if row else 0
        cur.execute(f"SELECT TOP 1 * FROM [{table_name}] WHERE 1=0")
        columns_result = [(d[0], d[1]) for d in (cur.description or [])]
        schema = [
            {"name": name, "type": "text" if tc == 25 else "int4" if tc == 23 else "numeric",
             "nullable": True}
            for name, tc in columns_result
        ]
        cur.execute(f"SELECT TOP 10 * FROM [{table_name}]")
        rows = cur.fetchall()
        col_names = [d[0] for d in (cur.description or [])]
        preview = {
            "columns": col_names,
            "rows": [list(r) for r in rows]
        }
        cur.close()
        pg_conn.close()
        return {
            "schema": schema,
            "preview": preview,
            "row_count": count_result,
            "column_count": len(schema)
        }
    except Exception as e:
        pg_conn.close()
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DEFINE["datasets.define.preview_failed"], table=table_name, error=str(e))
        )


async def define_dataset(
    conn_details: dict,
    table_name: str,
    decrypted_password: str,
    _db_pool,
    language: str,
    t,
) -> tuple:
    """Collect preview data and column metadata for dataset definition via Access/Jet-Server."""
    import psycopg2

    def _connect():
        return psycopg2.connect(
            host=conn_details["host"],
            port=conn_details["port"],
            user=conn_details["username"],
            password=decrypted_password,
            dbname=conn_details["database"],
            connect_timeout=15,
        )

    pg_conn = await asyncio.to_thread(_connect)
    try:
        cur = pg_conn.cursor()
        cur.execute(f"SELECT COUNT(*) FROM [{table_name}]")
        row = cur.fetchone()
        count_result = row[0] if row else 0
        cur.execute(f"SELECT TOP 10 * FROM [{table_name}]")
        rows = cur.fetchall()
        col_names = [d[0] for d in (cur.description or [])]
        preview_data = [dict(zip(col_names, row)) for row in rows]
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
        cur.close()
        pg_conn.close()
        data_snapshot = preview_data_serializable[:10] if preview_data_serializable else []
    except HTTPException:
        pg_conn.close()
        raise
    except Exception as e:
        pg_conn.close()
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DEFINE["datasets.define.verification_failed"], error=str(e))
        )

    return columns, data_snapshot, count_result
