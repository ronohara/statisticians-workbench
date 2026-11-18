"""
PostgreSQL data manager — dedicated `workbench_data` user-data storage.

Item 2: derive the data-database connection from DATABASE_URL (auto-creating
the `workbench_data` database if it does not exist) and hold a dedicated
asyncpg pool.
Item 3: user-data storage methods (create / drop / preview / full table) with a
Python-type → PostgreSQL-type map. Return types are plain rows (list of dicts),
not pandas DataFrames, so this module stays Go-portable.
Item 5: non-pandas CSV reader (stdlib csv) — sniff the header, read columns +
rows, and apply explicit value type-inference (int / float / bool / date /
datetime → else TEXT).
Item 6: non-pandas Excel reader (openpyxl) — read the first sheet into columns +
rows; openpyxl already yields typed values, so the shared PG type map applies.
"""

import csv
import io
import logging
import math
import os
import re
import tempfile
import uuid
import xml.etree.ElementTree as ET
import zipfile
from datetime import date, datetime, time
from decimal import Decimal
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import xlrd
from dbfread import DBF
from src.utils.timestamps import iso_utc

DATA_DB_NAME = "workbench_data"

# Every object the application creates in `workbench_data` lives in the schema of the
# account that owns it — `u_<user_id>`, created on the first write. The notebook
# importer's `nb_<import_id>` schemas are the precedent, not the exception.
USER_SCHEMA_PREFIX = "u_"

logger = logging.getLogger(__name__)

# Dedicated pool for the data database (uploads, notebooks).
_data_pool: Optional[asyncpg.Pool] = None


def derive_data_dsn(database_url: str, database_name: str = DATA_DB_NAME) -> str:
    """Return `database_url` with its database name swapped for `database_name`.

    The existing workbench role owns both databases (it has CREATEDB), so only
    the database path component changes — host, port, user and password are
    reused. No new environment entry is required.
    """
    parts = urlsplit(database_url)
    return urlunsplit(
        (parts.scheme, parts.netloc, "/" + database_name, parts.query, parts.fragment)
    )


async def _data_database_exists(dsn: str) -> bool:
    """Return True if the database named in `dsn` exists."""
    try:
        conn = await asyncpg.connect(dsn)
    except asyncpg.InvalidCatalogNameError:
        return False
    await conn.close()
    return True


async def ensure_data_database(database_url: str) -> str:
    """Ensure the `workbench_data` database exists, creating it if absent.

    Returns the derived data DSN. When the data database is missing it is
    created via a connection to the main `database_url` (the workbench role has
    CREATEDB); the caller then connects to the freshly created database.
    """
    data_dsn = derive_data_dsn(database_url, DATA_DB_NAME)
    if await _data_database_exists(data_dsn):
        return data_dsn

    logger.info("workbench_data database does not exist — creating it")
    conn = await asyncpg.connect(database_url)
    try:
        await conn.execute(f'CREATE DATABASE "{DATA_DB_NAME}"')
        # Set the new database's default zone in the same breath as creating it.
        #
        # A database inherits the cluster's default at creation, and that default is
        # whatever the installing machine was set to — Asia/Bangkok here, UTC on a cloud
        # VM, something else elsewhere. Setting it here is what makes a fresh install
        # match a deployed one; `0026_database_timezone_utc.sql` covers the case where
        # this database already existed, and cannot cover this one because it runs before
        # the database exists.
        #
        # The application pins its own pooled connections to UTC regardless, so this is
        # about every *other* consumer: a psql session, an operator's query, the
        # packaging importer.
        await conn.execute(f"ALTER DATABASE \"{DATA_DB_NAME}\" SET timezone = 'UTC'")
    finally:
        await conn.close()
    logger.info("workbench_data database created")
    return data_dsn


def set_data_pool(pool: Optional[asyncpg.Pool]) -> None:
    """Set the dedicated data-database pool (called at startup)."""
    global _data_pool
    _data_pool = pool


def get_data_pool() -> Optional[asyncpg.Pool]:
    """Return the dedicated data-database pool."""
    return _data_pool


def _require_pool() -> asyncpg.Pool:
    """Return the data pool, raising if it has not been initialised."""
    pool = get_data_pool()
    if pool is None:
        raise RuntimeError("Data database pool is not initialised")
    return pool


def _pg_type_for_value(value: Any) -> str:
    """Map a Python value's type to a PostgreSQL type (TEXT fallback).

    Note: bool is checked before int, and datetime before date, because bool
    subclasses int and datetime subclasses date.

    This is the *fallback* map: it is used when the source column's declared
    type is unknown, and it cannot see the width of an integer (Python has one
    ``int``) so every integer lands as BIGINT.
    """
    if isinstance(value, bool):
        return "BOOLEAN"
    if isinstance(value, int):
        return "BIGINT"
    if isinstance(value, float):
        return "DOUBLE PRECISION"
    if isinstance(value, Decimal):
        return "NUMERIC"
    if isinstance(value, datetime):
        return "TIMESTAMP"
    if isinstance(value, date):
        return "DATE"
    if isinstance(value, time):
        return "TIME"
    if isinstance(value, bytes):
        return "BYTEA"
    return "TEXT"


# Declared source type → PostgreSQL type. The keys are PostgreSQL's internal
# type names as the drivers report them (`asyncpg.types.Type.name`,
# `pgx`'s OID lookup), not SQL spellings: "int4", not "integer".
#
# A column is typed from this map when the source declares one, because the
# declared type carries what a decoded value loses — an integer's width most of
# all (int2/int4/int8), and a float's. Anything absent here falls back to
# :func:`_pg_type_for_value`, which is what every column did before this map
# existed, so an unmapped or unopened type keeps the previous behaviour rather
# than failing.
_PG_DECLARED_TYPES = {
    "bool": "BOOLEAN",
    "int2": "SMALLINT",
    "int4": "INTEGER",
    "int8": "BIGINT",
    "float4": "REAL",
    "float8": "DOUBLE PRECISION",
    "numeric": "NUMERIC",
    "text": "TEXT",
    "varchar": "TEXT",
    "bpchar": "TEXT",
    "name": "TEXT",
    "citext": "TEXT",
    "timestamp": "TIMESTAMP",
    "timestamptz": "TIMESTAMP",
    "date": "DATE",
    "time": "TIME",
    "timetz": "TIME",
    "bytea": "BYTEA",
}


