"""
Datasets Router – Upload, Define, and Manage Datasets
Part of the 0.0.10 "Statistical Foundation" milestone.
"""

from fastapi import APIRouter
from .crud import router as crud_router, set_db_pool as crud_set_db_pool
from .upload import router as upload_router, set_db_pool as upload_set_db_pool
from .define import router as raw_define_router, set_db_pool as define_set_db_pool
from .schema import router as schema_router, set_db_pool as schema_set_db_pool
from .describe import router as describe_router, set_db_pool as describe_set_db_pool
from .preparation import router as preparation_router, set_db_pool as preparation_set_db_pool
from .clean_chat import router as clean_chat_router, set_db_pool as clean_chat_set_db_pool
from .recipe_chat import router as recipe_chat_router, set_db_pool as recipe_chat_set_db_pool
from .virtual import router as virtual_router, set_db_pool as virtual_set_db_pool
from .virtual_chat import router as virtual_chat_router, set_db_pool as virtual_chat_set_db_pool
from .join_suggestions import router as join_suggestions_router
from .dataclean_chat import router as dataclean_chat_router, set_db_pool as dataclean_chat_set_db_pool
from .auto_create import router as auto_create_router, set_db_pool as auto_create_set_db_pool
from .transforms import router as transforms_router, set_db_pool as transforms_set_db_pool

# Create the main router
router = APIRouter(prefix="/api/datasets", tags=["datasets"])

# Include all sub-routers
router.include_router(crud_router)
router.include_router(upload_router)
router.include_router(raw_define_router)
router.include_router(schema_router)
router.include_router(describe_router)
router.include_router(preparation_router)
router.include_router(clean_chat_router)
router.include_router(recipe_chat_router)
router.include_router(virtual_router)
router.include_router(virtual_chat_router)
# The join suggester has no pool: it computes over the columns the caller sends
# and reads nothing, so it is included without a set_db_pool.
router.include_router(join_suggestions_router)
router.include_router(dataclean_chat_router)
router.include_router(auto_create_router)
router.include_router(transforms_router)

# Global database pool
_db_pool = None

def set_db_pool(pool):
    global _db_pool
    _db_pool = pool
    # Set it for all sub-routers
    crud_set_db_pool(pool)
    upload_set_db_pool(pool)
    define_set_db_pool(pool)
    schema_set_db_pool(pool)
    describe_set_db_pool(pool)
    preparation_set_db_pool(pool)
    clean_chat_set_db_pool(pool)
    recipe_chat_set_db_pool(pool)
    virtual_set_db_pool(pool)
    virtual_chat_set_db_pool(pool)
    dataclean_chat_set_db_pool(pool)
    auto_create_set_db_pool(pool)
    transforms_set_db_pool(pool)

__all__ = ["router", "set_db_pool"]