"""
Admin Visualization Types Router — P2 Group 1, item 6 (Prisma-removal plan).

Drop-in replacement for the frontend Prisma handlers:
  frontend/app/api/admin/visualization-types/route.ts      (GET · POST)
  frontend/app/api/admin/visualization-types/[id]/route.ts (PATCH · DELETE)

Contract parity:
  - GET: full-admin gate (checkAdmin = isAdmin only — no example bypass;
    example fixtures pass via the data quirk isAdmin=true), 11-field select,
    ordered by name asc.
  - POST: same gate; name/slug are required non-empty strings (absent/empty ->
    400 missing_fields, non-string -> 400 invalid_viz_type_field); slug
    collision -> 409 slug_exists; description is a nullable string, renderer
    defaults to "client" only when absent/null, and the JSON fields default to
    {} only when absent/null — anything else is stored as-is (explicit
    validation, no JS || truthiness — item 23); null/non-boolean enabled ->
    Prisma validation throw -> 500 viz_type_create_error.
  - PATCH: path ids strict-validated as decimal-digit strings -> 400
    invalid_id (item 11); truthy slug re-checked for uniqueness excluding self ->
    409 slug_exists; only body-present fields update; explicit field
    validation (item 12) — String fields reject null/non-strings and enabled
    rejects non-booleans with 400 invalid_viz_type_field; description and the
    Json fields (inputSchema/parameterSchema/defaultParameters) are nullable
    and accept null; a missing row (P2025) -> 500 viz_type_update_error; an
    empty update returns the row unchanged (no updatedAt bump), like Prisma
    data {}.
  - DELETE: strict decimal-digit id gate (item 11); FK RESTRICT on
    visualizationTypeId -> 409 instance_in_use (ForeignKeyViolation); a missing
    row (P2025) -> 404 viz_type_not_found; success -> {success: true}.
  - Coded error envelope throughout (api.admin.*); codes double as
    Translation-table keys. Every viz code already has an en.yaml /
    en-backend.yaml pair on both sides — no new keys, no translation run.

Auth helpers (_auth, _is_admin, _error) are shared from admin.users.py;
the pool is wired via set_db_pool in main.py.
"""

import json
from datetime import datetime
from typing import Any, Dict, List, Optional

import asyncpg
from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth, _error, _is_admin
from src.utils.timestamps import iso_utc

router = APIRouter(prefix="/api/admin", tags=["admin-visualization-types"])
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
E_SLUG_EXISTS = "api.admin.slug_exists"
E_INVALID_ID = "api.admin.invalid_id"
E_INVALID_FIELD = "api.admin.invalid_viz_type_field"
E_INSTANCE_IN_USE = "api.admin.instance_in_use"
E_VIZ_TYPES_LOAD_ERROR = "api.admin.viz_types_load_error"
E_VIZ_TYPE_CREATE_ERROR = "api.admin.viz_type_create_error"
E_VIZ_TYPE_UPDATE_ERROR = "api.admin.viz_type_update_error"
E_VIZ_TYPE_DELETE_ERROR = "api.admin.viz_type_delete_error"
E_VIZ_TYPE_NOT_FOUND = "api.admin.viz_type_not_found"

# Prisma `select`, mirrored exactly.
_VT_SELECT = ("id", "name", "slug", "description", "renderer", "inputSchema",
              "parameterSchema", "defaultParameters", "enabled", "createdAt",
              "updatedAt")


def _cols() -> str:
    return ", ".join(f'"{c}"' for c in _VT_SELECT)


def _public(row) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for c in _VT_SELECT:
        v = row[c]
        if isinstance(v, datetime):
            out[c] = iso_utc(v)
        else:
            out[c] = v
    return out




# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/visualization-types")
async def list_visualization_types(
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

        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                f'SELECT {_cols()} FROM "VisualizationType" ORDER BY name ASC'
            )
        return {"types": [_public(r) for r in rows]}
    except Exception:
        return await _error(500, E_VIZ_TYPES_LOAD_ERROR, language)