def _pg_type_for_declared(declared_type: Optional[str]) -> Optional[str]:
    """Map a source column's declared type to a PostgreSQL type, or None if the
    source cannot name it (so the caller falls back to value inference)."""
    if not declared_type:
        return None
    return _PG_DECLARED_TYPES.get(declared_type.strip().lower())


def _infer_column_type(
    rows: List[Dict[str, Any]],
    column: str,
    declared_type: Optional[str] = None,
) -> str:
    """A column's PostgreSQL type: the source's declared type when it names one
    we recognise, otherwise inferred from the first non-None value.

    The declared type wins because it is the truth about the source column; the
    value only carries what the driver chose to decode. Columns with no
    non-None value and no declared type default to TEXT, as before.
    """
    mapped = _pg_type_for_declared(declared_type)
    if mapped is not None:
        return mapped
    for row in rows:
        value = row.get(column)
        if value is not None:
            return _pg_type_for_value(value)
    return "TEXT"


def _quote(identifier: str) -> str:
    """Quote a table/column identifier for safe SQL interpolation."""
    return '"' + identifier.replace('"', '""') + '"'


def _split_qualified(name: str) -> Tuple[str, str]:
    """Split a possibly schema-qualified table name into (schema, table).

    A bare name (no dot) resolves to the ``public`` schema. Only the first dot
    splits; any further dots remain part of the table identifier, matching how
    PostgreSQL parses unquoted qualified names.
    """
    if "." in name:
        schema, _, table = name.partition(".")
        return schema, table
    return "public", name


def _quote_qualified(name: str) -> str:
    """Quote a (possibly schema-qualified) table name as "schema"."table"."""
    schema, table = _split_qualified(name)
    return f"{_quote(schema)}.{_quote(table)}"


async def _ensure_schema(conn, schema: str) -> None:
    """Create a schema in `workbench_data` if it does not exist yet."""
    await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {_quote(schema)}")


async def ensure_user_schema(conn, user_id: str) -> str:
    """Create the account's schema if it is missing, and return its name.

    Run on the first write for an account: the schema is the home of every
    object the application creates in `workbench_data`, so creating it is part
    of creating the first of them.
    """
    schema = user_schema_name(user_id)
    await _ensure_schema(conn, schema)
    return schema


async def create_table_from_rows(
    columns: List[str], rows: List[Dict[str, Any]], table_name: str
) -> str:
    """Create a typed table in `workbench_data` from ordered columns + rows.

    Column types are inferred from the first non-None value in each column via
    the Python→PostgreSQL type map; columns with no non-None value default to
    TEXT. Rows are bulk-inserted with executemany.

    `table_name` may be schema-qualified — `u_<user_id>.upload_…`, which is what
    the callers record in `UserDataset.tableName`. When it names a schema other
    than `public`, that schema is created first, so a caller only ever composes
    the name and never creates the schema itself.
    """
    pool = _require_pool()
    schema, _table = _split_qualified(table_name)
    qualified = _quote_qualified(table_name)
    col_types = {col: _infer_column_type(rows, col) for col in columns}
    col_defs = ", ".join(f"{_quote(col)} {col_types[col]}" for col in columns)
    create_sql = f"CREATE TABLE {qualified} ({col_defs})"

    async with pool.acquire() as conn:
        if schema != "public":
            await _ensure_schema(conn, schema)
        await conn.execute(create_sql)
        if rows:
            col_list = ", ".join(_quote(col) for col in columns)
            placeholders = ", ".join(f"${i}" for i in range(1, len(columns) + 1))
            insert_sql = (
                f"INSERT INTO {qualified} ({col_list}) "
                f"VALUES ({placeholders})"
            )
            await conn.executemany(
                insert_sql,
                [tuple(row.get(col) for col in columns) for row in rows],
            )

    return table_name


async def drop_table(table_name: str) -> bool:
    """Drop a table from `workbench_data` if it exists.

    Accepts a bare name (which resolves to the `public` schema) or a
    schema-qualified one, so a stored `UserDataset.tableName` is passed through
    to the drop that undoes the create.
    """
    pool = _require_pool()
    async with pool.acquire() as conn:
        await conn.execute(f"DROP TABLE IF EXISTS {_quote_qualified(table_name)}")
    return True


def _drop_statement(object_kind: str, object_name: str) -> str:
    """The statement that removes one manifest entry, by the kinds it may carry.

    The vocabulary is the one the manifest migration documents: a schema is
    dropped whole — `u_<user_id>` is every object an account owns, and a
    notebook import's `nb_<import_id>` — and anything else is a table whose name
    says where it lives.
    """
    if object_kind in ("user_schema", "notebook_schema"):
        return f"DROP SCHEMA IF EXISTS {_quote(object_name)} CASCADE"
    return f"DROP TABLE IF EXISTS {_quote_qualified(object_name)}"


