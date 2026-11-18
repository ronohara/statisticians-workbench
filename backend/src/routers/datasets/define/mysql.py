"""
MySQL schema extraction and dataset definition for the define wizard.
"""


import aiomysql
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
    """Get schema and preview data for a MySQL table."""
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
            detail=await t(_db_pool, language, DEFINE["datasets.define.database_connection_failed"],
                error=str(e),
            ),
        )

    try:
        async with mysql_conn.cursor(aiomysql.DictCursor) as cur:
            try:
                await cur.execute(f"SELECT COUNT(*) AS cnt FROM `{table_name}`")
                row = await cur.fetchone()
                count_result = row["cnt"]
            except Exception as e:
                mysql_conn.close()
                error_msg = str(e)
                if "doesn't exist" in error_msg.lower() or "does not exist" in error_msg.lower():
                    raise HTTPException(
                        status_code=404,
                        detail=await t(_db_pool, language, DEFINE["datasets.define.table_not_found"],
                            table=table_name,
                            database=conn_details["database"],
                        ),
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, DEFINE["datasets.define.table_access_failed"],
                            table=table_name,
                            error=error_msg,
                        ),
                    )

            await cur.execute(
                "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE "
                "FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                "ORDER BY ORDINAL_POSITION",
                (conn_details["database"], table_name),
            )
            columns_result = await cur.fetchall()

            schema = []
            for col in columns_result:
                schema.append({
                    "name": col["COLUMN_NAME"],
                    "type": col["DATA_TYPE"],
                    "nullable": col["IS_NULLABLE"] == "YES",
                })

            await cur.execute(f"SELECT * FROM `{table_name}` LIMIT 10")
            preview_result = await cur.fetchall()

            preview_data = [dict(row) for row in preview_result]
            from . import json_serializable
            preview_data_serializable = [json_serializable(row) for row in preview_data]

            preview = {
                "columns": list(preview_data_serializable[0].keys()) if preview_data_serializable else [],
                "rows": [
                    [row.get(col) for col in (preview_data_serializable[0].keys() if preview_data_serializable else [])]
                    for row in preview_data_serializable
                ],
            }

            mysql_conn.close()

            return {
                "schema": schema,
                "preview": preview,
                "row_count": count_result,
                "column_count": len(schema),
            }
    except HTTPException:
        mysql_conn.close()
        raise
    except Exception as e:
        mysql_conn.close()
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DEFINE["datasets.define.verification_failed"],
                error=str(e),
            ),
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
            detail=await t(_db_pool, language, DEFINE["datasets.define.database_connection_failed"],
                error=str(e),
            ),
        )

    data_snapshot = "[]"
    preview_data_serializable = []
    try:
        async with mysql_conn.cursor(aiomysql.DictCursor) as cur:
            try:
                await cur.execute("SELECT 1 AS test")
                row = await cur.fetchone()
                if row["test"] != 1:
                    mysql_conn.close()
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, DEFINE["datasets.define.connection_test_failed"],
                        ),
                    )
            except HTTPException:
                raise
            except Exception as e:
                mysql_conn.close()
                raise HTTPException(
                    status_code=400,
                    detail=await t(_db_pool, language, DEFINE["datasets.define.database_connection_failed"],
                        error=str(e),
                    ),
                )

            try:
                await cur.execute(f"SELECT COUNT(*) AS cnt FROM `{table_name}`")
                row = await cur.fetchone()
                count_result = row["cnt"]
            except Exception as e:
                mysql_conn.close()
                error_msg = str(e)
                if "doesn't exist" in error_msg.lower() or "does not exist" in error_msg.lower():
                    raise HTTPException(
                        status_code=404,
                        detail=await t(_db_pool, language, DEFINE["datasets.define.table_not_found"],
                            table=table_name,
                            database=conn_details["database"],
                        ),
                    )
                else:
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, DEFINE["datasets.define.table_access_failed"],
                            table=table_name,
                            error=error_msg,
                        ),
                    )

            await cur.execute(f"SELECT * FROM `{table_name}` LIMIT 10")
            preview_result = await cur.fetchall()
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
                        "is_datetime": col_type in ["datetime", "date", "time", "timestamp"] or "iso" in col_type,
                    })
            else:
                columns = []

            mysql_conn.close()

            data_snapshot = preview_data_serializable[:10] if preview_data_serializable else []

    except HTTPException:
        mysql_conn.close()
        raise
    except Exception as e:
        mysql_conn.close()
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DEFINE["datasets.define.verification_failed"],
                error=str(e),
            ),
        )

    return columns, data_snapshot, count_result
