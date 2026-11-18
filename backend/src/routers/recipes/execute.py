"""
Recipe execution orchestrator.
Handles the execution pipeline for recipes.
"""

import math
import uuid
from datetime import datetime
from decimal import Decimal
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncpg
import jwt
import os

from .models import ExecuteRecipeRequest
from .helpers import get_stage_executor, validate_stages
from src.routers.datasets.data_access import execute_compiled_sql_rows
from src.routers.datasets.sql_dialect import split_operations, compile_sql, quote_table, quote_identifier
from src.routers.datasets.virtual import materialize_virtual_dataset
from .relation import Relation, relation_source
from src.postgres_data_manager import (
    get_data_pool,
    get_distinct_values,
    get_relation_numeric_columns,
    materialize_temp_table,
    materialize_temp_table_from_rows,
)
from .stages.data_preparation import DataPreparationExecutor
from src.utils.translation import t
from src.routers.datasets.crud import get_current_language, get_user_id_from_token
from .translations import (
    error_database_pool_not_initialized,
    error_dataset_load_failed,
    error_execution_cannot_cancel,
    execution_not_found,
    recipes_execution_completed,
    recipes_execution_error,
    recipes_execution_failed,
    recipes_execution_preparation_error,
    recipes_execution_preparation_failed,
    recipes_execution_unknown_stage,
    recipes_not_found,
)
from src.utils.timestamps import iso_utc

router = APIRouter()
security = HTTPBearer()

_db_pool = None
SECRET_KEY = os.getenv("NEXTAUTH_SECRET")


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


def _sanitize_for_json(obj):
    """Recursively replace NaN/Infinity float values with None for safe JSON serialization."""
    if isinstance(obj, dict):
        return {k: _sanitize_for_json(v) for k, v in obj.items()}
    if isinstance(obj, list):
        return [_sanitize_for_json(v) for v in obj]
    if isinstance(obj, float) and (math.isnan(obj) or math.isinf(obj)):
        return None
    if isinstance(obj, datetime):
        return iso_utc(obj)
    if hasattr(obj, 'isoformat'):
        return obj.isoformat()
    if isinstance(obj, Decimal):
        return float(obj)
    try:
        return float(obj) if isinstance(obj, (int, float)) or hasattr(obj, 'item') else obj
    except (TypeError, ValueError):
        pass
    return obj


async def _relation_col_info(relation, data_conn):
    """Build validate_stages column info from a relation via SQL type detection.

    Uses ``pg_typeof`` (through ``get_relation_numeric_columns``) so stage
    validation no longer depends on a pandas DataFrame. ``data_conn`` is the
    held data-pool connection when the relation is a session TEMP table.
    """
    source_sql = relation_source(relation)
    release = None
    if data_conn is not None:
        conn = data_conn
    else:
        pool = get_data_pool()
        conn = await pool.acquire()
        release = pool
    try:
        numeric = await get_relation_numeric_columns(conn, source_sql, relation.columns)
    finally:
        if release is not None:
            await release.release(conn)
    return [
        {
            "name": col,
            "dtype": "numeric" if col in numeric else "categorical",
            "is_numeric": col in numeric,
            "is_categorical": col not in numeric,
        }
        for col in relation.columns
    ]