async def drop_manifest_objects(entries: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Drop each object a cleanup-manifest entry names, on the data pool.

    Returns one result per entry — the entry itself plus `dropped` and `error` —
    and never raises for a single failed object: a drop that fails leaves its
    entry for the caller to keep, so the cleanup stays retryable instead of
    being lost with the error. `DROP … IF EXISTS` makes an object that is
    already gone a success, which is what a re-run needs.
    """
    pool = _require_pool()
    results: List[Dict[str, Any]] = []
    async with pool.acquire() as conn:
        for entry in entries:
            statement = _drop_statement(entry["objectKind"], entry["objectName"])
            try:
                await conn.execute(statement)
                results.append({**entry, "dropped": True, "error": None})
            except Exception as exc:  # reported per object, never raised
                results.append({**entry, "dropped": False, "error": str(exc)})
    return results


async def get_table_preview(
    table_name: str, limit: int = 10
) -> List[Dict[str, Any]]:
    """Return the first `limit` rows of a table as a list of row dicts."""
    pool = _require_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT * FROM {_quote_qualified(table_name)} LIMIT {int(limit)}"
        )
    return [dict(row) for row in rows]


async def get_full_table(table_name: str) -> List[Dict[str, Any]]:
    """Return all rows of a table as a list of row dicts."""
    pool = _require_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(f"SELECT * FROM {_quote_qualified(table_name)}")
    return [dict(row) for row in rows]


async def _relation_preview(
    conn, source_sql: str, columns: List[str], limit: int
) -> List[Dict[str, Any]]:
    """Core preview query on an explicit connection.

    `source_sql` is the quoted FROM fragment. Column identifiers are quoted
    individually so the caller can push column selection down to SQL. Shared by
    the pool-backed (get_table_preview_columns) and held-connection
    (get_relation_preview) variants.
    """
    col_sql = ", ".join(_quote(c) for c in columns)
    rows = await conn.fetch(f"SELECT {col_sql} FROM {source_sql} LIMIT {int(limit)}")
    return [dict(row) for row in rows]


async def _relation_row_count(conn, source_sql: str) -> int:
    """Core COUNT(*) query on an explicit connection (shared by the table and
    relation variants)."""
    return await conn.fetchval(f"SELECT COUNT(*) FROM {source_sql}")


async def get_table_preview_columns(
    table_name: str, columns: List[str], limit: int = 10
) -> List[Dict[str, Any]]:
    """Return the first `limit` rows of the given columns as a list of row dicts."""
    pool = _require_pool()
    async with pool.acquire() as conn:
        return await _relation_preview(conn, _quote_qualified(table_name), columns, limit)


async def get_table_row_count(table_name: str) -> int:
    """Return the number of rows in a table."""
    pool = _require_pool()
    async with pool.acquire() as conn:
        return await _relation_row_count(conn, _quote_qualified(table_name))


async def get_relation_preview(
    conn, source_sql: str, columns: List[str], limit: int = 10
) -> List[Dict[str, Any]]:
    """Return the first `limit` rows of a relation using an explicit connection.

    `source_sql` is the FROM fragment (e.g. ``relation_source(relation)``); the
    caller holds `conn` so a session-scoped TEMP table stays visible.
    """
    return await _relation_preview(conn, source_sql, columns, limit)


async def get_relation_row_count(conn, source_sql: str) -> int:
    """Return COUNT(*) of a relation using an explicit connection."""
    return await _relation_row_count(conn, source_sql)


async def get_distinct_values(table_name: str, column: str) -> List[Any]:
    """Return the distinct values of a column, in ascending order."""
    pool = _require_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            f"SELECT DISTINCT {_quote(column)} AS value "
            f"FROM {_quote_qualified(table_name)} ORDER BY value"
        )
    return [row["value"] for row in rows]


async def get_grouped_sum(
    conn, source_sql: str, group_col: str, value_col: str
) -> List[Tuple[Any, Any]]:
    """Return (group_value, SUM(value_col)) pairs ordered by group value ascending.

    `source_sql` is the FROM fragment (e.g. ``relation_source(relation)``);
    mirrors ``df.groupby(group_col)[value_col].sum().reset_index()``.
    """
    rows = await conn.fetch(
        f"SELECT {_quote(group_col)} AS grp, SUM({_quote(value_col)}) AS val "
        f"FROM {source_sql} GROUP BY {_quote(group_col)} ORDER BY grp"
    )
    return [(row["grp"], row["val"]) for row in rows]


async def get_value_counts(
    conn, source_sql: str, column: str, sort_by_value: bool = False
) -> List[Tuple[Any, Any]]:
    """Return (value, count) pairs for a column.

    ``sort_by_value=False`` → count descending (mirrors pandas
    ``value_counts()``); ``sort_by_value=True`` → value ascending (mirrors
    ``value_counts().sort_index()``). NULLs are excluded (pandas drops NaN by
    default).
    """
    order = (
        f"ORDER BY {_quote(column)}"
        if sort_by_value
        else "ORDER BY cnt DESC, value ASC"
    )
    rows = await conn.fetch(
        f"SELECT {_quote(column)} AS value, COUNT(*) AS cnt "
        f"FROM {source_sql} "
        f"WHERE {_quote(column)} IS NOT NULL "
        f"GROUP BY {_quote(column)} {order}"
    )
    return [(row["value"], row["cnt"]) for row in rows]


_NUMERIC_PG_TYPES = {
    "smallint", "integer", "bigint", "decimal", "numeric",
    "real", "double precision", "smallserial", "serial", "bigserial",
}


async def get_relation_numeric_columns(
    conn, source_sql: str, columns: List[str]
) -> set:
    """Return the subset of `columns` whose PostgreSQL type is numeric.

    Uses ``pg_typeof`` over a small sample so a NULL in the first row does not
    misclassify the column.
    """
    numeric = set()
    if not columns:
        return numeric
    exprs = ", ".join(f"pg_typeof({_quote(c)}) AS {_quote(c)}" for c in columns)
    rows = await conn.fetch(f"SELECT {exprs} FROM {source_sql} LIMIT 10")
    for row in rows:
        for c in columns:
            typ = row[c]
            if typ is not None and str(typ) in _NUMERIC_PG_TYPES:
                numeric.add(c)
    return numeric


async def get_relation_rows(
    conn, source_sql: str, columns: List[str]
) -> List[Dict[str, Any]]:
    """Return all rows of the given columns from a relation."""
    col_sql = ", ".join(_quote(c) for c in columns)
    rows = await conn.fetch(f"SELECT {col_sql} FROM {source_sql}")
    return [dict(row) for row in rows]


async def materialize_temp_table(conn, sql: str) -> str:
    """Create a session-scoped TEMP table from a SELECT and return its name.

    The caller holds the connection for the recipe session so the table stays
    visible to later stages; it auto-drops when the connection closes.
    """
    table_name = f"_recipe_tmp_{uuid.uuid4().hex}"
    await conn.execute(f"CREATE TEMP TABLE {_quote(table_name)} AS {sql}")
    return table_name


async def materialize_temp_table_from_rows(
    conn,
    columns: List[str],
    rows: List[Dict[str, Any]],
    declared_types: Optional[Dict[str, str]] = None,
) -> str:
    """Create a session-scoped TEMP table from ordered columns + rows.

    A column's type is the source's declared type when ``declared_types`` names
    one this module recognises; otherwise it is inferred from the first non-None
    value per column (the same Python→PostgreSQL type map as
    :func:`create_table_from_rows`), with columns that have neither defaulting to
    TEXT. Used by the federated-data path (Item 24) to land external-engine rows
    into PostgreSQL so the relation-based stages can read them.

    ``declared_types`` maps a column name to the source's type name (e.g.
    ``"int4"``), as the driver reports it. Passing it is what keeps a 4-byte
    integer a 4-byte integer: value inference sees one Python ``int`` and can
    only ever say BIGINT.
    """
    declared_types = declared_types or {}
    table_name = f"_recipe_tmp_{uuid.uuid4().hex}"
    col_types = {
        col: _infer_column_type(rows, col, declared_types.get(col))
        for col in columns
    }
    col_defs = ", ".join(f"{_quote(col)} {col_types[col]}" for col in columns)
    await conn.execute(f"CREATE TEMP TABLE {_quote(table_name)} ({col_defs})")
    if rows:
        col_list = ", ".join(_quote(col) for col in columns)
        placeholders = ", ".join(f"${i}" for i in range(1, len(columns) + 1))
        await conn.executemany(
            f"INSERT INTO {_quote(table_name)} ({col_list}) VALUES ({placeholders})",
            [tuple(row.get(col) for col in columns) for row in rows],
        )
    return table_name


# ---------------------------------------------------------------------------
# Schema / statistics helpers (Item 9)
# ---------------------------------------------------------------------------

async def table_exists(table_name: str) -> bool:
    """Return True if a table exists in `workbench_data`.

    Accepts a bare name (``public`` schema) or a schema-qualified name
    (``schema.table``, as produced by notebook imports).
    """
    schema, table = _split_qualified(table_name)
    pool = _require_pool()
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            "SELECT 1 FROM information_schema.tables "
            "WHERE table_schema = $1 AND table_name = $2",
            schema,
            table,
        )
    return row is not None


async def get_table_schema(table_name: str) -> List[Dict[str, Any]]:
    """Return a table's columns as [{name, type, nullable}] (ordered)."""
    schema, table = _split_qualified(table_name)
    pool = _require_pool()
    async with pool.acquire() as conn:
        rows = await conn.fetch(
            "SELECT column_name, data_type, is_nullable "
            "FROM information_schema.columns "
            "WHERE table_schema = $1 AND table_name = $2 "
            "ORDER BY ordinal_position",
            schema,
            table,
        )
    return [
        {
            "name": row["column_name"],
            "type": row["data_type"].upper(),
            "nullable": row["is_nullable"] == "YES",
        }
        for row in rows
    ]


