"""
Distribution primitives — the permissive-library statistics substrate.

Pure-Python CDF / survival / quantile functions for the Normal, Student's t, F
and chi-squared distributions, mirroring the surface of
``workbench-go/internal/stats/distributions.go`` (which is backed by
gonum/stat/distuv). Only the stdlib ``math`` module is used, so the recipe
stream can drop scipy/statsmodels without changing the numbers.

Parity is verified against scipy 1.18.0 golden values in
``backend/tests/test_stats_distributions.py`` (scipy never appears here).
"""

import math

# Numerical guards (Numerical Recipes conventions).
_FPMIN = 1e-300  # floor for a divisor/corrector to avoid divide-by-zero
_EPS = 1e-16     # convergence tolerance for the continued fractions


# ---------------------------------------------------------------------------
# Incomplete gamma — P(a, x) and Q(a, x) (regularised)
# ---------------------------------------------------------------------------

def _gser(a, x):
    """Series representation of the lower regularised incomplete gamma P(a, x)."""
    ap = a
    s = 1.0 / a
    d = s
    for _ in range(200):
        ap += 1.0
        d *= x / ap
        s += d
        if abs(d) < abs(s) * _EPS:
            break
    return s * math.exp(-x + a * math.log(x) - math.lgamma(a))


def _gcf(a, x):
    """Lentz continued fraction for the upper regularised incomplete gamma Q(a, x)."""
    b = x + 1.0 - a
    c = 1.0 / _FPMIN
    d = 1.0 / b
    h = d
    for i in range(1, 200):
        an = -i * (i - a)
        b += 2.0
        d = an * d + b
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = b + an / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        del_ = d * c
        h *= del_
        if abs(del_ - 1.0) < _EPS:
            break
    return math.exp(-x + a * math.log(x) - math.lgamma(a)) * h


def _igam(a, x):
    """Lower regularised incomplete gamma P(a, x)."""
    if x <= 0.0:
        return 0.0
    if x < a + 1.0:
        return _gser(a, x)
    return 1.0 - _gcf(a, x)


def _igamc(a, x):
    """Upper regularised incomplete gamma Q(a, x)."""
    if x <= 0.0:
        return 1.0
    if x < a + 1.0:
        return 1.0 - _gser(a, x)
    return _gcf(a, x)


# ---------------------------------------------------------------------------
# Incomplete beta — I_x(a, b) (regularised)
# ---------------------------------------------------------------------------

