"""
Data Preparation stage executor for recipe execution.
Applies one or more preparation rules to the dataset in order.
"""

from typing import Dict, Any, List, Optional
import asyncpg

from .base import StageExecutor, StageResult
from ..relation import relation_source
from src.utils.translation import t
from ..translations import (
    recipes_preparation_all_rules_failed,
    recipes_preparation_no_db_pool,
    recipes_preparation_rule_failed,
    recipes_preparation_rule_not_found,
    recipes_preparation_rules_applied,
)


class DataPreparationExecutor(StageExecutor):
    """
    Applies preparation rules to a dataset during recipe execution.
    
    Config format:
    {
        "rule_ids": ["uuid1", "uuid2", ...],
        "description": "Clean and prepare data"
    }
    
    Rules are applied in the order specified by rule_ids.
    Each rule's operations are applied to the DataFrame in sequence.
    """
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.rule_ids: List[str] = config.get("rule_ids", [])
    
    async def execute(
        self,
        user_id: str,
        user_group: str,
        dataset_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Report on the preparation rules for a recipe.

        The data transformation is applied upstream by the inline Phase 5.5 SQL
        path (which materializes a TEMP table — Item 20); this stage no longer
        re-applies the rules, it only reports them.

        Args:
            user_id: The user executing the recipe
            user_group: The user's group for permission checks
            dataset_id: The dataset ID being analysed
            **kwargs: 'db_pool', 'language', 'relation' (prepared table), 'data_conn' (held data-pool connection)

        Returns:
            StageResult with rule/row/column metadata
        """
        db_pool: Optional[asyncpg.Pool] = kwargs.get("db_pool")
        language: str = kwargs.get("language", "en")
        relation = kwargs.get("relation")
        data_conn = kwargs.get("data_conn")

        if not self.rule_ids:
            return StageResult.success({
                "rules_applied": 0,
                "rows_before": 0,
                "rows_after": 0,
                "columns_before": 0,
                "columns_after": 0,
            })

        if db_pool is None:
            return StageResult.error(await t(db_pool, language, recipes_preparation_no_db_pool))

        rules_applied = []
        errors = []

        for rule_id in self.rule_ids:
            try:
                async with db_pool.acquire() as conn:
                    row = await conn.fetchrow(
                        'SELECT name FROM "DataPreparationRule" WHERE id = $1 AND "datasetId" = $2',
                        rule_id, dataset_id
                    )

                if row is None:
                    errors.append(await t(db_pool, language, recipes_preparation_rule_not_found, rule_id=rule_id))
                    continue

                rules_applied.append({
                    "rule_id": rule_id,
                    "rule_name": row["name"],
                })

            except Exception as e:
                errors.append(await t(db_pool, language, recipes_preparation_rule_failed, rule_id=rule_id, error=str(e)))

        # Prepared-side counts come from the relation (TEMP table); base-side
        # counts come from the dataset's base table. No re-application here.
        rows_after = 0
        columns_after = 0
        if relation is not None:
            columns_after = len(relation.columns)
            if data_conn is not None:
                rows_after = await data_conn.fetchval(
                    f"SELECT COUNT(*) FROM {relation_source(relation)}"
                )

        rows_before = 0
        columns_before = 0
        # The dataset must be one the caller can *see* — the row count below reads the
        # dataset's own table, so an invisible dataset must read as missing (Gap C).
        async with db_pool.acquire() as conn:
            ds_row = await conn.fetchrow(
                """
                SELECT "tableName", "storageType", "dataSnapshot"
                FROM "UserDataset"
                WHERE id = $1 AND ("userId" = $2 OR ("isShared" = true AND "datasetGroup" IN (
                    SELECT "userGroup" FROM "User" WHERE id = $2
                )))
                """,
                dataset_id, user_id
            )
        if ds_row and ds_row["storageType"] == "postgresql" and ds_row["tableName"]:
            from src.postgres_data_manager import get_table_row_count
            rows_before = await get_table_row_count(ds_row["tableName"])
            snapshot = ds_row["dataSnapshot"] or {}
            columns_before = len(snapshot.get("columns", []) if isinstance(snapshot, dict) else [])

        result_data = {
            "rules_applied": len(rules_applied),
            "rules_detail": rules_applied,
            "rows_before": rows_before,
            "rows_after": rows_after,
            "columns_before": columns_before,
            "columns_after": columns_after,
        }

        if errors:
            result_data["errors"] = errors
            if len(rules_applied) == 0:
                result_data["status"] = "error"
                result_data["error"] = await t(db_pool, language, recipes_preparation_all_rules_failed, errors="; ".join(errors))
                return result_data

        return StageResult.success(result_data, await t(db_pool, language, recipes_preparation_rules_applied, count=len(rules_applied)))
    
    def get_stage_type(self) -> str:
        return "data_preparation"
