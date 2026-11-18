"""
Schema extraction for the Database Design Assistant.
Connects to user database connections and extracts schema metadata.
"""


def _to_int(val):
    """Safely convert a value to int, handling psycopg2 string returns."""
    if val is None:
        return 0
    try:
        return int(val)
    except (ValueError, TypeError):
        return 0

import asyncio
import json
from typing import Optional, Dict, Any, List
import asyncpg
import psycopg2
import pymssql
import pymysql
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.utils.translation import t
from src.utils.encryption import decrypt_field
from src.routers.datasets.crud import (
    get_user_id_from_token,
    get_current_language,
    get_connection_row,
)
from src.routers.datasets.translations import DATASETS
from .translations import DBDESIGN_TK

router = APIRouter()
security = HTTPBearer()
_db_pool = None


def set_db_pool(pool):
    """Set the database pool for this router."""
    global _db_pool
    _db_pool = pool


# ============================================================
# POSTGRESQL SCHEMA EXTRACTION
# ============================================================

async def extract_postgresql_schema(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    language: str,
) -> Dict[str, Any]:
    """Extract complete schema from a PostgreSQL database."""
    
    pg_conn = await asyncpg.connect(
        host=host,
        port=port,
        database=database,
        user=username,
        password=password,
    )
    
    try:
        return await _extract_pg_schema_inner(pg_conn, language)
    finally:
        await pg_conn.close()


def extract_access_schema(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
) -> Dict[str, Any]:
    """Extract schema from Microsoft Access via msaccess-endpoint-ng using psycopg2.

    Uses synchronous queries (no pipelining) because the Jet/DAO engine
    is single-threaded and rejects concurrent operations.
    """
    import psycopg2.extras

    pg_conn = psycopg2.connect(
        host=host,
        port=port,
        user=username,
        password=password,
        dbname=database,
        connect_timeout=15,
    )

    try:
        cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)

        # 1. Get all user tables
        cur.execute("""
            SELECT t.table_schema, t.table_name, NULL AS comment
            FROM information_schema.tables t
            WHERE t.table_schema NOT IN ('pg_catalog', 'information_schema')
              AND t.table_type = 'BASE TABLE'
            ORDER BY t.table_schema, t.table_name
        """)
        table_rows = cur.fetchall()

        tables = []
        for trow in table_rows:
            schema_n = trow["table_schema"]
            table = trow["table_name"]

            # Get columns
            cur.execute("""
                SELECT c.column_name, c.data_type,
                    c.character_maximum_length,
                    c.is_nullable, c.column_default,
                    c.ordinal_position
                FROM information_schema.columns c
                WHERE c.table_schema = %s AND c.table_name = %s
                ORDER BY c.ordinal_position
            """, (schema_n, table))
            col_rows = cur.fetchall()

            columns = []
            for crow in col_rows:
                columns.append({
                    "name": crow["column_name"],
                    "type": crow["data_type"],
                    "max_length": _to_int(crow["character_maximum_length"]),
                    "nullable": crow["is_nullable"] == "YES",
                    "default": crow["column_default"],
                    "position": _to_int(crow["ordinal_position"]),
                    "comment": None,
                })

            # Get primary key
            cur.execute("""
                SELECT kcu.column_name
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                 AND tc.table_schema = kcu.table_schema
                WHERE tc.constraint_type = 'PRIMARY KEY'
                  AND tc.table_schema = %s AND tc.table_name = %s
                ORDER BY kcu.ordinal_position
            """, (schema_n, table))
            pk_rows = cur.fetchall()
            primary_key = [r["column_name"] for r in pk_rows]

            # Get foreign keys
            cur.execute("""
                SELECT kcu.column_name,
                    ccu.table_schema AS foreign_schema,
                    ccu.table_name AS foreign_table,
                    ccu.column_name AS foreign_column
                FROM information_schema.table_constraints tc
                JOIN information_schema.key_column_usage kcu
                  ON tc.constraint_name = kcu.constraint_name
                JOIN information_schema.constraint_column_usage ccu
                  ON tc.constraint_name = ccu.constraint_name
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = %s AND tc.table_name = %s
            """, (schema_n, table))
            fk_rows = cur.fetchall()

            foreign_keys = []
            for fkr in fk_rows:
                foreign_keys.append({
                    "column": fkr["column_name"],
                    "referenced_table": fkr["foreign_table"],
                    "referenced_column": fkr["foreign_column"],
                })

            # Get indexes
            cur.execute("""
                SELECT indexname AS name, indexdef AS definition
                FROM pg_catalog.pg_indexes
                WHERE schemaname = %s AND tablename = %s
            """, (schema_n, table))
            idx_rows = cur.fetchall()

            indexes = []
            pk_columns_set = set(primary_key)
            for idxr in idx_rows:
                is_pk = False
                if pk_columns_set:
                    for pk_col in pk_columns_set:
                        if pk_col in (idxr["definition"] or ""):
                            is_pk = True
                            break
                indexes.append({
                    "name": idxr["name"],
                    "definition": idxr["definition"],
                    "is_primary_key": is_pk,
                })

            tables.append({
                "schema": schema_n,
                "name": table,
                "comment": trow.get("comment"),
                "columns": columns,
                "primary_key": primary_key,
                "foreign_keys": foreign_keys,
                "indexes": indexes,
                "row_count": 0,
            })

        # 4. Sample text columns for semi-structured analysis
        sample_cur = pg_conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor)
        samples = _sample_text_columns_sync(sample_cur, tables, db_type="access")
        sample_cur.close()
        cur.close()

        return {
            "database_type": "Microsoft Access",
            "tables": tables,
            "total_tables": len(tables),
            "total_columns": sum(len(t["columns"]) for t in tables),
            "samples": samples,
        }

    finally:
        pg_conn.close()


