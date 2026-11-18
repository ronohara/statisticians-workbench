"""
Regression and two-way ANOVA — the permissive-library statistics substrate.

Pure-Python simple linear regression, multiple linear regression (normal
equations) and type-II two-way ANOVA with interaction, mirroring
``workbench-go/internal/stats/regression.go`` plus the ANOVA half of
``hypothesis.go``. Built on the Item 2 distribution primitives; no
numpy/scipy/statsmodels.

Parity is verified against scipy 1.18.0 / statsmodels 0.14.6 golden values in
``backend/tests/test_stats_regression.py``.
"""

import math
from dataclasses import dataclass
from typing import List

from .distributions import FSurvival, StudentsTSurvival

# Singularity threshold for the normal-equations solve, relative to the matrix
# scale (mirrors the error gonum's Inverse/SolveVec reports on rank-deficient
# designs).
_SINGULAR_EPS = 1e-12

# scipy.linregress's guard against a zero denominator when r == ±1.
_TINY = 1.0e-20


@dataclass
class LinregressResult:
    slope: float
    intercept: float
    r: float
    p: float
    stderr: float


@dataclass
class OLSResult:
    coefficients: List[float]  # intercept first, then predictors in order
    stderrs: List[float]
    tstats: List[float]
    pvalues: List[float]
    rsquared: float
    adj_rsquared: float
    f: float   # overall F statistic
    fp: float  # overall F p-value


@dataclass
class ANOVAEffect:
    sum_sq: float
    df: float
    f: float
    p: float


# ---------------------------------------------------------------------------
# Small dense linear algebra (no numpy)
# ---------------------------------------------------------------------------

def _dot(u, v):
    return sum(a * b for a, b in zip(u, v))


def _transpose(a):
    return [list(col) for col in zip(*a)]


def _mat_vec(a, v):
    """Matrix-vector product: a is m×p row-major, v is a p-vector."""
    return [_dot(row, v) for row in a]


def _xtx_xty(x, y):
    """Return (X^T X, X^T y) for an n×p row-major design matrix x."""
    n = len(x)
    p = len(x[0])
    xt = _transpose(x)  # p×n
    xtx = [[sum(xt[j][i] * xt[k][i] for i in range(n)) for k in range(p)] for j in range(p)]
    xty = [sum(xt[j][i] * y[i] for i in range(n)) for j in range(p)]
    return xtx, xty


def _solve(a, b):
    """Solve a x = b (a is p×p row-major) by Gaussian elimination with partial
    pivoting. Raises ValueError on a (near-)singular matrix."""
    n = len(a)
    scale = max(abs(v) for row in a for v in row)
    if scale == 0.0:
        raise ValueError("singular design matrix")
    m = [list(row) + [b[i]] for i, row in enumerate(a)]
    for col in range(n):
        piv = max(range(col, n), key=lambda i: abs(m[i][col]))
        if abs(m[piv][col]) < _SINGULAR_EPS * scale:
            raise ValueError("singular design matrix")
        if piv != col:
            m[col], m[piv] = m[piv], m[col]
        pivot = m[col][col]
        for row in range(col + 1, n):
            factor = m[row][col] / pivot
            if factor == 0.0:
                continue
            for k in range(col, n + 1):
                m[row][k] -= factor * m[col][k]
    x = [0.0] * n
    for i in range(n - 1, -1, -1):
        s = m[i][n]
        for j in range(i + 1, n):
            s -= m[i][j] * x[j]
        x[i] = s / m[i][i]
    return x


def _inv_diag(a):
    """Diagonal of the inverse of a symmetric p×p matrix (p solves)."""
    n = len(a)
    diag = []
    for i in range(n):
        e = [0.0] * n
        e[i] = 1.0
        diag.append(_solve(a, e)[i])
    return diag


def _mean(vals):
    return sum(vals) / len(vals)


