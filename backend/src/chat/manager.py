"""
ChatManager orchestrator.
Coordinates all chat operations including message sending, AI provider calls,
and chat management.
"""

import asyncpg
import logging
from typing import List, Dict, Any, Optional

from .connection import get_connection_details
from .crud import create_chat, get_chat, get_user_chats, delete_chat, update_chat_title
from .messages import add_message, get_messages_for_chat
from .title import generate_chat_title
from .language import get_language_context_message, get_user_language, get_language_name
from src.utils.ai_limits import resolve_ai_limits_for_model, apply_timeout_override
from src.utils.connection_timeouts import resolve_connection_timeouts
from .providers import ProviderFactory

# Set up logger
logger = logging.getLogger(__name__)


class ChatManager:
    """
    ChatManager orchestrates all chat operations.
    
    This is the main entry point for chat functionality, coordinating
    message sending, AI provider calls, and chat management.
    """
    
    def __init__(self, db_pool: asyncpg.Pool):
        """
        Initialize the ChatManager.
        
        Args:
            db_pool: Database connection pool
        """
        self.db_pool = db_pool
    
    async def get_connection_details(self, connection_id: int, user_id: str) -> Dict[str, Any]:
        """Get AI connection details, checking owned and shared connections."""
        return await get_connection_details(self.db_pool, connection_id, user_id)
    
    async def create_chat(self, user_id: str, title: Optional[str] = None) -> Dict[str, Any]:
        """Create a new chat for a user."""
        return await create_chat(self.db_pool, user_id, title)
    
    async def get_chat(self, chat_id: int, user_id: Optional[str] = None) -> Dict[str, Any]:
        """Get a chat by ID with its messages."""
        return await get_chat(self.db_pool, chat_id, user_id)
    
    async def get_user_chats(self, user_id: str, limit: int = 10, offset: int = 0) -> List[Dict[str, Any]]:
        """Get all chats for a user."""
        return await get_user_chats(self.db_pool, user_id, limit, offset)
    
    async def delete_chat(self, chat_id: int, user_id: Optional[str] = None) -> bool:
        """Delete a chat."""
        return await delete_chat(self.db_pool, chat_id, user_id)
    
    async def update_chat_title(self, chat_id: int, user_id: str, title: str) -> Dict[str, Any]:
        """Update a chat's title."""
        return await update_chat_title(self.db_pool, chat_id, user_id, title)
    
    async def add_message(self, chat_id: int, role: str, content: str) -> Dict[str, Any]:
        """Add a message to a chat."""
        return await add_message(self.db_pool, chat_id, role, content)
    
    async def generate_chat_title(self, user_id: str, chat_id: int, connection_id: int, user_message: str) -> Dict[str, Any]:
        """Generate a title for a chat based on the first user message."""
        return await generate_chat_title(self.db_pool, user_id, chat_id, connection_id, user_message)
    
    async def send_message(
        self,
        user_id: str,
        chat_id: Optional[int],
        connection_id: int,
        user_message: str,
        model: Optional[str] = None,
        timeout_override: Optional[int] = None
    ) -> Dict[str, Any]:
        """
        Send a message to the AI and get a response.
        
        This is the main entry point for sending messages. It handles:
        1. Creating or retrieving the chat
        2. Adding the user message
        3. Injecting language context at request time
        4. Getting AI response
        5. Adding the assistant message
        6. Auto-renaming new chats
        
        Args:
            user_id: The user ID
            chat_id: The chat ID (None for new chat)
            connection_id: The AI connection ID
            user_message: The user's message
            model: Optional model override
            
        Returns:
            The updated chat with all messages
            
        Raises:
            ValueError: If there's an error in the process
        """
        # Get or create chat
        if chat_id is None:
            chat = await self.create_chat(user_id, title="New Chat")
            chat_id = chat["id"]
        else:
            chat = await self.get_chat(chat_id, user_id)
        
        # Add user message
        await self.add_message(chat_id, "user", user_message)
        
        # Auto-rename if the chat title is still "New Chat"
        if chat["title"] == "New Chat":
            new_title = user_message.strip()[:50]
            if new_title:
                await self.update_chat_title(chat_id, user_id, new_title)
        
        # Get all messages for context
        messages = await get_messages_for_chat(self.db_pool, chat_id)
        # Convert to list of dicts with role and content
        context_messages = [{"role": m["role"], "content": m["content"]} for m in messages]
        
        # Inject language context at request time (not stored in database)
        language_instruction = await get_language_context_message(self.db_pool, user_id)
        context_messages.insert(0, {"role": "system", "content": language_instruction})
        
        # Get connection details
        try:
            conn_details = await self.get_connection_details(connection_id, user_id)
        except Exception as e:
            raise ValueError(f"connection_error:{str(e)}")
        
        # Create provider instance
        try:
            provider = ProviderFactory.create(
                conn_details["provider"],
                api_key=conn_details["apiKey"],
                endpoint=conn_details["endpoint"]
            )
        except Exception as e:
            raise ValueError(f"connection_error:{str(e)}")
        
        # The limits in force for this (connection, model) pair. Chat is a long
        # workload — a turn can take minutes on a local CPU — so it takes the pair's
        # bound rather than the provider's default.
        try:
            async with self.db_pool.acquire() as limits_conn:
                limits = await resolve_ai_limits_for_model(limits_conn, connection_id, model or "")
                # The connection's own connect and probe budgets (plan Item 4a). Resolved
                # on the same connection as the pair limits: one acquire, two reads, and
                # no window in which one is from a different transaction view.
                conn_timeouts = await resolve_connection_timeouts(limits_conn, connection_id)
        except Exception as e:
            raise ValueError(f"connection_error:{str(e)}")

        # The per-request tier (AI limits plan, Item 12), applied on top of the resolved
        # ones and touching only the timeout. Refused outside the range rather than
        # clamped, so a caller learns the ceiling instead of having their number moved.
        if timeout_override is not None:
            try:
                limits = apply_timeout_override(limits, timeout_override)
            except ValueError:
                raise ValueError("timeout_out_of_range")

        # Call AI provider
        try:
            result = await provider.call(
                messages=context_messages,
                model=model,
                temperature=limits.temperature,
                max_tokens=limits.max_tokens,
                timeout=float(limits.timeout_seconds),
                connect_timeout=float(conn_timeouts.connect_seconds),
            )
            assistant_content = result["content"]
        except Exception as e:
            # The timeout in force travels WITH the error, because the route cannot know
            # it: the value comes from the resolver, and a retry preset must be computed
            # from what actually failed rather than from the request's own (possibly
            # absent) override. A plain ValueError with an attribute, so every existing
            # `str(e)`-based branch is unaffected.
            provider_error = ValueError(f"ai_provider_error:{str(e)}")
            provider_error.timeout_seconds_used = limits.timeout_seconds
            raise provider_error
        
        # Add assistant message
        await self.add_message(chat_id, "assistant", assistant_content)
        
        # Return updated chat
        return await self.get_chat(chat_id, user_id)