async def get_table_statistics(table_name: str) -> Dict[str, Any]:
    """Return {table_name, row_count, column_count, schema} for a table."""
    pool = _require_pool()
    async with pool.acquire() as conn:
        row_count = await conn.fetchval(f"SELECT COUNT(*) FROM {_quote_qualified(table_name)}")
    schema = await get_table_schema(table_name)
    return {
        "table_name": table_name,
        "row_count": row_count,
        "column_count": len(schema),
        "schema": schema,
    }


# ---------------------------------------------------------------------------
# CSV reading (Item 5) — no pandas
# ---------------------------------------------------------------------------

# Values treated as missing, mirroring the common subset of pandas' default
# na_values. The check is case-insensitive on the stripped cell.
_NA_VALUES = {"", "nan", "na", "n/a", "none", "null", "nil"}


def _parse_timestamp(text: str):
    """Parse an ISO-8601 date or timestamp into date/datetime, else raise."""
    s = text.strip()
    if not s:
        raise ValueError("empty timestamp")
    # Date-only: YYYY-MM-DD
    if len(s) == 10 and s[4] == "-" and s[7] == "-":
        return date.fromisoformat(s)
    # Normalise a trailing Z (UTC marker) and a space date/time separator.
    if s.endswith(("Z", "z")):
        s = s[:-1] + "+00:00"
    if "T" not in s and " " in s:
        s = s.replace(" ", "T", 1)
    return datetime.fromisoformat(s)


def _parse_csv_value(value: str) -> Any:
    """Parse a CSV cell string into a typed value (explicit inference).

    Order: missing → None; bool → bool; int → int; float → float (finite only);
    ISO date/datetime → date/datetime; otherwise the string is returned
    unchanged (TEXT).
    """
    if value is None:
        return None
    s = value.strip()
    if s.lower() in _NA_VALUES:
        return None
    if s.lower() in ("true", "false"):
        return s.lower() == "true"
    try:
        return int(s)
    except ValueError:
        pass
    try:
        f = float(s)
        if math.isfinite(f):
            return f
    except ValueError:
        pass
    try:
        return _parse_timestamp(s)
    except ValueError:
        pass
    return value


def _normalise_columns(raw: List[str]) -> List[str]:
    """Turn a raw header row into unique, SQL-safe column names.

    Empty names become "Unnamed: {position}" (matching pandas and the notebooks
    parser); duplicate names get a _2/_3 suffix so the column list stays unique
    for CREATE TABLE.
    """
    result: List[str] = []
    seen: Dict[str, int] = {}
    for i, name in enumerate(raw):
        name = (name or "").strip()
        if name == "":
            name = f"Unnamed: {i}"
        if name in seen:
            seen[name] += 1
            name = f"{name}_{seen[name]}"
        else:
            seen[name] = 1
        result.append(name)
    return result


