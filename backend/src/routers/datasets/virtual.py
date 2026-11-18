"""
Virtual Datasets – AI-guided PostgreSQL federated SQL join views.
Create, validate, preview, and execute virtual datasets.
"""

import json

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.routers.datasets.crud import get_user_id_from_token, get_current_language, get_connection_row, can_edit_dataset
from src.utils.translation import t
from src.utils.encryption import decrypt_field
from .translations import DATASETS, SCHEMA
from src.routers.datasets.sql_dialect import quote_table, quote_identifier
from src.routers.common.translations import error_define_connection_not_found_2
from src.routers.datasets.connection_probe import fresh_failures
from src.routers.datasets.data_access import (
    execute_connection_sql_rows,
    execute_compiled_sql_rows,
)
from src.postgres_data_manager import (
    materialize_temp_table_from_rows, get_data_pool, ensure_user_schema, user_schema_name
)

_db_pool = None

def set_db_pool(pool):
    global _db_pool
    _db_pool = pool

router = APIRouter(prefix="/virtual", tags=["virtual-datasets"])
security = HTTPBearer()

# How many rows the join preview returns. Raised from 10 on 2026-09-25: the corpus
# Item 12 observes is fourteen rows, and a ten-row window cannot show its last
# four. The limit is appended to the join SQL itself, so it is also a
# response-size decision rather than "every row".
_PREVIEW_ROW_LIMIT = 20


# ── Save ────────────────────────────────────────────────────

def _definition_changed(previous, incoming) -> bool:
    """Does this save change the definition, as opposed to its metadata?

    Structural comparison of the parsed definition, so key order and the
    difference between a decoded int and a float cannot manufacture a change —
    the same rule `joinDiffLines` uses for two join sets, applied to a whole
    definition.

    A save that only renames the dataset must not re-run the join. Without this,
    every metadata edit costs the full build, which is how a table gets rebuilt
    for a reason nobody asked for.
    """
    before = previous
    if isinstance(before, str):
        try:
            before = json.loads(before)
        except Exception:
            before = None
    return (before or {}) != (incoming or {})


async def apply_materialisation(db_pool, dataset_id: str, virtual_sql: dict, user_id: str,
                                language: str, *, must_build: bool, should_drop: bool) -> dict:
    """Carry out the materialisation decision for one dataset, and record it.

    The two flags are decisions, not states: `must_build` says the definition
    changed (or the table was never built), `should_drop` says the user turned the
    choice off. Both default false, so a metadata-only save does nothing at all.

    **A failure is recorded, never raised.** The definition is already committed;
    undo would discard the user's work to report an operational problem they can
    fix. What comes back is the state as it now stands:
    `materializedAt` non-null means current, null means not built, and
    `materializeError` says why the last attempt failed.

    Returns ``{attempted, materializedAt, materializeError}``.
    """
    from src.postgres_data_manager import drop_table, user_schema_name

    result = {"attempted": False, "materializedAt": None, "materializeError": None}
    table_name = f"{user_schema_name(user_id)}.virtual_{dataset_id}"

    if should_drop:
        # The choice was switched off. The table is debris under a name that means
        # "this dataset is materialised", so it goes — and a failed drop is
        # reported the same way a failed build is, rather than swallowed.
        try:
            await drop_table(table_name)
        except Exception as exc:
            from .data_access import error_text

            result["materializeError"] = error_text(exc)
            async with db_pool.acquire() as conn:
                await conn.execute(
                    'UPDATE "UserDataset" SET "materializeError" = $2, "materializedAt" = NULL, '
                    '"updatedAt" = NOW() WHERE id = $1',
                    dataset_id, result["materializeError"],
                )
            return result

    if not must_build:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT "materializedAt", "materializeError" FROM "UserDataset" WHERE id = $1',
                dataset_id,
            )
        if row:
            result["materializedAt"] = row["materializedAt"]
            result["materializeError"] = row["materializeError"]
        return result

    result["attempted"] = True
    try:
        await materialize_virtual_dataset(dataset_id, virtual_sql or {}, user_id, db_pool, language)
        async with db_pool.acquire() as conn:
            # Plain NOW() as of 2026-11-08: `materializedAt` is a `timestamptz`, so the
            # value is an instant and needs no zone assertion. The `AT TIME ZONE 'UTC'`
            # wrapper belonged to the naive column and would now store seven hours early.
            row = await conn.fetchrow(
                'UPDATE "UserDataset" SET "materializedAt" = NOW(), '
                '"materializeError" = NULL, "updatedAt" = NOW() '
                'WHERE id = $1 RETURNING "materializedAt"',
                dataset_id,
            )
        result["materializedAt"] = row["materializedAt"] if row else None
    except Exception as exc:
        from .data_access import error_text

        result["materializeError"] = error_text(exc)
        async with db_pool.acquire() as conn:
            await conn.execute(
                'UPDATE "UserDataset" SET "materializeError" = $2, "materializedAt" = NULL, '
                '"updatedAt" = NOW() WHERE id = $1',
                dataset_id, result["materializeError"],
            )
    return result


