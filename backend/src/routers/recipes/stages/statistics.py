"""
Statistics stage executor.
Computes descriptive statistics on selected columns.

Reads the relation table (base or prepared TEMP table) via SQL row-fetch and
PostgreSQL aggregates — no pandas. The Group 2 permissive layer does the math
for the inferential techniques.
"""

from typing import Dict, Any, Optional
import math

from .base import StageExecutor, StageResult
from ..relation import relation_source
from ..stats import ChiSquaredContingency, FOneway, Linregress, MultipleRegression, TTestIndPooled, TTestRel, TwoWayANOVA
from src.postgres_data_manager import (
    get_data_pool,
    get_relation_numeric_columns,
    get_relation_row_count,
    get_relation_rows,
)
from src.utils.translation import t
from ..translations import (
    recipes_columns_required,
    recipes_no_columns_exist,
    recipes_no_dataset,
    statistics_anova_computation_failed,
    statistics_anova_needs_three_groups,
    statistics_column_must_be_numeric,
    statistics_computation_failed,
    statistics_each_group_two_observations,
    statistics_factor_column_not_found,
    statistics_group_column_required_anova,
    statistics_group_column_required_ttest,
    statistics_group_fewer_than_two,
    statistics_group_must_have_two_levels,
    statistics_need_five_observations_chi,
    statistics_need_observations_regression,
    statistics_need_ten_observations_anova,
    statistics_need_three_pairs,
    statistics_need_two_categories_chi,
    statistics_need_two_numeric_correlation,
    statistics_need_two_valid_numeric,
    statistics_no_valid_data_after_dropna,
    statistics_no_valid_numeric,
    statistics_non_numeric_column,
    statistics_select_dependent_independent,
    statistics_select_dependent_var,
    statistics_select_one_numeric_ttest,
    statistics_select_two_categorical_chi,
    statistics_select_two_numeric_paired,
    statistics_two_factors_required,
)


def _quote_ident(identifier: str) -> str:
    """Quote a table/column identifier for safe SQL interpolation."""
    return '"' + identifier.replace('"', '""') + '"'


def _num(value) -> Optional[float]:
    """Coerce a numeric SQL result to float, preserving NULL as None."""
    return float(value) if value is not None else None


def _mean(values) -> float:
    """Arithmetic mean of a non-empty iterable of numbers."""
    return sum(values) / len(values) if values else 0.0


def _sample_variance(values) -> float:
    """Sample variance (ddof=1) of an iterable of numbers."""
    n = len(values)
    if n < 2:
        return 0.0
    mean = sum(values) / n
    return sum((v - mean) ** 2 for v in values) / (n - 1)


def _std(values) -> float:
    """Sample standard deviation (ddof=1) of an iterable of numbers."""
    return math.sqrt(_sample_variance(values))


def _descriptive_aggregate_sql(source_sql: str, column: str, where: Optional[str] = None) -> str:
    """One-column descriptive aggregate query over a relation source.

    ``source_sql`` is the already-quoted FROM fragment (``relation_source``);
    ``where`` is an optional pre-built WHERE predicate (no leading keyword).
    """
    qc = _quote_ident(column)
    where_sql = f" WHERE {where}" if where else ""
    return (
        f"SELECT "
        f"COUNT(*) AS count, "
        f"COUNT({qc}) AS non_null, "
        f"AVG({qc}) AS mean, "
        f"PERCENTILE_CONT(0.5) WITHIN GROUP (ORDER BY {qc}) AS median, "
        f"mode() WITHIN GROUP (ORDER BY {qc}) AS mode, "
        f"VAR_SAMP({qc}) AS variance, "
        f"STDDEV_SAMP({qc}) AS std_dev, "
        f"MIN({qc}) AS min, "
        f"MAX({qc}) AS max, "
        f"MAX({qc}) - MIN({qc}) AS range, "
        f"PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {qc}) AS q1, "
        f"PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {qc}) AS q3, "
        f"PERCENTILE_CONT(0.75) WITHIN GROUP (ORDER BY {qc}) - PERCENTILE_CONT(0.25) WITHIN GROUP (ORDER BY {qc}) AS iqr, "
        f"SUM({qc}) AS sum "
        f"FROM {source_sql}{where_sql}"
    )


