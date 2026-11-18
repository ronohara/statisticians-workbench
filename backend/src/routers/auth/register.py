"""
User Registration Router — P2 Group 5, item 20 (Prisma-removal plan).

Drop-in replacement for the frontend Prisma handler:
  frontend/app/api/register/route.ts   (POST /api/register)

UNAUTHENTICATED (public path — the frontend proxy lists /api/register in
publicPaths). No HTTPBearer gate, no get_current_language dependency.

CLEAN VALIDATION (no JS-coercion emulation — see workbench-documents/development-records/code-quirks.md, the
item-9 coercion-defect entry). The frontend runs the email regex over a
String()-coerced value and feeds non-string passwords into validatePassword;
that coercion is a data-integrity defect, not a behaviour to recreate. Here:

  - email: must be a non-empty string matching the frontend regex, else 400
    invalid_email. (Observable parity with the frontend for all sane inputs;
    a non-string email is rejected at the gate instead of String()-coerced.)
  - password: must be a non-empty string, else 400 missing_fields. A
    non-string password never reaches validate_password — no .length-skip,
    no String()-coerced regex tests, no array->TypeError->500 path.
  - name: string or null; a truthy non-string name -> 500 (the frontend's
    Prisma String? rejection observable, mirrored as validation-not-coercion).
  - language: non-empty string or "en" (the frontend's `language || "en"`).

Check order mirrors the frontend exactly: body parse -> email regex ->
missing fields -> GlobalSettings -> password validation -> maxRegistrations
-> email-exists -> transaction (User + optional VerificationToken) -> email.
RegistrationMode gates this: mode 0 auto-verifies (no token/email), mode 1 is
rejected 403 (admin-created only), mode 2 leaves the user unverified with no
token/email (admin verifies), mode 4 is the token + email flow (pre-existing).

Translation (option b): the coded envelope {error: code, message} with the
REGISTER registry keyed by the canonical key (one name per key). The
password_validation_failed message is composed by localizing each failing
validation rule through t() (the shared validation.password.* keys), and the
"Registration limit reached (maximum N users)." template (limit_reached) is
routed through t() with a {max_reg} placeholder. t() language = the body's
language field (fallback "en").

Email-after-commit (item 24): the email is sent AFTER the transaction commits
(correct — sending before commit risks emailing for a rolled-back user). An
email failure no longer returns a partial-commit 500; the response is
{success, requiresVerification, verificationEmailFailed: true} so the client
can prompt the resend flow. See workbench-documents/development-records/code-quirks.md.
"""

import datetime
import json
import logging
import re
import secrets
import uuid

import bcrypt

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.routers.auth.translations import REGISTER
from src.utils.email import send_verification_email
from src.utils.password_validation import validate_password
from src.utils.translation import t

router = APIRouter(tags=["register"])
_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


_EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

E_INVALID_EMAIL = "api.register.invalid_email"
E_MISSING_FIELDS = "api.register.missing_fields"
E_SETTINGS_NOT_FOUND = "api.register.settings_not_found"
E_PASSWORD_VALIDATION_FAILED = "api.register.password_validation_failed"
E_LIMIT_REACHED = "api.register.limit_reached"
E_EMAIL_EXISTS = "api.register.email_exists"
E_REGISTRATION_DISABLED = "api.register.registration_disabled"
E_INTERNAL_ERROR = "api.register.internal_error"


async def _error(status: int, code: str, language: str, **kwargs) -> JSONResponse:
    """Coded-envelope error routed through t() (option b). The wire `error`
    code and the REGISTER registry key are the same canonical string — one
    name per key, no alias."""
    message = await t(_db_pool, language, REGISTER[code], **kwargs)
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def _raw_error(status: int, code: str, message: str) -> JSONResponse:
    """Dynamic-message passthrough (the frontend's own inline constructions,
    reproduced byte-identically)."""
    return JSONResponse(status_code=status, content={"error": code, "message": message})


