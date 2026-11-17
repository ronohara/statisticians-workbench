// app/resend-verification/translations.ts
// ============================================================
// RESEND VERIFICATION MODULE TRANSLATIONS
// All translation keys used by the resend verification page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const RESEND_VERIFICATION = {
    title: { key: "resend_verification.title", fallback: "Resend Verification Email" },
    description: { key: "resend_verification.description", fallback: "Enter your email address to receive a new verification link." },
    send_button: { key: "resend_verification.send_button", fallback: "Send Verification Email" },
    back_to_login: { key: "resend_verification.back_to_login", fallback: "Back to Login" },
    error: { key: "resend_verification.error", fallback: "Failed to send verification email." },
    sent: { key: "resend_verification.sent", fallback: "Verification email sent. Please check your inbox (and spam folder)." },
    sent_title: { key: "resend_verification.sent_title", fallback: "Email Sent" },
    sent_description: { key: "resend_verification.sent_description", fallback: "If an account exists with this email, you will receive a verification link." },
    check_spam: { key: "resend_verification.check_spam", fallback: "Please check your spam folder if you don't see the email within a few minutes." },
} as const;