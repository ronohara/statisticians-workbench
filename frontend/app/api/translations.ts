// app/api/translations.ts
// ============================================================
// API TRANSLATIONS
// Translation keys for API error messages used across frontend API routes.
// These keys are used when API routes return error responses.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

// ============================================================
// AUTH API
// ============================================================

export const API_AUTH = {
    unauthorized: { key: "api.auth.unauthorized", fallback: "Unauthorized" },
    invalid_credentials: { key: "api.auth.invalid_credentials", fallback: "Invalid credentials" },
    email_not_verified: { key: "api.auth.email_not_verified", fallback: "Email not verified. Please check your inbox and SPAM folder." },
    account_deleted: { key: "api.auth.account_deleted", fallback: "This account has been deleted." },
    example_user_blocked: { key: "api.auth.example_user_blocked", fallback: "Password changes are disabled for example users" },
    example_user_reset_blocked: { key: "api.auth.example_user_reset_blocked", fallback: "Password reset is disabled for example users" },
    example_user_forgot_blocked: { key: "api.auth.example_user_forgot_blocked", fallback: "Password reset is disabled for example users" },
    example_user_register_blocked: { key: "api.auth.example_user_register_blocked", fallback: "Example users cannot create new accounts" },
    missing_fields: { key: "api.auth.missing_fields", fallback: "Missing fields" },
    password_validation_failed: { key: "api.auth.password_validation_failed", fallback: "Password validation failed" },
    invalid_token: { key: "api.auth.invalid_token", fallback: "Invalid or expired token" },
    token_expired: { key: "api.auth.token_expired", fallback: "Token has expired" },
    missing_email: { key: "api.auth.missing_email", fallback: "Email required" },
    user_not_found: { key: "api.auth.user_not_found", fallback: "User not found" },
    invalid_current_password: { key: "api.auth.invalid_current_password", fallback: "Current password is incorrect" },
    internal_error: { key: "api.auth.internal_error", fallback: "Internal server error" },
} as const;

// ============================================================
// ADMIN API
// ============================================================

export const API_ADMIN = {
    insufficient_permissions: { key: "api.admin.insufficient_permissions", fallback: "Insufficient permissions for this action" },
    only_full_admin: { key: "api.admin.only_full_admin", fallback: "Only Full Admins can perform this action" },
    user_not_found: { key: "api.admin.user_not_found", fallback: "User not found" },
    cannot_delete_self: { key: "api.admin.cannot_delete_self", fallback: "Cannot delete your own account" },
    group_not_found: { key: "api.admin.group_not_found", fallback: "Group not found" },
    invalid_group_id: { key: "api.admin.invalid_group_id", fallback: "Invalid group_id. Must be 00-99" },
    description_required: { key: "api.admin.description_required", fallback: "Description cannot be empty" },
    provider_not_found: { key: "api.admin.provider_not_found", fallback: "Provider not found" },
    missing_fields: { key: "api.admin.missing_fields", fallback: "Missing required fields" },
    slug_exists: { key: "api.admin.slug_exists", fallback: "Slug already exists" },
    instance_exists: { key: "api.admin.instance_exists", fallback: "Cannot delete type because it has {count} associated instance(s)." },
    missing_user_id: { key: "api.admin.missing_user_id", fallback: "Missing userId" },
    no_fields: { key: "api.admin.no_fields", fallback: "No valid fields to update" },
    update_error: { key: "api.admin.update_error", fallback: "Failed to update user" },
    delete_error: { key: "api.admin.delete_error", fallback: "Failed to delete user" },
    users_load_error: { key: "api.admin.users_load_error", fallback: "Failed to load users" },
    user_load_error: { key: "api.admin.user_load_error", fallback: "Failed to load user" },
    invalid_upload_size: { key: "api.admin.invalid_upload_size", fallback: "maxUploadSizeMB must be a non-negative integer (0 for unlimited)." },
    invalid_upload_count: { key: "api.admin.invalid_upload_count", fallback: "maxUploadCount must be a non-negative integer (0 for unlimited)." },
    groups_load_error: { key: "api.admin.groups_load_error", fallback: "Failed to load groups" },
    groups_stats_error: { key: "api.admin.groups_stats_error", fallback: "Failed to load group statistics" },
    group_users_load_error: { key: "api.admin.group_users_load_error", fallback: "Failed to load group users" },
    no_group: { key: "api.admin.no_group", fallback: "User has no group assigned" },
    example_blocked: { key: "api.admin.example_blocked", fallback: "Example users cannot perform admin actions" },
    cannot_promote_example: { key: "api.admin.cannot_promote_example", fallback: "Cannot promote an Example User" },
    already_group_admin: { key: "api.admin.already_group_admin", fallback: "User is already a Group Admin" },
    already_full_admin: { key: "api.admin.already_full_admin", fallback: "User is already a Full Admin" },
    cannot_demote_self: { key: "api.admin.cannot_demote_self", fallback: "You cannot demote yourself" },
    cannot_demote_full_admin: { key: "api.admin.cannot_demote_full_admin", fallback: "Cannot demote a Full Admin" },
    not_group_admin: { key: "api.admin.not_group_admin", fallback: "User is not a Group Admin" },
    promote_error: { key: "api.admin.promote_error", fallback: "Failed to promote user" },
    demote_error: { key: "api.admin.demote_error", fallback: "Failed to demote user" },
    providers_load_error: { key: "api.admin.providers_load_error", fallback: "Failed to load providers" },
    provider_update_error: { key: "api.admin.provider_update_error", fallback: "Failed to update provider" },
    provider_delete_error: { key: "api.admin.provider_delete_error", fallback: "Failed to delete provider" },
    missing_id: { key: "api.admin.missing_id", fallback: "Missing id" },
    missing_provider_code: { key: "api.admin.missing_provider_code", fallback: "Missing providerCode parameter" },
    models_load_error: { key: "api.admin.models_load_error", fallback: "Failed to load models" },
    model_update_error: { key: "api.admin.model_update_error", fallback: "Failed to update model" },
    missing_model_id: { key: "api.admin.missing_model_id", fallback: "Missing model id" },
    viz_types_load_error: { key: "api.admin.viz_types_load_error", fallback: "Failed to load visualization types" },
    viz_type_create_error: { key: "api.admin.viz_type_create_error", fallback: "Failed to create visualization type" },
    viz_type_update_error: { key: "api.admin.viz_type_update_error", fallback: "Failed to update visualization type" },
    viz_type_delete_error: { key: "api.admin.viz_type_delete_error", fallback: "Failed to delete visualization type" },
    invalid_id: { key: "api.admin.invalid_id", fallback: "Invalid id" },
    missing_group_id: { key: "api.admin.missing_group_id", fallback: "Missing group ID" },
} as const;

