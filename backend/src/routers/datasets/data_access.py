"""
Dataset data-access layer — SQL execution and transform primitives.

Shared by the datasets and recipes modules. Mirrors the data/SQL helpers that
previously lived in recipes/helpers.py, moved here so the datasets <-> recipes
import graph is acyclic (no lazy imports).
"""
from typing import Dict, Any, List, Optional, Tuple
import math
from datetime import datetime, date
from decimal import Decimal
import asyncpg

from src.utils.translation import t
from src.utils.encryption import decrypt_field
from src.routers.datasets.crud import get_connection_row
from src.routers.datasets.translations import DATASETS
from src.routers.common.translations import (
    error_connection_connect_failed,
    error_connection_query_failed_2,
    error_connection_query_failed_3,
    error_connection_query_failed_4,
    error_connection_query_failed_5,
    error_connection_query_failed_6,
    error_connection_type_not_supported_3,
    error_dataset_load_failed_2,
    error_dataset_not_found_2,
    error_define_connection_not_found_2,
    error_preparation_rule_not_found_2,
)
from src.postgres_data_manager import get_data_pool

def _is_missing(value: Any) -> bool:
    """True for None and non-finite floats (NaN/Inf) — the ``isna`` subset we emit."""
    if value is None:
        return True
    if isinstance(value, float) and (math.isnan(value) or math.isinf(value)):
        return True
    return False




def _is_numeric_value(value: Any) -> bool:
    """True for int/float/Decimal, excluding bool (bool subclasses int)."""
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)




def _is_datetime_value(value: Any) -> bool:
    """True for datetime/date values."""
    return isinstance(value, (datetime, date))




