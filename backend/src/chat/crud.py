"""
Chat CRUD operations.
Handles create, read, update, and delete operations for chats.
"""

import asyncpg
from typing import List, Dict, Any, Optional


async def create_chat(
    db_pool: asyncpg.Pool,
    user_id: str,
    title: Optional[str] = None
) -> Dict[str, Any]:
    """
    Create a new chat for a user.
    
    Args:
        db_pool: Database connection pool
        user_id: The user ID
        title: Optional chat title (defaults to "New Chat")
        
    Returns:
        Dict containing the created chat with an empty messages list
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'INSERT INTO "Chat" ("userId", title, "updatedAt") VALUES ($1, $2, NOW()) RETURNING id, "userId", title, "createdAt", "updatedAt"',
            user_id, title or "New Chat"
        )
        chat = dict(row)
        chat["messages"] = []
        return chat


async def get_chat(
    db_pool: asyncpg.Pool,
    chat_id: int,
    user_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get a chat by ID with its messages.
    
    Args:
        db_pool: Database connection pool
        chat_id: The chat ID
        user_id: Optional user ID for ownership verification
        
    Returns:
        Dict containing the chat with its messages
        
    Raises:
        ValueError: If the chat is not found
    """
    async with db_pool.acquire() as conn:
        if user_id:
            chat_row = await conn.fetchrow(
                'SELECT id, "userId", title, "createdAt", "updatedAt" FROM "Chat" WHERE id = $1 AND "userId" = $2',
                chat_id, user_id
            )
        else:
            chat_row = await conn.fetchrow(
                'SELECT id, "userId", title, "createdAt", "updatedAt" FROM "Chat" WHERE id = $1',
                chat_id
            )
        
        if chat_row is None:
            raise ValueError("Chat not found")
        
        chat = dict(chat_row)
        
        # Get messages
        rows = await conn.fetch(
            'SELECT id, role, content, "createdAt" FROM "Message" WHERE "chatId" = $1 ORDER BY "createdAt" ASC',
            chat_id
        )
        chat["messages"] = [dict(row) for row in rows]
        return chat


async def get_user_chats(
    db_pool: asyncpg.Pool,
    user_id: str,
    limit: int = 10,
    offset: int = 0
) -> List[Dict[str, Any]]:
    """
    Get all chats for a user.
    
    Args:
        db_pool: Database connection pool
        user_id: The user ID
        limit: Maximum number of chats to return
        offset: Pagination offset
        
    Returns:
        List of chat dictionaries (without messages)
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT id, "userId", title, "createdAt", "updatedAt" FROM "Chat" WHERE "userId" = $1 ORDER BY "updatedAt" DESC LIMIT $2 OFFSET $3',
            user_id, limit, offset
        )
        return [dict(row) for row in rows]


async def delete_chat(
    db_pool: asyncpg.Pool,
    chat_id: int,
    user_id: Optional[str] = None
) -> bool:
    """
    Delete a chat.
    
    Args:
        db_pool: Database connection pool
        chat_id: The chat ID
        user_id: Optional user ID for ownership verification
        
    Returns:
        True if deleted, False if not found
    """
    async with db_pool.acquire() as conn:
        if user_id:
            result = await conn.execute(
                'DELETE FROM "Chat" WHERE id = $1 AND "userId" = $2',
                chat_id, user_id
            )
        else:
            result = await conn.execute(
                'DELETE FROM "Chat" WHERE id = $1',
                chat_id
            )
        return result != "DELETE 0"


async def update_chat_title(
    db_pool: asyncpg.Pool,
    chat_id: int,
    user_id: str,
    title: str
) -> Dict[str, Any]:
    """
    Update a chat's title.
    
    Args:
        db_pool: Database connection pool
        chat_id: The chat ID
        user_id: The user ID (for ownership verification)
        title: The new title
        
    Returns:
        Dict containing the updated chat
        
    Raises:
        ValueError: If the chat is not found or not owned by the user
    """
    async with db_pool.acquire() as conn:
        # Verify ownership
        chat = await conn.fetchrow(
            'SELECT id FROM "Chat" WHERE id = $1 AND "userId" = $2',
            chat_id, user_id
        )
        if chat is None:
            raise ValueError("Chat not found or not owned by user")
        
        # Update title
        row = await conn.fetchrow(
            'UPDATE "Chat" SET title = $1, "updatedAt" = NOW() WHERE id = $2 RETURNING id, "userId", title, "createdAt", "updatedAt"',
            title, chat_id
        )
        chat_result = dict(row)
        chat_result["messages"] = []
        return chat_result