async def save_virtual_dataset_record(
    db_pool,
    user_id: str,
    body: dict,
    language: str,
) -> dict:
    """Create or update a virtual dataset row.

    Shared by ``POST /save`` and the AI ``save_virtual_dataset`` tool so both
    write through the same code path."""
    dataset_id = body.get("id")
    name = body.get("name", "Untitled Virtual Dataset")
    description = body.get("description")
    virtual_sql = body.get("virtualSql")
    materialized = body.get("materialized", False)
    source_dataset_ids = body.get("sourceDatasetIds", [])
    source_connection_ids = body.get("sourceConnectionIds", [])
    output_schema = body.get("outputSchema")
    status = body.get("status", "ready")
    dataset_group = body.get("datasetGroup", "00")

    # ── the save gate (Item 8) ──────────────────────────────
    #
    # Neither surface enforced its own save gate on the server: the manual editor
    # checked in the client and the concierge's tool called this function
    # directly, so a definition the UI would have refused could be written by a
    # caller that skipped the check. The gate belongs where the write happens,
    # not in the client that built it.
    #
    # It runs the SAME validator the /validate endpoint uses, so the answer a
    # caller gets from validating is the answer the save applies — one rule set,
    # not a second opinion kept in step by hand.
    if virtual_sql is None:
        raise HTTPException(status_code=400, detail=await t(db_pool, language, DATASETS["virtual.validate.no_sources"]))

    verdict = await validate_virtual_dataset_definition(db_pool, user_id, virtual_sql, language)
    if not verdict.get("valid"):
        # A coded 400 rather than a 500: the definition is the caller's to fix,
        # and the messages say which part of it. `{errors}` carries the validator's
        # own sentences, already translated.
        raise HTTPException(
            status_code=400,
            detail=await t(
                db_pool, language, DATASETS["virtual.save.invalid_definition"],
                errors="; ".join(verdict.get("errors") or []),
            ),
        )
    # The schema the validator just read is the one to store: the columns were
    # checked against real introspection, so writing them costs nothing extra and
    # writing "UNKNOWN" would throw away the answer we already have.
    if verdict.get("outputSchema"):
        output_schema = verdict["outputSchema"]

    previous = None
    definition_changed = True  # a new row has nothing to be unchanged from

    async with db_pool.acquire() as conn:
        if dataset_id:
            # Update existing
            existing = await conn.fetchrow(
                'SELECT "userId", "virtualSql", "materialized", "materializedAt" '
                'FROM "UserDataset" WHERE id = $1', dataset_id
            )
            if not existing:
                raise HTTPException(status_code=404, detail=await t(db_pool, language, DATASETS["datasets.not_found_2"]))
            # Who may change the row: its owner, or an administrator when the dataset is
            # shared to their group (can_edit_dataset) — the rule every dataset write
            # asks, replacing the owner-only test. The refusal keeps its existing
            # shape: the row is known to exist at this point, so a caller who may not
            # change it gets a 403, not the 404 the not-found branch gives.
            if not await can_edit_dataset(db_pool, dataset_id, user_id):
                raise HTTPException(status_code=403, detail=await t(db_pool, language, DATASETS["datasets.not_owner"]))

            previous = existing
            definition_changed = _definition_changed(existing["virtualSql"], virtual_sql)

            await conn.execute(
                """
                UPDATE "UserDataset"
                SET name = $2, description = $3, "sourceType" = 'virtual',
                    "virtualSql" = $4, "materialized" = $5,
                    "sourceDatasetIds" = $6, "sourceConnectionIds" = $7,
                    "outputSchema" = $8, status = $9, "datasetGroup" = $10,
                    -- Cleared here, before any attempt: a timestamp that survived
                    -- a changed definition would claim the table was current for a
                    -- definition it was not built from. The attempt below sets it
                    -- again on success.
                    "materializedAt" = CASE WHEN $11 THEN NULL ELSE "materializedAt" END,
                    "materializeError" = CASE WHEN $11 THEN NULL ELSE "materializeError" END,
                    "updatedAt" = NOW()
                WHERE id = $1
                """,
                dataset_id, name, description, virtual_sql if virtual_sql else None,
                materialized, source_dataset_ids, source_connection_ids,
                output_schema if output_schema else None,
                status, dataset_group, definition_changed
            )
        else:
            # Create new
            import uuid
            new_id = body.get("id") or f"vd_{uuid.uuid4().hex[:16]}"
            await conn.execute(
                """
                INSERT INTO "UserDataset" (
                    id, "userId", name, description, "sourceType",
                    "virtualSql", "materialized", "sourceDatasetIds",
                    "sourceConnectionIds", "outputSchema", status, "datasetGroup",
                    "materializedAt", "materializeError", "updatedAt"
                ) VALUES ($1, $2, $3, $4, 'virtual', $5, $6, $7, $8, $9, $10, $11,
                          -- A row created now has never been built; the attempt
                          -- after this write is what records it.
                          NULL, NULL, NOW())
                """,
                new_id, user_id, name, description,
                virtual_sql if virtual_sql else None,
                materialized,
                source_dataset_ids, source_connection_ids,
                output_schema if output_schema else None,
                status, dataset_group
            )
            dataset_id = new_id

    # ── the materialisation attempt, after the definition is written ──────
    #
    # Save-and-report: the definition is the user's and is already committed, so
    # a build failure must not undo it. The failure is carried in the response and
    # stored, which is what lets a user return tomorrow, see that the table was
    # never built, and retry it.
    #
    # Only when it is needed. A save that renamed the dataset must not re-run the
    # join: that would make a metadata edit as expensive as the data, and it would
    # rebuld a table that is already correct.
    must_build = bool(materialized) and (definition_changed or not (previous or {}).get("materializedAt"))
    was_materialized = bool((previous or {}).get("materialized"))
    should_drop = was_materialized and not materialized

    attempt = await apply_materialisation(
        db_pool, dataset_id, virtual_sql, user_id, language,
        must_build=must_build, should_drop=should_drop,
    )

    return {
        "id": dataset_id,
        "status": status,
        "materialized": bool(materialized),
        "materializedAt": attempt["materializedAt"],
        "materializeError": attempt["materializeError"],
        "materializeAttempted": attempt["attempted"],
    }