async def apply_preparation_rule(
    db_pool: asyncpg.Pool,
    preparation_rule_id: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    language: str = "en"
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Apply a preparation rule to a table of rows.

    Args:
        db_pool: Database connection pool
        preparation_rule_id: The preparation rule ID
        columns: The column names in order
        rows: The rows as a list of plain dicts
        language: User's language for error messages

    Returns:
        ``(columns, rows)`` — the transformed table.

    Raises:
        ValueError: If the preparation rule is not found or operations fail
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT name, operations
            FROM "DataPreparationRule"
            WHERE id = $1
            """,
            preparation_rule_id
        )

        if row is None:
            raise ValueError(
                await t(db_pool, language, error_preparation_rule_not_found_2,
                    id=preparation_rule_id
                )
            )

        operations = row["operations"]

        # Apply each operation in order
        for op in operations:
            columns, rows = await _apply_operation(columns, rows, op)

        return columns, rows




def _sort_key(value):
    """Stable sort key for mixed-type values (None last)."""
    return (0, str(value)) if value is not None else (1, "")




def _to_numeric(value):
    """Coerce a value to int/float, or None on failure (mirrors pd.to_numeric coerce)."""
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return int(value)
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    if f.is_integer():
        return int(f)
    return f




def _to_datetime(value):
    """Coerce a value to datetime, or None on failure (mirrors pd.to_datetime coerce)."""
    if _is_missing(value):
        return None
    if isinstance(value, (datetime, date)):
        return value
    try:
        return datetime.fromisoformat(str(value))
    except (TypeError, ValueError):
        return None




def _to_bool(value):
    """Coerce a value to bool (mirrors astype(bool): non-empty/non-zero is True)."""
    if _is_missing(value):
        return None
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return value.strip().lower() in ("true", "1", "yes")
    return bool(value)




def _filter_match(value, operator, value_target) -> bool:
    """Apply one filter comparison, matching the SQL path (NULL never matches)."""
    if _is_missing(value):
        return False
    if operator == ">":
        return value > value_target
    if operator == ">=":
        return value >= value_target
    if operator == "<":
        return value < value_target
    if operator == "<=":
        return value <= value_target
    if operator == "==":
        return value == value_target
    if operator == "!=":
        return value != value_target
    if operator == "contains":
        return str(value_target) in str(value)
    if operator == "in":
        return value in value_target if isinstance(value_target, list) else value == value_target
    return True




def _fill_value(rows, column, method, operation):
    """Compute the fill value for a column (mean/median/mode/constant)."""
    if method == "constant":
        return operation.get("value")
    values = [r[column] for r in rows if not _is_missing(r.get(column))]
    if not values:
        return None
    if method == "mean" and all(_is_numeric_value(v) for v in values):
        return sum(values) / len(values)
    if method == "median" and all(_is_numeric_value(v) for v in values):
        ordered = sorted(values)
        n = len(ordered)
        mid = n // 2
        if n % 2:
            return ordered[mid]
        return (ordered[mid - 1] + ordered[mid]) / 2
    if method == "mode":
        counts = {}
        for v in values:
            counts[v] = counts.get(v, 0) + 1
        return sorted(counts.items(), key=lambda kv: (-kv[1], _sort_key(kv[0])))[0][0]
    return None




def _normalize_column(rows, column, standardize):
    """Min-max (standardize=False) or z-score (standardize=True) a numeric column in place."""
    values = [r[column] for r in rows if not _is_missing(r.get(column))]
    if not values or not all(_is_numeric_value(v) for v in values):
        return
    if standardize:
        mean = sum(values) / len(values)
        variance = sum((v - mean) ** 2 for v in values) / (len(values) - 1) if len(values) > 1 else 0
        std = math.sqrt(variance)
        for r in rows:
            if not _is_missing(r.get(column)):
                r[column] = (r[column] - mean) / std if std > 0 else 0
    else:
        min_val = min(values)
        max_val = max(values)
        for r in rows:
            if not _is_missing(r.get(column)):
                r[column] = (r[column] - min_val) / (max_val - min_val) if max_val > min_val else 0




def _one_hot_encode(columns, rows, column):
    """Add one-hot columns for a categorical column and drop the original."""
    categories = sorted({r.get(column) for r in rows if not _is_missing(r.get(column))}, key=_sort_key)
    new_cols = [f"{column}_{cat}" for cat in categories]
    for r in rows:
        v = r.get(column)
        for cat, nc in zip(categories, new_cols):
            r[nc] = 1 if (not _is_missing(v) and v == cat) else 0
    new_order = [c for c in columns if c != column] + new_cols
    for r in rows:
        r.pop(column, None)
    return new_order, rows




async def _apply_operation(
    columns: List[str],
    rows: List[Dict[str, Any]],
    operation: Dict[str, Any]
) -> Tuple[List[str], List[Dict[str, Any]]]:
    """
    Apply a single preparation operation to a table of rows (no pandas).

    Supported operations:
        - filter: Filter rows based on column condition
        - fill_missing: Fill missing values in a column
        - convert_type: Convert column data type
        - normalize: Min-Max scaling on numeric columns
        - standardize: Z-score standardization on numeric columns
        - encode: Categorical encoding (one-hot, label)
        - drop_duplicates: Drop duplicate rows (optionally keyed on a column subset)
        - drop_columns: Drop specified columns
        - rename_column: Rename a column

    Args:
        columns: The column names in order
        rows: The rows as a list of plain dicts
        operation: Operation configuration

    Returns:
        ``(columns, rows)`` — the transformed table.
    """
    op_type = operation.get("type")
    column = operation.get("column")
    op_columns = operation.get("columns", []) or []

    if op_type == "filter":
        operator = operation.get("operator")
        value = operation.get("value")
        if column and operator and value is not None:
            rows = [r for r in rows if _filter_match(r.get(column), operator, value)]

    elif op_type == "fill_missing":
        method = operation.get("method", "mean")
        if column and column in columns:
            if method == "drop":
                rows = [r for r in rows if not _is_missing(r.get(column))]
            else:
                fill_value = _fill_value(rows, column, method, operation)
                for r in rows:
                    if _is_missing(r.get(column)):
                        r[column] = fill_value

    elif op_type == "convert_type":
        target_type = operation.get("target_type")
        if column and column in columns and target_type:
            if target_type == "numeric":
                for r in rows:
                    r[column] = _to_numeric(r.get(column))
            elif target_type == "datetime":
                for r in rows:
                    r[column] = _to_datetime(r.get(column))
            elif target_type == "string":
                for r in rows:
                    v = r.get(column)
                    r[column] = str(v) if not _is_missing(v) else None
            elif target_type == "boolean":
                for r in rows:
                    v = r.get(column)
                    r[column] = _to_bool(v)

    elif op_type == "normalize":
        for col in op_columns:
            if col in columns:
                _normalize_column(rows, col, standardize=False)

    elif op_type == "standardize":
        for col in op_columns:
            if col in columns:
                _normalize_column(rows, col, standardize=True)

    elif op_type == "encode":
        encoding = operation.get("encoding", "one_hot")
        if column and column in columns:
            if encoding == "one_hot":
                columns, rows = _one_hot_encode(columns, rows, column)
            elif encoding == "label":
                codes = _label_encode([str(r.get(column)) for r in rows])
                for i, r in enumerate(rows):
                    r[column] = codes[i]

    elif op_type == "drop_duplicates":
        subset = op_columns or None
        seen = set()
        deduped = []
        for r in rows:
            if subset:
                key = tuple(repr(r.get(c)) for c in subset)
            else:
                key = tuple((k, repr(r.get(k))) for k in sorted(r.keys()))
            if key not in seen:
                seen.add(key)
                deduped.append(r)
        rows = deduped

    elif op_type == "drop_columns":
        existing_cols = [col for col in op_columns if col in columns]
        if existing_cols:
            columns = [c for c in columns if c not in existing_cols]
            for r in rows:
                for c in existing_cols:
                    r.pop(c, None)

    elif op_type == "rename_column":
        new_name = operation.get("new_name")
        if column and new_name and column in columns:
            columns = [new_name if c == column else c for c in columns]
            for r in rows:
                r[new_name] = r.pop(column)

    return columns, rows




def _label_encode(values) -> list:
    """Map each categorical value to an integer code in sorted unique-value order.

    Matches sklearn.preprocessing.LabelEncoder.fit_transform (which sorts the
    unique values). Sorted order is deliberate — the Go port mirrors it.
    """
    unique = sorted(set(values))
    code = {v: i for i, v in enumerate(unique)}
    return [code[v] for v in values]




def _sanitize_df_dict(data: dict) -> dict:
    """Replace None/NaN/Inf with None in a column-oriented dict."""
    for col, values in data.items():
        data[col] = [None if _is_missing(v) else v for v in values]
    return data




def _column_oriented_dict(columns, rows):
    """Build a sanitized column-oriented preview dict ``{col: [values]}``."""
    data = {col: [] for col in columns}
    for r in rows:
        for col in columns:
            data[col].append(r.get(col))
    return _sanitize_df_dict(data)




async def preview_preparation_rule(
    db_pool: asyncpg.Pool,
    preparation_rule_id: str,
    columns: List[str],
    rows: List[Dict[str, Any]],
    limit: int = 10,
    language: str = "en"
) -> Dict[str, Any]:
    """
    Preview the effect of a preparation rule on a table of rows.

    Args:
        db_pool: Database connection pool
        preparation_rule_id: The preparation rule ID
        columns: The column names in order
        rows: The rows as a list of plain dicts
        limit: Number of rows to preview
        language: User's language for error messages

    Returns:
        Dict containing original and transformed data previews
    """
    # Get the rule
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT name, operations
            FROM "DataPreparationRule"
            WHERE id = $1
            """,
            preparation_rule_id
        )

        if row is None:
            raise ValueError(
                await t(db_pool, language, error_preparation_rule_not_found_2,
                    id=preparation_rule_id
                )
            )

        operations = row["operations"]

    # Apply operations to a copy of the data
    transformed_columns = list(columns)
    transformed_rows = [dict(r) for r in rows]
    for op in operations:
        transformed_columns, transformed_rows = await _apply_operation(
            transformed_columns, transformed_rows, op
        )

    # Get preview data (sanitize NaN/Inf for JSON)
    original_preview = _column_oriented_dict(columns, rows[:limit])
    transformed_preview = _column_oriented_dict(transformed_columns, transformed_rows[:limit])

    return {
        "rule_name": row["name"],
        "original": {
            "rows": len(rows),
            "columns": list(columns),
            "preview": original_preview
        },
        "transformed": {
            "rows": len(transformed_rows),
            "columns": transformed_columns,
            "preview": transformed_preview
        },
        "row_count_before": len(rows),
        "row_count_after": len(transformed_rows),
        "rows_removed": len(rows) - len(transformed_rows)
    }




