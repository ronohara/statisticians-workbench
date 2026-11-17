// app/register/translations.ts
// ============================================================
// REGISTER MODULE TRANSLATIONS
// All translation keys used by the registration page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const REGISTER = {
    title: { key: "register.title", fallback: "Register" },
    description: { key: "register.description", fallback: "Create a new account" },
    name: { key: "register.name", fallback: "Name" },
    email: { key: "register.email", fallback: "Email" },
    password: { key: "register.password", fallback: "Password" },
    confirm_password: { key: "register.confirm_password", fallback: "Confirm Password" },
    language_description: { key: "register.language_description", fallback: "Choose your preferred language for the interface." },
    creating: { key: "register.creating", fallback: "Creating account..." },
    submit: { key: "register.submit", fallback: "Register" },
    have_account: { key: "register.have_account", fallback: "Already have an account?" },
    login_link: { key: "register.login_link", fallback: "Login" },
    password_mismatch: { key: "register.password_mismatch", fallback: "Passwords do not match" },
    success_auto_verified: { key: "register.success_auto_verified", fallback: "Your account has been created and is ready to use. You can now sign in." },
    success_pending_approval: { key: "register.success_pending_approval", fallback: "Your account has been created and is awaiting administrator approval. You will be able to sign in once it has been approved." },
    success_with_verification: { key: "register.success_with_verification", fallback: "Your account has been created. Check your email for the verification link to activate your account." },
    email_failed_use_resend: { key: "register.email_failed_use_resend", fallback: "Registration successful, but the verification email couldn't be sent. Please resend it from the login page." },
    failed: { key: "register.failed", fallback: "Registration failed" },
    registration_disabled: { key: "register.registration_disabled", fallback: "Self-registration is disabled. Please contact an administrator." },
} as const;