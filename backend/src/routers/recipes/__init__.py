"""
Recipes Router – Statistical Recipe Management and Execution
Part of the 0.0.10 "Statistical Foundation" milestone.
"""

from fastapi import APIRouter

from .crud import router as crud_router, set_db_pool as crud_set_db_pool
from .execute import router as execute_router, set_db_pool as execute_set_db_pool
from .history import router as history_router, set_db_pool as history_set_db_pool
from .transforms import router as transforms_router, set_db_pool as transforms_set_db_pool
from .algorithm_types import router as algorithm_types_router, set_db_pool as algorithm_types_set_db_pool
from .ai_session import router as ai_session_router, set_db_pool as ai_session_set_db_pool

# Create the main router
router = APIRouter(prefix="/api/recipes", tags=["recipes"])

# Include all sub-routers (specific routes before wildcards)
router.include_router(ai_session_router)
router.include_router(algorithm_types_router)
router.include_router(transforms_router)
router.include_router(history_router)
router.include_router(execute_router)
router.include_router(crud_router)

# Global database pool
_db_pool = None


def set_db_pool(pool):
    """Set the database pool for all recipe sub-routers."""
    global _db_pool
    _db_pool = pool
    crud_set_db_pool(pool)
    execute_set_db_pool(pool)
    history_set_db_pool(pool)
    transforms_set_db_pool(pool)
    ai_session_set_db_pool(pool)
    algorithm_types_set_db_pool(pool)


__all__ = ["router", "set_db_pool"]