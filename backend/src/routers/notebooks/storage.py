"""
Storage for notebook imports — workbench_data (PostgreSQL), external PostgreSQL, MySQL, MSSQL.
Implements schema-per-import with atomic rollback (R3).
"""

import logging
from datetime import datetime
import asyncpg
import aiomysql
from typing import Dict, Any, List, Optional
from src.utils.translation import t
from .translations import NOTEBOOKS


_MISSING_VALUES = {"", "nan", "none", "null", "na", "nat"}


def _is_missing(value):
    if value is None:
        return True
    return str(value).strip().lower() in _MISSING_VALUES


def _looks_int(value):
    try:
        int(str(value).strip())
        return True
    except (TypeError, ValueError):
        return False


def _looks_float(value):
    try:
        float(str(value).strip())
        return True
    except (TypeError, ValueError):
        return False


def _looks_bool(value):
    return str(value).strip().lower() in ("true", "false")


def _looks_datetime(value):
    try:
        datetime.fromisoformat(str(value).strip())
        return True
    except (TypeError, ValueError):
        return False


def infer_dtype(values):
    """Classify a column of cell values into a dtype name.

    Returns "integer", "float", "bool", "datetime" or "text", mirroring what
    pandas' read_html would infer for the column (so the MSSQL column-type
    mapping is unchanged). Values are the de-pandased (string) cells; missing
    values (None / "" / "nan" / "none" / "null") are ignored for the
    classification, and an all-missing column is "text". Datetime detection is
    stdlib-only and is the most fragile part of read_html parity — pinned in
    DP-7 with fixtures.
    """
    present = [v for v in values if not _is_missing(v)]
    if not present:
        return "text"
    if all(_looks_int(v) for v in present):
        return "integer"
    if all(_looks_float(v) for v in present):
        return "float"
    if all(_looks_bool(v) for v in present):
        return "bool"
    if all(_looks_datetime(v) for v in present):
        return "datetime"
    return "text"


logger = logging.getLogger(__name__)


