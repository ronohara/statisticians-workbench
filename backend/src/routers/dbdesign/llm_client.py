"""
Shared LLM client for database design AI specialists.

Provides a single `call_llm()` function used by Schema AI, Semantic AI,
and Integration AI. Handles AI provider lookup, API key decryption, HTTP
calls with retry logic, and structured error responses.

No LangChain dependency — direct HTTP call to the OpenAI-compatible
chat completions endpoint.
"""

import json
import logging
from typing import Optional

import httpx

from src.chat.connection import get_connection_details
from src.chat.language import language_instruction
from src.utils.translation import t
from .translations import LLM_CLIENT_TK

# ── Provider Lookup ──────────────────────────────────────────────────

async def _get_ai_connection(
    db_pool,
    user_id: str,
    connection_id: Optional[int] = None,
) -> dict:
    """Look up an AI connection and return {api_key, endpoint, model}.

    If connection_id is given, uses that specific connection.
    Otherwise, returns the first available connection for the user.

    The resolution itself — owned or shared, and the provider's default endpoint
    when the connection carries none of its own — belongs to the shared
    resolver; this keeps its own "first available" fallback and its
    never-raises contract.
    """
    if not connection_id:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                """SELECT "connectionId" FROM "UserAIConnection"
                   WHERE "userId" = $1
                   OR ("isShared" = true
                       AND "aiConnectionGroup" IN (
                           SELECT "userGroup" FROM "User" WHERE id = $1
                       ))
                   LIMIT 1""",
                user_id,
            )
        if not row:
            return {}
        connection_id = row["connectionId"]

    try:
        details = await get_connection_details(db_pool, connection_id, user_id)
    except ValueError:
        return {}

    return {
        "api_key": details["apiKey"],
        "endpoint": details["endpoint"],
        "model": details["model"],
    }


# ── LLM Call ─────────────────────────────────────────────────────────

