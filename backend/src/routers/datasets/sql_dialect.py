"""
SQL Dialect Helpers — Phase 5.1 + 5.2

Moved from recipes/sql_compiler.py so both datasets and recipes can import it
without a cycle.

Compiles transform operations into backend-native SQL SELECT statements.
Supports PostgreSQL, MySQL, MSSQL, and Access/Jet dialects.

Phase 5.1 — Universal operations (all backends):
  filter          → WHERE clause
  drop_column     → omit from SELECT list
  rename_column   → AS alias
  convert_type    → CAST
  fill_missing (constant) → COALESCE
  fill_missing (drop)     → WHERE IS NOT NULL

Phase 5.2 — Capability matrix & split-point engine:
  Determines which operations each backend can execute in SQL.
  Splits operation list into SQL-pushdown and Python-fallback phases.
  Dialect translation: LIMIT/TOP, identifier quoting.
"""

from typing import List, Dict, Any


# ============================================================
# DIALECT HELPERS
# ============================================================

def quote_identifier(name: str, storage_type: str) -> str:
    """Quote a column or table name per the backend dialect.

    ``access`` is quoted the PostgreSQL way: the Jet/ACE endpoint that once
    spoke Jet dialect (and accepted ``[name]``) has been retired, and its
    replacement -- ``msaccess-endpoint-ng`` -- is a true PostgreSQL engine, so
    an Access source now takes the PostgreSQL dialect on every SQL construct.
    """
    if storage_type in ("postgresql", "access"):
        return f'"{name}"'
    elif storage_type == "mysql":
        return f"`{name}`"
    elif storage_type == "mssql":
        return f"[{name}]"
    else:
        return name


def quote_table(name: str, storage_type: str) -> str:
    """Quote a (possibly schema-qualified) table name per the backend dialect.

    PostgreSQL table names may be schema-qualified
    (``schema.table``, e.g. a notebook import's ``nb_<import_id>.df_0``); those
    are quoted as two identifiers. Bare names fall through to
    :func:`quote_identifier`.
    """
    if storage_type in ("postgresql", "access") and "." in name:
        schema, _, table = name.partition(".")
        return f'"{schema}"."{table}"'
    return quote_identifier(name, storage_type)


def sql_cast(expr: str, target_type: str, storage_type: str) -> str:
    """Generate a CAST expression per dialect."""
    type_map = {
        "numeric": {"postgresql": "NUMERIC", "mysql": "DECIMAL(65,30)", "access": "NUMERIC", "mssql": "FLOAT"},
        "integer": {"postgresql": "BIGINT", "mysql": "BIGINT", "access": "BIGINT", "mssql": "BIGINT"},
        "datetime": {"postgresql": "TIMESTAMP", "mysql": "DATETIME", "access": "TIMESTAMP", "mssql": "DATETIME"},
        "string": {"postgresql": "VARCHAR", "mysql": "CHAR", "access": "VARCHAR", "mssql": "NVARCHAR(255)"},
        "boolean": {"postgresql": "BOOLEAN", "mysql": "BOOLEAN", "access": "BOOLEAN", "mssql": "BIT"},
    }
    sql_type = type_map.get(target_type, {}).get(storage_type, "VARCHAR")

    return f"CAST({expr} AS {sql_type})"


def sql_coalesce(col_expr: str, value: Any, storage_type: str) -> str:
    """Generate COALESCE(col, value) — universal across all 4 backends."""
    val_str = sql_literal(value, storage_type)
    return f"COALESCE({col_expr}, {val_str})"


def sql_literal(value: Any, storage_type: str) -> str:
    """Convert a Python value to a SQL literal."""
    if value is None:
        return "NULL"
    if isinstance(value, bool):
        if storage_type in ("postgresql", "access"):
            return "TRUE" if value else "FALSE"
        elif storage_type in ("mysql", "mssql"):
            return "1" if value else "0"
        else:
            return "true" if value else "false"
    if isinstance(value, (int, float)):
        return str(value)
    # String — escape single quotes
    escaped = str(value).replace("'", "''")
    return f"'{escaped}'"


# ============================================================
# CAPABILITY MATRIX (Phase 5.2)
# ============================================================

