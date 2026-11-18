"""
Recipe Assistant Agent — AI-powered statistical analysis and recipe generation.
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


AVAILABLE_TECHNIQUES = [
    ("descriptive", "Descriptive Statistics", "Summary measures (mean, median, std, quartiles)"),
    ("correlation", "Correlation Matrix", "Relationships between numeric variables (Pearson, Spearman, Kendall)"),
    ("t_test_independent", "Independent t-test", "Compare means of two independent groups"),
    ("t_test_paired", "Paired t-test", "Compare means of two paired measurements"),
    ("anova_one_way", "One-way ANOVA", "Compare means across 3+ groups"),
    ("anova_two_way", "Two-way ANOVA", "Compare means across two factors with interaction"),
    ("linear_regression", "Linear Regression", "Model relationship between variables (simple or multiple)"),
    ("chi_square", "Chi-square Test", "Test association between two categorical variables"),
]


class RecipeAssistantAgent(AIAgent):
    """
    AI agent that helps users choose statistical techniques, configure recipes,
    and interpret analysis results — all in the context of their specific dataset.
    """

    async def build_system_prompt(
        self,
        columns: Optional[List[str]] = None,
        rows: Optional[List[Dict[str, Any]]] = None,
        **context
    ) -> str:
        """
        Build a system prompt with dataset schema, available techniques,
        and guidance on recipe configuration.
        """
        technique_list = "\n".join(
            f"  - {name}: {desc}" for _, name, desc in AVAILABLE_TECHNIQUES
        )

        prompt = (
            "You are a statistical analysis assistant for Statisticians Workbench. "
            "Your job is to help the user design analysis recipes for their data. "
            "You understand the following techniques:\n\n"
            + technique_list
            + "\n\nYou help the user with:\n"
            "  - Choosing the right technique for their research question\n"
            "  - Identifying which columns to use as dependent/independent/grouping variables\n"
            "  - Understanding what each technique reveals about their data\n"
            "  - Interpreting statistical results (p-values, effect sizes, R², etc.)\n"
            "  - Suggesting appropriate visualisations\n\n"
            "Recipe configuration: the user builds recipes with 2-3 stages:\n"
            "  1. Data Selection — choose columns to analyse (first column is the primary measure)\n"
            "  2. Statistics — pick a technique and configure grouping/factors if needed\n"
            "  3. Visualisation — optional chart (bar, pie, line, scatter)\n\n"
            "When the user asks about a specific technique, explain concisely: what it does, "
            "what columns they need, how to interpret the output. "
            "Always reference the user's actual column names when possible."
        )

        if columns is None or rows is None:
            return prompt

        # Build schema summary (same pattern as DatasetCleanerAgent)
        schema_lines = []
        for col in columns:
            col_values = [r.get(col) for r in rows]
            present = [v for v in col_values if not _is_missing(v)]
            null_count = len(col_values) - len(present)
            unique_count = len({repr(v) for v in present})
            is_numeric = bool(present) and all(_is_numeric(v) for v in present)
            is_categorical = not is_numeric and unique_count <= min(50, len(rows) // 2)
            sample_values = present[:3]

            tags = []
            if is_numeric:
                tags.append("numeric")
            if is_categorical:
                tags.append("categorical")
            if bool(present) and all(_is_datetime(v) for v in present):
                tags.append("datetime")

            schema_lines.append(
                f"  - {col}: {_dtype_label(present)}"
                f" (nulls={null_count}, unique={unique_count}"
                f"{', ' + ', '.join(tags) if tags else ''}"
                f", samples={sample_values})"
            )

        sample_df = _table_string(columns, rows[:5])

        return (
            prompt
            + "\n\n---\nUSER'S DATASET:\n"
            + f"Dataset has {len(rows)} rows and {len(columns)} columns.\n\n"
            + "COLUMN SCHEMA:\n"
            + "\n".join(schema_lines)
            + "\n\nSAMPLE DATA (first 5 rows):\n"
            + sample_df
        )


# Auto-register
AgentFactory.register("recipe_assistant", RecipeAssistantAgent)
