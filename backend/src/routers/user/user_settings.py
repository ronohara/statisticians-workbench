"""
User Settings Router — P2 Group 2, item 10 (Prisma-removal plan).

Drop-in replacement for the frontend Prisma handler:
  frontend/app/api/user-settings/route.ts   (GET · POST)

Contract parity:
  - GET: any authenticated user reads 6 stored fields, returned flat with
    success: true; defaultAIConnectionId is coerced to a STRING
    (value?.toString() ?? null — an Int column); a missing user -> 404
    api.settings.user_not_found.
  - POST: example users blocked (403) BEFORE the body read (uniform read-only
    policy — item 10); body parse BEFORE the user fetch (malformed body ->
    500 even for a deleted user); only body-present fields update; an empty
    update returns 200 (Prisma data {}).
  - Field semantics mirrored exactly:
    emailNotifications/darkMode: Prisma Boolean — null/non-boolean -> 500.
    language: Prisma String — null/non-string -> 500.
    defaultAIConnectionId: JS truthiness + parseInt(String(v), 10) — falsy
    (false/0/""/null) -> NULL; "12abc" -> 12 (prefix-parse quirk, no FK on
    the column so any int stores); []/{}/true -> String() -> NaN, which is
    typeof "number" in JS so Prisma accepts it and stores NULL (verified
    live — NOT a 500).
  - P2025 (row gone between fetch and update) -> 500 save_failed.

Translation note: all responses route through t() with USER registry keys
(item 14); the api.settings.* pairs are now registered (item 35).

Auth helpers (_auth) are shared from admin.users.py; the JS parseInt port
is shared from admin.visualization_types.py; the pool is wired via
set_db_pool in main.py.
"""

import json

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth, _is_example
from src.routers.user.translations import USER
from src.utils.translation import t