@router.post("/execute")
async def execute_recipe(
    request: ExecuteRecipeRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """
    Execute a recipe with multiple preparation rules.
    
    Steps:
    1. Load recipe with preparation rules in order
    2. Load raw dataset from storage
    3. Apply rules sequentially
    4. Execute analysis stages
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized)
        )

    user_id = await get_user_id_from_token(credentials)

    # Get the user's group (still needed by stage executors)
    async with _db_pool.acquire() as conn:
        user_row = await conn.fetchrow(
            'SELECT "userGroup" FROM "User" WHERE id = $1',
            user_id
        )
        user_group = user_row["userGroup"] if user_row else "00"

    # Get the recipe (own or shared from group)
    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT r.id, r.name, r."datasetId", r.stages, r."userId"
            FROM "Recipe" r
            WHERE r.id = $1 AND (r."userId" = $2 OR ("isShared" = true AND r."recipeGroup" IN (
                SELECT "userGroup" FROM "User" WHERE id = $2
            )))
            """,
            request.recipe_id, user_id
        )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_not_found, id=request.recipe_id)
        )

    recipe = dict(row)
    dataset_id = recipe.get("datasetId")
    stages = recipe["stages"]

    # Get preparation rules in order
    async with _db_pool.acquire() as conn:
        rule_rows = await conn.fetch(
            """
            SELECT rpr."ruleId", rpr."order", dr.name, dr.operations
            FROM "RecipePreparationRule" rpr
            JOIN "DataPreparationRule" dr ON rpr."ruleId" = dr.id
            WHERE rpr."recipeId" = $1
            ORDER BY rpr."order" ASC
            """,
            request.recipe_id
        )
        preparation_rules = [
            {
                "id": row["ruleId"],
                "name": row["name"],
                "operations": row["operations"],
                "order": row["order"]
            }
            for row in rule_rows
        ]

    # Create execution record
    execution_id = str(uuid.uuid4())
    async with _db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO "RecipeExecution" (id, "recipeId", "userId", status, progress, "startedAt", "createdAt", "updatedAt")
            VALUES ($1, $2, $3, 'running', 0, NOW(), NOW(), NOW())
            """,
            execution_id, request.recipe_id, user_id
        )

    has_prep_stage = len(preparation_rules) > 0
    total_steps = (1 if has_prep_stage else 0) + len(stages) + 1  # +1 for data load

    # Execute stages
    results = {}
    errors = []
    current_step = 1

    data_conn = None
    try:
        relation = None

        # Fetch dataset metadata once; source type discriminates native vs external.
        # The dataset must be one the caller can *see* — their own, or one shared to
        # their group. The recipe that named it was validated when it was written, but
        # visibility can change afterwards and the native path below reads the
        # dataset's own table, so an invisible dataset reads as missing (Gap C).
        async with _db_pool.acquire() as conn:
            ds_row = await conn.fetchrow(
                """
                SELECT "sourceType", "storageType", "tableName", "dataSnapshot", "virtualSql"
                FROM "UserDataset"
                WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                    SELECT "userGroup" FROM "User" WHERE id = $2
                )))
                """,
                dataset_id, user_id
            )
        source_type = ds_row["sourceType"] if ds_row else ""
        storage_type = ds_row["storageType"] if ds_row else "postgresql"
        table_name = ds_row["tableName"] if ds_row else "data"

        # Native PostgreSQL = data already in workbench_data (uploaded / notebook).
        is_native_pg = source_type in ("upload", "notebook") and storage_type == "postgresql"
        # Federated = data in an external database connection (MySQL/MSSQL/Access/PostgreSQL).
        is_external = source_type in ("table", "view", "postgresql", "mysql", "mssql", "access")
        # Virtual = a federated join view, materialised into PostgreSQL on demand.
        is_virtual = source_type == "virtual"
        # Data that is (or is now) in workbench_data — usable with PG SQL/temp tables.
        is_local_pg = is_native_pg or is_virtual

        all_columns = []
        if ds_row and ds_row["dataSnapshot"]:
            snapshot = ds_row["dataSnapshot"]
            all_columns = snapshot.get("columns", []) if isinstance(snapshot, dict) else []

        # Virtual datasets are materialised into a persistent PostgreSQL table
        # (virtual_{id}) and then treated as local-PG data for the rest of the
        # stream (prep pushes down against that table).
        if is_virtual and ds_row:
            virtual_sql = ds_row["virtualSql"]
            if isinstance(virtual_sql, str):
                import json as _json
                virtual_sql = _json.loads(virtual_sql)
            if not virtual_sql:
                raise ValueError("virtual dataset has no definition")
            v_table, v_columns, _ = await materialize_virtual_dataset(
                dataset_id, virtual_sql, user_id, _db_pool, language
            )
            # The materialiser returns the name it created, schema-qualified since
            # Step B1. Rebuilding `virtual_{dataset_id}` here would point the rest
            # of the stream at a table that no longer exists under that name.
            table_name = v_table
            storage_type = "postgresql"
            all_columns = v_columns

        # Phase 5.5 — flatten preparation operations.
        all_operations = []
        for rule in preparation_rules:
            ops = rule.get("operations", [])
            if isinstance(ops, list):
                all_operations.extend(ops)

        if all_operations:
            # Split operations into SQL-pushdown and fallback phases.
            sql_ops, python_ops = split_operations(all_operations, storage_type)

            if is_local_pg:
                # Local PG (native or materialised virtual): every op is
                # SQL-capable, so compile the whole list to PG SQL against the
                # local table and materialise a session TEMP table (Item 20).
                for op in sql_ops:
                    if (
                        op.get("type") in ("encode", "encode_category")
                        and op.get("encoding") == "one_hot"
                    ):
                        col = op.get("column")
                        if col:
                            op["levels"] = await get_distinct_values(table_name, col)

                compiled_sql = compile_sql(sql_ops, "postgresql", table_name, all_columns)
                data_pool = get_data_pool()
                data_conn = await data_pool.acquire()
                temp_table = await materialize_temp_table(data_conn, compiled_sql)
                stmt = await data_conn.prepare(f'SELECT * FROM "{temp_table}"')
                relation = Relation(
                    storage_type="postgresql",
                    columns=[str(a.name) for a in stmt.get_attributes()],
                    table_name=temp_table,
                )
            elif is_external:
                # Federated: push the SQL-capable ops to the external engine,
                # materialise the rows into a session TEMP table, then run the
                # remaining fallback ops as PostgreSQL SQL against it.
                compiled_sql = compile_sql(sql_ops, storage_type, table_name, all_columns)
                columns, rows, declared_types = await execute_compiled_sql_rows(
                    compiled_sql, _db_pool, user_id, dataset_id, language
                )
                data_pool = get_data_pool()
                data_conn = await data_pool.acquire()
                temp_table = await materialize_temp_table_from_rows(
                    data_conn, columns, rows, declared_types
                )

                # Remaining ops (not pushable to the external engine) run as
                # PostgreSQL SQL against the materialized TEMP table.
                if python_ops:
                    # Inject one-hot levels from the TEMP table (they live on the
                    # held data_conn, not the workbench_data pool).
                    for op in python_ops:
                        if (
                            op.get("type") in ("encode", "encode_category")
                            and op.get("encoding") == "one_hot"
                        ):
                            col = op.get("column")
                            if col:
                                qc = quote_identifier(col, "postgresql")
                                qt = quote_table(temp_table, "postgresql")
                                lvls = await data_conn.fetch(
                                    f"SELECT DISTINCT {qc} FROM {qt} WHERE {qc} IS NOT NULL ORDER BY {qc}"
                                )
                                op["levels"] = [r[0] for r in lvls]
                    pg_sql = compile_sql(python_ops, "postgresql", temp_table, columns)
                    temp_table = await materialize_temp_table(data_conn, pg_sql)
                    stmt = await data_conn.prepare(f'SELECT * FROM "{temp_table}"')
                    columns = [str(a.name) for a in stmt.get_attributes()]

                relation = Relation(
                    storage_type="postgresql",
                    columns=columns,
                    table_name=temp_table,
                )
            else:
                raise ValueError(
                    await t(_db_pool, language, error_dataset_load_failed,
                        error=f"unsupported storage type '{storage_type}'"
                    )
                )
        else:
            # No preparation rules.
            if is_external:
                # Federated, no prep: SELECT * from the external table, then
                # materialize into a PostgreSQL session TEMP table.
                ext_sql = f"SELECT * FROM {quote_table(table_name, storage_type)}"
                columns, rows, declared_types = await execute_compiled_sql_rows(
                    ext_sql, _db_pool, user_id, dataset_id, language
                )
                data_pool = get_data_pool()
                data_conn = await data_pool.acquire()
                temp_table = await materialize_temp_table_from_rows(
                    data_conn, columns, rows, declared_types
                )
                relation = Relation(
                    storage_type="postgresql",
                    columns=columns,
                    table_name=temp_table,
                )
            elif is_virtual:
                # Virtual: already materialised into virtual_{id} at the top —
                # a native-PG base-table relation.
                relation = Relation(
                    storage_type="postgresql",
                    columns=all_columns,
                    table_name=table_name,
                )
            elif is_native_pg:
                # Native PG: read the actual table columns (no DataFrame load).
                from src.postgres_data_manager import get_table_schema
                schema = await get_table_schema(table_name)
                relation = Relation(
                    storage_type="postgresql",
                    columns=[c["name"] for c in schema],
                    table_name=table_name,
                )
            else:
                raise ValueError(
                    await t(_db_pool, language, error_dataset_load_failed,
                        error=f"unsupported storage type '{storage_type}'"
                    )
                )

        # Update progress after data load
        current_step += 1
        stage_index = 0
        progress = int((current_step / total_steps) * 100) if total_steps > 0 else 0

        # Execute data_preparation as a first-class stage
        if has_prep_stage:
            rule_ids = [r["id"] for r in preparation_rules]
            stage_index += 1
            current_step += 1
            progress = int((current_step / total_steps) * 100) if total_steps > 0 else 0

            try:
                executor = DataPreparationExecutor({"rule_ids": rule_ids})
                prep_result = await executor.execute(
                    user_id=user_id,
                    user_group=user_group,
                    dataset_id=dataset_id,
                    db_pool=_db_pool,
                    language=language,
                    relation=relation,
                    data_conn=data_conn
                )
                if isinstance(prep_result, dict):
                    prep_result["stage_type"] = "data_preparation"
                results[f"stage_{stage_index}"] = prep_result

                if prep_result.get("status") == "error":
                    errors.append(prep_result.get("error", await t(_db_pool, language, recipes_execution_preparation_failed)))
            except Exception as e:
                error_msg = await t(_db_pool, language, recipes_execution_preparation_error, error=str(e))
                errors.append(error_msg)
                results[f"stage_{stage_index}"] = {"status": "error", "error": error_msg, "stage_type": "data_preparation"}

        # Validate stages against actual dataset columns before execution.
        # The backend enforces the constraint matrix independently —
        # external API clients may bypass frontend guardrails.
        if not errors:
            try:
                col_info = await _relation_col_info(relation, data_conn)
                await validate_stages(stages, language, _db_pool, col_info)
            except ValueError as e:
                errors.append(str(e))

        # If no errors, execute stages
        if not errors:
            # Update progress for stage execution

            # Execute each stage
            for stage in stages:
                stage_index += 1
                stage_type = stage["type"]
                stage_config = stage["config"]

                current_step += 1
                progress = int((current_step / total_steps) * 100) if total_steps > 0 else 0

                # Get the appropriate executor
                try:
                    executor = get_stage_executor(stage_type, stage_config)
                except ValueError as e:
                    raise ValueError(
                        await t(_db_pool, language, recipes_execution_unknown_stage,
                            stage_type=stage_type
                        )
                    )

                # Execute the stage
                try:
                    result = await executor.execute(
                        user_id=user_id,
                        user_group=user_group,
                        dataset_id=dataset_id,
                        db_pool=_db_pool,
                        language=language,
                        relation=relation,
                        data_conn=data_conn
                    )
                except Exception as e:
                    result = {"status": "error", "error": await t(_db_pool, language, recipes_execution_error, error=str(e))}
                if isinstance(result, dict):
                    result["stage_type"] = stage_type
                results[f"stage_{stage_index}"] = result

                if "error" in result:
                    errors.append(result["error"])
                    break

    except Exception as e:
        errors.append(str(e))
    finally:
        if data_conn is not None:
            # Close (not release) so the session ends and its session TEMP
            # tables (_recipe_tmp_*) are dropped — one recipe = one session.
            await data_conn.close()

    status = "completed" if not errors else "failed"
    progress = 100 if not errors else int((current_step / total_steps) * 100) if total_steps > 0 else 0

    async with _db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE "RecipeExecution"
            SET status = $1, progress = $2, result = $3, error = $4, "completedAt" = NOW(), "updatedAt" = NOW()
            WHERE id = $5
            """,
            status,
            progress,
            _sanitize_for_json(results) if results else None,
            "\n".join(errors) if errors else None,
            execution_id
        )

    status_message = await t(_db_pool, language, recipes_execution_completed) if status == "completed" else await t(_db_pool, language, recipes_execution_failed)

    return _sanitize_for_json({
        "success": True,
        "execution_id": execution_id,
        "recipe_name": recipe.get("name"),
        "status": status,
        "progress": progress,
        "results": results,
        "errors": errors if errors else None,
        "preparation_rules_applied": len(preparation_rules),
        "message": status_message
    })


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution(
    execution_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Cancel a running or pending recipe execution."""
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, error_database_pool_not_initialized))

    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM "RecipeExecution" WHERE id = $1 AND "userId" = $2',
            execution_id, user_id
        )
        if not row:
            raise HTTPException(status_code=404, detail=await t(_db_pool, language, execution_not_found))

        if row["status"] not in ("running", "pending"):
            raise HTTPException(
                status_code=400,
                detail=await t(_db_pool, language, error_execution_cannot_cancel, status=row["status"])
            )

        await conn.execute(
            """UPDATE "RecipeExecution" SET status='cancelled', "completedAt"=NOW(), "updatedAt"=NOW() WHERE id=$1""",
            execution_id
        )

    return {"success": True, "execution_id": execution_id, "status": "cancelled"}
