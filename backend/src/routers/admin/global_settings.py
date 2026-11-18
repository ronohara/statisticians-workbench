"""
Admin Global Settings Router — P2 Group 1, item 3 (Prisma-removal plan).

Drop-in replacement for the frontend Prisma handler:
  frontend/app/api/admin/global-settings/route.ts   (GET + POST)

Contract parity with the consolidated handler (option a — see
workbench-documents/workbench-resolve-settings-errors-plan.html):
  - Coded error envelope {error: code, message: text}; codes double as
    Translation-table keys (api.admin.settings_*).
  - GET: full-admin gate (checkAdmin = isAdmin only — example users pass,
    mirroring the frontend), 12-field flat response incl.
    platformMaxUploadSizeMB; create-with-defaults when id=1 is missing.
  - POST: same gate, strict integer validation for the six numeric fields
    (int only — bool/float/str rejected with 400, no coercion), partial-save behaviour (only fields present in the body
    are updated), "unlimited" → NULL for maxRegistrations, empty/invalid
    emailSender and invalid platformMaxUploadSizeMB → 400 (item 18), empty
    update → 400 no_fields, upsert (UPDATE id=1; INSERT with defaults when
    absent). Success response is 11 fields (no platformMaxUploadSizeMB),
    matching the frontend.
  - The public GET (/api/global-settings) stays on the frontend until its
    Group-2 port; this router covers the admin surface only.

Auth helpers (_auth, _is_admin, _error) are shared from admin.users.py;
the pool is wired via set_db_pool in main.py.
"""

import re
from typing import Any, Optional
from urllib.parse import urlsplit

from fastapi import APIRouter, Depends, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from pydantic import BaseModel, ConfigDict

from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth, _error, _is_admin, current_demo_mode
from src.licensing import has_valid_licence, is_open_source
from src.utils.connection_timeouts import (
    CONNECT_TIMEOUT_CEILING,
    PROBE_TIMEOUT_CEILING,
    validate_connect_timeout,
    validate_probe_timeout,
)

router = APIRouter(prefix="/api/admin", tags=["admin-global-settings"])
security = HTTPBearer(auto_error=False)

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ============================================================
# FRONTEND ERROR-CODE CONTRACT (stable API surface — do not rename)
# ============================================================

E_UNAUTHORIZED = "api.auth.unauthorized"
E_VIEW_FORBIDDEN = "api.admin.settings_view_forbidden"
E_MODIFY_FORBIDDEN = "api.admin.settings_modify_forbidden"
E_INVALID_MAX_REGISTRATIONS = "api.admin.settings_invalid_max_registrations"
E_INVALID_EMAIL_TIMEOUT = "api.admin.settings_invalid_email_timeout"
E_INVALID_EMAIL_SENDER = "api.admin.settings_invalid_email_sender"
E_INVALID_PUBLIC_URL = "api.admin.settings_invalid_public_url"
E_INVALID_GRACE_PERIOD = "api.admin.settings_invalid_grace_period"
E_INVALID_UPLOAD_SIZE = "api.admin.settings_invalid_upload_size"
E_INVALID_UPLOAD_COUNT = "api.admin.settings_invalid_upload_count"
E_INVALID_PLATFORM_UPLOAD_SIZE = "api.admin.settings_invalid_platform_upload_size"
E_NO_FIELDS = "api.admin.no_fields"
# Plan Item 4b. A field another endpoint owns is a client error about WHICH endpoint,
# so the message names both the field and the endpoint that accepts it.
E_FIELD_NOT_OWNED = "api.admin.field_not_owned"
E_TUNING_RESET_ERROR = "api.admin.tuning_reset_error"
E_DEMO_MODE_REQUIRES_LICENCE = "api.admin.settings_demo_mode_requires_licence"
E_DEMO_UPLOAD_SIZE_LIMIT = "api.admin.settings_demo_upload_size_limit"
E_DEMO_UPLOAD_COUNT_LIMIT = "api.admin.settings_demo_upload_count_limit"
E_INVALID_REGISTRATION_MODE = "api.admin.settings_invalid_registration_mode"
E_INVALID_TEST_SECONDS = "api.admin.settings_invalid_slow_threshold"
# AI tuning refusals (plan Item 2). Three codes, not one: the three values fail
# for different reasons, and a single "invalid value" message would tell an
# administrator nothing about which field or which rule.
E_INVALID_TEMPERATURE = "api.admin.settings_invalid_temperature"
E_INVALID_MAX_TOKENS = "api.admin.settings_invalid_max_tokens"
E_INVALID_AI_TIMEOUT = "api.admin.settings_invalid_ai_timeout"
# Plan workbench-AI-timeout-policy-plan.html, Item 2. Their own codes rather than a
# reuse of the one above, because that message carries no ceiling and these do.
E_INVALID_CONNECT_TIMEOUT = "api.admin.settings_invalid_connect_timeout"
E_INVALID_PROBE_TIMEOUT = "api.admin.settings_invalid_probe_timeout"
E_LOAD_ERROR = "api.admin.settings_load_error"
E_SAVE_ERROR = "api.admin.settings_save_error"
E_PUBLIC_LOAD_ERROR = "api.global_settings_load_error"

