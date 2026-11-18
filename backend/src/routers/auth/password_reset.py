"""
Password Reset Router — P2 Group 5, item 21 (Prisma-removal plan).

Drop-in replacements for the frontend Prisma handlers:
  frontend/app/api/auth/forgot-password/route.ts   (POST /api/auth/forgot-password)
  frontend/app/api/auth/reset-password/route.ts    (POST /api/auth/reset-password)

UNAUTHENTICATED (public paths — the frontend proxy lists /api/register and the
/api/auth prefix under publicPaths; forgot/reset are NOT behind a session
gate). No HTTPBearer, no get_current_language.

CLEAN VALIDATION (no JS-coercion emulation — see workbench-documents/development-records/code-quirks.md, the
item-9 coercion-defect entry):
  - forgot: email must be a non-empty string, else 400 missing_email. A
    non-string email is rejected at the gate (not String()-coerced into a
    Prisma lookup).
  - reset: token and newPassword must be non-empty strings, else 400
    missing_fields. newPassword never reaches validate_password as a
    non-string.
  - malformed/null body: caught -> coded 500
    {error: "api.auth.internal_error", message: "Internal server error"}
    (item 25, matching register) instead of a bare framework 500.

Mirrored behaviour (parity, not correction):
  - forgot is silent for an unknown email -> 200 {success: true} (no user
    enumeration).
  - forgot sends email AFTER the token transaction commits — same
    partial-commit hazard as register (logged).
  - reset's password_validation_failed message is composed by localizing each
    failing validation rule through t() (the shared validation.password.* keys).

Expiry semantics: PasswordResetToken.expiresAt is `timestamp without time
zone`; Prisma writes/reads it as UTC. The expiry check therefore compares the
naive stored value against naive-UTC now (datetime.utcnow equivalent), not
local time.

Translation (option b): coded envelope {error: code, message}, message routed
through t() with the PASSWORD_RESET registry keyed by the canonical
api.auth.* key. The handler accepts a `language` QUERY parameter (default
"en") — the future globe-icon UI selector's value — and passes it to t();
the matrix pins language=en to match the current UI's lack of a signal, so
parity holds in English while the keys remain translatable.
"""

import json
import secrets
import uuid
from datetime import datetime, timezone

import bcrypt

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.routers.auth.translations import PASSWORD_RESET
from src.routers.admin.users import _is_example
from src.utils.email import send_password_reset_email
from src.utils.password_validation import validate_password
from src.utils.translation import t

router = APIRouter(tags=["password-reset"])
_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


E_MISSING_EMAIL = "api.auth.missing_email"
E_EXAMPLE_FORGOT = "api.auth.example_user_forgot_blocked"
E_MISSING_FIELDS = "api.auth.missing_fields"
E_INVALID_TOKEN = "api.auth.invalid_token"
E_TOKEN_EXPIRED = "api.auth.token_expired"
E_EXAMPLE_RESET = "api.auth.example_user_reset_blocked"
E_PASSWORD_VALIDATION_FAILED = "api.auth.password_validation_failed"
E_INTERNAL_ERROR = "api.auth.internal_error"


async def _error(status: int, code: str, language: str = "en", **kwargs) -> JSONResponse:
    message = await t(_db_pool, language, PASSWORD_RESET[code], **kwargs)
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def _raw_error(status: int, code: str, message: str) -> JSONResponse:
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def _utc_now():
    """Now, as an aware UTC instant.

    The naive form this replaces existed to match `expiresAt` while that column was
    `timestamp without time zone`. It is a `timestamptz` since Item 7 of the timestamp
    plan, so asyncpg returns an aware datetime and comparing it to a naive one raises
    `TypeError: can't compare offset-naive and offset-aware datetimes` — the endpoint
    500s rather than answering "expired". Both sides are now instants.
    """
    return datetime.now(timezone.utc)