async def _asyncpg_columns(conn, sql, result):
    """Column names for an asyncpg result (empty-safe via prepare)."""
    if result:
        return [str(k) for k in result[0].keys()]
    stmt = await conn.prepare(sql)
    return [str(a.name) for a in stmt.get_attributes()]


async def _asyncpg_declared_types(conn, sql) -> Dict[str, str]:
    """{column_name: declared type name} for `sql`, from a prepared statement.

    `asyncpg.types.Attribute` carries both the attribute name and its type, and
    `Type.name` is PostgreSQL's internal type name — "int4", "varchar" — which
    is what the value-based inference cannot see. Costs one extra round trip
    per query.

    Returns ``{}`` when the statement cannot be prepared: the caller then falls
    back to inferring types from the decoded values, which is what every column
    did before this helper existed, so an unprepared or exotic statement keeps
    the previous behaviour rather than failing.
    """
    try:
        stmt = await conn.prepare(sql)
        return {str(a.name): str(a.type.name) for a in stmt.get_attributes()}
    except Exception:
        return {}


# MySQL column type code → the PostgreSQL internal type name _PG_DECLARED_TYPES
# is keyed by. aiomysql reports MySQL's FIELD_TYPE_* at description[i][1]; the Go
# side reads go-sql-driver's spelling ("INT"). Two tables, one target, so a
# MySQL column lands as the same PostgreSQL type whichever backend federated it.
#
# Only the numeric and temporal families are mapped, because they are where the
# code says something the decoded value cannot: an integer's width, a FLOAT from
# a DOUBLE, a DATE from a DATETIME. They are also where inference disagrees today
# — a DECIMAL reaches Go as []byte, and a TIME as a string — so mapping them
# removes a divergence rather than adding one.
#
# The string/blob family is deliberately absent. MySQL gives TEXT and BLOB the
# same code (252), and VAR_STRING covers both VARCHAR and VARBINARY, so the code
# cannot say which side of the text/binary line a column is on — while value
# inference can, from whether the driver handed back str or bytes. Mapping it
# would have to pick one and both choices break something. Absent on both sides,
# the family keeps inference, which is right and identical.
_MYSQL_FIELD_TYPES = {
    1: "int2",         # TINY
    2: "int2",         # SHORT
    9: "int4",         # INT24 (MEDIUMINT)
    3: "int4",         # LONG
    8: "int8",         # LONGLONG
    4: "float4",       # FLOAT
    5: "float8",       # DOUBLE
    0: "numeric",      # DECIMAL
    246: "numeric",    # NEWDECIMAL
    10: "date",        # DATE
    14: "date",        # NEWDATE
    12: "timestamp",   # DATETIME
    7: "timestamptz",  # TIMESTAMP
    11: "time",        # TIME
}


