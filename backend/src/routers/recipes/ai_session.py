"""
AI Recipe Session CRUD — Phase 1.2 / 1.4

Persistent chat sessions for the AI Recipe Concierge.
Follows the VirtualDatasetChat pattern from virtual_chat.py.
"""

import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.chat.connection import get_connection_details
from src.routers.common.translations import CHAT
from src.routers.datasets.crud import get_user_id_from_token, get_current_language
from src.utils.translation import t
from src.utils.timestamps import iso_utc
from .translations import (
    ai_recipe_invalid_decision,
    ai_recipe_llm_error,
    ai_recipe_message_required,
    ai_recipe_session_name_required,
    error_database_pool_not_initialized,
    recipes_ai_session_create_error,
    recipes_ai_session_delete_error,
    recipes_ai_session_load_error,
    recipes_ai_session_not_found,
    recipes_ai_session_save_error,
    recipes_dataset_not_found,
    recipes_dataset_required,
)
from .ai_agent import AIChefAgent
from .ai_recipe_tools import build_scoreboard, register_all_tools
from .save import save_session_recipe

logger = logging.getLogger("uvicorn.trace")

register_all_tools()


async def _llm_error_detail(db_pool, language, error: str) -> str:
    """Map a raw LLM RuntimeError to a translated, user-facing detail.

    The repeat-loop abort and provider failures get a graceful message;
    the raw technical detail stays in the log, never in the reply.
    """
    if error.startswith("ai_repeat_loop:"):
        return await t(db_pool, language, CHAT["chat.ai_repeat_loop"])
    if error.startswith("ai_timeout:"):
        return await t(db_pool, language, CHAT["chat.ai_timeout"])
    if error.startswith("ai_provider_error:"):
        return await t(db_pool, language, CHAT["chat.ai_service_failed"])
    return await t(db_pool, language, ai_recipe_llm_error, error=error)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


router = APIRouter(prefix="/ai/sessions", tags=["ai-recipe-sessions"])
security = HTTPBearer()


# ============================================================
# POST: Create session
# ============================================================

@router.post("")
async def create_session(
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Create a new AI recipe session, optionally attached to a dataset."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized,
            ),
        )

    user_id = await get_user_id_from_token(credentials)
    session_id = str(uuid.uuid4())
    dataset_id = body.get("datasetId")

    # A dataset attached here must be one the caller can *see* — their own, or one
    # shared to their group. The session then reads that dataset's schema, so this is
    # the visibility predicate, not the edit rule (attaching writes nothing to the
    # dataset); a dataset the caller cannot see is refused with the same answer a
    # nonexistent id gives.
    if dataset_id:
        async with _db_pool.acquire() as conn:
            ds = await conn.fetchrow(
                """
                SELECT id FROM "UserDataset"
                WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                    SELECT "userGroup" FROM "User" WHERE id = $2
                )))
                """,
                dataset_id, user_id,
            )
        if not ds:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, recipes_dataset_not_found),
            )

    try:
        async with _db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO "AIRecipeSession"
                    (id, "userId", "datasetId", "updatedAt")
                VALUES ($1, $2, $3, NOW())
                """,
                session_id, user_id, dataset_id,
            )
    except Exception as e:
        logger.error(f"Failed to create AI recipe session: {e}")
        raise HTTPException(
            status_code=500,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_create_error,
            ),
        )

    return {"sessionId": session_id, "datasetId": dataset_id}


# ============================================================
# POST: Create session from manual recipe
# ============================================================

@router.post("/from-recipe/{recipe_id}")
async def create_from_recipe(
    recipe_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Create an AI recipe session from an existing manual recipe."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized,
            ),
        )

    user_id = await get_user_id_from_token(credentials)

    # Fetch the manual recipe
    async with _db_pool.acquire() as conn:
        recipe_row = await conn.fetchrow(
            """
            SELECT id, "datasetId", name, stages
            FROM "Recipe"
            WHERE id = $1 AND "userId" = $2
            """,
            recipe_id, user_id,
        )

    if not recipe_row:
        raise HTTPException(
            status_code=404,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_not_found,
            ),
        )

    raw_stages = recipe_row["stages"]
    stage_list = raw_stages or []

    # Copy the manual recipe's stages into the draft verbatim.
    state = {}
    state["convertedFromRecipeId"] = recipe_id
    if recipe_row["name"]:
        state["displayName"] = recipe_row["name"]
    state["stages"] = stage_list

    session_id = str(uuid.uuid4())

    try:
        async with _db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO "AIRecipeSession"
                    (id, "userId", "datasetId", state, stage, status, "updatedAt")
                VALUES ($1, $2, $3, $4, $5, $6, NOW())
                """,
                session_id, user_id, recipe_row["datasetId"],
                state,
                "review" if state else "greeting",
                "active",
            )
    except Exception as e:
        logger.error(f"Failed to create session from recipe {recipe_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_create_error,
            ),
        )

    return {"sessionId": session_id, "state": state}


