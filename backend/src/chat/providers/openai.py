"""
OpenAI-compatible AI provider implementation.
Supports DeepSeek, OpenRouter, and other OpenAI-compatible APIs.
"""

import asyncio
import json
import httpx
from typing import List, Dict, Optional

from .base import AIProvider, ProviderFactory
from src.utils.connection_timeouts import DEFAULT_CONNECT_TIMEOUT_SECONDS
from src.chat.failure_taxonomy import (
    HTTP_STATUS,
    OTHER,
    READ_TIMEOUT,
    ProviderError,
    classify_exception,
)


class OpenAICompatibleProvider(AIProvider):
    """
    OpenAI-compatible AI provider implementation.
    Supports any provider that implements the OpenAI API specification.
    """
    
    DEFAULT_MODEL = "deepseek-flash"
    PROVIDER_NAME = "deepseek"
    
    # Default models for known providers
    DEFAULT_MODELS = {
        "deepseek": "deepseek-flash",
        "openrouter": "openrouter/auto",
    }
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        endpoint: Optional[str] = None,
        provider: Optional[str] = None
    ):
        """
        Initialize the OpenAI-compatible provider.
        
        Args:
            api_key: The API key for the provider
            endpoint: The endpoint URL, resolved from the connection's provider
                row in the database (AIProvider.defaultEndpoint) — there is no
                hard-coded fallback
            provider: The provider name (e.g., 'deepseek', 'openrouter')
        """
        super().__init__(api_key, endpoint)
        self.provider = provider or "deepseek"
        # The endpoint has one home: AIProvider.defaultEndpoint, reached through
        # the connection resolver. A hard-coded map here would be a second
        # source of truth for the same fact, and would drift from the row.
        self.endpoint = endpoint
        self.default_model = self.DEFAULT_MODELS.get(self.provider, self.DEFAULT_MODEL)
    
    async def call(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        tools: Optional[list] = None,
        **kwargs
    ) -> Dict[str, str]:
        """Call the OpenAI-compatible API."""
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY_REQUIRED")
        if not self.endpoint:
            raise ValueError("OPENAI_ENDPOINT_REQUIRED")
        
        # Build the URL
        base_url = self.endpoint.rstrip("/")
        if not base_url.endswith("/chat/completions"):
            url = f"{base_url}/chat/completions"
        else:
            url = base_url
        
        # One home for the "model or default" decision, and it records what it
        # chose — see AIProvider.resolve_model.
        openai_model = self.resolve_model(model)
        
        payload = {
            "model": openai_model,
            "messages": messages,
            "stream": False,
            **kwargs
        }
        if tools:
            payload["tools"] = tools
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        timeout = kwargs.get("timeout", 300.0)
        # THE CONNECT DEADLINE, separate from the read deadline (plan Item 4 of
        # workbench-AI-timeout-policy-plan.html). One number used to bound both
        # phases, so an unreachable endpoint spent the entire call budget on the TCP
        # handshake. Clamped to the total, because a connect deadline longer than the
        # call can never fire and the failure would be misreported as a read timeout.
        _connect_timeout = min(
            float(kwargs.get("connect_timeout", DEFAULT_CONNECT_TIMEOUT_SECONDS)),
            timeout,
        )
        
        async with httpx.AsyncClient() as client:
            try:
                # TOTAL deadline, not a gap between bytes.
                #
                # httpx's `timeout=` bounds connect/read/write/pool PER OPERATION: it fires when
                # no byte arrives for N seconds, not when N seconds have elapsed. Measured
                # 2026-11-01 — a server trickling one byte every 2 s completed in 18.0 s under
                # `timeout=5`. Go's providers attach `context.WithTimeout` to the request, which
                # is a total deadline, so the same setting meant two different things and
                # "maximum AI time" held only on Go (Item 13's C2: 200 after 669 s under a 30 s
                # bound on Python, 402 at 30.0 s on Go).
                #
                # `asyncio.timeout` is the exact equivalent of Go's context deadline, and it is
                # layered OVER the httpx timeouts rather than replacing them: a stalled socket
                # should still fail early, and a call that keeps trickling should still be cut
                # off. This is ported code, so the mechanism mirrors the reference.
                async with asyncio.timeout(timeout):
                    response = await client.post(
                        url, headers=headers, json=payload,
                        timeout=httpx.Timeout(timeout, connect=_connect_timeout),
                    )
                    response.raise_for_status()
                
                try:
                    data = response.json()
                    message = data.get("choices", [{}])[0].get("message", {})
                    content = message.get("content", "")
                    result = {"role": "assistant", "content": content}
                    if message.get("tool_calls"):
                        result["tool_calls"] = message["tool_calls"]
                    return result
                except json.JSONDecodeError:
                    raise ValueError(f"OPENAI_INVALID_JSON:{response.text[:200]}")
                    
            except (httpx.TimeoutException, TimeoutError) as e:
                # TimeoutError is what `asyncio.timeout` raises; it is not an httpx
                # exception, so without it the budget would fall through to the
                # generic branch.
                #
                # The CLASS is decided here, where the type is still available
                # (plan Item 5). classify_exception separates a connect timeout from
                # a read timeout, which the old bare OPENAI_TIMEOUT could not.
                failure_class, status = classify_exception(e)
                if failure_class == OTHER:
                    failure_class = READ_TIMEOUT
                raise ProviderError("OPENAI_TIMEOUT", failure_class, status)
            except httpx.HTTPStatusError as e:
                detail = f"OPENAI_HTTP_ERROR:{e.response.status_code}"
                try:
                    error_body = e.response.text[:500]
                    if error_body:
                        detail += f":{error_body}"
                except:
                    pass
                # The STATUS travels beside the class. This is the path F5 measured
                # wrong: OpenRouter's 400 with "not a valid model ID" was reported as
                # "the model could not be reached" because the number was only ever a
                # substring of an error message.
                raise ProviderError(detail, HTTP_STATUS, e.response.status_code)
            except ProviderError:
                raise
            except Exception as e:
                failure_class, status = classify_exception(e)
                raise ProviderError(f"OPENAI_ERROR:{str(e)}", failure_class, status)
    
    def get_default_model(self) -> str:
        """Get the default model for this provider."""
        return self.default_model
    
    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return self.provider


# Register individual provider aliases with their default endpoints
def register_provider_alias(alias: str, provider_name: str = None):
    """Register a provider alias with its default endpoint."""
    provider_name = provider_name or alias
    
    class ProviderAlias(OpenAICompatibleProvider):
        def __init__(self, api_key: Optional[str] = None, endpoint: Optional[str] = None):
            super().__init__(api_key, endpoint, provider=provider_name)
    
    ProviderAlias.PROVIDER_NAME = alias
    ProviderFactory.register(alias, ProviderAlias)


# Register all known provider aliases
KNOWN_PROVIDERS = [
    "deepseek",
    "openrouter",
]

for provider in KNOWN_PROVIDERS:
    register_provider_alias(provider)