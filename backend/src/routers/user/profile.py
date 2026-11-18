"""
User Profile Router — P2 Group 2, item 7 (Prisma-removal plan).

Drop-in replacement for the frontend Prisma handler:
  frontend/app/api/user/profile/route.ts   (PATCH)

Contract parity:
  - Any authenticated user may rename themselves; example users are blocked
    (isExampleUser flag check, BEFORE the body is read).
  - 401 api.auth.unauthorized when the token is missing/invalid (the global
    HTTPBearer gate answers no-token requests first — same as items 1-6).
  - 400 api.profile.name_required when name is JS-falsy (false, 0, "", null)
    or trims to empty; the stored value is name.trim().
  - JS truthiness quirks mirrored: [] and {} are truthy, so name=[], name={},
    name=true -> name.trim is not a function -> TypeError -> 500
    update_failed (NOT 400).
  - P2025 (user row gone) -> 500 update_failed.
  - Success -> {success: true} (no user object).

Translation note: all responses route through t() with USER registry
keys (item 14); api.profile.* pairs added and example_blocked namespace
reconciled to api.user.* (item 35).

Auth helpers (_auth, _is_example) are shared from admin.users.py; the pool
is wired via set_db_pool in main.py.
"""

import json
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth, _is_example
from src.routers.user.translations import USER
from src.utils.translation import t

router = APIRouter(prefix="/api/user", tags=["user-profile"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ============================================================
# FRONTEND ERROR-CODE CONTRACT (stable API surface — do not rename)
# ============================================================

E_UNAUTHORIZED = "api.auth.unauthorized"
E_EXAMPLE_BLOCKED = "api.user.example_blocked"
E_NAME_REQUIRED = "api.profile.name_required"
E_UPDATE_FAILED = "api.profile.update_failed"
E_INVALID_NAME = "api.profile.invalid_name"
E_FETCH_FAILED = "api.profile.fetch_failed"
E_USER_NOT_FOUND = "api.user.user_not_found"


async def _error(status: int, code: str, language: str, **kwargs):
    """Coded-envelope error routed through t() (item 14)."""
    message = await t(_db_pool, language, USER[code], **kwargs)
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def _js_falsy(value) -> bool:
    """JS falsiness for JSON values: false, 0, "", null (no undefined/NaN on
    the wire). [] and {} are TRUTHY in JS — callers must let those fall
    through to the .trim TypeError path."""
    return value is None or value is False or value == "" or value == 0


# ============================================================
# ENDPOINTS
# ============================================================

@router.patch("/profile")
async def patch_profile(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)

        # Example check comes BEFORE the body read, mirroring the frontend.
        if await _is_example(uid):
            return await _error(403, E_EXAMPLE_BLOCKED, language)

        # req.json() throws on an empty/malformed body -> caught -> 500.
        try:
            body = json.loads(await req.body() or b"")
        except Exception:
            return await _error(500, E_UPDATE_FAILED, language)
        if body is None:
            # Destructuring null throws in the frontend -> 500.
            return await _error(500, E_UPDATE_FAILED, language)
        if not isinstance(body, dict):
            # Destructuring an array/string/number yields all-undefined.
            body = {}

        name = body.get("name")
        if _js_falsy(name):
            return await _error(400, E_NAME_REQUIRED, language)
        if not isinstance(name, str):
            # Clean validation (was the name.trim prototype assumption -> 500):
            # a truthy non-string name ([]/{} /true/numbers) -> 400.
            return await _error(400, E_INVALID_NAME, language)
        trimmed = name.strip()
        if trimmed == "":
            return await _error(400, E_NAME_REQUIRED, language)

        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'UPDATE "User" SET name = $1, "updatedAt" = NOW() '
                'WHERE id = $2 RETURNING id',
                trimmed, uid,
            )
        if row is None:
            # Prisma P2025 -> record not found -> 404 (item 16).
            return await _error(404, E_USER_NOT_FOUND, language)
        return {"success": True}
    except Exception:
        return await _error(500, E_UPDATE_FAILED, language)


@router.get("/profile")
async def get_profile(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Current user's name/email (for the NextAuth session refresh)."""
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT name, email FROM "User" WHERE id = $1', uid
            )
        if row is None:
            # Stale session for a deleted user — treat as unauthenticated.
            return await _error(401, E_UNAUTHORIZED, language)
        return {"name": row["name"], "email": row["email"]}
    except Exception:
        return await _error(500, E_FETCH_FAILED, language)
