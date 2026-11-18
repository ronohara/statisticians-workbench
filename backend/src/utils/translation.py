"""
Translation service for the backend.
Accesses the Translation table (same as frontend) for localized messages.
"""

import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Library-string intercepts: hardcoded third-party library strings → the
# translation key we route them through. Scope is deliberately limited (see the
# translation-system documentation, "Library-String Intercepts"): fixed,
# exact-match strings only — never parameterized or dynamically-composed
# messages. Each entry is a conscious, per-string decision.
INTERCEPTS = {
    "Not authenticated": "api.auth.not_authenticated",
}


def discover_intercept(string: str) -> Optional[str]:
    """Return the translation key for a hardcoded library string, or None if the
    string is not intercepted (the caller should then emit it unchanged)."""
    return INTERCEPTS.get(string)


async def get_translation(db_pool, language: str, key: str, fallback: Optional[str] = None) -> str:
    """Get a translation by key and language from the database."""
    try:
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT value FROM "Translation" WHERE language = $1 AND key = $2',
                language, key
            )
            if row:
                return row["value"]
            # A missing row is reported rather than passed over in silence: it is
            # the condition the Go backend logs, and without it the only evidence
            # that a key has no row anywhere is the fallback text quietly
            # appearing. The wording matches Go's line, so one search covers both
            # backends.
            logger.error(f"Translation DB lookup failed key={key} lang={language} error=no rows in result set")
    except Exception as e:
        logger.error(f"Translation DB lookup failed key={key} lang={language} error={e}")
    
    # Fallback to English
    if language != "en":
        return await get_translation(db_pool, "en", key, fallback)
    
    # Return fallback or key
    return fallback or key

async def t(db_pool, language: str, key, fallback: Optional[str] = None, **kwargs) -> str:
    """
    Translate a key with optional variable substitution.
    
    Args:
        db_pool: Database connection pool
        language: Language code (e.g., "en", "fr", "de")
        key: Translation key string (e.g., "error.dataset.not_found"), or a
             TranslationKey declaration object (duck-typed: exposes .key and
             .fallback) — the Option B shape; the declaration is the single
             source of the English fallback
        fallback: English fallback string (used when key is a plain string)
        **kwargs: Variables to substitute in the translation
    
    Returns:
        Translated string with variables replaced
    
    Example:
        await t(db_pool, "fr", RECIPES["recipes.not_found"], id=123)
        -> "Recette 123 introuvable" (if translation exists)
        -> "Recipe 123 not found" (if translation missing, falls back to English)
    """
    # Option B: unpack a TranslationKey declaration (key + fallback).
    if hasattr(key, "key") and hasattr(key, "fallback"):
        fallback = key.fallback
        key = key.key
    if not fallback:
        fallback = key

    translation = await get_translation(db_pool, language, key, fallback)
    
    # Replace variables
    for var_name, var_value in kwargs.items():
        placeholder = "{" + var_name + "}"
        if isinstance(var_value, (int, float)):
            var_value = str(var_value)
        translation = translation.replace(placeholder, str(var_value))
    
    return translation