# ============================================================
# GET: List sessions
# ============================================================

@router.get("")
async def list_sessions(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """List all AI recipe sessions for the current user, newest first."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized,
            ),
        )

    user_id = await get_user_id_from_token(credentials)

    try:
        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                """
                SELECT id, "datasetId", stage, status, state, "createdAt", "updatedAt"
                FROM "AIRecipeSession"
                WHERE "userId" = $1
                ORDER BY "updatedAt" DESC
                """,
                user_id,
            )
    except Exception as e:
        logger.error(f"Failed to list AI recipe sessions: {e}")
        raise HTTPException(
            status_code=500,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_load_error,
            ),
        )

    # Collect IDs of manual recipes that have been converted to AI sessions
    converted_recipe_ids = set()
    sessions = []
    for r in rows:
        raw_state = r["state"]
        state_data = raw_state or {}
        # state is read as an object everywhere below. A row that is not one —
        # left by an earlier write — must not take the whole list down with it.
        if not isinstance(state_data, dict):
            state_data = {}
        conv_id = state_data.get("convertedFromRecipeId")
        if conv_id:
            converted_recipe_ids.add(conv_id)
        sessions.append({
            "sessionId": r["id"],
            "datasetId": r["datasetId"],
            "stage": r["stage"],
            "status": r["status"],
            "createdAt": iso_utc(r["createdAt"]),
            "updatedAt": iso_utc(r["updatedAt"]),
            "isManualRecipe": False,
            "displayName": state_data.get("displayName") or state_data.get("goal") or None,
        })

    # Also fetch manual recipes, excluding those already converted
    try:
        async with _db_pool.acquire() as conn:
            recipe_rows = await conn.fetch(
                """
                SELECT id, "datasetId", stages, name, "createdAt", "updatedAt"
                FROM "Recipe"
                WHERE "userId" = $1
                ORDER BY "updatedAt" DESC
                """,
                user_id,
            )
        for r in recipe_rows:
            if r["id"] in converted_recipe_ids:
                continue  # already converted, skip manual entry
            raw_stages = r["stages"]
            stage_list = raw_stages or []
            has_stages = len(stage_list) > 0
            sessions.append({
                "sessionId": r["id"],
                "datasetId": r["datasetId"],
                "stage": "manual",
                "status": "complete" if has_stages else "draft",
                "createdAt": iso_utc(r["createdAt"]),
                "updatedAt": iso_utc(r["updatedAt"]),
                "isManualRecipe": True,
                "recipeName": r["name"] or "Manual Recipe",
                "displayName": r["name"] or "Manual Recipe",
            })
    except Exception:
        pass  # non-critical; AI sessions still returned

    return {"sessions": sessions}


# ============================================================
# GET: Load session
# ============================================================

@router.get("/{session_id}")
async def get_session(
    session_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Load a full AI recipe session with messages and state."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized,
            ),
        )

    user_id = await get_user_id_from_token(credentials)

    try:
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """
                SELECT * FROM "AIRecipeSession"
                WHERE id = $1 AND "userId" = $2
                """,
                session_id, user_id,
            )
    except Exception as e:
        logger.error(f"Failed to load AI recipe session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_load_error,
            ),
        )

    if not row:
        raise HTTPException(
            status_code=404,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_not_found,
            ),
        )

    raw_msgs = row["messages"]
    raw_state = row["state"] if isinstance(row["state"], dict) else {}
    raw_schema = row["schemaSnapshot"]

    # The scoreboard on open, not only after a turn. Resume used to hand the page
    # a draft and a transcript and no progress at all, so a reopened session
    # showed no count and no next step until the user spoke — the state read as
    # lost even though the draft was intact.
    #
    # Computed through `build_scoreboard`, the same function a turn uses, so
    # there is one definition of "what is decided" rather than a second one here.
    # Best-effort: if it raises, the session still loads without it, because
    # failing to compute a progress label must not make a session unopenable.
    scoreboard = None
    unread: list = []
    try:
        scoreboard, _, unread = await build_scoreboard(
            _db_pool, user_id, language,
            raw_state.get("stages") or [],
            raw_state.get("goal"),
        )
    except Exception as exc:  # noqa: BLE001 — a label must not break the load
        logger.warning("scoreboard unavailable for session %s: %s", session_id, exc)

    return {
        "sessionId": row["id"],
        "datasetId": row["datasetId"],
        "status": row["status"],
        "stage": row["stage"],
        "messages": raw_msgs or [],
        "state": raw_state,
        "schemaSnapshot": raw_schema,
        "scoreboard": scoreboard,
        "unread": unread or [],
        "createdAt": iso_utc(row["createdAt"]),
        "updatedAt": iso_utc(row["updatedAt"]),
    }


# ============================================================
# DELETE: Delete session
# ============================================================

@router.delete("/{session_id}")
async def delete_session(
    session_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Delete an AI recipe session."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized,
            ),
        )

    user_id = await get_user_id_from_token(credentials)

    try:
        async with _db_pool.acquire() as conn:
            await conn.execute(
                """
                DELETE FROM "AIRecipeSession"
                WHERE id = $1 AND "userId" = $2
                """,
                session_id, user_id,
            )
    except Exception as e:
        logger.error(f"Failed to delete AI recipe session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_delete_error,
            ),
        )

    return {"success": True}


# ============================================================
# PATCH: Set dataset — update session datasetId and capture schema
# ============================================================

@router.patch("/{session_id}/dataset")
async def set_session_dataset(
    session_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Attach a dataset to an existing AI recipe session and capture its schema."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized),
        )

    user_id = await get_user_id_from_token(credentials)
    dataset_id = body.get("datasetId")

    if not dataset_id:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, recipes_dataset_required),
        )

    # The dataset must be one the caller can *see* — their own, or one shared to their
    # group — which is what lets a shared dataset be attached to a session (case 3's
    # "input to a recipe"). Reading is not editing: attaching writes nothing to the
    # dataset, so this is the visibility predicate, not the edit rule.
    async with _db_pool.acquire() as conn:
        ds = await conn.fetchrow(
            """
            SELECT id FROM "UserDataset"
            WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                SELECT "userGroup" FROM "User" WHERE id = $2
            )))
            """,
            dataset_id, user_id,
        )
    if not ds:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_dataset_not_found),
        )

    # A change of dataset invalidates the draft: its data_selection names the
    # old dataset and the statistics/visualisation stages reference the old
    # dataset's columns. Reset the draft to a single data_selection stage
    # carrying the newly selected dataset (and drop the now-stale saved recipe
    # id), so the scoreboard shows "dataset" as crystallised and the model
    # rebuilds for the new dataset without re-asking for one.
    async with _db_pool.acquire() as conn:
        old = await conn.fetchrow(
            'SELECT "datasetId" FROM "AIRecipeSession" WHERE id = $1 AND "userId" = $2',
            session_id, user_id,
        )
    reset_draft = dataset_id != (old["datasetId"] if old else None)

    # Capture schema
    schema_snapshot = None
    try:
        from .ai_agent import AIChefAgent
        agent = AIChefAgent(_db_pool, user_id, session_id=session_id, language=language)
        schema = await agent._capture_schema(dataset_id)
        if schema:
            schema_snapshot = schema
    except Exception as e:
        logger.warning(f"Failed to capture schema for dataset {dataset_id}: {e}")

    async with _db_pool.acquire() as conn:
        await conn.execute(
            """
            UPDATE "AIRecipeSession"
            SET "datasetId" = $1, "schemaSnapshot" = $2,
                state = CASE WHEN $5 THEN state || jsonb_build_object(
                    'stages', jsonb_build_array(
                        jsonb_build_object(
                            'type', 'data_selection',
                            'config', jsonb_build_object('datasetId', $1::text, 'transformIds', jsonb_build_array())
                        )
                    ),
                    'saved_recipe_id', null
                ) ELSE state END,
                "updatedAt" = NOW()
            WHERE id = $3 AND "userId" = $4
            """,
            dataset_id, schema_snapshot, session_id, user_id, reset_draft,
        )

    return {"success": True, "datasetId": dataset_id}


# ============================================================
# PATCH: Rename session — update display name (state.goal)
# ============================================================

@router.patch("/{session_id}/name")
async def rename_session(
    session_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Rename an AI recipe session by updating its state.displayName field."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized,
            ),
        )

    user_id = await get_user_id_from_token(credentials)
    new_name = (body.get("name") or "").strip()

    if not new_name:
        raise HTTPException(
            status_code=400,
            detail=await t(
                _db_pool, language,
                ai_recipe_session_name_required,
            ),
        )

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT id FROM "AIRecipeSession"
            WHERE id = $1 AND "userId" = $2
            """,
            session_id, user_id,
        )

    if not row:
        raise HTTPException(
            status_code=404,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_not_found,
            ),
        )

    # One key, merged into whatever the row holds now. Reading the state and
    # writing the whole blob back — which is what this used to do — erased
    # anything another writer put there while this request was in flight, the
    # saved recipe id included.
    try:
        async with _db_pool.acquire() as conn:
            await conn.execute(
                """
                UPDATE "AIRecipeSession"
                SET state = state || jsonb_build_object('displayName', $1::text),
                    "updatedAt" = NOW()
                WHERE id = $2 AND "userId" = $3
                """,
                new_name, session_id, user_id,
            )
    except Exception as e:
        logger.error(f"Failed to rename session {session_id}: {e}")
        raise HTTPException(
            status_code=500,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_create_error,
            ),
        )

    return {"success": True, "displayName": new_name}


