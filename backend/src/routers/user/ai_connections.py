"""
User AI Connections Router — P2 Group 3, item 12 (Prisma-removal plan).

Drop-in replacement for the frontend Prisma handler:
  frontend/app/api/user/ai-connections/route.ts   (GET · POST · PATCH · DELETE)

Contract parity:
  - GET: any authenticated user (no example block) lists their own rows plus
    rows shared to their group (isShared=true AND aiConnectionGroup = the
    user's group). A missing user row (ghost session) reads group "00" — a
    ghost GET therefore returns the shared-"00" rows, NOT a 404. apiKey is
    AES-256-GCM decrypted (null when absent or corrupt); the numeric
    connectionId is mirrored as id (string) alongside the Prisma spread;
    providerDetails is the AIProvider lookup (or null for an orphan
    provider code). Rows order by createdAt ASC.
  - POST: example users blocked (403) BEFORE the body is read. name/provider
    JS-falsy -> 400 missing_fields; provider row lookup (400
    provider_not_found with the dynamic `Provider "{code}" not found`
    message); requiresApiKey && !apiKey -> 400 api_key_required; duplicate
    (userId, name) -> 400 connection_name_exists; apiKey AES-encrypted on
    store. Body quirks mirrored: a null body -> 500 (destructuring throws);
    a non-object body (array/string/number) -> 400 (destructuring yields
    all-undefined); truthy non-strings ([]/{}/numbers) survive the falsy
    guards and hit Prisma validation -> 500 (String/Boolean fields);
    shared=1/"x"/[] -> 500 (Prisma Boolean).
  - PATCH: id JS-falsy -> 400 missing_fields; id strict-validated as a
    decimal-digit string -> 400 invalid_connection_id (item 11); the row
    lookup is the caller's own row, or — for an administrator — a row shared
    to the caller's group
    (404 connection_not_found otherwise); the provider
    re-validation runs only when the new provider is truthy AND different;
    apiKey null/"" clears the stored key; absent fields are untouched; a
    fully empty update is a 200 no-op (Prisma data {}). P2025 -> 500.
  - DELETE: query-param id (strict-validated as PATCH); the caller's own row,
    or — for an administrator — a row shared to the caller's group (404
    otherwise); clears User.defaultAIConnectionId when it points at the deleted
    row — same transaction; 200 success:true.

Translation note: all responses route through t() with USER registry keys
(item 14); the drifted user.* namespaces are reconciled to api.user.* (item 35).

Auth: HTTPBearer(auto_error=False) + _auth (JWT decode) shared from
admin.users.py; the no-token 401 {"detail": "Not authenticated"} comes from
the get_current_language dependency (crud.py security=HTTPBearer()).
Encryption: utils/encryption.encrypt_field / decrypt_field_or_null
(AES-256-GCM iv:authTag:ciphertext base64, byte-compatible with @/lib/encryption).
"""

import json
import logging
import time
from datetime import timezone

import httpx

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth, _is_example, _is_admin, _user_group
from src.routers.user.translations import USER
from src.utils.encryption import encrypt_field, decrypt_field_or_null
from src.utils.connection_timeouts import resolve_connection_timeouts
from src.utils.connection_timeouts import (
    CONNECT_TIMEOUT_CEILING,
    PROBE_TIMEOUT_CEILING,
    validate_connect_timeout,
    validate_probe_timeout,
)
from src.utils.translation import t
from src.chat import test_registry
from src.chat import model_probe
from src.chat.connection import get_connection_details
from src.routers.user.model_results import record_result, ResultWriteRefused

logger = logging.getLogger(__name__)
# The provider-fetch helper lives in model_discovery now: the walk needs it, the fetch
# route needs it, and leaving it here meant the two modules imported each other. One
# direction — this module depends on that one — is what the go port's static imports
# require, and what Python was silently tolerating only while the import order happened
# to work.
from src.routers.user.model_discovery import (
    ConnectionNotFound,
    EmptyCatalogue,
    _ProviderFetchError,
    _fetch_models_from_provider,
    discover_connection,
)
from src.utils.timestamps import iso_utc


