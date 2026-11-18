"""
Schema Discovery – Get schema and preview data from datasets
Part of the 0.0.10 "Statistical Foundation" milestone.
"""

import math
import os
import pandas as pd
import asyncio
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from .crud import get_connection_row, get_current_language, get_user_id_from_token
from src.utils.translation import t
from .translations import (
    SCHEMA,
    unread_definition_incomplete,
    unread_definition_too_deep,
    unread_state_auth_failed,
    unread_state_incomplete,
    unread_state_no_database,
    unread_state_no_permission,
    unread_state_schema_error,
    unread_state_unreachable,
)
from .connection_probe import classify_connection_error, PROBE_UNREACHABLE
from src.postgres_data_manager import (
    _quote,
    _quote_qualified,
    get_data_pool,
    get_table_preview,
    get_table_schema,
    get_table_statistics,
    table_exists,
    user_schema_name,
)
from src.routers.datasets.data_access import error_text
from src.routers.common.relations import columns_of_visible_relation

# Global database pool - will be set from main.py
_db_pool = None

def set_db_pool(pool):
    global _db_pool
    _db_pool = pool

router = APIRouter()
security = HTTPBearer()


#: Which class a failure that never reached the probe belongs to.
#:
#: The probe's own vocabulary, so a cached verdict and a freshly-observed failure
#: are stated in the same words. `unknown` is never produced here: both readings
#: below have an answer, and inventing a third state for "we did not look" would
#: be a word with no repair behind it.
_UNREACHABLE = PROBE_UNREACHABLE
_DEFINITION_INCOMPLETE = "definition_incomplete"
_DEFINITION_TOO_DEEP = "definition_too_deep"

#: Probe state → the declaration that says what it means.
#:
#: Here rather than in `translations.py`, and that is the declaration rule rather
#: than taste: a map in the file that declares the keys gives each one a second
#: name in its own module, and a dict value is not a use — the linter reported all
#: six as unreferenced when the map lived there. This is the CHIP_HEADINGS pattern:
#: the declarations are imported by name into the module that resolves them.
#:
#: `unknown` is not a state either classifier emits; a stored row carrying it means
#: "something stopped us connecting", which is the unreachable sentence.
UNREAD_STATE_KEYS = {
    PROBE_UNREACHABLE: unread_state_unreachable,
    "auth_failed": unread_state_auth_failed,
    "no_database": unread_state_no_database,
    "no_permission": unread_state_no_permission,
    "schema_error": unread_state_schema_error,
    "incomplete": unread_state_incomplete,
    "unknown": unread_state_unreachable,
}


def _classify_unread(exc: BaseException) -> str:
    """The class to report for a failure on the schema-read path.

    **An `HTTPException`'s `detail` is used, never its `str()`.** `str()` renders
    the status into the message — `"500: Database pool not initialized"` — so the
    status code reached the screen as part of the sentence. Go's `StatusError`
    has never done that (its `Error()` returns the message alone), which made the
    two backends disagree about the same condition in a way no wording could
    reconcile. Reading `detail` removes the prefix at its source rather than
    stripping it afterwards, and it is also the half that was already translated
    by `t()` inside `get_connection_row`.

    A definition reason is reported as its own class: it is not a connection
    failure at all, and calling it `unreachable` would send the reader to check a
    host that is fine.

    An `HTTPException` whose detail is none of the classifier's needles — a pool
    that was never initialised, say — lands on `unreachable` by the classifier's
    own documented rule ("an unrecognised message becomes unreachable, not a
    silent success"). That is the least-wrong sentence in the closed vocabulary:
    the read genuinely produced nothing, and the alternative was to add a state
    the column's CHECK constraint does not admit. It is a server fault rather
    than the reader's, and it is logged as one.
    """
    if isinstance(exc, HTTPException):
        exc = RuntimeError(str(exc.detail or ""))

    state, _detail = classify_connection_error(exc)
    return state


async def _unread_state_text(db_pool, language: str, state: str) -> str:
    """The translated sentence for one unread class.

    Resolved here, at the boundary, like every other string in the scoreboard
    path: the declaration is the fallback's single source and the row carries the
    key beside the sentence so a missing translation is diagnosable. A state the
    map does not name is a defect, logged rather than rendered as a blank line.
    """
    if state == _DEFINITION_INCOMPLETE:
        declared = unread_definition_incomplete
    elif state == _DEFINITION_TOO_DEEP:
        declared = unread_definition_too_deep
    else:
        declared = UNREAD_STATE_KEYS.get(state)
    if declared is None:
        import logging
        logging.getLogger(__name__).error("unread source names an undeclared state: %r", state)
        return ""
    return await t(db_pool, language, declared)


