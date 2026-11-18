import os
import logging
from urllib.parse import urlparse
from src.version import BACKEND, VERSION
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, Request, status, Depends, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, Response
from fastapi.exceptions import RequestValidationError
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi.utils import is_body_allowed_for_status_code
from dotenv import load_dotenv
import asyncpg
import json
import uvicorn

from src.postgres_data_manager import ensure_data_database, set_data_pool
from src.licensing import load_licence
from src.utils.language import get_user_language, DEFAULT_LANGUAGE, get_language_from_header
from src.utils.translation import t, discover_intercept
from src.routers.common.translations import VALIDATION, SYSTEM

# ============================================================
# LOGGING — stderr, and in development also a rotated file
# ============================================================
#
# Two streams, one job each.
#
# **stderr is the record.** Every deployed environment already captures it and
# already rotates it: journald on Linux (the .deb's unit sets no
# `StandardOutput=`, so the default applies), NSSM on Windows
# (`AppStdout`/`AppStderr` plus `AppRotateFiles`). The application must not
# grow a third mechanism for a problem two collectors already solve — and
# cannot, because it does not know which one it is writing into.
#
# **In development there is no collector at all** — the stream goes to a
# terminal, per-user, and dies with the session. That is the one case the
# application has to handle itself: a run leaves no record, so a defect found
# later cannot be investigated by anyone who was not sitting at that terminal.
# Measured 2026-11-07: a decision turn logged `DECISION session=… joins=5` to a
# terminal the agent could not read, and the same question had to be asked of
# the user.
#
# So: `logs/backend.log` in development only, rotated at 10 MB keeping three
# backups — a 40 MB ceiling stated here rather than discovered later.
#
# **Anchored on the repository root, not on this file's directory, and the
# reason is a feedback loop measured on 2026-11-10.** `uvicorn.run(reload=True)`
# passes no `reload_dirs`, so it watches this file's directory — `backend/` —
# and `uvicorn` constructs its watcher as `watch(*reload_dirs, watch_filter=None)`
# (uvicorn 0.49.0, `supervisors/watchfilesreload.py`). That `None` means
# **watchfiles** logs `"1 change detected"` for every change it sees, *before*
# uvicorn's own filter — which would have rejected `.log` — is consulted. Those
# lines propagate to the root logger, whose RotatingFileHandler was writing into
# the watched directory, so every line was itself a change: 18 changes in 6
# seconds, all of them this file. Over ~30 hours it produced 303,411 lines
# against 2,042 real ones — 99.3% noise — and rotated 10 MB files every ~18
# hours, burying the `DECISION`/`TOOL_LOOP` lines the file exists for.
#
# The fix is to keep the watcher's tree free of the file the application writes
# constantly: one level up is the repository root, which is also where the Go
# backend writes (`workbench-go/logs/`), so the two layouts now agree. Moving the
# file out is what breaks the loop; silencing the `watchfiles` logger would have
# hidden the symptom and left the cause in place.
#
# This is the one deliberate exception to "the application does not rotate":
# in development the application IS the only collector.
from logging.handlers import RotatingFileHandler as _RotatingFileHandler


