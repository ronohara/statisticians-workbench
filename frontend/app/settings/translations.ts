// app/settings/translations.ts
// ============================================================
// SETTINGS MODULE TRANSLATIONS
// All translation keys used by settings pages.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

// ============================================================
// PROFILE
// ============================================================

export const PROFILE = {
    title: { key: "profile.title", fallback: "Profile Settings" },
    language_label: { key: "profile.language_label", fallback: "Language" },
    language_select_placeholder: { key: "profile.language_select_placeholder", fallback: "Select language" },
    name_label: { key: "profile.name_label", fallback: "Name" },
    name_placeholder: { key: "profile.name_placeholder", fallback: "Your name" },
    email_label: { key: "profile.email_label", fallback: "Email" },
    email_unchangeable: { key: "profile.email_unchangeable", fallback: "Email cannot be changed" },
    email_notifications_label: { key: "profile.email_notifications_label", fallback: "Email Notifications" },
    email_notifications_description: { key: "profile.email_notifications_description", fallback: "Receive email updates about your account." },
    dark_mode_label: { key: "profile.dark_mode_label", fallback: "Dark Mode" },
    dark_mode_description: { key: "profile.dark_mode_description", fallback: "Toggle between light and dark theme." },
    language_description: { key: "profile.language_description", fallback: "Choose your preferred language for the interface." },
    save_button: { key: "profile.save_button", fallback: "Save Changes" },
    load_error: { key: "profile.load_error", fallback: "Failed to load settings" },
    languages_load_error: { key: "profile.languages_load_error", fallback: "Failed to load languages" },
    group_load_error: { key: "profile.group_load_error", fallback: "Failed to load group info" },
    update_error: { key: "profile.update_error", fallback: "Failed to update profile" },
    save_success: { key: "profile.save_success", fallback: "Profile saved" },
    save_error: { key: "profile.save_error", fallback: "Failed to save profile" },
    password_disabled: { key: "profile.password_disabled", fallback: "Password changes are disabled for example users" },
    password_disabled_message: { key: "profile.password_disabled_message", fallback: "You are logged in as an Example User. Password functions are disabled." },
    password_mismatch: { key: "profile.password_mismatch", fallback: "New passwords do not match" },
    current_password_required: { key: "profile.current_password_required", fallback: "Current password is required" },
    password_change_failed: { key: "profile.password_change_failed", fallback: "Failed to change password" },
    password_changed: { key: "profile.password_changed", fallback: "Password changed successfully" },
    group_info_title: { key: "profile.group_info_title", fallback: "Group Information" },
    group_id: { key: "profile.group_id", fallback: "Group ID" },
    group_description: { key: "profile.group_description", fallback: "Description" },
    group_readonly_hint: { key: "profile.group_readonly_hint", fallback: "Your group is assigned by an administrator and cannot be changed here." },
    personal: {
        title: { key: "profile.personal.title", fallback: "Profile & Preferences" },
        description: { key: "profile.personal.description", fallback: "Update your personal information and app preferences." },
    },
    change_password: {
        title: { key: "profile.change_password.title", fallback: "Change Password" },
        description: { key: "profile.change_password.description", fallback: "Update your password." },
    },
    current_password: { key: "profile.current_password", fallback: "Current Password" },
    new_password: { key: "profile.new_password", fallback: "New Password" },
    confirm_password: { key: "profile.confirm_password", fallback: "Confirm New Password" },
    change_password_button: { key: "profile.change_password_button", fallback: "Change Password" },
} as const;

// ============================================================
// DATABASE CONNECTIONS
// ============================================================