async def virtual_dataset_schema_from_definition(virtual_sql: dict, user_id: str, language: str,
                                              materialized_table: str = "",
                                                    _depth: int = 0) -> dict:
    """The output schema of a virtual dataset, read from its definition.

    **No data is copied and no table is written.** Until 2026-11-06 the schema
    route answered a virtual dataset by calling `materialize_virtual_dataset`,
    which pulled every source's rows across the network and ran
    `DROP TABLE IF EXISTS …; CREATE TABLE … AS <join>` — for a *read*. Measured:
    a seven-source dataset took 60 seconds and then failed, and the failure left a
    persistent table rebuilt from a definition nobody asked to execute.

    The definition already names every output column, so the shape is knowable
    without running anything: each entry is `{source, column}`, and the output
    name is `{source}_{column}` — the same rule `build_postgres_join_sql` uses for
    its `AS` alias, so the two cannot disagree.

    Types come from the sources' metadata: a dataset reference reads its own
    schema, and a connection reference lists its table's columns. Both are
    catalogue reads.

    **A source that cannot be read is named, not hidden.** Until 2026-11-06 this
    swallowed the failure and emitted `UNKNOWN` types with nothing to explain
    them — a partial answer indistinguishable from a complete one. Measured: an
    unreachable source answered `200` after ten seconds with
    `[("s1_order_id", "UNKNOWN")]` and no mention of the connection. Now every
    unread source contributes a line to `unread`, and the response carries it.

    The probe is consulted first. It exists so a caller can know *before it acts*
    whether a connection can be reached, and this path opened a metadata
    connection per source without asking — the same defect phase 1 fixed for the
    materialise path, on the path phase 2 created.

    `total_rows` is **0 and not the join's count**, because the count is the one
    thing that genuinely needs the join to run. The response says so in its
    `warning`.
    """
    from .connection_probe import fresh_failures
    from .virtual import database_connect_timeout

    # A dataset source recurses through `fetch_dataset_schema`, so a definition
    # that references its own dataset — directly, or round a chain — would recurse
    # until Python's limit and answer a 500 with a RecursionError. Naming the
    # ceiling turns that into a reported source instead of a crash.
    if _depth >= 5:
        return {
            "columns": [], "total_rows": 0, "total_columns": 0,
            "row_count_known": False,
            "unread": [{
                "alias": "*",
                "state": _DEFINITION_TOO_DEEP,
                "stateText": await _unread_state_text(_db_pool, language, _DEFINITION_TOO_DEEP),
                "reason": "dataset references nested more than five deep",
            }],
            "warning": await t(_db_pool, language, SCHEMA["datasets.schema.row_count_not_computed"]),
        }

    sources = [s for s in (virtual_sql.get("sources") or []) if isinstance(s, dict)]
    connection_ids = [s.get("connectionId") for s in sources if s.get("connectionId")]
    refused = await fresh_failures(_db_pool, user_id, connection_ids)
    deadline = await database_connect_timeout(_db_pool, language)

    by_source: dict = {}
    unread: list = []
    for source in sources:
        alias = source.get("alias")
        if not alias:
            continue
        found: dict = {}
        reason = None
        # The class of the failure, so the entry can say what happened in words
        # both backends agree on. The driver's own text still travels as
        # `reason`, demoted to a diagnostic line: it is asyncpg's wording on one
        # backend and pgx's on the other, for the same failure.
        state = None
        try:
            if source.get("datasetId"):
                # Recurse through the definition reader, not `fetch_dataset_schema`,
                # so a nested virtual dataset is also answered without materialising
                # and the depth ceiling applies to it too.
                inner = await fetch_dataset_schema(
                    source["datasetId"], user_id, language, _depth=_depth + 1
                )
                for column in inner.get("columns") or []:
                    found[column.get("name")] = column
                # A nested dataset's own unread sources must surface here too, or
                # the outer answer is silent about why a type is UNKNOWN — the
                # defect this function exists to stop, one level down.
                for nested in inner.get("unread") or []:
                    if not (isinstance(nested, dict) and nested.get("reason")):
                        continue
                    reason = nested["reason"]
                    state = nested.get("state") or "schema_error"
                    # The ceiling's own sentence already says everything; prefixing
                    # it at each level back up produced "dataset X: dataset X: …"
                    # five times over. A reason that explains itself is passed on
                    # as it stands.
                    if "nested more than" not in reason:
                        reason = f"dataset {source['datasetId']}: {reason}"
                    unread.append({
                        "alias": alias, "state": state,
                        "stateText": await _unread_state_text(_db_pool, language, state),
                        "reason": reason,
                    })
            elif source.get("connectionId") and (source.get("tableName") or source.get("_tableName")):
                connection_id = source["connectionId"]
                if connection_id in refused:
                    # Known unreachable and still fresh: do not open a socket. The
                    # cache carries the state as well as the text — the text alone
                    # is driver wording and cannot be said out loud.
                    state, reason = refused[connection_id]
                else:
                    from .browse import list_table_columns

                    table = source.get("tableName") or source.get("_tableName")
                    for column in await list_table_columns(
                        _db_pool, user_id, language, connection_id, table,
                        connect_timeout=deadline,
                    ):
                        found[column.get("name")] = column
            else:
                state = _DEFINITION_INCOMPLETE
                reason = "the source names neither a dataset nor a connection table"
        except Exception as exc:
            from .data_access import error_text

            # Classify the failure the read actually had, not only what the cache
            # last believed. Measured 2026-11-11: a connection whose cached state
            # was `reachable` failed to resolve its host on this very read — so a
            # cache-only answer would have been "reachable", the one state that
            # says nothing went wrong.
            state = _classify_unread(exc)
            reason = error_text(exc)
        if reason:
            # The alias, not the connection id: a reader sees `s1` on every row
            # and needs to match the message to the source they can see.
            unread.append({
                "alias": alias,
                "state": state or _UNREACHABLE,
                "stateText": await _unread_state_text(_db_pool, language, state or _UNREACHABLE),
                "reason": reason,
            })
        by_source[alias] = found

    columns = []
    for entry in virtual_sql.get("columns") or []:
        if not isinstance(entry, dict):
            continue
        alias, name = entry.get("source"), entry.get("column")
        if not alias or not name:
            continue
        info = by_source.get(alias, {}).get(name) or {}
        dtype = str(info.get("type") or "UNKNOWN")
        columns.append({
            "name": f"{alias}_{name}",
            "dtype": dtype,
            "nullable": info.get("nullable"),
            "is_numeric": info.get("is_numeric", False),
            "is_categorical": info.get("is_categorical", False),
            "is_datetime": info.get("is_datetime", False),
            "unique_count": 0,
            "null_count": 0,
            "sample_values": [],
        })

    # Deduplicated: a chain of nested datasets propagates the same terminal reason
    # up through every level, and six identical lines tell a reader less than one.
    seen = set()
    deduped = []
    for entry in unread:
        key = (entry["alias"], entry["reason"])
        if key in seen:
            continue
        seen.add(key)
        deduped.append(entry)

    # A materialised dataset has already run its join, so its rows are a local
    # table and the count is one COUNT(*). The warning below is true only of a
    # *live* dataset, where the number genuinely needs the join to run — and
    # until 2026-11-06 that warning was emitted for both, so a dataset holding
    # 4,722 rows reported `total_rows: 0` beside a sentence saying the count was
    # not computed. Measured on vd_d31158c13fc04527.
    if materialized_table:
        try:
            if await table_exists(materialized_table):
                stats = await get_table_statistics(materialized_table)
                return {
                    "columns": columns,
                    "total_rows": stats.get("row_count", 0),
                    "total_columns": len(columns),
                    "row_count_known": True,
                    "unread": deduped,
                    "warning": None,
                }
        except Exception as e:
            # The table is named but unreadable. Fall through to the unknown
            # answer rather than reporting a zero: a failed count is not a count
            # of nothing, and the reader is told the question went unanswered.
            print(f"Warning: could not count the materialised table {materialized_table}: {e}")

    return {
        "columns": columns,
        "total_rows": 0,
        "total_columns": len(columns),
        # `total_rows` is present and zero, and this says why: the count was not
        # taken. Zero alone would claim the dataset is empty. A client that reads
        # the flag can say "not computed"; one that ignores it behaves exactly as
        # it did before the flag existed, which is why this is a companion rather
        # than an absent key (decided 2026-11-06).
        "row_count_known": False,
        "unread": deduped,
        "warning": await t(_db_pool, language, SCHEMA["datasets.schema.row_count_not_computed"]),
    }