@router.post("/api/register")
async def register(request: Request):
    try:
        # req.json() throws on empty/malformed body -> 500.
        try:
            body = json.loads(await request.body() or b"")
        except Exception:
            return await _error(500, E_INTERNAL_ERROR, "en")
        if body is None:
            # Destructuring null throws in the frontend -> 500.
            return await _error(500, E_INTERNAL_ERROR, "en")
        if not isinstance(body, dict):
            # Destructuring an array/string/number yields all-undefined.
            body = {}

        language = body.get("language")
        user_language = language if isinstance(language, str) and language else "en"

        email = body.get("email")
        if not isinstance(email, str) or not _EMAIL_RE.fullmatch(email):
            return await _error(400, E_INVALID_EMAIL, user_language)

        password = body.get("password")
        if not isinstance(password, str) or not password:
            return await _error(400, E_MISSING_FIELDS, user_language)

        name = body.get("name")
        if name is not None and not isinstance(name, str):
            # Prisma String? rejects a truthy non-string -> 500.
            return await _error(500, E_INTERNAL_ERROR, user_language)

        async with _db_pool.acquire() as conn:
            settings = await conn.fetchrow(
                'SELECT "passwordPolicy", "passwordPolicyCustom", "maxRegistrations", '
                '"emailVerificationTimeout", "defaultMaxUploadSizeMB", "defaultMaxUploadCount", '
                '"registrationMode" '
                'FROM "GlobalSettings" WHERE id = 1'
            )
        if settings is None:
            return await _error(500, E_SETTINGS_NOT_FOUND, user_language)

        registration_mode = settings["registrationMode"]
        if registration_mode == 1:
            return await _error(403, E_REGISTRATION_DISABLED, user_language)

        policy_name = settings["passwordPolicy"] or "medium"
        custom = settings["passwordPolicyCustom"]
        if not isinstance(custom, dict):
            custom = None

        errors = validate_password(password, policy_name, custom)
        if errors:
            messages = [await t(_db_pool, user_language, key, **kwargs) for key, kwargs in errors]
            return _raw_error(400, E_PASSWORD_VALIDATION_FAILED, " ".join(messages))

        max_reg = settings["maxRegistrations"]
        if max_reg is not None:
            async with _db_pool.acquire() as conn:
                user_count = await conn.fetchval('SELECT count(*) FROM "User"')
            if user_count >= max_reg:
                return await _error(403, E_LIMIT_REACHED, user_language, max_reg=max_reg)

        async with _db_pool.acquire() as conn:
            existing = await conn.fetchrow('SELECT id FROM "User" WHERE email = $1', email)
        if existing is not None:
            return await _error(400, E_EMAIL_EXISTS, user_language)

        hashed = bcrypt.hashpw(password.encode("utf-8"),
                               bcrypt.gensalt(rounds=10)).decode("utf-8")
        token = secrets.token_hex(32)
        timeout_hours = settings["emailVerificationTimeout"] \
            if settings["emailVerificationTimeout"] is not None else 24
        user_id = str(uuid.uuid4())
        # Aware, not naive. The `replace(tzinfo=None)` this used to carry built a UTC wall
        # clock with no zone, and `emailVerified` has been a `timestamptz` since Item 7 of
        # the timestamp plan — so asyncpg interpreted the naive value in the *client
        # process's* zone and the row landed seven hours in the past on a machine set to
        # Asia/Bangkok. Measured 2026-11-08: 25,200 s early, against 0 s for the aware
        # value. Nothing branches on the column (every read is IS NULL), so no user saw a
        # wrong answer — but the stored instant was wrong.
        email_verified = datetime.datetime.now(datetime.timezone.utc) if registration_mode == 0 else None

        async with _db_pool.acquire() as conn:
            async with conn.transaction():
                await conn.execute(
                    'INSERT INTO "User" '
                    '(id, email, password, name, "emailVerified", "maxUploadSizeMB", '
                    '"maxUploadCount", language, "emailNotifications", "darkMode", "updatedAt") '
                    'VALUES ($1, $2, $3, $4, $5, $6, $7, $8, false, false, NOW())',
                    user_id, email, hashed, name, email_verified,
                    settings["defaultMaxUploadSizeMB"] or 0,
                    settings["defaultMaxUploadCount"] or 0,
                    user_language,
                )
                # NOTE, deliberately absent: "modelSlowThresholdSeconds" is NOT copied here,
                # unlike the two upload limits above. Those are a snapshot decided once at
                # registration; the threshold must resolve live, so a new user's column
                # stays NULL and they inherit the global default as it changes. Copying it
                # would freeze the value at the moment of signup and silently stop tracking
                # the admin's setting — the bug this column's nullability exists to avoid.
                if registration_mode == 4:
                    await conn.execute(
                        'INSERT INTO "VerificationToken" (id, token, "userId", "expiresAt") '
                        "VALUES ($1, $2, $3, NOW() + ($4::int * INTERVAL '1 hour'))",
                        str(uuid.uuid4()), token, user_id, timeout_hours,
                    )

        # Item 24: email is sent AFTER commit. A sendmail failure here is no
        # longer a partial-commit 500 — the user is already committed, so we
        # surface success with a flag the client uses to prompt the resend flow.
        # Only mode 4 sends the verification email; modes 0/2 skip it.
        if registration_mode == 4:
            try:
                await send_verification_email(_db_pool, email, token, user_language)
            except Exception:
                return {
                    "success": True,
                    "requiresVerification": True,
                    "verificationEmailFailed": True,
                }
            return {"success": True, "requiresVerification": True}

        # Mode 0: auto-verified (ready now). Mode 2: unverified, pending admin.
        return {"success": True, "requiresVerification": registration_mode == 2}
    except Exception:
        logging.exception("Unexpected error in POST /api/register")
        return await _error(500, E_INTERNAL_ERROR, user_language)
