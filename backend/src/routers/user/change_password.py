"""
Change Password Routers — P2 Group 2, item 9 (Prisma-removal plan).

Drop-in replacements for the frontend Prisma handlers:
  frontend/app/api/user/change-password/route.ts  (POST — bare-string envelope)
  frontend/app/api/auth/change-password/route.ts  (POST — coded envelope)

The two frontend handlers share the same flow but different envelopes; the
UI uses the /api/user variant (settings/profile/page.tsx). Both are ported
here with a shared core, mirroring each handler's exact response shape:

  user route:  {error: "Unauthorized"}            (bare strings throughout,
                403/400/404/500 all bare)          no codes except the 403)
  auth route:  {error: code, message: text}        (coded throughout)

Contract parity (both routes):
  - 401 before anything else when the session/token is absent or invalid
    (the global HTTPBearer gate answers no-token requests first).
  - Example users blocked BEFORE the body is read -> 403.
  - !currentPassword || !newPassword (JS falsy) -> 400 missing fields. A
    non-string newPassword is rejected as missing too (clean type gate, no
    coercion — item 21).
  - Policy fetch: GlobalSettings id=1, passwordPolicy || "medium",
    passwordPolicyCustom || undefined; a missing row behaves as medium
    (behaviorally identical to an explicit medium policy — covered by the
    medium matrix cases).
  - validatePassword mirror: clean validation via the shared
    src/utils/password_validation module (item 21) — a non-string newPassword
    is rejected as a missing-field 400 (never silently coerced, never a 500),
    and string passwords are checked per-policy. Error list order: min_length,
    uppercase, lowercase, digit, special, too_weak — joined with a single
    space.
  - !user || !user.password -> 404 (ghost + null-password fixtures).
  - bcrypt.compare fail -> 400 current password incorrect.
  - bcrypt.hash(10) + update -> {success: true}.

Dependencies: bcrypt (bcryptjs-compatible) and zxcvbn (official port of
the same algorithm the frontend scores with) — both added to
requirements.txt with this item.

Translation note: both envelopes route through t() with USER registry keys
(item 14); api.auth.* pairs added and namespaces reconciled (item 35). The
validation message is composed by localizing each failing rule through t()
(the shared validation.password.* keys).

Auth helpers (_auth, _is_example) are shared from admin.users.py; the pool
is wired via set_db_pool in main.py.
"""

import json

import bcrypt
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth, _is_example
from src.routers.user.translations import USER
from src.utils.password_validation import validate_password
from src.utils.translation import t

router = APIRouter(tags=["change-password"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ============================================================
# FRONTEND ERROR-CODE CONTRACT (stable API surface — do not rename)
# ============================================================

E_USER_EXAMPLE_BLOCKED = "api.user.example_blocked"

E_AUTH_UNAUTHORIZED = "api.auth.unauthorized"
E_AUTH_EXAMPLE_BLOCKED = "api.auth.example_user_blocked"
E_AUTH_MISSING_FIELDS = "api.auth.missing_fields"
E_AUTH_VALIDATION_FAILED = "api.auth.password_validation_failed"
E_AUTH_USER_NOT_FOUND = "api.auth.user_not_found"
E_AUTH_INVALID_CURRENT = "api.auth.invalid_current_password"
E_AUTH_INTERNAL = "api.auth.internal_error"


async def _error(status: int, code: str, language: str, **kwargs):
    """Coded-envelope error routed through t() (item 14)."""
    message = await t(_db_pool, language, USER[code], **kwargs)
    return JSONResponse(status_code=status, content={"error": code, "message": message})


async def _t_error(status: int, key: str, language: str, **kwargs):
    """Bare-string error routed through t() (item 14)."""
    message = await t(_db_pool, language, USER[key], **kwargs)
    return JSONResponse(status_code=status, content={"error": message})


def _raw_error(status: int, code: str, message: str) -> JSONResponse:
    """Dynamic-message passthrough (coded)."""
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def _raw_bare(status: int, message: str) -> JSONResponse:
    """Dynamic-message passthrough (bare)."""
    return JSONResponse(status_code=status, content={"error": message})


# ============================================================
# SHARED CORE
# ============================================================

async def _fetch_policy():
    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT "passwordPolicy", "passwordPolicyCustom" '
            'FROM "GlobalSettings" WHERE id = 1'
        )
    if row is None:
        return "medium", None
    policy = row["passwordPolicy"] or "medium"
    custom = row["passwordPolicyCustom"]
    if not isinstance(custom, dict):
        custom = None
    return policy, custom


async def _change_password(uid: str, current_password, new_password, language: str) -> tuple[int, str, str | None]:
    """Shared flow. Returns (status, error, kind)."""
    if not current_password or not isinstance(new_password, str) or not new_password:
        return 400, None, "missing"

    policy_name, custom = await _fetch_policy()
    errors = validate_password(new_password, policy_name, custom)
    if errors:
        messages = [await t(_db_pool, language, key, **kwargs) for key, kwargs in errors]
        return 400, " ".join(messages), None

    async with _db_pool.acquire() as conn:
        user = await conn.fetchrow(
            'SELECT password FROM "User" WHERE id = $1', uid
        )
    if user is None or user["password"] is None:
        return 404, None, "not_found"

    try:
        valid = bcrypt.checkpw(
            str(current_password).encode("utf-8"),
            user["password"].encode("utf-8"),
        )
    except (TypeError, ValueError):
        # bcryptjs compare throws on non-string data / bad salt -> 500.
        return 500, None, "internal"
    if not valid:
        return 400, None, "wrong_current"

    hashed = bcrypt.hashpw(new_password.encode("utf-8"), bcrypt.gensalt(rounds=10)).decode("utf-8")
    async with _db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'UPDATE "User" SET password = $1, "updatedAt" = NOW() '
            'WHERE id = $2 RETURNING id',
            hashed, uid,
        )
    if row is None:
        # Prisma P2025 -> caught -> 500. Mirror.
        return 500, None, "internal"
    return 200, None, None


