"""
AI Providers Router — P2 Group 3, item 16 (Prisma-removal plan).

Drop-in replacement for the frontend Prisma handler:
  frontend/app/api/ai-providers/route.ts   (GET · PATCH · DELETE)

This is the NON-admin /api/ai-providers surface — distinct from the admin
/api/admin/ai-providers router (item 4). Contract parity:

  - GET: NO admin/example gate — any authenticated user lists the providers
    (ordered by name ASC, 7-field select). The frontend's canViewProviders()
    helper is DEAD CODE (defined, never called).
  - PATCH: checkAdmin gate (isAdmin only — an example user gets 403) ->
    {"error": "Forbidden"}. body {id, enabled}: !id OR typeof enabled !==
    "boolean" -> 400 "Missing id or enabled flag". The body id is used RAW
    (no Number() coercion) — a non-int id hits Prisma validation -> 500
    "Failed to update provider" (a missing provider is now 404
    provider_not_found, item 16).
  - DELETE: checkAdmin gate -> 403 "Forbidden". query id: missing -> 400
    "Missing provider id"; non-digit -> 400 "Invalid provider id"; unknown ->
    404 "Provider not found".

Error shape: BARE strings throughout ({"error": "<string>"}) — the same
divergence from the admin route's coded api.admin.* envelope, tracked in
workbench-documents/development-records/code-quirks.md. Routed through t() (option b): the English fallback
matches the frontend's exact string, so parity holds for English and the
keys become translatable once extracted/imported. The frontend GET has no
try/catch (an unhandled findMany error would surface as a Next.js default
500); the PATCH/DELETE 500s are the explicit catch-all messages. Ghost
sessions: GET -> 200 (no user lookup); PATCH/DELETE -> 403 (checkAdmin finds
no user -> false).

Auth helpers (_auth, _is_admin) are shared from admin.users.py; the pool is
wired via set_db_pool in main.py.
"""

import json
from typing import Any, Optional

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth, _is_admin
from src.routers.translations import ROUTERS
from src.utils.translation import t

router = APIRouter(prefix="/api/ai-providers", tags=["ai-providers"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


_PROVIDER_SELECT = ("id", "code", "name", "isLocal", "requiresApiKey",
                    "defaultEndpoint", "enabled")


async def _t_error(status_code: int, key: str, language: str, **kwargs) -> JSONResponse:
    """Bare-string error routed through t() (option b): the English fallback
    matches the frontend's exact string, so parity holds for English; the key
    is translatable once extracted/imported."""
    message = await t(_db_pool, language, ROUTERS[key], **kwargs)
    return JSONResponse(status_code=status_code, content={"error": message})


def _public(row):
    return {c: row[c] for c in _PROVIDER_SELECT}


def _js_truthy(value) -> bool:
    """JS truthiness: false/0/""/null are falsy; [] and {} are TRUTHY."""
    return not (value is None or value is False or value == "" or value == 0)


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("")
async def list_ai_providers(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(401, "ai_providers.unauthorized", language)

        cols = ", ".join(f'"{c}"' for c in _PROVIDER_SELECT)
        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                f'SELECT {cols} FROM "AIProvider" ORDER BY name ASC'
            )
        return {"providers": [_public(r) for r in rows]}
    except Exception:
        return await _t_error(500, "ai_providers.internal_error", language)


@router.patch("")
async def patch_ai_provider(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(401, "ai_providers.unauthorized", language)
        if not await _is_admin(uid):
            return await _t_error(403, "ai_providers.forbidden", language)

        try:
            body = json.loads(await req.body() or b"")
        except Exception:
            return await _t_error(500, "ai_providers.failed_to_update_provider", language)
        if body is None:
            # Destructuring null throws in the frontend -> 500.
            return await _t_error(500, "ai_providers.failed_to_update_provider", language)
        if not isinstance(body, dict):
            # Destructuring an array/string/number yields all-undefined.
            body = {}

        raw_id = body.get("id")
        enabled = body.get("enabled")

        if not _js_truthy(raw_id) or not isinstance(enabled, bool):
            return await _t_error(400, "ai_providers.missing_id_or_enabled", language)

        # id is used RAW (no coercion): non-int -> Prisma validation -> 500.
        if not isinstance(raw_id, int) or isinstance(raw_id, bool):
            return await _t_error(500, "ai_providers.failed_to_update_provider", language)

        cols = ", ".join(f'"{c}"' for c in _PROVIDER_SELECT)
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f'UPDATE "AIProvider" SET enabled = $1, "updatedAt" = NOW() '
                f'WHERE id = $2 RETURNING {cols}',
                enabled, raw_id,
            )
        if row is None:
            # Prisma P2025 -> record not found -> 404 (item 16).
            return await _t_error(404, "ai_providers.provider_not_found", language)
        return {"provider": _public(row)}
    except Exception:
        return await _t_error(500, "ai_providers.failed_to_update_provider", language)


@router.delete("")
async def delete_ai_provider(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(401, "ai_providers.unauthorized", language)
        if not await _is_admin(uid):
            return await _t_error(403, "ai_providers.forbidden", language)

        raw_id = req.query_params.get("id")
        if not raw_id:
            return await _t_error(400, "ai_providers.missing_provider_id", language)

        if not raw_id.isdigit():
            return await _t_error(400, "ai_providers.invalid_provider_id", language)
        provider_id = int(raw_id)

        async with _db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                'SELECT id FROM "AIProvider" WHERE id = $1', provider_id
            )
            if existing is None:
                return await _t_error(404, "ai_providers.provider_not_found", language)
            await conn.execute('DELETE FROM "AIProvider" WHERE id = $1', provider_id)
        return {"success": True}
    except Exception:
        return await _t_error(500, "ai_providers.failed_to_delete_provider", language)