async def _extract_pg_schema_inner(conn, language: str) -> Dict[str, Any]:
    """Extract PostgreSQL schema (run inside an open connection)."""
    tables = []
    warnings = []
    
    # 1. Get all user tables (exclude system schemas)
    # Use simple information_schema query (no pg_catalog joins to avoid permissions issues)
    table_rows = await conn.fetch("""
        SELECT t.table_schema, t.table_name, NULL AS comment
        FROM information_schema.tables t
        WHERE t.table_schema NOT IN ('pg_catalog', 'information_schema')
          AND t.table_type = 'BASE TABLE'
        ORDER BY t.table_schema, t.table_name
    """)
    
    # Try to get comments via pg_description (only if accessible)
    comments = await conn.fetch("""
        SELECT n.nspname AS schema_name, c.relname AS table_name, pd.description
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        LEFT JOIN pg_catalog.pg_description pd ON pd.objoid = c.oid AND pd.objsubid = 0
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema') AND c.relkind = 'r'
    """)
    comment_map = {(r['schema_name'], r['table_name']): r['description'] for r in comments}
    
    # 2. For each table, get columns, indexes, and foreign keys
    for trow in table_rows:
        schema = trow["table_schema"]
        table = trow["table_name"]
        comment = comment_map.get((schema, table))
        
        # Get columns
        columns = []
        col_rows = await conn.fetch("""
            SELECT c.column_name, c.data_type,
                c.character_maximum_length,
                c.is_nullable, c.column_default,
                c.ordinal_position, NULL AS comment
            FROM information_schema.columns c
            WHERE c.table_schema = $1 AND c.table_name = $2
            ORDER BY c.ordinal_position
        """, schema, table)
        
        for crow in col_rows:
            col_def = {
                "name": crow["column_name"],
                "type": crow["data_type"],
                "max_length": crow["character_maximum_length"],
                "nullable": crow["is_nullable"] == "YES",
                "default": crow["column_default"],
                "position": crow["ordinal_position"],
                "comment": crow["comment"],
            }
            columns.append(col_def)
        
        # Get primary key
        pk_rows = await conn.fetch("""
            SELECT kcu.column_name
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            WHERE tc.constraint_type = 'PRIMARY KEY'
              AND tc.table_schema = $1
              AND tc.table_name = $2
            ORDER BY kcu.ordinal_position
        """, schema, table)
        primary_key = [row["column_name"] for row in pk_rows]
        
        # Get foreign keys
        foreign_keys = []
        fk_rows = await conn.fetch("""
            SELECT 
                kcu.column_name,
                ccu.table_schema AS referenced_schema,
                ccu.table_name AS referenced_table,
                ccu.column_name AS referenced_column,
                tc.constraint_name,
                rc.delete_rule,
                rc.update_rule
            FROM information_schema.table_constraints tc
            JOIN information_schema.key_column_usage kcu
              ON tc.constraint_name = kcu.constraint_name
             AND tc.table_schema = kcu.table_schema
            JOIN information_schema.referential_constraints rc
              ON tc.constraint_name = rc.constraint_name
             AND tc.table_schema = rc.constraint_schema
            JOIN information_schema.key_column_usage ccu
              ON rc.unique_constraint_name = ccu.constraint_name
             AND rc.unique_constraint_schema = ccu.constraint_schema
            WHERE tc.constraint_type = 'FOREIGN KEY'
              AND tc.table_schema = $1
              AND tc.table_name = $2
        """, schema, table)
        
        for frow in fk_rows:
            fk = {
                "column": frow["column_name"],
                "referenced_schema": frow["referenced_schema"],
                "referenced_table": frow["referenced_table"],
                "referenced_column": frow["referenced_column"],
                "constraint_name": frow["constraint_name"],
                "on_delete": frow["delete_rule"],
                "on_update": frow["update_rule"],
            }
            foreign_keys.append(fk)
        
        # Get indexes
        indexes = []
        idx_rows = await conn.fetch("""
            SELECT 
                indexname,
                indexdef
            FROM pg_indexes
            WHERE schemaname = $1 AND tablename = $2
            ORDER BY indexname
        """, schema, table)
        
        pk_names = set()
        for idx_row in idx_rows:
            idx_def = idx_row["indexdef"]
            is_pk = "UNIQUE" in idx_def and "btree" in idx_def.lower()
            if "pkey" in idx_row["indexname"].lower() or "primary" in idx_row["indexname"].lower():
                is_pk = True
                pk_names.add(idx_row["indexname"])
            indexes.append({
                "name": idx_row["indexname"],
                "definition": idx_def,
                "is_primary_key": is_pk,
            })
        
        # Get row count
        row_count = await conn.fetchval(
            f'SELECT COUNT(*) FROM "{schema}"."{table}"'
        )
        
        table_info = {
            "schema": schema,
            "name": table,
            "comment": comment,
            "columns": columns,
            "primary_key": primary_key,
            "foreign_keys": foreign_keys,
            "indexes": indexes,
            "row_count": row_count,
        }
        tables.append(table_info)
    
    # 3. Sample text columns for semi-structured analysis
    samples = await _sample_text_columns(conn, tables)
    
    return {
        "database_type": "PostgreSQL",
        "tables": tables,
        "total_tables": len(tables),
        "total_columns": sum(len(t["columns"]) for t in tables),
        "samples": samples,
    }


