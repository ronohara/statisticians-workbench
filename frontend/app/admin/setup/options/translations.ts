// app/admin/setup/options/translations.ts
// ============================================================
// OPTIONS SETTINGS MODULE TRANSLATIONS
// Installation-time configuration — set once, rarely changed.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const OPTIONS_SETTINGS = {
    title: { key: "setup.options.title", fallback: "Options" },
    description: { key: "setup.options.description", fallback: "Installation-time settings that define this deployment's identity and behaviour. Change with care — these affect all users." },
    load_error: { key: "setup.options.load_error", fallback: "Failed to load options settings" },
    save_success: { key: "setup.options.save_success", fallback: "Options settings saved" },
    save_error: { key: "setup.options.save_error", fallback: "Failed to save options settings" },
    save_button: { key: "setup.options.save_button", fallback: "Save Options" },

    email_sender: {
        label: { key: "setup.options.email_sender.label", fallback: "Email Sender Address" },
        hint: { key: "setup.options.email_sender.hint", fallback: "The email address that verification emails will appear to come from." },
    },

    public_url: {
        label: { key: "setup.options.public_url.label", fallback: "Public URL" },
        hint: { key: "setup.options.public_url.hint", fallback: "The base URL used in email verification links (e.g., https://workbench.example.com)." },
    },

    welcome: {
        label: { key: "setup.options.welcome.label", fallback: "Welcome Message" },
        placeholder: { key: "setup.options.welcome.placeholder", fallback: "Enter a welcome message to display on the login page." },
        hint: { key: "setup.options.welcome.hint", fallback: "This message will appear on the login page. Leave empty to hide it." },
    },

    password_policy: {
        label: { key: "setup.options.password_policy.label", fallback: "Password Policy" },
        select: { key: "setup.options.password_policy.select", fallback: "Select policy" },
        low: { key: "setup.options.password_policy.low", fallback: "Low (min 6 chars)" },
        medium: { key: "setup.options.password_policy.medium", fallback: "Medium (min 8, upper, lower, digit)" },
        high: { key: "setup.options.password_policy.high", fallback: "High (min 10, upper, lower, digit, special)" },
        custom: { key: "setup.options.password_policy.custom", fallback: "Custom" },
        min_length: { key: "setup.options.password_policy.min_length", fallback: "Minimum Length" },
        require_uppercase: { key: "setup.options.password_policy.require_uppercase", fallback: "Require Uppercase" },
        require_lowercase: { key: "setup.options.password_policy.require_lowercase", fallback: "Require Lowercase" },
        require_digit: { key: "setup.options.password_policy.require_digit", fallback: "Require Digit" },
        require_special: { key: "setup.options.password_policy.require_special", fallback: "Require Special Character" },
        min_strength: { key: "setup.options.password_policy.min_strength", fallback: "Minimum Strength (zxcvbn score 0-4)" },
        hint: { key: "setup.options.password_policy.hint", fallback: "Choose the password complexity requirements for user registration and password changes." },
    },

    registration_mode: {
        label: { key: "setup.options.registration_mode.label", fallback: "Registration Mode" },
        select: { key: "setup.options.registration_mode.select", fallback: "Select registration mode" },
        mode_0: { key: "setup.options.registration_mode.mode_0", fallback: "Self registration automatically verified" },
        mode_1: { key: "setup.options.registration_mode.mode_1", fallback: "Admin creates verified users" },
        mode_2: { key: "setup.options.registration_mode.mode_2", fallback: "Self registration and Admin verified" },
        mode_4: { key: "setup.options.registration_mode.mode_4", fallback: "Self registration with email verification" },
        hint: { key: "setup.options.registration_mode.hint", fallback: "Choose how new user accounts are created and verified." },
    },

} as const;
