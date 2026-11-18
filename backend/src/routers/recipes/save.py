"""
Save an AI recipe session as a completed Recipe — the shared path.

A plain, auth-free helper called by both the HTTP save endpoint
(``routers/recipes/ai_session.py``) and the AI ``save_recipe`` tool
(``routers/recipes/ai_recipe_tools.py``). One code path, two callers — the
"dual-callable shared helper" pattern of ``project-design.md`` §1.3, and the
reason the two callers can no longer disagree about what saving a recipe means.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import HTTPException

from src.utils.translation import t

from .crud import create_recipe_record, validate_preparation_rules
from .helpers import collect_recipe_issues
from .translations import ai_recipe_session_name_required, recipes_dataset_required
from ..datasets.schema import fetch_dataset_schema

logger = logging.getLogger(__name__)


async def save_session_recipe(
    db_pool,
    user_id: str,
    language: str,
    session_id: str,
    stages: Optional[List[Dict[str, Any]]],
    name: str,
    dataset_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Validate a recipe draft and persist it, completing its session.

    Both callers supply what they each hold: the endpoint passes the persisted
    ``state["stages"]`` and its resolved name; the AI tool passes the arguments
    the model gave it. Everything after that — ownership, the validation gate,
    the preparation-rule check, the insert, and the session bookkeeping — is the
    same code for both.

    Returns one of:
        ``{"status": "ok", "recipe_id", "name", "stages"}``
        ``{"status": "not_found"}``            — no such session for this user
        ``{"status": "invalid", "message", "issues"}``   — validation failed
        ``{"status": "http_error", "status_code", "message"}`` — a shared helper
            rejected the request (e.g. a transform from another dataset); the
            endpoint re-raises the original status, the tool returns the message
        ``{"status": "error"}``                — unexpected failure, already logged
    """
    # 1. The session must exist and belong to this user.
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id, state->>'saved_recipe_id' AS saved_recipe_id
            FROM "AIRecipeSession"
            WHERE id = $1 AND "userId" = $2
            """,
            session_id, user_id,
        )

    if not row:
        return {"status": "not_found"}

    # Idempotent: if this session already saved a recipe, return that recipe
    # instead of inserting a duplicate (a model can call save_recipe more than
    # once). A dataset change clears saved_recipe_id (set_session_dataset), so
    # this only fires for a genuine re-save of the same recipe.
    if row["saved_recipe_id"]:
        async with db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                'SELECT id, name, stages FROM "Recipe" WHERE id = $1 AND "userId" = $2',
                row["saved_recipe_id"], user_id,
            )
        if existing:
            return {
                "status": "ok",
                "recipe_id": existing["id"],
                "name": existing["name"],
                "stages": existing["stages"],
            }

    # 2. The dataset and transform ids live in the data_selection stage's config
    #    — the same source the manual editor persists. A caller that was handed
    #    a dataset id (the AI tool) may fall back to it when the draft carries none.
    draft = stages or []
    config_dataset_id = None
    transform_ids: List[str] = []
    for stage in draft:
        if isinstance(stage, dict) and stage.get("type") == "data_selection":
            config = stage.get("config") or {}
            config_dataset_id = config.get("datasetId")
            transform_ids = config.get("transformIds") or []
            break

    effective_dataset_id = config_dataset_id or dataset_id

    # A recipe without a dataset is invalid — a data_selection stage with a
    # datasetId (or an explicit dataset_id) is required, otherwise the saved
    # recipe can never run. Checked before the validation gate, because the
    # column-aware checks below need a dataset to validate against.
    if not effective_dataset_id:
        return {
            "status": "invalid",
            "message": await t(db_pool, language, recipes_dataset_required),
            "issues": [],
        }

    # A name is required — a recipe is not complete without one, and a model can
    # invent a name the user never supplied. Fail rather than persist it.
    if not name or not name.strip():
        return {
            "status": "invalid",
            "message": await t(db_pool, language, ai_recipe_session_name_required),
            "issues": [],
        }

    # Resolve the dataset's columns so the validation gate applies the same
    # column checks the manual UI does — existence, type and count requirements —
    # rather than a column-blind pass.
    column_info = None
    try:
        # Columns only: the row count is not read here, so the narrower
        # function is used and the COUNT(*) is not paid for.
        schema = await fetch_dataset_schema(effective_dataset_id, user_id, language)
        cols = (schema or {}).get("columns") or []
        if cols:
            column_info = cols
    except HTTPException:
        # Schema unavailable (connection down, dataset deleted mid-flight): the
        # gate degrades to the column-blind pass rather than failing the save.
        column_info = None

    # 3. The one validation gate — structured issues, never raising.
    gate = await collect_recipe_issues(
        draft, language, db_pool, column_info=column_info, block_on_warnings=False
    )
    if gate["message"] is not None:
        return {
            "status": "invalid",
            "message": gate["message"],
            "issues": gate["issues"],
        }

    # 4. Transforms must belong to the linked dataset (the shared check).
    try:
        await validate_preparation_rules(
            db_pool, effective_dataset_id, transform_ids, language
        )
    except HTTPException as e:
        return {
            "status": "http_error",
            "status_code": e.status_code,
            "message": str(e.detail),
        }

    # 5. Persist — create_recipe_record runs its own transaction (recipe plus
    #    preparation-rule junction rows).
    try:
        recipe_id = await create_recipe_record(
            db_pool, user_id, name, None, effective_dataset_id, draft,
            transform_ids, False, "00",
        )
    except Exception as e:
        logger.error(f"Failed to save recipe from session {session_id}: {e}")
        return {"status": "error"}

    # 6. Complete the session and record the recipe id — one key, merged into
    #    whatever the row holds now. The turn that called this tool writes its
    #    own state after the tool loop returns, so a whole-blob write here would
    #    be undone by it; and replacing the blob would also drop keys this module
    #    does not model (the session's displayName, for one).
    try:
        async with db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE "AIRecipeSession"
                SET stage = 'complete', status = 'complete',
                    state = state || jsonb_build_object('saved_recipe_id', $1::text),
                    "updatedAt" = NOW()
                WHERE id = $2
                """,
                recipe_id,
                session_id,
            )
    except Exception as e:
        logger.error(f"Failed to complete session {session_id}: {e}")
        return {"status": "error"}

    return {
        "status": "ok",
        "recipe_id": recipe_id,
        "name": name,
        "stages": draft,
    }