export const DATABASE_CONNECTION = {
    deleted: { key: "database.connection.deleted", fallback: "Connection deleted" },
    delete_error: { key: "database.connection.delete_error", fallback: "Failed to delete connection" },
    default_set: { key: "database.connection.default_set", fallback: "Default connection updated" },
    load_error: { key: "database.connection.load_error", fallback: "Failed to load connections" },
    add_new: { key: "database.connection.add_new", fallback: "Add New Connection" },
    no_connections: { key: "database.connection.no_connections", fallback: "No database connections saved yet." },
    add_first: { key: "database.connection.add_first", fallback: "Add your first connection" },
    default_badge: { key: "database.connection.default_badge", fallback: "Default" },
    shared_badge: { key: "database.connection.shared_badge", fallback: "Shared" },
    by_label: { key: "database.connection.by_label", fallback: "by" },
    unknown_user: { key: "database.connection.unknown_user", fallback: "Unknown" },
    set_default: { key: "database.connection.set_default", fallback: "Set as Default" },
    shared_readonly: { key: "database.connection.shared_readonly", fallback: "Shared" },
    delete_title: { key: "database.connection.delete_title", fallback: "Delete Connection" },
    delete_confirmation: { key: "database.connection.delete_confirmation", fallback: "Are you sure you want to delete the connection" },
    delete_button: { key: "database.connection.delete_button", fallback: "Delete" },
    test_incomplete: { key: "database.connection.test_incomplete", fallback: "Please fill all fields before testing" },
    test_failed: { key: "database.connection.test_failed", fallback: "Connection failed" },
    test_success: { key: "database.connection.test_success", fallback: "Connection successful!" },
    test_network_error: { key: "database.connection.test_network_error", fallback: "Network error while testing connection." },
    add_success: { key: "database.connection.add_success", fallback: "Connection added successfully" },
    update_success: { key: "database.connection.update_success", fallback: "Connection updated successfully" },
    save_error: { key: "database.connection.save_error", fallback: "Failed to save connection" },
    not_found: { key: "database.connection.not_found", fallback: "Connection not found" },
    add_title: { key: "database.connection.add_title", fallback: "Add New Connection" },
    edit_title: { key: "database.connection.edit_title", fallback: "Edit Connection" },
    form_description: { key: "database.connection.form_description", fallback: "Enter your database connection details." },
    name_label: { key: "database.connection.name_label", fallback: "Connection Name" },
    name_placeholder: { key: "database.connection.name_placeholder", fallback: "e.g., Production DB" },
    type_label: { key: "database.connection.type_label", fallback: "Database Type" },
    select_type: { key: "database.connection.select_type", fallback: "Select type" },
    host_label: { key: "database.connection.host_label", fallback: "Host" },
    port_label: { key: "database.connection.port_label", fallback: "Port" },
    database_label: { key: "database.connection.database_label", fallback: "Database Name" },
    username_label: { key: "database.connection.username_label", fallback: "Username" },
    password_label: { key: "database.connection.password_label", fallback: "Password" },
    shared_label: { key: "database.connection.shared_label", fallback: "Share with group" },
    shared_description: { key: "database.connection.shared_description", fallback: "Make this connection available to other users in your group." },
    currently_shared: { key: "database.connection.currently_shared", fallback: "✅ Currently shared with group" },
    currently_not_shared: { key: "database.connection.currently_not_shared", fallback: "❌ Currently not shared" },
    test_button: { key: "database.connection.test_button", fallback: "Test Connection" },
} as const;

export const DATABASE = {
    title: { key: "database.title", fallback: "Database Settings" },
    default_hint: { key: "database.default_hint", fallback: "The default connection is used as a fallback when an analysis recipe does not specify a connection." },
    connection: DATABASE_CONNECTION,
} as const;

// ============================================================
// AI CONNECTIONS
// ============================================================