@router.post("/save")
async def save_virtual_dataset(
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Create or update a virtual dataset.
    If `id` is present, update the existing record; otherwise create new.
    """
    global _db_pool
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    return await save_virtual_dataset_record(_db_pool, user_id, body, language)


# ── Retry the materialisation ───────────────────────────────
#
# Its own route because it is its own decision. A save that failed to build a
# table is a saved dataset; the user fixes the operational problem and asks again,
# and that request carries no definition to write — it re-runs what is already
# stored. Folding it into save would mean re-submitting the definition to retry,
# which is how a stale client overwrites a newer dataset.
#
# Idempotent: building an already-current table rebuilds it. Cheap enough to be
# a button, and simpler than a check that has to decide what "current" means
# twice.

@router.post("/{dataset_id}/materialize")
async def retry_materialisation(
    dataset_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Build (or rebuild) a materialised virtual dataset from its stored definition."""
    global _db_pool
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT id, "virtualSql", "materialized" FROM "UserDataset" '
            "WHERE id = $1 AND \"sourceType\" = 'virtual'",
            dataset_id,
        )
    if not row:
        raise HTTPException(status_code=404, detail=await t(_db_pool, language, DATASETS["virtual.validate.dataset_not_found"]))

    if not await can_edit_dataset(_db_pool, dataset_id, user_id):
        raise HTTPException(status_code=404, detail=await t(_db_pool, language, DATASETS["virtual.validate.dataset_not_found"]))

    # Asking to build is asking for the table, so the choice is recorded too. A
    # dataset whose switch says live but whose route was pressed is incoherent;
    # making the retry set the choice keeps the two in step.
    async with _db_pool.acquire() as conn:
        await conn.execute(
            'UPDATE "UserDataset" SET "materialized" = true, "updatedAt" = NOW() WHERE id = $1',
            dataset_id,
        )

    virtual_sql = row["virtualSql"]
    if isinstance(virtual_sql, str):
        try:
            virtual_sql = json.loads(virtual_sql)
        except Exception:
            virtual_sql = {}
    attempt = await apply_materialisation(
        _db_pool, dataset_id, virtual_sql or {}, user_id, language,
        must_build=True, should_drop=False,
    )
    return {"id": dataset_id, "materialized": True, **attempt}


# ── Read a stored definition ────────────────────────────────

@router.get("/definition/{dataset_id}")
async def get_virtual_dataset_definition(
    dataset_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Read a stored virtual dataset definition, so one can be reopened for editing.

    The dataset read routes deliberately do not expose "virtualSql" (crud.py), so
    this is the only way a saved definition is readable over HTTP. Visible to the
    owner, or to a member of the group the dataset is shared with — the same
    predicate the dataset list and fetch_dataset_schema use, so the editor can
    open every dataset it offers. Reading is not editing: saving keeps its own rule —
    the dataset's owner, or an administrator when it is shared to the group that
    administrator belongs to — enforced in save_virtual_dataset_record.

    The static "definition/" segment is deliberate: this router is included before
    virtual_chat's (datasets/__init__.py), and FastAPI matches routes in
    registration order, so a bare "/{dataset_id}" here would shadow
    GET /virtual/chat and read "chat" as a dataset id.
    """
    global _db_pool
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, name, description, "virtualSql", "materialized",
                   "outputSchema", status
            FROM "UserDataset"
            WHERE id = $1 AND "sourceType" = 'virtual'
              AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                  SELECT "userGroup" FROM "User" WHERE id = $2
              )))
            """,
            dataset_id, user_id
        )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, DATASETS["error.dataset.not_found_2"], id=dataset_id)
        )

    virtual_sql = row["virtualSql"]
    # A row whose definition was written before the pool's jsonb codec existed can
    # hold a double-encoded string. preparation.py repairs this same column the same
    # way when it materialises a virtual dataset; the two readers must agree.
    if isinstance(virtual_sql, str):
        virtual_sql = json.loads(virtual_sql)

    return {
        "id": row["id"],
        "name": row["name"],
        "description": row["description"],
        "virtualSql": virtual_sql,
        "materialized": row["materialized"],
        "outputSchema": row["outputSchema"],
        "status": row["status"],
        # Whether *this* caller may save it — the rule the save itself enforces
        # (can_edit_dataset), so the editor's notice states what saving will do rather
        # than re-deriving the rule from ownership in the client.
        "canEdit": await can_edit_dataset(_db_pool, dataset_id, user_id),
    }