def _betacf(a, b, x):
    """Continued fraction for the incomplete beta function (Numerical Recipes)."""
    qab = a + b
    qap = a + 1.0
    qam = a - 1.0
    c = 1.0
    d = 1.0 - qab * x / qap
    if abs(d) < _FPMIN:
        d = _FPMIN
    d = 1.0 / d
    h = d
    for m in range(1, 200):
        m2 = 2 * m
        aa = m * (b - m) * x / ((qam + m2) * (a + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        h *= d * c
        aa = -(a + m) * (qab + m) * x / ((a + m2) * (qap + m2))
        d = 1.0 + aa * d
        if abs(d) < _FPMIN:
            d = _FPMIN
        c = 1.0 + aa / c
        if abs(c) < _FPMIN:
            c = _FPMIN
        d = 1.0 / d
        del_ = d * c
        h *= del_
        if abs(del_ - 1.0) < _EPS:
            break
    return h


def _betai(a, b, x):
    """Regularised incomplete beta I_x(a, b)."""
    if x <= 0.0:
        return 0.0
    if x >= 1.0:
        return 1.0
    bt = math.exp(
        math.lgamma(a + b) - math.lgamma(a) - math.lgamma(b)
        + a * math.log(x) + b * math.log1p(-x)
    )
    if x < (a + 1.0) / (a + b + 2.0):
        return bt * _betacf(a, b, x) / a
    return 1.0 - bt * _betacf(b, a, 1.0 - x) / b


# ---------------------------------------------------------------------------
# Inverse CDF helpers
# ---------------------------------------------------------------------------

def _ndtri(p):
    """Inverse of the standard normal CDF (Acklam + one Newton refinement)."""
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf

    a = (
        -3.969683028665376e+01, 2.209460984245205e+02, -2.759285104469687e+02,
        1.383577518672690e+02, -3.066479806614716e+01, 2.506628277459239e+00,
    )
    b = (
        -5.447609879822406e+01, 1.615858368580409e+02, -1.556989798598866e+02,
        6.680131188771972e+01, -1.328068155288572e+01,
    )
    c = (
        -7.784894002430293e-03, -3.223964580411365e-01, -2.400758277161838e+00,
        -2.549732539343734e+00, 4.374664141464968e+00, 2.938163982698783e+00,
    )
    d = (
        7.784695709041462e-03, 3.224671290700398e-01, 2.445134137142996e+00,
        3.754408661907416e+00,
    )

    plow = 0.02425
    phigh = 1.0 - plow
    if p < plow:
        q = math.sqrt(-2.0 * math.log(p))
        x = (((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)
    elif p <= phigh:
        q = p - 0.5
        r = q * q
        x = (((((a[0] * r + a[1]) * r + a[2]) * r + a[3]) * r + a[4]) * r + a[5]) * q / \
            (((((b[0] * r + b[1]) * r + b[2]) * r + b[3]) * r + b[4]) * r + 1.0)
    else:
        q = math.sqrt(-2.0 * math.log(1.0 - p))
        x = -(((((c[0] * q + c[1]) * q + c[2]) * q + c[3]) * q + c[4]) * q + c[5]) / \
            ((((d[0] * q + d[1]) * q + d[2]) * q + d[3]) * q + 1.0)

    # One Newton refinement against the exact CDF (erfc) to reach full precision.
    e = 0.5 * math.erfc(-x / math.sqrt(2.0)) - p
    u = e * math.sqrt(2.0 * math.pi) * math.exp(0.5 * x * x)
    return x - u / (1.0 + 0.5 * x * u)


def _invert_cdf(cdf, p, lo, hi, tol=1e-15, max_iter=200):
    """Invert a monotone increasing CDF on [lo, hi] by expanding + bisection."""
    if p <= 0.0:
        return lo
    if p >= 1.0:
        return math.inf
    while cdf(hi) < p:
        hi *= 2.0
    a, b = lo, hi
    for _ in range(max_iter):
        m = 0.5 * (a + b)
        if cdf(m) < p:
            a = m
        else:
            b = m
        if (b - a) < tol * max(1.0, abs(m)):
            break
    return 0.5 * (a + b)


# ---------------------------------------------------------------------------
# Normal distribution
# ---------------------------------------------------------------------------

def NormalCDF(mu, sigma, x):
    """CDF of N(mu, sigma) at x."""
    z = (x - mu) / sigma
    return 0.5 * math.erfc(-z / math.sqrt(2.0))


def NormalSurvival(mu, sigma, x):
    """Survival function 1 - NormalCDF(mu, sigma, x)."""
    z = (x - mu) / sigma
    return 0.5 * math.erfc(z / math.sqrt(2.0))


def NormalQuantile(mu, sigma, p):
    """Inverse CDF (quantile) of N(mu, sigma) at p."""
    return mu + sigma * _ndtri(p)


# ---------------------------------------------------------------------------
# Student's t distribution (standard, mu=0, sigma=1)
# ---------------------------------------------------------------------------

def StudentsTCDF(nu, x):
    """CDF of the standard Student's t distribution with nu df at x."""
    y = nu / (nu + x * x)
    if x >= 0.0:
        return 1.0 - 0.5 * _betai(nu / 2.0, 0.5, y)
    return 0.5 * _betai(nu / 2.0, 0.5, y)


def StudentsTSurvival(nu, x):
    """Survival function 1 - StudentsTCDF(nu, x)."""
    return 1.0 - StudentsTCDF(nu, x)


def StudentsTQuantile(nu, p):
    """Inverse CDF of the standard Student's t distribution with nu df at p."""
    if p <= 0.0:
        return -math.inf
    if p >= 1.0:
        return math.inf
    if p == 0.5:
        return 0.0
    if p < 0.5:
        return -StudentsTQuantile(nu, 1.0 - p)
    return _invert_cdf(lambda x: StudentsTCDF(nu, x), p, 0.0, 1.0)


# ---------------------------------------------------------------------------
# F distribution
# ---------------------------------------------------------------------------

def FCDF(d1, d2, x):
    """CDF of the F distribution with d1/d2 degrees of freedom at x."""
    if x <= 0.0:
        return 0.0
    y = d1 * x / (d1 * x + d2)
    return _betai(d1 / 2.0, d2 / 2.0, y)


def FSurvival(d1, d2, x):
    """Survival function 1 - FCDF(d1, d2, x)."""
    return 1.0 - FCDF(d1, d2, x)


def FQuantile(d1, d2, p):
    """Inverse CDF of the F distribution F(d1, d2) at p."""
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return math.inf
    return _invert_cdf(lambda x: FCDF(d1, d2, x), p, 0.0, 1.0)


# ---------------------------------------------------------------------------
# Chi-squared distribution
# ---------------------------------------------------------------------------

def ChiSquaredCDF(k, x):
    """CDF of the chi-squared distribution with k df at x."""
    if x <= 0.0:
        return 0.0
    return _igam(k / 2.0, x / 2.0)


def ChiSquaredSurvival(k, x):
    """Survival function 1 - ChiSquaredCDF(k, x)."""
    if x <= 0.0:
        return 1.0
    return _igamc(k / 2.0, x / 2.0)


def ChiSquaredQuantile(k, p):
    """Inverse CDF of the chi-squared distribution with k df at p."""
    if p <= 0.0:
        return 0.0
    if p >= 1.0:
        return math.inf
    return _invert_cdf(lambda x: ChiSquaredCDF(k, x), p, 0.0, 1.0)
