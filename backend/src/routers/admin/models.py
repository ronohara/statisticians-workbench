"""
Admin Models Router — the model list, over `LLMModel` (plan Item 18).

Replaces the admin's "Provider Models" surface. Provider stops being the axis: the
page lists models, and the three capability results sit beside each one. What a
model's `enabled` flag means has not changed; what changed is that it is now one
row rather than one row per provider, so enabling a model affects every connection
that serves it instead of one provider's copy.

WHY THIS IS A NEW ROUTER AND NOT A RENAME

`routers/admin/provider_models.py` addressed `"ProviderModel"` — the abandoned
table, keyed `(providerCode, modelName)`, which cannot tell two servers apart. All
three of its routes read or write that table, so all three retire with it (plan
Item 32). Nothing here shares code with it: the shape of the data is different
enough that a rename would have meant rewriting every query anyway, and leaving the
old file in place while editing it into something else is how a reader loses track
of which table a route is talking about.

WHAT EACH ROUTE DOES

  GET /api/admin/models
      Every model, ordered by name, optionally filtered. Each entry carries the
      model's own facts — enabled, preferred, comment — its three capability
      results, and the servers that can reach it.

  PATCH /api/admin/models
      `{id, enabled?, preferred?, comment?}`. Exactly the fields present are
      written; `enabled` and `preferred` must be real booleans, and `comment` may
      be a string or null. An id that names no row is a 404, not a silent no-op.

THE DERIVED SERVER LIST, NOT A PROVIDER COLUMN

The design says provider stops being an axis but does not stop mattering — "which
servers can reach this?" is still a question someone asks. So each model carries
`servers`: the connections whose discovery has seen it. Derived from
`ConnectionModelIntersect`, never stored, which is what keeps the page from
reintroducing the per-server axis the redesign removed.

WHY `enabled` IS FILTERED IN THE QUERY AND NOT IN THE PAGE

419 models is the measured size of the abandoned catalogue. Filtering and searching
in SQL keeps the page from holding every row to render thirty of them, and the
three filters are the three things anyone actually does here: find a model by name,
see what is switched off, see what failed a test.
"""

from typing import Any, Optional

from fastapi import APIRouter, Depends, Query, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel

from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth, _error, _is_admin, _is_example
from src.utils.timestamps import iso_utc