# ── Validate ────────────────────────────────────────────────

async def _source_columns(db_pool, user_id: str, language: str, src: dict):
    """The columns a source offers, as ``{name: type}`` — or None if unreadable.

    One read serving two questions: does this column exist, and what is its type.
    The alternative — asking existence from one place and type from another —
    is how "UNKNOWN" survived as every column's type while the docstring claimed
    the columns were checked.

    Returns ``None`` rather than an empty dict when the read fails. An empty dict
    means "this table has no columns", which would then be reported as every
    column being wrong; ``None`` means "we could not look", which is a different
    answer and must not be told as the first.
    """
    from .browse import list_table_columns
    from .schema import fetch_dataset_schema

    try:
        if src.get("datasetId"):
            schema = await fetch_dataset_schema(src["datasetId"], user_id, language)
            return {
                column.get("name"): column.get("dtype")
                for column in schema.get("columns", [])
                if column.get("name")
            }
        if src.get("connectionId") and src.get("tableName"):
            columns = await list_table_columns(
                db_pool, user_id, language, int(src["connectionId"]), src["tableName"]
            )
            return {
                column.get("name"): column.get("type")
                for column in columns
                if column.get("name")
            }
    except Exception:
        # A source that resolved but cannot be read is not a definition error —
        # it is an environment one. The columns stay unknown and every column
        # check that depends on them is skipped rather than failed.
        return None
    return None