DEFAULT_EMAIL_SENDER = "no-reply@replace-with-your-domain"
DEFAULT_PUBLIC_URL = "https://replace-with-your-external-host-name"
DEFAULT_WELCOME = "Welcome to Statisticians Workbench!"
EMAIL_REGEX = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")

# Flat response selects, mirrored from the frontend.
# The LIMITS and OPTIONS fields. This tuple is what POST /api/admin/global-settings
# accepts, and it no longer contains the AI tuning values (plan Item 4b of
# workbench-AI-timeout-policy-plan.html).
#
# WHY THEY LEFT. Two pages now edit one row. limits/page.tsx posts every field it
# holds on every save, so while tuning lived here a save from Limits overwrote
# whatever had been set on Tuning — last writer wins, silently, with a success
# toast. Splitting the endpoints makes a page unable to clobber what its endpoint
# does not accept, which is a mechanism rather than a rule to remember.
_LIMITS_POST_FIELDS = ("demoMode", "maxRegistrations", "emailVerificationTimeout",
                       "emailSender", "publicUrl", "registrationGracePeriodHours",
                       "welcome", "passwordPolicy", "passwordPolicyCustom",
                       "defaultMaxUploadSizeMB", "defaultMaxUploadCount", "registrationMode")

# The AI tuning fields, owned by POST /api/admin/tuning. Six, and they are not
# limits: everything in the tuple above is a cap on what a user may do, and these
# are how the AI behaves.
#
# `defaultModelTestSeconds` is here and it is NOT a timeout — it is the slow-model
# THRESHOLD, the number a recorded duration is compared against. Grouping it with
# the timeouts is deliberate and its label says so.
_TUNING_POST_FIELDS = ("defaultModelTestSeconds",
                       "temperature", "maxTokens", "timeoutSeconds",
                       "defaultConnectTimeoutSeconds", "defaultProbeTimeoutSeconds")

# The read tuple, EXPLICIT. It is not derived from either POST tuple.
#
# Deriving it was the defect this split would otherwise have introduced: with
# `_GET_FIELDS = _POST_FIELDS + (...)`, removing the six from the POST would have
# removed them from every response too — breaking this new page's own read and the
# six read-only pages that fetch this endpoint without posting (options,
# admin/users/[id], login, settings/profile, settings/ai/connection/[id],
# datasets/upload). All eighteen columns stay readable; only the write surface split.
_GET_FIELDS = _LIMITS_POST_FIELDS + _TUNING_POST_FIELDS + ("platformMaxUploadSizeMB",)

#: Sentinel for "this endpoint does not own that field". A plain string so it can
#: travel in a JSON body without a second shape.
_TUNING_OWNED = "POST /api/admin/tuning owns this field; POST /api/admin/global-settings does not"


