"""
Recipe Chat – AI-powered statistical analysis and recipe generation.
Stateless endpoint: takes dataset_id + user message, returns AI response.
Uses the RecipeAssistantAgent from the Agent Framework.
"""

import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import asyncpg

from src.routers.datasets.data_fetch import get_dataset_data
from src.utils.translation import t
from .translations import DATASETS
from src.routers.datasets.crud import get_current_language, get_user_id_from_token

router = APIRouter()
security = HTTPBearer()

_db_pool: Optional[asyncpg.Pool] = None
SECRET_KEY = os.getenv("NEXTAUTH_SECRET")


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


class RecipeChatRequest(BaseModel):
    message: str
    connectionId: int
    model: Optional[str] = None


class RecipeChatResponse(BaseModel):
    response: str


@router.post("/{dataset_id}/recipe-chat", response_model=RecipeChatResponse)
async def recipe_chat(
    dataset_id: str,
    request_body: RecipeChatRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """AI-powered statistical recipe assistant chat."""
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, DATASETS["database.pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials, _db_pool, language)

    async with _db_pool.acquire() as conn:
        user_row = await conn.fetchrow(
            'SELECT "userGroup" FROM "User" WHERE id = $1', user_id
        )
        user_group = user_row["userGroup"] if user_row else "00"

    try:
        columns, rows = await get_dataset_data(_db_pool, user_id, dataset_id, language)
    except Exception as e:
        raise HTTPException(
            status_code=404,
            detail=await t(_db_pool, language, DATASETS["error.dataset.not_found_3"],
                error=str(e),
            ),
        )

    from src.agents.recipe_assistant import RecipeAssistantAgent

    try:
        agent = RecipeAssistantAgent(
            db_pool=_db_pool,
            connection_id=request_body.connectionId,
            user_id=user_id,
            model=request_body.model,
            language=language,
        )
        response = await agent.ask(request_body.message, columns=columns, rows=rows)
        return RecipeChatResponse(response=response)
    except ValueError as e:
        error_msg = str(e)
        if error_msg.startswith("connection_error:"):
            error_key = error_msg.replace("connection_error:", "")
        elif error_msg.startswith("ai_provider_error:"):
            error_key = error_msg.replace("ai_provider_error:", "")
            detail = await t(_db_pool, language, DATASETS["chat.ai_provider_error"], error=error_key)
            raise HTTPException(
                status_code=402,
                detail=detail,
            )
        else:
            error_key = error_msg
        if error_key == "connection.not_found_or_not_accessible":
            detail = await t(_db_pool, language, DATASETS["chat.connection_not_found"])
        else:
            detail = await t(_db_pool, language, DATASETS["error.ai.call_failed"], error=error_key)
        raise HTTPException(
            status_code=400,
            detail=detail,
        )
    except Exception as e:
        raise HTTPException(
            status_code=402,
            detail=await t(_db_pool, language, DATASETS["error.ai.call_failed"],
                error=str(e),
            ),
        )