# Operations each backend can execute in SQL.
# True = can push to SQL. False = must fall back to Python.
CAPABILITY_MATRIX = {
    "postgresql": {
        "filter": True,
        "drop_column": True,
        "rename_column": True,
        "convert_type": True,
        "fill_missing": True,
        "normalize": True,
        "standardize": True,
        "encode": True,
        "drop_duplicates": True,
    },
    "mysql": {
        "filter": True,
        "drop_column": True,
        "rename_column": True,
        "convert_type": True,
        "fill_missing": True,
        "normalize": True,
        "standardize": True,
        "encode": True,
        "drop_duplicates": True,
    },
    "access": {
        "filter": True,
        "drop_column": True,
        "rename_column": True,
        "convert_type": True,
        "fill_missing": False,      # No COALESCE — only constant/drop via WHERE IS NULL
        "normalize": False,
        "standardize": False,
        "encode": False,
        "drop_duplicates": False,
    },
    "mssql": {
        "filter": True,
        "drop_column": True,
        "rename_column": True,
        "convert_type": True,
        "fill_missing": True,
        "normalize": True,
        "standardize": True,
        "encode": True,
        "drop_duplicates": True,
    },
}


def backend_can_execute(op_type: str, storage_type: str) -> bool:
    """Check if the backend can execute this operation type in SQL."""
    caps = CAPABILITY_MATRIX.get(storage_type, {})
    return caps.get(op_type, False)


def split_operations(
    operations: List[Dict[str, Any]],
    storage_type: str,
) -> tuple:
    """
    Split operations into SQL-pushdown and Python-fallback phases.

    Returns:
        (sql_ops, python_ops) — two lists of operations.
        sql_ops: operations the backend can execute in SQL (consecutive from start).
        python_ops: remaining operations that must run in Python.
    """
    sql_ops = []
    python_ops = []
    in_fallback = False

    for op in operations:
        op_type = op.get("type", "")

        # Map legacy operation type names
        if op_type == "drop_columns":
            op_type = "drop_column"
        elif op_type == "encode_category":
            op_type = "encode"

        # fill_missing with method "constant" or "drop" is universal even for Access
        if op_type == "fill_missing" and storage_type == "access":
            method = op.get("method", "constant")
            if method in ("constant", "drop"):
                sql_ops.append(op)
                continue
            else:
                in_fallback = True

        if not in_fallback and backend_can_execute(op_type, storage_type):
            sql_ops.append(op)
        else:
            in_fallback = True
            python_ops.append(op)

    return sql_ops, python_ops


# ============================================================
# DIALECT CONSTRUCTS (Phase 5.2)
# ============================================================

def sql_limit(storage_type: str, limit: int) -> str:
    """Generate a LIMIT/TOP clause for the backend dialect."""
    if storage_type == "mssql":
        return f"TOP {limit}"
    else:
        # PostgreSQL (and access, now a true PostgreSQL engine) use LIMIT
        return f"LIMIT {limit}"


def wrap_with_limit(sql: str, storage_type: str, limit: int) -> str:
    """Wrap a SELECT statement with the backend's LIMIT/TOP syntax."""
    if storage_type == "mssql":
        # MSSQL uses SELECT TOP N, not SELECT ... LIMIT N
        return sql.replace("SELECT", f"SELECT TOP {limit}", 1)
    else:
        return f"{sql}\nLIMIT {limit}"


# ============================================================
# SQL COMPILER
# ============================================================

