"""
Generic table browser endpoint — works for PostgreSQL, MySQL, MSSQL, and Access.
Provides table listing, column info, and row preview for any saved connection.
"""

import asyncio
import logging
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from typing import Optional

from src.utils.translation import t
from src.routers.common.translations import DATABASE
from src.routers.common.relations import (
    VISIBLE_RELATIONS,
    columns_of_visible_relation,
    relation_kind,
)
from .translations import DATASETS
from src.routers.datasets.crud import (
    get_user_id_from_token,
    get_current_language,
    get_connection_row,
)
from src.utils.encryption import decrypt_field

logger = logging.getLogger(__name__)

router = APIRouter()
security = HTTPBearer()

# ── column kinds ────────────────────────────────────────────
#
# Two booleans the source tree renders as a small glyph beside a column, so an
# assistant can point at "a numeric amount and a date" over rows the user can
# see (design §9.4.3). They annotate, never filter.
#
# Explicit member lists rather than substring tests. A substring test on the
# upper-cased type — the shape `fetch_dataset_overview` uses — reports every
# INTERVAL and POINT column as numeric, because both contain "INT". The lists
# below are the native type names the four drivers actually return, so a column
# is marked only when its type is one of them.
_NUMERIC_TYPES = frozenset({
    "int", "integer", "bigint", "smallint", "tinyint", "mediumint", "int2", "int4", "int8",
    "integer unsigned", "bigint unsigned", "smallint unsigned", "tinyint unsigned",
    "decimal", "numeric", "dec", "fixed", "real", "float", "float4", "float8",
    "double", "double precision", "money", "smallmoney",
    "serial", "bigserial", "smallserial", "number",
})
_DATETIME_TYPES = frozenset({
    "date", "time", "timetz", "timestamptz", "timestamp", "datetime", "datetime2",
    "smalldatetime", "datetimeoffset",
    "timestamp without time zone", "timestamp with time zone",
    "time without time zone", "time with time zone",
})

#: The text family, as every driver here spells it. A column of one of these
#: types is a label or a grouping variable, not a measurement.
#:
#: The set was missing until 2026-11-11: `column_kind` returned only `is_numeric`
#: and `is_datetime`, so every caller that read `is_categorical` off these records
#: got a default. `virtual_dataset_schema_from_definition` read it with a `False`
#: default, which meant **no column of a connection-backed virtual dataset was ever
#: categorical** — a fact hidden by how plausible the empty answer looked. Measured
#: on the recipe concierge: a `factorColumn` chip row could not be built for any
#: such dataset, and the column suggestion for the numeric fields came back empty
#: for the same reason, silently.
_CATEGORICAL_TYPES = frozenset({
    "char", "character", "character varying", "varchar", "varchar2", "nvarchar",
    "nchar", "bpchar", "text", "tinytext", "mediumtext", "longtext", "clob",
    "nclob", "ntext", "string", "enum", "uuid",
    "national character varying", "national char", "national character",
})


def column_kind(dtype: Optional[str]) -> dict:
    """The three kind flags for a driver-native type name.

    Returns every key always, so a caller can merge the result into a column
    record without testing for absence — and so a caller reading only one of them
    is reading a real answer rather than a default it supplied itself.
    """
    kind = (dtype or "").strip().lower()
    return {
        "is_numeric": kind in _NUMERIC_TYPES,
        "is_categorical": kind in _CATEGORICAL_TYPES,
        "is_datetime": kind in _DATETIME_TYPES,
    }

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


async def list_connection_tables(
    db_pool,
    user_id: str,
    language: str,
    connection_id: int,
) -> list:
    """List table names for a connection.

    Shared by ``GET /browse/{connection_id}`` and the AI ``get_tables`` tool."""
    conn_details = await get_connection_row(connection_id, user_id, language)
    if conn_details is None:
        raise HTTPException(
            status_code=404,
            detail=await t(db_pool, language, DATASETS["database.connection_not_found"])
        )
    password = conn_details["password"]
    try:
        password = decrypt_field(password)
    except Exception:
        pass

    db_type = conn_details["type"].lower()
    if db_type in ("postgresql", "postgres"):
        return await _discover_pg(conn_details, password)
    if db_type == "mysql":
        return await _discover_mysql(conn_details, password)
    if db_type == "mssql":
        return await _discover_mssql(conn_details, password)
    if db_type == "access":
        return await _discover_access(conn_details, password)
    return []


