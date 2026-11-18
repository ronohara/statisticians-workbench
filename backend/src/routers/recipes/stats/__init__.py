"""
Permissive statistics substrate for the recipe stream.

Pure-Python distribution primitives (CDF / survival / quantile) that mirror
``workbench-go/internal/stats/distributions.go``. Built on the stdlib ``math``
module only — no scipy / numpy / statsmodels / sklearn — so the recipe code can
drop the scientific stack while keeping byte-comparable numbers. Parity is
checked against scipy 1.18.0 golden values (scipy lives only in the tests).
"""

from .distributions import (
    ChiSquaredCDF,
    ChiSquaredQuantile,
    ChiSquaredSurvival,
    FCDF,
    FQuantile,
    FSurvival,
    NormalCDF,
    NormalQuantile,
    NormalSurvival,
    StudentsTCDF,
    StudentsTQuantile,
    StudentsTSurvival,
)
from .hypothesis import (
    ChiSquaredContingency,
    CramersV,
    FOneway,
    TTestIndPooled,
    TTestIndWelch,
    TTestRel,
)
from .regression import (
    ANOVAEffect,
    Linregress,
    LinregressResult,
    MultipleRegression,
    OLSResult,
    TwoWayANOVA,
)

__all__ = [
    "NormalCDF",
    "NormalSurvival",
    "NormalQuantile",
    "StudentsTCDF",
    "StudentsTSurvival",
    "StudentsTQuantile",
    "FCDF",
    "FSurvival",
    "FQuantile",
    "ChiSquaredCDF",
    "ChiSquaredSurvival",
    "ChiSquaredQuantile",
    "TTestIndPooled",
    "TTestIndWelch",
    "TTestRel",
    "FOneway",
    "ChiSquaredContingency",
    "CramersV",
    "Linregress",
    "LinregressResult",
    "MultipleRegression",
    "OLSResult",
    "TwoWayANOVA",
    "ANOVAEffect",
]
