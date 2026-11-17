// app/admin/translations.ts
// ============================================================
// ADMIN MODULE TRANSLATIONS
// All translation keys used by admin pages.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

// ============================================================
// ADMIN USERS
// ============================================================

export const ADMIN_USERS = {
    load_error: { key: "admin.users.load_error", fallback: "Failed to load users" },
    update_error: { key: "admin.users.update_error", fallback: "Failed to update user" },
    update_success: { key: "admin.users.update_success", fallback: "User updated" },
    bcc_updated: { key: "admin.users.bcc_updated", fallback: "BCC registration setting updated" },
    verify_error: { key: "admin.users.verify_error", fallback: "Failed to verify user" },
    verify_success: { key: "admin.users.verify_success", fallback: "User marked as verified" },
    restore_error: { key: "admin.users.restore_error", fallback: "Failed to restore user" },
    restore_success: { key: "admin.users.restore_success", fallback: "User restored" },
    delete_error: { key: "admin.users.delete_error", fallback: "Failed to delete user" },
    delete_success: { key: "admin.users.delete_success", fallback: "User permanently deleted" },
    hard_delete_error: { key: "admin.users.hard_delete_error", fallback: "Failed to permanently delete user" },
    hard_delete_success: { key: "admin.users.hard_delete_success", fallback: "User permanently deleted" },
    resend_error: { key: "admin.users.resend_error", fallback: "Failed to send verification email" },
    resend_success: { key: "admin.users.resend_success", fallback: "Verification email sent to {email}" },
    title: { key: "admin.users.title", fallback: "User Management" },
    add_user: { key: "admin.users.add_user", fallback: "Add User" },
    no_name: { key: "admin.users.no_name", fallback: "No name" },
    created_label: { key: "admin.users.created_label", fallback: "Created" },
    admin_badge: { key: "admin.users.admin_badge", fallback: "Admin" },
    unverified_badge: { key: "admin.users.unverified_badge", fallback: "Unverified" },
    verified_badge: { key: "admin.users.verified_badge", fallback: "Verified" },
    more_button: { key: "admin.users.more_button", fallback: "More..." },
    verify_button: { key: "admin.users.verify_button", fallback: "Verify" },
    resend_button: { key: "admin.users.resend_button", fallback: "Resend Email" },
    bcc_label: { key: "admin.users.bcc_label", fallback: "BCC Registrations" },
    remove_admin: { key: "admin.users.remove_admin", fallback: "Remove Admin" },
    make_admin: { key: "admin.users.make_admin", fallback: "Make Admin" },
    delete_button: { key: "admin.users.delete_button", fallback: "Delete" },
    deleted_label: { key: "admin.users.deleted_label", fallback: "Deleted" },
    deleted_badge: { key: "admin.users.deleted_badge", fallback: "Soft-Deleted" },
    restore_button: { key: "admin.users.restore_button", fallback: "Restore" },
    hard_delete_button: { key: "admin.users.hard_delete_button", fallback: "Permanent Delete" },
    delete_title: { key: "admin.users.delete_title", fallback: "Delete User" },
    delete_confirmation: { key: "admin.users.delete_confirmation", fallback: 'Are you sure you want to permanently delete "{name}"? This action CANNOT be undone.' },
    hard_delete_title: { key: "admin.users.hard_delete_title", fallback: "Permanently Delete User" },
    hard_delete_confirmation: { key: "admin.users.hard_delete_confirmation", fallback: 'Are you sure you want to permanently delete "{name}"? This action CANNOT be undone.' },
    group_admin_badge: { key: "admin.users.group_admin_badge", fallback: "Group Admin" },
    example_user_badge: { key: "admin.users.example_user_badge", fallback: "Example User" },
    current_user_badge: { key: "admin.users.current_user_badge", fallback: "You" },
    active_users: { key: "admin.users.active_users", fallback: "Active Users" },
    soft_deleted_users: { key: "admin.users.soft_deleted_users", fallback: "Soft-Deleted Users" },
    unauthorized: { key: "admin.users.unauthorized", fallback: "Unauthorized" },
    forbidden: { key: "admin.users.forbidden", fallback: "Forbidden" },
    user_not_found: { key: "admin.users.user_not_found", fallback: "User not found" },
    delete_self_error: { key: "admin.users.delete_self_error", fallback: "Cannot delete your own account" },
} as const;

// ============================================================
// ADMIN USER DETAILS
// ============================================================