async def _sample_text_columns(conn, tables: List[Dict]) -> Dict[str, Dict[str, List[str]]]:
    """Sample data from text/varchar columns for semantic AI analysis.

    Returns dict of {table_name: {column_name: [distinct_values]}}.
    Limited to 50 distinct values per column, max 100 characters each.
    No raw data rows exposed — only distinct, truncated samples.
    """
    samples: Dict[str, Dict[str, List[str]]] = {}
    text_types = ("text", "varchar", "char", "character")

    for table in tables:
        t_name = table.get("name", table.get("table_name", "unknown"))
        schema = table.get("schema", "public")
        col_samples: Dict[str, List[str]] = {}

        for col in table.get("columns", []):
            dtype = (col.get("type") or col.get("data_type") or "").lower()
            if not any(t in dtype for t in text_types):
                continue

            col_name = col.get("name") or col.get("column_name", "")
            if not col_name:
                continue

            try:
                rows = await conn.fetch(
                    f'SELECT DISTINCT "{col_name}" FROM "{schema}"."{t_name}" '
                    f'WHERE "{col_name}" IS NOT NULL LIMIT 50'
                )
                values = []
                for row in rows:
                    val = row[col_name]
                    if val is not None:
                        s = str(val)
                        if len(s) > 100:
                            s = s[:100]
                        if s:
                            values.append(s)
                if values:
                    col_samples[col_name] = values
            except Exception:
                pass  # Skip columns that can't be sampled

        if col_samples:
            samples[t_name] = col_samples

    return samples


