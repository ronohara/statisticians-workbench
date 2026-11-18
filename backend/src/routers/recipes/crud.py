"""
CRUD operations for recipes.
Handles create, read, update, and delete operations.
"""

import uuid
from typing import List, Optional, Dict, Any
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
import asyncpg
import jwt
import os

from .models import (
    CreateRecipeRequest,
    UpdateRecipeRequest,
    RecipeResponse,
    RecipeListResponse,
    RecipeStage
)
from .helpers import validate_stages, validate_recipe_stages
from .constraints import ColumnInfo, to_column_info
from src.utils.translation import t
from src.routers.datasets.crud import get_current_language, get_user_id_from_token
from .translations import (
    error_database_pool_not_initialized,
    error_dataset_not_found,
    error_preparation_rule_not_found,
    recipes_create_success,
    recipes_delete_error,
    recipes_delete_success,
    recipes_no_updates,
    recipes_not_found,
    recipes_not_owned,
    recipes_share_disabled,
    recipes_share_enabled,
    recipes_update_success,
)

router = APIRouter()
security = HTTPBearer()


def _stage_column_info(stages: List[Dict[str, Any]]) -> Optional[List[ColumnInfo]]:
    """The column schema stored in the data-selection stage, or None.

    The manual editor persists the dataset's columns in the data-selection
    stage's ``config.columns`` (the schema as the recipe was configured).

    Returns ``ColumnInfo`` objects, through the one conversion in
    ``constraints.to_column_info``: this function used to normalise the
    spellings itself, which made it a second place that knew the camelCase keys
    — and one that read only ``isNumeric`` while the schema route emits
    ``is_numeric``.
    """
    for stage in stages or []:
        if isinstance(stage, dict) and stage.get("type") == "data_selection":
            columns = ((stage.get("config") or {}).get("columns")) or []
            return to_column_info([c for c in columns if isinstance(c, dict)]) or None
    return None


def _recipe_ready(stages: List[Dict[str, Any]]) -> bool:
    """Whether the executor would accept this recipe as it stands.

    The verdict comes from ``validate_recipe_stages`` — the same pure validation
    the create/update gate and the executor's own pre-flight call — so the list
    and the runner cannot disagree about one recipe. Warnings count as blocking
    because ``validate_stages`` blocks on them at execution time.
    """
    column_info = _stage_column_info(stages)
    issues = validate_recipe_stages(stages or [], column_info)
    return not (issues.get("errors") or issues.get("warnings"))

_db_pool = None
SECRET_KEY = os.getenv("NEXTAUTH_SECRET")


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


async def can_edit_recipe(db_pool, recipe_id: str, user_id: str) -> bool:
    """May this caller change this recipe?

    Its owner — or an administrator, when the recipe is shared to the group that
    administrator belongs to. This is the datasets' rule (datasets/crud
    ``can_edit_dataset``) stated once for recipes: the statement is deliberately the
    same one with ``"recipeGroup"`` in place of ``"datasetGroup"``, so the two
    resources answer one way and neither write site composes its own predicate.
    Sharing is not part of editing — a recipe's share endpoint stays the owner's
    alone (Decision 1) — so this decides content only.

    The admin flag and the caller's group are read in the same statement rather than
    through admin helpers: the two backends must answer this question identically,
    and a second way of asking it would be a parity break waiting to drift.

    False covers both "no such row" and "not yours to change", so a caller who may
    not touch a recipe cannot learn that it exists.
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT ("userId" = $2) AS is_owner,
                   "isShared",
                   "recipeGroup",
                   EXISTS (SELECT 1 FROM "User" WHERE id = $2 AND "isAdmin" = true) AS caller_is_admin,
                   COALESCE((SELECT "userGroup" FROM "User" WHERE id = $2), '00') AS caller_group
            FROM "Recipe"
            WHERE id = $1
            """,
            recipe_id, user_id,
        )

    if row is None:
        return False
    if row["is_owner"]:
        return True

    return bool(
        row["isShared"]
        and row["caller_is_admin"]
        and row["recipeGroup"] == row["caller_group"]
    )


async def create_recipe_record(
    db_pool,
    user_id: str,
    name: str,
    description,
    dataset_id,
    stages: list,
    preparation_rule_ids: list,
    is_shared: bool = False,
    recipe_group: str = "00",
) -> str:
    """Insert a Recipe row (plus its preparation-rule junction rows) and return
    the new recipe id. Shared by the create endpoint and the AI save tool."""
    recipe_id = str(uuid.uuid4())
    effective_group = recipe_group if is_shared else "00"

    async with db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                """
                INSERT INTO "Recipe" (
                    id, "userId", name, description, "datasetId",
                    stages, "recipeGroup", "isShared", "createdAt", "updatedAt"
                )
                VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                """,
                recipe_id, user_id, name, description, dataset_id,
                stages, effective_group, is_shared,
            )
            for idx, rule_id in enumerate(preparation_rule_ids):
                await conn.execute(
                    """
                    INSERT INTO "RecipePreparationRule" (id, "recipeId", "ruleId", "order", "createdAt", "updatedAt")
                    VALUES ($1, $2, $3, $4, NOW(), NOW())
                    """,
                    str(uuid.uuid4()), recipe_id, rule_id, idx,
                )
    return recipe_id