def parse_csv(contents: bytes) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Parse CSV bytes into (columns, rows) using stdlib csv + type inference.

    Replaces pd.read_csv. The first row is treated as the header when the csv
    Sniffer detects one; otherwise columns are named col_0..col_N. Each cell is
    typed by _parse_csv_value, so the returned rows are ready to hand straight
    to create_table_from_rows.
    """
    text = contents.decode("utf-8", errors="replace")
    try:
        has_header = csv.Sniffer().has_header(text[:8192])
    except csv.Error:
        has_header = False

    raw_rows = list(csv.reader(io.StringIO(text)))
    if not raw_rows:
        return [], []

    if has_header:
        columns = _normalise_columns(raw_rows[0])
        data_rows = raw_rows[1:]
    else:
        width = max((len(r) for r in raw_rows), default=0)
        columns = [f"col_{i}" for i in range(width)]
        data_rows = raw_rows

    rows = [
        {
            col: _parse_csv_value(row[i] if i < len(row) else None)
            for i, col in enumerate(columns)
        }
        for row in data_rows
    ]
    return columns, rows


def parse_excel(contents: bytes) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Parse Excel bytes (.xlsx/.xlsm) into (columns, rows) using openpyxl.

    Replaces pd.read_excel. Reads the first worksheet; the first row is the
    header (columns) and the remaining rows are data. openpyxl already yields
    typed cell values (int / float / bool / datetime / time / str / None), so
    no value inference is needed — create_table_from_rows applies the shared
    PG type map on insert. Legacy .xls (binary) is not supported (needs xlrd).
    """
    import openpyxl
    workbook = openpyxl.load_workbook(
        io.BytesIO(contents), read_only=True, data_only=True
    )
    try:
        worksheet = workbook.worksheets[0]
        raw_rows = list(worksheet.iter_rows(values_only=True))
    finally:
        workbook.close()

    if not raw_rows:
        return [], []

    header = [str(c) if c is not None else "" for c in raw_rows[0]]
    columns = _normalise_columns(header)
    data_rows = raw_rows[1:]

    rows = [
        {
            col: row[i] if i < len(row) else None
            for i, col in enumerate(columns)
        }
        for row in data_rows
    ]
    return columns, rows


def _xls_header_text(sheet, col: int) -> str:
    """Render one .xls header cell the way the .xlsx path renders its values.

    An integral number loses its trailing ".0" because openpyxl yields int where
    xlrd always yields float, and the header text has to agree between the two
    Excel paths for the same workbook.
    """
    ctype = sheet.cell_type(0, col)
    if ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return ""
    value = sheet.cell_value(0, col)
    if ctype == xlrd.XL_CELL_NUMBER and float(value).is_integer():
        return str(int(value))
    return str(value)


def _xls_value(sheet, row: int, col: int, datemode: int) -> Any:
    """Type one .xls cell through xlrd's own cell types.

    xlrd has already decided date-versus-number from the cell's number format —
    for a built-in format index and for a custom format string alike — so this
    mirrors its answer rather than second-guessing it. Error cells carry the
    Excel error string, which is what openpyxl returns for .xlsx.
    """
    ctype = sheet.cell_type(row, col)
    value = sheet.cell_value(row, col)
    if ctype in (xlrd.XL_CELL_EMPTY, xlrd.XL_CELL_BLANK):
        return None
    if ctype == xlrd.XL_CELL_DATE:
        return xlrd.xldate.xldate_as_datetime(value, datemode)
    if ctype == xlrd.XL_CELL_BOOLEAN:
        return bool(value)
    if ctype == xlrd.XL_CELL_ERROR:
        return xlrd.error_text_from_code.get(value, f"#ERR{value}")
    return value


def parse_excel_legacy(contents: bytes) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Parse legacy .xls (BIFF) bytes into (columns, rows) using xlrd.

    parse_excel (openpyxl) cannot read BIFF and xlrd cannot read OOXML, so the
    two formats take different readers but keep one shape: row 0 is the header
    through _normalise_columns, and each data row is a dict over those columns
    with a missing cell as None — the same rule the .xlsx path already applies.
    Dates arrive as datetime rather than as serials, because xlrd types them
    from the cell's number format, so the shared PG type map applies unchanged.
    """
    book = xlrd.open_workbook(file_contents=contents)
    sheet = book.sheet_by_index(0)
    if sheet.nrows == 0:
        return [], []

    columns = _normalise_columns([
        _xls_header_text(sheet, col) for col in range(sheet.ncols)
    ])
    rows = [
        {col: _xls_value(sheet, row, i, book.datemode) for i, col in enumerate(columns)}
        for row in range(1, sheet.nrows)
    ]
    return columns, rows


# ---------------------------------------------------------------------------
# DIF and SYLK — hand-parsed on both sides
# ---------------------------------------------------------------------------
# Neither format has a library worth carrying in either language, so both are
# parsed here and mirrored in Go. The rules below are the specification for both
# sides: the same file must produce the same table, column for column.

_DIF_PAIR = re.compile(r"^(-?\d+),(.*)$")


def _dif_unquote(raw: str) -> str:
    """Strip a DIF string cell's quotes and unescape a doubled quote."""
    s = raw.strip()
    if len(s) >= 2 and s.startswith('"') and s.endswith('"'):
        s = s[1:-1]
    return s.replace('""', '"')


def _dif_date(value: str):
    """Read a dd/mm/yyyy or mm/dd/yyyy date, disambiguated by an obvious day.

    A first field above 12 must be the day, so 14/02/2026 is dd/mm and
    02/14/2026 is mm/dd. When neither field exceeds 12 the date is ambiguous
    and the international dd/mm is assumed. Anything else — both fields above
    12, a two-digit year, another separator, a date that does not exist — is
    not a date, and the caller keeps the text.
    """
    parts = value.strip().split("/")
    if len(parts) != 3:
        return None
    first, second, year = parts
    if not (first.isdigit() and second.isdigit() and year.isdigit()):
        return None
    if len(year) != 4:
        return None
    a, b, y = int(first), int(second), int(year)
    if a > 12:
        day, month = a, b
    elif b > 12:
        month, day = a, b
    else:
        day, month = a, b            # the international default
    try:
        return datetime(y, month, day, 0, 0, 0)
    except ValueError:
        return None


def _dif_number_or_date(value: str) -> Any:
    """Type a DIF type-0 slot: the CSV rule, then the date rule, else text."""
    parsed = _parse_csv_value(value)
    if not isinstance(parsed, str):
        return parsed
    found = _dif_date(value)
    return found if found is not None else parsed


