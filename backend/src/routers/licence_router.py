"""
Golden Screwdriver — Licence Management Router.

Admin-only endpoints for managing the licence file through the web
interface. No SSH or filesystem access required.

DELETE /api/licence       — remove licence file, revert to open-source
POST  /api/licence/preview — validate a licence without installing
POST  /api/licence/install — write licence to disk and hot-reload
"""

import logging
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from src.utils.translation import t
from .translations import ROUTERS
from .common.translations import AUTH, COMMON, GROUPS
from src.routers.datasets.crud import get_current_language
from src.routers.admin.users import _auth, _is_admin

from src.licensing import (
    get_licence_path,
    get_licence_info,
    load_licence,
    verify_licence_content,
)

router = APIRouter(prefix="/api/licence", tags=["licence"])
security = HTTPBearer(auto_error=False)


_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


# ── Shared admin check ────────────────────────────────────────────

async def _require_admin(credentials: HTTPAuthorizationCredentials, language: str) -> None:
    """Return 401 for no/invalid token, 403 for a non-admin user."""
    uid = await _auth(credentials)
    if uid is None:
        raise HTTPException(status_code=401, detail=await t(_db_pool, language, AUTH["auth.unauthorized"]))
    if not await _is_admin(uid):
        raise HTTPException(status_code=403, detail=await t(_db_pool, language, GROUPS["groups.admin_required"]))


# ── DELETE ────────────────────────────────────────────────────────

@router.delete("")
async def delete_licence(
    request: Request,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """Remove the current licence file and revert to open-source mode."""
    await _require_admin(credentials, language)

    path = get_licence_path()

    if not os.path.exists(path):
        # Already in open-source mode — nothing to delete
        load_licence(path)
        return {
            "message": await t(_db_pool, language, ROUTERS["licence.no_file_to_delete"]),
            **get_licence_info(),
        }

    try:
        os.remove(path)
        logging.info("Licence file deleted: %s", path)
    except OSError as e:
        logging.error("Failed to delete licence file %s: %s", path, e)
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, ROUTERS["licence.delete_failed"], error=str(e)),
        )

    # Reload — will find no file and switch to open-source
    load_licence(path)

    return {
        "message": await t(_db_pool, language, ROUTERS["licence.delete_success"]),
        **get_licence_info(),
    }


# ── PREVIEW ───────────────────────────────────────────────────────

@router.post("/preview")
async def preview_licence(
    request: Request,
    body: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """
    Validate a licence JSON string without installing it.

    Request body: {"content": "<licence JSON string>"}
    """
    await _require_admin(credentials, language)

    content = body.get("content")
    if not content or not isinstance(content, str):
        raise HTTPException(status_code=422, detail=await t(_db_pool, language, ROUTERS["licence.missing_content"]))

    result = verify_licence_content(content)

    if not result.get("valid"):
        return {
            "valid": False,
            "error": result.get("error", "Unknown validation error"),
        }

    return {
        "valid": True,
        **{k: v for k, v in result.items() if k not in ("valid", "error")},
    }


# ── INSTALL ───────────────────────────────────────────────────────

@router.post("/install")
async def install_licence(
    request: Request,
    body: dict,
    credentials: HTTPAuthorizationCredentials = Depends(security),
    language: str = Depends(get_current_language),
):
    """
    Validate, write, and hot-reload a licence file.

    Request body: {"content": "<licence JSON string>"}

    The licence is validated first. If valid, it is written to the
    configured licence path and load_licence() is called to reload
    the in-memory feature set without restarting the server.
    """
    await _require_admin(credentials, language)

    content = body.get("content")
    if not content or not isinstance(content, str):
        raise HTTPException(status_code=422, detail=await t(_db_pool, language, ROUTERS["licence.missing_content"]))

    # Validate first
    result = verify_licence_content(content)
    if not result.get("valid"):
        raise HTTPException(
            status_code=400,
            detail=result.get("error", "Licence validation failed"),
        )

    path = get_licence_path()

    # Write to disk
    try:
        with open(path, "w", encoding="utf-8") as f:
            f.write(content)
        logging.info("Licence file written to %s", path)
    except OSError as e:
        logging.error("Failed to write licence file %s: %s", path, e)
        raise HTTPException(
            status_code=500,
            detail=await t(_db_pool, language, ROUTERS["licence.write_failed"], error=str(e)),
        )

    # Hot-reload
    load_licence(path)

    return {
        "message": await t(_db_pool, language, ROUTERS["licence.install_success"]),
        **get_licence_info(),
    }
