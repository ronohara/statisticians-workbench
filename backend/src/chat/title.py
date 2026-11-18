"""
Title generation for chat.
Generates descriptive titles for chats based on the first user message.
"""

import asyncpg
from typing import Dict, Any

from .connection import get_connection_details
from src.utils.ai_limits import resolve_ai_limits_for_model
from src.utils.connection_timeouts import resolve_connection_timeouts
from .providers import ProviderFactory
from .crud import update_chat_title

# The cap a title's timeout is clamped to. Title generation is a five-to-seven-word
# workload, so it must not inherit a pair of timeouts tuned for a 345-second local
# model: the resolved value is still honoured, capped here. Ten seconds, because the
# surrounding comment bounds it — "a 30 s budget for a five-word title must not spend
# 10 s of it shaking hands" — so the connect phase has less than the cap to work
# with. The constant was *referenced* by that code and *defined* nowhere, which the
# undefined-name gate found on 2026-11-10.
TITLE_MAX_TIMEOUT_SECONDS = 10


async def generate_chat_title(
    db_pool: asyncpg.Pool,
    user_id: str,
    chat_id: int,
    connection_id: int,
    user_message: str
) -> Dict[str, Any]:
    """
    Generate a title for a chat based on the first user message.
    
    Args:
        db_pool: Database connection pool
        user_id: The user ID
        chat_id: The chat ID
        connection_id: The AI connection ID to use
        user_message: The first user message
        
    Returns:
        Dict containing the generated title
        
    Raises:
        ValueError: If title generation fails
    """
    # Get connection details
    conn_details = await get_connection_details(db_pool, connection_id, user_id)
    
    # Build messages for title generation
    system_message = {
        "role": "system",
        "content": "Generate a short, descriptive title (max 5-7 words) for a chat that starts with the following user message. Return only the title, no extra text."
    }
    user_msg = {"role": "user", "content": user_message}
    messages = [system_message, user_msg]
    
    try:
        # Create provider instance
        provider = ProviderFactory.create(
            conn_details["provider"],
            api_key=conn_details["apiKey"],
            endpoint=conn_details["endpoint"]
        )
        
        # Title generation is a SHORT workload — five to seven words — so it takes the
        # resolved bound CAPPED at TITLE_MAX_TIMEOUT_SECONDS. That cap is the
        # "caller decides the request-level override" half of the design: one resolved
        # value cannot serve a chat turn and a title at once, and a title that waits
        # out a pair tuned for a 345-second local model is a title nobody sees.
        async with db_pool.acquire() as limits_conn:
            limits = await resolve_ai_limits_for_model(limits_conn, connection_id, "")
            # Item 4a: this call DOES carry a connection id — the item predicted it
            # might not, and was wrong — so the connection's own connect budget applies
            # here too. Clamped to the title cap below, because a 30 s budget for a
            # five-word title must not spend 10 s of it shaking hands.
            conn_timeouts = await resolve_connection_timeouts(limits_conn, connection_id)
        title_timeout = min(float(limits.timeout_seconds), TITLE_MAX_TIMEOUT_SECONDS)
        title_connect_timeout = min(float(conn_timeouts.connect_seconds), title_timeout)

        # Call the provider
        result = await provider.call(
            messages=messages,
            model=None,
            temperature=limits.temperature,
            max_tokens=limits.max_tokens,
            timeout=title_timeout,
            connect_timeout=title_connect_timeout,
        )
        title = result["content"].strip()
        
        # Truncate if too long
        if len(title) > 100:
            title = title[:97] + "..."
        
        # Update the chat title
        await update_chat_title(db_pool, chat_id, user_id, title)
        return {"title": title}
        
    except Exception as e:
        raise ValueError(f"Title generation failed: {str(e)}")