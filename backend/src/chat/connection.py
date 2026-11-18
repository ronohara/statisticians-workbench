"""
Connection management for chat.
The single resolver for an AI connection, owned or shared.
"""

import asyncpg
from typing import Dict, Any
from src.utils.encryption import decrypt_field


async def get_connection_details(
    db_pool: asyncpg.Pool,
    connection_id: int,
    user_id: str,
) -> Dict[str, Any]:
    """
    Resolve an AI connection into what an LLM call needs.

    Owned connections are checked first, then a connection shared to the
    caller's group — so every caller accepts shared connections rather than
    some of them silently refusing one.

    A connection with no ``endpoint`` of its own falls back to its provider's
    ``defaultEndpoint``: the database is the source of truth for that default,
    and the sample environment creates connections without one.

    Args:
        db_pool: Database connection pool
        connection_id: The connection ID to look up
        user_id: The user ID making the request

    Returns:
        Dict containing provider, apiKey, endpoint and model

    Raises:
        ValueError: If the connection is not found or not accessible, or its
            stored API key cannot be decrypted
    """
    # Ensure connection_id is an integer
    try:
        connection_id = int(connection_id)
    except (TypeError, ValueError):
        raise ValueError("Invalid connection_id")

    async with db_pool.acquire() as conn:
        # Get the user's group
        user_row = await conn.fetchrow(
            'SELECT "userGroup" FROM "User" WHERE id = $1',
            user_id
        )
        user_group = user_row["userGroup"] if user_row else "00"

        # Check for owned connection first
        row = await conn.fetchrow(
            'SELECT provider, "apiKey", endpoint, "defaultModel" FROM "UserAIConnection" WHERE "connectionId" = $1 AND "userId" = $2',
            connection_id, user_id
        )

        # If not owned, check for shared connection from user's group
        if row is None:
            row = await conn.fetchrow(
                'SELECT provider, "apiKey", endpoint, "defaultModel" FROM "UserAIConnection" WHERE "connectionId" = $1 AND "isShared" = true AND "aiConnectionGroup" = $2',
                connection_id, user_group
            )

        if row is None:
            raise ValueError("connection.not_found_or_not_accessible")

        # A connection with no endpoint of its own takes its provider's default.
        # Without this an endpoint-less connection (the sample environment
        # creates one) is refused by the LLM layer as "not found", which sends
        # the caller looking in the wrong place.
        provider_default = None
        if not row["endpoint"]:
            provider_row = await conn.fetchrow(
                'SELECT "defaultEndpoint" FROM "AIProvider" WHERE code = $1',
                row["provider"],
            )
            provider_default = provider_row["defaultEndpoint"] if provider_row else None

    # Decrypt the API key. A key that is stored but will not decrypt is an
    # account anomaly: passing the stored value on as if it were the key only
    # produces a confusing 401 from the provider. A connection that stores no key
    # at all (a local provider) simply has none.
    api_key = None
    if row["apiKey"]:
        try:
            api_key = decrypt_field(row["apiKey"])
        except Exception as e:
            raise ValueError(f"Failed to decrypt API key: {e}")

    endpoint = row["endpoint"] or provider_default or None
    return {
        "provider": row["provider"],
        "apiKey": api_key,
        "endpoint": endpoint,
        "model": row["defaultModel"],
    }