def _sample_text_columns_sync(cursor, tables: List[Dict], db_type: str) -> Dict[str, Dict[str, List[str]]]:
    """Sync version of _sample_text_columns for psycopg2 (Access) and pymssql (MSSQL)."""
    samples: Dict[str, Dict[str, List[str]]] = {}

    if db_type == "mssql":
        text_types = ("varchar", "nvarchar", "char", "nchar", "text", "ntext")
        quote = ("[", "]")
        limit_clause = "TOP 50"
    else:
        text_types = ("text", "varchar", "char", "character")
        quote = ('"', '"')
        limit_clause = "LIMIT 50"

    for table in tables:
        t_name = table.get("name", table.get("table_name", "unknown"))
        schema = table.get("schema", "public") if db_type != "mssql" else table.get("schema", "dbo")
        col_samples: Dict[str, List[str]] = {}

        for col in table.get("columns", []):
            dtype = (col.get("type") or col.get("data_type") or "").lower()
            # For MSSQL: also match "nvarchar(100)", "varchar(max)" etc
            if not any(t in dtype for t in text_types):
                continue

            col_name = col.get("name") or col.get("column_name", "")
            if not col_name:
                continue

            try:
                if db_type == "mssql":
                    query = (
                        f"SELECT DISTINCT {limit_clause} "
                        f"{quote[0]}{col_name}{quote[1]} "
                        f"FROM {quote[0]}{schema}{quote[1]}.{quote[0]}{t_name}{quote[1]} "
                        f"WHERE {quote[0]}{col_name}{quote[1]} IS NOT NULL"
                    )
                else:
                    query = (
                        f'SELECT DISTINCT {quote[0]}{col_name}{quote[1]} '
                        f'FROM {quote[0]}{schema}{quote[1]}.{quote[0]}{t_name}{quote[1]} '
                        f'WHERE {quote[0]}{col_name}{quote[1]} IS NOT NULL '
                        f'{limit_clause}'
                    )
                cursor.execute(query)
                rows = cursor.fetchall()
                values = []
                for row in rows:
                    val = row[col_name] if col_name in row else list(row.values())[0] if hasattr(row, 'values') else row[0]
                    if val is not None:
                        s = str(val)
                        if len(s) > 100:
                            s = s[:100]
                        if s:
                            values.append(s)
                if values:
                    col_samples[col_name] = values
            except Exception:
                pass  # Skip columns that can't be sampled

        if col_samples:
            samples[t_name] = col_samples

    return samples


