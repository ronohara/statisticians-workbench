// app/adduser/translations.ts
// ============================================================
// ADD-USER MODULE TRANSLATIONS
// All translation keys used by the admin add-user page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const ADDUSER = {
    title: { key: "admin.adduser.title", fallback: "Add User" },
    description: { key: "admin.adduser.description", fallback: "Create a new user account. The account is verified immediately." },
    name: { key: "admin.adduser.name", fallback: "Name" },
    email: { key: "admin.adduser.email", fallback: "Email" },
    password: { key: "admin.adduser.password", fallback: "Password" },
    confirm_password: { key: "admin.adduser.confirm_password", fallback: "Confirm Password" },
    language_description: { key: "admin.adduser.language_description", fallback: "Choose the user's preferred language for the interface." },
    creating: { key: "admin.adduser.creating", fallback: "Creating user..." },
    submit: { key: "admin.adduser.submit", fallback: "Create User" },
    password_mismatch: { key: "admin.adduser.password_mismatch", fallback: "Passwords do not match" },
    success: { key: "admin.adduser.success", fallback: "Account created and verified. The new user can now sign in." },
    failed: { key: "admin.adduser.failed", fallback: "Failed to create user" },
    not_admin: { key: "admin.adduser.not_admin", fallback: "You do not have permission to access this page." },
    back_to_admin: { key: "admin.adduser.back_to_admin", fallback: "Back to Admin" },
} as const;