# ---------------------------------------------------------------------------
# Simple linear regression
# ---------------------------------------------------------------------------

def Linregress(x, y):
    """Simple linear regression of y on x.

    Matches scipy.stats.linregress (two-sided). Returns slope, intercept, the
    Pearson correlation r, the two-sided p-value for the slope, and the
    standard error of the slope. Needs at least three paired observations.
    """
    n = len(x)
    if n < 3 or len(y) != n:
        raise ValueError("linregress requires at least three paired observations")

    xmean = _mean(x)
    ymean = _mean(y)

    ssxm = ssym = ssxym = 0.0
    for i in range(n):
        dx = x[i] - xmean
        dy = y[i] - ymean
        ssxm += dx * dx
        ssym += dy * dy
        ssxym += dx * dy

    r = ssxym / math.sqrt(ssxm * ssym)
    if r > 1.0:
        r = 1.0
    elif r < -1.0:
        r = -1.0

    slope = ssxym / ssxm
    intercept = ymean - slope * xmean

    df = n - 2
    t = r * math.sqrt(df / ((1.0 - r + _TINY) * (1.0 + r + _TINY)))
    p = 2.0 * StudentsTSurvival(df, abs(t))
    stderr = math.sqrt((1.0 - r * r) * ssym / ssxm / df)

    return LinregressResult(slope=slope, intercept=intercept, r=r, p=p, stderr=stderr)


# ---------------------------------------------------------------------------
# Multiple linear regression
# ---------------------------------------------------------------------------

def MultipleRegression(y, predictors):
    """Ordinary least-squares fit of y = intercept + X·beta.

    Matches statsmodels' sm.OLS(y, sm.add_constant(X)).fit(). ``predictors`` is
    a list of predictor columns (each of length n); the intercept is added
    internally. Raises ValueError on too few observations or a singular design.
    """
    n = len(y)
    if n == 0:
        raise ValueError("no observations")
    for col in predictors:
        if len(col) != n:
            raise ValueError("predictor length does not match observations")

    p = len(predictors) + 1
    if n < p:
        raise ValueError("insufficient observations for regression")

    # Design matrix: intercept column first.
    x = [[1.0] + [col[i] for col in predictors] for i in range(n)]

    xtx, xty = _xtx_xty(x, y)
    try:
        beta = _solve(xtx, xty)
    except ValueError:
        raise ValueError("singular design matrix")
    xtx_inv_diag = _inv_diag(xtx)

    fitted = _mat_vec(x, beta)
    rss = sum((y[i] - fitted[i]) ** 2 for i in range(n))

    ymean = _mean(y)
    tss = sum((v - ymean) ** 2 for v in y)

    df_resid = n - p
    mse = rss / df_resid

    coefficients = list(beta)
    stderrs = [math.sqrt(mse * xtx_inv_diag[i]) for i in range(p)]
    tstats = [coefficients[i] / stderrs[i] for i in range(p)]
    pvalues = [2.0 * StudentsTSurvival(df_resid, abs(tstats[i])) for i in range(p)]

    rsquared = 1.0 - rss / tss
    adj_rsquared = 1.0 - (1.0 - rsquared) * (n - 1) / df_resid

    df_model = p - 1
    ess = tss - rss
    f = (ess / df_model) / (rss / df_resid)
    fp = FSurvival(df_model, df_resid, f)

    return OLSResult(
        coefficients=coefficients,
        stderrs=stderrs,
        tstats=tstats,
        pvalues=pvalues,
        rsquared=rsquared,
        adj_rsquared=adj_rsquared,
        f=f,
        fp=fp,
    )


# ---------------------------------------------------------------------------
# Two-way ANOVA (type-II, treatment-coded)
# ---------------------------------------------------------------------------

def _treatment_levels(factor):
    levels = []
    idx = []
    m = {}
    for v in factor:
        if v not in m:
            m[v] = len(levels)
            levels.append(v)
        idx.append(m[v])
    return levels, idx


