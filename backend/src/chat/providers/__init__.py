"""
AI Provider implementations for chat.
Exports provider classes and the ProviderFactory.
"""

from .base import AIProvider, ProviderFactory
from .ollama import OllamaProvider, OllamaRemoteProvider
from .openai import OpenAICompatibleProvider

# Register all providers when this module is imported
# (Registration happens in each provider module's __init__)

__all__ = [
    "AIProvider",
    "ProviderFactory",
    "OllamaProvider",
    "OllamaRemoteProvider",
    "OpenAICompatibleProvider",
]