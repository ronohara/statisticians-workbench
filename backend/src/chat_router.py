"""
Chat Router – AI Chat Messaging
Part of the 0.0.10 "Statistical Foundation" milestone.
"""

import os
import logging
from fastapi import APIRouter, Depends, HTTPException, status, Request
from starlette.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
from typing import List, Optional
import jwt
from dotenv import load_dotenv

from .chat import ChatManager
from src.utils.ai_limits import MAX_TIMEOUT_SECONDS, TIMEOUT_ERRORS
from src.utils.translation import t
from .routers.datasets.crud import get_current_language
from .routers.common.translations import CHAT
from src.utils.timestamps import iso_utc

load_dotenv()

# Set up logger
logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

# This will be set by main.py
db_pool = None

def set_db_pool(pool):
    global db_pool
    db_pool = pool

SECRET_KEY = os.getenv("NEXTAUTH_SECRET")
if not SECRET_KEY:
    raise RuntimeError("NEXTAUTH_SECRET environment variable not set")

security = HTTPBearer()

async def get_user_id_from_token(credentials: HTTPAuthorizationCredentials, db_pool=None, language: str = "en") -> str:
    token = credentials.credentials
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("id")
        if not user_id:
            raise HTTPException(status_code=401, detail=await t(db_pool, language, CHAT["auth.invalid_token_missing_user_id"]) if db_pool else "Invalid token: missing user id")
        return user_id
    except jwt.PyJWTError as e:
        raise HTTPException(status_code=401, detail=await t(db_pool, language, CHAT["auth.invalid_token_error"], error=str(e)) if db_pool else f"Invalid token: {str(e)}")

# Request/Response models
class ChatMessageResponse(BaseModel):
    id: int
    role: str
    content: str
    createdAt: str

class ChatResponse(BaseModel):
    id: int
    title: str
    messages: List[ChatMessageResponse]
    createdAt: str
    updatedAt: str

class SendMessageRequest(BaseModel):
    connectionId: int
    message: str
    chatId: Optional[int] = None
    model: Optional[str] = None
    # Per-request escalation (AI limits plan, Item 12). Absent means "the resolved
    # value"; present means "this one attempt". Never stored, never remembered.
    timeoutSeconds: Optional[int] = None

class SendMessageResponse(BaseModel):
    chat: ChatResponse

class ChatListResponse(BaseModel):
    chats: List[dict]

class UpdateChatTitleRequest(BaseModel):
    title: str

class GenerateTitleRequest(BaseModel):
    connectionId: int
    userMessage: str


@router.post("/", response_model=SendMessageResponse)
async def send_message(
    request: SendMessageRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    if db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(db_pool, language, CHAT["database.pool_not_initialized"])
        )
    manager = ChatManager(db_pool)
    user_id = await get_user_id_from_token(credentials, db_pool, language)
    try:
        result = await manager.send_message(
            user_id=user_id,
            chat_id=request.chatId,
            connection_id=request.connectionId,
            user_message=request.message,
            model=request.model,
            timeout_override=request.timeoutSeconds,
        )
        messages = [
            ChatMessageResponse(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                createdAt=iso_utc(m["createdAt"])
            )
            for m in result["messages"]
        ]
        return SendMessageResponse(
            chat=ChatResponse(
                id=result["id"],
                title=result["title"],
                messages=messages,
                createdAt=iso_utc(result["createdAt"]),
                updatedAt=iso_utc(result["updatedAt"])
            )
        )
    except ValueError as e:
        error_msg = str(e)
        if error_msg.startswith("connection_error:"):
            error_key = error_msg.replace("connection_error:", "")
            if error_key == "connection.not_found_or_not_accessible":
                detail = await t(db_pool, language, CHAT["chat.connection_not_found"])
            else:
                detail = await t(db_pool, language, CHAT["chat.connection_error"], error=error_key)
            status_code = 400
        elif error_msg == "timeout_out_of_range":
            # The caller asked for a value outside the ceiling. Say which, rather than
            # clamping and letting them believe they got what they asked for.
            detail = await t(db_pool, language, CHAT["chat.timeout_out_of_range"],
                             max_seconds=MAX_TIMEOUT_SECONDS)
            status_code = 400
        elif error_msg.startswith("ai_provider_error:"):
            error_key = error_msg.replace("ai_provider_error:", "")
            detail = await t(db_pool, language, CHAT["chat.ai_provider_error"], error=error_key)
            status_code = 402
            # A timeout is the one failure a retry can fix, and only with more time. The
            # body says so machine-readably; `detail` stays the user-facing sentence.
            # `timeoutSecondsUsed` is what the request actually ran with — the override
            # if one was supplied, else the resolved value — so a retry preset is
            # computed from what happened rather than from a guess.
            if error_key in TIMEOUT_ERRORS:
                # The timeout that failed comes from the error, not from the request: the
                # value in force is resolved from the pair, and the request may carry no
                # override at all. Reading request.timeoutSeconds here would report None
                # for the common case — the defect this comment replaced.
                return JSONResponse(
                    status_code=402,
                    content={
                        "detail": detail,
                        "reason": "timeout",
                        "timeoutSecondsUsed": getattr(e, "timeout_seconds_used", None),
                    },
                )
        else:
            detail = await t(db_pool, language, CHAT["chat.send_failed"], error=error_msg)
            status_code = 400
        raise HTTPException(
            status_code=status_code,
            detail=detail
        )
    except Exception as e:
        logger.error(f"Unexpected error in send_message: {type(e).__name__}: {str(e)}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=await t(db_pool, language, CHAT["chat.internal_error"], error=str(e))
        )


