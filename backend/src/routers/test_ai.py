"""
AI Connection Test Router — P2 Group 3, item 17 (Prisma-removal plan).

Drop-in replacement for the frontend handler:
  frontend/app/api/test-ai/route.ts   (POST)

This is the "test connection" endpoint. Contract parity:

  - POST {provider, apiKey, endpoint}. UNGATED — the frontend has NO session /
    checkAdmin check (a quirk, tracked in workbench-documents/development-records/code-quirks.md).
  - Body parse error / null body -> 500 {"success": false, "error": "Internal
    server error"} (the outer catch mirrors the frontend's single try/catch).
  - provider lookup by code (select code, name, isLocal, requiresApiKey,
    defaultEndpoint). Missing -> 400 "Unknown provider: {provider}".
  - apiKey trimmed; requiresApiKey && !apiKey -> 400 "API key is required for
    {name}.".
  - baseUrl = endpoint?.trim() || defaultEndpoint || ""; empty -> 400
    "No endpoint configured for this provider.".
  - OpenAI-compatible (non-local): if baseUrl lacks /v1, try
    {baseUrl}/v1/models first (10s); OK -> 200 "Endpoint at {baseUrl}/v1 is
    valid." (fall through on error). Then GET {baseUrl}/models (300s); OK ->
    200 "Endpoint at {baseUrl} is valid."; non-OK -> 500 "Connection failed:
    {msg}" (msg = error.error.message || error.message || "HTTP <status>").
  - Local (Ollama): GET {baseUrl}/api/tags (10s); OK -> 200 "{name} server at
    {baseUrl} is reachable."; non-OK -> 500 "{name} responded with status
    {status}"; timeout -> 500 "Connection timeout. Is {name} running at
    {baseUrl}?".

Error shape: {success: false, error: "<string>"} (NOT the bare {error} of
items 13-16). Success: {success: true, message: "<string>"}. Routed through
t() (option b): the English fallback matches the frontend's exact string.

Auth: NONE (mirrors the frontend). Language comes from Accept-Language /
default "en" via get_user_language(request, None, pool).
"""

import json
import logging

import httpx
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from src.routers.translations import TEST_AI
from src.utils.language import get_user_language
from src.utils.logger import Logger
from src.utils.translation import t

logger = Logger("test_ai", see_time=True, console_log=True)

router = APIRouter(prefix="/api/test-ai", tags=["test-ai"])

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


async def _t_success(status: int, key: str, language: str, **kwargs) -> JSONResponse:
    message = await t(_db_pool, language, TEST_AI[key], **kwargs)
    return JSONResponse(status_code=status, content={"success": True, "message": message})


async def _t_error(status: int, key: str, language: str, **kwargs) -> JSONResponse:
    message = await t(_db_pool, language, TEST_AI[key], **kwargs)
    return JSONResponse(status_code=status, content={"success": False, "error": message})


def _error_msg(res, status_code: int) -> str:
    """Mirror errorData.error?.message || errorData.message || "HTTP <status>"."""
    error_msg = f"HTTP {status_code}"
    try:
        data = res.json()
        nested = data.get("error")
        if isinstance(nested, dict) and nested.get("message"):
            error_msg = nested["message"]
        elif data.get("message"):
            error_msg = data["message"]
    except Exception:
        pass
    return error_msg


@router.post("")
async def test_ai(req: Request):
    language = await get_user_language(req, None, _db_pool)
    try:
        body = json.loads(await req.body() or b"")
        if body is None:
            # Destructuring null throws in the frontend -> 500.
            return await _t_error(500, "test_ai.internal_error", language)
        if not isinstance(body, dict):
            provider = api_key = endpoint = None
        else:
            provider = body.get("provider")
            api_key = body.get("apiKey")
            endpoint = body.get("endpoint")

        async with _db_pool.acquire() as conn:
            provider_record = await conn.fetchrow(
                'SELECT code, name, "isLocal", "requiresApiKey", "defaultEndpoint" '
                'FROM "AIProvider" WHERE code = $1',
                provider,
            )

        if provider_record is None:
            return await _t_error(400, "test_ai.unknown_provider", language, provider=provider)

        trimmed_api_key = api_key.strip() if api_key else None

        if provider_record["requiresApiKey"] and not trimmed_api_key:
            return await _t_error(400, "test_ai.api_key_required", language,
                                  name=provider_record["name"])

        base_url = (endpoint.strip() if endpoint else None) or provider_record["defaultEndpoint"] or ""
        if not base_url:
            return await _t_error(400, "test_ai.no_endpoint", language)

        is_local = provider_record["isLocal"]
        code = provider_record["code"]

        # OpenAI-compatible providers without /v1: try {baseUrl}/v1/models first.
        if not is_local:
            base_url = base_url.rstrip("/")
            if not base_url.endswith("/v1"):
                test_url = f"{base_url}/v1/models"
                test_headers = {"Authorization": f"Bearer {trimmed_api_key}"}
                try:
                    async with httpx.AsyncClient(timeout=10.0) as client:
                        res = await client.get(test_url, headers=test_headers)
                    if res.status_code == 200:
                        return await _t_success(200, "test_ai.endpoint_v1_valid", language,
                                                baseUrl=base_url)
                except Exception:
                    pass  # fall through to the no-/v1 path

        # Local providers (Ollama)
        if is_local:
            url = f"{base_url.rstrip('/')}/api/tags"
            try:
                async with httpx.AsyncClient(timeout=10.0) as client:
                    res = await client.get(url)
                if res.status_code == 200:
                    return await _t_success(200, "test_ai.server_reachable", language,
                                            name=provider_record["name"], baseUrl=base_url)
                return await _t_error(500, "test_ai.responded_with_status", language,
                                      name=provider_record["name"], status=res.status_code)
            except httpx.TimeoutException:
                return await _t_error(500, "test_ai.connection_timeout_local", language,
                                      name=provider_record["name"], baseUrl=base_url)
            except Exception as e:
                logger.log_message(f"test_ai local probe failed: {type(e).__name__}: {e}", level=logging.ERROR)
                return await _t_error(500, "test_ai.fetch_failed", language)

        # All other providers (OpenAI-compatible): GET {baseUrl}/models
        url = f"{base_url.rstrip('/')}/models"
        headers = {"Authorization": f"Bearer {trimmed_api_key}"}
        try:
            async with httpx.AsyncClient(timeout=300.0) as client:
                res = await client.get(url, headers=headers)
            if res.status_code == 200:
                return await _t_success(200, "test_ai.endpoint_valid", language, baseUrl=base_url)
            return await _t_error(500, "test_ai.connection_failed", language,
                                  msg=_error_msg(res, res.status_code))
        except Exception as e:
            logger.log_message(f"test_ai models probe failed: {type(e).__name__}: {e}", level=logging.ERROR)
            return await _t_error(500, "test_ai.fetch_failed", language)
    except Exception as e:
        logger.log_message(f"test_ai handler failed: {type(e).__name__}: {e}", level=logging.ERROR)
        return await _t_error(500, "test_ai.internal_error", language)
