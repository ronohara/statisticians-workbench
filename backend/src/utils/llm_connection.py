"""
Resolve a user's AI connection into a provider, ready to call.

Renamed from ``dspy_utils.py`` (plan D3, resolved 2026-11-01). The module no
longer depends on dspy: it answers one question — which provider, which model,
with which sampling settings — and returns it, leaving the call itself to the
caller. Go's mirror is ``internal/llm/connection.go``.

The sampling defaults are declared once, here. Item 6 of the litellm-removal
plan gives the Go side the same single declaration; until then Go passes the
two numbers literally at its call site.
"""

import asyncpg
import logging
from dataclasses import dataclass
from typing import Optional

from src.chat.providers import AIProvider, ProviderFactory
from src.utils.encryption import decrypt_field
from src.utils.logger import Logger

logger = Logger("llm_connection", see_time=True, console_log=True)

# Re-exported from ai_limits, which owns the fourth tier of the resolver. Declared
# here originally; moved because ai_limits needed them and importing this module from
# it closed a cycle (ai_limits → llm_connection → src.chat.providers → title →
# ai_limits). Importing them back keeps one declaration and one direction.
from src.utils.ai_limits import DEFAULT_MAX_TOKENS, DEFAULT_TEMPERATURE  # noqa: F401


@dataclass
class LLM:
    """A resolved AI provider, the model to call it with, and the sampling settings.

    Mirrors Go's ``llm.LLM``. The provider carries its own transport, so there
    is no third-party client object between this and the HTTP call.
    """

    provider: AIProvider
    model: str
    temperature: float
    max_tokens: int