async def call_llm(
    system_prompt: str,
    user_context: str,
    *,
    db_pool=None,
    user_id: str = "default",
    connection_id: Optional[int] = None,
    model: Optional[str] = None,
    max_retries: int = 2,
    timeout_seconds: float = 240.0,
    temperature: float = 0.1,
    max_tokens: Optional[int] = None,
    language: str = "en",
    caller: str = "LLM",
) -> dict:
    """Call the LLM and return {'content': str} or {'error': str}.

    Args:
        system_prompt: System message for the LLM (role, task, output format).
        user_context: User message with the schema/context to analyse.
        db_pool: Async database pool for AI connection lookup.
        user_id: User ID for AI connection lookup.
        connection_id: Optional specific AI connection to use.
        max_retries: Number of retry attempts on failure (default: 2).
        timeout_seconds: HTTP request timeout (default: 90).
        temperature: LLM temperature (default: 0.1 — deterministic).
        max_tokens: Maximum output tokens. If None, uses the model's default
                    based on the resolved model name (32K for pro, 8K for flash).
        language: ISO 639-1 code for the response language (default: "en").

    Returns:
        dict with 'content' (str) on success or 'error' (str) on failure.
        Never raises — all errors are returned as {'error': ...}.
    """
    # Resolve AI connection — the user's configured provider is the only source;
    # there is no environment-variable fallback.
    api_key = None
    endpoint = None

    if db_pool is not None:
        conn_info = await _get_ai_connection(db_pool, user_id, connection_id)
        if conn_info.get("api_key"):
            api_key = conn_info["api_key"]
            endpoint = conn_info["endpoint"]
            model = model or conn_info["model"]

    if not api_key or not endpoint:
        return {"error": await t(db_pool, language, LLM_CLIENT_TK["dbdesign.llm.no_ai_provider"])}

    if not model:
        return {"error": await t(db_pool, language, LLM_CLIENT_TK["dbdesign.llm.no_model"])}

    # Resolve max_tokens from model if not explicitly set
    if max_tokens is None:
        _MODEL_MAX_TOKENS: dict[str, int] = {
            "deepseek-v4-pro": 32768,
            "deepseek-v4-flash": 8192,
            "deepseek-chat": 8192,
            "deepseek-reasoner": 8192,
        }
        max_tokens = _MODEL_MAX_TOKENS.get(model, 8192)

    # Prime language: if the user's preferred language is not English,
    # prepend a priming instruction to the system prompt.
    system_prompt = language_instruction(language) + system_prompt

    # Ensure endpoint ends with /chat/completions
    if not endpoint.endswith("/chat/completions"):
        endpoint = endpoint.rstrip("/") + "/chat/completions"

    # Build payload
    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_context},
        ],
        "temperature": temperature,
        "max_tokens": max_tokens,
    }

    last_error = None
    for attempt in range(1, max_retries + 1):
        try:
            async with httpx.AsyncClient(timeout=timeout_seconds) as client:
                resp = await client.post(
                    endpoint,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json=payload,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    content = data["choices"][0]["message"]["content"]
                    # Empty response — LLM sometimes returns nothing for very large prompts
                    if not content or not content.strip():
                        logging.getLogger(__name__).warning(
                            "[%s] LLM returned empty content (attempt %d/%d) — retrying",
                            caller, attempt, max_retries,
                        )
                        last_error = await t(db_pool, language, LLM_CLIENT_TK["dbdesign.llm.empty_content"])
                        continue
                    logging.getLogger(__name__).info(
                        "[%s] LLM call succeeded: %d chars, attempt %d/%d",
                        caller, len(content), attempt, max_retries,
                    )
                    return {"content": content}

                # Non-200 response
                error_msg = await t(db_pool, language, LLM_CLIENT_TK["dbdesign.llm.http_error"], status_code=resp.status_code)
                try:
                    body = resp.json()
                    err = body.get("error", {})
                    if isinstance(err, dict):
                        error_msg = err.get("message") or err.get("type") or error_msg
                    elif isinstance(err, str):
                        error_msg = err
                except Exception:
                    error_msg = resp.text[:200] or error_msg

                logging.getLogger(__name__).warning(
                    "[%s] LLM call failed (attempt %d/%d): %s",
                    caller, attempt, max_retries, error_msg,
                )
                last_error = error_msg

                # Don't retry on 4xx errors (auth, bad request)
                if 400 <= resp.status_code < 500:
                    break

        except httpx.TimeoutException:
            last_error = await t(db_pool, language, LLM_CLIENT_TK["dbdesign.llm.timeout"], timeout_seconds=timeout_seconds)
            logging.getLogger(__name__).warning(
                "[%s] LLM timeout (attempt %d/%d)", caller, attempt, max_retries,
            )
        except Exception as e:
            last_error = str(e)
            logging.getLogger(__name__).warning(
                "LLM error (attempt %d/%d): %s", attempt, max_retries, e,
            )

    return {"error": last_error or await t(db_pool, language, LLM_CLIENT_TK["dbdesign.llm.unknown_error"])}


# ── JSON Extraction Helper ───────────────────────────────────────────

def extract_json(content: str) -> Optional[dict]:
    """Extract a JSON object from LLM output that may be wrapped in markdown.

    Handles:
      - Pure JSON: {"key": "value"}
      - Markdown code block: ```json\n{...}\n```
      - Generic code block: ```\n{...}\n```
    """
    if not content:
        return None

    text = content.strip()

    # Try parsing directly
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass

    # Try extracting from markdown code block
    import re
    # ```json ... ```
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text)
    if match:
        try:
            return json.loads(match.group(1))
        except json.JSONDecodeError:
            pass

    # Try sanitising common LLM JSON errors (raw control characters in strings)
    # LLMs sometimes output actual newlines/tabs inside JSON string values,
    # which json.loads rejects. Escape them within string contexts.
    def _sanitize_json_strings(s: str) -> str:
        """Escape raw control characters inside JSON string values."""
        result = []
        in_string = False
        escape = False
        for ch in s:
            if escape:
                result.append(ch)
                escape = False
                continue
            if ch == "\\":
                result.append(ch)
                escape = True
                continue
            if ch == '"':
                in_string = not in_string
                result.append(ch)
                continue
            if in_string:
                if ch == "\n":
                    result.append("\\n")
                elif ch == "\r":
                    result.append("\\r")
                elif ch == "\t":
                    result.append("\\t")
                else:
                    result.append(ch)
            else:
                result.append(ch)
        return "".join(result)

    # Try finding a JSON object by brace matching (string-aware)
    brace_start = text.find("{")
    if brace_start >= 0:
        depth = 0
        in_string = False
        escape = False
        for i in range(brace_start, len(text)):
            ch = text[i]
            if escape:
                escape = False
                continue
            if ch == "\\":
                escape = True
                continue
            if ch == '"' and not escape:
                in_string = not in_string
                continue
            if in_string:
                continue
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[brace_start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        pass  # try next closing brace
        # If no valid JSON found, try the whole text from brace_start
        if depth == 0:
            candidate = text[brace_start:]
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                pass
            # Last resort: sanitize and retry
            try:
                return json.loads(_sanitize_json_strings(candidate))
            except json.JSONDecodeError:
                pass

    # Final fallback: sanitize the full text and try brace matching again
    sanitized = _sanitize_json_strings(text)
    brace_start = sanitized.find("{")
    if brace_start >= 0:
        try:
            return json.loads(sanitized[brace_start:])
        except json.JSONDecodeError:
            pass

    return None
