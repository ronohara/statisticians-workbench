"""
Email Verification Router — P2 Group 5, item 22 (Prisma-removal plan).

Drop-in replacements for the frontend Prisma handlers:
  frontend/app/api/auth/verify-email/route.ts    (GET  /api/auth/verify-email?token=...)
  frontend/app/api/auth/verify-request/route.ts  (POST /api/auth/verify-request)

UNAUTHENTICATED (public paths). No HTTPBearer, no get_current_language.

Error-shape (resolved — see workbench-documents/development-records/code-quirks.md item 2): both handlers now emit
coded envelopes. verify-email's machine codes are canonical api.auth.*
identifiers the client maps to translated text (no t(), no language param);
verify-request's prose routes through t() with canonical api.auth.* keys and a
`language` query parameter (default "en").

CLEAN VALIDATION (no JS-coercion emulation): email/token are type-gated.

Mirrored behaviour (parity, not correction):
  - verify-request has no try/catch in the frontend -> malformed/null body
    raises -> 500 (empty body); asserted STATUS-ONLY.
  - verify-request is silent for an unknown email -> 200 {success: true}.
  - verify-email's !token check is OUTSIDE the frontend's try/catch (missing
    token -> 400 missing_token, not 500); the DB work is inside -> any DB
    error becomes 500 internal_error.
  - verify-request sends email AFTER the token transaction commits (partial-
    commit hazard, logged). The EMAIL content language is user.language
    (profile), mirroring the frontend — NOT the error-message language param.

Expiry: VerificationToken.expiresAt is `timestamp without time zone` stored
as UTC; compare against naive-UTC now.
"""

import json
import secrets
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.routers.auth.translations import PASSWORD_RESET
from src.utils.email import send_verification_email
from src.utils.translation import t

router = APIRouter(tags=["email-verification"])
_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# Bare machine codes (identifiers, not prose — stay literal).
C_MISSING_TOKEN = "api.auth.missing_token"
C_INVALID_TOKEN = "api.auth.invalid_token"
C_TOKEN_EXPIRED = "api.auth.token_expired"
C_INTERNAL_ERROR = "api.auth.internal_error"

# Canonical api.auth.* keys for the two bare-prose messages.
K_EMAIL_REQUIRED = "api.auth.missing_email"
K_EMAIL_ALREADY_VERIFIED = "api.auth.email_already_verified"


def _code_error(status: int, code: str) -> JSONResponse:
    """Bare machine-code error (identifier — no t(), no language)."""
    return JSONResponse(status_code=status, content={"error": code})


async def _prose_error(status: int, key: str, language: str) -> JSONResponse:
    """Coded-envelope error routed through t(): {error: <canonical key>,
    message: <translated>}."""
    message = await t(_db_pool, language, PASSWORD_RESET[key])
    return JSONResponse(status_code=status, content={"error": key, "message": message})


def _utc_now():
    """Now, as an aware UTC instant.

    The naive form this replaces matched `expiresAt` while that column was
    `timestamp without time zone`. It is a `timestamptz` since Item 7 of the timestamp
    plan, so the stored value comes back aware and comparing it to a naive clock raises
    `TypeError` instead of answering "expired".
    """
    return datetime.now(timezone.utc)


@router.get("/api/auth/verify-email")
async def verify_email(request: Request):
    token = request.query_params.get("token")

    # The frontend's !token check is OUTSIDE its try/catch.
    if not token:
        return _code_error(400, C_MISSING_TOKEN)

    try:
        async with _db_pool.acquire() as conn:
            vt = await conn.fetchrow(
                'SELECT id, "userId", "expiresAt" FROM "VerificationToken" WHERE token = $1',
                token,
            )
            if vt is None:
                return _code_error(400, C_INVALID_TOKEN)

            if vt["expiresAt"] < _utc_now():
                return _code_error(400, C_TOKEN_EXPIRED)

            async with conn.transaction():
                await conn.execute(
                    'UPDATE "User" SET "emailVerified" = NOW() WHERE id = $1',
                    vt["userId"],
                )
                await conn.execute(
                    'DELETE FROM "VerificationToken" WHERE id = $1', vt["id"]
                )

        return {"success": True}
    except Exception:
        return _code_error(500, C_INTERNAL_ERROR)


@router.post("/api/auth/verify-request")
async def verify_request(request: Request, language: str = "en"):
    # No try/catch in the frontend: malformed JSON / null body -> 500.
    body = json.loads(await request.body() or b"")  # raises -> 500 (mirror)
    if body is None:
        return JSONResponse(status_code=500)
    if not isinstance(body, dict):
        body = {}

    email = body.get("email")
    if not isinstance(email, str) or not email:
        return await _prose_error(400, K_EMAIL_REQUIRED, language)

    async with _db_pool.acquire() as conn:
        user = await conn.fetchrow(
            'SELECT id, language, "emailVerified" FROM "User" WHERE email = $1', email
        )
    if user is None:
        # Silent — no user enumeration.
        return {"success": True}

    if user["emailVerified"] is not None:
        return await _prose_error(400, K_EMAIL_ALREADY_VERIFIED, language)

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
                'DELETE FROM "VerificationToken" WHERE "userId" = $1', user["id"]
            )
            await conn.execute(
                'INSERT INTO "VerificationToken" (id, token, "userId", "expiresAt") '
                "VALUES ($1, $2, $3, NOW() + ($4::int * INTERVAL '1 hour'))",
                str(uuid.uuid4()), token, user["id"], timeout_hours,
            )

    # Mirrored: email AFTER commit. Email content language = profile language.
    await send_verification_email(_db_pool, email, token, user_language)

    return {"success": True}