router = APIRouter(prefix="/api/user/ai-connections", tags=["user-ai-connections"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ============================================================
# FRONTEND ERROR-CODE CONTRACT (stable API surface — do not rename)
# ============================================================

E_UNAUTHORIZED = "api.auth.unauthorized"
E_EXAMPLE_BLOCKED = "api.user.example_blocked"
E_MISSING_FIELDS = "api.user.missing_fields"
E_PROVIDER_NOT_FOUND = "api.user.provider_not_found"
E_API_KEY_REQUIRED = "api.user.api_key_required"
E_CONNECTION_NAME_EXISTS = "api.user.connection_name_exists"
E_CONNECTION_NOT_FOUND = "api.user.connection_not_found"
E_INTERNAL_ERROR = "api.user.internal_error"
E_INVALID_CONNECTION_ID = "api.user.invalid_connection_id"
# Plan workbench-AI-timeout-policy-plan.html, Item 2. Three codes rather than one
# "invalid timeout": a word, a decimal and a number above the ceiling are three
# different mistakes, and the third names both values so the administrator can see
# which one to change.
E_INVALID_CONNECT_TIMEOUT = "api.user.invalid_connect_timeout"
E_INVALID_PROBE_TIMEOUT = "api.user.invalid_probe_timeout"
E_CONNECT_EXCEEDS_PROBE = "api.user.connect_timeout_exceeds_probe"

async def _error(status: int, code: str, language: str, **kwargs):
    """Coded-envelope error routed through t() (item 14)."""
    message = await t(_db_pool, language, USER[code], **kwargs)
    return JSONResponse(status_code=status, content={"error": code, "message": message})


def _js_truthy(value) -> bool:
    """JS truthiness for JSON values: false, 0, "", null are falsy;
    [] and {} are TRUTHY (callers must let those fall through to the
    Prisma-validation 500 paths)."""
    return not (value is None or value is False or value == "" or value == 0)



def _provider_details(row):
    if row is None:
        return None
    return {"code": row["code"], "name": row["name"],
            "requiresApiKey": row["requiresApiKey"]}


def _conn_body(row, provider_details, api_key=None, with_id=False):
    """The Prisma spread shape: scalar columns in model order, then the
    JS overrides (apiKey, aiConnectionGroup, isShared) and additions."""
    out = {
        "connectionId": row["connectionId"],
        "userId": row["userId"],
        "name": row["name"],
        "provider": row["provider"],
        "apiKey": api_key if api_key is not None else None,
        "endpoint": row["endpoint"],
        "defaultModel": row["defaultModel"],
        "createdAt": iso_utc(row["createdAt"]),
        "updatedAt": iso_utc(row["updatedAt"]),
        "aiConnectionGroup": row["aiConnectionGroup"] or "00",
        "isShared": row["isShared"],
        # The two timeouts (plan workbench-AI-timeout-policy-plan.html, Item 2).
        # Null means "inherit the workbench default", which is what an unset field on
        # the page will show as blank rather than as a number the connection does not
        # actually hold. Every caller of this function reads its row with SELECT * or
        # RETURNING *, so the columns are always present.
        "connectTimeoutSeconds": row["connectTimeoutSeconds"],
        "probeTimeoutSeconds": row["probeTimeoutSeconds"],
    }
    if with_id:
        out["id"] = str(row["connectionId"])
    out["providerDetails"] = provider_details
    return out


async def _fetch_provider(conn, code):
    return await conn.fetchrow(
        'SELECT code, name, "requiresApiKey" FROM "AIProvider" WHERE code = $1',
        code,
    )


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("")
async def get_ai_connections(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)

        async with _db_pool.acquire() as conn:
            user = await conn.fetchrow(
                'SELECT "userGroup" FROM "User" WHERE id = $1', uid
            )
            user_group = user["userGroup"] if user else None
            user_group = user_group or "00"

            rows = await conn.fetch(
                'SELECT * FROM "UserAIConnection" '
                'WHERE "userId" = $1 OR ("isShared" = true AND "aiConnectionGroup" = $2) '
                'ORDER BY "createdAt" ASC',
                uid, user_group,
            )
            codes = sorted({r["provider"] for r in rows})
            if codes:
                provider_rows = await conn.fetch(
                    'SELECT code, name, "requiresApiKey" FROM "AIProvider" WHERE code = ANY($1::text[])',
                    codes,
                )
            else:
                provider_rows = []
        provider_map = {p["code"]: _provider_details(p) for p in provider_rows}

        connections = []
        for r in rows:
            body = _conn_body(
                r,
                provider_map.get(r["provider"]),
                api_key=decrypt_field_or_null(r["apiKey"]),
                with_id=True,
            )
            connections.append(body)
        return {"connections": connections}
    except Exception:
        return await _error(500, E_INTERNAL_ERROR, language)


# ============================================================
# FAILURE CLASSES → MESSAGES (plan Item 5 of workbench-AI-timeout-policy-plan.html)
# ============================================================

#: Statuses that mean "this connection does not serve that model" rather than "the
#: provider is broken". 404 is the obvious one; 400 is here because OpenRouter
#: answers a bad model name with 400 and the sentence "not a valid model ID" — the
#: case F5 measured, where the old token search found no 404 and reported the model
#: as unreachable.
_NO_SUCH_MODEL_STATUSES = frozenset({400, 404})

#: One message per failure class. Selected by the class the PROVIDER supplied, never
#: by searching the detail text — a string cannot be classified reliably, which is
#: what F5 demonstrated.
_TRANSPORT_MESSAGE_BY_CLASS = {
    "connect_refused": "api.user.test_connect_refused",
    "connect_timeout": "api.user.test_connect_timeout",
    "dns_failure": "api.user.test_dns_failure",
    "tls_failure": "api.user.test_tls_failure",
    "read_timeout": "api.user.test_read_timeout",
    "http_status": "api.user.test_http_status",
    "budget_exhausted": "api.user.test_budget_exhausted",
}
E_TRANSPORT_OTHER = "api.user.test_other_failure"


# ============================================================
# CONNECTION TIMEOUTS ON WRITE (plan workbench-AI-timeout-policy-plan.html, Item 2)
# ============================================================

def _timeout_updates(body, stored_connect, stored_probe):
    """The two timeout fields from a request body, validated, or the refusal to send.

    Returns `(updates, error)`, exactly one of which is None. `updates` holds only
    the fields the request named, so an absent field means "leave it" and an explicit
    null means "clear back to inherit" — the merge semantics the tuning endpoints
    already use, and the distinction 0018's nullable columns exist for.

    `stored_*` are what the row holds now, so the cross-check sees the pair the row
    will have after this write rather than only what the request carried. Without
    that, lowering the test timeout below an existing connect timeout would slip
    through and be silently clamped at read time — which is the behaviour D6 accepted
    for the cross-table case and not for this one, where a write is available to refuse.
    """
    updates = {}
    for field, validate, ceiling, code in (
        ("connectTimeoutSeconds", validate_connect_timeout,
         CONNECT_TIMEOUT_CEILING, E_INVALID_CONNECT_TIMEOUT),
        ("probeTimeoutSeconds", validate_probe_timeout,
         PROBE_TIMEOUT_CEILING, E_INVALID_PROBE_TIMEOUT),
    ):
        if field not in body:
            continue
        raw = body[field]
        if raw is None:
            # Explicit null: back to inheriting the workbench default.
            updates[field] = None
            continue
        if validate(raw) is not None:
            return None, (code, {"ceiling": ceiling})
        updates[field] = raw

    # `.get(field, stored)` rather than `.get(field) or stored`: an explicit None means
    # cleared, and `or` would replace it with the stored value and check a pair the
    # write is not producing.
    merged_connect = updates.get("connectTimeoutSeconds", stored_connect)
    merged_probe = updates.get("probeTimeoutSeconds", stored_probe)
    if (merged_connect is not None and merged_probe is not None
            and merged_connect > merged_probe):
        return None, (E_CONNECT_EXCEEDS_PROBE,
                      {"connect": merged_connect, "probe": merged_probe})

    return updates, None


@router.post("")
async def post_ai_connections(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)

        if await _is_example(uid):
            return await _error(403, E_EXAMPLE_BLOCKED, language)

        # req.json() throws on an empty/malformed body -> caught -> 500.
        try:
            body = json.loads(await req.body() or b"")
        except Exception:
            return await _error(500, E_INTERNAL_ERROR, language)
        if body is None:
            # Destructuring null throws in the frontend -> 500.
            return await _error(500, E_INTERNAL_ERROR, language)
        if not isinstance(body, dict):
            # Destructuring an array/string/number yields all-undefined.
            body = {}

        name = body.get("name")
        provider = body.get("provider")
        api_key = body.get("apiKey")
        endpoint = body.get("endpoint")
        shared = body.get("shared")
        ai_connection_group = body.get("aiConnectionGroup")

        if not _js_truthy(name) or not _js_truthy(provider):
            return await _error(400, E_MISSING_FIELDS, language)

        if not isinstance(provider, str):
            # Prisma String where-code rejects truthy non-strings -> 500.
            return await _error(500, E_INTERNAL_ERROR, language)

        async with _db_pool.acquire() as conn:
            provider_row = await _fetch_provider(conn, provider)
        if provider_row is None:
            return await _error(400, E_PROVIDER_NOT_FOUND, language, provider=provider)

        if provider_row["requiresApiKey"] and not _js_truthy(api_key):
            return await _error(400, E_API_KEY_REQUIRED, language)

        if not isinstance(name, str):
            # Clean validation (was a Prisma no-op quirk + 500 coercion): a
            # non-string name — including an empty object {} — is rejected 400.
            return await _t_error(400, "api.user.invalid_name", language)

        async with _db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                'SELECT "connectionId" FROM "UserAIConnection" '
                'WHERE "userId" = $1 AND name = $2',
                uid, name,
            )
        if existing is not None:
            return await _error(400, E_CONNECTION_NAME_EXISTS, language)

        # encrypt(apiKey) — truthy non-strings throw in the frontend -> 500.
        encrypted_api_key = None
        if _js_truthy(api_key):
            if not isinstance(api_key, str):
                return await _error(500, E_INTERNAL_ERROR, language)
            encrypted_api_key = encrypt_field(api_key)

        # endpoint || null — truthy non-strings hit Prisma String? -> 500.
        endpoint_value = endpoint if _js_truthy(endpoint) else None
        if endpoint_value is not None and not isinstance(endpoint_value, str):
            return await _error(500, E_INTERNAL_ERROR, language)

        # aiConnectionGroup || "00" — truthy non-strings -> 500.
        group_value = ai_connection_group if _js_truthy(ai_connection_group) else "00"
        if not isinstance(group_value, str):
            return await _error(500, E_INTERNAL_ERROR, language)

        # shared || false — truthy non-booleans hit Prisma Boolean -> 500.
        shared_value = shared if _js_truthy(shared) else False
        if not isinstance(shared_value, bool):
            return await _error(500, E_INTERNAL_ERROR, language)

        # The two timeouts. An absent field inserts NULL, which is "inherit the
        # workbench default" — the same meaning it has on every other connection.
        timeout_updates, timeout_error = _timeout_updates(body, None, None)
        if timeout_error is not None:
            code, kwargs = timeout_error
            return await _error(400, code, language, **kwargs)

        async with _db_pool.acquire() as conn:
            created = await conn.fetchrow(
                'INSERT INTO "UserAIConnection" '
                '("userId", name, provider, "apiKey", endpoint, "aiConnectionGroup", "isShared", '
                ' "connectTimeoutSeconds", "probeTimeoutSeconds", "updatedAt") '
                'VALUES ($1, $2, $3, $4, $5, $6, $7, $8, $9, NOW()) RETURNING *',
                uid, name, provider, encrypted_api_key, endpoint_value,
                group_value, shared_value,
                timeout_updates.get("connectTimeoutSeconds"),
                timeout_updates.get("probeTimeoutSeconds"),
            )
            provider_details_row = await _fetch_provider(conn, provider)
        # A ghost user (row gone, FK cascade) raises here -> caught -> 500.

        return {
            "success": True,
            "connection": _conn_body(
                created,
                _provider_details(provider_details_row),
                with_id=True,
            ),
        }
    except Exception:
        return await _error(500, E_INTERNAL_ERROR, language)


@router.patch("")
async def patch_ai_connections(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)

        if await _is_example(uid):
            return await _error(403, E_EXAMPLE_BLOCKED, language)

        try:
            body = json.loads(await req.body() or b"")
        except Exception:
            return await _error(500, E_INTERNAL_ERROR, language)
        if body is None:
            return await _error(500, E_INTERNAL_ERROR, language)
        if not isinstance(body, dict):
            body = {}

        raw_id = body.get("id")
        name = body.get("name")
        provider = body.get("provider")
        api_key = body.get("apiKey")
        endpoint = body.get("endpoint")
        shared = body.get("shared")
        ai_connection_group = body.get("aiConnectionGroup")

        if not _js_truthy(raw_id):
            return await _error(400, E_MISSING_FIELDS, language)

        # Strict id validation (no JS parseInt/String coercion — item 11).
        if not isinstance(raw_id, str) or not raw_id.isdigit():
            return await _error(400, E_INVALID_CONNECTION_ID, language)
        parsed_id = int(raw_id)

        # An administrator may also act on a connection shared to their group —
        # the rows GET returns with isOwn=false. Everyone else is confined to
        # their own rows, and a miss is the same 404 either way, so a row's
        # existence is never disclosed to an unauthorised caller.
        admin_group = None
        if await _is_admin(uid):
            admin_group = (await _user_group(uid)) or "00"

        async with _db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                'SELECT * FROM "UserAIConnection" WHERE "connectionId" = $1 AND "userId" = $2',
                parsed_id, uid,
            )
            if existing is None and admin_group is not None:
                existing = await conn.fetchrow(
                    'SELECT * FROM "UserAIConnection" '
                    'WHERE "connectionId" = $1 AND "isShared" = true '
                    'AND "aiConnectionGroup" = $2',
                    parsed_id, admin_group,
                )
        if existing is None:
            return await _error(404, E_CONNECTION_NOT_FOUND, language)

        # The two timeouts, checked against what the row holds now as well as what the
        # request carries (Item 2). `existing` is already read above, so the cross-check
        # costs no extra query.
        timeout_updates, timeout_error = _timeout_updates(
            body,
            existing["connectTimeoutSeconds"],
            existing["probeTimeoutSeconds"],
        )
        if timeout_error is not None:
            code, kwargs = timeout_error
            return await _error(400, code, language, **kwargs)

        if _js_truthy(provider) and provider != existing["provider"]:
            if not isinstance(provider, str):
                return await _error(500, E_INTERNAL_ERROR, language)
            async with _db_pool.acquire() as conn:
                provider_row = await _fetch_provider(conn, provider)
            if provider_row is None:
                return await _error(400, E_PROVIDER_NOT_FOUND, language, provider=provider)
            has_api_key = _js_truthy(api_key) or _js_truthy(existing["apiKey"])
            if provider_row["requiresApiKey"] and not has_api_key:
                return await _error(400, E_API_KEY_REQUIRED, language)

        update = {}
        if name is not None or "name" in body:
            # name !== undefined — null/non-string hit Prisma String -> 500.
            if not isinstance(name, str):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["name"] = name
        if provider is not None or "provider" in body:
            if not isinstance(provider, str):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["provider"] = provider
        if endpoint is not None or "endpoint" in body:
            endpoint_value = endpoint if _js_truthy(endpoint) else None
            if endpoint_value is not None and not isinstance(endpoint_value, str):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["endpoint"] = endpoint_value
        if ai_connection_group is not None or "aiConnectionGroup" in body:
            # No || "00" coercion here — stored as-is; null/non-string -> 500.
            if not isinstance(ai_connection_group, str):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["aiConnectionGroup"] = ai_connection_group
        if shared is not None or "shared" in body:
            # No || false coercion here — null/non-boolean -> 500.
            if not isinstance(shared, bool):
                return await _error(500, E_INTERNAL_ERROR, language)
            update["isShared"] = shared
        if api_key is not None or "apiKey" in body:
            if api_key is None or api_key == "":
                update["apiKey"] = None
            else:
                if not isinstance(api_key, str):
                    return await _error(500, E_INTERNAL_ERROR, language)
                update["apiKey"] = encrypt_field(api_key)

        # The timeout fields were validated above, before the provider change could
        # return an error — so a request that fails on its provider does not half-apply
        # a timeout. Merged here rather than in the loop above because their validation
        # needs the stored row, which the loop does not have.
        update.update(timeout_updates)

        async with _db_pool.acquire() as conn:
            if update:
                sets = ", ".join(f'"{c}" = ${i + 1}' for i, c in enumerate(update))
                values = list(update.values())
                updated = await conn.fetchrow(
                    f'UPDATE "UserAIConnection" SET {sets}, "updatedAt" = NOW() '
                    f'WHERE "connectionId" = ${len(values) + 1} RETURNING *',
                    *values, parsed_id,
                )
            else:
                # Prisma data {} — no-op update returns the row, 200.
                updated = await conn.fetchrow(
                    'SELECT * FROM "UserAIConnection" WHERE "connectionId" = $1',
                    parsed_id,
                )
            if updated is None:
                # Row vanished between existence check and UPDATE → 404.
                return await _error(404, E_CONNECTION_NOT_FOUND, language)
            provider_details_row = await _fetch_provider(conn, updated["provider"])

        return {
            "success": True,
            "connection": _conn_body(
                updated,
                _provider_details(provider_details_row),
                with_id=True,
            ),
        }
    except Exception:
        return await _error(500, E_INTERNAL_ERROR, language)