def _sort_key(value):
    """Deterministic sort key for categorical values (numbers numeric, else lexicographic)."""
    if isinstance(value, bool):
        return (0, int(value), "")
    if isinstance(value, (int, float)):
        return (1, value, "")
    return (2, 0, str(value))


def _crosstab(pairs):
    """Build a sorted contingency table from (col1, col2) pairs.

    Returns ``(table, row_labels, col_labels)`` where ``table`` is a 2-D list of
    counts and the labels are the sorted unique values of each column. Mirrors
    ``pd.crosstab`` for homogeneous categorical columns.
    """
    row_labels = sorted({a for a, _ in pairs}, key=_sort_key)
    col_labels = sorted({b for _, b in pairs}, key=_sort_key)
    row_idx = {v: i for i, v in enumerate(row_labels)}
    col_idx = {v: i for i, v in enumerate(col_labels)}
    table = [[0] * len(col_labels) for _ in row_labels]
    for a, b in pairs:
        table[row_idx[a]][col_idx[b]] += 1
    return table, row_labels, col_labels


class StatisticsExecutor(StageExecutor):
    """
    Statistics stage executor.
    Computes descriptive statistics or correlation matrices.
    """

    def get_stage_type(self) -> str:
        return "statistics"

    async def execute(
        self,
        user_id: str,
        user_group: str,
        dataset_id: str,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Execute statistics stage.

        Config expects:
            - technique: "descriptive" or "correlation" (default: "descriptive")
            - columns: List of column names to analyse
            - group_by: Optional column to group by (for descriptive stats)

        The data source is the relation passed via kwargs (a base or temp table).
        """
        language = kwargs.get("language", "en")
        db_pool = kwargs.get("db_pool")
        relation = kwargs.get("relation")
        data_conn = kwargs.get("data_conn")

        try:
            # Normalize frontend config structure to flat backend keys.
            # Frontend sends: { algorithmType, config: { factorColumn, responseColumn, ... } }
            # Backend expects: { technique, group_column, columns, ... }
            inner = self.config.get("config", {}) if isinstance(self.config.get("config"), dict) else {}
            technique = self.config.get("algorithmType") or self.config.get("technique", "descriptive")

            # Build flat config dict for downstream methods to read from
            _flat = dict(self.config)
            _flat["technique"] = technique
            _flat["group_by"] = inner.get("groupBy") or self.config.get("group_by")
            _flat["group_column"] = inner.get("factorColumn") or self.config.get("group_column")
            _flat["factor_1"] = inner.get("factorColumn") or self.config.get("factor_1")
            _flat["factor_2"] = inner.get("factorColumn2") or self.config.get("factor_2")

            # Build columns list from algorithm-specific config fields
            columns = self.config.get("columns", [])
            if not columns and inner.get("columns"):
                columns = list(inner["columns"])
            if not columns:
                algo_cols = []
                if inner.get("responseColumn"):
                    algo_cols.append(inner["responseColumn"])
                if inner.get("responseColumn2"):
                    algo_cols.append(inner["responseColumn2"])
                if inner.get("dependentColumn"):
                    algo_cols.append(inner["dependentColumn"])
                if inner.get("independentColumns"):
                    algo_cols.extend(inner["independentColumns"])
                if inner.get("factorColumn"):
                    algo_cols.append(inner["factorColumn"])
                if inner.get("categoryColumn"):
                    algo_cols.append(inner["categoryColumn"])
                columns = list(dict.fromkeys(algo_cols))  # deduplicate, preserve order

            # Also patch self.config so downstream reads work
            for k, v in _flat.items():
                self.config[k] = v
            self.config["columns"] = columns

            group_by = self.config.get("group_by")

            if not dataset_id:
                return StageResult.error(
                    await t(db_pool, language, recipes_no_dataset
                    )
                )

            if not columns:
                return StageResult.error(
                    await t(db_pool, language, recipes_columns_required
                    )
                )

            if relation is None:
                return StageResult.error(
                    await t(db_pool, language, statistics_computation_failed, error="no relation available")
                )

            # Filter to columns that exist in the relation
            all_columns = relation.columns or []
            available_columns = [col for col in columns if col in all_columns]
            if not available_columns:
                return StageResult.error(
                    await t(db_pool, language, recipes_no_columns_exist
                    )
                )

            source_sql = relation_source(relation)

            # Hold the caller's data_conn when present (session TEMP table is
            # visible there); otherwise acquire a fresh pool connection for a
            # base table.
            release = None
            if data_conn is not None:
                conn = data_conn
            else:
                pool = get_data_pool()
                if pool is None:
                    return StageResult.error(
                        await t(db_pool, language, statistics_computation_failed, error="data pool not initialised")
                    )
                conn = await pool.acquire()
                release = pool

            try:
                total_rows = await get_relation_row_count(conn, source_sql)

                if technique == "correlation":
                    result = await self._compute_correlation(conn, source_sql, available_columns, db_pool=db_pool, language=language)
                elif technique == "t_test_independent":
                    result = await self._compute_t_test_independent(conn, source_sql, available_columns, self.config.get("group_column"), all_columns, db_pool=db_pool, language=language)
                elif technique == "t_test_paired":
                    result = await self._compute_t_test_paired(conn, source_sql, available_columns, db_pool=db_pool, language=language)
                elif technique == "anova_one_way":
                    result = await self._compute_anova_one_way(conn, source_sql, available_columns, self.config.get("group_column"), all_columns, db_pool=db_pool, language=language)
                elif technique == "anova_two_way":
                    result = await self._compute_anova_two_way(conn, source_sql, available_columns, self.config.get("factor_1"), self.config.get("factor_2"), all_columns, db_pool=db_pool, language=language)
                elif technique == "linear_regression":
                    result = await self._compute_linear_regression(conn, source_sql, available_columns, db_pool=db_pool, language=language)
                elif technique == "chi_square":
                    result = await self._compute_chi_square(conn, source_sql, available_columns, db_pool=db_pool, language=language)
                else:
                    result = await self._compute_descriptive_stats(conn, source_sql, available_columns, group_by, all_columns, db_pool=db_pool, language=language)

                if "error" not in result:
                    result["status"] = "success"
                result["total_rows"] = total_rows
                return result
            finally:
                if release is not None:
                    await release.release(conn)

        except Exception as e:
            return StageResult.error(await t(db_pool, language, statistics_computation_failed, error=str(e)))

    # ------------------------------------------------------------------ helpers

    async def _distinct(self, conn, source_sql, column):
        """Distinct non-null values of a column, ascending order (mirrors dropna().unique())."""
        qc = _quote_ident(column)
        rows = await conn.fetch(f"SELECT DISTINCT {qc} AS v FROM {source_sql} WHERE {qc} IS NOT NULL ORDER BY v")
        return [row["v"] for row in rows]

    async def _column_descriptive(self, conn, source_sql, column, where_col=None, where_val=None, db_pool=None, language="en"):
        """Run the descriptive aggregate for one column and shape the result dict."""
        where = None
        args = []
        if where_col is not None:
            where = f"{_quote_ident(where_col)} = $1"
            args = [where_val]
        row = await conn.fetchrow(_descriptive_aggregate_sql(source_sql, column, where), *args)
        count = int(row["count"]) if row["count"] is not None else 0
        non_null = int(row["non_null"]) if row["non_null"] is not None else 0
        missing = count - non_null
        if non_null == 0:
            return {
                "error": await t(db_pool, language, statistics_no_valid_data_after_dropna),
                "count": count,
                "missing": missing,
            }
        mode_val = row["mode"]
        return {
            "count": count,
            "missing": missing,
            "dtype": "numeric",
            "mean": _num(row["mean"]),
            "median": _num(row["median"]),
            "mode": [mode_val] if mode_val is not None else [],
            "variance": _num(row["variance"]),
            "std_dev": _num(row["std_dev"]),
            "min": _num(row["min"]),
            "max": _num(row["max"]),
            "range": _num(row["range"]),
            "q1": _num(row["q1"]),
            "q3": _num(row["q3"]),
            "iqr": _num(row["iqr"]),
            "sum": _num(row["sum"]),
        }

    async def _compute_descriptive_stats(
        self,
        conn,
        source_sql,
        columns,
        group_by: Optional[str] = None,
        all_columns: Optional[list] = None,
        db_pool=None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """
        Compute descriptive statistics for selected columns, reading the
        relation table directly (no pandas).
        """
        result = {}
        numeric = await get_relation_numeric_columns(conn, source_sql, columns)

        # Validate columns exist and are numeric
        for col in columns:
            if col not in numeric:
                result[col] = {
                    "error": await t(db_pool, language, statistics_non_numeric_column),
                    "dtype": "categorical"
                }

        valid_columns = [col for col in columns if col in numeric]
        if not valid_columns:
            return {
                "error": await t(db_pool, language, statistics_no_valid_numeric),
                "result": result
            }

        dtype_map = {col: "numeric" for col in valid_columns}

        # Group by mode
        if group_by and (all_columns is None or group_by in all_columns):
            group_vals = await self._distinct(conn, source_sql, group_by)
            group_results = {}

            for group_val in group_vals:
                group_stats = {}
                for col in valid_columns:
                    group_stats[col] = await self._column_descriptive(
                        conn, source_sql, col, where_col=group_by, where_val=group_val,
                        db_pool=db_pool, language=language
                    )
                group_results[str(group_val)] = group_stats

            return {
                "grouped_by": group_by,
                "groups": [str(g) for g in group_vals],
                "statistics": group_results,
                "dtype_map": dtype_map
            }
        else:
            stats = {}
            for col in valid_columns:
                stats[col] = await self._column_descriptive(
                    conn, source_sql, col, db_pool=db_pool, language=language
                )
            return {
                "statistics": stats,
                "dtype_map": dtype_map
            }

    async def _compute_correlation(self, conn, source_sql, columns, db_pool=None, language: str = "en") -> Dict[str, Any]:
        """Compute a correlation matrix via pairwise PostgreSQL CORR() against the relation."""
        numeric = await get_relation_numeric_columns(conn, source_sql, columns)
        numeric_cols = [col for col in columns if col in numeric]

        if len(numeric_cols) < 2:
            return {
                "error": await t(db_pool, language, statistics_need_two_numeric_correlation),
                "result": {}
            }

        matrix = {c: {} for c in numeric_cols}
        for i, c1 in enumerate(numeric_cols):
            for c2 in numeric_cols[i:]:
                sql = f"SELECT CORR({_quote_ident(c1)}, {_quote_ident(c2)}) FROM {source_sql}"
                val = await conn.fetchval(sql)
                corr = _num(val)
                matrix[c1][c2] = corr
                matrix[c2][c1] = corr

        return {
            "correlation_matrix": matrix,
            "columns": numeric_cols,
            "dtype_map": {col: "numeric" for col in numeric_cols}
        }

    async def _compute_t_test_independent(
        self,
        conn,
        source_sql,
        columns,
        group_column: Optional[str] = None,
        all_columns: Optional[list] = None,
        db_pool=None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Compute independent samples t-test between two groups."""
        if not group_column or (all_columns is not None and group_column not in all_columns):
            return {
                "technique": "t_test_independent",
                "error": await t(db_pool, language, statistics_group_column_required_ttest)
            }

        if len(columns) < 1:
            return {
                "technique": "t_test_independent",
                "error": await t(db_pool, language, statistics_select_one_numeric_ttest)
            }

        numeric_col = columns[0]
        numeric = await get_relation_numeric_columns(conn, source_sql, [numeric_col])
        if numeric_col not in numeric:
            return {"technique": "t_test_independent", "error": await t(db_pool, language, statistics_column_must_be_numeric, col=numeric_col)}

        # Get group values
        groups = await self._distinct(conn, source_sql, group_column)
        if len(groups) != 2:
            return {
                "technique": "t_test_independent",
                "error": await t(db_pool, language, statistics_group_must_have_two_levels, group=group_column, n=len(groups)),
                "groups_found": [str(g) for g in groups]
            }

        rows = await get_relation_rows(conn, source_sql, [numeric_col, group_column])
        g1_data = [_num(r[numeric_col]) for r in rows if r[group_column] == groups[0] and r[numeric_col] is not None]
        g2_data = [_num(r[numeric_col]) for r in rows if r[group_column] == groups[1] and r[numeric_col] is not None]

        if len(g1_data) < 2 or len(g2_data) < 2:
            return {"technique": "t_test_independent", "error": await t(db_pool, language, statistics_each_group_two_observations)}

        t_stat, p_value, _ = TTestIndPooled(g1_data, g2_data)
        dof = len(g1_data) + len(g2_data) - 2

        # Cohen's d
        pooled_std = math.sqrt(
            ((len(g1_data) - 1) * _sample_variance(g1_data) + (len(g2_data) - 1) * _sample_variance(g2_data)) / dof
        )
        cohens_d = abs(_mean(g1_data) - _mean(g2_data)) / pooled_std if pooled_std > 0 else 0

        significant = p_value < 0.05
        g1_label, g2_label = str(groups[0]), str(groups[1])

        return {
            "technique": "t_test_independent",
            "column": numeric_col,
            "group_column": group_column,
            "groups": [g1_label, g2_label],
            g1_label: {
                "mean": _mean(g1_data),
                "std": _std(g1_data),
                "n": len(g1_data)
            },
            g2_label: {
                "mean": _mean(g2_data),
                "std": _std(g2_data),
                "n": len(g2_data)
            },
            "t_statistic": round(float(t_stat), 4),
            "p_value": round(float(p_value), 4),
            "degrees_of_freedom": dof,
            "cohens_d": round(cohens_d, 4),
            "significant": significant,
            "interpretation": (
                f"Significant difference between groups (p = {p_value:.4f})"
                if significant
                else f"No significant difference (p = {p_value:.4f})"
            )
        }

    async def _compute_t_test_paired(
        self,
        conn,
        source_sql,
        columns,
        db_pool=None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Compute paired samples t-test between two related measurements."""
        numeric = await get_relation_numeric_columns(conn, source_sql, columns)
        numeric_cols = [c for c in columns if c in numeric]

        if len(numeric_cols) < 2:
            return {
                "technique": "t_test_paired",
                "error": await t(db_pool, language, statistics_select_two_numeric_paired)
            }

        col1, col2 = numeric_cols[0], numeric_cols[1]
        rows = await get_relation_rows(conn, source_sql, [col1, col2])
        paired = [(r[col1], r[col2]) for r in rows if r[col1] is not None and r[col2] is not None]

        if len(paired) < 3:
            return {"technique": "t_test_paired", "error": await t(db_pool, language, statistics_need_three_pairs)}

        x = [_num(a) for a, _ in paired]
        y = [_num(b) for _, b in paired]
        t_stat, p_value, _ = TTestRel(x, y)
        dof = len(paired) - 1
        differences = [a - b for a, b in zip(x, y)]
        mean_diff = _mean(differences)
        std_diff = _std(differences)
        cohens_d = abs(mean_diff) / std_diff if std_diff > 0 else 0
        significant = p_value < 0.05

        return {
            "technique": "t_test_paired",
            "column_1": col1,
            "column_2": col2,
            "n_pairs": len(paired),
            "mean_1": _mean(x),
            "mean_2": _mean(y),
            "mean_difference": round(mean_diff, 4),
            "std_difference": round(std_diff, 4),
            "t_statistic": round(float(t_stat), 4),
            "p_value": round(float(p_value), 4),
            "degrees_of_freedom": dof,
            "cohens_d": round(cohens_d, 4),
            "significant": significant,
            "interpretation": (
                f"Significant difference between paired measurements (p = {p_value:.4f})"
                if significant
                else f"No significant difference (p = {p_value:.4f})"
            )
        }

    async def _compute_anova_one_way(
        self,
        conn,
        source_sql,
        columns,
        group_column: Optional[str] = None,
        all_columns: Optional[list] = None,
        db_pool=None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Compute one-way ANOVA comparing means across 3+ groups."""
        if not group_column or (all_columns is not None and group_column not in all_columns):
            return {
                "technique": "anova_one_way",
                "error": await t(db_pool, language, statistics_group_column_required_anova)
            }

        if len(columns) < 1:
            return {"technique": "anova_one_way", "error": await t(db_pool, language, statistics_select_dependent_var)}

        numeric_col = columns[0]
        numeric = await get_relation_numeric_columns(conn, source_sql, [numeric_col])
        if numeric_col not in numeric:
            return {"technique": "anova_one_way", "error": await t(db_pool, language, statistics_column_must_be_numeric, col=numeric_col)}

        group_values = await self._distinct(conn, source_sql, group_column)

        if len(group_values) < 3:
            return {
                "technique": "anova_one_way",
                "error": await t(db_pool, language, statistics_anova_needs_three_groups, n=len(group_values)),
                "groups_found": [str(g) for g in group_values]
            }

        rows = await get_relation_rows(conn, source_sql, [numeric_col, group_column])
        groups_data = {}
        for g in group_values:
            g_data = [_num(r[numeric_col]) for r in rows if r[group_column] == g and r[numeric_col] is not None]
            if len(g_data) < 2:
                return {
                    "technique": "anova_one_way",
                    "error": await t(db_pool, language, statistics_group_fewer_than_two, group=str(g))
                }
            groups_data[str(g)] = g_data

        f_stat, p_value = FOneway(*[groups_data[str(g)] for g in group_values])
        significant = p_value < 0.05

        return {
            "technique": "anova_one_way",
            "column": numeric_col,
            "group_column": group_column,
            "n_groups": len(group_values),
            "groups": {
                str(g): {
                    "mean": round(_mean(groups_data[str(g)]), 4),
                    "std": round(_std(groups_data[str(g)]), 4),
                    "n": len(groups_data[str(g)])
                }
                for g in group_values
            },
            "f_statistic": round(float(f_stat), 4),
            "p_value": round(float(p_value), 4),
            "significant": significant,
            "interpretation": (
                f"Significant difference between groups (F = {f_stat:.2f}, p = {p_value:.4f})"
                if significant
                else f"No significant difference between groups (F = {f_stat:.2f}, p = {p_value:.4f})"
            )
        }

    async def _compute_anova_two_way(
        self,
        conn,
        source_sql,
        columns,
        factor_1: Optional[str] = None,
        factor_2: Optional[str] = None,
        all_columns: Optional[list] = None,
        db_pool=None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Compute two-way ANOVA with interaction."""
        if not factor_1 or not factor_2:
            return {
                "technique": "anova_two_way",
                "error": await t(db_pool, language, statistics_two_factors_required)
            }
        if all_columns is not None and factor_1 not in all_columns:
            return {"technique": "anova_two_way", "error": await t(db_pool, language, statistics_factor_column_not_found, factor="1", col=factor_1)}
        if all_columns is not None and factor_2 not in all_columns:
            return {"technique": "anova_two_way", "error": await t(db_pool, language, statistics_factor_column_not_found, factor="2", col=factor_2)}

        if len(columns) < 1:
            return {"technique": "anova_two_way", "error": await t(db_pool, language, statistics_select_dependent_var)}

        numeric_col = columns[0]
        numeric = await get_relation_numeric_columns(conn, source_sql, [numeric_col])
        if numeric_col not in numeric:
            return {"technique": "anova_two_way", "error": await t(db_pool, language, statistics_column_must_be_numeric, col=numeric_col)}

        rows = await get_relation_rows(conn, source_sql, [numeric_col, factor_1, factor_2])
        y = []
        f1 = []
        f2 = []
        for r in rows:
            if r[numeric_col] is not None and r[factor_1] is not None and r[factor_2] is not None:
                y.append(_num(r[numeric_col]))
                f1.append(str(r[factor_1]))
                f2.append(str(r[factor_2]))

        if len(y) < 10:
            return {"technique": "anova_two_way", "error": await t(db_pool, language, statistics_need_ten_observations_anova)}

        try:
            factor1, factor2, interaction = TwoWayANOVA(y, f1, f2)

            def effect_dict(effect) -> dict:
                return {
                    "f_statistic": round(float(effect.f), 4),
                    "p_value": round(float(effect.p), 4),
                    "df": int(effect.df),
                    "sum_sq": round(float(effect.sum_sq), 4),
                }

            f1_result = effect_dict(factor1)
            f2_result = effect_dict(factor2)
            interaction_result = effect_dict(interaction)

            return {
                "technique": "anova_two_way",
                "column": numeric_col,
                "factor_1_name": factor_1,
                "factor_2_name": factor_2,
                "n_observations": len(y),
                "factor_1": {**f1_result, "significant": (f1_result.get("p_value") or 1) < 0.05},
                "factor_2": {**f2_result, "significant": (f2_result.get("p_value") or 1) < 0.05},
                "interaction": {**interaction_result, "significant": (interaction_result.get("p_value") or 1) < 0.05},
            }
        except Exception as e:
            return {
                "technique": "anova_two_way",
                "error": await t(db_pool, language, statistics_anova_computation_failed, error=str(e))
            }

    async def _compute_linear_regression(
        self,
        conn,
        source_sql,
        columns,
        db_pool=None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Compute simple or multiple linear regression.
        columns[0] = dependent variable (y), columns[1:] = independent (x)."""
        if len(columns) < 2:
            return {
                "technique": "linear_regression",
                "error": await t(db_pool, language, statistics_select_dependent_independent)
            }

        numeric = await get_relation_numeric_columns(conn, source_sql, columns)
        numeric_cols = [c for c in columns if c in numeric]
        if len(numeric_cols) < 2:
            return {"technique": "linear_regression", "error": await t(db_pool, language, statistics_need_two_valid_numeric)}

        dep = numeric_cols[0]
        indep = numeric_cols[1:]
        rows = await get_relation_rows(conn, source_sql, [dep] + indep)
        clean = [r for r in rows if all(r[c] is not None for c in [dep] + indep)]

        if len(clean) < max(3, len(indep) + 2):
            return {"technique": "linear_regression", "error": await t(db_pool, language, statistics_need_observations_regression, n=max(3, len(indep)+2))}

        y = [_num(r[dep]) for r in clean]
        X = {col: [_num(r[col]) for r in clean] for col in indep}

        result = {
            "technique": "linear_regression",
            "n": len(clean),
            "dependent": dep,
            "independent": indep,
        }

        # Simple regression (2 columns)
        if len(indep) == 1:
            linres = Linregress(X[indep[0]], y)
            slope, intercept, r_value, p_value, std_err = (
                linres.slope, linres.intercept, linres.r, linres.p, linres.stderr
            )
            result.update({
                "r_squared": round(float(r_value ** 2), 4),
                "r": round(float(r_value), 4),
                "slope": round(float(slope), 4),
                "intercept": round(float(intercept), 4),
                "p_value": round(float(p_value), 4),
                "std_err": round(float(std_err), 4),
                "significant": p_value < 0.05,
                "coefficients": [{
                    "name": indep[0],
                    "coefficient": round(float(slope), 4),
                    "p_value": round(float(p_value), 4),
                    "std_err": round(float(std_err), 4),
                }],
                "interpretation": (
                    f"R² = {r_value**2:.3f}, {'significant' if p_value < 0.05 else 'not significant'} "
                    f"(p = {p_value:.4f})"
                )
            })
        else:
            # Multiple regression via the permissive layer
            model = MultipleRegression(y, [X[col] for col in indep])

            names = ["Intercept"] + indep
            coefs = [
                {
                    "name": name,
                    "coefficient": round(float(model.coefficients[i]), 4),
                    "p_value": round(float(model.pvalues[i]), 4),
                    "std_err": round(float(model.stderrs[i]), 4),
                }
                for i, name in enumerate(names)
            ]

            result.update({
                "r_squared": round(float(model.rsquared), 4),
                "adjusted_r_squared": round(float(model.adj_rsquared), 4),
                "f_statistic": round(float(model.f), 4),
                "f_p_value": round(float(model.fp), 4),
                "coefficients": coefs,
                "significant": model.fp < 0.05,
                "interpretation": (
                    f"R² = {model.rsquared:.3f} (adj = {model.adj_rsquared:.3f}), "
                    f"F = {model.f:.2f}, p = {model.fp:.4f}"
                ),
            })

        return result

    async def _compute_chi_square(
        self,
        conn,
        source_sql,
        columns,
        db_pool=None,
        language: str = "en"
    ) -> Dict[str, Any]:
        """Compute chi-square test of independence between two categorical columns."""
        if len(columns) < 2:
            return {"technique": "chi_square", "error": await t(db_pool, language, statistics_select_two_categorical_chi)}

        col1, col2 = columns[0], columns[1]
        rows = await get_relation_rows(conn, source_sql, [col1, col2])
        pairs = [(r[col1], r[col2]) for r in rows if r[col1] is not None and r[col2] is not None]

        if len(pairs) < 5:
            return {"technique": "chi_square", "error": await t(db_pool, language, statistics_need_five_observations_chi)}

        table, row_labels, col_labels = _crosstab(pairs)

        if len(row_labels) < 2 or len(col_labels) < 2:
            return {"technique": "chi_square", "error": await t(db_pool, language, statistics_need_two_categories_chi)}

        chi2, p_value, dof = ChiSquaredContingency(table)
        dof = int(dof)
        n = len(pairs)
        cramers_v = math.sqrt(chi2 / (n * min(len(row_labels) - 1, len(col_labels) - 1))) if n > 0 else 0
        significant = p_value < 0.05

        return {
            "technique": "chi_square",
            "n": int(n),
            "column_1": col1,
            "column_2": col2,
            "contingency_table": table,
            "row_labels": [str(r) for r in row_labels],
            "col_labels": [str(c) for c in col_labels],
            "chi2": round(float(chi2), 4),
            "p_value": round(float(p_value), 4),
            "degrees_of_freedom": dof,
            "cramers_v": round(float(cramers_v), 4),
            "significant": significant,
            "interpretation": (
                f"{'Significant' if significant else 'No significant'} association "
                f"(χ² = {chi2:.2f}, p = {p_value:.4f}, V = {cramers_v:.3f})"
            ),
        }