@router.get("/browse/{connection_id}")
async def browse_tables(
    connection_id: int,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """List all tables (and optionally views) for a database connection."""
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATABASE["pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials)
    try:
        tables = await list_connection_tables(_db_pool, user_id, language, connection_id)
    except HTTPException:
        raise
    except Exception as e:
        logger.warning("Table discovery failed for connection %d: %s", connection_id, e)
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["datasets.browse.discover_failed"], error=str(e)))

    return {"tables": tables}


#: The default when a caller supplies no deadline. The same number as
#: GlobalSettings.defaultConnectTimeoutSeconds, so it is not a second policy —
#: it is what an unreadable settings row would have given.
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10


async def list_table_columns(
    db_pool,
    user_id: str,
    language: str,
    connection_id: int,
    table_name: str,
    connect_timeout: int | None = None,
) -> list:
    """List columns for a table.

    Shared by ``GET /browse/{connection_id}/{table_name}/columns`` and the AI
    ``get_columns`` tool."""
    conn_details = await get_connection_row(connection_id, user_id, language)
    if conn_details is None:
        raise HTTPException(
            status_code=404,
            detail=await t(db_pool, language, DATASETS["database.connection_not_found"])
        )
    password = conn_details["password"]
    try:
        password = decrypt_field(password)
    except Exception:
        pass

    deadline = connect_timeout or DEFAULT_CONNECT_TIMEOUT_SECONDS
    db_type = conn_details["type"].lower()
    if db_type in ("postgresql", "postgres"):
        return await _columns_pg(conn_details, password, table_name, deadline)
    if db_type == "mysql":
        return await _columns_mysql(conn_details, password, table_name, deadline)
    if db_type == "mssql":
        return await _columns_mssql(conn_details, password, table_name, deadline)
    if db_type == "access":
        return await _columns_access(conn_details, password, table_name, deadline)
    return []


@router.get("/browse/{connection_id}/{table_name}/columns")
async def browse_columns(
    connection_id: int,
    table_name: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """List columns for a specific table."""
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATABASE["pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials)
    try:
        columns = await list_table_columns(_db_pool, user_id, language, connection_id, table_name)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["datasets.browse.columns_failed"], error=str(e)))

    return {"columns": columns}