export const AI_CONNECTION = {
    deleted: { key: "ai.connection.deleted", fallback: "AI connection deleted" },
    delete_error: { key: "ai.connection.delete_error", fallback: "Failed to delete AI connection" },
    default_set: { key: "ai.connection.default_set", fallback: "Default AI connection updated" },
    load_error: { key: "ai.connection.load_error", fallback: "Failed to load connections" },
    add_new: { key: "ai.connection.add_new", fallback: "Add New AI Connection" },
    no_connections: { key: "ai.connection.no_connections", fallback: "No AI connections saved yet." },
    add_first: { key: "ai.connection.add_first", fallback: "Add your first AI connection" },
    default_badge: { key: "ai.connection.default_badge", fallback: "Default" },
    shared_badge: { key: "ai.connection.shared_badge", fallback: "Shared" },
    by_label: { key: "ai.connection.by_label", fallback: "by" },
    unknown_user: { key: "ai.connection.unknown_user", fallback: "Unknown" },
    set_default: { key: "ai.connection.set_default", fallback: "Set as Default" },
    shared_readonly: { key: "ai.connection.shared_readonly", fallback: "Shared" },
    delete_title: { key: "ai.connection.delete_title", fallback: "Delete AI Connection" },
    delete_confirmation: { key: "ai.connection.delete_confirmation", fallback: "Are you sure you want to delete the connection" },
    delete_button: { key: "ai.connection.delete_button", fallback: "Delete" },
    load_providers_error: { key: "ai.connection.load_providers_error", fallback: "Failed to load providers" },
    models_synced: { key: "ai.connection.models_synced", fallback: "Models synced successfully" },
    models_sync_error: { key: "ai.connection.models_sync_error", fallback: "Failed to sync models" },
    select_provider_first: { key: "ai.connection.select_provider_first", fallback: "Please select a provider first" },
    metadata_loading: { key: "ai.connection.metadata_loading", fallback: "Provider information is still loading. Please wait." },
    add_success: { key: "ai.connection.add_success", fallback: "AI connection added successfully" },
    update_success: { key: "ai.connection.update_success", fallback: "AI connection updated successfully" },
    save_error: { key: "ai.connection.save_error", fallback: "Failed to save AI connection" },
    not_found: { key: "ai.connection.not_found", fallback: "Connection not found" },
    add_title: { key: "ai.connection.add_title", fallback: "Add New AI Connection" },
    edit_title: { key: "ai.connection.edit_title", fallback: "Edit AI Connection" },
    form_description: { key: "ai.connection.form_description", fallback: "Configure an AI provider connection." },
    name_label: { key: "ai.connection.name_label", fallback: "Connection Name" },
    name_placeholder: { key: "ai.connection.name_placeholder", fallback: "e.g., My AI connection" },
    provider_label: { key: "ai.connection.provider_label", fallback: "Provider" },
    select_provider: { key: "ai.connection.select_provider", fallback: "Choose the AI provider" },
    endpoint_label: { key: "ai.connection.endpoint_label", fallback: "Endpoint URL" },
    endpoint_hint: { key: "ai.connection.endpoint_hint", fallback: "Override the default API endpoint if needed." },
    api_key_label: { key: "ai.connection.api_key_label", fallback: "API Key" },
    api_key_hint: { key: "ai.connection.api_key_hint", fallback: "Your API key is encrypted before storage." },
    shared_label: { key: "ai.connection.shared_label", fallback: "Share with group" },
    shared_description: { key: "ai.connection.shared_description", fallback: "Make this connection available to other users in your group." },
    currently_shared: { key: "ai.connection.currently_shared", fallback: "✅ Currently shared with group" },
    currently_not_shared: { key: "ai.connection.currently_not_shared", fallback: "❌ Currently not shared" },
    test_button: { key: "ai.connection.test_button", fallback: "Test Connection" },
    models: { key: "ai.connection.models", fallback: "Available Models" },
} as const;

export const AI = {
    title: { key: "ai.title", fallback: "AI Settings" },
    default_hint: { key: "ai.default_hint", fallback: "The default connection is used as a fallback when an analysis recipe does not specify an AI provider." },
    test_error: { key: "ai.test_error", fallback: "Connection failed." },
    test_success: { key: "ai.test_success", fallback: "Connection successful!" },
    connection: AI_CONNECTION,
} as const;


// ============================================================
// SETTINGS MODULE EXPORTS (root-level, used by the sidebar)
// ============================================================

export const SETTINGS = {
    title: { key: "settings.title", fallback: "Settings" },
    profile: { title: { key: "settings.profile.title", fallback: "Preferences" } },
    database: { title: { key: "settings.database.title", fallback: "Database Connections" } },
    ai: { title: { key: "settings.ai.title", fallback: "AI Connections" } },
} as const;