async def extract_mysql_schema(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    language: str,
) -> Dict[str, Any]:
    """Extract complete schema from a MySQL database."""
    import aiomysql
    
    mysql_conn = await aiomysql.connect(
        host=host,
        port=port,
        db=database,
        user=username,
        password=password,
    )
    
    try:
        async with mysql_conn.cursor(aiomysql.DictCursor) as cur:
            tables = []
            
            # 1. Get all user tables
            await cur.execute(
                "SELECT TABLE_SCHEMA, TABLE_NAME, TABLE_COMMENT, TABLE_ROWS "
                "FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA NOT IN ('information_schema', 'mysql', 'performance_schema', 'sys') "
                "AND TABLE_TYPE = 'BASE TABLE' "
                "AND TABLE_SCHEMA = %s "
                "ORDER BY TABLE_SCHEMA, TABLE_NAME",
                (database,)
            )
            table_rows = await cur.fetchall()
            
            # 2. For each table, get schema, columns, indexes, FKs
            for trow in table_rows:
                schema = trow["TABLE_SCHEMA"]
                table = trow["TABLE_NAME"]
                comment = trow.get("TABLE_COMMENT") or None
                row_count = trow.get("TABLE_ROWS") or 0
                
                # Get columns
                await cur.execute(
                    "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, "
                    "IS_NULLABLE, COLUMN_DEFAULT, ORDINAL_POSITION, COLUMN_COMMENT "
                    "FROM information_schema.COLUMNS "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                    "ORDER BY ORDINAL_POSITION",
                    (schema, table)
                )
                col_rows = await cur.fetchall()
                columns = []
                for crow in col_rows:
                    columns.append({
                        "name": crow["COLUMN_NAME"],
                        "type": crow["DATA_TYPE"],
                        "max_length": crow.get("CHARACTER_MAXIMUM_LENGTH"),
                        "nullable": crow["IS_NULLABLE"] == "YES",
                        "default": crow.get("COLUMN_DEFAULT"),
                        "position": crow["ORDINAL_POSITION"],
                        "comment": crow.get("COLUMN_COMMENT"),
                    })
                
                # Get primary key
                await cur.execute(
                    "SELECT COLUMN_NAME FROM information_schema.KEY_COLUMN_USAGE "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s AND CONSTRAINT_NAME = 'PRIMARY' "
                    "ORDER BY ORDINAL_POSITION",
                    (schema, table)
                )
                pk_rows = await cur.fetchall()
                primary_key = [row["COLUMN_NAME"] for row in pk_rows]
                
                # Get indexes
                await cur.execute(f"SHOW INDEX FROM `{schema}`.`{table}`")
                idx_rows = await cur.fetchall()
                indexes = []
                seen = set()
                for irow in idx_rows:
                    name = irow["Key_name"]
                    if name not in seen:
                        seen.add(name)
                        indexes.append({
                            "name": name,
                            "definition": f"INDEX {name}" if name != "PRIMARY" else "PRIMARY KEY",
                            "is_primary_key": name == "PRIMARY",
                        })
                
                tables.append({
                    "schema": schema, "name": table, "comment": comment,
                    "columns": columns, "primary_key": primary_key,
                    "foreign_keys": [], "indexes": indexes, "row_count": row_count,
                })

            # 5. Sample text columns for semi-structured analysis
            samples: Dict[str, Dict[str, List[str]]] = {}
            text_types = ("varchar", "char", "text", "tinytext", "mediumtext", "longtext")
            for table in tables:
                t_name = table["name"]
                schema = table["schema"]
                col_samples: Dict[str, List[str]] = {}
                for col in table.get("columns", []):
                    dtype = (col.get("type") or col.get("data_type") or "").lower()
                    if not any(t in dtype for t in text_types):
                        continue
                    col_name = col.get("name") or col.get("column_name", "")
                    if not col_name:
                        continue
                    try:
                        await cur.execute(
                            f"SELECT DISTINCT `{col_name}` FROM `{schema}`.`{t_name}` "
                            f"WHERE `{col_name}` IS NOT NULL LIMIT 50"
                        )
                        rows = await cur.fetchall()
                        values = []
                        for row in rows:
                            val = row[col_name]
                            if val is not None:
                                s = str(val)
                                if len(s) > 100:
                                    s = s[:100]
                                if s:
                                    values.append(s)
                        if values:
                            col_samples[col_name] = values
                    except Exception:
                        pass
                if col_samples:
                    samples[t_name] = col_samples

            return {
                "database_type": "MySQL",
                "tables": tables,
                "total_tables": len(tables),
                "total_columns": sum(len(t["columns"]) for t in tables),
                "samples": samples,
            }
    finally:
        mysql_conn.close()


