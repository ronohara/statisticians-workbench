"""
Ollama AI provider implementation.
Supports both local and remote Ollama instances.
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


class OllamaProvider(AIProvider):
    """Ollama AI provider implementation."""
    
    DEFAULT_MODEL = "llama3.2"
    PROVIDER_NAME = "ollama-local"
    
    def __init__(self, api_key: Optional[str] = None, endpoint: Optional[str] = None):
        """Initialize the Ollama provider."""
        super().__init__(api_key, endpoint)
        # The endpoint has one home: AIProvider.defaultEndpoint, reached through
        # the connection resolver. A hard-coded endpoint here would be a second
        # source of truth for the same fact, and would drift from the row.
        self.endpoint = endpoint
    
    async def call(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        tools: Optional[list] = None,
        **kwargs
    ) -> Dict[str, str]:
        """Call the Ollama API."""
        if not self.endpoint:
            raise ValueError("OLLAMA_ENDPOINT_REQUIRED")
        url = f"{self.endpoint.rstrip('/')}/api/chat"
        ollama_model = self.resolve_model(model)
        
        # Ollama names these under `options`; translate the OpenAI-style tuning
        # parameters the shared ToolAgent layer passes (temperature, max_tokens)
        # so a local model honours the same temperature / max-tokens the
        # concierge asks for, rather than dropping them.
        options = {}
        temperature = kwargs.pop("temperature", None)
        max_tokens = kwargs.pop("max_tokens", None)
        if temperature is not None:
            options["temperature"] = temperature
        if max_tokens is not None:
            options["num_predict"] = max_tokens
        
        payload = {
            "model": ollama_model,
            "messages": messages,
            "stream": False,
            **kwargs
        }
        if options:
            payload["options"] = options
        if tools:
            payload["tools"] = tools
        
        timeout = kwargs.get("timeout", 300.0)
        # THE CONNECT DEADLINE, separate from the read deadline (plan Item 4 of
        # workbench-AI-timeout-policy-plan.html).
        #
        # One number used to bound both phases, which meant an unreachable host spent
        # the whole 300 s on the TCP handshake before anything was even asked — and on
        # a silent drop the kernel's SYN backoff decided instead, about 127 s here.
        # The two are different failures: nothing answering is a fault, knowable in
        # seconds; a model still thinking is patience, and only that needs minutes.
        #
        # Clamped to the total budget. A connect deadline longer than the call can
        # never fire — asyncio.timeout wins first — and the failure would then be
        # reported as a read timeout rather than a connect timeout, which is the
        # misclassification this split exists to remove.
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
                        url, json=payload,
                        timeout=httpx.Timeout(timeout, connect=_connect_timeout),
                    )
                    response.raise_for_status()
                
                try:
                    data = response.json()
                    message = data.get("message", {})
                    content = message.get("content", "")
                    result = {"role": "assistant", "content": content}
                    if message.get("tool_calls"):
                        result["tool_calls"] = message["tool_calls"]
                    return result
                except json.JSONDecodeError:
                    raise ValueError(f"OLLAMA_INVALID_JSON:{response.text[:200]}")
                    
            except (httpx.TimeoutException, TimeoutError) as e:
                # TimeoutError is what `asyncio.timeout` raises; it is not an
                # httpx exception, so without it the budget above would fall
                # through to the generic branch.
                #
                # The CLASS is decided here, where the exception type is still
                # available (plan Item 5). `classify_exception` separates a connect
                # timeout from a read timeout, which the old bare
                # `OLLAMA_TIMEOUT` could not — and that distinction is the whole
                # point of the connect/read split.
                failure_class, status = classify_exception(e)
                if failure_class == OTHER:
                    # A bare asyncio TimeoutError says nothing about its phase.
                    failure_class = READ_TIMEOUT
                raise ProviderError("OLLAMA_TIMEOUT", failure_class, status)
            except httpx.HTTPStatusError as e:
                detail = f"OLLAMA_HTTP_ERROR:{e.response.status_code}"
                try:
                    error_body = e.response.text[:500]
                    if error_body:
                        detail += f":{error_body}"
                except:
                    pass
                # The STATUS travels beside the class, because 402, 404 and 429 are
                # different problems with different owners and the caller has to tell
                # them apart. The old code put the number in a string for a regex to
                # find, which is how OpenRouter's 400 became "could not be reached".
                raise ProviderError(detail, HTTP_STATUS, e.response.status_code)
            except ProviderError:
                # The JSON branch above raises this; let it through unchanged rather
                # than re-wrapping it as a generic error.
                raise
            except Exception as e:
                failure_class, status = classify_exception(e)
                raise ProviderError(f"OLLAMA_ERROR:{str(e)}", failure_class, status)
    
    def get_default_model(self) -> str:
        """Get the default model for Ollama."""
        return self.DEFAULT_MODEL
    
    @property
    def provider_name(self) -> str:
        """Get the provider name."""
        return self.PROVIDER_NAME


class OllamaRemoteProvider(OllamaProvider):
    """Ollama Remote provider (requires API key)."""
    
    PROVIDER_NAME = "ollama-remote"
    
    async def call(
        self,
        messages: List[Dict[str, str]],
        model: Optional[str] = None,
        tools: Optional[list] = None,
        **kwargs
    ) -> Dict[str, str]:
        """Call the Ollama Remote API (OpenAI-compatible)."""
        if not self.api_key:
            raise ValueError("OLLAMA_REMOTE_API_KEY_REQUIRED")
        if not self.endpoint:
            raise ValueError("OLLAMA_REMOTE_ENDPOINT_REQUIRED")
        
        url = f"{self.endpoint.rstrip('/')}/chat/completions"
        ollama_model = self.resolve_model(model)
        
        payload = {
            "model": ollama_model,
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
        # workbench-AI-timeout-policy-plan.html).
        #
        # One number used to bound both phases, which meant an unreachable host spent
        # the whole 300 s on the TCP handshake before anything was even asked — and on
        # a silent drop the kernel's SYN backoff decided instead, about 127 s here.
        # The two are different failures: nothing answering is a fault, knowable in
        # seconds; a model still thinking is patience, and only that needs minutes.
        #
        # Clamped to the total budget. A connect deadline longer than the call can
        # never fire — asyncio.timeout wins first — and the failure would then be
        # reported as a read timeout rather than a connect timeout, which is the
        # misclassification this split exists to remove.
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
                    raise ValueError(f"OLLAMA_REMOTE_INVALID_JSON:{response.text[:200]}")
                    
            except (httpx.TimeoutException, TimeoutError) as e:
                failure_class, status = classify_exception(e)
                if failure_class == OTHER:
                    failure_class = READ_TIMEOUT
                raise ProviderError("OLLAMA_REMOTE_TIMEOUT", failure_class, status)
            except httpx.HTTPStatusError as e:
                detail = f"OLLAMA_REMOTE_HTTP_ERROR:{e.response.status_code}"
                try:
                    error_body = e.response.text[:500]
                    if error_body:
                        detail += f":{error_body}"
                except:
                    pass
                raise ProviderError(detail, HTTP_STATUS, e.response.status_code)
            except ProviderError:
                raise
            except Exception as e:
                failure_class, status = classify_exception(e)
                raise ProviderError(f"OLLAMA_REMOTE_ERROR:{str(e)}", failure_class, status)


# Register providers
ProviderFactory.register("ollama-local", OllamaProvider)
ProviderFactory.register("ollama-remote", OllamaRemoteProvider)