async def validate_virtual_dataset_definition(
    db_pool,
    user_id: str,
    virtual_sql: dict,
    language: str,
) -> dict:
    """Validate a virtual dataset definition.

    Shared by ``POST /validate`` and the AI ``validate_virtual_dataset`` tool
    so both check through the same code path."""
    errors = []
    sources = virtual_sql.get("sources", [])
    joins = virtual_sql.get("joins", [])
    columns = virtual_sql.get("columns", [])

    if not sources:
        errors.append(await t(db_pool, language, DATASETS["virtual.validate.no_sources"]))
        return {"valid": False, "errors": errors}

    # Validate each source exists and is accessible
    source_schemas = {}
    for i, src in enumerate(sources):
        alias = src.get("alias", f"source_{i}")
        storage_type = src.get("storageType")

        if src.get("datasetId"):
            dataset_id = src.get("datasetId")
            if not dataset_id:
                errors.append(await t(db_pool, language, DATASETS["virtual.validate.dataset_id_required"], alias=alias))
                continue
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT id, name, "tableName" FROM "UserDataset"
                    WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                        SELECT "userGroup" FROM "User" WHERE id = $2
                    )))
                    """,
                    dataset_id, user_id
                )
                if not row:
                    errors.append(await t(db_pool, language, DATASETS["virtual.validate.dataset_not_found"], alias=alias, dataset_id=dataset_id))
                    continue
                src["_tableName"] = row["tableName"] or row["name"]
        else:
            conn_id = src.get("connectionId")
            if not conn_id:
                errors.append(await t(db_pool, language, DATASETS["virtual.validate.connection_id_required"], alias=alias, storage_type=storage_type))
                continue
            async with db_pool.acquire() as conn:
                row = await conn.fetchrow(
                    """
                    SELECT "connectionId" FROM "UserDatabaseConnection"
                    WHERE "connectionId" = $1 AND ("userId" = $2 OR ("isShared" = true AND "dbConnectionGroup" IN (
                        SELECT "userGroup" FROM "User" WHERE id = $2
                    )))
                    """,
                    conn_id, user_id
                )
                if not row:
                    errors.append(await t(db_pool, language, DATASETS["virtual.validate.connection_not_found"], alias=alias, conn_id=conn_id))
                    continue

        # Read the source's columns, so the checks below can ask whether a join
        # or output column EXISTS rather than merely whether its alias does.
        # Before this, `validate_virtual_dataset` promised in its own tool
        # description that it checked "join columns exist" and never did — it
        # compared aliases and stopped. A definition naming a column that is not
        # there validated as `{valid: true}` and failed later, at preview or
        # execute, as a database error instead of a field-level message.
        #
        # `_columns` is None when the read failed: the source resolved, but its
        # schema could not be read. That is reported separately below rather
        # than treated as "no such column", because the two are different
        # answers and the second would be a lie about a table we could not see.
        src["_columns"] = await _source_columns(db_pool, user_id, language, src)
        source_schemas[alias] = src

    if errors:
        return {"valid": False, "errors": errors}

    # Validate join columns exist in sources
    for j_idx, join in enumerate(joins):
        left_alias = join.get("left")
        right_alias = join.get("right")
        left_col = join.get("leftCol")
        right_col = join.get("rightCol")

        if left_alias not in source_schemas:
            errors.append(await t(db_pool, language, DATASETS["virtual.validate.join_left_source_not_found"], j_idx=j_idx, left_alias=left_alias))
        if right_alias not in source_schemas:
            errors.append(await t(db_pool, language, DATASETS["virtual.validate.join_right_source_not_found"], j_idx=j_idx, right_alias=right_alias))
        # Each join column must exist on its own side. Skipped when that source's
        # schema could not be read — an unread table is not evidence of a missing
        # column.
        if left_alias in source_schemas and left_col:
            known = source_schemas[left_alias].get("_columns")
            if known is not None and left_col not in known:
                errors.append(await t(db_pool, language, DATASETS["virtual.validate.join_column_not_found"], j_idx=j_idx, alias=left_alias, column=left_col))
        if right_alias in source_schemas and right_col:
            known = source_schemas[right_alias].get("_columns")
            if known is not None and right_col not in known:
                errors.append(await t(db_pool, language, DATASETS["virtual.validate.join_column_not_found"], j_idx=j_idx, alias=right_alias, column=right_col))

    # Validate output columns
    selected_columns = []
    for c_idx, col in enumerate(columns):
        src_alias = col.get("source")
        col_name = col.get("column")
        if src_alias not in source_schemas:
            errors.append(await t(db_pool, language, DATASETS["virtual.validate.column_source_not_found"], c_idx=c_idx, src_alias=src_alias))
            continue
        known = source_schemas[src_alias].get("_columns")
        if known is not None and col_name not in known:
            errors.append(await t(db_pool, language, DATASETS["virtual.validate.output_column_not_found"], c_idx=c_idx, src_alias=src_alias, column=col_name))
            continue
        # The type the column was READ with, not "UNKNOWN". This is decision 2's
        # fill, folded into this item: the same introspection that proves the
        # column exists yields its type, so writing the type costs nothing extra.
        # A source whose schema could not be read still reports UNKNOWN, and that
        # is now the only reason a column's type is unknown.
        column_type = (known or {}).get(col_name) or "UNKNOWN"
        selected_columns.append({"name": f"{src_alias}_{col_name}", "type": column_type})

    result = {
        "valid": len(errors) == 0,
        "errors": errors,
    }

    if result["valid"]:
        result["outputSchema"] = selected_columns
        result["status"] = "ready"

    return result


@router.post("/validate")
async def validate_virtual_dataset(
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Validate a virtual dataset definition.
    Checks: sources exist, introspection succeeds, join columns exist,
    permissions, type compatibility.
    Returns structured errors or success with outputSchema.
    """
    global _db_pool
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    return await validate_virtual_dataset_definition(
        _db_pool, user_id, body.get("virtualSql", {}), language
    )


# ── Preview ─────────────────────────────────────────────────

@router.post("/preview")
async def preview_virtual_dataset(
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Execute the virtual dataset join and return preview rows, capped at
    ``_PREVIEW_ROW_LIMIT``.
    """
    global _db_pool
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    try:
        columns, rows = await fetch_virtual_join(
            body.get("virtualSql", {}), user_id, _db_pool, language, limit=_PREVIEW_ROW_LIMIT
        )
        # Serialise values to match the previous preview shape (list of lists,
        # stringified for JSON safety — Decimal/date/etc).
        row_lists = [
            [str(r[c]) if r[c] is not None else None for c in columns]
            for r in rows
        ]
        return {"columns": columns, "rows": row_lists, "row_count": len(row_lists)}

    except Exception as e:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["virtual.preview_failed"], error=str(e)))


# ── Execute ─────────────────────────────────────────────────

@router.post("/execute")
async def execute_virtual_dataset(
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Execute the virtual dataset join. If materialized=True, materialise a persistent
    PostgreSQL table virtual_{datasetId}. Returns row count or materialized table name.
    """
    global _db_pool
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials, _db_pool, language)
    virtual_sql = body.get("virtualSql", {})
    dataset_id = body.get("datasetId")

    # The stored definition is the authority on whether this dataset is a
    # materialised one. Until 2026-11-06 `materialized` came from the request
    # body, so a caller could materialise a dataset defined live, or skip one
    # defined materialised — and the switch in the manual editor therefore chose
    # nothing at all. A body value is honoured only when there is no stored row to
    # ask (an unsaved definition being executed directly).
    materialized = body.get("materialized") if "materialized" in body else None
    if dataset_id:
        async with _db_pool.acquire() as conn:
            stored = await conn.fetchval(
                'SELECT "materialized" FROM "UserDataset" WHERE id = $1 AND "sourceType" = \'virtual\'',
                dataset_id,
            )
        if stored is not None:
            materialized = stored
    if materialized is None:
        materialized = False

    try:
        if materialized and dataset_id:
            table_name, _columns, row_count = await materialize_virtual_dataset(
                dataset_id, virtual_sql, user_id, _db_pool, language
            )
        else:
            row_count = await count_virtual_join(virtual_sql, user_id, _db_pool, language)
            table_name = None

        return {
            "row_count": row_count,
            "materialized": materialized,
            "table_name": table_name,
        }

    except Exception as e:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["virtual.execute_failed"], error=str(e)))


