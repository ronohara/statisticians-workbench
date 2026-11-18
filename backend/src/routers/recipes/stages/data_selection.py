"""
Data Selection stage executor.
Handles column selection and filtering of datasets.
"""

from typing import Dict, Any

from .base import StageExecutor, StageResult
from ..relation import relation_source
from src.utils.translation import t
from ..translations import (
    recipes_data_selection_error,
    recipes_no_columns_exist,
    recipes_no_dataset,
)


class DataSelectionExecutor(StageExecutor):
    """
    Data Selection stage executor.
    Filters the dataset to selected columns and returns preview data.
    """
    
    def get_stage_type(self) -> str:
        return "data_selection"
    
    async def execute(
        self,
        user_id: str,
        user_group: str,
        dataset_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute data selection stage.
        
        Config expects:
            - columns: List of column names to select (optional)
            
        Returns:
            - status: "success" or "error"
            - dataset_id: The dataset ID
            - columns: List of selected columns
            - row_count: Number of rows in the dataset
            - data: Preview data (first 10 rows)
            - total_rows: Total number of rows
            - full_data_available: Always True
        """
        # Get language from kwargs
        language = kwargs.get("language", "en")
        db_pool = kwargs.get("db_pool")
        relation = kwargs.get("relation")
        data_conn = kwargs.get("data_conn")
        
        try:
            columns = self.config.get("columns", [])
            
            if not dataset_id:
                return StageResult.error(
                    await t(db_pool, language, recipes_no_dataset
                    )
                )
            
            # Available columns come from the relation.
            all_columns = relation.columns if relation else []
            
            # If columns are specified, filter to those that exist
            if columns:
                # Columns may be dicts (from frontend RecipeColumn) or plain strings
                column_names = [
                    col["name"] if isinstance(col, dict) else str(col)
                    for col in columns
                ]
                available_columns = [col for col in column_names if col in all_columns]
                if not available_columns:
                    return StageResult.error(
                        await t(db_pool, language, recipes_no_columns_exist
                        )
                    )
            else:
                available_columns = list(all_columns)
            
            if relation is None:
                return StageResult.error(
                    await t(db_pool, language, recipes_data_selection_error, error="no relation available")
                )

            # Relation-passing: query the relation's table (base or temp). The
            # held data_conn sees a session TEMP table; otherwise the base table
            # is read via the pool-backed helpers.
            source_sql = relation_source(relation)
            if data_conn is not None:
                from src.postgres_data_manager import (
                    get_relation_preview,
                    get_relation_row_count,
                )
                preview_rows = await get_relation_preview(
                    data_conn, source_sql, available_columns, 10
                )
                row_count = await get_relation_row_count(data_conn, source_sql)
            else:
                from src.postgres_data_manager import (
                    get_table_preview_columns,
                    get_table_row_count,
                )
                preview_rows = await get_table_preview_columns(
                    relation.table_name, available_columns, 10
                )
                row_count = await get_table_row_count(relation.table_name)
            data_preview = {
                col: {i: row[col] for i, row in enumerate(preview_rows)}
                for col in available_columns
            }
            
            return StageResult.success({
                "dataset_id": dataset_id,
                "columns": available_columns,
                "row_count": row_count,
                "data": data_preview,
                "total_rows": row_count,
                "full_data_available": True
            })
            
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Data selection stage failed: {e}", exc_info=True)
            return StageResult.error(
                await t(db_pool, language, recipes_data_selection_error, error=str(e))
            )