def _mysql_declared_types(cursor) -> Dict[str, str]:
    """{column_name: declared type name} for a MySQL result.

    Reads MySQL's own type code from ``cursor.description[i][1]`` and turns it
    into the PostgreSQL internal name the shared declared-type map knows. A code
    this table does not hold is simply left out, so that column keeps value
    inference — the same fallback an unmapped PostgreSQL type gets.
    """
    if not cursor.description:
        return {}
    out: Dict[str, str] = {}
    for desc in cursor.description:
        pg_name = _MYSQL_FIELD_TYPES.get(desc[1])
        if pg_name:
            out[str(desc[0])] = pg_name
    return out


# MS SQL column type name → the PostgreSQL internal type name the shared map is
# keyed by. Unlike MySQL that name does not come from the driver: pymssql's
# ``description[i][1]`` is a coarse DB-API type (STRING/NUMBER/DATETIME/…), not
# the declared type — measured 2026-10-11, which is why this branch asks the
# server instead of reading metadata the way the other drivers do.
#
# `sys.dm_exec_describe_first_result_set` (SQL Server 2012+) reports SQL Server's
# own `system_type_name` — "int", "decimal(18,2)", "nvarchar(50)" — which is the
# same vocabulary go-mssqldb hands the Go side, so `mssqlDeclaredTypes` and this
# table are the same list: the two sides agree by construction rather than by a
# hand-check, and neither has to resolve FreeTDS's nullable wrappers from a byte
# size.
#
# The parenthesised length is dropped, because the PostgreSQL word carries none.
# The binary family is absent, as it is on the Go side; and SQL Server's
# `timestamp` is deliberately *not* here — it is an alias for `rowversion`, a
# binary type, not a date, so mapping it to TIMESTAMP would be wrong.
_MSSQL_TYPE_NAMES = {
    "TINYINT": "int2", "SMALLINT": "int2", "INT": "int4", "BIGINT": "int8",
    "REAL": "float4", "FLOAT": "float8",
    "DECIMAL": "numeric", "NUMERIC": "numeric", "MONEY": "numeric", "SMALLMONEY": "numeric",
    "BIT": "bool",
    "SMALLDATETIME": "timestamp", "DATETIME": "timestamp", "DATETIME2": "timestamp",
    "DATETIMEOFFSET": "timestamptz",
    "DATE": "date", "TIME": "time",
    "VARCHAR": "text", "NVARCHAR": "text", "CHAR": "text", "NCHAR": "text",
    "TEXT": "text", "NTEXT": "text",
}


