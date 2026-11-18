"""
Helper functions for recipe operations.
Recipe-stage validation surface only — the data/SQL helpers moved to
routers/datasets/data_access.py and data_fetch.py.
"""
from typing import Dict, Any, List, Optional
import asyncpg

from src.utils.translation import t
from .translations import (
    recipes_invalid_stage_type,
    recipes_no_stages,
    recipes_validation_failed,
)

def validate_recipe_stages(
    stages: List[Dict[str, Any]],
    column_info: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, List[Any]]:
    """Extract the algorithm/output stage configs, build ColumnInfo from
    ``column_info``, and run the pure validator — returning
    ``{"errors": [...], "warnings": [...]}`` without raising. Shared by the
    server-side save/execute gate and the AI ``validate_recipe`` tool."""
    from .constraints import to_column_info, validate_recipe

    cols = to_column_info(column_info) if column_info else None

    algorithm: Optional[Dict[str, Any]] = None
    output: Optional[Dict[str, Any]] = None
    for stage in stages:
        stage_type = stage.get("type")
        config = stage.get("config") or {}
        if stage_type == "statistics":
            algorithm = config
        elif stage_type == "visualisation":
            output = config

    return validate_recipe(None, cols, algorithm, output)




async def collect_recipe_issues(
    stages: List[Dict[str, Any]],
    language: str = "en",
    db_pool: asyncpg.Pool = None,
    column_info: Optional[List[Dict[str, Any]]] = None,
    block_on_warnings: bool = True,
) -> Dict[str, Any]:
    """Validate recipe stages and return the issues without raising.

    The single validation gate: ``validate_stages`` raises on this result, and
    the AI save helper returns it to its caller instead. Shared by the HTTP
    save endpoint and the AI ``save_recipe`` tool.

    Returns:
        ``{"message": str | None, "issues": [...]}`` — ``message`` is the
        translated, displayable text (``None`` when the draft is clean);
        ``issues`` are the structured ``ValidationIssue`` objects behind it,
        empty for the two structural failures, which carry their own
        translated message instead.
    """
    from .constraints import format_recipe_issues

    if stages is None or len(stages) == 0:
        return {
            "message": await t(db_pool, language, recipes_no_stages),
            "issues": [],
        }

    valid_types = ["data_selection", "data_preparation", "statistics", "visualisation"]

    for stage in stages:
        stage_type = stage.get("type")
        if stage_type not in valid_types:
            return {
                "message": await t(
                    db_pool, language, recipes_invalid_stage_type,
                    type=stage_type,
                    types=", ".join(valid_types),
                ),
                "issues": [],
            }

    result = validate_recipe_stages(stages, column_info)
    issues = list(result["errors"])
    if block_on_warnings:
        issues.extend(result["warnings"])

    if issues:
        msg = await format_recipe_issues(issues, db_pool, language)
        return {
            "message": await t(
                db_pool, language, recipes_validation_failed,
                errors=msg,
            ),
            "issues": issues,
        }

    return {"message": None, "issues": []}


async def validate_stages(
    stages: List[Dict[str, Any]],
    language: str = "en",
    db_pool: asyncpg.Pool = None,
    column_info: Optional[List[Dict[str, Any]]] = None,
    block_on_warnings: bool = True,
) -> None:
    """
    Validate recipe stages with translated error messages.

    Performs:
    1. Structural checks (stage types, required stage presence)
    2. Config completeness (algorithm/output required fields)
    3. Algorithm↔output compatibility (constraint matrix)
    4. Column existence and type requirements (when column_info is provided)

    The backend MUST validate independently — the API may be called
    by external clients that bypass frontend guardrails.

    Args:
        stages: List of stage dictionaries
        language: User's language for error messages
        db_pool: Database pool for translation lookups
        column_info: Optional list of column dicts with name, dtype,
            is_numeric, is_categorical keys

    Raises:
        ValueError: If stages are invalid, with a structured multi-line
            message the frontend can display directly.
    """
    result = await collect_recipe_issues(
        stages, language, db_pool, column_info, block_on_warnings
    )
    if result["message"] is not None:
        raise ValueError(result["message"])




def get_stage_executor(stage_type: str, config: Dict[str, Any]) -> Any:
    """
    Get the appropriate stage executor for a given stage type.
    
    Args:
        stage_type: The stage type (data_selection, statistics, visualisation, data_preparation)
        config: The stage configuration
        
    Returns:
        An instance of the appropriate StageExecutor subclass
        
    Raises:
        ValueError: If the stage type is unknown
    """
    from .stages import (
        DataSelectionExecutor,
        StatisticsExecutor,
        VisualisationExecutor,
        DataPreparationExecutor
    )
    
    executors = {
        "data_selection": DataSelectionExecutor,
        "statistics": StatisticsExecutor,
        "visualisation": VisualisationExecutor,
        "data_preparation": DataPreparationExecutor,
    }
    
    executor_class = executors.get(stage_type)
    if executor_class is None:
        raise ValueError(f"Unknown stage type: {stage_type}")
    
    return executor_class(config)