async def validate_preparation_rules(
    db_pool,
    dataset_id: str,
    preparation_rule_ids: list,
    language: str,
) -> None:
    """Validate that every preparation rule belongs to the given dataset.
    Raises HTTPException(404, error_preparation_rule_not_found) on the first
    mismatch. Shared by the create/update endpoints and the AI save paths so
    the check lives in one place."""
    if not preparation_rule_ids or not dataset_id:
        return
    async with db_pool.acquire() as conn:
        for rule_id in preparation_rule_ids:
            rule_row = await conn.fetchrow(
                """
                SELECT id FROM "DataPreparationRule"
                WHERE id = $1 AND "datasetId" = $2
                """,
                rule_id, dataset_id
            )
            if rule_row is None:
                raise HTTPException(
                    status_code=404,
                    detail=await t(
                        db_pool, language, error_preparation_rule_not_found, id=rule_id
                    )
                )


@router.post("/", response_model=Dict[str, Any])
async def create_recipe(
    request: CreateRecipeRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Create a new recipe."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized)
        )

    user_id = await get_user_id_from_token(credentials)

    # Validate stages — against the stored column schema when the data_selection
    # stage carries one, so the backend applies the same column checks the manual
    # UI does client-side (external clients bypass the frontend guardrails).
    stages = [stage.dict() for stage in request.stages]
    try:
        await validate_stages(
            stages, language, _db_pool,
            column_info=_stage_column_info(stages),
            block_on_warnings=False,
        )
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=str(e)
        )

    # Validate dataset exists and user has access (only if datasetId provided)
    if request.datasetId:
        async with _db_pool.acquire() as conn:
            dataset_row = await conn.fetchrow(
                """
                SELECT id FROM "UserDataset"
                WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (SELECT "userGroup" FROM "User" WHERE id = $2)))
                """,
                request.datasetId, user_id
            )

            if dataset_row is None:
                raise HTTPException(
                    status_code=404,
                    detail=await t(_db_pool, language, error_dataset_not_found, id=request.datasetId)
                )

    # Validate all preparation rules belong to the same dataset
    await validate_preparation_rules(
        _db_pool, request.datasetId, request.preparationRuleIds, language
    )

    recipe_id = await create_recipe_record(
        _db_pool,
        user_id,
        request.name,
        request.description,
        request.datasetId,
        stages,
        request.preparationRuleIds,
        request.shared,
        request.recipeGroup,
    )

    recipe_group = request.recipeGroup if request.shared else "00"

    return {
        "success": True,
        "recipe_id": recipe_id,
        "name": request.name,
        "description": request.description,
        "datasetId": request.datasetId,
        "recipeGroup": recipe_group,
        "preparationRuleIds": request.preparationRuleIds,
        "message": await t(_db_pool, language, recipes_create_success, name=request.name)
    }


@router.get("/", response_model=RecipeListResponse)
async def list_recipes(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """List all recipes for the current user, including shared from group."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized)
        )

    user_id = await get_user_id_from_token(credentials)

    # Build query: own recipes + shared recipes from group
    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT r.id, r.name, r.description, r."datasetId", 
                   r.stages,
                   r."recipeGroup", r."userId", r."isShared", 
                   r."createdAt", r."updatedAt",
                   u.name as user_name, d.name as dataset_name
            FROM "Recipe" r
            LEFT JOIN "User" u ON r."userId" = u.id
            LEFT JOIN "UserDataset" d ON r."datasetId" = d.id
            WHERE r."userId" = $1 OR (r."isShared" = true AND r."recipeGroup" IN (SELECT "userGroup" FROM "User" WHERE id = $1))
            ORDER BY r."createdAt" DESC
            """,
            user_id
        )

    result = []
    for row in rows:
        recipe = dict(row)
        recipe["isOwn"] = recipe["userId"] == user_id
        if recipe.get("user_name"):
            recipe["user"] = {"name": recipe["user_name"]}
        else:
            recipe["user"] = None
        if not recipe.get("stages"):
            recipe["stages"] = []

        # Whether the executor would accept it as it stands — see _recipe_ready.
        recipe["ready"] = _recipe_ready(recipe["stages"])
        
        # Fetch preparation rules for this recipe
        async with _db_pool.acquire() as conn:
            rule_rows = await conn.fetch(
                """
                SELECT rpr."ruleId", rpr."order", dr.name, dr.description
                FROM "RecipePreparationRule" rpr
                JOIN "DataPreparationRule" dr ON rpr."ruleId" = dr.id
                WHERE rpr."recipeId" = $1
                ORDER BY rpr."order" ASC
                """,
                recipe["id"]
            )
            recipe["preparation_rules"] = [
                {
                    "id": row["ruleId"],
                    "name": row["name"],
                    "description": row["description"],
                    "order": row["order"]
                }
                for row in rule_rows
            ]
        
        result.append(recipe)

    return RecipeListResponse(recipes=result)