def _configure_logging() -> None:
    """stderr always; `logs/backend.log` in development, rotated.

    Idempotent: the root logger is cleared first, so a reload or a second
    import cannot stack a second set of handlers and double every line. It also
    means the two handlers below are the complete set — a future `basicConfig`
    elsewhere would be replaced rather than added to, which is the behaviour
    you want from a single startup path.
    """
    formatter = logging.Formatter(
        # `%z` because a log line must be orderable against a line from another
        # host, and until 2026-11-07 neither backend printed an offset. Measured:
        # a dev line at 08:53 and a database column at 01:53 are the same event
        # on a UTC+7 machine, and nothing in either said so. A stateless log is
        # one a later reader has to guess the timezone of.
        "%(asctime)s - %(levelname)s - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S%z",
    )

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    for existing in list(root.handlers):
        root.removeHandler(existing)

    # stderr — logging's own default stream, which is what the Go backend
    # mirrors (`internal/log`, "to stderr").
    stream = logging.StreamHandler()
    stream.setFormatter(formatter)
    root.addHandler(stream)

    # The development file. The predicate is the same one
    # `src/utils/logger.py` already uses, so there is one definition of
    # "development" rather than two that can disagree.
    if os.getenv("ENVIRONMENT", "development") != "development":
        return

    # The repository root — one level above this file — deliberately outside the
    # directory uvicorn's reloader watches. See the block comment above: a log
    # file inside the watched tree is a change that writes a line that is a
    # change, and the loop is real, measured, and 99.3% of this file's content.
    # Still anchored on a file location rather than the working directory, so it
    # lands in the same place whichever directory uvicorn is started from.
    log_dir = os.path.join(
        os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "logs"
    )
    try:
        os.makedirs(log_dir, exist_ok=True)
        file_handler = _RotatingFileHandler(
            os.path.join(log_dir, "backend.log"),
            maxBytes=10 * 1024 * 1024,
            backupCount=3,
            encoding="utf-8",
        )
    except OSError as exc:
        # A read-only tree, a full disk, a directory that cannot be created.
        # The backend must still start and still log to stderr — losing the
        # file is a degraded development experience, not a reason to refuse to
        # run. The warning goes to stderr, which is the stream that always
        # exists.
        logging.getLogger(__name__).warning(
            "Could not open %s/backend.log (%s) — logging to stderr only", log_dir, exc
        )
        return

    file_handler.setFormatter(formatter)
    root.addHandler(file_handler)


# Load environment variables from .env file
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))

# Configure logging AFTER `load_dotenv`, because the decision it makes depends on
# `ENVIRONMENT` — and until 2026-11-07 `logging.basicConfig` ran before this line,
# which was harmless only because that call read nothing from the environment.
# Now it does: the file handler is a development-only branch, and reading the
# variable before `.env` is loaded would silently take the default every time.
#
# Called here rather than at the top of the file so the ordering is not a
# convention someone has to remember: `load_dotenv` is the line above it.
_configure_logging()

# Import routers
from src.routers import datasets, recipes, groups, dbdesign, notebooks
from src.routers.datasets.browse import router as browse_router, set_db_pool as browse_set_db_pool
from src.routers.audio_presets import router as audio_presets_router, set_db_pool as audio_presets_set_db_pool
from src.routers.features_router import router as features_router
from src.routers.licence_router import router as licence_router, set_db_pool as licence_set_db_pool
from src.routers.access_router import router as access_router, set_db_pool as access_set_db_pool
from src.routers.admin.users import router as admin_users_router, set_db_pool as admin_users_set_db_pool
from src.routers.admin.groups import router as admin_groups_router, set_db_pool as admin_groups_set_db_pool
from src.routers.admin.global_settings import router as admin_global_settings_router, set_db_pool as admin_global_settings_set_db_pool
from src.routers.admin.global_settings import public_router as global_settings_public_router
from src.routers.languages import router as languages_router, set_db_pool as languages_set_db_pool
from src.routers.admin.ai_providers import router as admin_ai_providers_router, set_db_pool as admin_ai_providers_set_db_pool
from src.routers.ai_providers import router as ai_providers_router, set_db_pool as ai_providers_set_db_pool
from src.routers.test_ai import router as test_ai_router, set_db_pool as test_ai_set_db_pool
from src.routers.aitesting.synthetic_dataset import set_db_pool as aitesting_dataset_set_db_pool
from src.routers.admin.models import router as admin_models_router, set_db_pool as admin_models_set_db_pool
from src.routers.admin.visualization_types import router as admin_visualization_types_router, set_db_pool as admin_visualization_types_set_db_pool
from src.routers.visualization_types import router as visualization_types_router, set_db_pool as visualization_types_set_db_pool
from src.routers.visualization_instances import router as visualization_instances_router, set_db_pool as visualization_instances_set_db_pool
from src.routers.user.profile import router as user_profile_router, set_db_pool as user_profile_set_db_pool
from src.routers.user.role import router as user_role_router, set_db_pool as user_role_set_db_pool
from src.routers.user.change_password import router as change_password_router, set_db_pool as change_password_set_db_pool
from src.routers.user.user_settings import router as user_settings_router, set_db_pool as user_settings_set_db_pool
from src.routers.user.ai_connections import router as user_ai_connections_router, set_db_pool as user_ai_connections_set_db_pool
from src.routers.user.model_tuning import router as user_model_tuning_router, set_db_pool as user_model_tuning_set_db_pool
from src.routers.user.database_connections import router as user_database_connections_router, set_db_pool as user_database_connections_set_db_pool
from src.routers.auth.register import router as register_router, set_db_pool as register_set_db_pool
from src.routers.auth.password_reset import router as password_reset_router, set_db_pool as password_reset_set_db_pool
from src.routers.auth.email_verification import router as email_verification_router, set_db_pool as email_verification_set_db_pool
from src.routers.auth.login import router as login_router, set_db_pool as login_set_db_pool
from src.chat_router import router as chat_router, set_db_pool as set_chat_pool
from src.middleware.debug_logging import trace_middleware