@router.post("/api/auth/forgot-password")
async def forgot_password(request: Request, language: str = "en"):
    # Item 25: malformed JSON / null body -> coded 500 (matching register),
    # not a bare framework 500.
    try:
        body = json.loads(await request.body() or b"")
    except Exception:
        return await _error(500, E_INTERNAL_ERROR, language)
    if body is None:
        return await _error(500, E_INTERNAL_ERROR, language)
    if not isinstance(body, dict):
        body = {}

    email = body.get("email")
    if not isinstance(email, str) or not email:
        return await _error(400, E_MISSING_EMAIL, language)

    async with _db_pool.acquire() as conn:
        user = await conn.fetchrow(
            'SELECT id, language FROM "User" WHERE email = $1', email
        )
    if user is None:
        # Silent — no user enumeration.
        return {"success": True}

    if await _is_example(user["id"]):
        return await _error(403, E_EXAMPLE_FORGOT, language)

    async with _db_pool.acquire() as conn:
        settings = await conn.fetchrow(
            'SELECT "emailVerificationTimeout" FROM "GlobalSettings" WHERE id = 1'
        )
    timeout_hours = settings["emailVerificationTimeout"] \
        if settings is not None and settings["emailVerificationTimeout"] is not None else 24
    token = secrets.token_hex(32)
    user_language = user["language"] or "en"

    async with _db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                'DELETE FROM "PasswordResetToken" WHERE "userId" = $1', user["id"]
            )
            await conn.execute(
                'INSERT INTO "PasswordResetToken" (id, token, "userId", "expiresAt") '
                "VALUES ($1, $2, $3, NOW() + ($4::int * INTERVAL '1 hour'))",
                str(uuid.uuid4()), token, user["id"], timeout_hours,
            )

    # Mirrored: email AFTER commit.
    await send_password_reset_email(_db_pool, email, token, user_language)

    return {"success": True}


@router.post("/api/auth/reset-password")
async def reset_password(request: Request, language: str = "en"):
    try:
        body = json.loads(await request.body() or b"")
    except Exception:
        return await _error(500, E_INTERNAL_ERROR, language)
    if body is None:
        return await _error(500, E_INTERNAL_ERROR, language)
    if not isinstance(body, dict):
        body = {}

    token = body.get("token")
    new_password = body.get("newPassword")
    if not isinstance(token, str) or not token \
            or not isinstance(new_password, str) or not new_password:
        return await _error(400, E_MISSING_FIELDS, language)

    async with _db_pool.acquire() as conn:
        reset_token = await conn.fetchrow(
            'SELECT id, "userId", "expiresAt" FROM "PasswordResetToken" WHERE token = $1',
            token,
        )
    if reset_token is None:
        return await _error(400, E_INVALID_TOKEN, language)

    if reset_token["expiresAt"] < _utc_now():
        return await _error(400, E_TOKEN_EXPIRED, language)

    if await _is_example(reset_token["userId"]):
        return await _error(403, E_EXAMPLE_RESET, language)

    async with _db_pool.acquire() as conn:
        settings = await conn.fetchrow(
            'SELECT "passwordPolicy", "passwordPolicyCustom" FROM "GlobalSettings" WHERE id = 1'
        )
    policy_name = (settings["passwordPolicy"] if settings else None) or "medium"
    custom = settings["passwordPolicyCustom"] if settings else None
    if not isinstance(custom, dict):
        custom = None

    errors = validate_password(new_password, policy_name, custom)
    if errors:
        messages = [await t(_db_pool, language, key, **kwargs) for key, kwargs in errors]
        return _raw_error(400, E_PASSWORD_VALIDATION_FAILED, " ".join(messages))

    hashed = bcrypt.hashpw(new_password.encode("utf-8"),
                           bcrypt.gensalt(rounds=10)).decode("utf-8")

    async with _db_pool.acquire() as conn:
        async with conn.transaction():
            await conn.execute(
                'UPDATE "User" SET password = $1 WHERE id = $2',
                hashed, reset_token["userId"],
            )
            await conn.execute(
                'DELETE FROM "PasswordResetToken" WHERE id = $1', reset_token["id"]
            )

    return {"success": True}