class GlobalSettingsBody(BaseModel):
    # All fields Optional[Any]: the six numeric fields are validated strictly
    # in the handler (int only — bool/float/str rejected), never coerced.
    demoMode: Optional[Any] = None
    maxRegistrations: Optional[Any] = None
    emailVerificationTimeout: Optional[Any] = None
    emailSender: Optional[Any] = None
    publicUrl: Optional[Any] = None
    registrationGracePeriodHours: Optional[Any] = None
    welcome: Optional[Any] = None
    passwordPolicy: Optional[Any] = None
    passwordPolicyCustom: Optional[Any] = None
    defaultMaxUploadSizeMB: Optional[Any] = None
    defaultMaxUploadCount: Optional[Any] = None
    platformMaxUploadSizeMB: Optional[Any] = None
    registrationMode: Optional[Any] = None
    defaultModelTestSeconds: Optional[Any] = None
    # AI tuning defaults (plan Item 2). Any-typed like every other field here, so
    # the validation below — not Pydantic — decides what is acceptable and which
    # translated message a refusal carries.
    temperature: Optional[Any] = None
    maxTokens: Optional[Any] = None
    timeoutSeconds: Optional[Any] = None
    # The two connection-timeout defaults (plan Item 2). Any-typed like the rest, so
    # the handler — not Pydantic — decides what is acceptable and which translated
    # message a refusal carries.
    defaultConnectTimeoutSeconds: Optional[Any] = None
    defaultProbeTimeoutSeconds: Optional[Any] = None


# ============================================================
# HELPERS
# ============================================================

def _public(row, fields):
    """Format a DB row for the wire."""
    out = {}
    for col in fields:
        out[col] = row[col]
    return out


async def _fetch_settings():
    async with _db_pool.acquire() as conn:
        cols = ", ".join(f'"{c}"' for c in _GET_FIELDS)
        return await conn.fetchrow(f'SELECT {cols} FROM "GlobalSettings" WHERE id = 1')


async def _insert_defaults(data: dict, validated_max):
    """Prisma create-with-defaults mirror (?? semantics)."""
    async with _db_pool.acquire() as conn:
        await conn.execute(
            """
            INSERT INTO "GlobalSettings" (
                id, "demoMode", "maxRegistrations", "emailVerificationTimeout",
                "emailSender", "publicUrl", "registrationGracePeriodHours",
                "welcome", "passwordPolicy", "passwordPolicyCustom",
                "defaultMaxUploadSizeMB", "defaultMaxUploadCount",
                "registrationMode", "platformMaxUploadSizeMB", "updatedAt"
                -- THE SIX AI TUNING COLUMNS ARE DELIBERATELY ABSENT (plan Item 4b).
                --
                -- They used to be here with a literal fallback each, because this
                -- INSERT is also reached from the POST's UPDATE-0 branch and a value
                -- supplied in that request had to survive the create. Item 4b removed
                -- that possibility: the limits POST now REFUSES any of the six, so
                -- `data` can never carry one. The other three callers pass {}.
                --
                -- So the literals were unreachable duplication of the DDL defaults, and
                -- the DDL is the authority for a default now (the reset endpoint uses
                -- SET col = DEFAULT for the same reason). Omitting the columns is not a
                -- behaviour change: PostgreSQL fills them from the table definition.
            ) VALUES (
                1, $1, $2, $3, $4, $5, $6, $7, $8, $9, $10, $11, $12, 10, NOW()
            )
            """,
            True if data.get("demoMode") is True else False,
            validated_max,
            data.get("emailVerificationTimeout") if data.get("emailVerificationTimeout") is not None else 24,
            data.get("emailSender") if data.get("emailSender") else DEFAULT_EMAIL_SENDER,
            data.get("publicUrl") if data.get("publicUrl") else DEFAULT_PUBLIC_URL,
            data.get("registrationGracePeriodHours") if data.get("registrationGracePeriodHours") is not None else 24,
            data.get("welcome") if data.get("welcome") is not None else DEFAULT_WELCOME,
            data.get("passwordPolicy") if data.get("passwordPolicy") else "medium",
            data.get("passwordPolicyCustom"),
            data.get("defaultMaxUploadSizeMB") if data.get("defaultMaxUploadSizeMB") is not None else 0,
            data.get("defaultMaxUploadCount") if data.get("defaultMaxUploadCount") is not None else 0,
            data.get("registrationMode") if data.get("registrationMode") is not None else 0,
        )


# ============================================================
# ENDPOINTS
# ============================================================

