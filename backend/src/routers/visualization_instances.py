"""
Public Visualization Instances Router — P2 Group 7, item 26 (Prisma-removal plan).

Drop-in replacements for the frontend Prisma handlers:
  frontend/app/api/visualization-instances/route.ts            (POST)
  frontend/app/api/visualization-instances/[id]/route.ts       (GET)
  frontend/app/api/visualization-instances/[id]/render/route.ts (GET)

CLEAN VALIDATION (no JS-coercion emulation — see workbench-documents/development-records/code-quirks.md, the
item-9 coercion-defect entry). The frontend's `parseInt(id)` (hex/prefix/
partial-parse quirks) and Prisma's float->Int truncation are data-integrity
defects, not behaviours to recreate. Here:

  - id (path): parsed with strict int() — a non-decimal-integer string is a
    400 invalid_instance_id (never parseInt's "5abc"->5 or "0x1A"->26).
  - visualizationTypeId: JS-falsy -> 400 viz_type_id_required; a truthy
    non-INT -> 500 (Prisma Int rejection, mirrored as validation — no
    float truncation; 2.5 is rejected, not silently stored as 2).
  - outputId: JS-falsy -> null; a truthy non-string -> 500 (Prisma String?
    rejection).
  - parameters: an object merges over the type's defaultParameters
    ({...defaults, ...user}); anything else -> {} (clean — no JS spread of
    a string/array into numeric keys).
  - dataSnapshot: Json? — any JSON value; JS-falsy -> null.

The JS `||`/`!x` TRUTHINESS (falsy = false/0/""/null) is preserved — that is
a boolean test, not type coercion. The observable divergences from the
reference are the intentional ones (strict id parse, strict Int validation).

Contract parity (elsewhere):
  - POST: any authenticated user (session.user.id) -> else 401 "Unauthorized".
    validationTypeId type lookup -> !type -> 400 invalid_viz_type; create
    with outputId||null, parameters = merged defaults+user, dataSnapshot||null,
    generatedImageUrl null. Response {"instance": {...9 fields...}} in the
    select order (no visualizationType field).
  - GET /{id}: own-only (userId scoped) -> else 404 instance_not_found.
    Response adds visualizationType {name, slug, renderer} (or null) LAST.
  - GET /{id}/render: own-only. renderer === "client" ->
    {renderer, type, data, parameters}; generatedImageUrl ->
    {renderer, imageUrl}; else 404 no_rendered_output. A missing type ->
    404 viz_type_not_found.

Error shape: BARE strings throughout ({"error": "<string>"}) — the same
divergence from the admin coded envelope, tracked in workbench-documents/development-records/code-quirks.md.
Routed through t() (option b): English fallback == frontend string; keys
translatable once extracted/imported.

Auth helpers (_auth) shared from admin.users.py; the pool is wired via
set_db_pool in main.py.
"""

import json
from datetime import datetime, timezone
from typing import Any, Dict, Tuple

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth
from src.routers.translations import ROUTERS
from src.utils.translation import t
from src.utils.timestamps import iso_utc

