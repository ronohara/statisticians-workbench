// app/admin/setup/limits/translations.ts
// ============================================================
// LIMITS SETTINGS MODULE TRANSLATIONS
// Operational controls an admin adjusts over time.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const LIMITS_SETTINGS = {
    title: { key: "setup.limits.title", fallback: "Limits" },
    description: { key: "setup.limits.description", fallback: "Operational controls for resource limits, timeouts, and system behaviour. Safe to adjust at any time." },
    load_error: { key: "setup.limits.load_error", fallback: "Failed to load limits settings" },
    save_success: { key: "setup.limits.save_success", fallback: "Limits settings saved" },
    save_error: { key: "setup.limits.save_error", fallback: "Failed to save limits settings" },
    save_button: { key: "setup.limits.save_button", fallback: "Save Limits" },
    invalid_registration_max: { key: "setup.limits.invalid_registration_max", fallback: "Please enter a valid positive number for max registrations" },
    invalid_timeout: { key: "setup.limits.invalid_timeout", fallback: "Please enter a valid positive number for verification timeout (hours)" },
    invalid_grace_period: { key: "setup.limits.invalid_grace_period", fallback: "Please enter a valid positive number for deletion delay (hours)" },
    // AI tuning, plan Item 3. Three refusals rather than one: each field has its own
    // rule, and a shared "invalid value" would leave the admin guessing which.

    // The six AI tuning values moved to admin/setup/tuning/translations.ts
    // (plan Item 4b). They are declared there and referenced from there; a second
    // declaration here would be the same key twice, which the linter reports.

    demo_mode: {
        label: { key: "setup.limits.demo_mode.label", fallback: "Demo Mode" },
        description: { key: "setup.limits.demo_mode.description", fallback: "When enabled, the system runs in demo mode — destructive actions are blocked and indicators are shown in the UI." },
    },

    max_registrations: {
        label: { key: "setup.limits.max_registrations.label", fallback: "Maximum User Registrations" },
        placeholder: { key: "setup.limits.max_registrations.placeholder", fallback: "Select limit" },
        unlimited: { key: "setup.limits.max_registrations.unlimited", fallback: "Unlimited" },
        users: { key: "setup.limits.max_registrations.users", fallback: "users" },
        hint: { key: "setup.limits.max_registrations.hint", fallback: "Set a limit on how many users can register." },
    },

    email_timeout: {
        label: { key: "setup.limits.email_timeout.label", fallback: "Email Verification Timeout (hours)" },
        hint: { key: "setup.limits.email_timeout.hint", fallback: "How many hours the email verification link remains valid." },
    },

    grace_period: {
        label: { key: "setup.limits.grace_period.label", fallback: "Deletion Delay (hours)" },
        hint: { key: "setup.limits.grace_period.hint", fallback: "Hours before soft-deleted accounts are permanently erased." },
    },

    upload: {
        default_size_label: { key: "setup.limits.upload.default_size_label", fallback: "Default Max Upload Size per User (MB)" },
        select_size: { key: "setup.limits.upload.select_size", fallback: "Select limit" },
        size_hint: { key: "setup.limits.upload.size_hint", fallback: "Maximum total storage per user (0 = unlimited). Applied to new users." },
        default_count_label: { key: "setup.limits.upload.default_count_label", fallback: "Default Max Upload Count per User" },
        select_count: { key: "setup.limits.upload.select_count", fallback: "Select limit" },
        count_hint: { key: "setup.limits.upload.count_hint", fallback: "Maximum number of datasets per user (0 = unlimited). Applied to new users." },
        size_unlimited: { key: "setup.limits.upload.size_unlimited", fallback: "Unlimited" },
        size_1_mb: { key: "setup.limits.upload.size_1_mb", fallback: "1 MB" },
        size_5_mb: { key: "setup.limits.upload.size_5_mb", fallback: "5 MB" },
        size_10_mb: { key: "setup.limits.upload.size_10_mb", fallback: "10 MB" },
        size_25_mb: { key: "setup.limits.upload.size_25_mb", fallback: "25 MB" },
        size_50_mb: { key: "setup.limits.upload.size_50_mb", fallback: "50 MB" },
        size_100_mb: { key: "setup.limits.upload.size_100_mb", fallback: "100 MB" },
        size_250_mb: { key: "setup.limits.upload.size_250_mb", fallback: "250 MB" },
        size_500_mb: { key: "setup.limits.upload.size_500_mb", fallback: "500 MB" },
        size_1_gb: { key: "setup.limits.upload.size_1_gb", fallback: "1 GB" },
        count_unlimited: { key: "setup.limits.upload.count_unlimited", fallback: "Unlimited" },
        count_1: { key: "setup.limits.upload.count_1", fallback: "1" },
        count_5: { key: "setup.limits.upload.count_5", fallback: "5" },
        count_10: { key: "setup.limits.upload.count_10", fallback: "10" },
        count_25: { key: "setup.limits.upload.count_25", fallback: "25" },
        count_50: { key: "setup.limits.upload.count_50", fallback: "50" },
        count_100: { key: "setup.limits.upload.count_100", fallback: "100" },
        count_250: { key: "setup.limits.upload.count_250", fallback: "250" },
        count_500: { key: "setup.limits.upload.count_500", fallback: "500" },
        count_1000: { key: "setup.limits.upload.count_1000", fallback: "1000" },
    },
} as const;