@router.get("/", response_model=ChatListResponse)
async def list_chats(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
    limit: int = 10,
    offset: int = 0
):
    if db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(db_pool, language, CHAT["database.pool_not_initialized"])
        )
    manager = ChatManager(db_pool)
    user_id = await get_user_id_from_token(credentials, db_pool, language)
    try:
        chats = await manager.get_user_chats(user_id, limit, offset)
        return ChatListResponse(chats=chats)
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(db_pool, language, CHAT["chat.list_failed"], error=str(e))
        )


@router.get("/{chat_id}", response_model=ChatResponse)
async def get_chat(
    chat_id: int,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    if db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(db_pool, language, CHAT["database.pool_not_initialized"])
        )
    manager = ChatManager(db_pool)
    user_id = await get_user_id_from_token(credentials, db_pool, language)
    try:
        result = await manager.get_chat(chat_id, user_id)
        messages = [
            ChatMessageResponse(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                createdAt=iso_utc(m["createdAt"])
            )
            for m in result["messages"]
        ]
        return ChatResponse(
            id=result["id"],
            title=result["title"],
            messages=messages,
            createdAt=iso_utc(result["createdAt"]),
            updatedAt=iso_utc(result["updatedAt"])
        )
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=await t(db_pool, language, CHAT["chat.not_found"], id=chat_id)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(db_pool, language, CHAT["chat.get_failed"], error=str(e))
        )


@router.patch("/{chat_id}")
async def update_chat_title(
    chat_id: int,
    request: UpdateChatTitleRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    if db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(db_pool, language, CHAT["database.pool_not_initialized"])
        )
    manager = ChatManager(db_pool)
    user_id = await get_user_id_from_token(credentials, db_pool, language)
    try:
        chat = await manager.update_chat_title(chat_id, user_id, request.title)
        return {
            "success": True,
            "chat": chat,
            "message": await t(db_pool, language, CHAT["chat.title_updated"])
        }
    except ValueError as e:
        raise HTTPException(
            status_code=404,
            detail=await t(db_pool, language, CHAT["chat.not_found_or_not_owned"], id=chat_id)
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(db_pool, language, CHAT["chat.update_failed"], error=str(e))
        )


@router.post("/{chat_id}/generate-title")
async def generate_chat_title(
    chat_id: int,
    request: GenerateTitleRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    if db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(db_pool, language, CHAT["database.pool_not_initialized"])
        )
    manager = ChatManager(db_pool)
    user_id = await get_user_id_from_token(credentials, db_pool, language)
    try:
        result = await manager.generate_chat_title(
            user_id=user_id,
            chat_id=chat_id,
            connection_id=request.connectionId,
            user_message=request.userMessage
        )
        return result
    except ValueError as e:
        raise HTTPException(
            status_code=400,
            detail=await t(db_pool, language, CHAT["chat.generate_title_failed"], error=str(e))
        )
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(db_pool, language, CHAT["chat.internal_error"], error=str(e))
        )


@router.delete("/{chat_id}")
async def delete_chat(
    chat_id: int,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language)
):
    if db_pool is None:
        raise HTTPException(
            status_code=500,
            detail=await t(db_pool, language, CHAT["database.pool_not_initialized"])
        )
    manager = ChatManager(db_pool)
    try:
        user_id = await get_user_id_from_token(credentials, db_pool, language)
        success = await manager.delete_chat(chat_id, user_id)
        if not success:
            raise HTTPException(
                status_code=404,
                detail=await t(db_pool, language, CHAT["chat.not_found_or_not_owned"], id=chat_id)
            )
        return {
            "success": True,
            "message": await t(db_pool, language, CHAT["chat.deleted"], id=chat_id)
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=await t(db_pool, language, CHAT["chat.delete_failed"], error=str(e))
        )