@router.post("/visualization-types")
async def create_visualization_type(
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

        # req.json() throws on an empty/malformed body -> caught -> 500.
        try:
            body = json.loads(await req.body() or b"")
        except Exception:
            return await _error(500, E_VIZ_TYPE_CREATE_ERROR, language)
        if body is None:
            # Destructuring null throws in the frontend -> 500.
            return await _error(500, E_VIZ_TYPE_CREATE_ERROR, language)
        if not isinstance(body, dict):
            # Destructuring an array/string/number yields all-undefined.
            body = {}

        name = body.get("name")
        slug = body.get("slug")

        # Required non-empty strings (explicit validation — item 23).
        if name is None or slug is None:
            return await _error(400, E_MISSING_FIELDS, language)
        if not isinstance(name, str) or not isinstance(slug, str):
            return await _error(400, E_INVALID_FIELD, language)
        if not name or not slug:
            # Empty strings are falsy in the frontend's !name || !slug gate.
            return await _error(400, E_MISSING_FIELDS, language)

        async with _db_pool.acquire() as conn:
            exists = await conn.fetchval(
                'SELECT 1 FROM "VisualizationType" WHERE slug = $1', slug
            )
        if exists:
            return await _error(409, E_SLUG_EXISTS, language)

        # description — nullable string (default null; no JS || truthiness).
        description = body.get("description")
        if description is not None and not isinstance(description, str):
            return await _error(400, E_INVALID_FIELD, language)

        # renderer — string, defaults to "client" only when absent/null.
        renderer = body.get("renderer")
        if renderer is None:
            renderer = "client"
        elif not isinstance(renderer, str):
            return await _error(400, E_INVALID_FIELD, language)

        # JSON fields — default {} only when absent/null; store anything else as-is.
        input_schema = body.get("inputSchema")
        parameter_schema = body.get("parameterSchema")
        default_parameters = body.get("defaultParameters")
        input_schema = {} if input_schema is None else input_schema
        parameter_schema = {} if parameter_schema is None else parameter_schema
        default_parameters = {} if default_parameters is None else default_parameters
        if "enabled" in body:
            enabled = body["enabled"]
            if not isinstance(enabled, bool):
                # Prisma Boolean field: null/non-boolean -> validation throw.
                return await _error(500, E_VIZ_TYPE_CREATE_ERROR, language)
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
                RETURNING {_cols()}
                """,
                name, slug, description, renderer,
                input_schema, parameter_schema,
                default_parameters, enabled,
            )
        return {"type": _public(row)}
    except Exception:
        return await _error(500, E_VIZ_TYPE_CREATE_ERROR, language)


@router.patch("/visualization-types/{type_id}")
async def patch_visualization_type(
    type_id: str,
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

        if not type_id.isdigit():
            return await _error(400, E_INVALID_ID, language)
        tid = int(type_id)

        try:
            body = json.loads(await req.body() or b"")
        except Exception:
            return await _error(500, E_VIZ_TYPE_UPDATE_ERROR, language)
        if body is None:
            return await _error(500, E_VIZ_TYPE_UPDATE_ERROR, language)
        if not isinstance(body, dict):
            body = {}

        # Truthy slug re-checked for uniqueness, excluding self.
        if body.get("slug"):
            async with _db_pool.acquire() as conn:
                exists = await conn.fetchval(
                    'SELECT 1 FROM "VisualizationType" WHERE slug = $1 AND id != $2',
                    body["slug"], tid,
                )
            if exists:
                return await _error(409, E_SLUG_EXISTS, language)

        update: Dict[str, Any] = {}
        # Explicit field validation (item 12): declare the contract rather
        # than mirror Prisma's runtime coercion. String/Boolean fields reject
        # null/non-matching types with 400; Json fields stay nullable.
        for col in ("name", "slug", "renderer"):
            if col in body:
                if body[col] is None or not isinstance(body[col], str):
                    return await _error(400, E_INVALID_FIELD, language)
                update[col] = body[col]
        if "description" in body:
            if body["description"] is not None and not isinstance(body["description"], str):
                return await _error(400, E_INVALID_FIELD, language)
            update["description"] = body["description"]  # nullable — null OK
        if "enabled" in body:
            if not isinstance(body["enabled"], bool):
                return await _error(400, E_INVALID_FIELD, language)
            update["enabled"] = body["enabled"]
        # Json fields: nullable — any JSON value (including null) stored as-is.
        for col in ("inputSchema", "parameterSchema", "defaultParameters"):
            if col in body:
                update[col] = body[col]

        async with _db_pool.acquire() as conn:
            if update:
                sets = ", ".join(f'"{c}" = ${i + 1}' for i, c in enumerate(update))
                values = list(update.values())
                row = await conn.fetchrow(
                    f'UPDATE "VisualizationType" SET {sets}, "updatedAt" = NOW() '
                    f'WHERE id = ${len(values) + 1} RETURNING {_cols()}',
                    *values, tid,
                )
            else:
                # Prisma data {} — no-op update returns the row unchanged.
                row = await conn.fetchrow(
                    f'SELECT {_cols()} FROM "VisualizationType" WHERE id = $1', tid
                )
        if row is None:
            # Prisma P2025 -> record not found -> 404 (item 16).
            return await _error(404, E_VIZ_TYPE_NOT_FOUND, language)
        return {"type": _public(row)}
    except Exception:
        return await _error(500, E_VIZ_TYPE_UPDATE_ERROR, language)


@router.delete("/visualization-types/{type_id}")
async def delete_visualization_type(
    type_id: str,
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

        if not type_id.isdigit():
            return await _error(400, E_INVALID_ID, language)
        tid = int(type_id)

        async with _db_pool.acquire() as conn:
            try:
                deleted = await conn.fetchval(
                    'DELETE FROM "VisualizationType" WHERE id = $1 RETURNING id', tid
                )
            except asyncpg.exceptions.ForeignKeyViolationError:
                # FK RESTRICT: one or more instances still reference this type.
                return await _error(409, E_INSTANCE_IN_USE, language)
        if deleted is None:
            # Prisma P2025 -> record not found -> 404 (item 16).
            return await _error(404, E_VIZ_TYPE_NOT_FOUND, language)
        return {"success": True}
    except Exception:
        return await _error(500, E_VIZ_TYPE_DELETE_ERROR, language)