def _mssql_declared_types(cursor, sql: str) -> Dict[str, str]:
    """{column_name: declared type name} for an MS SQL result, asked of the server.

    Runs `sys.dm_exec_describe_first_result_set` over the same SQL through the same
    cursor — one extra round trip, the same order of cost as the other drivers
    reading their own metadata — and maps each column's `system_type_name` through
    `_MSSQL_TYPE_NAMES`. The SQL is bound as a parameter, never interpolated.

    Returns ``{}`` when the DMV cannot describe the statement, or when the type has
    no counterpart: the caller then keeps value inference, the fallback an unmapped
    declared type gets everywhere else.
    """
    if not sql:
        return {}
    try:
        cursor.execute(
            "SELECT name, system_type_name "
            "FROM sys.dm_exec_describe_first_result_set(%s, NULL, 0)",
            (sql,),
        )
        described = cursor.fetchall() or []
    except Exception:
        return {}
    out: Dict[str, str] = {}
    for row in described:
        base = str(row[1] or "").split("(", 1)[0].strip().upper()
        pg_name = _MSSQL_TYPE_NAMES.get(base)
        if pg_name:
            out[str(row[0])] = pg_name
    return out


def _psycopg2_declared_types(cur) -> Dict[str, str]:
    """{column_name: declared type name} for a psycopg2 result — the Access path.

    psycopg2 reports each column's declared type as a PostgreSQL OID in
    ``description[i][1]`` (asyncpg hands back the type name directly; pgx
    resolves the OID from its own map), so the OID is turned into the PostgreSQL
    internal type name ("int4", "varchar", "date") through the server's own
    ``pg_type`` catalogue — one lookup for the whole result. That keeps the
    vocabulary identical to what the Go side reads from pgx, with no second
    static table to keep in step. An OID the catalogue does not hold, or a lookup
    that fails, is simply left out, so that column keeps value inference — the
    same fallback an unmapped type gets.

    Re-executes ``cur`` for the lookup, so read any rows before calling it; the
    column descriptions are captured first, so this is safe after ``fetchall``.
    """
    descs = cur.description
    if not descs:
        return {}
    oids = sorted({desc[1] for desc in descs if desc[1] is not None})
    if not oids:
        return {}
    try:
        cur.execute("SELECT oid, typname FROM pg_type WHERE oid = ANY(%s)", (oids,))
        names = {int(o): str(n) for o, n in cur.fetchall()}
    except Exception:
        return {}
    out: Dict[str, str] = {}
    for desc in descs:
        name = names.get(int(desc[1])) if desc[1] is not None else None
        if name:
            out[str(desc[0])] = name
    return out


#: Used when the caller supplies no deadline and the settings row cannot be read.
#: The same number as GlobalSettings.defaultConnectTimeoutSeconds, so falling back
#: here is not a second policy — it is the value an unreadable settings row would
#: have given.
DEFAULT_CONNECT_TIMEOUT_SECONDS = 10


def error_text(exc: BaseException) -> str:
    """A message that is never empty.

    `str(TimeoutError())` is `""`, and an asyncio connect that hits its deadline
    raises exactly that. Interpolated into a translated message with `{error}` it
    produced *"Could not load schema: "* and nothing after it — measured
    2026-11-06, a 60-second hang with an empty explanation. Naming the class is
    the minimum a caller needs to know which failure happened.
    """
    text = str(exc).strip()
    return text or type(exc).__name__


