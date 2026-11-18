"""
Data Cleaning Chat – Stateful session lifecycle for the AI data-cleaning concierge.

Session endpoints (create / list / get / delete) over the `DataCleanChat` table,
mirroring the virtual-dataset chat session endpoints. The send-message tool loop
and the dataset-selection action are layered on top of these sessions in later
plan items.
"""

import uuid
import logging
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.routers.datasets.crud import get_user_id_from_token, get_current_language
from src.utils.timestamps import iso_utc
from src.utils.translation import t
from .translations import DATASETS
from .clean_chat import handle_dataset_selected

logger = logging.getLogger(__name__)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


router = APIRouter(prefix="/dataclean/chat", tags=["dataclean-chat"])
security = HTTPBearer()


# ── POST: Create session ──────────────────────────────────────

@router.post("")
async def create_chat_session(
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Create a new data-cleaning chat session (no dataset bound yet)."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]),
        )

    user_id = await get_user_id_from_token(credentials)
    chat_id = str(uuid.uuid4())

    try:
        async with _db_pool.acquire() as conn:
            await conn.execute(
                """
                INSERT INTO "DataCleanChat"
                    (id, "userId", "datasetId", "contextData", "messages", "status", "updatedAt")
                VALUES ($1, $2, NULL, '{}'::jsonb, '[]'::jsonb, 'active', NOW())
                """,
                chat_id, user_id,
            )
    except Exception as e:
        logger.error(f"Failed to create data-cleaning chat session: {e}")
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DATASETS["dataclean_chat.create_error"]),
        )

    return {"chatId": chat_id, "datasetId": None}


# ── POST: Dataset selected (re-grounding turn) ────────────────

@router.post("/{chat_id}/dataset-selected")
async def dataset_selected(
    chat_id: str,
    body: dict,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Bind a dataset to the session and run one short re-grounding turn."""
    if _db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]),
        )

    user_id = await get_user_id_from_token(credentials)
    dataset_id = (body.get("datasetId") or "").strip()
    if not dataset_id:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, DATASETS["dataclean_chat.dataset_id_required"]),
        )

    try:
        return await handle_dataset_selected(
            _db_pool, user_id, chat_id, dataset_id,
            connection_id=body.get("connectionId"),
            model=body.get("model"),
            language=language,
        )
    except ValueError as e:
        if str(e) == "session_not_found":
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, DATASETS["dataclean_chat.chat_session_not_found"]),
            )
        raise HTTPException(status_code=400, detail=str(e))
    except RuntimeError as e:
        logger.error(f"LLM error for chat {chat_id}: {e}")
        raise HTTPException(
            status_code=502,
            detail=await t(_db_pool, language, DATASETS["error.ai.call_failed"], error=str(e)),
        )


# ── GET: List sessions ────────────────────────────────────────

@router.get("")
async def list_chat_sessions(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """List data-cleaning chat sessions for the current user."""
    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        rows = await conn.fetch(
            """
            SELECT id, "datasetId", status, "createdAt", "updatedAt"
            FROM "DataCleanChat"
            WHERE "userId" = $1
            ORDER BY "updatedAt" DESC
            """,
            user_id,
        )

        chats = []
        for r in rows:
            chats.append({
                "chatId": r["id"],
                "datasetId": r["datasetId"],
                "status": r["status"],
                "createdAt": iso_utc(r["createdAt"]),
                "updatedAt": iso_utc(r["updatedAt"]),
            })

        return {"chats": chats}


# ── GET: Load session ─────────────────────────────────────────

@router.get("/{chat_id}")
async def get_chat_session(
    chat_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Load a data-cleaning chat session."""
    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT * FROM "DataCleanChat" WHERE id = $1 AND "userId" = $2',
            chat_id, user_id,
        )
        if not row:
            raise HTTPException(
                status_code=404,
                detail=await t(_db_pool, language, DATASETS["dataclean_chat.chat_session_not_found"]),
            )

        raw_messages = row["messages"]
        raw_context = row["contextData"]
        return {
            "chatId": row["id"],
            "datasetId": row["datasetId"],
            "contextData": raw_context or {},
            "messages": raw_messages or [],
            "status": row["status"],
        }


# ── DELETE: Delete session ────────────────────────────────────

@router.delete("/{chat_id}")
async def delete_chat_session(
    chat_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Delete a data-cleaning chat session (does not delete the dataset)."""
    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        await conn.execute(
            'DELETE FROM "DataCleanChat" WHERE id = $1 AND "userId" = $2',
            chat_id, user_id,
        )

    return {"success": True}