def _cell_text(value: Any) -> str:
    """Render a header cell the way every other reader renders one."""
    return "" if value is None else str(value)


def parse_dif(contents: bytes) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Parse a DIF (Data Interchange Format) file into (columns, rows).

    The header block runs to DATA. The data is pairs of lines — a "type,value"
    line and a value line — with -1,0 / BOT ending each tuple and EOD ending
    the data. A type-0 cell carries its value on the type line with V beneath
    it; a type-1 cell carries 1,0 with the quoted text beneath.
    """
    lines = contents.decode("utf-8", errors="replace").splitlines()
    try:
        i = lines.index("DATA") + 1
    except ValueError:
        return [], []

    # Some writers open the data with a 0,0 / "" marker before the first tuple.
    # Its second line is "" where every real numeric cell's is V, so it is a
    # marker rather than a cell: read as a cell it would shift every column.
    if i + 1 < len(lines) and lines[i] == "0,0" and lines[i + 1] == '""':
        i += 2

    grid: List[List[Any]] = []
    row: List[Any] = []
    first_tuple = True
    while i < len(lines):
        match = _DIF_PAIR.match(lines[i])
        if match is None:
            i += 1
            continue
        kind, value = match.group(1), match.group(2)
        if kind == "-1":
            marker = lines[i + 1] if i + 1 < len(lines) else ""
            # A tuple with no cells is the marker's own, not a row.
            if row or not first_tuple:
                grid.append(row)
            row = []
            first_tuple = False
            i += 2
            if marker == "EOD":
                break
            continue
        if kind == "1":
            text = _dif_unquote(lines[i + 1] if i + 1 < len(lines) else '""')
            row.append(None if text == "" else text)
        elif kind == "0":
            row.append(_dif_number_or_date(value))
        i += 2

    if not grid:
        return [], []
    width = max(len(r) for r in grid)
    columns = _normalise_columns(
        [_cell_text(c) for c in grid[0]] + [""] * (width - len(grid[0]))
    )
    rows = [
        {col: (r[i] if i < len(r) else None) for i, col in enumerate(columns)}
        for r in grid[1:]
    ]
    return columns, rows


def _sylk_fields(line: str) -> Dict[str, str]:
    """Split a SYLK record into its "";X"-keyed fields, honouring quotes."""
    fields: Dict[str, str] = {}
    i, n = 0, len(line)
    while i < n:
        if line[i] != ";":
            i += 1
            continue
        i += 1
        if i >= n:
            break
        key = line[i]
        i += 1
        start = i
        in_quotes = False
        while i < n:
            char = line[i]
            if char == '"':
                in_quotes = not in_quotes
            elif char == ";" and not in_quotes:
                break
            i += 1
        fields[key] = line[start:i]
    return fields


