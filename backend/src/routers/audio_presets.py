"""
Audio Presets API – Per-user audio settings for speech output.
GET  /api/user/audio-presets/{chatType}  – load settings
POST /api/user/audio-presets/{chatType}  – save settings
"""

import os
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel
import asyncpg

from src.routers.datasets.crud import get_user_id_from_token, get_current_language
from src.utils.translation import t
from .translations import ROUTERS

router = APIRouter(prefix="/api/user/audio-presets", tags=["audio-presets"])
security = HTTPBearer()

_db_pool: Optional[asyncpg.Pool] = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


class AudioPresetRequest(BaseModel):
    voiceName: Optional[str] = None
    speed: float = 1.0
    pitch: float = 1.0
    volume: Optional[float] = None
    micVolume: Optional[float] = None
    micMuted: Optional[bool] = None
    speakerMuted: Optional[bool] = None


class AudioPresetResponse(BaseModel):
    voiceName: Optional[str] = None
    speed: float = 1.0
    pitch: float = 1.0
    volume: float = 1.0
    micVolume: float = 1.0
    micMuted: bool = False
    speakerMuted: bool = False


@router.get("/{chatType}", response_model=AudioPresetResponse)
async def get_audio_preset(
    chatType: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Get audio settings for the current user and chat type."""
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, ROUTERS["database.pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials)

    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            """
            SELECT "voiceName", speed, pitch, volume, "micVolume", "micMuted", "speakerMuted"
            FROM user_audio_presets
            WHERE "userId" = $1 AND "chatType" = $2
            """,
            user_id, chatType,
        )

    if row is None:
        return AudioPresetResponse()

    return AudioPresetResponse(
        voiceName=row["voiceName"],
        speed=float(row["speed"]),
        pitch=float(row["pitch"]),
        volume=float(row["volume"]) if row["volume"] is not None else 1.0,
        micVolume=float(row["micVolume"]) if row["micVolume"] is not None else 1.0,
        micMuted=bool(row["micMuted"]),
        speakerMuted=bool(row["speakerMuted"]),
    )


@router.post("/{chatType}", response_model=AudioPresetResponse)
async def save_audio_preset(
    chatType: str,
    body: AudioPresetRequest,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Save audio settings for the current user and chat type."""
    if _db_pool is None:
        raise HTTPException(status_code=500, detail=await t(_db_pool, language, ROUTERS["database.pool_not_initialized"]))

    user_id = await get_user_id_from_token(credentials)

    # Validate chatType
    valid_types = ("general", "dataclean", "recipe", "database")
    if chatType not in valid_types:
        raise HTTPException(
            status_code=400,
            detail=await t(_db_pool, language, ROUTERS["audio_presets.invalid_chat_type"], chat_type=chatType, valid_types=", ".join(valid_types)),
        )

    # Validate ranges
    speed = max(0.5, min(2.0, body.speed))
    pitch = max(0.5, min(2.0, body.pitch))

    async with _db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO user_audio_presets
                ("userId", "chatType", "voiceName", speed, pitch, volume, "micVolume", "micMuted", "speakerMuted", "updatedAt")
            VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW())
            ON CONFLICT ("userId", "chatType")
            DO UPDATE SET
                "voiceName" = $3, speed = $4, pitch = $5,
                volume = $6, "micVolume" = $7,
                "micMuted" = $8, "speakerMuted" = $9,
                "updatedAt" = NOW()
            """,
            user_id, chatType, body.voiceName, speed, pitch,
            getattr(body, "volume", 1.0),
            getattr(body, "micVolume", 1.0),
            getattr(body, "micMuted", False),
            getattr(body, "speakerMuted", False),
        )

    return AudioPresetResponse(voiceName=body.voiceName, speed=speed, pitch=pitch)