@router.get("/{recipe_id}", response_model=RecipeResponse)
async def get_recipe(
    recipe_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Get a recipe by ID."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized)
        )

    user_id = await get_user_id_from_token(credentials)

    # Fetch recipe (own or shared from group)
    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT r.id, r.name, r.description, r."datasetId", 
                   r.stages, r."recipeGroup", r."userId", r."isShared",
                   r."createdAt", r."updatedAt",
                   u.name as user_name, d.name as dataset_name
            FROM "Recipe" r
            LEFT JOIN "User" u ON r."userId" = u.id
            LEFT JOIN "UserDataset" d ON r."datasetId" = d.id
            WHERE r.id = $1 AND (r."userId" = $2 OR (r."isShared" = true AND r."recipeGroup" IN (SELECT "userGroup" FROM "User" WHERE id = $2)))
            """,
            recipe_id, user_id
        )

    if row is None:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_not_found, id=recipe_id)
        )

    result = dict(row)
    result["isOwn"] = result["userId"] == user_id
    if result.get("user_name"):
        result["user"] = {"name": result["user_name"]}
    else:
        result["user"] = None

    # Whether *this* caller may save it — the rule the update and delete endpoints already
    # enforce (can_edit_recipe: the owner, or an administrator when the recipe is shared to
    # the administrator's group), so the editor's read-only state follows the backend's
    # verdict rather than re-deriving one from ownership in the client.
    result["canEdit"] = await can_edit_recipe(_db_pool, recipe_id, user_id)

    # Fetch preparation rules for this recipe
    async with _db_pool.acquire() as conn:
        rule_rows = await conn.fetch(
            """
            SELECT rpr."ruleId", rpr."order", dr.name, dr.description
            FROM "RecipePreparationRule" rpr
            JOIN "DataPreparationRule" dr ON rpr."ruleId" = dr.id
            WHERE rpr."recipeId" = $1
            ORDER BY rpr."order" ASC
            """,
            recipe_id
        )
        result["preparation_rules"] = [
            {
                "id": row["ruleId"],
                "name": row["name"],
                "description": row["description"],
                "order": row["order"]
            }
            for row in rule_rows
        ]

    return RecipeResponse(**result)


@router.put("/{recipe_id}")
async def update_recipe(
    recipe_id: str,
    request: UpdateRecipeRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Update an existing recipe."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized)
        )

    user_id = await get_user_id_from_token(credentials)

    # Who may change this recipe: its owner, or an administrator when it is shared to
    # the group that administrator belongs to (can_edit_recipe) — the rule the dataset
    # writes ask. A caller who may not change it gets the same answer a missing recipe
    # gives, so the row's existence is not disclosed.
    may_edit = await can_edit_recipe(_db_pool, recipe_id, user_id)

    async with _db_pool.acquire() as conn:
        existing = await conn.fetchrow(
            'SELECT id, "datasetId" FROM "Recipe" WHERE id = $1',
            recipe_id
        )
        if existing is None or not may_edit:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, recipes_not_owned, id=recipe_id)
            )

    # If datasetId is being changed, validate access
    if request.datasetId is not None:
        async with _db_pool.acquire() as conn:
            dataset_row = await conn.fetchrow(
                """
                SELECT id FROM "UserDataset"
                WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (SELECT "userGroup" FROM "User" WHERE id = $2)))
                """,
                request.datasetId, user_id
            )

            if dataset_row is None:
                raise HTTPException(
                    status_code=404,
                    detail=await t(_db_pool, language, error_dataset_not_found, id=request.datasetId)
                )

    # Validate all preparation rules belong to the dataset
    if request.preparationRuleIds is not None:
        dataset_id_to_check = request.datasetId if request.datasetId is not None else existing["datasetId"]
        await validate_preparation_rules(
            _db_pool, dataset_id_to_check, request.preparationRuleIds, language
        )

    # Validate stages if provided — against the stored column schema when the
    # data_selection stage carries one (the same column checks the manual UI
    # does client-side; external clients bypass the frontend guardrails).
    if request.stages is not None:
        stages_to_validate = [stage.dict() for stage in request.stages]
        try:
            await validate_stages(
                stages_to_validate, language, _db_pool,
                column_info=_stage_column_info(stages_to_validate),
                block_on_warnings=False,
            )
        except ValueError as e:
            raise HTTPException(
                status_code=400,
                detail=str(e)
            )

    updates = []
    params = []
    param_counter = 2  # Start after recipe_id

    if request.name is not None:
        updates.append(f'name = ${param_counter}')
        params.append(request.name)
        param_counter += 1

    if request.description is not None:
        updates.append(f'description = ${param_counter}')
        params.append(request.description)
        param_counter += 1

    if request.datasetId is not None:
        updates.append(f'"datasetId" = ${param_counter}')
        params.append(request.datasetId)
        param_counter += 1

    if request.stages is not None:
        stages = [stage.dict() for stage in request.stages]
        updates.append(f'stages = ${param_counter}')
        params.append(stages)
        param_counter += 1

    if request.recipeGroup is not None:
        updates.append(f'"recipeGroup" = ${param_counter}')
        params.append(request.recipeGroup)
        param_counter += 1

    if not updates:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, recipes_no_updates)
        )

    updates.append('"updatedAt" = NOW()')

    query = f"""
        UPDATE "Recipe"
        SET {', '.join(updates)}
        WHERE id = $1
    """

    async with _db_pool.acquire() as conn:
        result = await conn.execute(query, recipe_id, *params)
        if result == "UPDATE 0":
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, recipes_not_owned, id=recipe_id)
            )

    # Update preparation rules junction entries in a single transaction
    if request.preparationRuleIds is not None:
        async with _db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    'DELETE FROM "RecipePreparationRule" WHERE "recipeId" = $1',
                    recipe_id
                )

                for idx, rule_id in enumerate(request.preparationRuleIds):
                    await conn.execute(
                        """
                        INSERT INTO "RecipePreparationRule" (id, "recipeId", "ruleId", "order", "createdAt", "updatedAt")
                        VALUES ($1, $2, $3, $4, NOW(), NOW())
                        """,
                        str(uuid.uuid4()), recipe_id, rule_id, idx
                    )

    return {
        "success": True,
        "recipe_id": recipe_id,
        "message": await t(_db_pool, language, recipes_update_success, id=recipe_id)
    }


@router.delete("/{recipe_id}")
async def delete_recipe(
    recipe_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Delete a recipe (its owner, or an administrator when it is shared to their group)."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized)
        )

    user_id = await get_user_id_from_token(credentials)

    # Who may delete it: its owner, or an administrator when the recipe is shared to
    # the group that administrator belongs to (can_edit_recipe).
    if not await can_edit_recipe(_db_pool, recipe_id, user_id):
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_not_owned, id=recipe_id)
        )

    # Delete the recipe (junction entries will be cascade deleted)
    async with _db_pool.acquire() as conn:
        try:
            result = await conn.execute(
                'DELETE FROM "Recipe" WHERE id = $1',
                recipe_id
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=await t(_db_pool, language, recipes_delete_error, error=str(e))
            )
        if result == "DELETE 0":
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, recipes_not_owned, id=recipe_id)
            )

    return {
        "success": True,
        "message": await t(_db_pool, language, recipes_delete_success, id=recipe_id)
    }


@router.post("/{recipe_id}/share")
async def toggle_recipe_share(
    recipe_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    """Toggle the shared state of a recipe (owner only)."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized)
        )

    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        # Fetch current recipe state (owner-only)
        row = await conn.fetchrow(
            """
            SELECT "isShared", "recipeGroup", "userId", name
            FROM "Recipe"
            WHERE id = $1 AND "userId" = $2
            """,
            recipe_id, user_id
        )

        if row is None:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, recipes_not_owned, id=recipe_id)
            )

        current_shared = row["isShared"]
        new_shared = not current_shared

        if new_shared:
            # Get owner's userGroup for sharing
            user_row = await conn.fetchrow(
                'SELECT "userGroup" FROM "User" WHERE id = $1', user_id
            )
            new_group = user_row["userGroup"] if user_row and user_row["userGroup"] else "00"
            message_key = recipes_share_enabled
        else:
            new_group = "00"  # Private
            message_key = recipes_share_disabled

        await conn.execute(
            """
            UPDATE "Recipe"
            SET "isShared" = $1, "recipeGroup" = $2, "updatedAt" = NOW()
            WHERE id = $3
            """,
            new_shared, new_group, recipe_id
        )

        return {
            "success": True,
            "isShared": new_shared,
            "message": await t(_db_pool, language, message_key)
        }