def _ones_col(n):
    return [1.0] * n


def _dummy_cols(idx, n_levels):
    cols = []
    for level in range(1, n_levels):
        cols.append([1.0 if v == level else 0.0 for v in idx])
    return cols


def _interaction_cols(a, b):
    cols = []
    for ac in a:
        for bc in b:
            cols.append([x * y for x, y in zip(ac, bc)])
    return cols


def _concat_cols(*groups):
    cols = []
    for g in groups:
        cols.extend(g)
    return cols


def _ols_rss(cols, y):
    """Residual sum of squares of the OLS fit of y on the given design columns."""
    n = len(y)
    p = len(cols)
    x = [[cols[j][i] for j in range(p)] for i in range(n)]
    xtx, xty = _xtx_xty(x, y)
    beta = _solve(xtx, xty)
    fitted = _mat_vec(x, beta)
    return sum((y[i] - fitted[i]) ** 2 for i in range(n))


def _anova_effect(ss, df, ms_err, df_err):
    ms = ss / df
    f = ms / ms_err
    return ANOVAEffect(sum_sq=ss, df=float(df), f=f, p=FSurvival(df, df_err, f))


def TwoWayANOVA(y, f1, f2):
    """Type-II two-way ANOVA with interaction for a numeric response y and two
    categorical factors.

    Matches statsmodels' ols("y ~ C(f1) + C(f2) + C(f1):C(f2)").fit() followed
    by anova_lm(typ=2). Returns (factor1, factor2, interaction) as
    :class:`ANOVAEffect`. Raises ValueError when the design is degenerate (a
    factor with fewer than two levels, an empty cell, or insufficient residual
    degrees of freedom).
    """
    n = len(y)
    if n == 0 or len(f1) != n or len(f2) != n:
        raise ValueError("input lengths do not match")

    f1_levels, f1_idx = _treatment_levels(f1)
    f2_levels, f2_idx = _treatment_levels(f2)
    if len(f1_levels) < 2 or len(f2_levels) < 2:
        raise ValueError("each factor requires at least two levels")

    seen = set()
    for i in range(n):
        seen.add((f1_idx[i], f2_idx[i]))
    if len(seen) < len(f1_levels) * len(f2_levels):
        raise ValueError("empty cell in two-way design")

    intercept = _ones_col(n)
    a_cols = _dummy_cols(f1_idx, len(f1_levels))
    b_cols = _dummy_cols(f2_idx, len(f2_levels))
    ab_cols = _interaction_cols(a_cols, b_cols)

    intercept_group = [intercept]
    rss_a = _ols_rss(_concat_cols(intercept_group, a_cols), y)
    rss_b = _ols_rss(_concat_cols(intercept_group, b_cols), y)
    rss_ab = _ols_rss(_concat_cols(intercept_group, a_cols, b_cols), y)
    full_cols = _concat_cols(intercept_group, a_cols, b_cols, ab_cols)
    rss_full = _ols_rss(full_cols, y)

    df_a = len(f1_levels) - 1
    df_b = len(f2_levels) - 1
    df_ab = df_a * df_b
    df_err = n - len(full_cols)
    if df_err <= 0:
        raise ValueError("insufficient residual degrees of freedom")

    # Type-II sums of squares: each term's reduction in RSS when added to a
    # model containing every term of the same or lower order. Clamp numerical
    # noise that nudges a zero SS slightly negative.
    ss_a = max(0.0, rss_b - rss_ab)
    ss_b = max(0.0, rss_a - rss_ab)
    ss_ab = max(0.0, rss_ab - rss_full)
    ms_err = rss_full / df_err

    factor1 = _anova_effect(ss_a, df_a, ms_err, df_err)
    factor2 = _anova_effect(ss_b, df_b, ms_err, df_err)
    interaction = _anova_effect(ss_ab, df_ab, ms_err, df_err)
    return factor1, factor2, interaction
