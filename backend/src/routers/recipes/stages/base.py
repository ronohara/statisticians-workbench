"""
Base stage executor interface for recipe stages.
All stage executors must implement the execute() method.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, Optional

from src.utils.translation import t
from ..translations import recipes_stage_not_implemented


class StageExecutor(ABC):
    """
    Abstract base class for recipe stage executors.
    
    Each stage type (data_selection, statistics, visualisation, data_preparation)
    must implement this interface.
    """
    
    def __init__(self, config: Dict[str, Any]):
        """
        Initialize the stage executor with configuration.
        
        Args:
            config: Stage configuration from the recipe
        """
        self.config = config
    
    @abstractmethod
    async def execute(
        self,
        user_id: str,
        user_group: str,
        dataset_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute the stage.

        The data source is passed via kwargs — <code>relation</code>/<code>data_conn</code> for
        relation-based stages, or <code>df</code> for stages still consuming a DataFrame.

        Args:
            user_id: The user executing the recipe
            user_group: The user's group for permission checks
            dataset_id: The dataset ID being analysed
            **kwargs: Additional arguments (db_pool, language, relation, data_conn, df, …)

        Returns:
            Dict containing stage results with at minimum a 'status' field
        """
        pass
    
    @abstractmethod
    def get_stage_type(self) -> str:
        """Return the stage type identifier (e.g., 'data_selection', 'statistics')."""
        pass


class StageResult:
    """Helper class for consistent stage result formatting."""
    
    @staticmethod
    def success(data: Dict[str, Any], message: Optional[str] = None) -> Dict[str, Any]:
        """Return a success result with optional message."""
        result = {"status": "success", **data}
        if message:
            result["message"] = message
        return result
    
    @staticmethod
    def error(error_message: str) -> Dict[str, Any]:
        """Return an error result."""
        return {"status": "error", "error": error_message}
    
    @staticmethod
    async def not_implemented(
        db_pool, language: str, stage_type: str
    ) -> Dict[str, Any]:
        """Return a not-implemented result for placeholder stages.

        Asynchronous because it translates its own message: `stage_type` is
        substituted into the declared fallback, so a new stage executor cannot
        return an untranslated placeholder by accident. Call it as
        `return await StageResult.not_implemented(db_pool, language, "statistics")`.
        """
        return {
            "status": "not_implemented",
            "message": await t(
                db_pool, language, recipes_stage_not_implemented, stage_type=stage_type
            ),
        }