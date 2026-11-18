"""
Language detection for the backend.
Extracts user language preference from JWT token or Accept-Language header.
"""

import os
from typing import Optional
from fastapi import Request, HTTPException
from fastapi.security import HTTPAuthorizationCredentials
import jwt

# Constants
DEFAULT_LANGUAGE = "en"
HEADER_LANGUAGE = "Accept-Language"

async def get_user_language_from_token(
    credentials: HTTPAuthorizationCredentials,
    db_pool
) -> str:
    """Extract user language preference from JWT token."""
    SECRET_KEY = os.getenv("NEXTAUTH_SECRET")
    if not SECRET_KEY:
        return DEFAULT_LANGUAGE
    
    try:
        token = credentials.credentials
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        user_id = payload.get("id")
        if not user_id:
            return DEFAULT_LANGUAGE
        
        # Fetch user's language directly from User table
        async with db_pool.acquire() as conn:
            row = await conn.fetchrow(
                'SELECT language FROM "User" WHERE id = $1',
                user_id
            )
            if row and row["language"]:
                return row["language"]
    except Exception:
        pass
    
    return DEFAULT_LANGUAGE

def get_language_from_header(request: Request) -> str:
    """Extract language from Accept-Language header."""
    accept_language = request.headers.get(HEADER_LANGUAGE)
    if not accept_language:
        return DEFAULT_LANGUAGE
    
    # Parse Accept-Language header (e.g., "fr-FR,fr;q=0.9,en;q=0.8")
    languages = accept_language.split(",")
    if languages:
        first_lang = languages[0].split(";")[0].strip()
        # Get the language code (e.g., "fr" from "fr-FR")
        lang_code = first_lang.split("-")[0]
        return lang_code
    
    return DEFAULT_LANGUAGE

async def get_user_language(
    request: Request,
    credentials: Optional[HTTPAuthorizationCredentials] = None,
    db_pool = None
) -> str:
    """
    Get user's preferred language.
    Priority: 1. JWT token, 2. Accept-Language header, 3. Default
    """
    # Try to get from JWT token first
    if credentials and db_pool:
        try:
            lang = await get_user_language_from_token(credentials, db_pool)
            if lang:
                return lang
        except Exception:
            pass
    
    # Fall back to Accept-Language header
    header_lang = get_language_from_header(request)
    if header_lang:
        return header_lang
    
    return DEFAULT_LANGUAGE