# Global database pool
_db_pool = None
# Dedicated pool for the data database (workbench_data)
_data_pool = None
security = HTTPBearer(auto_error=False)


# ============================================================
# DEPENDENCY: Get current user's language
# ============================================================

async def get_current_language(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security)
) -> str:
    """Dependency to get the current user's language preference."""
    global _db_pool
    return await get_user_language(request, credentials, _db_pool)


# ============================================================
# LIFESPAN MANAGEMENT
# ============================================================

async def _init_connection(conn: asyncpg.Connection) -> None:
    """Per-connection setup, run once for every connection in both pools.

    Item 32's json/jsonb codecs, and Item 12 of the timestamp plan's session-timezone
    pin.
    """
    # Item 12 of the timestamp plan: render every session in UTC.
    #
    # Defence, not mechanism. Every timestamp column is `timestamptz` since Item 7, so
    # the instant a row holds does not depend on this; only its rendering does. What the
    # pin buys is the case where a *naive* value slips through — a `datetime.utcnow()`
    # somebody reintroduces — because a naive value bound to a `timestamptz` column is
    # interpreted in the session zone, and with the zone pinned to UTC that happens to
    # be right rather than whatever the machine's operator set.
    #
    # Not a substitute for producing instants: a naive value on a server whose zone is
    # not UTC still writes the wrong instant. This removes one machine-dependent
    # variable from the failure and no more.
    await conn.execute("SET TIME ZONE 'UTC'")

    await conn.set_type_codec(
        "json", encoder=json.dumps, decoder=json.loads, schema="pg_catalog",
    )
    await conn.set_type_codec(
        "jsonb", encoder=json.dumps, decoder=json.loads, schema="pg_catalog",
    )


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle with shared memory and database pool."""
    global _db_pool, _data_pool

    logging.info("Starting up...")

    # Initialize feature licensing (Golden Screwdriver)
    load_licence()

    # Initialize database pool
    DATABASE_URL = os.getenv("DATABASE_URL")
    if not DATABASE_URL:
        logging.error("DATABASE_URL not set")
        raise RuntimeError("DATABASE_URL environment variable not set")

    _db_pool = await asyncpg.create_pool(DATABASE_URL, init=_init_connection)
    _cluster = _database_cluster(DATABASE_URL)
    logging.info(
        "Workbench database cluster: %s:%s (database %r)",
        _cluster["host"], _cluster["port"], urlparse(DATABASE_URL).path.lstrip("/"),
    )
    logging.info("Database pool initialized.")

    # Data database pool (workbench_data) — derived from DATABASE_URL, no new env entry.
    # ensure_data_database auto-creates workbench_data on first run if it is absent.
    data_dsn = await ensure_data_database(DATABASE_URL)
    _data_pool = await asyncpg.create_pool(data_dsn, init=_init_connection)
    set_data_pool(_data_pool)
    logging.info("Data database pool initialized (workbench_data).")

    # Assign the one pool every module reads (src/db.py). This is the whole wiring:
    # one assignment, findable with one grep, and nothing per-module to forget.
    # The per-module set_db_pool calls below are the old convention and are being
    # retired module by module — a module absent from db.MIGRATED still needs its own.
    from src import db as _db_module
    _db_module.set_pool(_db_pool)

    # Set database pool for routers
    datasets.set_db_pool(_db_pool)
    recipes.set_db_pool(_db_pool)
    groups.set_db_pool(_db_pool)
    dbdesign.schema.set_db_pool(_db_pool)
    dbdesign.report.set_db_pool(_db_pool)
    dbdesign.streaming.set_db_pool(_db_pool)
    dbdesign.email_pdf.set_db_pool(_db_pool)
    notebooks.set_db_pool(_db_pool)
    set_chat_pool(_db_pool)
    audio_presets_set_db_pool(_db_pool)
    access_set_db_pool(_db_pool)
    licence_set_db_pool(_db_pool)
    browse_set_db_pool(_db_pool)
    admin_users_set_db_pool(_db_pool)
    admin_groups_set_db_pool(_db_pool)
    admin_global_settings_set_db_pool(_db_pool)
    admin_ai_providers_set_db_pool(_db_pool)
    ai_providers_set_db_pool(_db_pool)
    test_ai_set_db_pool(_db_pool)
    aitesting_dataset_set_db_pool(_db_pool)
    admin_models_set_db_pool(_db_pool)
    admin_visualization_types_set_db_pool(_db_pool)
    visualization_types_set_db_pool(_db_pool)
    visualization_instances_set_db_pool(_db_pool)
    user_profile_set_db_pool(_db_pool)
    user_role_set_db_pool(_db_pool)
    change_password_set_db_pool(_db_pool)
    user_settings_set_db_pool(_db_pool)
    user_ai_connections_set_db_pool(_db_pool)
    user_model_tuning_set_db_pool(_db_pool)
    user_database_connections_set_db_pool(_db_pool)
    register_set_db_pool(_db_pool)
    password_reset_set_db_pool(_db_pool)
    email_verification_set_db_pool(_db_pool)
    login_set_db_pool(_db_pool)
    languages_set_db_pool(_db_pool)

    yield  # Application runs here

    logging.info("Shutting down...")

    # Close database pool
    if _db_pool:
        await _db_pool.close()
        logging.info("Database pool closed.")

    # Close data database pool
    if _data_pool:
        await _data_pool.close()
        logging.info("Data database pool closed.")

    logging.info("Shutdown complete.")


# ============================================================
# FASTAPI APPLICATION
# ============================================================

app = FastAPI(
    title="Statisticians Workbench API",
    version=VERSION,
    lifespan=lifespan,
)


# ============================================================
# GLOBAL EXCEPTION HANDLER WITH TRANSLATION
# ============================================================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Return detailed validation errors with translation support."""
    global _db_pool
    
    # Get language from request
    language = await get_user_language(request, None, _db_pool)
    
    errors = []
    for error in exc.errors():
        field = ".".join(str(loc) for loc in error["loc"])
        # Try to translate the error message
        error_msg = await t(_db_pool, language, f"validation.{error['type']}", 
                           error.get("msg", "Validation error"), 
                           field=field, 
                           msg=error.get("msg", "Validation error"))
        errors.append({
            "field": field,
            "message": error_msg,
            "type": error["type"],
        })
    
    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content={
            "detail": await t(_db_pool, language, VALIDATION["validation.error"], count=len(errors)),
            "errors": errors,
        },
    )


