"""Shared feature-gate helpers for database connection types.

A database connection type maps to a licence feature key; any request against a
connection whose type's feature is not enabled must fail with 403.
"""
from fastapi import HTTPException

from src.licensing import feature_for_db_type, is_feature_enabled
from src.utils.translation import t

from .translations import DATABASE


async def require_db_feature(db_pool, db_type: str, language: str) -> None:
    """Raise 403 if the licence feature for db_type is not enabled."""
    feature = feature_for_db_type(db_type)
    if feature is not None and not is_feature_enabled(feature):
        raise HTTPException(
            status_code=403,
            detail=await t(db_pool, language, DATABASE["database.feature_required"]),
        )