// ============================================================
// DATASETS API
// ============================================================

export const API_DATASETS = {
    proxy_error: { key: "api.datasets.proxy_error", fallback: "Internal server error" },
    example_blocked: { key: "api.datasets.example_blocked", fallback: "Example users cannot create datasets" },
    update_blocked: { key: "api.datasets.update_blocked", fallback: "Example users cannot update datasets" },
    delete_blocked: { key: "api.datasets.delete_blocked", fallback: "Example users cannot delete datasets" },
} as const;

// ============================================================
// RECIPES API
// ============================================================

export const API_RECIPES = {
    not_found: { key: "api.recipes.not_found", fallback: "Recipe not found" },
    not_owned: { key: "api.recipes.not_owned", fallback: "Recipe not found or not owned" },
    name_required: { key: "api.recipes.name_required", fallback: "Name and stages are required" },
    dataset_required: { key: "api.recipes.dataset_required", fallback: "datasetId is required" },
    load_error: { key: "api.recipes.load_error", fallback: "Failed to load recipes" },
    create_error: { key: "api.recipes.create_error", fallback: "Failed to create recipe" },
    delete_error: { key: "api.recipes.delete_error", fallback: "Failed to delete recipe" },
    update_error: { key: "api.recipes.update_error", fallback: "Failed to update recipe" },
    missing_id: { key: "api.recipes.missing_id", fallback: "Recipe ID required" },
    dataset_not_found: { key: "api.recipes.dataset_not_found", fallback: "Dataset not found" },
    execute_error: { key: "api.recipes.execute_error", fallback: "Failed to execute recipe" },
    executions_load_error: { key: "api.recipes.executions_load_error", fallback: "Failed to load executions" },
    execution_not_found: { key: "api.recipes.execution_not_found", fallback: "Execution not found" },
    execution_load_error: { key: "api.recipes.execution_load_error", fallback: "Failed to load execution" },
} as const;

// ============================================================
// USER API
// ============================================================

export const API_USER = {
    example_blocked: { key: "api.user.example_blocked", fallback: "Example users cannot perform this action" },
    connection_not_found: { key: "api.user.connection_not_found", fallback: "Connection not found" },
    connection_name_exists: { key: "api.user.connection_name_exists", fallback: "A connection with this name already exists" },
    provider_not_found: { key: "api.user.provider_not_found", fallback: "Provider \"{provider}\" not found" },
    api_key_required: { key: "api.user.api_key_required", fallback: "API key is required for this provider" },
    missing_fields: { key: "api.user.missing_fields", fallback: "Missing required fields" },
    internal_error: { key: "api.user.internal_error", fallback: "Internal server error" },
    user_not_found: { key: "api.user.user_not_found", fallback: "User not found" },
} as const;

// ============================================================
// SETTINGS API
// ============================================================

export const API_SETTINGS = {
    user_not_found: { key: "api.settings.user_not_found", fallback: "User not found" },
    save_failed: { key: "api.settings.save_failed", fallback: "Failed to save settings" },
    load_failed: { key: "api.settings.load_failed", fallback: "Failed to load settings" },
    global_settings_load_error: { key: "api.global_settings_load_error", fallback: "Internal server error" },
} as const;

// ============================================================
// PROFILE API
// ============================================================

export const API_PROFILE = {
    name_required: { key: "api.profile.name_required", fallback: "Name is required" },
    update_failed: { key: "api.profile.update_failed", fallback: "Failed to update profile" },
} as const;

// ============================================================
// REGISTER API
// ============================================================

export const API_REGISTER = {
    email_exists: { key: "api.register.email_exists", fallback: "Email already exists" },
    invalid_email: { key: "api.register.invalid_email", fallback: "Invalid email format" },
    limit_reached: { key: "api.register.limit_reached", fallback: "Registration limit reached (maximum {max_reg} users)." },
    internal_error: { key: "api.register.internal_error", fallback: "Internal server error" },
    missing_fields: { key: "api.register.missing_fields", fallback: "Missing fields" },
    password_validation_failed: { key: "api.register.password_validation_failed", fallback: "Password validation failed" },
    settings_not_found: { key: "api.register.settings_not_found", fallback: "Global settings not found" },
} as const;

// ============================================================
// API ROOT
// ============================================================

export const API = {
    auth: API_AUTH,
    admin: API_ADMIN,
    datasets: API_DATASETS,
    recipes: API_RECIPES,
    user: API_USER,
    settings: API_SETTINGS,
    profile: API_PROFILE,
    register: API_REGISTER,
} as const;