# ============================================================
# POST: Send message (Phase 2.3)
# ============================================================

@router.post("/{session_id}/message")
async def send_message(
    session_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Send a user message to the AI recipe concierge."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized,
            ),
        )

    user_id = await get_user_id_from_token(credentials)
    user_message = body.get("message", "")

    if not user_message.strip():
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, ai_recipe_message_required,
            ),
        )

    # Verify session exists and belongs to user
    async with _db_pool.acquire() as conn:
        exists = await conn.fetchrow(
            """
            SELECT id FROM "AIRecipeSession"
            WHERE id = $1 AND "userId" = $2
            """,
            session_id, user_id,
        )

    if not exists:
        raise HTTPException(
            status_code=404,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_not_found,
            ),
        )

    # Resolve AI connection details if provided, through the shared resolver:
    # owned or shared connections, and the provider's default endpoint when the
    # connection carries none of its own.
    api_key = None
    endpoint = None
    provider = None
    connection_model = None
    connection_id = body.get("connectionId")
    if connection_id:
        try:
            details = await get_connection_details(_db_pool, connection_id, user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=await t(_db_pool, language, CHAT["chat.connection_not_found"]))
        api_key, endpoint = details["apiKey"], details["endpoint"]
        provider = details["provider"]
        connection_model = details["model"]

    # The connection's default model is the fallback: with none the request goes
    # out as model=null and the provider rejects the body outright.
    model = body.get("model") or connection_model

    try:
        agent = AIChefAgent(_db_pool, user_id, session_id=session_id, language=language, api_key=api_key, endpoint=endpoint, model=model, provider=provider)
        result = await agent.send_message(session_id, user_message)
        return result
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_not_found,
            ),
        )
    except RuntimeError as e:
        logger.error(f"LLM error for session {session_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=await _llm_error_detail(_db_pool, language, str(e)),
        )


