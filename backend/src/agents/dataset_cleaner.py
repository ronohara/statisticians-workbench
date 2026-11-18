"""
Dataset Cleaner Agent — AI-powered dataset cleaning and preparation.
"""

import math
from datetime import datetime, date
from decimal import Decimal
from typing import Optional, List, Dict, Any

from .base import AIAgent, AgentFactory


def _is_missing(v):
    return v is None or (isinstance(v, float) and (math.isnan(v) or math.isinf(v)))


def _is_numeric(v):
    return isinstance(v, (int, float, Decimal)) and not isinstance(v, bool)


def _is_datetime(v):
    return isinstance(v, (datetime, date))


def _dtype_label(values):
    if not values:
        return "unknown"
    if all(isinstance(v, bool) for v in values):
        return "boolean"
    if all(isinstance(v, int) and not isinstance(v, bool) for v in values):
        return "integer"
    if all(_is_numeric(v) for v in values):
        return "number"
    if all(_is_datetime(v) for v in values):
        return "datetime"
    return "string"


def _table_string(columns, rows):
    if not rows:
        return "(no rows)"
    lines = ["\t".join(str(c) for c in columns)]
    for r in rows:
        lines.append("\t".join("" if _is_missing(r.get(c)) else str(r.get(c)) for c in columns))
    return "\n".join(lines)


class DatasetCleanerAgent(AIAgent):
    """
    AI agent for dataset cleaning and preparation.
    Analyses dataset schema and sample data, answers questions about
    cleaning operations, and suggests preparation rules.
    """

    async def build_system_prompt(
        self,
        columns: Optional[List[str]] = None,
        rows: Optional[List[Dict[str, Any]]] = None,
        **context
    ) -> str:
        """
        Build a system prompt with dataset schema and sample data context.

        Args:
            columns: The column names in order.
            rows: The rows as a list of plain dicts.
        """
        if columns is None or rows is None:
            return (
                "You are a dataset cleaning and preparation assistant for Statisticians Workbench. "
                "Help the user understand and clean their data. "
                "When suggesting cleaning operations, mention specific column names and operation types."
            )

        # Build schema summary
        schema_lines = []
        for col in columns:
            col_values = [r.get(col) for r in rows]
            present = [v for v in col_values if not _is_missing(v)]
            null_count = len(col_values) - len(present)
            unique_count = len({repr(v) for v in present})
            is_numeric = bool(present) and all(_is_numeric(v) for v in present)
            sample_values = present[:3]
            schema_lines.append(
                f"  - {col}: {_dtype_label(present)}"
                f" (nulls={null_count}, unique={unique_count}"
                f"{', numeric' if is_numeric else ''}"
                f", samples={sample_values})"
            )

        sample_df = _table_string(columns, rows[:5])

        return (
            "You are a dataset cleaning and preparation assistant for Statisticians Workbench. "
            "Help the user understand and clean their dataset. You can suggest operations like:\n"
            "  - filter rows by condition\n"
            "  - fill missing values (mean, median, mode, constant, or drop)\n"
            "  - convert column types (numeric, datetime, string, boolean)\n"
            "  - normalize or standardize numeric columns\n"
            "  - encode categorical columns (one-hot or label)\n"
            "  - drop or rename columns\n"
            "  - detect outliers and anomalies\n\n"
            f"Dataset has {len(rows)} rows and {len(columns)} columns.\n\n"
            "COLUMN SCHEMA:\n"
            + "\n".join(schema_lines)
            + "\n\nSAMPLE DATA (first 5 rows):\n"
            + sample_df
            + "\n\nAnswer questions about this dataset concisely. "
            "When suggesting cleaning operations, mention the specific column names and operation types "
            "the user can apply in the Data Preparation Rules editor."
        )


# Auto-register
AgentFactory.register("dataset_cleaner", DatasetCleanerAgent)
