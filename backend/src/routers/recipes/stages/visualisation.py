"""
Visualisation stage executor.
Generates chart data for various visualisation types via SQL / row-fetch
(no pandas).
"""

from typing import Dict, Any, List, Optional

from .base import StageExecutor, StageResult
from ..relation import relation_source
from src.utils.translation import t
from ..translations import (
    recipes_distribution_no_columns,
    recipes_histogram_no_columns,
    recipes_histogram_numeric,
    recipes_no_columns_exist,
    recipes_no_dataset,
    recipes_scatter_two_columns,
    recipes_scatter_two_numeric,
    recipes_unsupported_chart_type,
    recipes_visualisation_columns_required,
    recipes_visualisation_error,
    recipes_visualisation_generated,
)


class VisualisationExecutor(StageExecutor):
    """
    Visualisation stage executor.
    Generates chart data for bar, pie, line, and scatter charts.
    """

    def get_stage_type(self) -> str:
        return "visualisation"

    async def execute(
        self,
        user_id: str,
        user_group: str,
        dataset_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute visualisation stage.

        Config expects:
            - type: "bar", "pie", "line", "scatter" (default: "bar")
            - columns: List of column names to use (at least 1-2 depending on type)

        The data source is the relation passed via kwargs (a base or temp table).
        """
        language = kwargs.get("language", "en")
        db_pool = kwargs.get("db_pool")
        relation = kwargs.get("relation")
        data_conn = kwargs.get("data_conn")

        try:
            # Normalize frontend config structure to flat backend keys.
            inner = self.config.get("config", {}) if isinstance(self.config.get("config"), dict) else {}
            chart_type = self.config.get("outputType") or self.config.get("type", "bar")

            # Build columns list from frontend's named config fields
            columns = self.config.get("columns", [])
            if not columns:
                algo_cols = []
                for key in ("xColumn", "categoryColumn", "labelColumn"):
                    if inner.get(key):
                        algo_cols.append(inner[key])
                for key in ("yColumn", "valueColumn"):
                    if inner.get(key):
                        algo_cols.append(inner[key])
                columns = list(dict.fromkeys(algo_cols))  # deduplicate, preserve order

            self.config["type"] = chart_type
            self.config["columns"] = columns

            relation_columns = relation.columns if relation else []

            # Table output with no columns specified → use all columns
            if chart_type == "table" and not columns:
                columns = list(relation_columns)
                self.config["columns"] = columns

            if not dataset_id:
                return StageResult.error(await t(db_pool, language, recipes_no_dataset))

            if not columns or len(columns) < 1:
                return StageResult.error(await t(db_pool, language, recipes_visualisation_columns_required))

            available_columns = [col for col in columns if col in relation_columns]
            if not available_columns:
                return StageResult.error(await t(db_pool, language, recipes_no_columns_exist))

            if relation is None:
                return StageResult.error(
                    await t(db_pool, language, recipes_visualisation_error, error="no relation available")
                )

            chart_data, total_rows = await self._chart_data(
                relation, data_conn, available_columns, chart_type, db_pool, language
            )

            if "error" in chart_data:
                return StageResult.error(chart_data["error"])

            return StageResult.success({
                "type": chart_type,
                "columns": available_columns,
                "chart_data": chart_data,
                "total_rows": total_rows,
                "message": await t(db_pool, language, recipes_visualisation_generated)
            })

        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Visualisation stage failed: {e}", exc_info=True)
            return StageResult.error(
                await t(db_pool, language, recipes_visualisation_error, error=str(e))
            )

    async def _chart_data(self, relation, data_conn, columns, chart_type, db_pool, language):
        """Acquire a connection (held data_conn or a fresh one) and compute chart data."""
        source_sql = relation_source(relation)
        release = None
        if data_conn is not None:
            conn = data_conn
        else:
            from src.postgres_data_manager import get_data_pool
            pool = get_data_pool()
            conn = await pool.acquire()
            release = pool
        try:
            from src.postgres_data_manager import (
                get_relation_numeric_columns,
                get_relation_row_count,
            )
            numeric = await get_relation_numeric_columns(conn, source_sql, columns)
            total_rows = await get_relation_row_count(conn, source_sql)
            chart_data = await self._generate_chart_data(
                conn, source_sql, columns, chart_type, numeric, db_pool, language
            )
            return chart_data, total_rows
        finally:
            if release is not None:
                await release.release(conn)

    async def _generate_chart_data(
        self, conn, source_sql, columns, chart_type, numeric, db_pool, language
    ) -> Dict[str, Any]:
        if chart_type == "bar":
            return await self._generate_bar_chart_data(conn, source_sql, columns, numeric)
        elif chart_type == "hbar":
            return await self._generate_hbar_chart_data(conn, source_sql, columns, numeric)
        elif chart_type == "pie":
            return await self._generate_pie_chart_data(conn, source_sql, columns, numeric)
        elif chart_type == "donut":
            return await self._generate_donut_chart_data(conn, source_sql, columns, numeric)
        elif chart_type == "line":
            return await self._generate_line_chart_data(conn, source_sql, columns, numeric)
        elif chart_type == "area":
            return await self._generate_area_chart_data(conn, source_sql, columns, numeric)
        elif chart_type == "table":
            return await self._generate_table_data(conn, source_sql, columns)
        elif chart_type == "scatter":
            return await self._generate_scatter_chart_data(conn, source_sql, columns, numeric, db_pool, language)
        elif chart_type == "histogram":
            return await self._generate_histogram_chart_data(conn, source_sql, columns, numeric, db_pool, language)
        elif chart_type == "distribution":
            return await self._generate_distribution_chart_data(conn, source_sql, columns, numeric, db_pool, language)
        else:
            return {"error": await t(db_pool, language, recipes_unsupported_chart_type, chart_type=chart_type)}

    # ------------------------------------------------------------------ helpers

    async def _grouped_sum(self, conn, source_sql, group_col, value_col):
        """Return (labels, values) for groupby(group_col)[value_col].sum()."""
        from src.postgres_data_manager import get_grouped_sum
        pairs = await get_grouped_sum(conn, source_sql, group_col, value_col)
        return [p[0] for p in pairs], [p[1] for p in pairs]

    async def _value_counts(self, conn, source_sql, col, sort_by_value=False):
        """Return (labels, counts) for value_counts() (optionally sort_index())."""
        from src.postgres_data_manager import get_value_counts
        pairs = await get_value_counts(conn, source_sql, col, sort_by_value=sort_by_value)
        return [p[0] for p in pairs], [p[1] for p in pairs]

    async def _column_values(self, conn, source_sql, col):
        """Return all values of a column as a list (NULLs kept as None)."""
        from src.postgres_data_manager import get_relation_rows
        rows = await get_relation_rows(conn, source_sql, [col])
        return [row[col] for row in rows]

    async def _columns_values(self, conn, source_sql, cols):
        """Return a list of row dicts for the given columns."""
        from src.postgres_data_manager import get_relation_rows
        return await get_relation_rows(conn, source_sql, cols)

    # ------------------------------------------------------------ chart methods

    async def _generate_bar_chart_data(self, conn, source_sql, columns, numeric) -> Dict[str, Any]:
        if len(columns) >= 2:
            x_col = columns[0]
            y_col = columns[1]
            if y_col in numeric:
                x_vals, y_vals = await self._grouped_sum(conn, source_sql, x_col, y_col)
                return {
                    "type": "bar",
                    "x": x_vals,
                    "y": y_vals,
                    "x_label": x_col,
                    "y_label": y_col
                }
            x_vals, y_vals = await self._value_counts(conn, source_sql, x_col)
            return {
                "type": "bar",
                "x": x_vals,
                "y": y_vals,
                "x_label": x_col,
                "y_label": "count"
            }
        x_vals, y_vals = await self._value_counts(conn, source_sql, columns[0])
        return {
            "type": "bar",
            "x": x_vals,
            "y": y_vals,
            "x_label": columns[0],
            "y_label": "count"
        }

    async def _generate_hbar_chart_data(self, conn, source_sql, columns, numeric) -> Dict[str, Any]:
        if len(columns) >= 2:
            x_col = columns[0]
            y_col = columns[1]
            if y_col in numeric:
                x_vals, y_vals = await self._grouped_sum(conn, source_sql, x_col, y_col)
                return {
                    "type": "hbar",
                    "x": y_vals,
                    "y": x_vals,
                    "x_label": y_col,
                    "y_label": x_col,
                    "orientation": "h"
                }
            x_vals, y_vals = await self._value_counts(conn, source_sql, x_col)
            return {
                "type": "hbar",
                "x": y_vals,
                "y": x_vals,
                "x_label": "count",
                "y_label": x_col,
                "orientation": "h"
            }
        x_vals, y_vals = await self._value_counts(conn, source_sql, columns[0])
        return {
            "type": "hbar",
            "x": y_vals,
            "y": x_vals,
            "x_label": "count",
            "y_label": columns[0],
            "orientation": "h"
        }

    async def _generate_pie_chart_data(self, conn, source_sql, columns, numeric) -> Dict[str, Any]:
        if len(columns) >= 2:
            label_col = columns[0]
            value_col = columns[1]
            if value_col in numeric:
                labels, values = await self._grouped_sum(conn, source_sql, label_col, value_col)
                return {"type": "pie", "labels": labels, "values": values}
            labels, values = await self._value_counts(conn, source_sql, label_col)
            return {"type": "pie", "labels": labels, "values": values}
        labels, values = await self._value_counts(conn, source_sql, columns[0])
        return {"type": "pie", "labels": labels, "values": values}

    async def _generate_donut_chart_data(self, conn, source_sql, columns, numeric) -> Dict[str, Any]:
        if len(columns) >= 2:
            label_col = columns[0]
            value_col = columns[1]
            if value_col in numeric:
                labels, values = await self._grouped_sum(conn, source_sql, label_col, value_col)
                return {"type": "donut", "labels": labels, "values": values, "hole": 0.4}
            labels, values = await self._value_counts(conn, source_sql, label_col)
            return {"type": "donut", "labels": labels, "values": values, "hole": 0.4}
        labels, values = await self._value_counts(conn, source_sql, columns[0])
        return {"type": "donut", "labels": labels, "values": values, "hole": 0.4}

    async def _generate_line_chart_data(self, conn, source_sql, columns, numeric) -> Dict[str, Any]:
        if len(columns) >= 2:
            x_col = columns[0]
            y_cols = [c for c in columns[1:] if c in numeric]
            if y_cols:
                rows = await self._columns_values(conn, source_sql, [x_col] + y_cols)
                x_vals = [row[x_col] for row in rows]
                result = {
                    "type": "line",
                    "x": x_vals,
                    "x_label": x_col,
                    "series": []
                }
                for y_col in y_cols:
                    result["series"].append({
                        "name": y_col,
                        "y": [row[y_col] for row in rows]
                    })
                return result
            x_vals, y_vals = await self._value_counts(conn, source_sql, x_col, sort_by_value=True)
            return {
                "type": "line",
                "x": x_vals,
                "y": y_vals,
                "x_label": x_col,
                "y_label": "count"
            }
        x_vals, y_vals = await self._value_counts(conn, source_sql, columns[0], sort_by_value=True)
        return {
            "type": "line",
            "x": x_vals,
            "y": y_vals,
            "x_label": columns[0],
            "y_label": "count"
        }

    async def _generate_area_chart_data(self, conn, source_sql, columns, numeric) -> Dict[str, Any]:
        if len(columns) >= 2:
            x_col = columns[0]
            y_cols = [c for c in columns[1:] if c in numeric]
            if y_cols:
                rows = await self._columns_values(conn, source_sql, [x_col] + y_cols)
                x_vals = [row[x_col] for row in rows]
                result = {
                    "type": "area",
                    "x": x_vals,
                    "x_label": x_col,
                    "series": []
                }
                for y_col in y_cols:
                    result["series"].append({
                        "name": y_col,
                        "y": [row[y_col] for row in rows]
                    })
                return result
            x_vals, y_vals = await self._value_counts(conn, source_sql, x_col, sort_by_value=True)
            return {
                "type": "area",
                "x": x_vals,
                "y": y_vals,
                "x_label": x_col,
                "y_label": "count"
            }
        x_vals, y_vals = await self._value_counts(conn, source_sql, columns[0], sort_by_value=True)
        return {
            "type": "area",
            "x": x_vals,
            "y": y_vals,
            "x_label": columns[0],
            "y_label": "count"
        }

    async def _generate_scatter_chart_data(self, conn, source_sql, columns, numeric, db_pool, language) -> Dict[str, Any]:
        if len(columns) >= 2:
            x_col = columns[0]
            y_col = columns[1]
            if x_col in numeric and y_col in numeric:
                rows = await self._columns_values(conn, source_sql, [x_col, y_col])
                return {
                    "type": "scatter",
                    "x": [row[x_col] for row in rows if row[x_col] is not None and row[y_col] is not None],
                    "y": [row[y_col] for row in rows if row[x_col] is not None and row[y_col] is not None],
                    "x_label": x_col,
                    "y_label": y_col
                }
            return {"error": await t(db_pool, language, recipes_scatter_two_numeric)}
        return {"error": await t(db_pool, language, recipes_scatter_two_columns)}

    async def _generate_histogram_chart_data(self, conn, source_sql, columns, numeric, db_pool, language) -> Dict[str, Any]:
        if columns and columns[0] in numeric:
            values = await self._column_values(conn, source_sql, columns[0])
            return {
                "type": "histogram",
                "x": [v for v in values if v is not None],
                "x_label": columns[0]
            }
        elif columns:
            return {"error": await t(db_pool, language, recipes_histogram_numeric)}
        return {"error": await t(db_pool, language, recipes_histogram_no_columns)}

    async def _generate_distribution_chart_data(self, conn, source_sql, columns, numeric, db_pool, language) -> Dict[str, Any]:
        if len(columns) >= 2:
            x_col = columns[0]
            y_col = columns[1]
            if y_col in numeric:
                rows = await self._columns_values(conn, source_sql, [x_col, y_col])
                return {
                    "type": "distribution",
                    "values": [row[y_col] for row in rows if row[y_col] is not None],
                    "groups": [str(row[x_col]) for row in rows],
                    "value_label": y_col,
                    "group_label": x_col
                }
            rows = await self._columns_values(conn, source_sql, [x_col, y_col])
            return {
                "type": "distribution",
                "values": [row[x_col] for row in rows if row[x_col] is not None],
                "groups": [str(row[y_col]) for row in rows],
                "value_label": x_col,
                "group_label": y_col
            }
        elif columns:
            values = await self._column_values(conn, source_sql, columns[0])
            return {
                "type": "distribution",
                "values": [v for v in values if v is not None],
                "value_label": columns[0]
            }
        return {"error": await t(db_pool, language, recipes_distribution_no_columns)}

    async def _generate_table_data(self, conn, source_sql, columns) -> Dict[str, Any]:
        from src.postgres_data_manager import get_relation_preview, get_relation_row_count
        cols = columns if columns else []
        rows = await get_relation_preview(conn, source_sql, cols, 100)
        total_rows = await get_relation_row_count(conn, source_sql)
        return {
            "type": "table",
            "columns": cols,
            "rows": rows,
            "total_rows": total_rows,
        }
