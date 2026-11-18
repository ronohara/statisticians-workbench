"""
Base provider interface for AI providers.
Defines the contract that all provider implementations must follow.
"""

from typing import List, Dict, Any, Optional
from abc import ABC, abstractmethod

class AIProvider(ABC):
    """Abstract base class for AI provider implementations."""
    
    def __init__(self, api_key: Optional[str] = None, endpoint: Optional[str] = None):
        """
        Initialize the provider.

        Args:
            api_key: The API key for the provider (if required)
            endpoint: The endpoint URL for the provider (if custom)
        """
        self.api_key = api_key
        self.endpoint = endpoint
        # The model the most recent call actually used, after the `model or
        # default` resolution. Empty until a call is made.
        #
        # Why it exists: the caller cannot work this out for itself. It passes
        # `model=None` when the connection has no stored default, and each provider
        # quietly substitutes its own — so the agent knows what it ASKED for and not
        # what ran. That gap made `TOOL_LOOP` print `model=-` on every turn that took
        # a default, which is every turn, and left a latency investigation unable to
        # name the model it was measuring.
        #
        # An attribute rather than a key on the returned dict, deliberately: the
        # returned dict becomes an entry in `messages`, which is persisted to the
        # session's jsonb and echoed back to the provider on the next round. A
        # `model` key there would be stored transcript data and would be sent back
        # as an unknown field.
        self.last_model: str = ""

    def resolve_model(self, model: Optional[str]) -> str:
        """The model this call will use — and the one place that records it.

        Both providers route their `model or default` choice through here, so
        `last_model` cannot drift from the model actually sent.
        """
        self.last_model = model or self.get_default_model()
        return self.last_model
    
    @abstractmethod
    async def call(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        tools: Optional[list] = None,
        **kwargs
    ) -> Dict[str, str]:
        """
        Call the AI provider with the given messages.
        
        Args:
            messages: List of message objects with 'role' and 'content'
            model: The model to use (if None, use provider default)
            tools: Optional OpenAI-style tool definitions; when provided the
                provider asks the model to make tool calls and, if the model
                does, includes the resulting ``tool_calls`` in the returned dict.
            **kwargs: Additional provider-specific parameters
            
        Returns:
            Dict with 'role' and 'content' keys, plus 'tool_calls' when the
            model chose to call tools.
            
        Raises:
            ValueError: If the call fails
        """
        pass
    
    @abstractmethod
    def get_default_model(self) -> str:
        """Get the default model for this provider."""
        pass
    
    @property
    @abstractmethod
    def provider_name(self) -> str:
        """Get the provider name (e.g., 'ollama', 'anthropic', 'openai')."""
        pass


class ProviderFactory:
    """Factory for creating provider instances."""
    
    _providers = {}
    
    @classmethod
    def register(cls, name: str, provider_class):
        """Register a provider class."""
        cls._providers[name] = provider_class
    
    @classmethod
    def create(cls, name: str, api_key: Optional[str] = None, endpoint: Optional[str] = None) -> AIProvider:
        """Create a provider instance."""
        if name not in cls._providers:
            raise ValueError(f"Unknown provider: {name}")
        return cls._providers[name](api_key, endpoint)
    
    @classmethod
    def get_provider_names(cls) -> List[str]:
        """Get a list of registered provider names."""
        return list(cls._providers.keys())