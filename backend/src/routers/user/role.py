"""
User Role Router — P2 Group 2, item 8 (Prisma-removal plan).

Drop-in replacement for the frontend Prisma handler:
  frontend/app/api/user/role/route.ts   (GET)

Contract parity:
  - Any authenticated user reads their own role flags: a flat 200 response
    {isAdmin, isGroupAdmin, isExampleUser, userGroup} — no wrapper, no 403
    path (unlike the profile PATCH, examples are not blocked here).
  - 401 api.auth.unauthorized when the token is missing/invalid (the global
    HTTPBearer gate answers no-token requests first — same as items 1-7).
  - A missing user row (deleted session user, stale JWT) -> 404
    api.user.user_not_found — the correct not-found pattern, in contrast to
    the P2025 -> 500 family on the admin update paths.
  - 500 api.user.internal_error on any other failure.

Translation note: all three responses route through t() with USER registry
keys (item 14); the registry carries the api.user.*/api.auth.* namespaces
matching the wire codes (item 35).

Auth helpers (_auth) are shared from admin.users.py; the pool is wired via
set_db_pool in main.py.
"""

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth
from src.routers.user.translations import USER
from src.utils.translation import t

router = APIRouter(prefix="/api/user", tags=["user-role"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ============================================================
# FRONTEND ERROR-CODE CONTRACT (stable API surface — do not rename)
# ============================================================

E_UNAUTHORIZED = "api.auth.unauthorized"
E_USER_NOT_FOUND = "api.user.user_not_found"
E_INTERNAL_ERROR = "api.user.internal_error"

_ROLE_SELECT = ("isAdmin", "isGroupAdmin", "isExampleUser", "userGroup")


async def _error(status: int, code: str, language: str, **kwargs):
    """Coded-envelope error routed through t() (item 14)."""
    message = await t(_db_pool, language, USER[code], **kwargs)
    return JSONResponse(status_code=status, content={"error": code, "message": message})


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/role")
async def get_user_role(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)

        cols = ", ".join(f'"{c}"' for c in _ROLE_SELECT)
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f'SELECT {cols} FROM "User" WHERE id = $1', uid
            )
        if row is None:
            return await _error(404, E_USER_NOT_FOUND, language)
        return {c: row[c] for c in _ROLE_SELECT}
    except Exception:
        return await _error(500, E_INTERNAL_ERROR, language)
