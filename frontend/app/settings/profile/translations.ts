// app/settings/profile/translations.ts
// ============================================================
// PROFILE SETTINGS MODULE TRANSLATIONS
// All translation keys used by the profile settings page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const PROFILE_SETTINGS = {
    title: { key: "profile.title", fallback: "Profile Settings" },

    // Personal
    personal: {
        title: { key: "profile.personal.title", fallback: "Profile & Preferences" },
        description: { key: "profile.personal.description", fallback: "Update your personal information and app preferences." },
    },

    // The slow-model threshold (plan Item 21). The user's own value, empty when they
    // inherit — and the effective number is shown beside it, so an empty field never hides
    // what actually applies.
    slow_threshold: {
        title: { key: "profile.slow_threshold.title", fallback: "Slow-model threshold" },
        description: {
            key: "profile.slow_threshold.description",
            fallback: "A model test taking longer than this is reported as too slow. Leave empty to use the site default.",
        },
        label: { key: "profile.slow_threshold.label", fallback: "My limit" },
        placeholder: { key: "profile.slow_threshold.placeholder", fallback: "Use the site default" },
        effective: { key: "profile.slow_threshold.effective", fallback: "Currently in effect:" },
        seconds: { key: "profile.slow_threshold.seconds", fallback: "seconds" },
        save: { key: "profile.slow_threshold.save", fallback: "Save limit" },
        saved: { key: "profile.slow_threshold.saved", fallback: "Slow-model limit saved" },
        invalid: {
            key: "profile.slow_threshold.invalid",
            fallback: "The limit must be a whole number of seconds, at least 1",
        },
    },

    // Fields
    name_label: { key: "profile.name_label", fallback: "Name" },
    name_placeholder: { key: "profile.name_placeholder", fallback: "Your name" },
    email_label: { key: "profile.email_label", fallback: "Email" },
    email_unchangeable: { key: "profile.email_unchangeable", fallback: "Email cannot be changed" },

    // Group info
    group_info_title: { key: "profile.group_info_title", fallback: "Group Information" },
    group_id: { key: "profile.group_id", fallback: "Group ID" },
    group_description: { key: "profile.group_description", fallback: "Description" },
    group_readonly_hint: { key: "profile.group_readonly_hint", fallback: "Your group is assigned by an administrator and cannot be changed here." },

    // Preferences
    email_notifications_label: { key: "profile.email_notifications_label", fallback: "Email Notifications" },
    email_notifications_description: { key: "profile.email_notifications_description", fallback: "Receive email updates about your account." },
    dark_mode_label: { key: "profile.dark_mode_label", fallback: "Dark Mode" },
    dark_mode_description: { key: "profile.dark_mode_description", fallback: "Toggle between light and dark theme." },
    language_label: { key: "profile.language_label", fallback: "Language" },
    language_select_placeholder: { key: "profile.language_select_placeholder", fallback: "Select language" },
    language_description: { key: "profile.language_description", fallback: "Choose your preferred language for the interface." },

    // Save
    save_button: { key: "profile.save_button", fallback: "Save Changes" },

    // Change Password
    change_password: {
        title: { key: "profile.change_password.title", fallback: "Change Password" },
        description: { key: "profile.change_password.description", fallback: "Update your password." },
    },
    current_password: { key: "profile.current_password", fallback: "Current Password" },
    new_password: { key: "profile.new_password", fallback: "New Password" },
    confirm_password: { key: "profile.confirm_password", fallback: "Confirm New Password" },
    change_password_button: { key: "profile.change_password_button", fallback: "Change Password" },

    // Example User
    password_disabled: { key: "profile.password_disabled", fallback: "Password changes are disabled for example users" },
    password_disabled_message: { key: "profile.password_disabled_message", fallback: "You are logged in as an Example User. Password functions are disabled." },
    example_user_name_hint: { key: "profile.example_user_name_hint", fallback: "Register for full access to change your name." },
    example_user_notifications_hint: { key: "profile.example_user_notifications_hint", fallback: "Register for full access to change notification settings." },
    example_user_theme_hint: { key: "profile.example_user_theme_hint", fallback: "Register for full access to change theme preferences." },
    example_user_language_hint: { key: "profile.example_user_language_hint", fallback: "Register for full access to change your language preference." },
    example_user_save_hint: { key: "profile.example_user_save_hint", fallback: "Register for full access to save changes." },

    // Error messages
    load_error: { key: "profile.load_error", fallback: "Failed to load settings" },
    languages_load_error: { key: "profile.languages_load_error", fallback: "Failed to load languages" },
    group_load_error: { key: "profile.group_load_error", fallback: "Failed to load group info" },
    update_error: { key: "profile.update_error", fallback: "Failed to update profile" },
    save_success: { key: "profile.save_success", fallback: "Profile saved" },
    save_error: { key: "profile.save_error", fallback: "Failed to save profile" },
    password_mismatch: { key: "profile.password_mismatch", fallback: "New passwords do not match" },
    current_password_required: { key: "profile.current_password_required", fallback: "Current password is required" },
    password_change_failed: { key: "profile.password_change_failed", fallback: "Failed to change password" },
    password_changed: { key: "profile.password_changed", fallback: "Password changed successfully" },
} as const;