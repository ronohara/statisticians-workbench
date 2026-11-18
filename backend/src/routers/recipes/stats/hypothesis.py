"""
Hypothesis tests — the permissive-library statistics substrate.

Pure-Python t-tests (independent pooled + Welch, paired), one-way ANOVA, and
the chi-squared test of independence with Cramér's V, mirroring
``workbench-go/internal/stats/hypothesis.go``. Built on the Item 2
distribution primitives (``distributions.py``); no scipy/statsmodels.

Parity is verified against scipy 1.18.0 golden values in
``backend/tests/test_stats_hypothesis.py``.
"""

import math

from .distributions import ChiSquaredSurvival, FSurvival, StudentsTSurvival


def _mean(vals):
    return sum(vals) / len(vals)


def _variance(vals):
    """Sample variance (ddof=1), two-pass."""
    n = len(vals)
    m = _mean(vals)
    return sum((x - m) * (x - m) for x in vals) / (n - 1)


def TTestIndPooled(x, y):
    """Two-sample independent t-test assuming equal variances (Student's t).

    Matches scipy.stats.ttest_ind with equal_var=True. Returns the t
    statistic, the two-sided p-value and the degrees of freedom (n1 + n2 - 2).
    Each sample needs at least two observations, else all three are NaN.
    """
    n1 = len(x)
    n2 = len(y)
    if n1 < 2 or n2 < 2:
        return math.nan, math.nan, math.nan
    v1 = _variance(x)
    v2 = _variance(y)
    df = n1 + n2 - 2
    svar = ((n1 - 1) * v1 + (n2 - 1) * v2) / df
    denom = math.sqrt(svar * (1.0 / n1 + 1.0 / n2))
    t = (_mean(x) - _mean(y)) / denom
    p = 2.0 * StudentsTSurvival(df, abs(t))
    return t, p, float(df)


def TTestIndWelch(x, y):
    """Welch's two-sample independent t-test (unequal variances).

    Matches scipy.stats.ttest_ind with equal_var=False. Returns the t
    statistic, the two-sided p-value and the Welch-Satterthwaite degrees of
    freedom. Each sample needs at least two observations, else all NaN.
    """
    n1 = len(x)
    n2 = len(y)
    if n1 < 2 or n2 < 2:
        return math.nan, math.nan, math.nan
    v1 = _variance(x)
    v2 = _variance(y)
    vn1 = v1 / n1
    vn2 = v2 / n2
    denom = math.sqrt(vn1 + vn2)
    df = (vn1 + vn2) * (vn1 + vn2) / (vn1 * vn1 / (n1 - 1) + vn2 * vn2 / (n2 - 1))
    t = (_mean(x) - _mean(y)) / denom
    p = 2.0 * StudentsTSurvival(df, abs(t))
    return t, p, df


def TTestRel(x, y):
    """Paired (dependent) t-test on the differences x[i] - y[i].

    Matches scipy.stats.ttest_rel. Returns the t statistic, the two-sided
    p-value and the degrees of freedom (n - 1). At least two pairs are
    required, else all three are NaN.
    """
    n = len(x)
    if n < 2:
        return math.nan, math.nan, math.nan
    d = [x[i] - y[i] for i in range(n)]
    df = n - 1
    dm = _mean(d)
    v = _variance(d)
    denom = math.sqrt(v / n)
    t = dm / denom
    p = 2.0 * StudentsTSurvival(df, abs(t))
    return t, p, float(df)


def FOneway(*groups):
    """One-way ANOVA F-test for equal group means.

    Matches scipy.stats.f_oneway. Returns the F statistic and its p-value from
    the F distribution with (k-1, N-k) degrees of freedom. Needs at least two
    non-empty groups and at least one group of size > 1, else both are NaN.
    """
    k = len(groups)
    if k < 2:
        return math.nan, math.nan

    total = 0
    all_single = True
    for g in groups:
        n = len(g)
        if n == 0:
            return math.nan, math.nan
        total += n
        if n != 1:
            all_single = False
    if all_single:
        return math.nan, math.nan

    # Grand mean; centering removes the location so the sum-of-squares stays
    # accurate (scipy's approach).
    offset = sum(v for g in groups for v in g) / total

    centered_sum = 0.0
    sstot = 0.0
    for g in groups:
        for v in g:
            c = v - offset
            sstot += c * c
            centered_sum += c
    normalized_ss = centered_sum * centered_sum / total
    sstot -= normalized_ss

    ssbn = 0.0
    for g in groups:
        group_sum = sum(v - offset for v in g)
        ssbn += group_sum * group_sum / len(g)
    ssbn -= normalized_ss

    sswn = sstot - ssbn
    dfbn = k - 1
    dfwn = total - k
    msb = ssbn / dfbn
    msw = sswn / dfwn
    f = msb / msw
    p = FSurvival(dfbn, dfwn, f)
    return f, p


def ChiSquaredContingency(observed):
    """Chi-squared test of independence on an r×c contingency table.

    Matches scipy.stats.chi2_contingency with correction=True (Yates'
    continuity correction for a 2×2 table). Returns the chi-squared statistic,
    the two-sided p-value and the degrees of freedom (r-1)(c-1).
    """
    r = len(observed)
    if r == 0:
        return math.nan, math.nan, math.nan
    c = len(observed[0])
    if c == 0:
        return math.nan, math.nan, math.nan

    row_sum = [0.0] * r
    col_sum = [0.0] * c
    total = 0.0
    for i in range(r):
        for j in range(c):
            v = observed[i][j]
            total += v
            row_sum[i] += v
            col_sum[j] += v
    if total == 0:
        return math.nan, math.nan, math.nan

    dof = (r - 1) * (c - 1)
    chi2 = 0.0
    for i in range(r):
        for j in range(c):
            expected = row_sum[i] * col_sum[j] / total
            diff = observed[i][j] - expected
            if dof == 1:
                diff = abs(diff) - 0.5
            chi2 += diff * diff / expected
    p = ChiSquaredSurvival(dof, chi2)
    return chi2, p, float(dof)


def CramersV(chi2, n, r, c):
    """Cramér's V measure of association for an r×c contingency table."""
    min_dim = min(r - 1, c - 1)
    if n <= 0 or min_dim <= 0:
        return 0.0
    return math.sqrt(chi2 / (n * min_dim))