def compile_sql(
    operations: List[Dict[str, Any]],
    storage_type: str,
    table_name: str,
    all_columns: List[str],
) -> str:
    """
    Compile a list of transform operations into a backend-native SELECT.

    Args:
        operations: List of operation dicts (type, column, operator, value, etc.)
        storage_type: Backend type ('postgresql', 'mysql', 'mssql', 'access')
        table_name: Source table name
        all_columns: Column names in the source table (for building the initial SELECT list)

    Returns:
        A complete SQL SELECT statement
    """
    q = lambda name: quote_identifier(name, storage_type)

    # Active column tracking: {original_name: current_expression}
    # Start with all columns as-is (or SELECT * if columns are unknown)
    if not all_columns:
        columns: Dict[str, str] = {"*": "*"}
    else:
        columns: Dict[str, str] = {col: q(col) for col in all_columns}

    where_clauses: List[str] = []

    for op in operations:
        op_type = op.get("type", "")

        if op_type == "filter":
            clause = _compile_filter(op, columns, q, storage_type)
            if clause:
                where_clauses.append(clause)

        elif op_type in ("drop_column", "drop_columns"):
            # Canonical "drop_columns" takes a columns list; legacy "drop_column" a single column.
            cols_to_drop = op.get("columns") or ([op.get("column")] if op.get("column") else [])
            for col in cols_to_drop:
                if col and col in columns:
                    del columns[col]

        elif op_type == "rename_column":
            col = op.get("column")
            new_name = op.get("new_name")
            if col and new_name and col in columns:
                current_expr = columns[col]
                del columns[col]
                columns[new_name] = f"{current_expr} AS {q(new_name)}"

        elif op_type == "convert_type":
            col = op.get("column")
            target = op.get("target_type", "numeric")
            if col and col in columns:
                current_expr = columns[col]
                columns[col] = sql_cast(current_expr, target, storage_type)

        elif op_type == "fill_missing":
            col = op.get("column")
            method = op.get("method", "constant")
            if not col or col not in columns:
                continue

            if method == "drop":
                current_expr = columns[col]
                where_clauses.append(f"{current_expr} IS NOT NULL")
            elif method == "constant":
                current_expr = columns[col]
                value = op.get("value", 0)
                columns[col] = sql_coalesce(current_expr, value, storage_type)
            elif method == "mean":
                current_expr = columns[col]
                q_col = q(col)
                subq = f"(SELECT AVG({q_col}) FROM {quote_table(table_name, storage_type)})"
                columns[col] = f"COALESCE({current_expr}, {subq})"
            elif method == "median":
                current_expr = columns[col]
                q_col = q(col)
                if storage_type == "mysql":
                    subq = f"(SELECT {q_col} FROM {quote_table(table_name, storage_type)} ORDER BY {q_col} LIMIT 1 OFFSET (SELECT COUNT(*) FROM {quote_table(table_name, storage_type)})/2)"
                else:
                    subq = f"(SELECT PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {q_col}) FROM {quote_table(table_name, storage_type)})"
                columns[col] = f"COALESCE({current_expr}, {subq})"
            elif method == "mode":
                current_expr = columns[col]
                q_col = q(col)
                subq = f"(SELECT {q_col} FROM {quote_table(table_name, storage_type)} GROUP BY {q_col} ORDER BY COUNT(*) DESC LIMIT 1)"
                columns[col] = f"COALESCE({current_expr}, {subq})"

        elif op_type == "drop_duplicates":
            # Track that we need DISTINCT — handled at SELECT build time
            columns["__drop_duplicates__"] = "1"

        elif op_type in ("encode", "encode_category"):
            col = op.get("column")
            encoding = op.get("encoding", "label")
            if not col or col not in columns:
                continue

            if encoding == "label":
                current_expr = columns[col]
                encoded_name = f"{col}_encoded"
                q_col = q(col)
                if storage_type == "mysql":
                    columns[encoded_name] = (
                        f"DENSE_RANK() OVER (ORDER BY {current_expr}) - 1 AS {q(encoded_name)}"
                    )
                else:
                    columns[encoded_name] = (
                        f"DENSE_RANK() OVER (ORDER BY {current_expr}) - 1 AS {q(encoded_name)}"
                    )
                # Keep original column
            elif encoding == "one_hot":
                # One-hot: CASE WHEN col = level THEN 1 ELSE 0 END per distinct
                # level. Levels are injected by the caller (op["levels"]).
                levels = op.get("levels") or []
                if not levels:
                    continue
                current_expr = columns[col]
                for level in levels:
                    dummy_name = f"{col}_{level}"
                    lit = sql_literal(level, storage_type)
                    columns[dummy_name] = (
                        f"CASE WHEN {current_expr} = {lit} THEN 1 ELSE 0 END AS {q(dummy_name)}"
                    )
                # Drop the original column (matches pd.get_dummies).
                del columns[col]

        elif op_type in ("normalize", "standardize"):
            # Canonical: type determines the method — "normalize" = min-max,
            # "standardize" = z-score. Columns arrive as a list.
            target_cols = op.get("columns", [])
            method = "minmax" if op_type == "normalize" else "zscore"

            for col in target_cols:
                if not col or col not in columns:
                    continue
                current_expr = columns[col]
                if method == "zscore":
                    # (col - AVG(col) OVER()) / NULLIF(STDDEV(col) OVER(), 0)
                    columns[col] = (
                        f"({current_expr} - AVG({current_expr}) OVER()) / "
                        f"NULLIF(STDDEV({current_expr}) OVER(), 0)"
                    )
                elif method == "minmax":
                    # (col - MIN(col) OVER()) / NULLIF(MAX(col) OVER() - MIN(col) OVER(), 0)
                    columns[col] = (
                        f"({current_expr} - MIN({current_expr}) OVER()) / "
                        f"NULLIF(MAX({current_expr}) OVER() - MIN({current_expr}) OVER(), 0)"
                    )

    # Handle drop_duplicates: the sentinel only marks DISTINCT and must not
    # leak into the SELECT list, so pop it before building select_cols.
    has_distinct = "__drop_duplicates__" in columns
    columns.pop("__drop_duplicates__", None)

    # Build SELECT list preserving original order
    select_cols = []
    for col in all_columns:
        if col in columns:
            select_cols.append(columns[col])
        # If column was renamed and removed, the new name is already in the dict
        # but won't be in all_columns. We add renamed columns at the end.
    # Add columns that exist in the dict but weren't in all_columns (renamed)
    for col, expr in columns.items():
        if col not in all_columns:
            select_cols.append(expr)

    q_table = quote_table(table_name, storage_type)
    select_clause = ",\n  ".join(select_cols)

    if has_distinct:
        sql = f"SELECT DISTINCT\n  {select_clause}\nFROM {q_table}"
    else:
        sql = f"SELECT\n  {select_clause}\nFROM {q_table}"

    if where_clauses:
        sql += "\nWHERE " + "\n  AND ".join(where_clauses)

    return sql