@router.post("/{session_id}/decision")
async def apply_decision(
    session_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Apply a decision the user made by clicking a suggestion chip (technique or
    output), then re-ground the model — the clickable counterpart to typing the
    choice. Mirrors the message endpoint's connection resolution and error shape."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized),
        )

    user_id = await get_user_id_from_token(credentials)
    piece = body.get("piece")
    value = (body.get("value") or "").strip()

    # `name` is a decision like any other from this route's point of view: the
    # chip the user accepted carries it, and the applier writes it to the draft.
    # It is an `invite` piece, so the value is the user's own words rather than a
    # token from a closed set — which is why it is validated for being non-empty
    # and nothing else.
    if piece not in ("technique", "output", "name") or not value:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, ai_recipe_invalid_decision),
        )

    # Verify session exists and belongs to user
    async with _db_pool.acquire() as conn:
        exists = await conn.fetchrow(
            """
            SELECT id FROM "AIRecipeSession"
            WHERE id = $1 AND "userId" = $2
            """,
            session_id, user_id,
        )

    if not exists:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_ai_session_not_found),
        )

    # Resolve AI connection details if provided (same as the message endpoint).
    api_key = None
    endpoint = None
    provider = None
    connection_model = None
    connection_id = body.get("connectionId")
    if connection_id:
        try:
            details = await get_connection_details(_db_pool, connection_id, user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=await t(_db_pool, language, CHAT["chat.connection_not_found"]))
        api_key, endpoint = details["apiKey"], details["endpoint"]
        provider = details["provider"]
        connection_model = details["model"]

    model = body.get("model") or connection_model

    try:
        agent = AIChefAgent(_db_pool, user_id, session_id=session_id, language=language, api_key=api_key, endpoint=endpoint, model=model, provider=provider)
        return await agent.handle_decision(session_id, piece, value)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_ai_session_not_found),
        )
    except RuntimeError as e:
        logger.error(f"LLM error for session {session_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=await _llm_error_detail(_db_pool, language, str(e)),
        )


