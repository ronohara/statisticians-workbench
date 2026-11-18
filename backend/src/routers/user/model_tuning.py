"""
Per-pair AI tuning (plan Item 9 of workbench-ai-limits-plan.html).

The three values that decide how a model answers — temperature, output cap and
per-call time — belong to the `(connectionId, modelId)` pair, because that is the
pair every AI request already carries. This module is the only way to read or write
them.

WHO MAY DO WHAT

    read   any caller who can USE the connection — owner, or a member of the group
           it is shared with — and any admin. Reading must be at least as wide as
           using: a member who cannot see that a model is tuned to 0.2 gets
           behaviour they cannot explain.
    write  the owner, or ANY admin.

The write predicate is deliberately WIDER than `patch_ai_connections`, which admits
an admin only for a row shared to *that admin's group*. Decision D2 from the plan:
tuning is a behaviour choice, credentials are not, and an administrator who has to
reason about group membership before fixing a timeout will not fix it. The
divergence is intentional and recorded in the plan's Notes — a later reader who
"fixes" one to match the other should read that first.

A MISS IS THE SAME 404 FOR EVERYONE

An unauthorised caller learns nothing about whether the pair exists. That is the
rule `project-design.md` §4 records for datasets, and the same rule the connections
router follows.

WHAT IS NOT HERE

- The per-request `timeoutSeconds` escalation (Item 12). It is a property of one
  attempt, never stored, so it has nothing to do with this table.
- The resolver (Item 5). This module answers "what is configured"; the resolver
  answers "what is in force", and it is the one that knows the precedence.

THE WRITE IS A MERGE, NOT A REPLACEMENT

Only the columns the caller supplied are written, in one statement. A body carrying
`temperature` must not clear a `timeoutSeconds`, and a caller clearing one value
must not have to restate the other two. `None` explicitly means "clear it back to
inherit" — which is different from the key being absent, and the difference is kept
because the resolver distinguishes NULL from a value.

`lastSeenAt` is left alone on update: it records when the pair was last observed by
discovery or testing, and retuning a pair does not mean anything looked at it. On
insert it takes the column default.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from starlette.responses import JSONResponse

from src.routers.admin.users import _is_admin
from src.routers.user.ai_connections import _auth
from src.routers.user.translations import USER
from src.routers.datasets.crud import get_current_language
from src.utils.translation import t

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/user/model-tuning", tags=["user-model-tuning"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# Bounds, mirroring the CHECK constraints and the settings endpoint's validation.
# Repeated here rather than imported from the admin router because these two
# surfaces must be able to change their wording independently; the database is the
# authority that keeps them honest.
TEMPERATURE_MIN = 0.0
TEMPERATURE_MAX = 2.0


async def _error(status: int, code: str, language: str, **kwargs) -> JSONResponse:
    message = await t(_db_pool, language, USER[code], **kwargs)
    return JSONResponse(status_code=status, content={"error": code, "message": message})


async def _read_body(request: Request) -> Optional[dict]:
    """The JSON body, or None when it is not an object.

    Mirrors the parse contract the other user routers use: malformed is a 500 at the
    call site, a non-object is "nothing supplied".
    """
    raw = await request.body()
    if not raw:
        return {}
    try:
        parsed = json.loads(raw)
    except Exception:
        raise ValueError("malformed")
    if parsed is None:
        raise ValueError("malformed")
    if not isinstance(parsed, dict):
        return {}
    return parsed


async def _resolve_access(conn, uid: str, connection_id: int, want_write: bool):
    """The connection row if `uid` may read (or, with `want_write`, write) it.

    Returns None for every refusal — the caller turns that into one 404, so the two
    reasons are indistinguishable from outside.
    """
    owned = await conn.fetchrow(
        'SELECT "connectionId", "userId", "isShared", "aiConnectionGroup" '
        'FROM "UserAIConnection" WHERE "connectionId" = $1 AND "userId" = $2',
        connection_id, uid,
    )
    if owned is not None:
        return owned

    if want_write:
        # Any admin may tune a pair, whatever group it is shared to (D2).
        if await _is_admin(uid):
            row = await conn.fetchrow(
                'SELECT "connectionId", "userId", "isShared", "aiConnectionGroup" '
                'FROM "UserAIConnection" WHERE "connectionId" = $1',
                connection_id,
            )
            return row  # may still be None -> 404
        return None

    # Reading: a group member may read what they may use.
    user = await conn.fetchrow('SELECT "userGroup" FROM "User" WHERE id = $1', uid)
    group = (user["userGroup"] if user else None) or "00"
    shared = await conn.fetchrow(
        'SELECT "connectionId", "userId", "isShared", "aiConnectionGroup" '
        'FROM "UserAIConnection" '
        'WHERE "connectionId" = $1 AND "isShared" = true AND "aiConnectionGroup" = $2',
        connection_id, group,
    )
    if shared is not None:
        return shared
    if await _is_admin(uid):
        return await conn.fetchrow(
            'SELECT "connectionId", "userId", "isShared", "aiConnectionGroup" '
            'FROM "UserAIConnection" WHERE "connectionId" = $1',
            connection_id,
        )
    return None


def _tuning_payload(row) -> dict:
    """The three values, with null meaning "inherit" made explicit to the caller.

    `inherited` is included so the UI can say which values are the caller's own
    choice and which fall through — the difference a user needs to understand
    precedence without reading the resolver.
    """
    return {
        "connectionId": row["connectionId"],
        "modelId": row["modelId"],
        "temperature": float(row["temperature"]) if row["temperature"] is not None else None,
        "maxTokens": row["maxTokens"],
        "timeoutSeconds": row["timeoutSeconds"],
        "inherited": {
            "temperature": row["temperature"] is None,
            "maxTokens": row["maxTokens"] is None,
            "timeoutSeconds": row["timeoutSeconds"] is None,
        },
    }


def _validate_tuning(body: dict) -> tuple[Optional[dict], Optional[str]]:
    """Validate the three fields. Returns (updates, error_code).

    Absent means "leave alone". Null means "clear to inherit". Anything else must be
    legal, checked here so the caller gets a coded 400 rather than a constraint
    violation surfacing as a 500.
    """
    updates: dict = {}

    if "temperature" in body:
        v = body["temperature"]
        if v is None:
            updates["temperature"] = None
        else:
            # A bool is an int in Python; `True` would otherwise store as 1.0.
            if isinstance(v, bool) or not isinstance(v, (int, float)):
                return None, "api.user.tuning_invalid_temperature"
            f = float(v)
            if f < TEMPERATURE_MIN or f > TEMPERATURE_MAX:
                return None, "api.user.tuning_invalid_temperature"
            updates["temperature"] = f

    if "maxTokens" in body:
        v = body["maxTokens"]
        if v is None:
            updates["maxTokens"] = None
        else:
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                return None, "api.user.tuning_invalid_max_tokens"
            updates["maxTokens"] = v

    if "timeoutSeconds" in body:
        v = body["timeoutSeconds"]
        if v is None:
            updates["timeoutSeconds"] = None
        else:
            if isinstance(v, bool) or not isinstance(v, int) or v < 1:
                return None, "api.user.tuning_invalid_ai_timeout"
            updates["timeoutSeconds"] = v

    return updates, None


@router.get("/{connection_id}/{model_id}")
async def get_model_tuning(
    connection_id: str,
    model_id: str,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """The tuning configured for one pair. Anyone who may use the connection may read it."""
    uid = await _auth(credentials)
    if uid is None:
        return await _error(401, "api.auth.unauthorized", language)

    if not connection_id.isdigit():
        return await _error(400, "api.user.invalid_connection_id", language)
    cid = int(connection_id)

    async with _db_pool.acquire() as conn:
        access = await _resolve_access(conn, uid, cid, want_write=False)
        if access is None:
            return await _error(404, "api.user.tuning_connection_not_found", language)

        row = await conn.fetchrow(
            'SELECT "connectionId", "modelId", "temperature", "maxTokens", "timeoutSeconds" '
            'FROM public."ConnectionModelIntersect" '
            'WHERE "connectionId" = $1 AND "modelId" = $2',
            cid, model_id,
        )
        if row is None:
            # No row means nothing is tuned, which is a true answer rather than a
            # miss: every value inherits. Returning 404 here would make an untuned
            # pair indistinguishable from a pair nobody may see.
            return JSONResponse(status_code=200, content={
                "connectionId": cid,
                "modelId": model_id,
                "temperature": None,
                "maxTokens": None,
                "timeoutSeconds": None,
                "inherited": {"temperature": True, "maxTokens": True, "timeoutSeconds": True},
            })

        return JSONResponse(status_code=200, content=_tuning_payload(row))


@router.patch("/{connection_id}/{model_id}")
async def update_model_tuning(
    connection_id: str,
    model_id: str,
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Write a pair's tuning. The owner, or any admin (plan decision D2)."""
    uid = await _auth(credentials)
    if uid is None:
        return await _error(401, "api.auth.unauthorized", language)

    if not connection_id.isdigit():
        return await _error(400, "api.user.invalid_connection_id", language)
    cid = int(connection_id)

    try:
        body = await _read_body(request)
    except ValueError:
        return await _error(500, "api.user.tuning_malformed_body", language)
    if body is None:
        body = {}

    updates, err = _validate_tuning(body)
    if err is not None:
        return await _error(400, err, language)
    if not updates:
        # Nothing supplied. Not an error — but say so plainly rather than returning a
        # row the caller may read as "your change was applied".
        return await _error(400, "api.user.tuning_nothing_to_update", language)

    async with _db_pool.acquire() as conn:
        # One transaction: the authorization decision and the write must see the same
        # row. A connection re-shared between the two would otherwise let a caller
        # write after losing access.
        async with conn.transaction():
            access = await _resolve_access(conn, uid, cid, want_write=True)
            if access is None:
                return await _error(404, "api.user.tuning_connection_not_found", language)

            # The model must exist: modelId carries a foreign key, and a violation
            # escaping as a 500 would tell the caller nothing actionable.
            model = await conn.fetchrow(
                'SELECT id, "modelName" FROM public."LLMModel" WHERE id = $1', model_id
            )
            if model is None:
                return await _error(404, "api.user.tuning_model_not_found", language)

            # Create the row on demand. Discovery creates these when a model is seen,
            # so a pair that has never been tested has none — and tuning a pair is a
            # reason for the row to exist. ON CONFLICT DO NOTHING keeps this safe
            # against a concurrent discovery writing the same pair.
            await conn.execute(
                'INSERT INTO public."ConnectionModelIntersect" ("connectionId", "modelId") '
                'VALUES ($1, $2) ON CONFLICT ("connectionId", "modelId") DO NOTHING',
                cid, model_id,
            )

            # Merge: only the supplied columns are named in the SET, so a body with
            # one field cannot disturb the other two.
            assignments = ", ".join(f'"{col}" = ${i + 3}' for i, col in enumerate(updates))
            await conn.execute(
                f'UPDATE public."ConnectionModelIntersect" SET {assignments} '
                'WHERE "connectionId" = $1 AND "modelId" = $2',
                cid, model_id, *updates.values(),
            )

            row = await conn.fetchrow(
                'SELECT "connectionId", "modelId", "temperature", "maxTokens", "timeoutSeconds" '
                'FROM public."ConnectionModelIntersect" '
                'WHERE "connectionId" = $1 AND "modelId" = $2',
                cid, model_id,
            )

    return JSONResponse(status_code=200, content=_tuning_payload(row))
