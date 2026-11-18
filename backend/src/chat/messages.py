"""
Message management for chat.
Handles adding and retrieving messages from chats.
"""

import asyncpg
from typing import Dict, Any


async def add_message(
    db_pool: asyncpg.Pool,
    chat_id: int,
    role: str,
    content: str
) -> Dict[str, Any]:
    """
    Add a message to a chat.
    
    Args:
        db_pool: Database connection pool
        chat_id: The chat ID
        role: The message role ('user', 'assistant', or 'system')
        content: The message content
        
    Returns:
        Dict containing the created message
        
    Raises:
        ValueError: If the role is invalid or the chat is not found
    """
    if role not in ("user", "assistant", "system"):
        raise ValueError("Invalid role")
    
    async with db_pool.acquire() as conn:
        # Verify chat exists
        chat = await conn.fetchrow('SELECT id FROM "Chat" WHERE id = $1', chat_id)
        if chat is None:
            raise ValueError("Chat not found")
        
        # Add message
        row = await conn.fetchrow(
            'INSERT INTO "Message" ("chatId", role, content) VALUES ($1, $2, $3) RETURNING id, "chatId", role, content, "createdAt"',
            chat_id, role, content
        )
        return dict(row)


async def get_messages_for_chat(
    db_pool: asyncpg.Pool,
    chat_id: int
) -> list:
    """
    Get all messages for a chat.
    
    Args:
        db_pool: Database connection pool
        chat_id: The chat ID
        
    Returns:
        List of message dictionaries ordered by creation time
    """
    async with db_pool.acquire() as conn:
        rows = await conn.fetch(
            'SELECT id, role, content, "createdAt" FROM "Message" WHERE "chatId" = $1 ORDER BY "createdAt" ASC',
            chat_id
        )
        return [dict(row) for row in rows]


async def get_last_message(
    db_pool: asyncpg.Pool,
    chat_id: int
) -> Dict[str, Any]:
    """
    Get the most recent message in a chat.
    
    Args:
        db_pool: Database connection pool
        chat_id: The chat ID
        
    Returns:
        Dict containing the most recent message, or None if no messages
    """
    async with db_pool.acquire() as conn:
        row = await conn.fetchrow(
            'SELECT id, role, content, "createdAt" FROM "Message" WHERE "chatId" = $1 ORDER BY "createdAt" DESC LIMIT 1',
            chat_id
        )
        return dict(row) if row else None