async def extract_mssql_schema(
    host: str,
    port: int,
    database: str,
    username: str,
    password: str,
    language: str,
) -> Dict[str, Any]:
    """Extract complete schema from a Microsoft SQL Server database."""

    def _extract() -> Dict[str, Any]:
        conn = pymssql.connect(
            host=host, port=port, database=database,
            user=username, password=password,
        )
        try:
            cursor = conn.cursor(as_dict=True)

            # 1. Get all base tables
            cursor.execute(
                "SELECT TABLE_SCHEMA, TABLE_NAME "
                "FROM INFORMATION_SCHEMA.TABLES "
                "WHERE TABLE_TYPE = 'BASE TABLE' "
                "ORDER BY TABLE_SCHEMA, TABLE_NAME"
            )
            table_rows = cursor.fetchall()

            # 2. Get all comments (table + column) via sys.extended_properties
            cursor.execute(
                "SELECT SCHEMA_NAME(t.schema_id) AS schema_name, "
                "t.name AS table_name, NULL AS column_name, "
                "ep.value AS comment "
                "FROM sys.tables t "
                "LEFT JOIN sys.extended_properties ep "
                "  ON ep.major_id = t.object_id "
                " AND ep.minor_id = 0 "
                " AND ep.name = 'MS_Description' "
                "WHERE ep.value IS NOT NULL "
                "UNION ALL "
                "SELECT SCHEMA_NAME(t.schema_id) AS schema_name, "
                "t.name AS table_name, c.name AS column_name, "
                "ep.value AS comment "
                "FROM sys.tables t "
                "JOIN sys.columns c ON c.object_id = t.object_id "
                "LEFT JOIN sys.extended_properties ep "
                "  ON ep.major_id = t.object_id "
                " AND ep.minor_id = c.column_id "
                " AND ep.name = 'MS_Description' "
                "WHERE ep.value IS NOT NULL"
            )
            comment_rows = cursor.fetchall()
            table_comments: Dict[tuple, str] = {}
            col_comments: Dict[tuple, str] = {}
            for r in comment_rows:
                if r["column_name"] is None:
                    table_comments[(r["schema_name"], r["table_name"])] = r["comment"]
                else:
                    col_comments[(r["schema_name"], r["table_name"], r["column_name"])] = r["comment"]

            # 3. Approximate row counts via sys.partitions
            cursor.execute(
                "SELECT SCHEMA_NAME(s.schema_id) AS schema_name, "
                "t.name AS table_name, SUM(p.rows) AS row_count "
                "FROM sys.tables t "
                "JOIN sys.schemas s ON t.schema_id = s.schema_id "
                "JOIN sys.partitions p ON t.object_id = p.object_id "
                "WHERE p.index_id IN (0, 1) "
                "GROUP BY s.name, t.name, s.schema_id"
            )
            row_counts = {
                (r["schema_name"], r["table_name"]): r["row_count"]
                for r in cursor.fetchall()
            }

            tables: list = []

            for trow in table_rows:
                schema = trow["TABLE_SCHEMA"]
                table = trow["TABLE_NAME"]

                # -- Columns --
                cursor.execute(
                    "SELECT COLUMN_NAME, DATA_TYPE, CHARACTER_MAXIMUM_LENGTH, "
                    "IS_NULLABLE, COLUMN_DEFAULT, ORDINAL_POSITION "
                    "FROM INFORMATION_SCHEMA.COLUMNS "
                    "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                    "ORDER BY ORDINAL_POSITION",
                    (schema, table),
                )
                col_rows = cursor.fetchall()

                # -- Primary key --
                cursor.execute(
                    "SELECT c.name AS column_name "
                    "FROM sys.indexes i "
                    "JOIN sys.index_columns ic "
                    "  ON i.object_id = ic.object_id AND i.index_id = ic.index_id "
                    "JOIN sys.columns c "
                    "  ON ic.object_id = c.object_id AND ic.column_id = c.column_id "
                    "JOIN sys.tables t ON i.object_id = t.object_id "
                    "JOIN sys.schemas s ON t.schema_id = s.schema_id "
                    "WHERE s.name = %s AND t.name = %s "
                    "  AND i.is_primary_key = 1 "
                    "ORDER BY ic.key_ordinal",
                    (schema, table),
                )
                pk_rows = cursor.fetchall()
                primary_key = [r["column_name"] for r in pk_rows]

                columns: list = []
                for crow in col_rows:
                    col_name = crow["COLUMN_NAME"]
                    col_type = crow["DATA_TYPE"]
                    max_len = crow.get("CHARACTER_MAXIMUM_LENGTH")
                    if max_len is not None and col_type.lower() in (
                        "varchar", "nvarchar", "char", "nchar",
                        "varbinary", "binary",
                    ):
                        col_type = f"{col_type}({max_len})"

                    columns.append({
                        "name": col_name,
                        "type": col_type,
                        "nullable": crow["IS_NULLABLE"] == "YES",
                        "default": crow.get("COLUMN_DEFAULT"),
                        "is_primary_key": col_name in primary_key,
                        "comment": col_comments.get(
                            (schema, table, col_name), ""
                        ),
                    })

                # -- Foreign keys (SQL Server system catalog) --
                cursor.execute(
                    "SELECT "
                    "  col_name(fkc.parent_object_id, fkc.parent_column_id) AS column_name, "
                    "  OBJECT_NAME(fkc.referenced_object_id) AS referenced_table, "
                    "  col_name(fkc.referenced_object_id, fkc.referenced_column_id) AS referenced_column "
                    "FROM sys.foreign_key_columns fkc "
                    "JOIN sys.tables t ON fkc.parent_object_id = t.object_id "
                    "WHERE t.name = %s AND SCHEMA_NAME(t.schema_id) = %s",
                    (table, schema),
                )
                fk_rows = cursor.fetchall()
                foreign_keys: list = []
                for frow in fk_rows:
                    foreign_keys.append({
                        "column": frow["column_name"],
                        "referenced_table": frow["referenced_table"],
                        "referenced_column": frow["referenced_column"],
                    })

                # -- Indexes (non-PK) --
                cursor.execute(
                    "SELECT i.name AS index_name, "
                    "i.is_primary_key, i.is_unique, "
                    "STRING_AGG(c.name, ', ') "
                    "  WITHIN GROUP (ORDER BY ic.key_ordinal) AS columns "
                    "FROM sys.indexes i "
                    "JOIN sys.index_columns ic "
                    "  ON i.object_id = ic.object_id AND i.index_id = ic.index_id "
                    "JOIN sys.columns c "
                    "  ON ic.object_id = c.object_id AND ic.column_id = c.column_id "
                    "JOIN sys.tables t ON i.object_id = t.object_id "
                    "JOIN sys.schemas s ON t.schema_id = s.schema_id "
                    "WHERE s.name = %s AND t.name = %s "
                    "  AND i.type > 0 "
                    "GROUP BY i.name, i.is_primary_key, i.is_unique",
                    (schema, table),
                )
                idx_rows = cursor.fetchall()
                indexes: list = []
                for irow in idx_rows:
                    if irow["is_primary_key"]:
                        continue  # already captured as primary_key
                    idx_type = (
                        "UNIQUE INDEX" if irow["is_unique"] else "INDEX"
                    )
                    definition = (
                        f"CREATE {idx_type} [{irow['index_name']}] "
                        f"ON [{schema}].[{table}] ({irow['columns']})"
                    )
                    indexes.append({
                        "name": irow["index_name"],
                        "definition": definition,
                    })

                tables.append({
                    "name": table,
                    "schema": schema,
                    "row_count": row_counts.get((schema, table), 0),
                    "comment": table_comments.get((schema, table), ""),
                    "primary_key": primary_key,
                    "columns": columns,
                    "foreign_keys": foreign_keys,
                    "indexes": indexes,
                })

            # 6. Sample text columns for semi-structured analysis
            samples = _sample_text_columns_sync(cursor, tables, db_type="mssql")

            return {
                "database_type": "mssql",
                "database_name": database,
                "total_tables": len(tables),
                "total_columns": sum(len(t["columns"]) for t in tables),
                "tables": tables,
                "samples": samples,
            }
        finally:
            conn.close()

    return await asyncio.to_thread(_extract)