export const ADMIN_USER_DETAILS = {
    load_error: { key: "admin.user_details.load_error", fallback: "Failed to load user details" },
    save_success: { key: "admin.user_details.save_success", fallback: "User details updated" },
    save_error: { key: "admin.user_details.save_error", fallback: "Failed to update user" },
    not_found: { key: "admin.user_details.not_found", fallback: "User not found" },
    title: { key: "admin.user_details.title", fallback: "Administer User" },
    unnamed: { key: "admin.user_details.unnamed", fallback: "Unnamed User" },
    name_label: { key: "admin.user_details.name_label", fallback: "Name" },
    email_label: { key: "admin.user_details.email_label", fallback: "Email" },
    user_group: { key: "admin.user_details.user_group", fallback: "User Group" },
    select_group: { key: "admin.user_details.select_group", fallback: "Select group" },
    group_hint: { key: "admin.user_details.group_hint", fallback: "The user's group determines which shared resources they can access." },
    group_admin_label: { key: "admin.user_details.group_admin_label", fallback: "Group Admin" },
    group_admin_description: { key: "admin.user_details.group_admin_description", fallback: "User can manage other users within their group." },
    full_admin_note: { key: "admin.user_details.full_admin_note", fallback: "Full Admins have all Group Admin permissions by default." },
    email_notifications_label: { key: "admin.user_details.email_notifications_label", fallback: "Email Notifications" },
    email_notifications_description: { key: "admin.user_details.email_notifications_description", fallback: "Receive email updates about your account." },
    dark_mode_label: { key: "admin.user_details.dark_mode_label", fallback: "Dark Mode" },
    dark_mode_description: { key: "admin.user_details.dark_mode_description", fallback: "Toggle between light and dark theme." },
    language_label: { key: "admin.user_details.language_label", fallback: "Language" },
    language_select_placeholder: { key: "admin.user_details.language_select_placeholder", fallback: "Select language" },
    max_upload_size_label: { key: "admin.user_details.max_upload_size_label", fallback: "Max Upload Size" },
    max_upload_size_placeholder: { key: "admin.user_details.max_upload_size_placeholder", fallback: "Select size" },
    max_upload_size_hint: { key: "admin.user_details.max_upload_size_hint", fallback: "Maximum total storage per user (0 = unlimited)." },
    max_upload_count_label: { key: "admin.user_details.max_upload_count_label", fallback: "Max Upload Count" },
    max_upload_count_placeholder: { key: "admin.user_details.max_upload_count_placeholder", fallback: "Select count" },
    max_upload_count_hint: { key: "admin.user_details.max_upload_count_hint", fallback: "Maximum number of datasets per user (0 = unlimited)." },
} as const;

// ============================================================
// ADMIN — SET PASSWORD CARD
// ============================================================

// The card's own strings. The two password-field labels and the mismatch message
// are NOT declared here: "New Password", "Confirm New Password" and "New
// passwords do not match" already exist as profile.* keys, and the shared
// Translation table is keyed by the key string — a second key with the same
// English text would be drift (and would need translating again). Those three are
// imported from the profile module and used as they are.
export const ADMIN_SET_PASSWORD = {
    title: { key: "admin.set_password.title", fallback: "Set Password" },
    description: { key: "admin.set_password.description", fallback: "Set a new password for this user. Your own admin password is required to confirm the change." },
    admin_password: { key: "admin.set_password.admin_password", fallback: "Admin Password" },
    admin_password_required: { key: "admin.set_password.admin_password_required", fallback: "Admin password is required" },
    success: { key: "admin.set_password.success", fallback: "Password set successfully" },
    failed: { key: "admin.set_password.failed", fallback: "Failed to set password" },
} as const;

// ============================================================
// ADMIN GROUPS
// ============================================================