@app.exception_handler(HTTPException)
async def translated_http_exception_handler(request: Request, exc: HTTPException):
    """Reproduce FastAPI's default HTTPException handler, translating any
    intercepted library string (e.g. HTTPBearer's "Not authenticated")."""
    headers = getattr(exc, "headers", None)

    # Library-string intercept: translate the detail if it is a fixed string we
    # have chosen to intercept.
    if isinstance(exc.detail, str):
        key = discover_intercept(exc.detail)
        if key:
            language = get_language_from_header(request)
            detail = await t(_db_pool, language, key, fallback=exc.detail)
            return JSONResponse(
                status_code=exc.status_code,
                content={"detail": detail},
                headers=headers,
            )

    # FastAPI's default http_exception_handler behaviour.
    if not is_body_allowed_for_status_code(exc.status_code):
        return Response(status_code=exc.status_code, headers=headers)
    return JSONResponse(
        {"detail": exc.detail}, status_code=exc.status_code, headers=headers
    )


# ============================================================
# CORS
# ============================================================

allowed_origins = os.getenv("ALLOWED_ORIGINS", "http://localhost:3000").split(",")
app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Trace logging for all failing requests (always active, no configuration)
app.middleware("http")(trace_middleware)


# ============================================================
# ROUTERS
# ============================================================

