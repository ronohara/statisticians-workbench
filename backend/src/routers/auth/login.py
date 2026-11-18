"""
User Login Router — P4 (Prisma-removal plan).

Backend-authorized credential verification for NextAuth's Credentials
provider. Called server-side by the rewritten `lib/auth.ts` authorize; the
frontend `[...nextauth]` route stays the NextAuth surface.

UNAUTHENTICATED (public — no HTTPBearer gate), like /api/register.

CLEAN, not parity-mirrored (P3 closed the parity matrix; 2026-08-23):
  - The frontend's old two-message split for invalid credentials ("Invalid
    credentials" when the user is missing vs "Invalid email or password."
    when the password is wrong) is a user-enumeration signal and an
    inconsistency. Here a single auth.login_invalid_credentials message
    covers missing / unknown / wrong-password alike.
  - Password is verified BEFORE account status (deleted / email-not-verified)
    is revealed, so a wrong-password attempt cannot learn an account's status.

Success: {id, email, name, isAdmin, isExampleUser, language}. The
example-user language override stays in the frontend authorize (step 2).

Error: {error: <canonical key>, message: <localized>, language: <lang>}.
"""

import json

import bcrypt
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.routers.auth.translations import LOGIN
from src.utils.translation import t

router = APIRouter(tags=["login"])
_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


E_INVALID_CREDENTIALS = "auth.login_invalid_credentials"
E_ACCOUNT_DELETED = "auth.account_deleted"
E_EMAIL_NOT_VERIFIED = "auth.email_not_verified"
E_INTERNAL_ERROR = "auth.internal_error"


async def _error(status: int, code: str, language: str) -> JSONResponse:
    message = await t(_db_pool, language, LOGIN[code])
    return JSONResponse(
        status_code=status,
        content={"error": code, "message": message, "language": language},
    )


@router.post("/api/auth/login")
async def login(request: Request):
    err_lang = "en"
    try:
        try:
            body = json.loads(await request.body() or b"")
        except Exception:
            body = None
        if not isinstance(body, dict):
            body = {}

        email = body.get("email")
        password = body.get("password")
        lang = body.get("language")
        if isinstance(lang, str) and lang:
            err_lang = lang

        # Missing fields, unknown email, or wrong password all produce the
        # same invalid-credentials result — no user enumeration.
        if (
            not isinstance(email, str)
            or not email
            or not isinstance(password, str)
            or not password
        ):
            return await _error(401, E_INVALID_CREDENTIALS, err_lang)

        async with _db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT id, email, name, password, "isAdmin", "isExampleUser", '
                '"emailVerified", "deletedAt", language FROM "User" WHERE email = $1',
                email,
            )

        if row is None or not row["password"]:
            return await _error(401, E_INVALID_CREDENTIALS, err_lang)

        stored = row["language"]
        err_lang = stored if isinstance(stored, str) and stored else "en"

        if not bcrypt.checkpw(
            password.encode("utf-8"), row["password"].encode("utf-8")
        ):
            return await _error(401, E_INVALID_CREDENTIALS, err_lang)

        if row["deletedAt"] is not None:
            return await _error(403, E_ACCOUNT_DELETED, err_lang)

        if row["isAdmin"] is not True and row["emailVerified"] is None:
            return await _error(403, E_EMAIL_NOT_VERIFIED, err_lang)

        return {
            "id": row["id"],
            "email": row["email"],
            "name": row["name"],
            "isAdmin": row["isAdmin"] is True,
            "isExampleUser": row["isExampleUser"] is True,
            "language": err_lang,
        }
    except Exception:
        return await _error(500, E_INTERNAL_ERROR, err_lang)