async def execute_connection_sql_rows(sql: str, conn_details: dict, db_pool, language: str = "en",
                                      connect_timeout: float | None = None):
    """Run `sql` against an external connection.

    Returns ``(columns, rows, declared_types)``. `conn_details` must include
    type/host/port/database/username and a decrypted password. Rows are plain
    dicts.

    `connect_timeout` bounds *reaching* the host, and every driver gets it. It was
    absent until 2026-11-06: the PostgreSQL path called `asyncpg.connect(conn_str)`
    with no timeout at all, so a blocked host cost asyncpg's own 60-second default
    for each source in turn — and a dataset with seven sources could sit for seven
    minutes before failing.

    `declared_types` maps a column name to the source's declared type name, so a
    caller that lands these rows into PostgreSQL can type the columns from the
    source instead of guessing from decoded values. Every driver supplies it:
    asyncpg and psycopg2 read a PostgreSQL OID, aiomysql reads MySQL's type code,
    and pymssql asks the server (see the module's per-driver helpers). A driver
    that cannot name a column leaves it out of the map, and that column keeps
    value inference.
    """
    import asyncio
    import aiomysql

    conn_type = conn_details["type"]
    password = conn_details["password"]

    # PostgreSQL
    if conn_type == "postgresql":
        conn_str = (
            f"postgresql://{conn_details['username']}:{password}"
            f"@{conn_details['host']}:{conn_details['port']}/{conn_details['database']}"
        )
        deadline = connect_timeout or DEFAULT_CONNECT_TIMEOUT_SECONDS
        try:
            ext_conn = await asyncpg.connect(conn_str, timeout=deadline)
        except Exception as e:
            # `error.connection.connect_failed` reads "MySQL connection failed",
            # which was wrong here — this branch is PostgreSQL. This key names no
            # driver, so it is right for every one of them.
            raise ValueError(
                await t(db_pool, language, DATASETS["database.connection_failed"],
                        error=error_text(e))
            )
        try:
            result = await ext_conn.fetch(sql)
            columns = await _asyncpg_columns(ext_conn, sql, result)
            declared_types = await _asyncpg_declared_types(ext_conn, sql)
            rows = [dict(r) for r in result]
            await ext_conn.close()
            return columns, rows, declared_types
        except Exception as e:
            await ext_conn.close()
            raise ValueError(
                await t(db_pool, language, error_connection_query_failed_3,
                        error=error_text(e))
            )

    # MySQL
    elif conn_type == "mysql":
        try:
            mysql_conn = await aiomysql.connect(
                host=conn_details["host"],
                port=conn_details["port"],
                db=conn_details["database"],
                user=conn_details["username"],
                password=password,
                # The compiled default, not the resolved value: Go's MySQL DSN
                # carries a hard-coded `timeout=10s` and the two sides must agree.
                # Only PostgreSQL takes the resolved setting, because it is the
                # one that was unbounded.
                connect_timeout=DEFAULT_CONNECT_TIMEOUT_SECONDS,
            )
        except Exception as e:
            raise ValueError(
                await t(db_pool, language, error_connection_connect_failed,
                        error=error_text(e))
            )
        try:
            cursor = await mysql_conn.cursor()
            await cursor.execute(sql)
            result = await cursor.fetchall()
            col_names = [desc[0] for desc in cursor.description]
            declared_types = _mysql_declared_types(cursor)
            rows = [dict(zip(col_names, r)) for r in result]
            await cursor.close()
            mysql_conn.close()
            return [str(c) for c in col_names], rows, declared_types
        except Exception as e:
            mysql_conn.close()
            raise ValueError(
                await t(db_pool, language, error_connection_query_failed_4,
                        error=error_text(e))
            )

    # MSSQL
    elif conn_type == "mssql":
        import pymssql
        def _mssql_query():
            c = pymssql.connect(
                server=conn_details["host"],
                port=conn_details["port"],
                user=conn_details["username"],
                password=password,
                database=conn_details["database"],
                login_timeout=DEFAULT_CONNECT_TIMEOUT_SECONDS,
            )
            try:
                cursor = c.cursor()
                cursor.execute(sql)
                result = cursor.fetchall()
                col_names = [desc[0] for desc in cursor.description]
                declared_types = _mssql_declared_types(cursor, sql)
                rows = [dict(zip(col_names, row)) for row in result]
                c.close()
                return rows, col_names, declared_types
            except Exception:
                c.close()
                raise
        try:
            rows, col_names, declared_types = await asyncio.to_thread(_mssql_query)
            return [str(c) for c in col_names], rows, declared_types
        except Exception as e:
            raise ValueError(
                await t(db_pool, language, error_connection_query_failed_5,
                        error=error_text(e))
            )

    # Access via msaccess-endpoint-ng
    elif conn_type == "access":
        import psycopg2
        access_path = conn_details["database"]
        host = conn_details.get("host", "127.0.0.1")
        port = conn_details.get("port", 9432)
        user = conn_details.get("username", "admin")
        password = conn_details.get("password", "admin")
        try:
            conn = psycopg2.connect(
                host=host, port=port, user=user, password=password,
                dbname=access_path,
                connect_timeout=DEFAULT_CONNECT_TIMEOUT_SECONDS,
            )
            cur = conn.cursor()
            cur.execute(sql)
            col_names = [desc[0] for desc in cur.description] if cur.description else []
            rows = cur.fetchall()
            declared_types = _psycopg2_declared_types(cur)
            cur.close()
            conn.close()
            return [str(c) for c in col_names], [dict(zip(col_names, r)) for r in rows], declared_types
        except Exception as e:
            raise ValueError(
                await t(db_pool, language, error_connection_query_failed_6,
                        error=error_text(e))
            )

    else:
        raise ValueError(
            await t(db_pool, language, error_connection_type_not_supported_3, type=conn_type)
        )