export const ADMIN_GROUPS = {
    readonly_badge: { key: "admin.groups.readonly_badge", fallback: "(read-only)" },
    load_error: { key: "admin.groups.load_error", fallback: "Failed to load groups" },
    load_success: { key: "admin.groups.load_success", fallback: "Groups loaded successfully" },
    description_required: { key: "admin.groups.description_required", fallback: "Description cannot be empty" },
    update_error: { key: "admin.groups.update_error", fallback: "Failed to update group" },
    update_success: { key: "admin.groups.update_success", fallback: "Group description updated" },
    promote_success: { key: "admin.groups.promote_success", fallback: "User promoted to Group Admin" },
    demote_success: { key: "admin.groups.demote_success", fallback: "User demoted from Group Admin" },
    readonly_title: { key: "admin.groups.readonly_title", fallback: "Group Management (Read-Only)" },
    title: { key: "admin.groups.title", fallback: "Group Management" },
    back_to_admin: { key: "admin.groups.back_to_admin", fallback: "Back to Admin" },
    readonly_message: { key: "admin.groups.readonly_message", fallback: "You are viewing this page in read-only mode. Example users cannot make changes." },
    select_group: { key: "admin.groups.select_group", fallback: "Select Group" },
    select_group_placeholder: { key: "admin.groups.select_group_placeholder", fallback: "Select a group" },
    group_description: { key: "admin.groups.group_description", fallback: "Group Description" },
    description_placeholder: { key: "admin.groups.description_placeholder", fallback: "Enter description" },
    users_in_group: { key: "admin.groups.users_in_group", fallback: "Users in Group" },
    no_users: { key: "admin.groups.no_users", fallback: "No users found in this group." },
    demote: { key: "admin.groups.demote", fallback: "Demote" },
    promote: { key: "admin.groups.promote", fallback: "Promote" },
    cannot_modify_self: { key: "admin.groups.cannot_modify_self", fallback: "Cannot modify your own account" },
    delete_title: { key: "admin.groups.delete_title", fallback: "Delete User" },
    delete_confirmation: { key: "admin.groups.delete_confirmation", fallback: 'Are you sure you want to delete {name}? This user will be soft-deleted and can be restored by a Full Admin.' },
    group_users_load_error: { key: "admin.groups.group_users_load_error", fallback: "Failed to load group users" },
    promote_error: { key: "admin.groups.promote_error", fallback: "Failed to promote user" },
    demote_error: { key: "admin.groups.demote_error", fallback: "Failed to demote user" },
    delete_error: { key: "admin.groups.delete_error", fallback: "Failed to delete user" },
} as const;

// ============================================================
// ADMIN MODELS
// ============================================================

export const ADMIN_MODELS = {
    load_models_error: { key: "admin.models.load_models_error", fallback: "Failed to load models" },
    toggle_error: { key: "admin.models.toggle_error", fallback: "Failed to update model" },
    update_success: { key: "admin.models.update_success", fallback: "Model updated" },
    update_error: { key: "admin.models.update_error", fallback: "Failed to update comment" },
    description: { key: "admin.models.description", fallback: "Every model the workbench knows about. Enabling a model affects every connection that serves it; the servers column shows which ones can reach it." },
    fetch_non_standard: { key: "admin.models.fetch_non_standard", fallback: "This provider does not expose a standard model-listing API. Add models manually in the admin panel." },
    fetch_auth_required: { key: "admin.models.fetch_auth_required", fallback: "This provider requires an API key to list models. Refresh from Settings → AI Connections instead." },
    no_models: { key: "admin.models.no_models", fallback: "No models yet. Discovery creates them from a connection." },
    comment_placeholder: { key: "admin.models.comment_placeholder", fallback: "Enter comment" },
    no_comment: { key: "admin.models.no_comment", fallback: "—" },
    edit_comment: { key: "admin.models.edit_comment", fallback: "Edit comment" },
    enabled: { key: "admin.models.enabled", fallback: "Enabled" },
    disabled: { key: "admin.models.disabled", fallback: "Disabled" },
    preferred: { key: "admin.models.preferred", fallback: "Preferred" },
    // Per-pair AI tuning (AI limits plan, Item 10). Flat keys under `models`, matching
    // every other declaration here — an `ai: { … }` sub-object would repeat the key's
    // own words in the property path, which the table-shape linter reports as R1/R3.
    // The three field LABELS and the temperature refusal are NOT declared here. They
    // already exist for the workbench-wide defaults on the limits page, and identical
    // fallback text under two keys is the duplicate the linter reports. This panel
    // imports those declarations instead — one string, one key, wherever it is shown.
    tuning_title: { key: "admin.models.tuning_title", fallback: "AI settings for this server" },
    tuning_loading: { key: "admin.models.tuning_loading", fallback: "Loading AI settings…" },
    tuning_hint: { key: "admin.models.tuning_hint", fallback: "These values apply wherever this model is used on this connection. Blank means it inherits the workbench default." },
    tuning_temperature_hint: { key: "admin.models.tuning_temperature_hint", fallback: "Lower values give more repeatable answers; higher values give more varied ones." },
    tuning_timeout_hint: { key: "admin.models.tuning_timeout_hint", fallback: "Seconds one AI request may run. A local CPU model can need several minutes." },
    tuning_inherited: { key: "admin.models.tuning_inherited", fallback: "inherited" },
    tuning_inherited_title: { key: "admin.models.tuning_inherited_title", fallback: "Blank inherits the workbench default" },
    tuning_saved: { key: "admin.models.tuning_saved", fallback: "AI settings saved" },
    // No client-side validation keys here. The ENDPOINT validates and returns
    // `api.user.tuning_invalid_*`, whose translated message the dialog renders via
    // getErrorMessageFromData. Declaring frontend copies produced two keys that
    // nothing referenced — the server's message is the one a user sees.
    tuning_load_error: { key: "admin.models.tuning_load_error", fallback: "Could not load the AI settings" },
    tuning_save_error: { key: "admin.models.tuning_save_error", fallback: "Could not save the AI settings" },
    not_preferred: { key: "admin.models.not_preferred", fallback: "Not Preferred" },

    // Item 18: the list over LLMModel. Provider stops being the axis, so the keys
    // that named a provider selection are gone with the control they labelled.
    search_placeholder: { key: "admin.models.search_placeholder", fallback: "Search model name" },
    // One label for the three filter controls. The options inside them reuse
    // `enabled`, `disabled` and the test/state keys that already exist — a second
    // declaration of "Enabled" is the duplicate the linter reports, and it is the
    // same word either way.
    filter_state: { key: "admin.models.filter_state", fallback: "State" },
    filter_any: { key: "admin.models.filter_any", fallback: "Any state" },
    filter_test: { key: "admin.models.filter_test", fallback: "Capability test" },
    filter_result: { key: "admin.models.filter_result", fallback: "Result" },
    filter_clear: { key: "admin.models.filter_clear", fallback: "Clear filters" },
    servers_title: { key: "admin.models.servers_title", fallback: "Reachable from" },
    no_servers: { key: "admin.models.no_servers", fallback: "No connection serves this model yet" },
    no_matches: { key: "admin.models.no_matches", fallback: "No models match these filters." },
    model_count: { key: "admin.models.model_count", fallback: "{count} models" },
} as const;