router = APIRouter(prefix="/api/user-settings", tags=["user-settings"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ============================================================
# FRONTEND ERROR-CODE CONTRACT (stable API surface — do not rename)
# ============================================================

E_UNAUTHORIZED = "api.auth.unauthorized"
E_EXAMPLE_BLOCKED = "api.settings.example_blocked"
E_USER_NOT_FOUND = "api.settings.user_not_found"
E_LOAD_FAILED = "api.settings.load_failed"
E_SAVE_FAILED = "api.settings.save_failed"
E_INVALID_DEFAULT_AI = "api.settings.invalid_default_ai_connection"
E_INVALID_THRESHOLD = "api.settings.invalid_slow_threshold"

_GET_SELECT = ("emailNotifications", "darkMode", "language",
               "defaultAIConnectionId", "maxUploadSizeMB", "maxUploadCount",
               "modelSlowThresholdSeconds")

# ============================================================
# THE MODEL-SLOW THRESHOLD — one resolution function
# ============================================================
#
# "Too slow" is not a property of a model and not a property of a server. It is a
# judgement, and it belongs to the person waiting: the same 41 s measurement is fine for
# a lunch break and unusable in a chat window.
#
# THE RULE THIS EXISTS TO ENFORCE: resolution happens once per backend. The read path
# (Item 17) asks this function, and so does anything that displays a limit. Two callers
# comparing against two slightly different rules is how a page and an API come to
# disagree about whether a model is too slow — and with two backends there are four
# possible rules unless one function per backend owns it.
#
# TWO LEVELS, AND NO GROUP LEVEL. The design settles it: groups govern connection
# sharing, they do not govern patience.
#
#   the user's own value, else the global default, else the built-in below.
#
# The built-in is stated here, in code, with its reason rather than in a migration: a
# database with no settings row must still answer, and the number needs its reasoning
# beside it, which a schema default cannot carry.

DEFAULT_MODEL_TEST_SECONDS = 30
"""The seed for a new settings row — and the emergency value when the row is absent.

30 seconds, from the design's own worked example ("took 41.2 s, your limit is 30 s"), so
the number a reader meets in the design is the number the code uses. A shorter limit
refuses models a local GPU answers in 12 s; a much longer one delivers the refusal after
the user has given up waiting, which is the situation it exists to prevent.

NOT a third tier competing with the global setting. The global column is
NOT NULL DEFAULT 30, so in a healthy database the global tier always holds a number and
this constant is never consulted. It answers one case only: the settings row is missing
entirely, which the read path normally prevents by creating it. Returning a number there
beats raising inside a resolver that three callers use.
"""


async def resolve_slow_threshold(conn, user_id):
    """The slow-model limit in effect for one user, in seconds.

    Three tiers, in order. The query reads both columns in ONE round trip, so a change
    to the global default between two queries cannot produce a value that was never true.

    `conn` is an asyncpg connection — passed in rather than taken from `_db_pool`, so a
    caller already inside a transaction resolves against that transaction's view.
    """
    # A LEFT JOIN, not `FROM "User" WHERE id = $1`: with a plain WHERE, a missing user
    # returns no row at all and the global default — which does not depend on the user —
    # is lost with it. Measured in the Go mirror: it returned the built-in where the
    # global default applied. The join guarantees one row carrying both tiers, so the
    # lower tier survives a user that does not exist.
    #
    # No LIMIT 1 on the global side. The table carries a CHECK (id = 1) constraint, so
    # there can be at most one row and `g.id = 1` names it exactly. A LIMIT would be a
    # filter that silently picks a row when there should be one — the same defect the
    # constraint was added to remove.
    row = await conn.fetchrow(
        'SELECT u."modelSlowThresholdSeconds" AS own, g."defaultModelTestSeconds" AS global '
        'FROM (SELECT 1) AS one '
        'LEFT JOIN "User" u ON u.id = $1 '
        'LEFT JOIN "GlobalSettings" g ON g.id = 1',
        user_id,
    )
    if row is None:
        # Cannot happen with the join, but a caller that resolves inside an aborted
        # transaction should get the built-in rather than an exception from a None.
        row = {"own": None, "global": None}

    if row["own"] is not None:
        return int(row["own"])
    if row["global"] is not None:
        return int(row["global"])
    # Reachable only when the settings row is absent — the column itself cannot be NULL.
    # A number here beats an exception in a function three callers depend on.
    return DEFAULT_MODEL_TEST_SECONDS


async def _error(status: int, code: str, language: str, **kwargs):
    """Coded-envelope error routed through t() (item 14)."""
    message = await t(_db_pool, language, USER[code], **kwargs)
    return JSONResponse(status_code=status, content={"error": code, "message": message})


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("")
async def get_user_settings(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)

        cols = ", ".join(f'"{c}"' for c in _GET_SELECT)
        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                f'SELECT {cols} FROM "User" WHERE id = $1', uid
            )
        if row is None:
            return await _error(404, E_USER_NOT_FOUND, language)

        conn_id = row["defaultAIConnectionId"]
        # Resolved through the one function, not recomputed here: a second derivation in
        # this handler is the divergence the item exists to prevent.
        effective = await resolve_slow_threshold(_db_pool, uid)
        return {
            "success": True,
            "emailNotifications": row["emailNotifications"],
            "darkMode": row["darkMode"],
            "language": row["language"],
            "defaultAIConnectionId": str(conn_id) if conn_id is not None else None,
            "maxUploadSizeMB": row["maxUploadSizeMB"],
            "maxUploadCount": row["maxUploadCount"],
            # The user's OWN value, null when they inherit — the page must be able to tell
            # "not set" from "set to the value that happens to equal the default", which
            # the resolved number cannot say.
            "modelSlowThresholdSeconds": row["modelSlowThresholdSeconds"],
            # And the number actually in effect, from the same function the read path uses.
            # Two fields answer two questions: what have I chosen, and what applies to me.
            # Item 21's fourth clause needs the second — without it there is nothing to
            # compare between backends.
            "modelSlowThresholdEffectiveSeconds": effective,
        }
    except Exception:
        return await _error(500, E_LOAD_FAILED, language)


@router.post("")
async def post_user_settings(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)

        # Example users are read-only (uniform policy — item 10): block
        # BEFORE the body read, matching the other user routes.
        if await _is_example(uid):
            return await _error(403, E_EXAMPLE_BLOCKED, language)

        # req.json() throws on an empty/malformed body -> caught -> 500.
        try:
            body = json.loads(await req.body() or b"")
        except Exception:
            return await _error(500, E_SAVE_FAILED, language)
        if body is None:
            # Destructuring null throws in the frontend -> 500.
            return await _error(500, E_SAVE_FAILED, language)
        if not isinstance(body, dict):
            # Destructuring an array/string/number yields all-undefined.
            body = {}

        async with _db_pool.acquire() as conn:
            user = await conn.fetchrow(
                'SELECT id FROM "User" WHERE id = $1', uid
            )
        if user is None:
            return await _error(404, E_USER_NOT_FOUND, language)

        update = {}
        for col in ("emailNotifications", "darkMode"):
            if col in body:
                if not isinstance(body[col], bool):
                    # Prisma Boolean field: null/non-boolean -> validation throw.
                    return await _error(500, E_SAVE_FAILED, language)
                update[col] = body[col]
        if "language" in body:
            if not isinstance(body["language"], str):
                # Prisma String field: null/non-string -> validation throw.
                return await _error(500, E_SAVE_FAILED, language)
            update["language"] = body["language"]
        if "modelSlowThresholdSeconds" in body:
            v = body["modelSlowThresholdSeconds"]
            if v is None:
                # Clearing the user's own value reverts them to inheriting. Allowed, and
                # distinct from sending 0.
                update["modelSlowThresholdSeconds"] = None
            elif isinstance(v, bool) or not isinstance(v, int):
                # Validate, don't coerce. A float or a numeric string is refused with a
                # message, not truncated: silently accepting 12.7 as 12 is the coercion
                # this project forbids, and a bool is an int in Python, so it is named.
                return await _error(400, E_INVALID_THRESHOLD, language)
            elif v < 1:
                # 0 or negative would make every model "too slow", which is a refusal of
                # everything rather than a limit. The reason is stated in the message.
                return await _error(400, E_INVALID_THRESHOLD, language)
            else:
                update["modelSlowThresholdSeconds"] = v

        if "defaultAIConnectionId" in body:
            v = body["defaultAIConnectionId"]
            if v is None:
                update["defaultAIConnectionId"] = None
            elif isinstance(v, int) and not isinstance(v, bool):
                update["defaultAIConnectionId"] = v
            else:
                # Clean validation (was NaN -> NULL coercion): reject a
                # non-integer defaultAIConnectionId.
                return await _error(400, E_INVALID_DEFAULT_AI, language)

        async with _db_pool.acquire() as conn:
            if update:
                sets = ", ".join(f'"{c}" = ${i + 1}' for i, c in enumerate(update))
                values = list(update.values())
                row = await conn.fetchrow(
                    f'UPDATE "User" SET {sets}, "updatedAt" = NOW() '
                    f'WHERE id = ${len(values) + 1} RETURNING id',
                    *values, uid,
                )
            else:
                # Prisma data {} — no-op update returns 200.
                row = await conn.fetchrow(
                    'SELECT id FROM "User" WHERE id = $1', uid
                )
        if row is None:
            # Row vanished between existence check and UPDATE → 404.
            return await _error(404, E_USER_NOT_FOUND, language)
        return {"success": True}
    except Exception:
        return await _error(500, E_SAVE_FAILED, language)
