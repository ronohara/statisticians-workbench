"""
Recipe algorithm types endpoint.
Returns the available statistical algorithm types and their config requirements.
"""

from fastapi import APIRouter, Depends, Request
from typing import Dict
from src.utils.translation import t
from src.routers.datasets.crud import get_current_language
from src.routers.recipes.constraints import (
    ALGORITHM_DEFS,
    FIELD_DEFS,
    OUTPUT_DEFS,
    serialize_recipe_model,
)

router = APIRouter()

_db_pool = None


def set_db_pool(pool):
    global _db_pool
    _db_pool = pool


@router.get("/recipe-algorithms")
async def get_algorithm_types(
    request: Request,
    language: str = Depends(get_current_language),
):
    """Return all available algorithm types with their config and column requirements."""
    algorithms = []
    for alg_key, d in ALGORITHM_DEFS.items():
        field_labels = {}
        for k in d.fields:
            field_labels[k] = await t(_db_pool, language, FIELD_DEFS[k].label)
        algorithms.append({
            "value": alg_key,
            "configFields": d.fields,
            "fieldLabels": field_labels,
            "minCategorical": d.min_categorical,
            "minNumeric": d.min_numeric,
            "needsCategorical": d.min_categorical > 0,
            "needsNumeric": d.min_numeric > 0,
            "description": await t(_db_pool, language, d.description),
        })
    return {"algorithms": algorithms}


@router.get("/recipe-model")
async def get_recipe_model(request: Request):
    """Return the canonical recipe constraint model: fields, algorithms, outputs.

    Labels and descriptions are returned as ``{key, fallback}`` pairs (never
    pre-translated strings) so the caller resolves them in its own language via
    the standard three tiers (DB → en → fallback).
    """
    return serialize_recipe_model()
