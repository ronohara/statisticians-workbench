// app/verify-email/translations.ts
// ============================================================
// VERIFY EMAIL MODULE TRANSLATIONS
// All translation keys used by the verify email page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const VERIFY_EMAIL = {
    invalid_token: { key: "verify_email.invalid_token", fallback: "Invalid verification link." },
    unknown_error: { key: "verify_email.unknown_error", fallback: "Something went wrong." },
    network_error: { key: "verify_email.network_error", fallback: "Network error. Please try again." },
    success_title: { key: "verify_email.success_title", fallback: "Email Verified" },
    success_description: { key: "verify_email.success_description", fallback: "Your email has been successfully verified. Redirecting to login..." },
    login_button: { key: "verify_email.login_button", fallback: "Proceed to Login" },
    expired_title: { key: "verify_email.expired_title", fallback: "Link Expired" },
    expired_description: { key: "verify_email.expired_description", fallback: "The verification link has expired." },
    expired_message: { key: "verify_email.expired_message", fallback: "You can request a new verification email below." },
    resend_button: { key: "verify_email.resend_button", fallback: "Resend Verification Email" },
    missing_title: { key: "verify_email.missing_title", fallback: "No Verification Token" },
    missing_description: { key: "verify_email.missing_description", fallback: "No verification token was provided." },
    error_title: { key: "verify_email.error_title", fallback: "Verification Failed" },
    error_description: { key: "verify_email.error_description", fallback: "Something went wrong." },
} as const;