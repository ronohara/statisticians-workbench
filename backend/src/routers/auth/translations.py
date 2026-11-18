# src/routers/auth/translations.py
# ============================================================
# AUTH ROUTER TRANSLATIONS
# All translation keys used by the auth router.
# ============================================================

from dataclasses import dataclass


@dataclass
class TranslationKey:
    """A translation key with an English fallback."""
    key: str
    fallback: str


AUTH = {
    # Error messages
    "auth.unauthorized": TranslationKey(
        "auth.unauthorized",
        "Unauthorized"
    ),
    "auth.invalid_credentials": TranslationKey(
        "auth.invalid_credentials",
        "Invalid credentials"
    ),
    "auth.email_not_verified": TranslationKey(
        "auth.email_not_verified",
        "Email not verified. Please check your inbox and SPAM folder."
    ),
    "auth.account_deleted": TranslationKey(
        "auth.account_deleted",
        "This account has been deleted."
    ),
    "auth.example_user_blocked": TranslationKey(
        "auth.example_user_blocked",
        "Password functions are disabled for example users"
    ),
    "auth.example_user_reset_blocked": TranslationKey(
        "auth.example_user_reset_blocked",
        "Password reset is disabled for example users"
    ),
    "auth.example_user_forgot_blocked": TranslationKey(
        "auth.example_user_forgot_blocked",
        "Password reset is disabled for example users"
    ),
    "auth.missing_fields": TranslationKey(
        "auth.missing_fields",
        "Missing fields"
    ),
    "auth.password_validation_failed": TranslationKey(
        "auth.password_validation_failed",
        "Password validation failed"
    ),
    "auth.invalid_token": TranslationKey(
        "auth.invalid_token",
        "Invalid or expired token"
    ),
    "auth.token_expired": TranslationKey(
        "auth.token_expired",
        "Token has expired"
    ),
    "auth.missing_email": TranslationKey(
        "auth.missing_email",
        "Email required"
    ),
    "auth.user_not_found": TranslationKey(
        "auth.user_not_found",
        "User not found"
    ),
    "auth.invalid_current_password": TranslationKey(
        "auth.invalid_current_password",
        "Current password is incorrect"
    ),
    "auth.internal_error": TranslationKey(
        "auth.internal_error",
        "Internal server error"
    ),

    # Success messages
    "auth.password_changed": TranslationKey(
        "auth.password_changed",
        "Password changed successfully"
    ),
    "auth.reset_email_sent": TranslationKey(
        "auth.reset_email_sent",
        "Password reset email sent"
    ),
}


# src/routers/auth/translations.py
# ============================================================
# REGISTER ROUTER TRANSLATIONS (item 20)
# ============================================================
# Keyed by the CANONICAL key string (one name per key — no alias indirection).
# password_validation_failed is not here: it is composed by localizing the
# shared validation.password.* keys through t().

REGISTER = {
    "api.register.invalid_email": TranslationKey(
        "api.register.invalid_email",
        "Invalid email format"
    ),
    "api.register.missing_fields": TranslationKey(
        "api.register.missing_fields",
        "Missing fields"
    ),
    "api.register.settings_not_found": TranslationKey(
        "api.register.settings_not_found",
        "Global settings not found"
    ),
    "api.register.email_exists": TranslationKey(
        "api.register.email_exists",
        "Email already exists"
    ),
    "api.register.internal_error": TranslationKey(
        "api.register.internal_error",
        "Internal server error"
    ),
    "api.register.limit_reached": TranslationKey(
        "api.register.limit_reached",
        "Registration limit reached (maximum {max_reg} users)."
    ),
    "api.register.registration_disabled": TranslationKey(
        "api.register.registration_disabled",
        "Self-registration is disabled. Please contact an administrator."
    ),
}


# src/routers/auth/translations.py
# ============================================================
# PASSWORD RESET ROUTER TRANSLATIONS (item 21)
# ============================================================
# Keyed by the CANONICAL api.auth.* key string (one name per key). The
# password_validation_failed message is composed by localizing the shared
# validation.password.* keys through t() in the router, not a registry entry.

PASSWORD_RESET = {
    "api.auth.missing_email": TranslationKey(
        "api.auth.missing_email",
        "Email required"
    ),
    "api.auth.example_user_forgot_blocked": TranslationKey(
        "api.auth.example_user_forgot_blocked",
        "Password reset is disabled for example users"
    ),
    "api.auth.missing_fields": TranslationKey(
        "api.auth.missing_fields",
        "Missing fields"
    ),
    "api.auth.invalid_token": TranslationKey(
        "api.auth.invalid_token",
        "Invalid or expired token"
    ),
    "api.auth.token_expired": TranslationKey(
        "api.auth.token_expired",
        "Token has expired"
    ),
    "api.auth.example_user_reset_blocked": TranslationKey(
        "api.auth.example_user_reset_blocked",
        "Password reset is disabled for example users"
    ),
    "api.auth.internal_error": TranslationKey(
        "api.auth.internal_error",
        "Internal server error"
    ),
    "api.auth.email_already_verified": TranslationKey(
        "api.auth.email_already_verified",
        "Email already verified"
    ),
}


# src/routers/auth/translations.py
# ============================================================
# LOGIN ROUTER TRANSLATIONS (P4)
# ============================================================
# Keyed by the CANONICAL key string (one name per key — no alias). The
# invalid-credentials message is unified (auth.login_invalid_credentials) —
# the frontend's old "Invalid credentials" vs "Invalid email or password."
# split is a dropped parity quirk (see the login router docstring).
# account_deleted / email_not_verified / internal_error reuse the existing
# canonical auth.* keys with their existing English fallbacks.

LOGIN = {
    "auth.login_invalid_credentials": TranslationKey(
        "auth.login_invalid_credentials",
        "Invalid email or password."
    ),
    "auth.account_deleted": TranslationKey(
        "auth.account_deleted",
        "This account has been deleted."
    ),
    "auth.email_not_verified": TranslationKey(
        "auth.email_not_verified",
        "Email not verified. Please check your inbox and SPAM folder."
    ),
    "auth.internal_error": TranslationKey(
        "auth.internal_error",
        "Internal server error"
    ),
}