def build_postgres_join_sql(virtual_sql: dict, source_tables: dict) -> str:
    """Build a PostgreSQL SELECT … JOIN against already-materialised source tables.

    The sources are assumed to already exist as PostgreSQL tables (session TEMP
    tables or workbench_data tables) keyed by alias — no ``ATTACH`` / ``DETACH``.
    It preserves the ``{alias}_{column}`` column aliasing so the output schema is
    unchanged.

    Args:
        virtual_sql: ``{sources, joins, columns}`` JSON definition.
        source_tables: ``{alias: table_name}`` — the PostgreSQL table name for
            each source alias (bare or schema-qualified).

    No ``LIMIT``: a limit is a property of a *request*, not of a dataset, so the
    preview appends its own. It used to be a parameter here that every caller
    passed nothing for — dead surface that implied this builder owned the row
    cap, which it never did.

    Returns:
        A complete PostgreSQL SELECT statement.
    """
    def q(name: str) -> str:
        return quote_identifier(name, "postgresql")

    sources = virtual_sql.get("sources", [])
    joins = virtual_sql.get("joins", [])
    columns = virtual_sql.get("columns", [])

    if not sources:
        raise ValueError("virtual dataset has no sources")

    # SELECT list — {alias}."{col}" AS "{alias}_{col}"
    col_refs = []
    for col in columns:
        src_alias = col.get("source")
        col_name = col.get("column")
        if not src_alias or not col_name:
            continue
        col_refs.append(f'{q(src_alias)}.{q(col_name)} AS {q(f"{src_alias}_{col_name}")}')
    if not col_refs:
        col_refs = ["*"]

    first_alias = sources[0]["alias"]
    first_table = source_tables.get(first_alias)
    if first_table is None:
        raise ValueError(f"no materialised table for source alias '{first_alias}'")

    sql = (
        f"SELECT {', '.join(col_refs)} "
        f"FROM {quote_table(first_table, 'postgresql')} AS {q(first_alias)}"
    )

    # Attach each source exactly once, whichever side of a join is not yet in
    # the FROM list. (The old code always attached the ``right`` side, so a
    # parent listed first — ``sources[0]`` — that was also a join's right-hand
    # side got emitted twice and PostgreSQL rejected the query with "table
    # name specified more than once".)
    added = {first_alias}
    remaining = []
    for src in sources:
        alias = src.get("alias")
        if alias and alias not in added and alias not in remaining:
            remaining.append(alias)

    while remaining:
        progressed = False
        for join in joins:
            left = join.get("left")
            right = join.get("right")
            left_col = join.get("leftCol")
            right_col = join.get("rightCol")
            join_type = (join.get("type") or "INNER").strip().upper()
            on_clause = f"ON {q(left)}.{q(left_col)} = {q(right)}.{q(right_col)}"

            if left in added and right in remaining:
                new_alias, table = right, source_tables.get(right)
                emitted_type = join_type
            elif right in added and left in remaining:
                new_alias, table = left, source_tables.get(left)
                # LEFT/RIGHT are not symmetric — flipping the attached side
                # swaps which table is row-preserving, so invert the type.
                emitted_type = {"LEFT": "RIGHT", "RIGHT": "LEFT"}.get(join_type, join_type)
            else:
                continue

            if table is None:
                raise ValueError(f"no materialised table for source alias '{new_alias}'")
            sql += (
                f"\n  {emitted_type} JOIN {quote_table(table, 'postgresql')} AS {q(new_alias)} "
                f"{on_clause}"
            )
            added.add(new_alias)
            remaining.remove(new_alias)
            progressed = True

        if not progressed:
            raise ValueError(
                f"could not join sources {sorted(remaining)}: no join connects them to the rest"
            )

    return sql


