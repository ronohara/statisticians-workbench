"""
Chat Module – AI Chat Messaging
Part of the 0.0.10 "Statistical Foundation" milestone.
"""

from .manager import ChatManager
from .connection import get_connection_details
from .crud import create_chat, get_chat, get_user_chats, delete_chat, update_chat_title
from .messages import add_message
from .title import generate_chat_title

__all__ = [
    "ChatManager",
    "get_connection_details",
    "create_chat",
    "get_chat",
    "get_user_chats",
    "delete_chat",
    "update_chat_title",
    "add_message",
    "generate_chat_title",
]