def parse_sylk(contents: bytes) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Parse a SYLK (Symbolic Link) file into (columns, rows).

    Each cell is a C record — C;X<col>;Y<row>;K<value>, optionally with an
    E<expression> that carries no value. A quoted K is a string, an unquoted
    one a number by the CSV rule. The file is sparse, so the grid is the
    maximum extent and an absent cell is None.
    """
    text = contents.decode("utf-8", errors="replace")
    cells: Dict[Tuple[int, int], Any] = {}
    max_row = max_col = -1
    for line in text.splitlines():
        if not line:
            continue
        if line[0] == "E":
            break
        if line[0] != "C":
            continue                      # ID, F, B, O, P records carry no cell
        fields = _sylk_fields(line)
        if "X" not in fields or "Y" not in fields or "K" not in fields:
            continue
        try:
            col, line_no = int(fields["X"]), int(fields["Y"])
        except ValueError:
            continue
        raw = fields["K"]
        value: Any
        if raw.startswith('"'):
            value = raw[1:-1].replace('""', '"') if raw.endswith('"') else raw[1:]
            if value == "":
                value = None
        else:
            value = _parse_csv_value(raw)
        cells[(line_no - 1, col - 1)] = value
        max_row, max_col = max(max_row, line_no - 1), max(max_col, col - 1)

    if max_row < 0 or max_col < 0:
        return [], []
    columns = _normalise_columns(
        [_cell_text(cells.get((0, c))) for c in range(max_col + 1)]
    )
    rows = [
        {col: cells.get((r, i)) for i, col in enumerate(columns)}
        for r in range(1, max_row + 1)
    ]
    return columns, rows


# ---------------------------------------------------------------------------
# ODS — hand-parsed on both sides
# ---------------------------------------------------------------------------
# zipfile plus an XML parser here; archive/zip plus encoding/xml in Go. odfpy
# stays permitted and unused: a library on one side and a hand-written parser on
# the other is the arrangement in which dates diverge silently.

_NS_TABLE = "urn:oasis:names:tc:opendocument:xmlns:table:1.0"
_NS_OFFICE = "urn:oasis:names:tc:opendocument:xmlns:office:1.0"

# The format's own row limit; a repeated row is expanded no further than this.
_ODS_MAX_ROWS = 1_048_576

_ODS_DURATION = re.compile(r"^PT(?:(\d+)H)?(?:(\d+)M)?(?:(\d+(?:\.\d+)?)S)?$")


def _local(tag: str) -> str:
    """The local name of a namespaced element tag."""
    return tag.rsplit("}", 1)[-1]


def _ods_attr(el, namespace: str, name: str) -> Optional[str]:
    """An attribute by its full namespaced name.

    Local names are not enough here: LibreOffice writes office:value-type and
    calcext:value-type side by side, and their local names collide.
    """
    return el.get(f"{{{namespace}}}{name}")


def _ods_int_attr(el, namespace: str, name: str, default: int = 1) -> int:
    raw = _ods_attr(el, namespace, name)
    if raw is None:
        return default
    try:
        return max(1, int(raw))
    except ValueError:
        return default


def _ods_text(cell) -> str:
    """The text of a cell's paragraphs.

    Only what the fixture shows. <text:s> (a run of spaces), <text:tab/> and
    <text:line-break/> are NOT converted, so a cell written
    `first<text:s/>second` loses that space and its words run together. That is
    a recorded gap, and no fixture exercises it.
    """
    return "\n".join("".join(p.itertext()) for p in cell if _local(p.tag) == "p")


def _ods_datetime(raw: Optional[str]):
    """office:date-value is a bare ISO date; midnight is ours to add."""
    if not raw:
        return None
    s = raw.strip()
    try:
        d = date.fromisoformat(s)
        return datetime(d.year, d.month, d.day)
    except ValueError:
        pass
    try:
        return datetime.fromisoformat(s)
    except ValueError:
        return None


def _ods_time(raw: Optional[str]):
    """office:time-value is an ISO-8601 duration, e.g. PT12H34M56S.

    A duration spanning more than a day is not a time of day and is left as
    None; the fixture carries no time cells at all, so this is written from the
    specification and unproven.
    """
    if not raw:
        return None
    match = _ODS_DURATION.match(raw.strip())
    if match is None:
        return None
    hours = int(match.group(1) or 0)
    minutes = int(match.group(2) or 0)
    seconds = float(match.group(3) or 0)
    if hours > 23:
        return None
    whole = int(seconds)
    return time(hours, minutes, whole, round((seconds - whole) * 1_000_000))


def _ods_cell_value(cell) -> Any:
    """Type one cell from its office:value-type.

    currency keeps the number and drops the currency code: office:currency has
    nowhere to go, since the same column is a plain number through every other
    format. That is a recorded loss, not a side effect.
    """
    vtype = _ods_attr(cell, _NS_OFFICE, "value-type")
    if vtype in ("float", "currency", "percentage"):
        raw = _ods_attr(cell, _NS_OFFICE, "value")
        return _parse_csv_value(raw) if raw is not None else None
    if vtype == "date":
        return _ods_datetime(_ods_attr(cell, _NS_OFFICE, "date-value"))
    if vtype == "time":
        return _ods_time(_ods_attr(cell, _NS_OFFICE, "time-value"))
    if vtype == "boolean":
        raw = _ods_attr(cell, _NS_OFFICE, "boolean-value")
        return None if raw is None else raw == "true"
    text = _ods_text(cell)
    return text if text != "" else None


def parse_ods(contents: bytes) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Parse an ODS (OpenDocument Spreadsheet) file into (columns, rows).

    ODS pads its sheets: every row in the fixture expands to the same 257
    columns, and the sheet pads to the row limit. So both repeats are expanded
    first and the padding discarded second — a trailing empty run does not widen
    a row, and the grid stops at the last row that carries data. Read literally
    without that, a naive reader gets 257 columns and 1,048,576 rows.
    """
    try:
        with zipfile.ZipFile(io.BytesIO(contents)) as archive:
            content = archive.read("content.xml")
    except (zipfile.BadZipFile, KeyError):
        return [], []
    try:
        root = ET.fromstring(content)
    except ET.ParseError:
        return [], []

    table = next((el for el in root.iter() if _local(el.tag) == "table"), None)
    if table is None:
        return [], []

    parsed: List[Tuple[List[Any], int]] = []
    for row_el in table:
        if _local(row_el.tag) != "table-row":
            continue
        cells: List[Any] = []
        for cell in row_el:
            name = _local(cell.tag)
            if name not in ("table-cell", "covered-table-cell"):
                continue
            repeat = _ods_int_attr(cell, _NS_TABLE, "number-columns-repeated")
            # A covered cell is the far side of a merge: it holds no value but
            # it occupies its columns, so skipping it would shift the row.
            value = None if name == "covered-table-cell" else _ods_cell_value(cell)
            cells.extend([value] * repeat)
        while cells and cells[-1] is None:
            cells.pop()                # a trailing run is padding, not columns
        parsed.append((cells, _ods_int_attr(row_el, _NS_TABLE, "number-rows-repeated")))

    # The pad to the row limit is a repeated empty row at the end. Stopping at
    # the last row carrying data means it is never expanded at all.
    last = -1
    for i, (cells, _) in enumerate(parsed):
        if cells:
            last = i
    if last < 0:
        return [], []

    grid: List[List[Any]] = []
    for cells, repeat in parsed[:last + 1]:
        if len(grid) >= _ODS_MAX_ROWS:
            break
        for _ in range(min(repeat, _ODS_MAX_ROWS - len(grid))):
            grid.append(list(cells))
    if not grid:
        return [], []

    width = max(len(r) for r in grid)
    columns = _normalise_columns(
        [_cell_text(c) for c in grid[0]] + [""] * (width - len(grid[0]))
    )
    rows = [
        {col: (r[i] if i < len(r) else None) for i, col in enumerate(columns)}
        for r in grid[1:]
    ]
    return columns, rows


# ---------------------------------------------------------------------------
# .dbf — dBASE, read with dbfread
# ---------------------------------------------------------------------------
# The rules below were settled on 2026-09-24 and are mirrored in the Go port
# (internal/postgresdata/dbf.go), because neither side has a reference library
# to be held to. The type always comes from the field descriptor and the reader
# supplies raw content only, so the two cannot diverge on what a value means:
#
#   C  the decoded text, trimmed of its padding    TEXT
#   L  T/t/Y/y true, F/f/N/n false, ?/blank null   BOOLEAN
#   N  the CSV rule over the text                  BIGINT / DOUBLE PRECISION
#   F  a float                                     DOUBLE PRECISION
#   D  YYYYMMDD -> a datetime at midnight          TIMESTAMP
#
# Two things are refused rather than guessed: a memo field, whose value lives in
# a sidecar .dbt the upload does not carry; and any other field type, which
# neither reader can be asked to read. The Go reader builds its field list from
# a switch with no default, so a type it does not recognise is dropped from that
# list and every field after it is then mis-sliced — refusing at the header is
# what keeps the two sides agreeing.
#
# dbfread is driven through a temp file in raw mode: it takes a filename, and
# raw mode returns each field's bytes rather than its own typed conversion, so
# the descriptor above is the only typing applied. NUL padding is blanked first,
# because some encoders pad numeric fields with NULs rather than spaces and
# dbfread's typed parser raises on those (measured 2026-09-24).

