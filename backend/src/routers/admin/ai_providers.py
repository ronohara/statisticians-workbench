"""
Admin AI Providers Router — P2 Group 1, item 4 (Prisma-removal plan).

Drop-in replacement for the frontend Prisma handler:
  frontend/app/api/admin/ai-providers/route.ts   (GET · PATCH · DELETE)

Contract parity:
  - GET: canViewProviders (full admin OR example user) -> {providers: [...]}
    ordered by name asc, 7-field select. 403 only_full_admin otherwise.
  - PATCH: full-admin gate (checkAdmin = isAdmin only — example users pass,
    mirroring the frontend), body {id, enabled} with strict boolean
    validation -> 400 missing_fields; a non-int id -> 400 invalid_id (item
    17); a missing provider -> 404 provider_not_found (item 16).
  - DELETE: full-admin gate, query id; missing -> 400 missing_id;
    non-decimal id -> 400 invalid_id (item 17); unknown id -> 404
    provider_not_found.
  - Coded error envelope throughout (api.admin.*); codes double as
    Translation-table keys.

Auth helpers (_auth, _is_admin, _is_example, _error) are shared from
admin.users.py; the pool is wired via set_db_pool in main.py.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth, _error, _is_admin, _is_example

router = APIRouter(prefix="/api/admin", tags=["admin-ai-providers"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ============================================================
# FRONTEND ERROR-CODE CONTRACT (stable API surface — do not rename)
# ============================================================

E_UNAUTHORIZED = "api.auth.unauthorized"
E_ONLY_FULL_ADMIN = "api.admin.only_full_admin"
E_MISSING_FIELDS = "api.admin.missing_fields"
E_MISSING_ID = "api.admin.missing_id"
E_INVALID_ID = "api.admin.invalid_id"
E_PROVIDER_NOT_FOUND = "api.admin.provider_not_found"
E_PROVIDERS_LOAD_ERROR = "api.admin.providers_load_error"
E_PROVIDER_UPDATE_ERROR = "api.admin.provider_update_error"
E_PROVIDER_DELETE_ERROR = "api.admin.provider_delete_error"

_PROVIDER_SELECT = ("id", "code", "name", "isLocal", "requiresApiKey",
                    "defaultEndpoint", "enabled")


class ProviderPatchBody(BaseModel):
    id: Optional[Any] = None
    enabled: Optional[Any] = None


# ============================================================
# HELPERS
# ============================================================

async def _fetch_provider(provider_id: int):
    cols = ", ".join(f'"{c}"' for c in _PROVIDER_SELECT)
    async with _db_pool.acquire() as conn:
        return await conn.fetchrow(
            f'SELECT {cols} FROM "AIProvider" WHERE id = $1', provider_id
        )


def _public(row):
    return {c: row[c] for c in _PROVIDER_SELECT}


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/ai-providers")
async def list_ai_providers(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if not await _is_admin(uid) and not await _is_example(uid):
            return await _error(403, E_ONLY_FULL_ADMIN, language)

        cols = ", ".join(f'"{c}"' for c in _PROVIDER_SELECT)
        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                f'SELECT {cols} FROM "AIProvider" ORDER BY name ASC'
            )
        return {"providers": [_public(r) for r in rows]}
    except Exception:
        return await _error(500, E_PROVIDERS_LOAD_ERROR, language)


@router.patch("/ai-providers")
async def patch_ai_provider(
    body: ProviderPatchBody,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if not await _is_admin(uid):
            return await _error(403, E_ONLY_FULL_ADMIN, language)

        if not body.id or not isinstance(body.enabled, bool):
            return await _error(400, E_MISSING_FIELDS, language)

        if not isinstance(body.id, int) or isinstance(body.id, bool):
            # Strict Int body id -> 400 (item 17).
            return await _error(400, E_INVALID_ID, language)
        provider_id = body.id

        cols = ", ".join(f'"{c}"' for c in _PROVIDER_SELECT)
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f'UPDATE "AIProvider" SET enabled = $1, "updatedAt" = NOW() '
                f'WHERE id = $2 RETURNING {cols}',
                body.enabled, provider_id,
            )
        if row is None:
            # Prisma P2025 -> record not found -> 404 (item 16).
            return await _error(404, E_PROVIDER_NOT_FOUND, language)
        return {"provider": _public(row)}
    except Exception:
        return await _error(500, E_PROVIDER_UPDATE_ERROR, language)


@router.delete("/ai-providers")
async def delete_ai_provider(
    req: Request,
    id: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if not await _is_admin(uid):
            return await _error(403, E_ONLY_FULL_ADMIN, language)

        if not id:
            return await _error(400, E_MISSING_ID, language)

        if not id.isdigit():
            # Strict Int query id -> 400 (item 17).
            return await _error(400, E_INVALID_ID, language)
        provider_id = int(id)

        existing = await _fetch_provider(provider_id)
        if existing is None:
            return await _error(404, E_PROVIDER_NOT_FOUND, language)

        async with _db_pool.acquire() as conn:
            await conn.execute('DELETE FROM "AIProvider" WHERE id = $1', provider_id)
        return {"success": True}
    except Exception:
        return await _error(500, E_PROVIDER_DELETE_ERROR, language)
