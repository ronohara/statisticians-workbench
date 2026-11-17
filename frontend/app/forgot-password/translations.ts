// app/forgot-password/translations.ts
// ============================================================
// FORGOT PASSWORD MODULE TRANSLATIONS
// All translation keys used by the forgot password page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const FORGOT_PASSWORD = {
    title: { key: "forgot_password.title", fallback: "Forgot Password" },
    description: { key: "forgot_password.description", fallback: "Enter your email address and we'll send you a link to reset your password." },
    submit: { key: "forgot_password.submit", fallback: "Send Reset Link" },
    back_to_login: { key: "forgot_password.back_to_login", fallback: "Back to Login" },
    error: { key: "forgot_password.error", fallback: "Failed to send reset email" },
    sent: { key: "forgot_password.sent", fallback: "If an account exists with this email, you will receive a password reset link." },
    sent_title: { key: "forgot_password.sent_title", fallback: "Email Sent" },
    sent_description: { key: "forgot_password.sent_description", fallback: "If an account exists with this email, you will receive a password reset link." },
    check_spam: { key: "forgot_password.check_spam", fallback: "Please check your spam folder if you don't see the email within a few minutes." },
} as const;