@router.get("/global-settings")
async def get_global_settings(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if not await _is_admin(uid):
            return await _error(403, E_VIEW_FORBIDDEN, language)

        row = await _fetch_settings()
        if row is None:
            await _insert_defaults({}, None)
            row = await _fetch_settings()
        return _public(row, _GET_FIELDS)
    except Exception:
        return await _error(500, E_LOAD_ERROR, language)


@router.post("/global-settings")
async def post_global_settings(
    body: GlobalSettingsBody,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if not await _is_admin(uid):
            return await _error(403, E_MODIFY_FORBIDDEN, language)

        data = body.model_dump(exclude_unset=True)

        # A tuning field posted here is refused, not ignored (plan Item 4b).
        #
        # The user's decision, 2026-11-02: "silent ignore is wrong so option (b)".
        # Ignoring would have made a stale Limits page lose its own edits with a 200
        # and a success toast — a fault that reports like success. Naming the owning
        # endpoint tells the caller which page the field belongs to.
        stray = [f for f in _TUNING_POST_FIELDS if f in data]
        if stray:
            return await _error(400, E_FIELD_NOT_OWNED, language,
                                fields=", ".join(stray), endpoint=_TUNING_OWNED)

        # Effective demo mode: the value being saved, else the current value.
        if "demoMode" in data and isinstance(data["demoMode"], bool):
            effective_demo = data["demoMode"]
        else:
            effective_demo = await current_demo_mode()

        # --- maxRegistrations ---
        validated_max: Optional[Any] = None
        if "maxRegistrations" in data and data["maxRegistrations"] is not None:
            value = data["maxRegistrations"]
            if value == "unlimited":
                # "unlimited" → NULL (no cap) — intentional (item 18).
                validated_max = None
            elif isinstance(value, bool) or not isinstance(value, int) or value < 1:
                return await _error(400, E_INVALID_MAX_REGISTRATIONS, language)
            else:
                validated_max = value

        # --- emailVerificationTimeout ---
        validated_timeout: Optional[Any] = None
        if ("emailVerificationTimeout" in data
                and data["emailVerificationTimeout"] is not None):
            value = data["emailVerificationTimeout"]
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                return await _error(400, E_INVALID_EMAIL_TIMEOUT, language)
            validated_timeout = value

        # --- emailSender (empty/invalid → 400 directly, item 18) ---
        validated_sender: Optional[str] = None
        if "emailSender" in data:
            validated_sender = data["emailSender"]
            if not validated_sender or not EMAIL_REGEX.match(str(validated_sender)):
                return await _error(400, E_INVALID_EMAIL_SENDER, language)

        # --- publicUrl ---
        validated_public_url: Optional[str] = None
        if "publicUrl" in data:
            validated_public_url = data["publicUrl"] or DEFAULT_PUBLIC_URL
            if validated_public_url is not None and not urlsplit(str(validated_public_url)).scheme:
                return await _error(400, E_INVALID_PUBLIC_URL, language)

        # --- registrationGracePeriodHours ---
        validated_grace: Optional[Any] = None
        if ("registrationGracePeriodHours" in data
                and data["registrationGracePeriodHours"] is not None):
            value = data["registrationGracePeriodHours"]
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                return await _error(400, E_INVALID_GRACE_PERIOD, language)
            validated_grace = value

        # --- defaultMaxUploadSizeMB ---
        validated_size: Optional[Any] = None
        if "defaultMaxUploadSizeMB" in data and data["defaultMaxUploadSizeMB"] is not None:
            value = data["defaultMaxUploadSizeMB"]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return await _error(400, E_INVALID_UPLOAD_SIZE, language)
            if effective_demo and (value == 0 or value > 5):
                return await _error(400, E_DEMO_UPLOAD_SIZE_LIMIT, language)
            validated_size = value

        # --- defaultMaxUploadCount ---
        validated_count: Optional[Any] = None
        if "defaultMaxUploadCount" in data and data["defaultMaxUploadCount"] is not None:
            value = data["defaultMaxUploadCount"]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return await _error(400, E_INVALID_UPLOAD_COUNT, language)
            if effective_demo and (value == 0 or value > 5):
                return await _error(400, E_DEMO_UPLOAD_COUNT_LIMIT, language)
            validated_count = value

        # --- platformMaxUploadSizeMB (reject invalid, item 18) ---
        validated_platform: Optional[Any] = None
        if "platformMaxUploadSizeMB" in data and data["platformMaxUploadSizeMB"] is not None:
            value = data["platformMaxUploadSizeMB"]
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                return await _error(400, E_INVALID_PLATFORM_UPLOAD_SIZE, language)
            validated_platform = value

        # The six AI tuning fields are no longer accepted here (plan Item 4b);
        # they are refused above and handled by POST /api/admin/tuning.

        # --- registrationMode (must be one of 0|1|2|4) ---
        validated_registration_mode: Optional[Any] = None
        if "registrationMode" in data and data["registrationMode"] is not None:
            value = data["registrationMode"]
            if isinstance(value, bool) or not isinstance(value, int) or value not in (0, 1, 2, 4):
                return await _error(400, E_INVALID_REGISTRATION_MODE, language)
            validated_registration_mode = value

        # --- updateData: presence-based partial save ---
        updates: dict = {}
        if "demoMode" in data and isinstance(data["demoMode"], bool):
            if not data["demoMode"] and not is_open_source() and not has_valid_licence():
                return await _error(400, E_DEMO_MODE_REQUIRES_LICENCE, language)
            updates["demoMode"] = data["demoMode"]
        if "maxRegistrations" in data:
            updates["maxRegistrations"] = validated_max
        if "emailVerificationTimeout" in data:
            updates["emailVerificationTimeout"] = validated_timeout
        if "emailSender" in data:
            updates["emailSender"] = validated_sender
        if "publicUrl" in data:
            updates["publicUrl"] = validated_public_url
        if "registrationGracePeriodHours" in data:
            updates["registrationGracePeriodHours"] = validated_grace
        if "welcome" in data:
            updates["welcome"] = data["welcome"]
        if "passwordPolicy" in data:
            updates["passwordPolicy"] = data["passwordPolicy"]
        if "passwordPolicyCustom" in data:
            updates["passwordPolicyCustom"] = data["passwordPolicyCustom"]
        if "defaultMaxUploadSizeMB" in data:
            updates["defaultMaxUploadSizeMB"] = validated_size
        if "defaultMaxUploadCount" in data:
            updates["defaultMaxUploadCount"] = validated_count
        if "registrationMode" in data:
            updates["registrationMode"] = validated_registration_mode
        if validated_platform is not None:
            updates["platformMaxUploadSizeMB"] = validated_platform

        if updates:
            async with _db_pool.acquire() as conn:
                sets = ", ".join(f'"{k}" = ${i + 1}' for i, k in enumerate(updates))
                result = await conn.execute(
                    f'UPDATE "GlobalSettings" SET {sets}, "updatedAt" = NOW() WHERE id = 1',
                    *updates.values(),
                )
                if result == "UPDATE 0":
                    await _insert_defaults(data, validated_max)
        else:
            # Empty update data -> 400 (item 18): no valid fields to update.
            return await _error(400, E_NO_FIELDS, language)

        row = await _fetch_settings()
        # The full read tuple, not the write tuple: a caller that just saved wants
        # to see the row it now has, including the tuning values it does not own.
        return _public(row, _GET_FIELDS)
    except Exception:
        return await _error(500, E_SAVE_ERROR, language)


# ============================================================
# AI TUNING — its own endpoint (plan Item 4b of
# workbench-AI-timeout-policy-plan.html)
# ============================================================
#
# WHY THIS EXISTS AT ALL
# The six values below used to be accepted by POST /api/admin/global-settings,
# alongside the twelve limits and options fields. They are a different kind of
# thing — every one of those twelve is a cap on what a user may do, and these are
# how the AI behaves — and two pages now edit one row.
#
# limits/page.tsx posts EVERY field it holds on every save. While tuning lived on
# the same endpoint, saving Limits overwrote whatever had been set on Tuning with
# the stale copy in its own state: last writer wins, silently, with a success
# toast. Two endpoints make that structurally impossible, because a page cannot
# clobber a column its endpoint does not accept.
#
# The refusal travels in both directions: POST /api/admin/global-settings answers
# 400 for any of these six (see _TUNING_POST_FIELDS there), and this endpoint
# answers 400 for any field from _LIMITS_POST_FIELDS.


class TuningBody(BaseModel):
    """The six AI tuning fields. Any-typed, like GlobalSettingsBody, so THIS
    handler decides what is acceptable and which translated message a refusal
    carries — not Pydantic's 422.

    `extra="allow"` is load-bearing, not tidiness. Without it Pydantic DISCARDS any
    field the model does not declare, so a limits field posted here never reached the
    ownership check below and the caller got "no valid fields" instead of being told
    which endpoint owns it — measured 2026-11-02: {"demoMode": true} answered
    api.admin.no_fields rather than api.admin.field_not_owned. Go reads a raw map and
    caught it immediately, which is how the divergence showed.
    """

    model_config = ConfigDict(extra="allow")

    defaultModelTestSeconds: Optional[Any] = None
    temperature: Optional[Any] = None
    maxTokens: Optional[Any] = None
    timeoutSeconds: Optional[Any] = None
    defaultConnectTimeoutSeconds: Optional[Any] = None
    defaultProbeTimeoutSeconds: Optional[Any] = None


@router.post("/tuning")
async def post_tuning(
    body: TuningBody,
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Save the six AI tuning defaults.

    Presence-based like its sibling: an absent field is left alone, so a partial
    save is a partial save and cannot blank a value the caller did not send.

    Validate, don't coerce, throughout — a bool is an int in Python, a float would
    be truncated by an int column, and either would silently change a number every
    provider call in the product reads.
    """
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if not await _is_admin(uid):
            return await _error(403, E_MODIFY_FORBIDDEN, language)

        data = body.model_dump(exclude_unset=True)

        # A field the OTHER endpoint owns is refused, naming both (plan Item 4b).
        # The mirror of the check in post_global_settings: the split is enforced from
        # both sides, so neither endpoint silently accepts what belongs to the other.
        stray = [f for f in _LIMITS_POST_FIELDS if f in data]
        if stray:
            return await _error(400, E_FIELD_NOT_OWNED, language,
                                fields=", ".join(stray),
                                endpoint="POST /api/admin/global-settings owns this field; POST /api/admin/tuning does not")

        updates: dict = {}

        # The slow-model THRESHOLD. Not a timeout: it is the number a recorded
        # duration is compared against to show "too slow". Grouped with the timeouts
        # because they share a page, and named so a reader cannot confuse them.
        if "defaultModelTestSeconds" in data:
            value = data["defaultModelTestSeconds"]
            if value is None:
                return await _error(400, E_INVALID_TEST_SECONDS, language)
            if isinstance(value, bool) or not isinstance(value, int) or value < 1:
                return await _error(400, E_INVALID_TEST_SECONDS, language)
            updates["defaultModelTestSeconds"] = value

        # temperature is the only float here, so it is the only one that accepts a
        # float — and an int, because 1 is a legal temperature and JSON has no separate
        # integer type a client must use. A bool is refused first: in Python `True`
        # is an int, so a `True` slipping through as 1.0 would set a value nobody chose.
        #
        # The band is the provider contract (0 to 2), not a preference. Outside it an
        # OpenAI-compatible endpoint rejects the request or clamps it, so the value the
        # administrator set would not be the value in force.
        if "temperature" in data:
            value = data["temperature"]
            if (value is None or isinstance(value, bool)
                    or not isinstance(value, (int, float))
                    or not (0 <= float(value) <= 2)):
                return await _error(400, E_INVALID_TEMPERATURE, language)
            updates["temperature"] = float(value)

        if "maxTokens" in data:
            value = data["maxTokens"]
            if value is None or isinstance(value, bool) or not isinstance(value, int) or value < 1:
                return await _error(400, E_INVALID_MAX_TOKENS, language)
            updates["maxTokens"] = value

        if "timeoutSeconds" in data:
            value = data["timeoutSeconds"]
            if value is None or isinstance(value, bool) or not isinstance(value, int) or value < 1:
                return await _error(400, E_INVALID_AI_TIMEOUT, language)
            updates["timeoutSeconds"] = value

        # The two connection timeouts. Range-checked only: their upper bounds are
        # product judgements held in connection_timeouts, not ranges a provider
        # contract dictates, so each refusal names its own ceiling.
        #
        # No cross-check against each other. A stored connect default above the probe
        # default is possible — one is edited, then the other — and the resolver clamps
        # it at read time (D6's second half). Refusing it here would mean reading the
        # row on every save to reject a state the clamp already handles.
        if "defaultConnectTimeoutSeconds" in data:
            value = data["defaultConnectTimeoutSeconds"]
            if value is None or validate_connect_timeout(value) is not None:
                return await _error(400, E_INVALID_CONNECT_TIMEOUT, language,
                                    ceiling=CONNECT_TIMEOUT_CEILING)
            updates["defaultConnectTimeoutSeconds"] = value

        if "defaultProbeTimeoutSeconds" in data:
            value = data["defaultProbeTimeoutSeconds"]
            if value is None or validate_probe_timeout(value) is not None:
                return await _error(400, E_INVALID_PROBE_TIMEOUT, language,
                                    ceiling=PROBE_TIMEOUT_CEILING)
            updates["defaultProbeTimeoutSeconds"] = value

        if not updates:
            return await _error(400, E_NO_FIELDS, language)

        async with _db_pool.acquire() as conn:
            sets = ", ".join(f'"{k}" = ${i + 1}' for i, k in enumerate(updates))
            await conn.execute(
                f'UPDATE "GlobalSettings" SET {sets}, "updatedAt" = NOW() WHERE id = 1',
                *updates.values(),
            )

        row = await _fetch_settings()
        return _public(row, _GET_FIELDS)
    except Exception:
        return await _error(500, E_SAVE_ERROR, language)


@router.post("/tuning/reset")
async def post_tuning_reset(
    req: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Reset the six AI tuning defaults to the values the DDL declares.

    WHY THE DDL AND NOT THE COMPILED CONSTANTS. The user, 2026-11-02: "defaults from
    the migrations is better than constants .. the DDL is consistent against all
    installs". It is also the better argument: "reset to defaults" means "as a new
    installation would be", and the DDL default IS that, where the compiled constant
    answers a different question — what applies when the row is missing.

    So this endpoint contains no numbers at all: `SET col = DEFAULT` once per column,
    and PostgreSQL supplies the value from the table's own definition. A future change
    to a default is a migration, and reset follows it automatically.

    GLOBAL ONLY. Per-connection overrides live on UserAIConnection and are untouched —
    this is the admin global surface, and resetting here must not silently undo a
    per-server decision an administrator made deliberately.

    All six are reset together, in one statement, so a failure cannot leave three
    reset and three not. `updatedAt` moves with them.
    """
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        if not await _is_admin(uid):
            return await _error(403, E_MODIFY_FORBIDDEN, language)

        async with _db_pool.acquire() as conn:
            await conn.execute(
                'UPDATE "GlobalSettings" SET '
                + ", ".join(f'"{c}" = DEFAULT' for c in _TUNING_POST_FIELDS)
                + ', "updatedAt" = NOW() WHERE id = 1'
            )

        row = await _fetch_settings()
        return _public(row, _GET_FIELDS)
    except Exception:
        return await _error(500, E_TUNING_RESET_ERROR, language)



# ============================================================
# PUBLIC SETTINGS + AUTHENTICATED GLOBAL SETTINGS
# ============================================================
# /api/public-settings (GET, unauthenticated) returns only the non-sensitive
# fields public pages need (login/register/reset-password/demo indicators):
# demoMode, passwordPolicy, passwordPolicyCustom, welcome.
# /api/global-settings (GET, authenticated) returns the full field set for any
# signed-in user — no admin gate (the admin surface is the /api/admin router
# above). A missing id=1 row is created with the frontend's exact defaults.

_PUBLIC_FIELDS = ("demoMode", "passwordPolicy", "passwordPolicyCustom", "welcome", "registrationMode")

public_router = APIRouter(tags=["global-settings"])


@public_router.get("/api/public-settings")
async def get_public_settings(language: str = "en"):
    try:
        row = await _fetch_settings()
        if row is None:
            await _insert_defaults({}, None)
            row = await _fetch_settings()
        return _public(row, _PUBLIC_FIELDS)
    except Exception:
        return await _error(500, E_PUBLIC_LOAD_ERROR, language)


@public_router.get("/api/global-settings")
async def get_authenticated_global_settings(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = "en",
):
    try:
        uid = await _auth(credentials)
        if uid is None:
            return await _error(401, E_UNAUTHORIZED, language)
        row = await _fetch_settings()
        if row is None:
            await _insert_defaults({}, None)
            row = await _fetch_settings()
        return _public(row, _GET_FIELDS)
    except Exception:
        return await _error(500, E_PUBLIC_LOAD_ERROR, language)