# ============================================================
# ENDPOINTS
# ============================================================

async def _read_body(req) -> tuple:
    """Mirror req.json(): returns (body, parse_ok). null -> (None, True);
    non-dict -> ({}, True); malformed/empty -> (None, False)."""
    try:
        body = json.loads(await req.body() or b"")
    except Exception:
        return None, False
    if body is None:
        return None, True
    if not isinstance(body, dict):
        return {}, True
    return body, True


@router.post("/api/user/change-password")
async def user_change_password(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(401, "api.auth.unauthorized", language)
        if await _is_example(uid):
            return await _error(403, E_USER_EXAMPLE_BLOCKED, language)
        body, ok = await _read_body(req)
        if not ok:
            return await _t_error(500, "api.user.internal_error", language)
        current_password = body.get("currentPassword")
        new_password = body.get("newPassword")
        status, error, kind = await _change_password(uid, current_password, new_password, language)
        if status == 200:
            return {"success": True}
        if status == 400:
            if kind == "missing":
                return await _t_error(400, "api.user.missing_fields", language)
            if kind == "wrong_current":
                return await _t_error(400, "api.user.invalid_current_password", language)
            return _raw_bare(400, error)  # joined localized validation messages
        if status == 404:
            return await _t_error(404, "api.user.user_not_found", language)
        return await _t_error(500, "api.user.internal_error", language)
    except Exception:
        return await _t_error(500, "api.user.internal_error", language)


@router.post("/api/auth/change-password")
async def auth_change_password(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_AUTH_UNAUTHORIZED, language)
        if await _is_example(uid):
            return await _error(403, E_AUTH_EXAMPLE_BLOCKED, language)
        body, ok = await _read_body(req)
        if not ok:
            return await _error(500, E_AUTH_INTERNAL, language)
        current_password = body.get("currentPassword")
        new_password = body.get("newPassword")
        status, error, kind = await _change_password(uid, current_password, new_password, language)
        if status == 200:
            return {"success": True}
        if status == 400:
            if kind == "missing":
                return await _error(400, E_AUTH_MISSING_FIELDS, language)
            if kind == "wrong_current":
                return await _error(400, E_AUTH_INVALID_CURRENT, language)
            return _raw_error(400, E_AUTH_VALIDATION_FAILED, error)
        if status == 404:
            return await _error(404, E_AUTH_USER_NOT_FOUND, language)
        return await _error(500, E_AUTH_INTERNAL, language)
    except Exception:
        return await _error(500, E_AUTH_INTERNAL, language)