@router.post("/{session_id}/proposal")
async def apply_proposal(
    session_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Apply a proposal the user accepted by clicking its chip, then re-ground the
    model.

    A route of its own rather than a third `piece` on `/decision`: that route
    carries one choice as a string, and a proposal is a list of field choices.
    Keeping them apart means neither body has two shapes, and `/decision`'s three
    existing refusals (invalid piece, empty value, unknown session) keep meaning
    exactly what they meant before.

    Only the fields still undecided are applied — see `AIChefAgent.handle_proposal`;
    a snapshot replayed over a choice the user has since made would undo it.
    """
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized),
        )

    user_id = await get_user_id_from_token(credentials)
    fields = body.get("fields")

    if not isinstance(fields, list) or not fields:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, ai_recipe_invalid_decision),
        )

    async with _db_pool.acquire() as conn:
        exists = await conn.fetchrow(
            'SELECT id FROM "AIRecipeSession" WHERE id = $1 AND "userId" = $2',
            session_id, user_id,
        )

    if not exists:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_ai_session_not_found),
        )

    # Resolve AI connection details if provided (same as the decision endpoint).
    api_key = None
    endpoint = None
    provider = None
    connection_model = None
    connection_id = body.get("connectionId")
    if connection_id:
        try:
            details = await get_connection_details(_db_pool, connection_id, user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=await t(_db_pool, language, CHAT["chat.connection_not_found"]))
        api_key, endpoint = details["apiKey"], details["endpoint"]
        provider = details["provider"]
        connection_model = details["model"]

    model = body.get("model") or connection_model

    try:
        agent = AIChefAgent(_db_pool, user_id, session_id=session_id, language=language, api_key=api_key, endpoint=endpoint, model=model, provider=provider)
        return await agent.handle_proposal(session_id, fields)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_ai_session_not_found),
        )
    except RuntimeError as e:
        logger.error(f"LLM error for session {session_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=await _llm_error_detail(_db_pool, language, str(e)),
        )


@router.post("/{session_id}/field-column")
async def apply_field_column_choice(
    session_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Record a column choice the user made by clicking a column chip, then
    re-ground the model — the clickable counterpart to typing the column name."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized),
        )

    user_id = await get_user_id_from_token(credentials)
    piece = body.get("piece")
    field = (body.get("field") or "").strip()
    column = (body.get("column") or "").strip()
    action = body.get("action") or "commit"

    if piece not in ("technique_fields", "output_fields") or not field:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, ai_recipe_invalid_decision),
        )
    if action not in ("commit", "toggle", "done"):
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, ai_recipe_invalid_decision),
        )
    if action in ("commit", "toggle") and not column:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, ai_recipe_invalid_decision),
        )

    # Verify session exists and belongs to user
    async with _db_pool.acquire() as conn:
        exists = await conn.fetchrow(
            """
            SELECT id FROM "AIRecipeSession"
            WHERE id = $1 AND "userId" = $2
            """,
            session_id, user_id,
        )

    if not exists:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_ai_session_not_found),
        )

    # Resolve AI connection details if provided (same as the message endpoint).
    api_key = None
    endpoint = None
    provider = None
    connection_model = None
    connection_id = body.get("connectionId")
    if connection_id:
        try:
            details = await get_connection_details(_db_pool, connection_id, user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=await t(_db_pool, language, CHAT["chat.connection_not_found"]))
        api_key, endpoint = details["apiKey"], details["endpoint"]
        provider = details["provider"]
        connection_model = details["model"]

    model = body.get("model") or connection_model

    try:
        agent = AIChefAgent(_db_pool, user_id, session_id=session_id, language=language, api_key=api_key, endpoint=endpoint, model=model, provider=provider)
        return await agent.handle_field_column(session_id, piece, field, column or None, action)
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_ai_session_not_found),
        )
    except RuntimeError as e:
        logger.error(f"LLM error for session {session_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=await _llm_error_detail(_db_pool, language, str(e)),
        )


@router.post("/{session_id}/dataset-selected")
async def dataset_selected(
    session_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Acknowledge a newly selected dataset (one short LLM turn)."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized),
        )

    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        exists = await conn.fetchrow(
            'SELECT id FROM "AIRecipeSession" WHERE id = $1 AND "userId" = $2',
            session_id, user_id,
        )
    if not exists:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_ai_session_not_found),
        )

    # Resolve AI connection details if provided, through the shared resolver:
    # owned or shared connections, and the provider's default endpoint when the
    # connection carries none of its own.
    api_key = None
    endpoint = None
    provider = None
    connection_model = None
    connection_id = body.get("connectionId")
    if connection_id:
        try:
            details = await get_connection_details(_db_pool, connection_id, user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=await t(_db_pool, language, CHAT["chat.connection_not_found"]))
        api_key, endpoint = details["apiKey"], details["endpoint"]
        provider = details["provider"]
        connection_model = details["model"]

    # The connection's default model is the fallback: with none the request goes
    # out as model=null and the provider rejects the body outright.
    model = body.get("model") or connection_model

    try:
        agent = AIChefAgent(_db_pool, user_id, session_id=session_id, language=language, api_key=api_key, endpoint=endpoint, model=model, provider=provider)
        result = await agent.handle_dataset_selected(session_id)
        return result
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_ai_session_not_found),
        )
    except RuntimeError as e:
        logger.error(f"LLM error for session {session_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=await _llm_error_detail(_db_pool, language, str(e)),
        )


@router.post("/{session_id}/recipe-loaded")
async def recipe_loaded(
    session_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Acknowledge a session cloned from a saved recipe (one short LLM turn)."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized),
        )

    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        exists = await conn.fetchrow(
            'SELECT id FROM "AIRecipeSession" WHERE id = $1 AND "userId" = $2',
            session_id, user_id,
        )
    if not exists:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_ai_session_not_found),
        )

    # Resolve AI connection details if provided, through the shared resolver:
    # owned or shared connections, and the provider's default endpoint when the
    # connection carries none of its own.
    api_key = None
    endpoint = None
    provider = None
    connection_model = None
    connection_id = body.get("connectionId")
    if connection_id:
        try:
            details = await get_connection_details(_db_pool, connection_id, user_id)
        except ValueError:
            raise HTTPException(status_code=400, detail=await t(_db_pool, language, CHAT["chat.connection_not_found"]))
        api_key, endpoint = details["apiKey"], details["endpoint"]
        provider = details["provider"]
        connection_model = details["model"]

    # The connection's default model is the fallback: with none the request goes
    # out as model=null and the provider rejects the body outright.
    model = body.get("model") or connection_model

    try:
        agent = AIChefAgent(_db_pool, user_id, session_id=session_id, language=language, api_key=api_key, endpoint=endpoint, model=model, provider=provider)
        result = await agent.handle_recipe_loaded(session_id)
        return result
    except ValueError:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, recipes_ai_session_not_found),
        )
    except RuntimeError as e:
        logger.error(f"LLM error for session {session_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=await _llm_error_detail(_db_pool, language, str(e)),
        )


# ============================================================
# POST: Save session as recipe (Phase 4.1)
# ============================================================

@router.post("/{session_id}/save")
async def save_recipe(
    session_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Save an AI recipe session as a completed Recipe."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, error_database_pool_not_initialized,
            ),
        )

    user_id = await get_user_id_from_token(credentials)

    # Load the session's draft. The shared path (recipes/save.py) owns ownership,
    # validation, the insert and the session bookkeeping — and re-checks ownership
    # itself, because the AI tool calls it without coming through this endpoint.
    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT state
            FROM "AIRecipeSession"
            WHERE id = $1 AND "userId" = $2
            """,
            session_id, user_id,
        )

    if not row:
        raise HTTPException(
            status_code=404,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_not_found,
            ),
        )

    state_data = row["state"] or {}

    recipe_name = (
        body.get("name") or state_data.get("displayName") or state_data.get("goal") or ""
    ).strip()
    if not recipe_name:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, ai_recipe_session_name_required),
        )

    # The draft stages are already canonical — read them straight from state.
    stages = state_data.get("stages") or []

    result = await save_session_recipe(
        _db_pool, user_id, language, session_id, stages, recipe_name,
    )

    if result["status"] == "not_found":
        raise HTTPException(
            status_code=404,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_not_found,
            ),
        )
    if result["status"] == "invalid":
        raise HTTPException(status_code=400, detail=result["message"])
    if result["status"] == "http_error":
        raise HTTPException(
            status_code=result["status_code"], detail=result["message"]
        )
    if result["status"] == "error":
        raise HTTPException(
            status_code=500,
            detail=await t(
                _db_pool, language,
                recipes_ai_session_save_error,
            ),
        )

    return {
        "recipeId": result["recipe_id"],
        "name": result["name"],
        "stages": result["stages"],
    }