async def create_llm(
    db_pool: asyncpg.Pool,
    user_id: str,
    connection_id: Optional[int] = None,
    model_name: Optional[str] = None,
    temperature: float = DEFAULT_TEMPERATURE,
    max_tokens: int = DEFAULT_MAX_TOKENS,
) -> LLM:
    """
    Resolve the user's AI connection and return a provider ready to call.

    If connection_id is provided, uses that specific connection.
    Otherwise, finds the user's default or first available connection.
    Also checks for shared connections from the user's group if no own
    connection is found.

    The sentinels ``DSPY_NO_CONNECTION`` and ``DSPY_DECRYPTION_FAILED`` keep
    their historical spelling: the caller matches on the substring and so does
    the Go caller, so they are a wire contract rather than a library reference.
    """
    logger.log_message(f"create_llm called: user_id={user_id}, connection_id={connection_id}, model_name={model_name}", level=logging.INFO)

    async with db_pool.acquire() as conn:
        # Get the user's group
        user_row = await conn.fetchrow(
            'SELECT "userGroup" FROM "User" WHERE id = $1',
            user_id
        )
        user_group = user_row["userGroup"] if user_row else "00"
        logger.log_message(f"User group: {user_group}", level=logging.INFO)

        row = None

        # If a specific connection_id is provided
        if connection_id is not None:
            logger.log_message(f"Looking for connection with connection_id: {connection_id}", level=logging.INFO)

            # First, check if the connection is owned by the user
            row = await conn.fetchrow(
                """
                SELECT c."connectionId", c.provider, c."apiKey", c.endpoint, c."defaultModel",
                       p.code, p."requiresApiKey", p."defaultEndpoint"
                FROM "UserAIConnection" c
                JOIN "AIProvider" p ON c.provider = p.code
                WHERE c."connectionId" = $1 AND c."userId" = $2
                """,
                connection_id, user_id
            )

            if row:
                logger.log_message(f"Found connection owned by user", level=logging.INFO)
            else:
                # If not owned, check if it's shared with the user's group
                logger.log_message(f"Checking for shared connection in group: {user_group}", level=logging.INFO)
                row = await conn.fetchrow(
                    """
                    SELECT c."connectionId", c.provider, c."apiKey", c.endpoint, c."defaultModel",
                           p.code, p."requiresApiKey", p."defaultEndpoint"
                    FROM "UserAIConnection" c
                    JOIN "AIProvider" p ON c.provider = p.code
                    WHERE c."connectionId" = $1 AND c."isShared" = true AND c."aiConnectionGroup" = $2
                    """,
                    connection_id, user_group
                )
                if row:
                    logger.log_message(f"Found shared connection in group {user_group}", level=logging.INFO)

        # If no specific connection_id, find the user's default or first available
        else:
            logger.log_message("No specific connection_id provided, looking for default or first available", level=logging.INFO)

            # First, try to get the user's default connection
            row = await conn.fetchrow(
                """
                SELECT c."connectionId", c.provider, c."apiKey", c.endpoint, c."defaultModel",
                       p.code, p."requiresApiKey", p."defaultEndpoint"
                FROM "UserAIConnection" c
                JOIN "AIProvider" p ON c.provider = p.code
                WHERE c."connectionId" = (SELECT "defaultAIConnectionId" FROM "User" WHERE id = $1)
                """,
                user_id
            )

            if row:
                logger.log_message(f"Found default connection", level=logging.INFO)

            # If no default, get the user's first own connection
            if row is None:
                row = await conn.fetchrow(
                    """
                    SELECT c."connectionId", c.provider, c."apiKey", c.endpoint, c."defaultModel",
                           p.code, p."requiresApiKey", p."defaultEndpoint"
                    FROM "UserAIConnection" c
                    JOIN "AIProvider" p ON c.provider = p.code
                    WHERE c."userId" = $1 AND c."aiConnectionGroup" = '00'
                    ORDER BY c."createdAt" ASC
                    LIMIT 1
                    """,
                    user_id
                )
                if row:
                    logger.log_message(f"Found first own connection", level=logging.INFO)

            # If still no connection and user is in a group, check for shared connections
            if row is None:
                logger.log_message(f"Looking for shared connection in group: {user_group}", level=logging.INFO)
                row = await conn.fetchrow(
                    """
                    SELECT c."connectionId", c.provider, c."apiKey", c.endpoint, c."defaultModel",
                           p.code, p."requiresApiKey", p."defaultEndpoint"
                    FROM "UserAIConnection" c
                    JOIN "AIProvider" p ON c.provider = p.code
                    WHERE c."isShared" = true AND c."aiConnectionGroup" = $1 AND c."userId" != $2
                    ORDER BY c."createdAt" ASC
                    LIMIT 1
                    """,
                    user_group, user_id
                )
                if row:
                    logger.log_message(f"Found shared connection in group", level=logging.INFO)

        if row is None:
            logger.log_message(f"No connection found. user_id={user_id}, connection_id={connection_id}, user_group={user_group}", level=logging.ERROR)
            # This is an internal error - the caller should catch and translate
            raise ValueError("DSPY_NO_CONNECTION")

        logger.log_message(f"Connection found: provider={row['provider']}, endpoint={row['endpoint']}", level=logging.INFO)

        api_key = None
        if row["apiKey"] and row["requiresApiKey"]:
            try:
                api_key = decrypt_field(row["apiKey"])
            except Exception as e:
                logger.log_message(f"Failed to decrypt API key: {e}", level=logging.ERROR)
                # This is an internal error - the caller should catch and translate
                raise ValueError("DSPY_DECRYPTION_FAILED")

        if model_name is None:
            model_name = row["defaultModel"] or "gpt-3.5-turbo"

        provider_code = row["provider"]
        endpoint = row["endpoint"] or row["defaultEndpoint"]

        # DIFFERENT from the dspy version this replaces: an unknown provider code
        # is an error rather than a silent fall back to an OpenAI-compatible
        # client, because the factory only knows the registered codes. Go wraps
        # the same failure the same way (internal/llm/connection.go), and the
        # caller's "other error" branch renders it — it must NOT be reported as
        # DSPY_NO_CONNECTION, which would name the wrong cause.
        try:
            provider = ProviderFactory.create(provider_code, api_key, endpoint)
        except ValueError as e:
            logger.log_message(f"Could not create provider {provider_code!r}: {e}", level=logging.ERROR)
            raise ValueError(f"create provider {provider_code}: {e}")

        logger.log_message(f"Created LLM for user {user_id}: provider={provider_code} model={model_name}")
        return LLM(provider=provider, model=model_name, temperature=temperature, max_tokens=max_tokens)