async def database_connect_timeout(db_pool, language: str = "en") -> int:
    """The deadline for *reaching* an external database, in seconds.

    Read from ``GlobalSettings.defaultConnectTimeoutSeconds`` — the workbench-wide
    value, because ``UserDatabaseConnection`` carries no timeout columns of its own.
    That is also why ``resolve_connection_timeouts`` is **not** the helper here: it
    joins ``UserAIConnection`` on the same id, so pointing it at a database
    connection would read whichever AI connection happens to share the number.

    An unreadable settings row falls back to the compiled default rather than
    failing: a missing deadline is a reason to bound the connect conservatively,
    not a reason to refuse to connect.
    """
    try:
        async with db_pool.acquire() as conn:
            value = await conn.fetchval(
                'SELECT "defaultConnectTimeoutSeconds" FROM "GlobalSettings" WHERE id = 1'
            )
        if isinstance(value, int) and value > 0:
            return value
    except Exception:
        pass
    from .data_access import DEFAULT_CONNECT_TIMEOUT_SECONDS
    return DEFAULT_CONNECT_TIMEOUT_SECONDS


async def refuse_if_known_unreachable(db_pool, user_id: str, sources, language: str = "en") -> None:
    """Raise rather than connect when a fresh probe already recorded a failure.

    The probe exists so a caller can know *before it acts* whether a connection can
    be reached. The data paths ignored it: they connected, and paid the full
    deadline to learn what the cache already held. Measured 2026-11-06 — a schema
    read blocked for its whole 60-second default while the same connection's
    cached state said the host did not answer.

    Only *fresh* failures refuse (see ``fresh_failures``); a stale one is an
    opinion about a host that may have come back.
    """
    connection_ids = [
        src.get("connectionId") for src in sources or [] if isinstance(src, dict)
    ]
    refused = await fresh_failures(db_pool, user_id, connection_ids)
    if not refused:
        return
    connection_id = sorted(refused)[0]
    _state, detail = refused[connection_id]
    raise ValueError(
        await t(db_pool, language, SCHEMA["datasets.schema.connection_unreachable"],
                connection_id=connection_id, error=detail)
    )


async def materialize_virtual_source(conn, source: dict, user_id: str, db_pool, language: str = "en",
                                     connect_timeout: int | None = None):
    """Pull a virtualSql source's rows into a PostgreSQL session TEMP table.

    Handles two source kinds:

    - external connection (``storageType`` in postgresql/mysql/mssql/access with
      a ``connectionId``) — queried via its native driver;
    - dataset reference (identified by ``datasetId``) — resolved and pulled via
      ``execute_compiled_sql_rows``.

    Args:
        conn: the held data-pool connection (session TEMP tables live here).
        source: a virtualSql source dict.
        user_id, db_pool, language: for external-query routing.

    Returns:
        ``(temp_table, columns)``.
    """

    storage_type = source.get("storageType")

    if source.get("datasetId"):
        # Reference to another dataset — resolve it and pull its rows.
        dataset_id = source.get("datasetId")
        if not dataset_id:
            raise ValueError("virtual source references a dataset but has no datasetId")
        # The referenced dataset must be one the caller can *see* — their own, or one
        # shared to their group (Gap C). Its rows are pulled below through
        # execute_compiled_sql_rows, which checks the same thing, but this read is what
        # decides whether the source resolves at all, so it must not answer for a
        # dataset the caller cannot see.
        async with db_pool.acquire() as mc:
            row = await mc.fetchrow(
                """
                SELECT "storageType", "tableName"
                FROM "UserDataset"
                WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                    SELECT "userGroup" FROM "User" WHERE id = $2
                )))
                """,
                dataset_id, user_id,
            )
        if row is None:
            raise ValueError(f"referenced dataset {dataset_id} not found")
        ref_storage = row["storageType"] or "postgresql"
        ref_table = row["tableName"]
        if not ref_table:
            raise ValueError(f"referenced dataset {dataset_id} has no table")
        sql = f"SELECT * FROM {quote_table(ref_table, ref_storage)}"
        columns, rows, declared_types = await execute_compiled_sql_rows(
            sql, db_pool, user_id, dataset_id, language
        )
    else:
        # External connection source.
        connection_id = source.get("connectionId")
        table_name = source.get("tableName") or source.get("_tableName")
        if not connection_id:
            raise ValueError(f"virtual source '{source.get('alias')}' has no connectionId")
        if not table_name:
            raise ValueError(f"virtual source '{source.get('alias')}' has no tableName")
        sql = f"SELECT * FROM {quote_table(table_name, storage_type)}"
        conn_details = await get_connection_row(connection_id, user_id, language)
        if conn_details is None:
            raise ValueError(await t(db_pool, language, error_define_connection_not_found_2))
        conn_details["password"] = decrypt_field(conn_details["password"])
        columns, rows, declared_types = await execute_connection_sql_rows(
            sql, conn_details, db_pool, language, connect_timeout=connect_timeout
        )

    temp_table = await materialize_temp_table_from_rows(conn, columns, rows, declared_types)
    return temp_table, columns