// ============================================================
// ADMIN PROVIDERS
// ============================================================

export const ADMIN_PROVIDERS = {
    fetch_error: { key: "admin.providers.fetch_error", fallback: "Failed to load providers" },
    toggle_error: { key: "admin.providers.toggle_error", fallback: "Failed to update provider" },
    update_success: { key: "admin.providers.update_success", fallback: "Provider updated" },
    delete_error: { key: "admin.providers.delete_error", fallback: "Failed to delete provider" },
    delete_success: { key: "admin.providers.delete_success", fallback: "Provider deleted" },
    title: { key: "admin.providers.title", fallback: "AI Providers" },
    description: { key: "admin.providers.description", fallback: "Enable or disable AI providers. Disabled providers will not appear in user connection forms." },
    list_title: { key: "admin.providers.list_title", fallback: "All Providers" },
    code_label: { key: "admin.providers.code_label", fallback: "Code" },
    local: { key: "admin.providers.local", fallback: "Local" },
    requires_api_key: { key: "admin.providers.requires_api_key", fallback: "requires API key" },
    no_api_key: { key: "admin.providers.no_api_key", fallback: "no API key required" },
    enabled: { key: "admin.providers.enabled", fallback: "Enabled" },
    disabled: { key: "admin.providers.disabled", fallback: "Disabled" },
    delete_provider: { key: "admin.providers.delete_provider", fallback: "Delete provider" },
    delete_title: { key: "admin.providers.delete_title", fallback: "Delete Provider" },
    delete_confirmation: { key: "admin.providers.delete_confirmation", fallback: 'Are you sure you want to delete the provider "{name}"? This will also remove all associated models and cannot be undone.' },
    delete_button: { key: "admin.providers.delete_button", fallback: "Delete" },
} as const;

// ============================================================
// ADMIN VISUALIZATION TYPES
// ============================================================

