"""
Shared validation for dataset operations (preparation rules and transform rules).

Both preparation.py and transforms.py used identical validation logic with
separate translation-key dictionaries. This module consolidates the constants
and the validate_operations() function so there is a single source of truth.

The error keys are flat and shared — declared once in common/translations.py,
referenced directly here via t().
"""

from typing import List, Any
from src.utils.translation import t
from src.routers.common.translations import (
    invalid_operation_type,
    column_required,
    filter_operator_required,
    filter_value_required,
    invalid_fill_method,
    invalid_target_type,
    invalid_encoding,
    encode_column_required,
    columns_required,
    rename_new_name_required,
)


# ============================================================
# CONSTANTS
# ============================================================

VALID_OPERATION_TYPES = [
    "filter",
    "fill_missing",
    "convert_type",
    "normalize",
    "standardize",
    "encode",
    "drop_duplicates",
    "drop_columns",
    "rename_column",
]

FILL_MISSING_METHODS = ["mean", "median", "mode", "constant", "drop"]
ENCODING_TYPES = ["one_hot", "label"]
TARGET_TYPES = ["numeric", "datetime", "string", "boolean"]


# ============================================================
# VALIDATION
# ============================================================

async def validate_operations(
    operations: List[Any],
    language: str,
    db_pool,
) -> None:
    """
    Validate a list of operation objects with translated error messages.

    Parameters:
        operations:    list of objects each having .type, .column, .columns,
                       .operator, .value, .method, .target_type, .new_name,
                       .encoding attributes (PreparationOperation or
                       TransformOperation).
        language:      ISO language code for error messages.
        db_pool:       asyncpg connection pool (needed by the t() helper).

    Raises:
        ValueError: With a translated error message.
    """
    for op in operations:
        # --- operation type ---
        if op.type not in VALID_OPERATION_TYPES:
            raise ValueError(
                await t(
                    db_pool, language, invalid_operation_type,
                    type=op.type,
                    types=", ".join(VALID_OPERATION_TYPES),
                )
            )

        # --- column required ---
        if op.type in ("filter", "fill_missing", "convert_type", "rename_column"):
            if not op.column:
                raise ValueError(
                    await t(db_pool, language, column_required, type=op.type)
                )

        # --- filter ---
        if op.type == "filter":
            if not op.operator:
                raise ValueError(
                    await t(db_pool, language, filter_operator_required)
                )
            if op.value is None and op.operator not in ("is_null", "is_not_null"):
                raise ValueError(
                    await t(db_pool, language, filter_value_required)
                )

        # --- fill_missing ---
        if op.type == "fill_missing":
            if op.method and op.method not in FILL_MISSING_METHODS:
                raise ValueError(
                    await t(
                        db_pool, language, invalid_fill_method,
                        method=op.method,
                        methods=", ".join(FILL_MISSING_METHODS),
                    )
                )

        # --- convert_type ---
        if op.type == "convert_type":
            if op.target_type and op.target_type not in TARGET_TYPES:
                raise ValueError(
                    await t(
                        db_pool, language, invalid_target_type,
                        target_type=op.target_type,
                        types=", ".join(TARGET_TYPES),
                    )
                )

        # --- encode ---
        if op.type == "encode":
            if op.encoding and op.encoding not in ENCODING_TYPES:
                raise ValueError(
                    await t(
                        db_pool, language, invalid_encoding,
                        encoding=op.encoding,
                        types=", ".join(ENCODING_TYPES),
                    )
                )
            if not op.column:
                raise ValueError(
                    await t(db_pool, language, encode_column_required)
                )

        # --- normalize / standardize / drop_columns ---
        if op.type in ("normalize", "standardize", "drop_columns"):
            if not op.columns:
                raise ValueError(
                    await t(db_pool, language, columns_required, type=op.type)
                )

        # --- rename_column ---
        if op.type == "rename_column":
            if not op.new_name:
                raise ValueError(
                    await t(db_pool, language, rename_new_name_required)
                )
