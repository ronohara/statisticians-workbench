// app/login/translations.ts
// ============================================================
// LOGIN MODULE TRANSLATIONS
// All translation keys used by the login page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const LOGIN = {
    title: { key: "login.title", fallback: "Login" },
    description: { key: "login.description", fallback: "Sign in to your account" },
    email: { key: "login.email", fallback: "Email" },
    password: { key: "login.password", fallback: "Password" },
    forgot_password: { key: "login.forgot_password", fallback: "Forgot password?" },
    resend_link: { key: "login.resend_link", fallback: "Resend verification email?" },
    signing_in: { key: "login.signing_in", fallback: "Signing in..." },
    submit: { key: "login.submit", fallback: "Login" },
    no_account: { key: "login.no_account", fallback: "Don't have an account?" },
    register_link: { key: "login.register_link", fallback: "Register" },
    success: { key: "login.success", fallback: "Logged in successfully" },
    email_verified: { key: "login.email_verified", fallback: "Email verified successfully! You can now log in." },
    invalid_token: { key: "login.invalid_token", fallback: "Invalid verification link. Please request a new one." },
    token_expired: { key: "login.token_expired", fallback: "Verification link has expired. Please request a new one." },
    missing_token: { key: "login.missing_token", fallback: "No verification token provided." },
    email_not_verified: { key: "login.email_not_verified", fallback: "Email not verified. Please check your inbox and SPAM folder." },
    account_deleted: { key: "login.account_deleted", fallback: "This account has been deleted." },
    invalid_credentials: { key: "login.invalid_credentials", fallback: "Invalid email or password." },
    docs_more_info: { key: "login.docs_more_info", fallback: "has more information" },
} as const;