def _coerce_value(value: Any) -> Any:
    """Try to convert string values to numbers for SQL comparisons."""
    if not isinstance(value, str):
        return value
    # Try int first, then float
    try:
        return int(value)
    except (ValueError, TypeError):
        pass
    try:
        return float(value)
    except (ValueError, TypeError):
        pass
    return value


def _compile_filter(
    op: Dict[str, Any],
    columns: Dict[str, str],
    q,
    storage_type: str,
) -> str | None:
    """Compile a single filter operation to a WHERE clause fragment."""
    col = op.get("column")
    operator = op.get("operator", "=")
    value = op.get("value")

    if not col:
        return None

    if col in columns:
        col_expr = columns[col]
    else:
        # Column not in tracking dict (e.g. SELECT * mode) — use quoted name
        col_expr = q(col)

    if operator == "is_null":
        return f"{col_expr} IS NULL"

    if operator == "is_not_null":
        return f"{col_expr} IS NOT NULL"

    if value is None:
        return None

    # "in" takes a list of values.
    if operator == "in":
        if isinstance(value, list) and value:
            vals = ", ".join(sql_literal(_coerce_value(v), storage_type) for v in value)
            return f"{col_expr} IN ({vals})"
        return None

    # Try numeric conversion for comparison operators
    typed_value = _coerce_value(value)

    if operator == ">":
        return f"{col_expr} > {sql_literal(typed_value, storage_type)}"
    elif operator == ">=":
        return f"{col_expr} >= {sql_literal(typed_value, storage_type)}"
    elif operator == "<":
        return f"{col_expr} < {sql_literal(typed_value, storage_type)}"
    elif operator == "<=":
        return f"{col_expr} <= {sql_literal(typed_value, storage_type)}"
    elif operator in ("=", "=="):
        return f"{col_expr} = {sql_literal(typed_value, storage_type)}"
    elif operator == "!=":
        return f"{col_expr} != {sql_literal(typed_value, storage_type)}"
    elif operator == "contains":
        # LIKE with wildcards
        escaped = str(value).replace("'", "''")
        return f"{col_expr} LIKE '%{escaped}%'"
    else:
        return None