export const ADMIN_VIZ_TYPES = {
    fetch_error: { key: "admin.visualization_types.fetch_error", fallback: "Failed to load visualization types" },
    delete_error: { key: "admin.visualization_types.delete_error", fallback: "Failed to delete" },
    delete_success: { key: "admin.visualization_types.delete_success", fallback: "Visualization type deleted" },
    toggle_error: { key: "admin.visualization_types.toggle_error", fallback: "Failed to update" },
    update_success: { key: "admin.visualization_types.update_success", fallback: "Visualization type updated" },
    invalid_json: { key: "admin.visualization_types.invalid_json", fallback: "Invalid JSON in one of the schema fields" },
    save_error: { key: "admin.visualization_types.save_error", fallback: "Failed to save" },
    create_success: { key: "admin.visualization_types.create_success", fallback: "Visualization type created" },
    title: { key: "admin.visualization_types.title", fallback: "Visualization Types" },
    add_button: { key: "admin.visualization_types.add_button", fallback: "Add New Type" },
    edit_title: { key: "admin.visualization_types.edit_title", fallback: "Edit Visualization Type" },
    add_title: { key: "admin.visualization_types.add_title", fallback: "Add Visualization Type" },
    name: { key: "admin.visualization_types.name", fallback: "Name" },
    slug: { key: "admin.visualization_types.slug", fallback: "Slug" },
    description: { key: "admin.visualization_types.description", fallback: "Description" },
    renderer: { key: "admin.visualization_types.renderer", fallback: "Renderer" },
    input_schema: { key: "admin.visualization_types.input_schema", fallback: "Input Schema (JSON)" },
    parameter_schema: { key: "admin.visualization_types.parameter_schema", fallback: "Parameter Schema (JSON)" },
    default_parameters: { key: "admin.visualization_types.default_parameters", fallback: "Default Parameters (JSON)" },
    enabled: { key: "admin.visualization_types.enabled", fallback: "Enabled" },
    list_title: { key: "admin.visualization_types.list_title", fallback: "All Visualization Types" },
    no_types: { key: "admin.visualization_types.no_types", fallback: "No visualization types defined yet." },
    slug_label: { key: "admin.visualization_types.slug_label", fallback: "Slug" },
    renderer_label: { key: "admin.visualization_types.renderer_label", fallback: "Renderer" },
    renderer_client: { key: "admin.visualization_types.renderer_client", fallback: "Client" },
    renderer_server: { key: "admin.visualization_types.renderer_server", fallback: "Server" },
    disabled: { key: "admin.visualization_types.disabled", fallback: "Disabled" },
    edit: { key: "admin.visualization_types.edit", fallback: "Edit" },
    delete: { key: "admin.visualization_types.delete", fallback: "Delete" },
    delete_title: { key: "admin.visualization_types.delete_title", fallback: "Delete Visualization Type" },
    delete_confirmation: { key: "admin.visualization_types.delete_confirmation", fallback: 'Are you sure you want to delete the type "{name}"? This will also remove all associated instances and cannot be undone.' },
    delete_button: { key: "admin.visualization_types.delete_button", fallback: "Delete" },
} as const;

// ============================================================
// ADMIN ROOT
// ============================================================

// ============================================================
// ADMIN SETTINGS (setup pages — coded error envelope)
// ============================================================

export const ADMIN_SETTINGS = {
    view_forbidden: { key: "api.admin.settings_view_forbidden", fallback: "Only Full Admins can view global settings" },
    modify_forbidden: { key: "api.admin.settings_modify_forbidden", fallback: "Only Full Admins can modify global settings" },
    invalid_max_registrations: { key: "api.admin.settings_invalid_max_registrations", fallback: "Max registrations must be a positive number or unlimited" },
    invalid_email_timeout: { key: "api.admin.settings_invalid_email_timeout", fallback: "Email verification timeout must be a positive number (hours)" },
    invalid_email_sender: { key: "api.admin.settings_invalid_email_sender", fallback: "Invalid sender email address format" },
    invalid_public_url: { key: "api.admin.settings_invalid_public_url", fallback: "Invalid public URL format" },
    invalid_grace_period: { key: "api.admin.settings_invalid_grace_period", fallback: "Registration grace period must be a positive number (hours)" },
    invalid_upload_size: { key: "api.admin.settings_invalid_upload_size", fallback: "Default max upload size must be a non-negative integer (0 for unlimited)." },
    invalid_upload_count: { key: "api.admin.settings_invalid_upload_count", fallback: "Default max upload count must be a non-negative integer (0 for unlimited)." },
    load_error: { key: "api.admin.settings_load_error", fallback: "Failed to load global settings" },
    save_error: { key: "api.admin.settings_save_error", fallback: "Failed to save global settings" },
} as const;

export const ADMIN = {
    title: { key: "admin.title", fallback: "Admin Panel" },
    users: ADMIN_USERS,
    user_details: ADMIN_USER_DETAILS,
    set_password: ADMIN_SET_PASSWORD,
    groups: ADMIN_GROUPS,
    models: ADMIN_MODELS,
    providers: ADMIN_PROVIDERS,
    visualization_types: ADMIN_VIZ_TYPES,
    settings: ADMIN_SETTINGS,
} as const;