class NotebookStorage:
    """Manages storage for notebook imports across multiple engines."""

    async def import_notebook(
        self,
        import_id: str,
        dataframes: List[Dict[str, Any]],
        storage_type: str = "postgresql",
        conn_details: Optional[Dict[str, Any]] = None,
        create_database: bool = False,
        db_pool=None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Import notebook DataFrames into the target storage engine.

        Schema: nb_{import_id}
        Tables: df_0, df_1, ...

        Returns: { "success": bool, "tables": [...], "error": str | None }
        """
        if storage_type == "postgresql":
            if conn_details is None:
                return await self._import_workbench_data(import_id, dataframes, db_pool=db_pool, language=language)
            return await self._import_postgresql(import_id, dataframes, conn_details, create_database, db_pool=db_pool, language=language)
        elif storage_type == "mysql":
            return await self._import_mysql(import_id, dataframes, conn_details, create_database, db_pool=db_pool, language=language)
        elif storage_type == "mssql":
            return await self._import_mssql(import_id, dataframes, conn_details, create_database, db_pool=db_pool, language=language)
        else:
            return {"success": False, "tables": [], "error": await t(db_pool, language, NOTEBOOKS["notebooks_storage.unsupported_storage_type"], type=storage_type)}

    async def delete_import(
        self,
        import_id: str,
        storage_type: str = "postgresql",
        conn_details: Optional[Dict[str, Any]] = None,
        create_database: bool = False,
        db_pool=None,
        language: str = "en",
    ) -> Dict[str, Any]:
        """Delete all tables for an import. Drops database if create_database was used."""
        schema_name = f"nb_{import_id.replace('-', '_')}"
        db_name = f"nb_{import_id.replace('-', '_')}"
        if storage_type == "postgresql":
            if conn_details is None:
                return await self._delete_workbench_data(schema_name, db_pool=db_pool, language=language)
            if create_database:
                return await self._delete_postgresql_database(db_name, conn_details, db_pool=db_pool, language=language)
            return await self._delete_postgresql(schema_name, conn_details, db_pool=db_pool, language=language)
        elif storage_type == "mysql":
            if create_database:
                return await self._delete_mysql_database(db_name, conn_details, db_pool=db_pool, language=language)
            return await self._delete_mysql(schema_name, conn_details, db_pool=db_pool, language=language)
        elif storage_type == "mssql":
            if create_database:
                return await self._delete_mssql_database(db_name, conn_details, db_pool=db_pool, language=language)
            return await self._delete_mssql(schema_name, conn_details, db_pool=db_pool, language=language)
        return {"success": False, "error": await t(db_pool, language, NOTEBOOKS["notebooks_storage.unsupported_storage_type"], type=storage_type)}

    # ----------------------------------------------------------------
    # workbench_data (internal PostgreSQL)
    # ----------------------------------------------------------------

    async def _create_schema_and_tables(
        self, conn, schema_name: str, dataframes: List[Dict[str, Any]],
        db_pool=None, language: str = "en",
    ) -> Dict[str, Any]:
        """Create `schema_name` + df_* TEXT tables and insert rows (atomic).

        Shared by the external PostgreSQL and internal workbench_data import
        paths. Notebook values are stored as TEXT (de-typed).
        """
        created_tables = []
        result = {"success": False, "tables": [], "error": None}
        async with conn.transaction():
            await conn.execute(f"CREATE SCHEMA IF NOT EXISTS {schema_name}")
            for i, df in enumerate(dataframes):
                try:
                    table_name = f"df_{i}"
                    full_name = f"{schema_name}.{table_name}"
                    cols = ", ".join(f'"{c}" TEXT' for c in df["columns"])
                    await conn.execute(f'CREATE TABLE {full_name} ({cols})')
                    for row in df["rows"]:
                        vals = [None if _is_missing(row.get(c)) else str(row.get(c)) for c in df["columns"]]
                        placeholders = ", ".join(f"${j+1}" for j in range(len(vals)))
                        await conn.execute(
                            f'INSERT INTO {full_name} VALUES ({placeholders})',
                            *vals,
                        )
                    row_count = await conn.fetchval(f"SELECT COUNT(*) FROM {full_name}")
                    col_count = len(df["columns"])
                    created_tables.append({"name": full_name, "rows": row_count, "cols": col_count})
                except Exception as e:
                    await conn.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
                    result["error"] = await t(db_pool, language, NOTEBOOKS["notebooks_storage.failed_create_table"], table=f"df_{i}", error=str(e))
                    return result
        result["success"] = True
        result["tables"] = created_tables
        return result

    async def _import_workbench_data(
        self, import_id: str, dataframes: List[Dict[str, Any]],
        db_pool=None, language: str = "en",
    ) -> Dict[str, Any]:
        """Import notebook DataFrames into the internal workbench_data database."""
        from src.postgres_data_manager import get_data_pool
        schema_name = f"nb_{import_id.replace('-', '_')}"
        data_pool = get_data_pool()
        if data_pool is None:
            return {"success": False, "tables": [], "error": await t(db_pool, language, NOTEBOOKS["notebooks_storage.no_data_pool"])}
        try:
            async with data_pool.acquire() as conn:
                return await self._create_schema_and_tables(
                    conn, schema_name, dataframes, db_pool=db_pool, language=language
                )
        except Exception as e:
            return {"success": False, "tables": [], "error": str(e)}

    async def _delete_workbench_data(self, schema_name: str, db_pool=None, language: str = "en") -> Dict[str, Any]:
        """Drop a notebook schema from workbench_data."""
        from src.postgres_data_manager import get_data_pool
        data_pool = get_data_pool()
        if data_pool is None:
            return {"success": False, "error": await t(db_pool, language, NOTEBOOKS["notebooks_storage.no_data_pool"])}
        try:
            async with data_pool.acquire() as conn:
                await conn.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
            return {"success": True, "error": None}
        except Exception as e:
            logger.warning(f"Failed to drop workbench_data schema {schema_name}: {e}")
            return {"success": False, "error": str(e)}

    # ----------------------------------------------------------------
    # PostgreSQL
    # ----------------------------------------------------------------

    async def _import_postgresql(
        self, import_id: str, dataframes: List[Dict[str, Any]],
        conn_details: Optional[Dict[str, Any]], create_database: bool,
        db_pool=None, language: str = "en",
    ) -> Dict[str, Any]:
        if not conn_details:
            return {"success": False, "tables": [], "error": await t(db_pool, language, NOTEBOOKS["notebooks_storage.no_connection_details"])}
        schema_name = f"nb_{import_id.replace('-', '_')}"
        conn = None
        try:
            pg_db = conn_details["database"]
            if create_database:
                sys_conn = await asyncpg.connect(
                    host=conn_details["host"], port=conn_details["port"],
                    user=conn_details["username"], password=conn_details["password"],
                    database=conn_details.get("system_db", "postgres"),
                )
                db_name = f"nb_{import_id.replace('-', '_')}"
                await sys_conn.execute(f'CREATE DATABASE "{db_name}"')
                await sys_conn.close()
                pg_db = db_name

            conn = await asyncpg.connect(
                host=conn_details["host"], port=conn_details["port"],
                user=conn_details["username"], password=conn_details["password"],
                database=pg_db,
            )
            return await self._create_schema_and_tables(
                conn, schema_name, dataframes, db_pool=db_pool, language=language
            )
        except Exception as e:
            return {"success": False, "tables": [], "error": str(e)}
        finally:
            if conn:
                try:
                    await conn.close()
                except Exception:
                    pass

    async def _delete_postgresql(self, schema_name: str, conn_details: Optional[Dict[str, Any]], db_pool=None, language: str = "en") -> Dict[str, Any]:
        if not conn_details:
            return {"success": False, "error": await t(db_pool, language, NOTEBOOKS["notebooks_storage.no_connection_details_short"])}
        try:
            conn = await asyncpg.connect(
                host=conn_details["host"], port=conn_details["port"],
                user=conn_details["username"], password=conn_details["password"],
                database=conn_details["database"],
            )
            await conn.execute(f"DROP SCHEMA IF EXISTS {schema_name} CASCADE")
            await conn.close()
            return {"success": True, "error": None}
        except Exception as e:
            logger.warning(f"Failed to drop PG schema {schema_name}: {e}")
            return {"success": False, "error": str(e)}

    # ----------------------------------------------------------------
    # MySQL
    # ----------------------------------------------------------------

    async def _import_mysql(
        self, import_id: str, dataframes: List[Dict[str, Any]],
        conn_details: Optional[Dict[str, Any]], create_database: bool,
        db_pool=None, language: str = "en",
    ) -> Dict[str, Any]:
        if not conn_details:
            return {"success": False, "tables": [], "error": await t(db_pool, language, NOTEBOOKS["notebooks_storage.no_connection_details"])}
        table_prefix = f"nb_{import_id.replace('-', '_')}"
        created_tables = []
        result = {"success": False, "tables": [], "error": None}
        conn = None
        try:
            mysql_db = conn_details["database"]
            if create_database:
                sys_conn = await aiomysql.connect(
                    host=conn_details["host"], port=conn_details["port"],
                    user=conn_details["username"], password=conn_details["password"],
                    db="mysql",
                )
                db_name = f"nb_{import_id.replace('-', '_')}"
                async with sys_conn.cursor() as cur:
                    await cur.execute(f"CREATE DATABASE IF NOT EXISTS `{db_name}`")
                sys_conn.close()
                mysql_db = db_name

            conn = await aiomysql.connect(
                host=conn_details["host"], port=conn_details["port"],
                user=conn_details["username"], password=conn_details["password"],
                db=mysql_db,
            )
            async with conn.cursor() as cur:
                for i, df in enumerate(dataframes):
                    try:
                        full_name = f"`{table_prefix}_df_{i}`"
                        cols = ", ".join(f"`{c}` TEXT" for c in df["columns"])
                        await cur.execute(f"CREATE TABLE IF NOT EXISTS {full_name} ({cols})")
                        for row in df["rows"]:
                            vals = [None if _is_missing(row.get(c)) else str(row.get(c)) for c in df["columns"]]
                            placeholders = ", ".join(["%s"] * len(vals))
                            await cur.execute(
                                f"INSERT INTO {full_name} VALUES ({placeholders})",
                                vals,
                            )
                        await cur.execute(f"SELECT COUNT(*) FROM {full_name}")
                        row_count = (await cur.fetchone())[0]
                        col_count = len(df["columns"])
                        created_tables.append({"name": full_name, "rows": row_count, "cols": col_count})
                    except Exception as e:
                        # Rollback: drop tables created so far
                        for tbl in created_tables:
                            try:
                                await cur.execute(f"DROP TABLE IF EXISTS {tbl['name']}")
                            except Exception:
                                pass
                        result["error"] = await t(db_pool, language, NOTEBOOKS["notebooks_storage.failed_create_table"], table=f"df_{i}", error=str(e))
                        return result
            await conn.commit()
            result["success"] = True
            result["tables"] = created_tables
            return result
        except Exception as e:
            result["error"] = str(e)
            return result
        finally:
            if conn:
                try:
                    await conn.close()
                except Exception:
                    pass

    async def _delete_mysql(self, schema_name: str, conn_details: Optional[Dict[str, Any]], db_pool=None, language: str = "en") -> Dict[str, Any]:
        """Drop tables with the import prefix (MySQL doesn't have schemas)."""
        if not conn_details:
            return {"success": False, "error": await t(db_pool, language, NOTEBOOKS["notebooks_storage.no_connection_details_short"])}
        try:
            conn = await aiomysql.connect(
                host=conn_details["host"], port=conn_details["port"],
                user=conn_details["username"], password=conn_details["password"],
                db=conn_details["database"],
            )
            async with conn.cursor() as cur:
                # Find all tables matching the prefix
                await cur.execute(f"SHOW TABLES LIKE '{schema_name}\\_%'")
                tables = await cur.fetchall()
                for (table_name,) in tables:
                    await cur.execute(f"DROP TABLE IF EXISTS `{table_name}`")
            conn.close()
            return {"success": True, "error": None}
        except Exception as e:
            logger.warning(f"Failed to drop MySQL tables with prefix {schema_name}: {e}")
            return {"success": False, "error": str(e)}

    async def _delete_postgresql_database(self, db_name: str, conn_details: Optional[Dict[str, Any]], db_pool=None, language: str = "en") -> Dict[str, Any]:
        """Drop the entire database (used when create_database was True)."""
        if not conn_details:
            return {"success": False, "error": await t(db_pool, language, NOTEBOOKS["notebooks_storage.no_connection_details_short"])}
        try:
            sys_conn = await asyncpg.connect(
                host=conn_details["host"], port=conn_details["port"],
                user=conn_details["username"], password=conn_details["password"],
                database=conn_details.get("system_db", "postgres"),
            )
            await sys_conn.execute(f'DROP DATABASE IF EXISTS "{db_name}"')
            await sys_conn.close()
            return {"success": True, "error": None}
        except Exception as e:
            logger.warning(f"Failed to drop PostgreSQL database {db_name}: {e}")
            return {"success": False, "error": str(e)}

    async def _delete_mysql_database(self, db_name: str, conn_details: Optional[Dict[str, Any]], db_pool=None, language: str = "en") -> Dict[str, Any]:
        """Drop the entire database (used when create_database was True)."""
        if not conn_details:
            return {"success": False, "error": await t(db_pool, language, NOTEBOOKS["notebooks_storage.no_connection_details_short"])}
        try:
            conn = await aiomysql.connect(
                host=conn_details["host"], port=conn_details["port"],
                user=conn_details["username"], password=conn_details["password"],
                db="mysql",
            )
            async with conn.cursor() as cur:
                await cur.execute(f"DROP DATABASE IF EXISTS `{db_name}`")
            conn.close()
            return {"success": True, "error": None}
        except Exception as e:
            logger.warning(f"Failed to drop MySQL database {db_name}: {e}")
            return {"success": False, "error": str(e)}

    # ----------------------------------------------------------------
    # MS SQL Server
    # ----------------------------------------------------------------

    @staticmethod
    def _dtype_to_mssql(dtype: str) -> str:
        """Map inferred dtype name to SQL Server column type."""
        if dtype == "integer":
            return "INT"
        elif dtype == "float":
            return "FLOAT"
        elif dtype == "bool":
            return "BIT"
        elif dtype == "datetime":
            return "DATETIME2"
        else:
            return "NVARCHAR(MAX)"

    async def _import_mssql(
        self, import_id: str, dataframes: List[Dict[str, Any]],
        conn_details: Optional[Dict[str, Any]], create_database: bool,
        db_pool=None, language: str = "en",
    ) -> Dict[str, Any]:
        if not conn_details:
            return {"success": False, "tables": [], "error": await t(db_pool, language, NOTEBOOKS["notebooks_storage.no_connection_details"])}
        import asyncio
        import pymssql
        schema_name = f"nb_{import_id.replace('-', '_')}"
        created_tables = []
        result = {"success": False, "tables": [], "error": None}

        def _do_import():
            mssql_db = conn_details["database"]
            if create_database:
                db_name = f"nb_{import_id.replace('-', '_')}"
                # Connect to master to create the database
                sys_conn = pymssql.connect(
                    host=conn_details["host"], port=conn_details["port"],
                    user=conn_details["username"], password=conn_details["password"],
                    database="master",
                )
                sys_conn.autocommit(True)
                sys_cursor = sys_conn.cursor()
                try:
                    sys_cursor.execute(
                        f"IF NOT EXISTS (SELECT name FROM sys.databases WHERE name = '{db_name}') "
                        f"CREATE DATABASE [{db_name}]"
                    )
                finally:
                    sys_conn.close()
                mssql_db = db_name

            conn = pymssql.connect(
                host=conn_details["host"], port=conn_details["port"],
                user=conn_details["username"], password=conn_details["password"],
                database=mssql_db,
            )
            conn.autocommit(False)
            try:
                cursor = conn.cursor()
                # Create schema if not exists
                cursor.execute(
                    f"IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = '{schema_name}') "
                    f"EXEC('CREATE SCHEMA [{schema_name}]')"
                )
                for i, df in enumerate(dataframes):
                    try:
                        table_name = f"df_{i}"
                        full_name = f"[{schema_name}].[{table_name}]"
                        cols = ", ".join(
                            f"[{c}] {self._dtype_to_mssql(infer_dtype([row.get(c) for row in df["rows"]]))}" for c in df["columns"]
                        )
                        cursor.execute(f"CREATE TABLE {full_name} ({cols})")
                        for row in df["rows"]:
                            vals = [None if _is_missing(row.get(c)) else str(row.get(c)) for c in df["columns"]]
                            placeholders = ", ".join(["%s"] * len(vals))
                            cursor.execute(
                                f"INSERT INTO {full_name} VALUES ({placeholders})",
                                tuple(vals),
                            )
                        cursor.execute(f"SELECT COUNT(*) FROM {full_name}")
                        row_count = cursor.fetchone()[0]
                        col_count = len(df["columns"])
                        created_tables.append({"name": full_name, "rows": row_count, "cols": col_count})
                    except Exception:
                        # Rollback: drop tables created so far
                        for tbl in created_tables:
                            try:
                                cursor.execute(f"DROP TABLE IF EXISTS {tbl['name']}")
                            except Exception:
                                pass
                        raise
                conn.commit()
                conn.close()
                result["success"] = True
                result["tables"] = created_tables
                return result
            except Exception as e:
                conn.rollback()
                conn.close()
                result["error"] = str(e)
                return result

        thread_result = await asyncio.to_thread(_do_import)
        if not thread_result.get("success") and thread_result.get("error") and db_pool:
            # Translate the error from the sync thread function
            thread_result["error"] = await t(db_pool, language, NOTEBOOKS["notebooks_storage.failed_create_table_mssql"], error=thread_result["error"])
        return thread_result

    async def _delete_mssql(self, schema_name: str, conn_details: Optional[Dict[str, Any]], db_pool=None, language: str = "en") -> Dict[str, Any]:
        """Drop all tables in the schema, then drop the schema."""
        if not conn_details:
            return {"success": False, "error": await t(db_pool, language, NOTEBOOKS["notebooks_storage.no_connection_details_short"])}
        import asyncio
        import pymssql

        def _drop():
            conn = pymssql.connect(
                host=conn_details["host"], port=conn_details["port"],
                user=conn_details["username"], password=conn_details["password"],
                database=conn_details["database"],
            )
            conn.autocommit(True)
            try:
                cursor = conn.cursor()
                # Drop all tables in the schema
                cursor.execute(
                    f"DECLARE @sql NVARCHAR(MAX) = ''; "
                    f"SELECT @sql = @sql + 'DROP TABLE IF EXISTS [{schema_name}].' + QUOTENAME(t.name) + ';' "
                    f"FROM sys.tables t JOIN sys.schemas s ON t.schema_id = s.schema_id "
                    f"WHERE s.name = '{schema_name}'; "
                    f"IF @sql != '' EXEC sp_executesql @sql;"
                )
                cursor.execute(f"DROP SCHEMA IF EXISTS [{schema_name}]")
                conn.close()
                return {"success": True, "error": None}
            except Exception as e:
                conn.close()
                logger.warning(f"Failed to drop MSSQL schema {schema_name}: {e}")
                return {"success": False, "error": str(e)}

        return await asyncio.to_thread(_drop)

    async def _delete_mssql_database(self, db_name: str, conn_details: Optional[Dict[str, Any]], db_pool=None, language: str = "en") -> Dict[str, Any]:
        """Drop the entire database (used when create_database was True)."""
        if not conn_details:
            return {"success": False, "error": await t(db_pool, language, NOTEBOOKS["notebooks_storage.no_connection_details_short"])}
        import asyncio
        import pymssql

        def _drop():
            conn = pymssql.connect(
                host=conn_details["host"], port=conn_details["port"],
                user=conn_details["username"], password=conn_details["password"],
                database="master",
            )
            conn.autocommit(True)
            try:
                cursor = conn.cursor()
                cursor.execute(f"DROP DATABASE IF EXISTS [{db_name}]")
                conn.close()
                return {"success": True, "error": None}
            except Exception as e:
                conn.close()
                logger.warning(f"Failed to drop MSSQL database {db_name}: {e}")
                return {"success": False, "error": str(e)}

        return await asyncio.to_thread(_drop)

    @staticmethod
    def _is_system_db(database: str, db_type: str) -> bool:
        """Check if the database is a system database that should not be imported into."""
        db_lower = database.lower().strip()
        if db_type == "postgresql":
            return db_lower in ("postgres", "template0", "template1")
        if db_type == "mysql":
            return db_lower in ("mysql", "information_schema", "performance_schema", "sys")
        if db_type == "mssql":
            return db_lower in ("master", "tempdb", "model", "msdb")
        return False


# Singleton
_notebook_storage: Optional[NotebookStorage] = None


def get_notebook_storage() -> NotebookStorage:
    global _notebook_storage
    if _notebook_storage is None:
        _notebook_storage = NotebookStorage()
    return _notebook_storage