@router.delete("")
async def delete_ai_connections(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)

        if await _is_example(uid):
            return await _error(403, E_EXAMPLE_BLOCKED, language)

        raw_id = req.query_params.get("id")
        if not raw_id or not _js_truthy(raw_id):
            return await _error(400, E_MISSING_FIELDS, language)

        # Strict id validation (no JS parseInt/String coercion — item 11).
        if not raw_id.isdigit():
            return await _error(400, E_INVALID_CONNECTION_ID, language)
        parsed_id = int(raw_id)

        # An administrator may also delete a connection shared to their group —
        # the rows GET returns with isOwn=false. Everyone else is confined to
        # their own rows, and a miss is the same 404 either way, so a row's
        # existence is never disclosed to an unauthorised caller.
        admin_group = None
        if await _is_admin(uid):
            admin_group = (await _user_group(uid)) or "00"

        async with _db_pool.acquire() as conn:
            existing = await conn.fetchrow(
                'SELECT "connectionId" FROM "UserAIConnection" '
                'WHERE "connectionId" = $1 AND "userId" = $2',
                parsed_id, uid,
            )
            if existing is None and admin_group is not None:
                existing = await conn.fetchrow(
                    'SELECT "connectionId" FROM "UserAIConnection" '
                    'WHERE "connectionId" = $1 AND "isShared" = true '
                    'AND "aiConnectionGroup" = $2',
                    parsed_id, admin_group,
                )
            if existing is None:
                return await _error(404, E_CONNECTION_NOT_FOUND, language)

            # prisma.$transaction([updateMany, delete]) — one transaction.
            async with conn.transaction():
                await conn.execute(
                    'UPDATE "User" SET "defaultAIConnectionId" = NULL '
                    'WHERE id = $1 AND "defaultAIConnectionId" = $2',
                    uid, parsed_id,
                )
                await conn.execute(
                    'DELETE FROM "UserAIConnection" WHERE "connectionId" = $1',
                    parsed_id,
                )

        return {"success": True}
    except Exception:
        return await _error(500, E_INTERNAL_ERROR, language)