@router.get("/browse/{connection_id}/{table_name}/preview")
async def browse_preview(
    connection_id: int,
    table_name: str,
    limit: int = Query(100, ge=1, le=1000),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Preview rows from a specific table."""
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATABASE["pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials)

    conn_details = await get_connection_row(connection_id, user_id, language)
    if conn_details is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, DATASETS["database.connection_not_found"])
        )
    password = conn_details["password"]
    try:
        password = decrypt_field(password)
    except Exception:
        pass

    db_type = conn_details["type"].lower()
    rows = []
    col_names = []

    try:
        if db_type in ("postgresql", "postgres"):
            rows, col_names = await _preview_pg(conn_details, password, table_name, limit)
        elif db_type == "mysql":
            rows, col_names = await _preview_mysql(conn_details, password, table_name, limit)
        elif db_type == "mssql":
            rows, col_names = await _preview_mssql(conn_details, password, table_name, limit)
        elif db_type == "access":
            rows, col_names = await _preview_access(conn_details, password, table_name, limit)
    except Exception as e:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["datasets.browse.preview_failed"], error=str(e)))

    return {"rows": rows, "columns": col_names}


# ── PostgreSQL ──────────────────────────────────────────────────────

async def _discover_pg(cd: dict, password: str) -> list:
    import asyncpg
    c = await asyncpg.connect(
        host=cd["host"], port=cd["port"] or 5432, database=cd["database"],
        user=cd["username"], password=password, timeout=10,
    )
    # Relations this session can name by bare name — see `common/relations.py`. Views are
    # included: the client's own message promises "tables or views".
    rows = await c.fetch(VISIBLE_RELATIONS)
    await c.close()
    return [{"name": r["table_name"], "type": relation_kind(r["table_type"])} for r in rows]


async def _columns_pg(cd: dict, password: str, table: str, timeout: int = DEFAULT_CONNECT_TIMEOUT_SECONDS) -> list:
    import asyncpg
    c = await asyncpg.connect(
        host=cd["host"], port=cd["port"] or 5432, database=cd["database"],
        user=cd["username"], password=password, timeout=timeout,
    )
    rows = await c.fetch(columns_of_visible_relation("$1"), table)
    await c.close()
    return [
        {"name": r["column_name"], "type": r["data_type"], "nullable": r["is_nullable"] == "YES",
         **column_kind(r["data_type"])}
        for r in rows
    ]


async def _preview_pg(cd: dict, password: str, table: str, limit: int) -> tuple:
    import asyncpg
    c = await asyncpg.connect(
        host=cd["host"], port=cd["port"] or 5432, database=cd["database"],
        user=cd["username"], password=password, timeout=10,
    )
    # Get column names
    cols = await c.fetch(columns_of_visible_relation("$1"), table)
    col_names = [r["column_name"] for r in cols]
    safe_cols = ", ".join(f'"{cn}"' for cn in col_names)
    # Unqualified, so the relation resolves through the search path — which is how the
    # session can name it at all. Qualifying it `public` was what broke previews on a
    # mounted file even when the listing had started to work.
    rows = await c.fetch(f'SELECT {safe_cols} FROM "{table}" LIMIT {limit}')
    await c.close()
    return [[str(r[cn]) if r[cn] is not None else "NULL" for cn in col_names] for r in rows], col_names


# ── MySQL ───────────────────────────────────────────────────────────

async def _discover_mysql(cd: dict, password: str) -> list:
    import aiomysql
    c = await aiomysql.connect(
        host=cd["host"], port=cd["port"] or 3306, db=cd["database"],
        user=cd["username"], password=password,
    )
    cursor = await c.cursor()
    # Views included, and the kind travels with the name. `BASE TABLE` alone was a bug:
    # the PostgreSQL and Access paths list views (VISIBLE_RELATIONS covers 'v'), so the
    # same tool answered with a different set depending on the driver — and a view the
    # session can read was invisible on MySQL. `relation_kind` is the one mapping, so
    # the `type` values stay identical across all four drivers.
    await cursor.execute(
        "SELECT TABLE_NAME, TABLE_TYPE FROM information_schema.tables "
        "WHERE TABLE_SCHEMA = %s AND TABLE_TYPE IN ('BASE TABLE', 'VIEW') "
        "ORDER BY TABLE_NAME",
        (cd["database"],),
    )
    rows = await cursor.fetchall()
    c.close()
    return [{"name": r[0], "type": relation_kind(r[1])} for r in rows]


async def _columns_mysql(cd: dict, password: str, table: str, timeout: int = DEFAULT_CONNECT_TIMEOUT_SECONDS) -> list:
    import aiomysql
    c = await aiomysql.connect(
        host=cd["host"], port=cd["port"] or 3306, db=cd["database"],
        user=cd["username"], password=password,
    )
    cursor = await c.cursor()
    await cursor.execute(
        "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM information_schema.columns "
        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
        (cd["database"], table),
    )
    rows = await cursor.fetchall()
    c.close()
    return [{"name": r[0], "type": r[1], "nullable": r[2] == "YES", **column_kind(r[1])} for r in rows]


async def _preview_mysql(cd: dict, password: str, table: str, limit: int) -> tuple:
    import aiomysql
    c = await aiomysql.connect(
        host=cd["host"], port=cd["port"] or 3306, db=cd["database"],
        user=cd["username"], password=password,
    )
    cursor = await c.cursor()
    await cursor.execute(f"SELECT * FROM `{table}` LIMIT {limit}")
    col_names = [d[0] for d in cursor.description]
    rows = await cursor.fetchall()
    c.close()
    return [[str(v) if v is not None else "NULL" for v in r] for r in rows], col_names


# ── MSSQL ───────────────────────────────────────────────────────────

async def _discover_mssql(cd: dict, password: str) -> list:
    return await asyncio.to_thread(_discover_mssql_sync, cd, password)


def _discover_mssql_sync(cd: dict, password: str) -> list:
    import pymssql
    c = pymssql.connect(
        host=cd["host"], port=cd["port"] or 1433, database=cd["database"],
        user=cd["username"], password=password, tds_version="7.4", login_timeout=10,
    )
    cursor = c.cursor()
    # Views included, for the reason given in `_discover_mysql`: the other two drivers
    # list them, so filtering them out here made the same tool answer differently per
    # driver, and `INFORMATION_SCHEMA.TABLES` already carries the kind.
    cursor.execute(
        "SELECT TABLE_NAME, TABLE_TYPE FROM INFORMATION_SCHEMA.TABLES "
        "WHERE TABLE_TYPE IN ('BASE TABLE', 'VIEW') ORDER BY TABLE_NAME"
    )
    rows = cursor.fetchall()
    c.close()
    return [{"name": r[0], "type": relation_kind(r[1])} for r in rows]


async def _columns_mssql(cd: dict, password: str, table: str, timeout: int = DEFAULT_CONNECT_TIMEOUT_SECONDS) -> list:
    return await asyncio.to_thread(_columns_mssql_sync, cd, password, table)


def _columns_mssql_sync(cd: dict, password: str, table: str, timeout: int = DEFAULT_CONNECT_TIMEOUT_SECONDS) -> list:
    import pymssql
    c = pymssql.connect(
        host=cd["host"], port=cd["port"] or 1433, database=cd["database"],
        user=cd["username"], password=password, tds_version="7.4", login_timeout=timeout,
    )
    cursor = c.cursor()
    cursor.execute(
        "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE FROM INFORMATION_SCHEMA.COLUMNS "
        "WHERE TABLE_NAME = %s ORDER BY ORDINAL_POSITION",
        (table,),
    )
    rows = cursor.fetchall()
    c.close()
    return [{"name": r[0], "type": r[1], "nullable": r[2] == "YES", **column_kind(r[1])} for r in rows]


async def _preview_mssql(cd: dict, password: str, table: str, limit: int) -> tuple:
    return await asyncio.to_thread(_preview_mssql_sync, cd, password, table, limit)


def _preview_mssql_sync(cd: dict, password: str, table: str, limit: int) -> tuple:
    import pymssql
    c = pymssql.connect(
        host=cd["host"], port=cd["port"] or 1433, database=cd["database"],
        user=cd["username"], password=password, tds_version="7.4", login_timeout=10,
    )
    cursor = c.cursor()
    cursor.execute(f"SELECT TOP {limit} * FROM [{table}]")
    col_names = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    c.close()
    return [[str(v) if v is not None else "NULL" for v in r] for r in rows], col_names


# ── Access (via msaccess-endpoint-ng / psycopg2) ────────────────────

async def _discover_access(cd: dict, password: str) -> list:
    return await asyncio.to_thread(_discover_access_sync, cd, password)


def _discover_access_sync(cd: dict, password: str) -> list:
    import psycopg2
    c = psycopg2.connect(
        host=cd["host"], port=cd["port"] or 9432, dbname=cd["database"],
        user=cd["username"], password=password, connect_timeout=10,
    )
    cursor = c.cursor()
    cursor.execute(VISIBLE_RELATIONS)
    rows = cursor.fetchall()
    c.close()
    return [
        {"name": name, "type": relation_kind(kind)}
        for _schema, name, kind in rows
        if not name.startswith("MSys")
    ]


async def _columns_access(cd: dict, password: str, table: str, timeout: int = DEFAULT_CONNECT_TIMEOUT_SECONDS) -> list:
    return await asyncio.to_thread(_columns_access_sync, cd, password, table)


def _columns_access_sync(cd: dict, password: str, table: str, timeout: int = DEFAULT_CONNECT_TIMEOUT_SECONDS) -> list:
    import psycopg2
    c = psycopg2.connect(
        host=cd["host"], port=cd["port"] or 9432, dbname=cd["database"],
        user=cd["username"], password=password, connect_timeout=timeout,
    )
    cursor = c.cursor()
    cursor.execute(columns_of_visible_relation("%s"), (table,))
    rows = cursor.fetchall()
    c.close()
    return [{"name": r[0], "type": r[1], "nullable": r[2] == "YES", **column_kind(r[1])} for r in rows]


async def _preview_access(cd: dict, password: str, table: str, limit: int) -> tuple:
    return await asyncio.to_thread(_preview_access_sync, cd, password, table, limit)


def _preview_access_sync(cd: dict, password: str, table: str, limit: int) -> tuple:
    import psycopg2
    c = psycopg2.connect(
        host=cd["host"], port=cd["port"] or 9432, dbname=cd["database"],
        user=cd["username"], password=password, connect_timeout=10,
    )
    cursor = c.cursor()
    cursor.execute(f'SELECT * FROM "{table}" LIMIT {limit}')
    col_names = [d[0] for d in cursor.description]
    rows = cursor.fetchall()
    c.close()
    return [[str(v) if v is not None else "NULL" for v in r] for r in rows], col_names