async def _materialize_sources_and_build_join(conn, virtual_sql, user_id, db_pool, language="en"):
    """Materialise all sources into session TEMP tables and build the join SQL.

    Shared by the preview/count/materialise paths. The source TEMP tables live
    on ``conn`` and auto-drop when it closes.
    """
    sources = virtual_sql.get("sources", [])
    if not sources:
        raise ValueError("virtual dataset has no sources")

    # Refuse before connecting when the probe already recorded a fresh failure,
    # and resolve the deadline once rather than per source. Both are here rather
    # than in `materialize_virtual_source` because both are facts about the whole
    # set: one query each instead of one per source, and the first failure stops
    # the run instead of surfacing after the others have been attempted.
    await refuse_if_known_unreachable(db_pool, user_id, sources, language)
    connect_timeout = await database_connect_timeout(db_pool, language)

    source_tables = {}
    for src in sources:
        alias = src.get("alias")
        if not alias:
            raise ValueError("virtual source has no alias")
        source_tables[alias], _ = await materialize_virtual_source(
            conn, src, user_id, db_pool, language, connect_timeout=connect_timeout
        )

    join_sql = build_postgres_join_sql(virtual_sql, source_tables)
    return source_tables, join_sql


async def fetch_virtual_join(
    virtual_sql: dict,
    user_id: str,
    db_pool,
    language: str = "en",
    limit: int = None,
):
    """Run the virtual join (sources in TEMP tables) and return (columns, rows).

    No persistence — the join runs against session TEMP tables and the rows are
    returned directly. ``limit`` (if given) is appended as ``LIMIT n``.
    """

    data_pool = get_data_pool()
    if data_pool is None:
        raise RuntimeError("data database pool is not initialised")

    conn = await data_pool.acquire()
    try:
        _, join_sql = await _materialize_sources_and_build_join(
            conn, virtual_sql, user_id, db_pool, language
        )
        sql = f"{join_sql}\nLIMIT {int(limit)}" if limit else join_sql
        result = await conn.fetch(sql)
        if result:
            columns = [str(k) for k in result[0].keys()]
        else:
            stmt = await conn.prepare(sql)
            columns = [str(a.name) for a in stmt.get_attributes()]
        rows = [dict(r) for r in result]
    finally:
        # Close so the session TEMP tables (sources) are dropped.
        await conn.close()
    return columns, rows


async def count_virtual_join(virtual_sql: dict, user_id: str, db_pool, language: str = "en") -> int:
    """Return the row count of the virtual join (no persistence)."""

    data_pool = get_data_pool()
    if data_pool is None:
        raise RuntimeError("data database pool is not initialised")

    conn = await data_pool.acquire()
    try:
        _, join_sql = await _materialize_sources_and_build_join(
            conn, virtual_sql, user_id, db_pool, language
        )
        return int(await conn.fetchval(f"SELECT COUNT(*) FROM ({join_sql}) AS _vt"))
    finally:
        # Close so the session TEMP tables (sources) are dropped.
        await conn.close()


async def materialize_virtual_dataset(
    dataset_id: str,
    virtual_sql: dict,
    user_id: str,
    db_pool,
    language: str = "en",
):
    """Materialise a virtual dataset into a persistent PostgreSQL table.

    Pulls each source into a session TEMP table (Item 24c), builds the join
    (Item 24b), and creates ``u_<user_id>.virtual_{dataset_id}`` in
    ``workbench_data`` — the owning account's schema, like every other object
    the application creates there. The whole write is transactional; the source
    TEMP tables auto-drop when the connection closes.

    Args:
        dataset_id: the virtual dataset id (the table becomes
            ``u_<user_id>.virtual_{id}``).
        virtual_sql: ``{sources, joins, columns}`` JSON definition.
        user_id, db_pool, language: for source pulling.

    Returns:
        ``(table_name, columns, row_count)``.
    """

    data_pool = get_data_pool()
    if data_pool is None:
        raise RuntimeError("data database pool is not initialised")

    table_name = f"{user_schema_name(user_id)}.virtual_{dataset_id}"
    qt = quote_table(table_name, "postgresql")

    conn = await data_pool.acquire()
    try:
        async with conn.transaction():
            # The account's schema is created on first write, inside the same
            # transaction, so the (re)create below always has a home and a
            # failed join leaves nothing behind.
            await ensure_user_schema(conn, user_id)
            _, join_sql = await _materialize_sources_and_build_join(
                conn, virtual_sql, user_id, db_pool, language
            )

            # (Re)create the persistent table atomically.
            await conn.execute(f"DROP TABLE IF EXISTS {qt}")
            await conn.execute(f"CREATE TABLE {qt} AS {join_sql}")

        # Read columns + row count (post-commit, read-only).
        stmt = await conn.prepare(f"SELECT * FROM {qt}")
        columns = [str(a.name) for a in stmt.get_attributes()]
        row_count = await conn.fetchval(f"SELECT COUNT(*) FROM {qt}")
    finally:
        # Close so the session TEMP tables (sources) are dropped; the persistent
        # virtual_{id} table survives (it is a regular table).
        await conn.close()

    return table_name, columns, int(row_count)