async def _describe_pg_table(table_name: str):
    """Describe a PostgreSQL table in workbench_data.

    Returns ``(columns, total_rows, total_columns)`` where ``columns`` is the
    schema-detail list, or ``(None, 0, 0)`` when the table is missing. Shared by
    the native-PG and virtual-dataset describe paths.
    """

    if not await table_exists(table_name):
        return None, 0, 0

    schema = await get_table_schema(table_name)

    columns = []
    for col_info in schema:
        dtype = col_info["type"]
        col_data = {
            "name": col_info["name"],
            "dtype": dtype,
            "nullable": col_info["nullable"],
            "is_numeric": any(t in dtype.upper() for t in ("INT", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL")),
            "is_categorical": "VARCHAR" in dtype.upper() or "TEXT" in dtype.upper(),
            "is_datetime": "TIMESTAMP" in dtype.upper() or "DATE" in dtype.upper() or "TIME" in dtype.upper(),
            "unique_count": 0,
            "null_count": 0,
            "sample_values": []
        }
        columns.append(col_data)

    stats = await get_table_statistics(table_name)

    # Exact per-column unique + null counts (single aggregate scan over the table).
    names = [c["name"] for c in columns]
    if names:
        data_pool = get_data_pool()
        if data_pool is not None:
            agg = ", ".join(
                f"COUNT(DISTINCT {_quote(n)}), COUNT(*) - COUNT({_quote(n)})"
                for n in names
            )
            async with data_pool.acquire() as conn:
                row = await conn.fetchrow(
                    f"SELECT {agg} FROM {_quote_qualified(table_name)}"
                )
            if row:
                for i, col in enumerate(columns):
                    col["unique_count"] = int(row[2 * i])
                    col["null_count"] = int(row[2 * i + 1])

    # Example values for display only — not statistics.
    try:
        preview_rows = await get_table_preview(table_name, limit=10)
        if preview_rows:
            for col in columns:
                col_name = col["name"]
                col["sample_values"] = [
                    r.get(col_name)
                    for r in preview_rows
                    if r.get(col_name) is not None
                    and not (isinstance(r.get(col_name), float) and math.isnan(r.get(col_name)))
                ][:5]
    except Exception as e:
        print(f"Warning: Could not get sample data from workbench_data: {e}")

    return columns, stats.get("row_count", 0), stats.get("column_count", len(columns))


@router.get("/{dataset_id}/schema")
async def get_dataset_schema(
    dataset_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Get the schema of a dataset including column names, types, and statistics."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, SCHEMA["error.database.pool_not_initialized"])
        )
    user_id = await get_user_id_from_token(credentials)
    return await fetch_dataset_overview(dataset_id, user_id, language)


async def fetch_dataset_overview(
    dataset_id: str,
    user_id: str,
    language: str,
):
    """Return the schema of a dataset, including its row count.

    "Overview" because it reports a usage statistic alongside the schema: every
    source type below runs a ``SELECT COUNT(*)`` (for PostgreSQL tables, two
    full-table scans). Callers that only need the columns should use
    ``fetch_dataset_schema``, which is this function without them.

    Shared by the HTTP endpoint and the AI get_dataset_schema tool."""
    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT "sourceType", "storageType", "sourceConnectionId", 
                   "databaseName", "tableName", "dataSnapshot", "virtualSql",
                   "materialized", "userId"
            FROM "UserDataset"
            WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                SELECT "userGroup" FROM "User" WHERE id = $2
            )))
            """,
            dataset_id, user_id
        )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, SCHEMA["error.dataset.not_found_5"], id=dataset_id)
        )

    source_type = row["sourceType"]
    storage_type = row["storageType"]
    source_connection_id = row["sourceConnectionId"]
    table_name = row["tableName"]
    data_snapshot = row["dataSnapshot"]
    virtual_sql_raw = row.get("virtualSql")
    virtual_sql = virtual_sql_raw or {}
    # The owner, not the caller: a shared dataset's materialised table lives in
    # the owner's schema. Same reason the delete path reads `userId` rather than
    # the caller's id.
    owner_id = row["userId"]

    sample_data = []
    if data_snapshot:
        if isinstance(data_snapshot, list):
            sample_data = data_snapshot
        elif isinstance(data_snapshot, dict):
            sample_data = [data_snapshot]

    if source_type in ("upload", "notebook") and storage_type == "postgresql" and table_name:
        try:
            columns, total_rows, total_columns = await _describe_pg_table(table_name)
            if columns is None:
                return {
                    "dataset_id": dataset_id,
                    "columns": [],
                    "total_rows": 0,
                    "total_columns": 0,
                    # The table is absent, so zero rows is not an estimate: there
                    # is nothing to count and nothing that could hold rows.
                    "row_count_known": True,
                    "source_type": source_type,
                    "storage_type": storage_type,
                    "warning": await t(_db_pool, language, SCHEMA["datasets.schema.table_missing"])
                }
            return {
                "dataset_id": dataset_id,
                "columns": columns,
                "total_rows": total_rows,
                "total_columns": total_columns,
                "row_count_known": True,
                "source_type": source_type,
                "storage_type": storage_type
            }
        except Exception as e:
            print(f"Error getting schema from workbench_data: {e}")
            return {
                "dataset_id": dataset_id,
                "columns": [],
                "total_rows": 0,
                "total_columns": 0,
                # The read failed, so the count was never taken. A zero here
                # would report a failure as an empty table.
                "row_count_known": False,
                "source_type": source_type,
                "storage_type": storage_type,
                "warning": await t(_db_pool, language, SCHEMA["datasets.schema.load_error"], error=error_text(e))
            }

    elif source_type in ["table", "view", "access", "mssql", "mysql", "postgresql"] and source_connection_id and table_name:
        try:
            connection_row = await get_connection_row(source_connection_id, user_id, language)
            if connection_row is None:
                raise HTTPException(
                    status_code=404,
                    detail=await t(_db_pool, language, SCHEMA["error.define.connection_not_found"])
                )
            
            if connection_row["type"] in ("postgresql", "access"):
                from src.utils.encryption import decrypt_field
                try:
                    decrypted_password = decrypt_field(connection_row["password"])
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.decryption_failed"], error=error_text(e))
                    )
                
                conn_str = f"postgresql://{connection_row['username']}:{decrypted_password}@{connection_row['host']}:{connection_row['port']}/{connection_row['database']}"
                try:
                    ext_conn = await asyncpg.connect(conn_str)
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.failed"], error=error_text(e))
                    )
                
                try:
                    # The session's own schema, not `public` — see common/relations.py.
                    columns_query = columns_of_visible_relation("$1")
                    columns_result = await ext_conn.fetch(columns_query, table_name)
                    
                    columns = []
                    for col in columns_result:
                        columns.append({
                            "name": col["column_name"],
                            "dtype": col["data_type"],
                            "nullable": col["is_nullable"] == "YES",
                            "is_numeric": col["data_type"] in ["integer", "bigint", "smallint", "decimal", "numeric", "real", "double precision", "float"],
                            "is_categorical": col["data_type"] in ["character varying", "varchar", "text", "character", "char"],
                            "is_datetime": col["data_type"] in ["timestamp", "timestamp without time zone", "timestamp with time zone", "date", "time"],
                            "unique_count": 0,
                            "null_count": 0,
                            "sample_values": []
                        })
                    
                    try:
                        sample_query = f'SELECT * FROM "{table_name}" LIMIT 10'
                        sample_result = await ext_conn.fetch(sample_query)
                        sample_data = [dict(row) for row in sample_result]
                        
                        for col in columns:
                            col_name = col["name"]
                            values = []
                            for row_data in sample_data:
                                v = row_data[col_name]
                                if col_name in row_data and v is not None and not (isinstance(v, float) and math.isnan(v)):
                                    values.append(v)
                            col["sample_values"] = values[:5]
                            col["unique_count"] = len(set(values)) if values else 0
                            col["null_count"] = len(sample_data) - len(values) if sample_data else 0
                    except Exception as e:
                        print(f"Warning: Could not get sample data: {e}")
                    
                    count_query = f'SELECT COUNT(*) FROM "{table_name}"'
                    total_rows = await ext_conn.fetchval(count_query)
                    
                    await ext_conn.close()
                    
                    return {
                        "dataset_id": dataset_id,
                        "columns": columns,
                        "total_rows": total_rows,
                        "total_columns": len(columns),
                        "row_count_known": True,
                        "source_type": source_type,
                        "storage_type": storage_type
                    }
                except Exception as e:
                    await ext_conn.close()
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.query_failed_7"], error=error_text(e))
                    )
            elif connection_row["type"] == "mysql":
                import aiomysql
                from src.utils.encryption import decrypt_field
                try:
                    decrypted_password = decrypt_field(connection_row["password"])
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.decryption_failed"], error=error_text(e))
                    )
                
                try:
                    mysql_conn = await aiomysql.connect(
                        host=connection_row["host"],
                        port=connection_row["port"],
                        db=connection_row["database"],
                        user=connection_row["username"],
                        password=decrypted_password,
                    )
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.failed"], error=error_text(e))
                    )
                
                try:
                    async with mysql_conn.cursor(aiomysql.DictCursor) as cur:
                        await cur.execute(
                            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE "
                            "FROM information_schema.COLUMNS "
                            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                            "ORDER BY ORDINAL_POSITION",
                            (connection_row["database"], table_name)
                        )
                        columns_result = await cur.fetchall()
                        
                        mysql_numeric = ["int", "bigint", "smallint", "tinyint", "decimal", "numeric", "float", "double", "real"]
                        mysql_text = ["varchar", "char", "text", "longtext", "mediumtext", "tinytext"]
                        mysql_datetime = ["datetime", "timestamp", "date", "time", "year"]
                        
                        columns = []
                        for col in columns_result:
                            columns.append({
                                "name": col["COLUMN_NAME"],
                                "dtype": col["DATA_TYPE"],
                                "nullable": col["IS_NULLABLE"] == "YES",
                                "is_numeric": col["DATA_TYPE"].lower() in mysql_numeric,
                                "is_categorical": col["DATA_TYPE"].lower() in mysql_text,
                                "is_datetime": col["DATA_TYPE"].lower() in mysql_datetime,
                                "unique_count": 0,
                                "null_count": 0,
                                "sample_values": []
                            })
                        
                        try:
                            await cur.execute(f"SELECT * FROM `{table_name}` LIMIT 10")
                            sample_result = await cur.fetchall()
                            sample_data = [dict(row) for row in sample_result]
                            
                            for col in columns:
                                col_name = col["name"]
                                values = []
                                for row_data in sample_data:
                                    v = row_data[col_name]
                                    if col_name in row_data and v is not None and not (isinstance(v, float) and math.isnan(v)):
                                        values.append(v)
                                col["sample_values"] = values[:5]
                                col["unique_count"] = len(set(values)) if values else 0
                                col["null_count"] = len(sample_data) - len(values) if sample_data else 0
                        except Exception as e:
                            print(f"Warning: Could not get sample data: {e}")
                        
                        await cur.execute(f"SELECT COUNT(*) AS cnt FROM `{table_name}`")
                        row = await cur.fetchone()
                        total_rows = row["cnt"]
                        
                        mysql_conn.close()
                        
                        return {
                            "dataset_id": dataset_id,
                            "columns": columns,
                            "total_rows": total_rows,
                            "total_columns": len(columns),
                            "row_count_known": True,
                            "source_type": source_type,
                            "storage_type": storage_type
                        }
                except Exception as e:
                    mysql_conn.close()
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.query_failed_7"], error=error_text(e))
                    )
            elif connection_row["type"] == "mssql":
                import pymssql
                from src.utils.encryption import decrypt_field
                try:
                    decrypted_password = decrypt_field(connection_row["password"])
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.decryption_failed"], error=error_text(e))
                    )
                def _connect():
                    return pymssql.connect(
                        host=connection_row["host"],
                        port=connection_row["port"],
                        database=connection_row["database"],
                        user=connection_row["username"],
                        password=decrypted_password,
                    )
                conn = await asyncio.to_thread(_connect)
                try:
                    cursor = conn.cursor(as_dict=True)
                    cursor.execute(
                        "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE "
                        "FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                        "ORDER BY ORDINAL_POSITION",
                        (connection_row.get("schema", "dbo"), table_name)
                    )
                    columns_result = cursor.fetchall()
                    mssql_numeric = ["int", "bigint", "smallint", "tinyint", "decimal", "numeric", "float", "real", "money", "smallmoney"]
                    mssql_text = ["varchar", "char", "text", "nvarchar", "nchar", "ntext"]
                    mssql_datetime = ["datetime", "datetime2", "smalldatetime", "date", "time", "datetimeoffset"]
                    columns = []
                    for col in columns_result:
                        columns.append({
                            "name": col["COLUMN_NAME"],
                            "dtype": col["DATA_TYPE"],
                            "nullable": col["IS_NULLABLE"] == "YES",
                            "is_numeric": col["DATA_TYPE"].lower() in mssql_numeric,
                            "is_categorical": col["DATA_TYPE"].lower() in mssql_text,
                            "is_datetime": col["DATA_TYPE"].lower() in mssql_datetime,
                            "unique_count": 0,
                            "null_count": 0,
                            "sample_values": []
                        })
                    try:
                        cursor.execute(f"SELECT TOP 10 * FROM [{table_name}]")
                        sample_result = cursor.fetchall()
                        sample_data = [dict(row) for row in sample_result]
                        for col in columns:
                            col_name = col["name"]
                            values = []
                            for row_data in sample_data:
                                v = row_data[col_name]
                                if col_name in row_data and v is not None and not (isinstance(v, float) and math.isnan(v)):
                                    values.append(v)
                            col["sample_values"] = values[:5]
                            col["unique_count"] = len(set(values)) if values else 0
                            col["null_count"] = len(sample_data) - len(values) if sample_data else 0
                    except Exception as e:
                        print(f"Warning: Could not get sample data: {e}")
                    cursor.execute(f"SELECT COUNT(*) AS cnt FROM [{table_name}]")
                    row = cursor.fetchone()
                    total_rows = row["cnt"]
                    conn.close()
                    return {
                        "dataset_id": dataset_id,
                        "columns": columns,
                        "total_rows": total_rows,
                        "total_columns": len(columns),
                        "row_count_known": True,
                        "source_type": source_type,
                        "storage_type": storage_type
                    }
                except Exception as e:
                    conn.close()
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.query_failed_7"], error=error_text(e))
                    )
            else:
                raise HTTPException(
                    status_code=501,
                    detail=await t(_db_pool, language, SCHEMA["error.connection.type_not_supported_2"], type=connection_row["type"])
                )
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error getting schema from external database: {e}")
            if sample_data and isinstance(sample_data, list):
                try:
                    df = pd.DataFrame(sample_data)
                    columns = []
                    for col in df.columns:
                        col_values = df[col].dropna().tolist()
                        columns.append({
                            "name": col,
                            "dtype": str(df[col].dtype),
                            "is_numeric": pd.api.types.is_numeric_dtype(df[col]),
                            "is_categorical": df[col].dtype == 'object',
                            "is_datetime": pd.api.types.is_datetime64_any_dtype(df[col]),
                            "unique_count": len(df[col].unique()),
                            "null_count": df[col].isna().sum(),
                            "sample_values": col_values[:5] if col_values else []
                        })
                    return {
                        "dataset_id": dataset_id,
                        "columns": columns,
                        "total_rows": len(df),
                        "total_columns": len(df.columns),
                        "row_count_known": True,
                        "source_type": source_type,
                        "storage_type": storage_type,
                        "warning": await t(_db_pool, language, SCHEMA["datasets.schema.from_preview"])
                    }
                except Exception as e2:
                    print(f"Error parsing dataSnapshot: {e2}")
            raise HTTPException(
                status_code=500,
                detail=await t(_db_pool, language, SCHEMA["datasets.schema.external_failed"], error=error_text(e))
            )
    
    elif source_type == "virtual" and virtual_sql:
        # From the definition, not by running it.
        #
        # This branch used to call materialise_virtual_dataset, which pulled every
        # source's rows and rebuilt a persistent table to answer "what columns
        # does this have?" — a write, on a read path, whose cost grew with the
        # data. Measured 2026-11-06: 60 seconds and a failure on a seven-source
        # dataset. See virtual_dataset_schema_from_definition.
        try:
            import json
            vsql = json.loads(virtual_sql) if isinstance(virtual_sql, str) else virtual_sql
            # The overview is the outer entry point, so it starts at depth 0: the
            # depth parameter exists for the recursion inside the helper, and this
            # function has no enclosing dataset to be nested in.
            # A materialised dataset owns a table in its owner's schema, and the
            # helper counts it when it is there. A live one has no table, so the
            # helper answers `row_count_known: False` and says why.
            materialized_table = (
                f"{user_schema_name(owner_id)}.virtual_{dataset_id}"
                if row["materialized"] else ""
            )
            described = await virtual_dataset_schema_from_definition(
                vsql, user_id, language, materialized_table
            )
            return {
                "dataset_id": dataset_id,
                "columns": described["columns"],
                "total_rows": described["total_rows"],
                "total_columns": described["total_columns"],
                "row_count_known": described.get("row_count_known", False),
                "source_type": source_type,
                "storage_type": storage_type,
                "unread": described["unread"],
                "warning": described["warning"],
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=await t(_db_pool, language, SCHEMA["datasets.schema.load_error"], error=error_text(e))
            )
    else:
        raise HTTPException(
            status_code=501,
            detail=await t(_db_pool, language, SCHEMA["datasets.schema.not_implemented"], type=source_type)
        )


async def _describe_pg_table_columns(table_name: str):
    """Describe a PostgreSQL table in workbench_data without its statistics.

    ``_describe_pg_table`` with both full-table scans removed: the
    ``SELECT COUNT(*)`` inside ``get_table_statistics``, and the per-column
    ``COUNT(DISTINCT ...), COUNT(*) - ...`` aggregate. ``unique_count`` and
    ``null_count`` therefore stay 0, and no row count is returned at all.

    Returns ``(columns, total_columns)``, or ``(None, 0)`` when the table is
    missing. Shared by the narrow ``fetch_dataset_schema``.
    """

    if not await table_exists(table_name):
        return None, 0

    schema = await get_table_schema(table_name)

    columns = []
    for col_info in schema:
        dtype = col_info["type"]
        col_data = {
            "name": col_info["name"],
            "dtype": dtype,
            "nullable": col_info["nullable"],
            "is_numeric": any(t in dtype.upper() for t in ("INT", "FLOAT", "DOUBLE", "DECIMAL", "NUMERIC", "REAL")),
            "is_categorical": "VARCHAR" in dtype.upper() or "TEXT" in dtype.upper(),
            "is_datetime": "TIMESTAMP" in dtype.upper() or "DATE" in dtype.upper() or "TIME" in dtype.upper(),
            "unique_count": 0,
            "null_count": 0,
            "sample_values": []
        }
        columns.append(col_data)

    # Example values for display only — not statistics.
    try:
        preview_rows = await get_table_preview(table_name, limit=10)
        if preview_rows:
            for col in columns:
                col_name = col["name"]
                col["sample_values"] = [
                    r.get(col_name)
                    for r in preview_rows
                    if r.get(col_name) is not None
                    and not (isinstance(r.get(col_name), float) and math.isnan(r.get(col_name)))
                ][:5]
    except Exception as e:
        print(f"Warning: Could not get sample data from workbench_data: {e}")

    return columns, len(columns)


async def fetch_dataset_schema(
    dataset_id: str,
    user_id: str,
    language: str,
    _depth: int = 0,
):
    """Return the schema of a dataset, without asking for its row count.

    ``fetch_dataset_overview`` with every ``SELECT COUNT(*)`` removed: the count
    in each external-connection branch, and both full-table scans behind
    ``_describe_pg_table``. Columns, types, nullability and the bounded ten-row
    sample values are unchanged.

    There is deliberately no ``total_rows`` key rather than a zero: zero would
    claim the table is empty, while an absent key says the question was not
    asked. Prefer this reader wherever the count is not going to be shown — on
    a large or remote source it is a full scan, not a metadata read.
    """
    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT "sourceType", "storageType", "sourceConnectionId", 
                   "databaseName", "tableName", "dataSnapshot", "virtualSql"
            FROM "UserDataset"
            WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                SELECT "userGroup" FROM "User" WHERE id = $2
            )))
            """,
            dataset_id, user_id
        )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, SCHEMA["error.dataset.not_found_5"], id=dataset_id)
        )

    source_type = row["sourceType"]
    storage_type = row["storageType"]
    source_connection_id = row["sourceConnectionId"]
    table_name = row["tableName"]
    data_snapshot = row["dataSnapshot"]
    virtual_sql_raw = row.get("virtualSql")
    virtual_sql = virtual_sql_raw or {}
    
    sample_data = []
    if data_snapshot:
        if isinstance(data_snapshot, list):
            sample_data = data_snapshot
        elif isinstance(data_snapshot, dict):
            sample_data = [data_snapshot]

    if source_type in ("upload", "notebook") and storage_type == "postgresql" and table_name:
        try:
            columns, total_columns = await _describe_pg_table_columns(table_name)
            if columns is None:
                return {
                    "dataset_id": dataset_id,
                    "columns": [],
                    "total_columns": 0,
                    "source_type": source_type,
                    "storage_type": storage_type,
                    "warning": await t(_db_pool, language, SCHEMA["datasets.schema.table_missing"])
                }
            return {
                "dataset_id": dataset_id,
                "columns": columns,
                "total_columns": total_columns,
                "source_type": source_type,
                "storage_type": storage_type
            }
        except Exception as e:
            print(f"Error getting schema from workbench_data: {e}")
            return {
                "dataset_id": dataset_id,
                "columns": [],
                "total_columns": 0,
                "source_type": source_type,
                "storage_type": storage_type,
                "warning": await t(_db_pool, language, SCHEMA["datasets.schema.load_error"], error=error_text(e))
            }

    elif source_type in ["table", "view", "access", "mssql", "mysql", "postgresql"] and source_connection_id and table_name:
        try:
            connection_row = await get_connection_row(source_connection_id, user_id, language)
            if connection_row is None:
                raise HTTPException(
                    status_code=404,
                    detail=await t(_db_pool, language, SCHEMA["error.define.connection_not_found"])
                )
            
            if connection_row["type"] in ("postgresql", "access"):
                from src.utils.encryption import decrypt_field
                try:
                    decrypted_password = decrypt_field(connection_row["password"])
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.decryption_failed"], error=error_text(e))
                    )
                
                conn_str = f"postgresql://{connection_row['username']}:{decrypted_password}@{connection_row['host']}:{connection_row['port']}/{connection_row['database']}"
                try:
                    ext_conn = await asyncpg.connect(conn_str)
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.failed"], error=error_text(e))
                    )
                
                try:
                    # The session's own schema, not `public` — see common/relations.py.
                    columns_query = columns_of_visible_relation("$1")
                    columns_result = await ext_conn.fetch(columns_query, table_name)
                    
                    columns = []
                    for col in columns_result:
                        columns.append({
                            "name": col["column_name"],
                            "dtype": col["data_type"],
                            "nullable": col["is_nullable"] == "YES",
                            "is_numeric": col["data_type"] in ["integer", "bigint", "smallint", "decimal", "numeric", "real", "double precision", "float"],
                            "is_categorical": col["data_type"] in ["character varying", "varchar", "text", "character", "char"],
                            "is_datetime": col["data_type"] in ["timestamp", "timestamp without time zone", "timestamp with time zone", "date", "time"],
                            "unique_count": 0,
                            "null_count": 0,
                            "sample_values": []
                        })
                    
                    try:
                        sample_query = f'SELECT * FROM "{table_name}" LIMIT 10'
                        sample_result = await ext_conn.fetch(sample_query)
                        sample_data = [dict(row) for row in sample_result]
                        
                        for col in columns:
                            col_name = col["name"]
                            values = []
                            for row_data in sample_data:
                                v = row_data[col_name]
                                if col_name in row_data and v is not None and not (isinstance(v, float) and math.isnan(v)):
                                    values.append(v)
                            col["sample_values"] = values[:5]
                            col["unique_count"] = len(set(values)) if values else 0
                            col["null_count"] = len(sample_data) - len(values) if sample_data else 0
                    except Exception as e:
                        print(f"Warning: Could not get sample data: {e}")
                    
                    await ext_conn.close()
                    
                    return {
                        "dataset_id": dataset_id,
                        "columns": columns,
                        "total_columns": len(columns),
                        "source_type": source_type,
                        "storage_type": storage_type
                    }
                except Exception as e:
                    await ext_conn.close()
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.query_failed_7"], error=error_text(e))
                    )
            elif connection_row["type"] == "mysql":
                import aiomysql
                from src.utils.encryption import decrypt_field
                try:
                    decrypted_password = decrypt_field(connection_row["password"])
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.decryption_failed"], error=error_text(e))
                    )
                
                try:
                    mysql_conn = await aiomysql.connect(
                        host=connection_row["host"],
                        port=connection_row["port"],
                        db=connection_row["database"],
                        user=connection_row["username"],
                        password=decrypted_password,
                    )
                except Exception as e:
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.failed"], error=error_text(e))
                    )
                
                try:
                    async with mysql_conn.cursor(aiomysql.DictCursor) as cur:
                        await cur.execute(
                            "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE "
                            "FROM information_schema.COLUMNS "
                            "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                            "ORDER BY ORDINAL_POSITION",
                            (connection_row["database"], table_name)
                        )
                        columns_result = await cur.fetchall()
                        
                        mysql_numeric = ["int", "bigint", "smallint", "tinyint", "decimal", "numeric", "float", "double", "real"]
                        mysql_text = ["varchar", "char", "text", "longtext", "mediumtext", "tinytext"]
                        mysql_datetime = ["datetime", "timestamp", "date", "time", "year"]
                        
                        columns = []
                        for col in columns_result:
                            columns.append({
                                "name": col["COLUMN_NAME"],
                                "dtype": col["DATA_TYPE"],
                                "nullable": col["IS_NULLABLE"] == "YES",
                                "is_numeric": col["DATA_TYPE"].lower() in mysql_numeric,
                                "is_categorical": col["DATA_TYPE"].lower() in mysql_text,
                                "is_datetime": col["DATA_TYPE"].lower() in mysql_datetime,
                                "unique_count": 0,
                                "null_count": 0,
                                "sample_values": []
                            })
                        
                        try:
                            await cur.execute(f"SELECT * FROM `{table_name}` LIMIT 10")
                            sample_result = await cur.fetchall()
                            sample_data = [dict(row) for row in sample_result]
                            
                            for col in columns:
                                col_name = col["name"]
                                values = []
                                for row_data in sample_data:
                                    v = row_data[col_name]
                                    if col_name in row_data and v is not None and not (isinstance(v, float) and math.isnan(v)):
                                        values.append(v)
                                col["sample_values"] = values[:5]
                                col["unique_count"] = len(set(values)) if values else 0
                                col["null_count"] = len(sample_data) - len(values) if sample_data else 0
                        except Exception as e:
                            print(f"Warning: Could not get sample data: {e}")
                        
                        mysql_conn.close()
                        
                        return {
                            "dataset_id": dataset_id,
                            "columns": columns,
                            "total_columns": len(columns),
                            "source_type": source_type,
                            "storage_type": storage_type
                        }
                except Exception as e:
                    mysql_conn.close()
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.query_failed_7"], error=error_text(e))
                    )
            elif connection_row["type"] == "mssql":
                import pymssql
                from src.utils.encryption import decrypt_field
                try:
                    decrypted_password = decrypt_field(connection_row["password"])
                except Exception as e:
                    raise HTTPException(
                        status_code=500,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.decryption_failed"], error=error_text(e))
                    )
                def _connect():
                    return pymssql.connect(
                        host=connection_row["host"],
                        port=connection_row["port"],
                        database=connection_row["database"],
                        user=connection_row["username"],
                        password=decrypted_password,
                    )
                conn = await asyncio.to_thread(_connect)
                try:
                    cursor = conn.cursor(as_dict=True)
                    cursor.execute(
                        "SELECT COLUMN_NAME, DATA_TYPE, IS_NULLABLE "
                        "FROM INFORMATION_SCHEMA.COLUMNS "
                        "WHERE TABLE_SCHEMA = %s AND TABLE_NAME = %s "
                        "ORDER BY ORDINAL_POSITION",
                        (connection_row.get("schema", "dbo"), table_name)
                    )
                    columns_result = cursor.fetchall()
                    mssql_numeric = ["int", "bigint", "smallint", "tinyint", "decimal", "numeric", "float", "real", "money", "smallmoney"]
                    mssql_text = ["varchar", "char", "text", "nvarchar", "nchar", "ntext"]
                    mssql_datetime = ["datetime", "datetime2", "smalldatetime", "date", "time", "datetimeoffset"]
                    columns = []
                    for col in columns_result:
                        columns.append({
                            "name": col["COLUMN_NAME"],
                            "dtype": col["DATA_TYPE"],
                            "nullable": col["IS_NULLABLE"] == "YES",
                            "is_numeric": col["DATA_TYPE"].lower() in mssql_numeric,
                            "is_categorical": col["DATA_TYPE"].lower() in mssql_text,
                            "is_datetime": col["DATA_TYPE"].lower() in mssql_datetime,
                            "unique_count": 0,
                            "null_count": 0,
                            "sample_values": []
                        })
                    try:
                        cursor.execute(f"SELECT TOP 10 * FROM [{table_name}]")
                        sample_result = cursor.fetchall()
                        sample_data = [dict(row) for row in sample_result]
                        for col in columns:
                            col_name = col["name"]
                            values = []
                            for row_data in sample_data:
                                v = row_data[col_name]
                                if col_name in row_data and v is not None and not (isinstance(v, float) and math.isnan(v)):
                                    values.append(v)
                            col["sample_values"] = values[:5]
                            col["unique_count"] = len(set(values)) if values else 0
                            col["null_count"] = len(sample_data) - len(values) if sample_data else 0
                    except Exception as e:
                        print(f"Warning: Could not get sample data: {e}")
                    conn.close()
                    return {
                        "dataset_id": dataset_id,
                        "columns": columns,
                        "total_columns": len(columns),
                        "source_type": source_type,
                        "storage_type": storage_type
                    }
                except Exception as e:
                    conn.close()
                    raise HTTPException(
                        status_code=400,
                        detail=await t(_db_pool, language, SCHEMA["error.connection.query_failed_7"], error=error_text(e))
                    )
            else:
                raise HTTPException(
                    status_code=501,
                    detail=await t(_db_pool, language, SCHEMA["error.connection.type_not_supported_2"], type=connection_row["type"])
                )
        except HTTPException:
            raise
        except Exception as e:
            print(f"Error getting schema from external database: {e}")
            if sample_data and isinstance(sample_data, list):
                try:
                    df = pd.DataFrame(sample_data)
                    columns = []
                    for col in df.columns:
                        col_values = df[col].dropna().tolist()
                        columns.append({
                            "name": col,
                            "dtype": str(df[col].dtype),
                            "is_numeric": pd.api.types.is_numeric_dtype(df[col]),
                            "is_categorical": df[col].dtype == 'object',
                            "is_datetime": pd.api.types.is_datetime64_any_dtype(df[col]),
                            "unique_count": len(df[col].unique()),
                            "null_count": df[col].isna().sum(),
                            "sample_values": col_values[:5] if col_values else []
                        })
                    return {
                        "dataset_id": dataset_id,
                        "columns": columns,
                        "total_columns": len(df.columns),
                        "source_type": source_type,
                        "storage_type": storage_type,
                        "warning": await t(_db_pool, language, SCHEMA["datasets.schema.from_preview"])
                    }
                except Exception as e2:
                    print(f"Error parsing dataSnapshot: {e2}")
            raise HTTPException(
                status_code=500,
                detail=await t(_db_pool, language, SCHEMA["datasets.schema.external_failed"], error=error_text(e))
            )
    
    elif source_type == "virtual" and virtual_sql:
        # From the definition, not by running it — the same rule as the overview
        # path above, and the reason `fetch_dataset_schema` exists at all.
        try:
            import json
            vsql = json.loads(virtual_sql) if isinstance(virtual_sql, str) else virtual_sql
            described = await virtual_dataset_schema_from_definition(
                vsql, user_id, language, _depth=_depth
            )
            return {
                "dataset_id": dataset_id,
                "columns": described["columns"],
                "total_columns": described["total_columns"],
                "source_type": source_type,
                "storage_type": storage_type,
                "unread": described["unread"],
                "warning": described["warning"],
            }
        except Exception as e:
            import traceback
            traceback.print_exc()
            raise HTTPException(
                status_code=500,
                detail=await t(_db_pool, language, SCHEMA["datasets.schema.load_error"], error=error_text(e))
            )
    else:
        raise HTTPException(
            status_code=501,
            detail=await t(_db_pool, language, SCHEMA["datasets.schema.not_implemented"], type=source_type)
        )