# ============================================================
# ITEM 13 — GET /{connectionId}/models (models sub-route)
# ============================================================
#
# Frontend source:
#   frontend/app/api/user/ai-connections/[connectionId]/models/route.ts
#
# Contract parity:
#   - GET only. Any authenticated user (no example block) lists the models THIS
#     connection serves, from ConnectionModelIntersect (Item 17), scoped to a
#     connection they own OR one shared to their group.
#   - connectionId strict-validated as a decimal-digit string -> 400
#     invalid_connection_id (item 11). A valid id with no matching
#     (own|shared) row -> 404.
#   - ?enabled=true (EXACT string) filters to enabled rows; any other value
#     (or absent) is ignored. Order: preferred DESC, modelName ASC.
#   - Response: {"models": [{id, modelCode, modelName, enabled, preferred,
#     comment}]} — id is the raw Int, modelCode duplicates modelName.
#
# ERROR SHAPE (resolved — see workbench-documents/development-records/code-quirks.md item 1): sub-route errors
# use the coded envelope {error: <canonical key>, message: <translated>},
# matching the parent route. Routed through t() with canonical api.* keys.


async def _t_error(status_code: int, key: str, language: str, **kwargs) -> JSONResponse:
    """Coded-envelope error routed through t(): {error: <canonical key>,
    message: <translated>} — matches the parent route's shape."""
    tk = USER[key]
    message = await t(_db_pool, language, tk, **kwargs)
    return JSONResponse(status_code=status_code, content={"error": tk.key, "message": message})