_DBF_READABLE_TYPES = frozenset("CLDNF")
_DBF_MEMO_TYPES = frozenset("MGPB")


class DbfMemoUnsupportedError(Exception):
    """A .dbf whose header declares a memo field.

    The memo text lives in a sidecar (.dbt/.fpt) that a single-file upload does
    not carry, and the two readers disagree about what the field would hold.
    """


class DbfFieldTypeUnsupportedError(Exception):
    """A .dbf declaring a field type this reader will not guess at."""


def _dbf_text(raw: Any, encoding: str) -> str:
    """Decode a raw field value, blanking NUL padding and trimming."""
    if raw is None:
        return ""
    data = raw if isinstance(raw, bytes) else str(raw).encode("utf-8", "replace")
    return data.decode(encoding, errors="replace").replace("\x00", " ").strip()


def _dbf_datetime(text: str) -> Optional[datetime]:
    """Type a D field: YYYYMMDD, becoming a datetime at midnight.

    Midnight is ours to add, as it was for DIF and ODS, so this column types the
    same way as every other reader of the same date.
    """
    if len(text) != 8 or not text.isdigit():
        return None
    try:
        return datetime(int(text[0:4]), int(text[4:6]), int(text[6:8]), 0, 0, 0)
    except ValueError:
        return None


def _dbf_cell(field_type: str, raw: Any, encoding: str) -> Any:
    """Type one field value from its descriptor, never from the reader."""
    text = _dbf_text(raw, encoding)
    if text == "":
        return None
    if field_type == "L":
        upper = text.upper()
        if upper in ("T", "Y"):
            return True
        if upper in ("F", "N"):
            return False
        return None                 # "?" — never initialised
    if field_type == "D":
        return _dbf_datetime(text)
    if field_type in ("N", "F"):
        return _parse_csv_value(text)
    return text                     # C


def parse_dbf(contents: bytes) -> Tuple[List[str], List[Dict[str, Any]]]:
    """Parse a dBASE (.dbf) file into (columns, rows).

    Raises DbfMemoUnsupportedError or DbfFieldTypeUnsupportedError for a table
    this reader will not take; see the rules above. Deleted records are skipped,
    which is what dbfread's record iterator does on its own.
    """
    handle = tempfile.NamedTemporaryFile(suffix=".dbf", delete=False)
    try:
        handle.write(contents)
        handle.close()
        table = DBF(
            handle.name,
            raw=True,
            recfactory=None,
            ignorecase=False,
            ignore_missing_memofile=True,
            char_decode_errors="replace",
        )
        field_types = [field.type for field in table.fields]
        memo = sorted(set(field_types) & _DBF_MEMO_TYPES)
        if memo:
            raise DbfMemoUnsupportedError(", ".join(memo))
        unreadable = sorted(set(field_types) - _DBF_READABLE_TYPES)
        if unreadable:
            raise DbfFieldTypeUnsupportedError(", ".join(unreadable))

        encoding = table.encoding
        columns = _normalise_columns([field.name for field in table.fields])
        rows: List[Dict[str, Any]] = []
        for items in table:
            row: Dict[str, Any] = {}
            for index, (column, field) in enumerate(zip(columns, table.fields)):
                raw = items[index][1] if index < len(items) else None
                row[column] = _dbf_cell(field.type, raw, encoding)
            rows.append(row)
        return columns, rows
    finally:
        handle.close()
        os.unlink(handle.name)


# ---------------------------------------------------------------------------
# Accepted upload formats — the single list for this side
# ---------------------------------------------------------------------------
# Extension → parser. One home, so the handler's decision and the refusal
# message's enumeration cannot drift apart. Matching is case-insensitive at the
# call site, because a user's file may arrive as DATA.CSV.
UPLOAD_FORMATS = {
    ".csv": parse_csv,
    ".xlsx": parse_excel,
    ".xlsm": parse_excel,
    ".xls": parse_excel_legacy,
    ".dif": parse_dif,
    ".slk": parse_sylk,
    ".ods": parse_ods,
    ".dbf": parse_dbf,
}


# ---------------------------------------------------------------------------
# Upload helpers (Item 7) — table naming + JSON-safe previews
# ---------------------------------------------------------------------------

def _sanitise_table_name(name: str) -> str:
    """Sanitise a table name to `[a-zA-Z0-9_]`, max 63 chars."""
    sanitised = re.sub(r"[^a-zA-Z0-9_]", "_", name)
    if sanitised and sanitised[0].isdigit():
        sanitised = f"_{sanitised}"
    if len(sanitised) > 63:
        sanitised = sanitised[:63]
    return sanitised


def generate_table_name(user_id: str) -> str:
    """Generate a unique upload table name: upload_{user}_{ts}_{uuid}."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    unique_id = str(uuid.uuid4())[:8]
    return _sanitise_table_name(f"upload_{user_id}_{timestamp}_{unique_id}")


def user_schema_name(user_id: str) -> str:
    """Return the `workbench_data` schema an account's objects live in.

    `u_` plus the sanitised user id, sanitised exactly as a table name is, so the
    result is always a valid identifier and its owner can be read back from it.
    """
    return _sanitise_table_name(f"{USER_SCHEMA_PREFIX}{user_id}")


def json_safe(value: Any) -> Any:
    """Return a JSON-serialisable copy of a value (dates/times → ISO strings).

    Used for the UserDataset.dataSnapshot preview: the raw typed values stay in
    the PostgreSQL table, while the JSON snapshot needs stringified dates and
    no NaN/Infinity.
    """
    if value is None:
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (int, float, str)):
        return value
    if isinstance(value, datetime):
        return iso_utc(value)
    if isinstance(value, (date, time)):
        return value.isoformat()
    if isinstance(value, bytes):
        return value.decode("utf-8", errors="replace")
    if isinstance(value, dict):
        return {k: json_safe(v) for k, v in value.items()}
    if isinstance(value, (list, tuple)):
        return [json_safe(v) for v in value]
    return str(value)