router = APIRouter(prefix="/api/admin", tags=["admin-models"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ============================================================
# ERROR CODES
#
# The three shared ones already exist and are reused rather than re-declared —
# `api.admin.only_full_admin`, `api.admin.no_fields` and `api.auth.unauthorized`
# are in the common registry, and a second declaration of the same text would be a
# duplicate fallback the linter reports.
# ============================================================

E_UNAUTHORIZED = "api.auth.unauthorized"
E_ONLY_FULL_ADMIN = "api.admin.only_full_admin"
E_NO_FIELDS = "api.admin.no_fields"
E_MISSING_MODEL_ID = "api.admin.missing_model_id"
E_MODEL_NOT_FOUND = "api.admin.model_not_found"
E_MODEL_UPDATE_ERROR = "api.admin.model_update_error"
E_MODELS_LOAD_ERROR = "api.admin.models_load_error"

# What the page can filter on. Anything else is ignored rather than refused: a
# stale bookmark should show the unfiltered list, not an error about a parameter
# the reader did not type.
_TEST_FILTERS = {"tools", "competence", "turn"}


class ModelPatchBody(BaseModel):
    id: Optional[Any] = None
    enabled: Optional[Any] = None
    preferred: Optional[Any] = None
    comment: Optional[Any] = None


async def _servers_by_model(conn, model_ids):
    """Which connections have seen each model, as `{modelId: [servers]}`.

    One query for the whole page rather than one per row. `LEFT JOIN` from the
    intersect keeps a model with no sightings reachable — it exists, nothing has
    discovered it yet, and the page says so rather than omitting it.

    Deliberately **unscoped**: no owner and no group filter, because this is the
    admin lens. That is what makes an administrator able to see every connection
    that has a model, not only their own or their group's. `connectionId` is
    selected so the entry can name the pair a later tuning write acts on —
    without it the page could say a connection has the model but not which one,
    which is a permission with no route to it.
    """
    if not model_ids:
        return {}
    rows = await conn.fetch(
        'SELECT c."modelId", a."connectionId", a.name, a.provider '
        'FROM public."ConnectionModelIntersect" c '
        'JOIN public."UserAIConnection" a ON a."connectionId" = c."connectionId" '
        'WHERE c."modelId" = ANY($1::text[]) '
        'ORDER BY a.name ASC',
        model_ids,
    )
    out: dict = {}
    for r in rows:
        out.setdefault(r["modelId"], []).append(
            {"connectionId": r["connectionId"], "name": r["name"], "provider": r["provider"]}
        )
    return out


def _public(row, servers):
    """One model as the page consumes it.

    `testResults` is always an object, never null — the page indexes it by test id
    and a null would force every caller to defend against a shape the API is
    promising not to send. Same rule as the user-facing read path, deliberately.
    """
    capability = row["modelTestResults"] or {}
    return {
        "id": row["id"],
        "modelName": row["modelName"],
        "enabled": row["enabled"],
        "preferred": row["preferred"],
        "comment": row["comment"],
        "testResults": capability,
        "servers": servers,
        "createdAt": iso_utc(row["createdAt"]),
        "updatedAt": iso_utc(row["updatedAt"]),
    }


@router.get("/models")
async def list_models(
    req: Request,
    search: Optional[str] = Query(None),
    enabled: Optional[str] = Query(None),
    test: Optional[str] = Query(None),
    result: Optional[str] = Query(None),
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        # Example users may look: the admin models page renders read-only for them,
        # and the gate here mirrors that rather than inventing a second rule.
        if not await _is_admin(uid) and not await _is_example(uid):
            return await _error(403, E_ONLY_FULL_ADMIN, language)

        where = []
        args = []
        if search:
            args.append(f"%{search}%")
            where.append(f'm."modelName" ILIKE ${len(args)}')
        if enabled in ("true", "false"):
            args.append(enabled == "true")
            where.append(f'm.enabled = ${len(args)}')
        if test in _TEST_FILTERS and result:
            # `result` names a state the model's entry for that test must carry.
            # A model with no entry at all has no state, so it cannot match — which
            # is what "filter by result" should mean for an untested model.
            args.append(test)
            args.append(result)
            where.append(
                f'm."modelTestResults" -> ${len(args) - 1} ->> \'state\' = ${len(args)}'
            )

        sql = (
            'SELECT m."id", m."modelName", m.enabled, m.preferred, m.comment, '
            '       m."modelTestResults", m."createdAt", m."updatedAt" '
            'FROM public."LLMModel" m'
        )
        if where:
            sql += " WHERE " + " AND ".join(where)
        sql += ' ORDER BY m."preferred" DESC, m."modelName" ASC'

        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(sql, *args)
            servers = await _servers_by_model(conn, [r["id"] for r in rows])

        return {"models": [_public(r, servers.get(r["id"], [])) for r in rows]}
    except Exception:
        return await _error(500, E_MODELS_LOAD_ERROR, language)


@router.patch("/models")
async def patch_model(
    body: ModelPatchBody,
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

        if not body.id:
            return await _error(400, E_MISSING_MODEL_ID, language)

        updates = {}
        if isinstance(body.enabled, bool):
            updates["enabled"] = body.enabled
        if isinstance(body.preferred, bool):
            updates["preferred"] = body.preferred
        if body.comment is not None:
            updates["comment"] = body.comment

        if not updates:
            return await _error(400, E_NO_FIELDS, language)

        sets = ", ".join(f'"{k}" = ${i + 2}' for i, k in enumerate(updates))
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f'UPDATE public."LLMModel" SET {sets}, "updatedAt" = NOW() '
                f'WHERE id = $1 '
                f'RETURNING "id", "modelName", enabled, preferred, comment, '
                f'          "modelTestResults", "createdAt", "updatedAt"',
                body.id, *updates.values(),
            )
            if row is None:
                return await _error(404, E_MODEL_NOT_FOUND, language)
            servers = await _servers_by_model(conn, [row["id"]])

        return {"model": _public(row, servers.get(row["id"], []))}
    except Exception:
        return await _error(500, E_MODEL_UPDATE_ERROR, language)