@router.get("/{connectionId}/models")
async def get_connection_models(
    connectionId: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(401, "api.auth.unauthorized", language)

        if not connectionId.isdigit():
            return await _t_error(400, "api.user.invalid_connection_id", language)
        parsed_id = int(connectionId)

        enabled_only = req.query_params.get("enabled") == "true"

        async with _db_pool.acquire() as conn:
            user = await conn.fetchrow(
                'SELECT "userGroup" FROM "User" WHERE id = $1', uid
            )
            user_group = (user["userGroup"] if user else None) or "00"

            # Existence and visibility only: the provider code is no longer needed
            # once the query starts at the connection intersect, so nothing is
            # carried forward that could drift from what the join actually uses.
            connection = await conn.fetchrow(
                'SELECT 1 AS visible FROM "UserAIConnection" '
                'WHERE "connectionId" = $1 AND ("userId" = $2 OR '
                '("isShared" = true AND "aiConnectionGroup" = $3))',
                parsed_id, uid, user_group,
            )

        if connection is None:
            return await _t_error(404, "api.user.connection_not_found", language)

        # The join starts at the CONNECTION intersect, not at the provider's
        # catalogue. That is the whole point of the redesign: `ProviderModel`
        # answered "what does this provider offer", which for a local provider is
        # the union of every host's sightings, so a connection appeared to serve
        # models it could not reach. This query cannot make that claim — a row
        # exists only where discovery saw the model on THIS connection.
        #
        # Capability comes from the model (a result about the model, whichever
        # server produced it) and the durations from the intersect (a result about
        # the server). Design rule 2, expressed as two columns in one row.
        query = (
            'SELECT m."id", m."modelName", m.enabled, m.preferred, m.comment, '
            '       m."modelTestResults" AS capability, '
            '       c."connectionTestResults" AS performance, '
            '       c."lastSeenAt" '
            'FROM public."ConnectionModelIntersect" c '
            'JOIN public."LLMModel" m ON m."id" = c."modelId" '
            'WHERE c."connectionId" = $1 '
            '  AND ($2::boolean = false OR m.enabled = true) '
            'ORDER BY m."preferred" DESC, m."modelName" ASC'
        )

        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(query, parsed_id, enabled_only)

        # `tests` is the registry of what CAN be tested, not a result: the page
        # builds its columns from it, so it stays beside the models rather than
        # inside them.
        #
        # `testResults` is back, keyed by test id, and now read from
        # `LLMModel."modelTestResults"` — the model's own record — instead of the
        # column Item 2 dropped. An untested model answers `{}`, never `null`: the
        # page indexes it directly (`m.testResults?.[t.id]`) and a null would force
        # every caller to defend against a shape the API is promising not to send.
        return {
            "tests": [
                {
                    "id": t.test_id,
                    "duration": t.duration,
                    "requiresDataset": t.requires_dataset,
                }
                for t in (test_registry.get(tid) for tid in test_registry.all_ids())
                if t is not None
            ],
            "models": [
                {
                    "id": r["id"],
                    "modelCode": r["modelName"],
                    "modelName": r["modelName"],
                    "enabled": r["enabled"],
                    "preferred": r["preferred"],
                    "comment": r["comment"],
                    "testResults": r["capability"] or {},
                    "connectionTestResults": r["performance"] or {},
                    "lastSeenAt": (
                        iso_utc(r["lastSeenAt"])
                    ),
                }
                for r in rows
            ]
        }
    except Exception:
        return await _t_error(500, "api.user.internal_error", language)


# ============================================================
# AI MODEL SUITABILITY — POST /{connectionId}/models/test
# ============================================================
#
# Runs one test against one model and records the result.
#
# Contract (plan Item 8):
#   - POST. Body {"model": <modelName>, "test": <testId>}. One test per
#     request, so a long `turn` cannot block a quick `tools`.
#   - Authorisation mirrors the models GET: the connection must be the
#     caller's own or shared to their group. No admin check — D4 settled that
#     any user who can read the connection may record a result, and every write
#     is attributed (`testedBy`).
#   - The model must already be in the provider's catalogue: an unknown model
#     is refused before any provider call, which also stops a caller recording
#     results against a model that does not exist.
#
# WHAT IS NOT RECORDED
#   A transport failure — no key, unknown provider, refused connection, HTTP
#   error, timeout — returns 400 and leaves the stored result untouched. Only
#   an observed behaviour becomes a verdict; see chat/model_probe.py.


@router.post("/{connectionId}/models/test")
async def test_connection_model(
    connectionId: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(401, "api.auth.unauthorized", language)

        if not connectionId.isdigit():
            return await _t_error(400, "api.user.invalid_connection_id", language)
        parsed_id = int(connectionId)

        try:
            body = json.loads(await req.body() or b"")
        except Exception:
            return await _t_error(500, "api.user.internal_error", language)
        if not isinstance(body, dict):
            body = {}

        model_name = body.get("model")
        test_id = body.get("test")

        if not _js_truthy(model_name) or not _js_truthy(test_id):
            return await _t_error(400, "api.user.missing_fields", language)
        if not isinstance(model_name, str) or not isinstance(test_id, str):
            return await _t_error(400, "api.user.missing_fields", language)

        definition = test_registry.get(test_id)
        if definition is None:
            return await _t_error(
                400, "api.user.unknown_test_id", language,
                test=test_id, known=", ".join(test_registry.all_ids()),
            )

        # THE CONNECTION IS RESOLVED THROUGH THE SHARED RESOLVER, NOT READ RAW.
        #
        # This route used to select `provider, "apiKey", endpoint` itself and pass the
        # column straight through. `endpoint` is nullable by design — NULL means "inherit
        # my provider's AIProvider.defaultEndpoint" — so a connection that stores no
        # endpoint of its own arrived here with a null and the provider refused it with
        # OPENAI_ENDPOINT_REQUIRED. Chat worked on the same connection because it goes
        # through this resolver, which applies the provider default; discovery worked
        # because it applies the same rule internally. Measured 2026-11-19: the AI-testing
        # page could not test `sample-bikestore-AI` (connection 310, deepseek, endpoint
        # NULL) while chat on it answered normally.
        #
        # The rule now lives in ONE place. This route also no longer spells out the
        # ownership/sharing predicate or the key decryption a second time: the resolver
        # owns all three, so a later change to any of them cannot reach chat and miss the
        # tests page.
        try:
            details = await get_connection_details(_db_pool, parsed_id, uid)
        except ValueError:
            # Not found, not visible to this caller, or a stored key that will not
            # decrypt. Same 404 and same key as before, so the contract is unchanged.
            return await _t_error(404, "api.user.connection_not_found", language)

        provider_code = details["provider"]
        endpoint = details["endpoint"]
        api_key = details["apiKey"]

        # Does THIS CONNECTION serve that model? The question is a
        # ConnectionModelIntersect row, not a provider catalogue: two connections
        # to the same provider may front different servers with different models,
        # so a catalogue entry is not evidence about this connection.
        #
        # One query, so the model id and the served answer come from the same
        # read — an id fetched separately could belong to a row a concurrent
        # discovery had pruned between the two statements.
        async with _db_pool.acquire() as conn:
            served = await conn.fetchrow(
                'SELECT m.id AS model_id FROM public."ConnectionModelIntersect" i '
                'JOIN public."LLMModel" m ON m.id = i."modelId" '
                'WHERE i."connectionId" = $1 AND m."modelName" = $2',
                parsed_id, model_name,
            )
        if served is None:
            # 404 against the connection, and the message says what the fix is:
            # the model has not been discovered here. The abandoned plan's message
            # for a similar case told the user to refresh a catalogue, which is
            # the wrong instruction for this fact.
            return await _t_error(
                404, "api.user.model_not_served_by_connection", language,
                model=model_name,
            )
        model_id = served["model_id"]

        # A registered test may not have its probe yet (turn, until Item 20e).
        probe_fn = getattr(model_probe, definition.probe, None)
        if probe_fn is None:
            return await _t_error(
                400, "api.user.test_not_implemented", language, test=test_id,
            )

        # The two budgets in force for THIS connection (plan Item 4a). Resolved here
        # because the route already holds the pool, and passed explicitly because a
        # probe's defaults are the compiled ones — 300 s and 10 s, neither of which an
        # administrator can reach. That was Item 25's finding: the test route ran on
        # constants no setting could change.
        async with _db_pool.acquire() as timeout_conn:
            conn_timeouts = await resolve_connection_timeouts(timeout_conn, parsed_id)

        started = time.monotonic()
        try:
            outcome = await probe_fn(
                provider_code, api_key, endpoint, model_name,
                timeout=float(conn_timeouts.probe_seconds),
                connect_timeout=float(conn_timeouts.connect_seconds),
            )
        except model_probe.ProbeTransportError as exc:
            # The model was never asked. No capability verdict is written, and the
            # stored one (if any) keeps whatever it had.
            #
            # THE DURATION IS STILL RECORDED (plan Item 25): a connection that takes
            # 200 s to fail is slow in a way a user feels, so what the failure cost
            # belongs on the connection's record even though nothing is known about
            # the model. It goes through the SAME gate as a successful run rather than
            # a second path — INCONCLUSIVE has no state, so `record_result` writes the
            # duration and leaves the model record alone — so there is one rule about
            # which rows a result reaches, not two.
            #
            # A write that fails here must not replace the transport answer: the
            # caller asked what went wrong with their connection, and a 500 about a
            # bookkeeping write would bury it. The failure to record is logged rather
            # than silent, and the answer still says the run failed.
            duration_ms = int((time.monotonic() - started) * 1000)
            try:
                await record_result(
                    _db_pool,
                    model_id,
                    parsed_id,
                    test_id,
                    model_probe.INCONCLUSIVE,
                    duration_ms,
                    uid,
                    failure_class=exc.failure_class,
                )
            except Exception:
                logger.exception(
                    "could not record the duration of a transport failure "
                    "(connection %s, model %s, test %s)",
                    parsed_id, model_name, test_id,
                )

            # A provider that answers "no such model" is a different fact from a
            # provider that cannot be reached: the first means this connection's
            # discovery is behind, the second means the host is down. Both leave
            # the record untouched — neither is evidence about the model's
            # capability — but telling the user the wrong one sends them to the
            # wrong fix.
            # A provider that ANSWERED with a status saying "no such model" is a
            # different fact from an unreachable host — plan Item 5 closes F5 here.
            #
            # The old test was `_provider_says_no_such_model(exc.detail)`, which split
            # the detail on colons and looked for a token that was the digits 404.
            # Measured 2026-11-02: OpenRouter answered OPENAI_HTTP_ERROR:400 with a body
            # saying "not a valid model ID", the token test found no 404, and the user
            # was told "the model could not be reached" about a provider that had just
            # answered clearly.
            #
            # Now the STATUS travels as a number, so the question is decidable.
            if exc.failure_class == "http_status" and exc.http_status in _NO_SUCH_MODEL_STATUSES:
                return await _t_error(
                    404, "api.user.model_not_served_by_connection", language,
                    model=model_name,
                )
            # One message per class, selected by the class the provider supplied.
            # Never by searching the detail (plan Item 5).
            return await _t_error(
                400, _TRANSPORT_MESSAGE_BY_CLASS.get(exc.failure_class, E_TRANSPORT_OTHER),
                language, detail=exc.detail,
            )
        duration_ms = int((time.monotonic() - started) * 1000)

        # The gate decides which rows a result goes to: a state means both writes,
        # no state means the duration only. Resolving the state here as well would
        # be a second decision about the same fact, so `record_result` owns it.
        try:
            capability, performance = await record_result(
                _db_pool,
                model_id,
                parsed_id,
                test_id,
                outcome.outcome,
                duration_ms,
                uid,
                outcome.observations,
            )
        except ResultWriteRefused as exc:
            message = await t(_db_pool, language, exc.key, **exc.kwargs)
            return JSONResponse(
                status_code=400,
                content={"error": exc.key.key, "message": message},
            )

        # `state` is reported from the recorded entry rather than recomputed: what
        # the caller sees and what was stored are then the same decision.
        return {
            "model": model_name,
            "test": test_id,
            "state": None if capability is None else capability.get("state"),
            "outcome": outcome.outcome,
            "detail": outcome.detail,
            "durationMs": duration_ms,
            "result": capability,
            "performance": performance,
        }
    except Exception:
        return await _t_error(500, "api.user.internal_error", language)


# ============================================================
# ITEM 31 — POST /{connectionId}/models/discover (the discovery walk, routed)
# ============================================================
#
# The walk has existed since Item 15 and nothing called it: `discover_connection`
# was reachable only from tests, so a model that appeared on a server never reached
# an LLMModel row, a provider intersect or this connection's intersect. Item 15's own
# Done note says as much. This is the route.
#
# IT REPLACED THE FETCH ROUTE (Item 31). That one wrote ProviderModel — a catalogue
# keyed by provider code — and the AI-test page reads ConnectionModelIntersect, so
# pressing it there changed nothing the page could see. The provider-wide catalogue
# and its route are both gone (Items 31-33); discovery is the only way a catalogue is
# learned now:
#   discover  "what does THIS server actually serve?" -> LLMModel + both intersects
#
# AUTHORISATION mirrors the models GET and the test endpoint: own connection, or one
# shared to the caller's group. A shared connection may be discovered because the
# walk reads the server, not the caller's data — and its result is shared by design,
# which is the point of sharing it.
#
# STATUS CODES, and why each is the one it is:
#   400 invalid_connection_id   the id is not a decimal-digit string
#   404 connection_not_found    no own-or-shared row with that id
#   400 <provider error key>    the server refused or could not be reached; the
#                               fetch helper's own key carries which
#   400 user.no_models_returned the server answered with nothing usable — refused
#                               rather than pruned, because an empty list deletes
#                               every row (`x <> ALL('{}')` is true for everything)
#   500 internal_error          anything else


@router.post("/{connectionId}/models/discover")
async def discover_connection_models(
    connectionId: str,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(401, "api.auth.unauthorized", language)

        if not connectionId.isdigit():
            return await _t_error(400, "api.user.invalid_connection_id", language)
        parsed_id = int(connectionId)

        async with _db_pool.acquire() as conn:
            user = await conn.fetchrow(
                'SELECT "userGroup" FROM "User" WHERE id = $1', uid
            )
            user_group = (user["userGroup"] if user else None) or "00"

            connection = await conn.fetchrow(
                'SELECT "connectionId" FROM "UserAIConnection" '
                'WHERE "connectionId" = $1 AND ("userId" = $2 OR '
                '("isShared" = true AND "aiConnectionGroup" = $3))',
                parsed_id, uid, user_group,
            )

            if connection is None:
                return await _t_error(404, "api.user.connection_not_found", language)

            # The walk joins this connection's transaction, so the whole catalogue is
            # recorded or none of it is. It fetches from the server outside that
            # boundary itself, so a slow host does not hold locks here.
            try:
                result = await discover_connection(conn, parsed_id)
            except ConnectionNotFound:
                # Raced with a delete between the ownership read and the walk.
                return await _t_error(404, "api.user.connection_not_found", language)
            except EmptyCatalogue:
                return await _t_error(400, "user.no_models_returned", language)
            except _ProviderFetchError as e:
                return await _t_error(400, e.key, language, **e.kwargs)

        return {
            "success": True,
            "modelsSeen": result.models_seen,
            "modelsCreated": result.models_created,
            "connectionModelsCreated": result.connection_intersects_created,
            "connectionModelsRefreshed": result.connection_intersects_refreshed,
            "connectionModelsPruned": result.connection_intersects_pruned,
        }
    except Exception:
        return await _t_error(500, "api.user.internal_error", language)



# ============================================================
# ITEM 15 — GET /available (connections usable in the chat UI)
# ============================================================
#
# Frontend source:
#   frontend/app/api/user/ai-connections/available/route.ts
#
# Contract parity:
#   - GET only. Lists a user's OWN connections plus connections shared to
#     their group (isShared=true AND aiConnectionGroup = the user's group).
#     Ordered by createdAt ASC. No example-user block.
#   - DIVERGENCE from the item-12 GET: a missing user row (ghost session)
#     returns 404 {"error": "User not found"} here — the item-12 GET falls
#     through to userGroup "00" and returns 200. Mirrored exactly.
#   - Response is a CURATED shape (not the item-12 Prisma spread):
#     {connections: [{id (string), connectionId, name, provider, endpoint,
#     apiKey (decrypted), aiConnectionGroup, isShared, userId, userName,
#     isOwn, createdAt, updatedAt}], userGroup}. No providerDetails; adds
#     userId/userName/isOwn. userName = owner's name, "Unknown User" when the
#     owner row is missing.
#
# Error shape: same bare-string divergence as items 13/14 ({"error": "<string>"}).


@router.get("/available")
async def get_available_connections(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _t_error(401, "api.auth.unauthorized", language)

        async with _db_pool.acquire() as conn:
            user = await conn.fetchrow(
                'SELECT "userGroup" FROM "User" WHERE id = $1', uid
            )
        user_group = (user["userGroup"] if user else None) or "00"

        async with _db_pool.acquire() as conn:
            rows = await conn.fetch(
                'SELECT * FROM "UserAIConnection" '
                'WHERE "userId" = $1 OR ("isShared" = true AND "aiConnectionGroup" = $2) '
                'ORDER BY "createdAt" ASC',
                uid, user_group,
            )
            user_ids = sorted({r["userId"] for r in rows})
            if user_ids:
                user_rows = await conn.fetch(
                    'SELECT id, name, email FROM "User" WHERE id = ANY($1::text[])',
                    user_ids,
                )
            else:
                user_rows = []

            provider_codes = sorted({r["provider"] for r in rows})
            if provider_codes:
                provider_rows = await conn.fetch(
                    'SELECT code, name FROM "AIProvider" WHERE code = ANY($1::text[])',
                    provider_codes,
                )
            else:
                provider_rows = []
        user_map = {u["id"]: u for u in user_rows}
        provider_map = {p["code"]: p["name"] for p in provider_rows}

        return {
            "connections": [
                {
                    "id": str(r["connectionId"]),
                    "connectionId": r["connectionId"],
                    "name": r["name"],
                    "provider": r["provider"],
                    "providerName": provider_map.get(r["provider"]) or r["provider"],
                    "endpoint": r["endpoint"],
                    "apiKey": decrypt_field_or_null(r["apiKey"]),
                    "aiConnectionGroup": r["aiConnectionGroup"] or "00",
                    "isShared": r["isShared"],
                    "userId": r["userId"],
                    "userName": (user_map.get(r["userId"]) or {}).get("name") or "Unknown User",
                    "isOwn": r["userId"] == uid,
                    # The two per-connection timeouts. They were MISSING here while the
                    # single-connection GET returned them (see _connection_body), so the
                    # same row answered two different shapes depending on the route —
                    # and Go's /available did include them, which the parity sweep
                    # reported as a divergence on 2026-11-02. Python was the odd one out,
                    # not Go.
                    "connectTimeoutSeconds": r["connectTimeoutSeconds"],
                    "probeTimeoutSeconds": r["probeTimeoutSeconds"],
                    "createdAt": iso_utc(r["createdAt"]),
                    "updatedAt": iso_utc(r["updatedAt"]),
                }
                for r in rows
            ],
            "userGroup": user_group,
        }
    except Exception:
        return await _t_error(500, "api.user.internal_error", language)