async def execute_compiled_sql_rows(
    sql: str,
    db_pool,
    user_id: str,
    dataset_id: str,
    language: str = "en",
):
    """Execute a compiled SQL SELECT on the dataset's native backend, return rows.

    Returns ``(columns, rows, declared_types)`` where ``columns`` is a list of
    column-name strings in SELECT order, ``rows`` is a list of plain dicts (no
    pandas), and ``declared_types`` maps a column name to the source's declared
    type name where the backend can name it (see
    :func:`execute_connection_sql_rows`; ``{}`` otherwise).

    Routes to PostgreSQL (asyncpg), MySQL (aiomysql),
    MSSQL (pymssql), or Access (msaccess-endpoint-ng) based on the dataset's storageType.
    """
    # Get dataset metadata
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT "sourceType", "storageType", "sourceConnectionId", "databaseName", "tableName"
            FROM "UserDataset"
            WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (SELECT "userGroup" FROM "User" WHERE id = $2)))
            """,
            dataset_id, user_id
        )

    if row is None:
        raise ValueError(
            await t(db_pool, language, error_dataset_not_found_2, id=dataset_id)
        )

    storage_type = row["storageType"]
    source_type = row["sourceType"]
    source_connection_id = row["sourceConnectionId"]

    # PostgreSQL (workbench_data) — uploaded / notebook datasets
    if source_type in ("upload", "notebook") and storage_type == "postgresql":
        data_pool = get_data_pool()
        if data_pool is None:
            raise ValueError(
                await t(db_pool, language, error_dataset_load_failed_2,
                    error="workbench_data pool not initialised")
            )
        try:
            async with data_pool.acquire() as conn:
                result = await conn.fetch(sql)
                columns = await _asyncpg_columns(conn, sql, result)
                declared_types = await _asyncpg_declared_types(conn, sql)
                return columns, [dict(r) for r in result], declared_types
        except Exception as e:
            raise ValueError(
                await t(db_pool, language, error_connection_query_failed_2, error=str(e))
            )

    # Virtual dataset — the caller materialised it to virtual_{id}; execute the
    # compiled SQL against that workbench_data table.
    if source_type == "virtual":
        data_pool = get_data_pool()
        if data_pool is None:
            raise ValueError(
                await t(db_pool, language, error_dataset_load_failed_2,
                    error="workbench_data pool not initialised")
            )
        try:
            async with data_pool.acquire() as conn:
                result = await conn.fetch(sql)
                columns = await _asyncpg_columns(conn, sql, result)
                declared_types = await _asyncpg_declared_types(conn, sql)
                return columns, [dict(r) for r in result], declared_types
        except Exception as e:
            raise ValueError(
                await t(db_pool, language, error_connection_query_failed_2, error=str(e))
            )

    # External databases
    conn_details = await get_connection_row(source_connection_id, user_id, language)
    if conn_details is None:
        raise ValueError(await t(db_pool, language, error_define_connection_not_found_2))
    conn_details["password"] = decrypt_field(conn_details["password"])
    return await execute_connection_sql_rows(sql, conn_details, db_pool, language)
