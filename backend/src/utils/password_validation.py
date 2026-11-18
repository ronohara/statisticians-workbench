"""
Clean password validation — P2 Group 5, item 20 (Prisma-removal plan).

This is a DELIBERATE departure from the item-9 mirror (change_password.py):
that mirror faithfully recreated JavaScript's implicit type-coercion — the
undefined-.length skip, the String()-coerced regex tests, the non-empty-array
-> TypeError -> 500 path. JS coercion is a data-integrity defect, not a
behaviour to recreate (see workbench-documents/development-records/code-quirks.md, "Item-9 password validation
emulates JS coercion — a defect to rectify, not to reuse").

Clean contract:

  - validate_password(password, policy_name, custom) takes a STRING password.
    Non-string passwords are rejected by the CALLER's type gate before this
    module is reached — this module never raises, never coerces, and never
    silently skips a rule.
  - The policy rule table (min length, uppercase/lowercase/digit/special
    requirements, zxcvbn min strength) mirrors the frontend's policy tiers
    (low / medium / high / custom) with sensible defaults.
  - Returns the failing rules as (TranslationKey, kwargs) pairs, in the same
    order the frontend builds them; the caller localizes each via t() and
    joins with a single space.
"""

import re

from zxcvbn import zxcvbn as _zxcvbn

from src.routers.common.translations import VALIDATION

# Failing rule -> canonical TranslationKey (declared in common/translations.py).
_RULES = {
    "min_length": VALIDATION["validation.password.min_length"],
    "uppercase": VALIDATION["validation.password.require_uppercase"],
    "lowercase": VALIDATION["validation.password.require_lowercase"],
    "digit": VALIDATION["validation.password.require_digit"],
    "special": VALIDATION["validation.password.require_special"],
    "too_weak": VALIDATION["validation.password.too_weak"],
}

_RE_UPPER = re.compile(r"[A-Z]")
_RE_LOWER = re.compile(r"[a-z]")
_RE_DIGIT = re.compile(r"\d")
_RE_SPECIAL = re.compile(r"[^a-zA-Z0-9]")


def _policy_rules(policy_name, custom):
    """Policy rule table — mirrors the frontend tiers with clean defaults.
    policy_name: "low" | "medium" | "high" | "custom" (default "low").
    custom: dict of minLength/requireUppercase/... for the custom tier."""
    min_length = 6
    require_upper = require_lower = require_digit = require_special = False
    min_strength = 0

    if policy_name == "low":
        pass
    elif policy_name == "medium":
        min_length = 8
        require_upper = require_lower = require_digit = True
        min_strength = 2
    elif policy_name == "high":
        min_length = 10
        require_upper = require_lower = require_digit = require_special = True
        min_strength = 3
    elif policy_name == "custom":
        if isinstance(custom, dict):
            min_length = custom.get("minLength") or 6
            require_upper = bool(custom.get("requireUppercase", False))
            require_lower = bool(custom.get("requireLowercase", False))
            require_digit = bool(custom.get("requireDigit", False))
            require_special = bool(custom.get("requireSpecial", False))
            min_strength = custom.get("minStrength") or 0

    return min_length, require_upper, require_lower, require_digit, \
        require_special, min_strength


def validate_password(password, policy_name, custom=None):
    """Clean validation of a STRING password against the policy. Returns the
    failing rules as (TranslationKey, kwargs) pairs (empty = valid); the caller
    localizes each via t() and joins. Never raises; never coerces; never skips
    a rule on type grounds."""
    if not isinstance(password, str):
        # The caller must type-gate; this is a defensive contract assertion.
        return [(_RULES["min_length"], {"min": 8})]

    (min_length, require_upper, require_lower, require_digit,
     require_special, min_strength) = _policy_rules(policy_name, custom)

    errors = []
    if len(password) < min_length:
        errors.append((_RULES["min_length"], {"min": min_length}))
    if require_upper and not _RE_UPPER.search(password):
        errors.append((_RULES["uppercase"], {}))
    if require_lower and not _RE_LOWER.search(password):
        errors.append((_RULES["lowercase"], {}))
    if require_digit and not _RE_DIGIT.search(password):
        errors.append((_RULES["digit"], {}))
    if require_special and not _RE_SPECIAL.search(password):
        errors.append((_RULES["special"], {}))
    # zxcvbn strength check — mirrors the frontend: runs unconditionally
    # (whenever the password is non-empty), so `too_weak` can co-appear with
    # the rule errors above.
    if password and min_strength > 0 and _zxcvbn(password)["score"] < min_strength:
        errors.append((_RULES["too_weak"], {}))

    return errors
