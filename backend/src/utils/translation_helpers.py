# src/utils/translation_helpers.py
# ============================================================
# TRANSLATION HELPERS
# Utility functions for working with TranslationKey objects.
# No translation keys are defined here - they live in module
# translation files.
# ============================================================

from dataclasses import dataclass
from typing import Any, Dict, Optional


@dataclass
class TranslationKey:
    """A translation key with an English fallback."""
    key: str
    fallback: str


async def tt(
    db_pool,
    language: str,
    translation: TranslationKey,
    **kwargs
) -> str:
    """
    Get a translation using a TranslationKey object.
    
    Args:
        db_pool: Database connection pool
        language: User's language code
        translation: TranslationKey object with key and fallback
        **kwargs: Variables to substitute in the translation
    
    Returns:
        Translated string with variables replaced
    
    Example:
        from src.routers.datasets.translations import DATASETS
        msg = await tt(db_pool, language, DATASETS["datasets.not_found"], id=dataset_id)
    """
    from src.utils.translation import t
    return await t(db_pool, language, translation, **kwargs)


def get_translation_key(key: str, fallback: str) -> TranslationKey:
    """
    Create a TranslationKey object (for dynamic keys).
    
    Args:
        key: The translation key
        fallback: The English fallback string
    
    Returns:
        TranslationKey object
    
    Example:
        dynamic_key = get_translation_key(f"error.{module}.{code}", "An error occurred")
    """
    return TranslationKey(key, fallback)


def get_error_message_from_data(
    error_data: Any,
    default_key: TranslationKey
) -> str:
    """
    Extract a user-facing error message from error data.
    This is a synchronous version for use outside async contexts.
    
    Args:
        error_data: The error data object (dict or similar)
        default_key: TranslationKey to use as fallback
    
    Returns:
        User-facing error message string
    
    Example:
        from src.routers.datasets.translations import DATASETS
        msg = get_error_message_from_data(error_data, DATASETS["datasets.list_error"])
    """
    if not error_data:
        return default_key.fallback
    
    # If we have both error and message, treat error as key, message as fallback
    if hasattr(error_data, 'get'):
        error = error_data.get('error')
        message = error_data.get('message')
        
        if error and message:
            # If error looks like a translation key, use it with message as fallback
            if isinstance(error, str) and '.' in error:
                # We can't translate here (no db_pool), but we can return the fallback
                # with a note that it should be translated
                return message
        
        # If we have a detail field (FastAPI style)
        if error_data.get('detail'):
            detail = error_data['detail']
            if isinstance(detail, str):
                return detail
            return str(detail)
        
        # If we have a message field
        if error_data.get('message'):
            message = error_data['message']
            if isinstance(message, str):
                return message
            return str(message)
        
        # If we have an error field
        if error_data.get('error'):
            error = error_data['error']
            if isinstance(error, str):
                return error
            return str(error)
    
    return default_key.fallback