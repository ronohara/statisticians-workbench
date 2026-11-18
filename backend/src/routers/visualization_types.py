"""
Public Visualization Types Router — P2 Group 7, item 25 (Prisma-removal plan).

Drop-in replacements for the frontend Prisma handlers:
  frontend/app/api/visualization-types/route.ts        (GET · POST)
  frontend/app/api/visualization-types/[slug]/route.ts (GET)

This is the NON-admin /api/visualization-types surface — distinct from the
admin /api/admin/visualization-types router (item 6). Contract parity:

  - GET (list): canViewTypes gate = any authenticated user (session.user.id
    exists, NO user lookup — a ghost session passes) -> else 403 "Forbidden".
    11-field select ordered by name ASC; response {"types": [...]} with the
    select order (renderer 5th).
  - POST: checkAdmin gate (isAdmin only — an example user gets 403) -> else
    403 "Forbidden". req.json()/destructure throw (empty, malformed, or null
    body) -> 500 "Internal server error"; a JSON non-object -> 400. !name ||
    !slug -> 400 "Name and slug are required"; slug collision -> 409 "Slug
    already exists". Create defaults mirror the frontend's JS || semantics
    (NOT Python truthiness — [] and {} are TRUTHY in JS): description||null,
    renderer||"client", inputSchema/parameterSchema/defaultParameters||{},
    enabled !== undefined ? enabled : true. A null/non-boolean enabled or a
    truthy non-String name/description/renderer -> Prisma validation throw ->
    500. The create response field order is the Prisma SCHEMA order (renderer
    8th, after defaultParameters — unlike the list select).
  - GET /{slug}: NO auth in the handler (the layer-2 proxy gates — /api/
    visualization-types is not in publicPaths, so an unauthenticated request
    redirects to /login before reaching the handler; a ghost session still
    gets 200). 8-field select (renderer LAST); missing -> 404 "Visualization
    type not found"; DB failure -> 500.

Error shape: BARE strings throughout ({"error": "<string>"}) — the same
divergence from the admin route's coded api.admin.* envelope, tracked in
workbench-documents/development-records/code-quirks.md. Routed through t() (option b): the English fallback
matches the frontend's exact string, so parity holds for English and the
keys become translatable once extracted/imported.

Auth helpers (_auth, _is_admin) are shared from admin.users.py; the pool is
wired via set_db_pool in main.py.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth, _is_admin
from src.routers.translations import ROUTERS
from src.utils.translation import t
from src.utils.timestamps import iso_utc

router = APIRouter(prefix="/api/visualization-types", tags=["visualization-types"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# Prisma `select` orders, mirrored exactly (order is part of the wire contract).
_VT_LIST_SELECT = ("id", "name", "slug", "description", "renderer",
                   "inputSchema", "parameterSchema", "defaultParameters",
                   "enabled", "createdAt", "updatedAt")
_VT_CREATE_SELECT = ("id", "name", "slug", "description", "inputSchema",
                     "parameterSchema", "defaultParameters", "renderer",
                     "enabled", "createdAt", "updatedAt")
_VT_SLUG_SELECT = ("id", "name", "slug", "description", "inputSchema",
                   "parameterSchema", "defaultParameters", "renderer")

# Canonical translation keys (keyed by their canonical name — no alias layer).
K_FORBIDDEN = "visualization_types.forbidden"
K_INTERNAL_ERROR = "visualization_types.internal_error"
K_NAME_SLUG_REQUIRED = "visualization_types.name_and_slug_required"
K_SLUG_EXISTS = "visualization_types.slug_already_exists"
K_TYPE_NOT_FOUND = "visualization_types.type_not_found"


def _cols(select: Tuple[str, ...]) -> str:
    return ", ".join(f'"{c}"' for c in select)



def _public(row, select: Tuple[str, ...]) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for c in select:
        v = row[c]
        if isinstance(v, datetime):
            out[c] = iso_utc(v)
        else:
            out[c] = v
    return out


def _js_truthy(value) -> bool:
    """JS truthiness: false/0/""/null/undefined are falsy; [] and {} are
    TRUTHY (unlike Python). The create defaults use JS `||`, so this must not
    be swapped for Python truthiness."""
    return not (value is None or value is False or value == "" or value == 0)




async def _t_error(status_code: int, key: str, language: str, **kwargs) -> JSONResponse:
    """Bare-string error routed through t() (option b): the English fallback
    matches the frontend's exact string, so parity holds for English; the key
    is translatable once extracted/imported."""
    message = await t(_db_pool, language, ROUTERS[key], **kwargs)
    return JSONResponse(status_code=status_code, content={"error": message})


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("")
async def list_visualization_types(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        # canViewTypes = !!session?.user?.id — no user lookup (ghost passes).
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(403, K_FORBIDDEN, language)

        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                f'SELECT {_cols(_VT_LIST_SELECT)} FROM "VisualizationType" '
                f'ORDER BY name ASC'
            )
        return {"types": [_public(r, _VT_LIST_SELECT) for r in rows]}
    except Exception:
        return await _t_error(500, K_INTERNAL_ERROR, language)


@router.post("")
async def create_visualization_type(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(403, K_FORBIDDEN, language)
        if not await _is_admin(uid):
            return await _t_error(403, K_FORBIDDEN, language)

        # req.json() throws on an empty/malformed body -> caught -> 500.
        try:
            body = json.loads(await req.body() or b"")
        except Exception:
            return await _t_error(500, K_INTERNAL_ERROR, language)
        if body is None:
            # Destructuring null throws in the frontend -> 500.
            return await _t_error(500, K_INTERNAL_ERROR, language)
        if not isinstance(body, dict):
            # Destructuring an array/string/number yields all-undefined -> 400.
            return await _t_error(400, K_NAME_SLUG_REQUIRED, language)

        name = body.get("name")
        slug = body.get("slug")
        if not _js_truthy(name) or not _js_truthy(slug):
            return await _t_error(400, K_NAME_SLUG_REQUIRED, language)

        # findUnique({where: {slug}}) — a non-String slug is a Prisma type
        # validation throw -> 500.
        if not isinstance(slug, str):
            return await _t_error(500, K_INTERNAL_ERROR, language)

        async with _db_pool.acquire() as conn:
            exists = await conn.fetchval(
                'SELECT 1 FROM "VisualizationType" WHERE slug = $1', slug
            )
        if exists:
            return await _t_error(409, K_SLUG_EXISTS, language)

        # name is a required String — a truthy non-String is a Prisma throw.
        if not isinstance(name, str):
            return await _t_error(500, K_INTERNAL_ERROR, language)

        description = body.get("description")
        description = description if _js_truthy(description) else None
        if description is not None and not isinstance(description, str):
            # Prisma String? field: truthy non-String -> validation throw.
            return await _t_error(500, K_INTERNAL_ERROR, language)

        renderer = body.get("renderer")
        renderer = renderer if _js_truthy(renderer) else "client"
        if not isinstance(renderer, str):
            return await _t_error(500, K_INTERNAL_ERROR, language)

        input_schema = body.get("inputSchema")
        input_schema = input_schema if _js_truthy(input_schema) else {}
        parameter_schema = body.get("parameterSchema")
        parameter_schema = parameter_schema if _js_truthy(parameter_schema) else {}
        default_parameters = body.get("defaultParameters")
        default_parameters = default_parameters if _js_truthy(default_parameters) else {}

        if "enabled" in body:
            enabled = body["enabled"]
            if not isinstance(enabled, bool):
                # Prisma Boolean field: null/non-boolean -> validation throw.
                return await _t_error(500, K_INTERNAL_ERROR, language)
        else:
            enabled = True

        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                INSERT INTO "VisualizationType" (
                    name, slug, description, renderer, "inputSchema",
                    "parameterSchema", "defaultParameters", enabled,
                    "createdAt", "updatedAt"
                ) VALUES ($1, $2, $3, $4, $5, $6, $7, $8, NOW(), NOW())
                RETURNING {_cols(_VT_CREATE_SELECT)}
                """,
                name, slug, description, renderer,
                input_schema, parameter_schema,
                default_parameters, enabled,
            )
        return {"type": _public(row, _VT_CREATE_SELECT)}
    except Exception:
        return await _t_error(500, K_INTERNAL_ERROR, language)


@router.get("/{slug}")
async def get_visualization_type(
    slug: str,
    req: Request,
    language: str = Depends(get_current_language),
):
    # No auth in the handler (the proxy gates). No user lookup — a ghost
    # session still receives the type, matching the frontend.
    try:
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f'SELECT {_cols(_VT_SLUG_SELECT)} FROM "VisualizationType" '
                f'WHERE slug = $1',
                slug,
            )
        if row is None:
            return await _t_error(404, K_TYPE_NOT_FOUND, language)
        return {"type": _public(row, _VT_SLUG_SELECT)}
    except Exception:
        return await _t_error(500, K_INTERNAL_ERROR, language)