router = APIRouter(prefix="/api/visualization-instances",
                   tags=["visualization-instances"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


_INSTANCE_SELECT = ("id", "userId", "visualizationTypeId", "outputId",
                    "parameters", "dataSnapshot", "generatedImageUrl",
                    "createdAt", "updatedAt")

# Canonical translation keys (keyed by their canonical name — no alias layer).
K_UNAUTHORIZED = "visualization_instances.unauthorized"
K_INTERNAL_ERROR = "visualization_instances.internal_error"
K_VIZ_TYPE_ID_REQUIRED = "visualization_instances.viz_type_id_required"
K_INVALID_VIZ_TYPE = "visualization_instances.invalid_viz_type"
K_INVALID_INSTANCE_ID = "visualization_instances.invalid_instance_id"
K_INSTANCE_NOT_FOUND = "visualization_instances.instance_not_found"
K_VIZ_TYPE_NOT_FOUND = "visualization_instances.viz_type_not_found"
K_NO_RENDERED_OUTPUT = "visualization_instances.no_rendered_output"


def _cols(select: Tuple[str, ...]) -> str:
    return ", ".join(f'"{c}"' for c in select)



def _public_instance(row) -> Dict[str, Any]:
    out: Dict[str, Any] = {}
    for c in _INSTANCE_SELECT:
        v = row[c]
        if isinstance(v, datetime):
            out[c] = iso_utc(v)
        else:
            out[c] = v
    return out




async def _t_error(status_code: int, key: str, language: str, **kwargs) -> JSONResponse:
    """Bare-string error routed through t() (option b)."""
    message = await t(_db_pool, language, ROUTERS[key], **kwargs)
    return JSONResponse(status_code=status_code, content={"error": message})


def _is_falsy(value) -> bool:
    """JS truthiness (a boolean test, NOT type coercion): false/0/""/None are
    falsy; [] and {} are truthy. Mirrors the frontend's `!x` / `||`."""
    return value is None or value is False or value == "" or value == 0


async def _resolve_viz_type(conn, type_id: int, select: Tuple[str, ...]):
    return await conn.fetchrow(
        f'SELECT {", ".join(f"\"{c}\"" for c in select)} '
        f'FROM "VisualizationType" WHERE id = $1',
        type_id,
    )


# ============================================================
# ENDPOINTS
# ============================================================

@router.post("")
async def create_visualization_instance(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(401, K_UNAUTHORIZED, language)

        try:
            body = json.loads(await req.body() or b"")
        except Exception:
            return await _t_error(500, K_INTERNAL_ERROR, language)
        if body is None:
            # Destructuring null throws in the frontend -> 500.
            return await _t_error(500, K_INTERNAL_ERROR, language)
        if not isinstance(body, dict):
            # Destructuring an array/string/number yields all-undefined.
            body = {}

        viz_type_id = body.get("visualizationTypeId")
        if _is_falsy(viz_type_id):
            return await _t_error(400, K_VIZ_TYPE_ID_REQUIRED, language)
        # Prisma Int rejection, mirrored as validation (no float truncation).
        if isinstance(viz_type_id, bool) or not isinstance(viz_type_id, int):
            return await _t_error(500, K_INTERNAL_ERROR, language)

        async with _db_pool.acquire() as conn:
            type_row = await conn.fetchrow(
                'SELECT id, "defaultParameters" FROM "VisualizationType" WHERE id = $1',
                viz_type_id,
            )
        if type_row is None:
            return await _t_error(400, K_INVALID_VIZ_TYPE, language)

        default_params = type_row["defaultParameters"]
        default_params = default_params if isinstance(default_params, dict) else {}

        user_params = body.get("parameters")
        user_params = user_params if isinstance(user_params, dict) else {}
        merged = {**default_params, **user_params}

        output_id = body.get("outputId")
        if _is_falsy(output_id):
            output_id = None
        elif not isinstance(output_id, str):
            # Prisma String? rejects a truthy non-string -> 500.
            return await _t_error(500, K_INTERNAL_ERROR, language)

        data_snapshot = body.get("dataSnapshot")
        if _is_falsy(data_snapshot):
            data_snapshot = None

        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f"""
                INSERT INTO "VisualizationInstance" (
                    "userId", "visualizationTypeId", "outputId", parameters,
                    "dataSnapshot", "generatedImageUrl", "createdAt", "updatedAt"
                ) VALUES ($1, $2, $3, $4, $5, NULL, NOW(), NOW())
                RETURNING {_cols(_INSTANCE_SELECT)}
                """,
                uid, viz_type_id, output_id,
                merged,
                data_snapshot if data_snapshot is not None else None,
            )
        return {"instance": _public_instance(row)}
    except Exception:
        return await _t_error(500, K_INTERNAL_ERROR, language)


@router.get("/{instance_id}")
async def get_visualization_instance(
    instance_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(401, K_UNAUTHORIZED, language)

        try:
            iid = int(instance_id)
        except ValueError:
            return await _t_error(400, K_INVALID_INSTANCE_ID, language)

        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f'SELECT {_cols(_INSTANCE_SELECT)} FROM "VisualizationInstance" '
                f'WHERE id = $1 AND "userId" = $2',
                iid, uid,
            )
        if row is None:
            return await _t_error(404, K_INSTANCE_NOT_FOUND, language)

        async with _db_pool.acquire() as conn:
            vt = await _resolve_viz_type(conn, row["visualizationTypeId"],
                                         ("name", "slug", "renderer"))

        instance = _public_instance(row)
        instance["visualizationType"] = (
            {"name": vt["name"], "slug": vt["slug"], "renderer": vt["renderer"]}
            if vt else None
        )
        return {"instance": instance}
    except Exception:
        return await _t_error(500, K_INTERNAL_ERROR, language)


@router.get("/{instance_id}/render")
async def render_visualization_instance(
    instance_id: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(401, K_UNAUTHORIZED, language)

        try:
            iid = int(instance_id)
        except ValueError:
            return await _t_error(400, K_INVALID_INSTANCE_ID, language)

        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT id, "visualizationTypeId", parameters, "dataSnapshot", '
                '"generatedImageUrl" FROM "VisualizationInstance" '
                'WHERE id = $1 AND "userId" = $2',
                iid, uid,
            )
        if row is None:
            return await _t_error(404, K_INSTANCE_NOT_FOUND, language)

        async with _db_pool.acquire() as conn:
            vt = await _resolve_viz_type(conn, row["visualizationTypeId"],
                                         ("slug", "renderer"))
        if vt is None:
            return await _t_error(404, K_VIZ_TYPE_NOT_FOUND, language)

        if vt["renderer"] == "client":
            return {
                "renderer": "client",
                "type": vt["slug"],
                "data": row["dataSnapshot"],
                "parameters": row["parameters"],
            }

        if row["generatedImageUrl"]:
            return {"renderer": "server", "imageUrl": row["generatedImageUrl"]}

        return await _t_error(404, K_NO_RENDERED_OUTPUT, language)
    except Exception:
        return await _t_error(500, K_INTERNAL_ERROR, language)