app.include_router(chat_router)
app.include_router(datasets.router)
app.include_router(browse_router, prefix="/api/datasets", tags=["datasets"])
app.include_router(recipes.router)
app.include_router(groups.router)
app.include_router(dbdesign.schema_router, prefix="/api/dbdesign", tags=["dbdesign"])
app.include_router(notebooks.router, prefix="/api/notebooks", tags=["notebooks"])
app.include_router(dbdesign.report_router, prefix="/api/dbdesign", tags=["dbdesign"])
app.include_router(dbdesign.streaming_router, prefix="/api/dbdesign", tags=["dbdesign"])
app.include_router(dbdesign.email_pdf_router, prefix="/api/dbdesign", tags=["dbdesign"])
app.include_router(audio_presets_router)
app.include_router(features_router)
app.include_router(licence_router)
app.include_router(access_router)
app.include_router(admin_users_router)
app.include_router(admin_groups_router)
app.include_router(admin_global_settings_router)
app.include_router(global_settings_public_router)
app.include_router(languages_router)
app.include_router(admin_ai_providers_router)
app.include_router(ai_providers_router)
app.include_router(test_ai_router)
app.include_router(admin_models_router)
app.include_router(admin_visualization_types_router)
app.include_router(visualization_types_router)
app.include_router(visualization_instances_router)
app.include_router(user_profile_router)
app.include_router(user_role_router)
app.include_router(change_password_router)
app.include_router(user_settings_router)
app.include_router(user_ai_connections_router)
app.include_router(user_model_tuning_router)
app.include_router(user_database_connections_router)
app.include_router(register_router)
app.include_router(password_reset_router)
app.include_router(email_verification_router)
app.include_router(login_router)


def _database_cluster(dsn: str | None) -> dict:
    """Describe the workbench database cluster the given DSN points at.

    Parsed from DATABASE_URL rather than queried, deliberately: the question
    this answers is "am I pointed at the cluster I think I am?", which must be
    answerable when the database itself is unreachable -- the moment /api/health
    is most likely to be called. Reachability is what pool_initialized reports.

    host and port are both returned: the same port on a different host is a
    different cluster, and a port alone cannot tell them apart.
    """
    if not dsn:
        return {"host": None, "port": None}
    parsed = urlparse(dsn)
    return {"host": parsed.hostname, "port": parsed.port or 5432}


# ============================================================
# HEALTH CHECK
# ============================================================

@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {
        "status": "healthy",
        "version": VERSION,
        "backend": BACKEND,
        "database": {
            "pool_initialized": _db_pool is not None,
            **_database_cluster(os.getenv("DATABASE_URL")),
        }
    }


# ============================================================
# ROOT
# ============================================================

@app.get("/hello")
async def hello(
    request: Request,
    language: str = Depends(get_current_language)
):
    global _db_pool
    return {"message": await t(_db_pool, language, SYSTEM["system.hello_world"])}


# ============================================================
# MAIN ENTRY POINT (for running with timestamps)
# ============================================================

if __name__ == "__main__":
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_config=None,  # Use our logging configuration
    )