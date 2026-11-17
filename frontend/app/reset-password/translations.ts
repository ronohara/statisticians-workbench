// app/reset-password/translations.ts
// ============================================================
// RESET PASSWORD MODULE TRANSLATIONS
// All translation keys used by the reset password page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const RESET_PASSWORD = {
    title: { key: "reset_password.title", fallback: "Reset Password" },
    description: { key: "reset_password.description", fallback: "Enter your new password below." },
    new_password: { key: "reset_password.new_password", fallback: "New Password" },
    confirm_password: { key: "reset_password.confirm_password", fallback: "Confirm New Password" },
    submit: { key: "reset_password.submit", fallback: "Reset Password" },
    login_button: { key: "reset_password.login_button", fallback: "Go to Login" },
    missing_token: { key: "reset_password.missing_token", fallback: "No reset token provided" },
    password_mismatch: { key: "reset_password.password_mismatch", fallback: "Passwords do not match" },
    failed: { key: "reset_password.failed", fallback: "Failed to reset password" },
    success: { key: "reset_password.success", fallback: "Password reset successfully" },
    success_title: { key: "reset_password.success_title", fallback: "Password Reset" },
    success_description: { key: "reset_password.success_description", fallback: "Your password has been reset. Redirecting to login..." },
} as const;