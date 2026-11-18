"""
Request trace logging middleware.
Logs detailed request context for every failing (4xx/5xx) response.
No configuration, no env vars, always active.
"""

import logging
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("uvicorn.trace")


async def trace_middleware(request: Request, call_next):
    response: Response = await call_next(request)
    
    if response.status_code >= 400:
        auth = request.headers.get("authorization", "")
        token_suffix = f"...{auth[-8:]}" if len(auth) > 12 else (auth or "<none>")
        
        logger.warning(
            "[TRACE] %s %s %s | Auth: %s",
            response.status_code,
            request.method,
            request.url.path,
            token_suffix,
        )
    
    return response