# ============================================================
# SCHEMA ENDPOINT
# ============================================================

@router.get("/schema/{connection_id}")
async def get_schema(
    connection_id: int,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Extract and return the schema of a connected database."""
    global _db_pool
    
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DBDESIGN_TK["error.database.pool_not_initialized"]),
        )
    
    user_id = await get_user_id_from_token(credentials)
    
    # Get connection details (with permission check)
    try:
        conn_details = await get_connection_row(connection_id, user_id, language)
    except HTTPException as e:
        raise e
    
    if conn_details is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, DATASETS["database.connection_not_found"])
        )
    
    # Decrypt password
    try:
        decrypted_password = decrypt_field(conn_details["password"])
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DBDESIGN_TK["dbdesign.schema_error_2"], error=str(e)),
        )
    
    db_type = conn_details["type"].lower()
    
    try:
        if db_type in ("postgresql", "postgres"):
            schema = await extract_postgresql_schema(
                host=conn_details["host"],
                port=conn_details["port"],
                database=conn_details["database"],
                username=conn_details["username"],
                password=decrypted_password,
                language=language,
            )
        elif db_type == "mysql":
            schema = await extract_mysql_schema(
                host=conn_details["host"],
                port=conn_details["port"],
                database=conn_details["database"],
                username=conn_details["username"],
                password=decrypted_password,
                language=language,
            )
        elif db_type == "mssql":
            schema = await extract_mssql_schema(
                host=conn_details["host"],
                port=conn_details["port"],
                database=conn_details["database"],
                username=conn_details["username"],
                password=decrypted_password,
                language=language,
            )
        elif db_type == "access":
            schema = extract_access_schema(
                host=conn_details["host"],
                port=conn_details["port"],
                database=conn_details["database"],
                username=conn_details["username"],
                password=decrypted_password,
            )
        else:
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, DBDESIGN_TK["dbdesign.unsupported_type_2"]),
            )
        
        return schema
        
    except HTTPException:
        raise
    except (asyncpg.exceptions.PostgresError, OSError,
            psycopg2.Error, pymssql.Error, pymysql.err.Error) as e:
        raise HTTPException(
            status_code=502,
            detail=await t(_db_pool, language, DBDESIGN_TK["dbdesign.connection_error"], error=str(e)),
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DBDESIGN_TK["dbdesign.schema_error"], error=str(e)),
        )