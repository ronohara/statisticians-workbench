import asyncpg
from typing import Optional, Dict, Any
from src.utils.logger import Logger

logger = Logger("db_utils", see_time=True, console_log=True)

async def get_user_default_connection(pool: asyncpg.Pool, user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get the user's default AI connection. Returns None if no default is set or no connections exist.
    """
    async with pool.acquire() as conn:
        # First, get the default connection ID from User table
        user_row = await conn.fetchrow(
            'SELECT "defaultAIConnectionId" FROM "User" WHERE id = $1',
            user_id
        )
        connection_id = user_row["defaultAIConnectionId"] if user_row else None

        if connection_id:
            # Fetch the connection details using connectionId
            row = await conn.fetchrow(
                'SELECT "connectionId", provider, "apiKey", endpoint, "defaultModel" FROM "UserAIConnection" WHERE "connectionId" = $1 AND "userId" = $2',
                connection_id, user_id
            )
            if row:
                return dict(row)
        
        # If no default, get the first connection (ordered by creation)
        row = await conn.fetchrow(
            'SELECT "connectionId", provider, "apiKey", endpoint, "defaultModel" FROM "UserAIConnection" WHERE "userId" = $1 ORDER BY "createdAt" ASC LIMIT 1',
            user_id
        )
        if row:
            return dict(row)
        
        return None

async def get_connection_by_id(pool: asyncpg.Pool, user_id: str, connection_id: int) -> Optional[Dict[str, Any]]:
    """
    Get a specific AI connection by its connectionId.
    """
    async with pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT "connectionId", provider, "apiKey", endpoint, "defaultModel" FROM "UserAIConnection" WHERE "connectionId" = $1 AND "userId" = $2',
            connection_id, user_id
        )
        if row:
            return dict(row)
        return None