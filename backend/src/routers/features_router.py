"""
Golden Screwdriver — /api/features endpoint.

Returns the currently enabled features based on the licence file
loaded at startup. No authentication required — the response is
informational; actual enforcement happens server-side on each
gated route.
"""

from fastapi import APIRouter

from src.licensing import get_licence_info

router = APIRouter(prefix="/api", tags=["features"])


@router.get("/features")
async def get_features():
    """Return the list of currently enabled features."""
    return get_licence_info()
