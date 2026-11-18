# src/routers/admin/translations.py
# ============================================================
# ADMIN ROUTER TRANSLATIONS
# All translation keys used by the admin router.
# ============================================================

from dataclasses import dataclass


@dataclass
class TranslationKey:
    """A translation key with an English fallback."""
    key: str
    fallback: str


ADMIN = {
    # Error messages
    "api.admin.insufficient_permissions": TranslationKey(
        "api.admin.insufficient_permissions",
        "Insufficient permissions for this action"
    ),
    "api.admin.only_full_admin": TranslationKey(
        "api.admin.only_full_admin",
        "Only Full Admins can perform this action"
    ),
    "api.admin.user_not_found": TranslationKey(
        "api.admin.user_not_found",
        "User not found"
    ),
    "api.admin.cannot_delete_self": TranslationKey(
        "api.admin.cannot_delete_self",
        "Cannot delete your own account"
    ),
    "admin.group_not_found": TranslationKey(
        "admin.group_not_found",
        "Group not found"
    ),
    "api.admin.invalid_group_id": TranslationKey(
        "api.admin.invalid_group_id",
        "Invalid group_id. Must be 00-99"
    ),
    "api.admin.description_required": TranslationKey(
        "api.admin.description_required",
        "Description cannot be empty"
    ),
    "api.admin.provider_not_found": TranslationKey(
        "api.admin.provider_not_found",
        "Provider not found"
    ),
    "api.admin.missing_fields": TranslationKey(
        "api.admin.missing_fields",
        "Missing required fields"
    ),
    "api.admin.invalid_email": TranslationKey(
        "api.admin.invalid_email",
        "Invalid email format"
    ),
    "api.admin.email_exists": TranslationKey(
        "api.admin.email_exists",
        "Email already exists"
    ),
    "api.admin.settings_not_found": TranslationKey(
        "api.admin.settings_not_found",
        "Global settings not found"
    ),
    "api.admin.create_user_error": TranslationKey(
        "api.admin.create_user_error",
        "Failed to create user"
    ),
    "api.admin.slug_exists": TranslationKey(
        "api.admin.slug_exists",
        "Slug already exists"
    ),
    "api.admin.instance_exists": TranslationKey(
        "api.admin.instance_exists",
        "Cannot delete type because it has {count} associated instance(s)."
    ),
    "api.admin.instance_in_use": TranslationKey(
        "api.admin.instance_in_use",
        "Cannot delete type because it has associated instances."
    ),
    "api.admin.missing_user_id": TranslationKey(
        "api.admin.missing_user_id",
        "Missing userId"
    ),
    "api.admin.no_fields": TranslationKey(
        "api.admin.no_fields",
        "No valid fields to update"
    ),
    "api.admin.update_error": TranslationKey(
        "api.admin.update_error",
        "Failed to update user"
    ),
    "api.admin.delete_error": TranslationKey(
        "api.admin.delete_error",
        "Failed to delete user"
    ),
    "admin.users_load_error": TranslationKey(
        "admin.users_load_error",
        "Failed to load users"
    ),
    "api.admin.users_load_error": TranslationKey(
        "api.admin.users_load_error",
        "Failed to load users"
    ),
    "api.admin.user_load_error": TranslationKey(
        "api.admin.user_load_error",
        "Failed to load user"
    ),
    "api.admin.invalid_upload_size": TranslationKey(
        "api.admin.invalid_upload_size",
        "maxUploadSizeMB must be a non-negative integer (0 for unlimited)."
    ),
    "api.admin.invalid_upload_count": TranslationKey(
        "api.admin.invalid_upload_count",
        "maxUploadCount must be a non-negative integer (0 for unlimited)."
    ),
    "api.admin.groups_load_error": TranslationKey(
        "api.admin.groups_load_error",
        "Failed to load groups"
    ),
    "api.admin.groups_stats_error": TranslationKey(
        "api.admin.groups_stats_error",
        "Failed to load group statistics"
    ),
    "api.admin.group_users_load_error": TranslationKey(
        "api.admin.group_users_load_error",
        "Failed to load group users"
    ),
    "api.admin.no_group": TranslationKey(
        "api.admin.no_group",
        "User has no group assigned"
    ),
    "api.auth.unauthorized": TranslationKey(
        "api.auth.unauthorized",
        "Unauthorized"
    ),
    "api.admin.example_blocked": TranslationKey(
        "api.admin.example_blocked",
        "Example users cannot perform admin actions"
    ),
    "api.admin.cannot_promote_example": TranslationKey(
        "api.admin.cannot_promote_example",
        "Cannot promote an Example User"
    ),
    "api.admin.already_group_admin": TranslationKey(
        "api.admin.already_group_admin",
        "User is already a Group Admin"
    ),
    "api.admin.already_full_admin": TranslationKey(
        "api.admin.already_full_admin",
        "User is already a Full Admin"
    ),
    "api.admin.cannot_demote_self": TranslationKey(
        "api.admin.cannot_demote_self",
        "You cannot demote yourself"
    ),
    "api.admin.cannot_demote_full_admin": TranslationKey(
        "api.admin.cannot_demote_full_admin",
        "Cannot demote a Full Admin"
    ),
    "api.admin.not_group_admin": TranslationKey(
        "api.admin.not_group_admin",
        "User is not a Group Admin"
    ),
    "api.admin.promote_error": TranslationKey(
        "api.admin.promote_error",
        "Failed to promote user"
    ),
    "api.admin.demote_error": TranslationKey(
        "api.admin.demote_error",
        "Failed to demote user"
    ),
    "api.admin.providers_load_error": TranslationKey(
        "api.admin.providers_load_error",
        "Failed to load providers"
    ),
    "api.admin.provider_update_error": TranslationKey(
        "api.admin.provider_update_error",
        "Failed to update provider"
    ),
    "api.admin.provider_delete_error": TranslationKey(
        "api.admin.provider_delete_error",
        "Failed to delete provider"
    ),
    "api.admin.missing_id": TranslationKey(
        "api.admin.missing_id",
        "Missing id"
    ),
    "api.admin.models_load_error": TranslationKey(
        "api.admin.models_load_error",
        "Failed to load models"
    ),
    "api.admin.model_update_error": TranslationKey(
        "api.admin.model_update_error",
        "Failed to update model"
    ),
    "api.admin.model_not_found": TranslationKey(
        "api.admin.model_not_found",
        "Model not found"
    ),
    "api.admin.missing_model_id": TranslationKey(
        "api.admin.missing_model_id",
        "Missing model id"
    ),
    "api.admin.viz_types_load_error": TranslationKey(
        "api.admin.viz_types_load_error",
        "Failed to load visualization types"
    ),
    "api.admin.viz_type_create_error": TranslationKey(
        "api.admin.viz_type_create_error",
        "Failed to create visualization type"
    ),
    "api.admin.viz_type_update_error": TranslationKey(
        "api.admin.viz_type_update_error",
        "Failed to update visualization type"
    ),
    "api.admin.viz_type_delete_error": TranslationKey(
        "api.admin.viz_type_delete_error",
        "Failed to delete visualization type"
    ),
    "api.admin.viz_type_not_found": TranslationKey(
        "api.admin.viz_type_not_found",
        "Visualization type not found"
    ),
    "api.admin.invalid_id": TranslationKey(
        "api.admin.invalid_id",
        "Invalid id"
    ),
    "api.admin.invalid_viz_type_field": TranslationKey(
        "api.admin.invalid_viz_type_field",
        "Invalid visualization type field value"
    ),
    "api.admin.missing_group_id": TranslationKey(
        "api.admin.missing_group_id",
        "Missing group ID"
    ),
    "api.admin.settings_view_forbidden": TranslationKey(
        "api.admin.settings_view_forbidden",
        "Only Full Admins can view global settings"
    ),
    "api.admin.settings_modify_forbidden": TranslationKey(
        "api.admin.settings_modify_forbidden",
        "Only Full Admins can modify global settings"
    ),
    "api.admin.settings_invalid_max_registrations": TranslationKey(
        "api.admin.settings_invalid_max_registrations",
        "Max registrations must be a positive number or unlimited"
    ),
    "api.admin.settings_invalid_email_timeout": TranslationKey(
        "api.admin.settings_invalid_email_timeout",
        "Email verification timeout must be a positive number (hours)"
    ),
    "api.admin.settings_invalid_email_sender": TranslationKey(
        "api.admin.settings_invalid_email_sender",
        "Invalid sender email address format"
    ),
    "api.admin.settings_invalid_public_url": TranslationKey(
        "api.admin.settings_invalid_public_url",
        "Invalid public URL format"
    ),
    "api.admin.settings_invalid_grace_period": TranslationKey(
        "api.admin.settings_invalid_grace_period",
        "Registration grace period must be a positive number (hours)"
    ),
    "api.admin.settings_invalid_upload_size": TranslationKey(
        "api.admin.settings_invalid_upload_size",
        "Default max upload size must be a non-negative integer (0 for unlimited)."
    ),
    "api.admin.settings_invalid_upload_count": TranslationKey(
        "api.admin.settings_invalid_upload_count",
        "Default max upload count must be a non-negative integer (0 for unlimited)."
    ),
    "api.admin.settings_invalid_platform_upload_size": TranslationKey(
        "api.admin.settings_invalid_platform_upload_size",
        "Platform max upload size must be a non-negative integer (0 for unlimited)."
    ),
    "api.admin.settings_demo_mode_requires_licence": TranslationKey(
        "api.admin.settings_demo_mode_requires_licence",
        "Demo mode cannot be disabled without a valid licence."
    ),
    "api.admin.settings_demo_upload_size_limit": TranslationKey(
        "api.admin.settings_demo_upload_size_limit",
        "In demo mode, the default max upload size must be between 1 and 5 MB."
    ),
    "api.admin.settings_demo_upload_count_limit": TranslationKey(
        "api.admin.settings_demo_upload_count_limit",
        "In demo mode, the default max upload count must be between 1 and 5."
    ),
    "api.admin.users_demo_upload_size_limit": TranslationKey(
        "api.admin.users_demo_upload_size_limit",
        "In demo mode, the max upload size for a user must be between 1 and 5 MB."
    ),
    "api.admin.users_demo_upload_count_limit": TranslationKey(
        "api.admin.users_demo_upload_count_limit",
        "In demo mode, the max upload count for a user must be between 1 and 5."
    ),
    "api.admin.settings_invalid_slow_threshold": TranslationKey(
        "api.admin.settings_invalid_slow_threshold",
        "The slow-model limit must be a whole number of seconds, at least 1"
    ),
    "api.admin.settings_invalid_temperature": TranslationKey(
        "api.admin.settings_invalid_temperature",
        "Temperature must be a number between 0 and 2"
    ),
    "api.admin.settings_invalid_max_tokens": TranslationKey(
        "api.admin.settings_invalid_max_tokens",
        "The output limit must be a whole number of tokens, at least 1"
    ),
    "api.admin.settings_invalid_ai_timeout": TranslationKey(
        "api.admin.settings_invalid_ai_timeout",
        "The AI time limit must be a whole number of seconds, at least 1"
    ),
    # The two connection-timeout defaults (plan workbench-AI-timeout-policy-plan.html,
    # Item 2). Separate keys from settings_invalid_ai_timeout above, because that one
    # carries no ceiling: a per-call time limit may be raised to 1200 s, while a
    # connect budget past 60 s is never useful and the message says so.
    #
    # Named "test timeout", not "model test timeout": the column beside it is
    # defaultModelTestSeconds, the slow-model THRESHOLD — the number a recorded
    # duration is compared against. Reusing "model test" for this one would invite
    # exactly the conflation that field already causes.
    # Plan Item 4b: a field the other endpoint owns, and the reset's own failure.
    "api.admin.field_not_owned": TranslationKey(
        "api.admin.field_not_owned",
        "This field is not set on this page. {endpoint}. Offending: {fields}"
    ),
    "api.admin.tuning_reset_error": TranslationKey(
        "api.admin.tuning_reset_error",
        "The AI tuning defaults could not be reset"
    ),
    "api.admin.settings_invalid_connect_timeout": TranslationKey(
        "api.admin.settings_invalid_connect_timeout",
        "The default connect timeout must be a whole number of seconds, at least "
        "1 and at most {ceiling}"
    ),
    "api.admin.settings_invalid_probe_timeout": TranslationKey(
        "api.admin.settings_invalid_probe_timeout",
        "The default test timeout must be a whole number of seconds, at least 1 "
        "and at most {ceiling}"
    ),
    "api.admin.settings_invalid_registration_mode": TranslationKey(
        "api.admin.settings_invalid_registration_mode",
        "Registration mode must be one of 0, 1, 2, or 4."
    ),
    "api.admin.settings_load_error": TranslationKey(
        "api.admin.settings_load_error",
        "Failed to load global settings"
    ),
    "api.admin.settings_save_error": TranslationKey(
        "api.admin.settings_save_error",
        "Failed to save global settings"
    ),
    "api.global_settings_load_error": TranslationKey(
        "api.global_settings_load_error",
        "Internal server error"
    ),
    # Item 36 — promote/demote success templates. The provider-models fetch codes
    # that sat here were deleted with the router in Item 32 of the models-testing
    # plan; that path no longer exists, so its messages had no caller.
    "api.admin.promote_success": TranslationKey(
        "api.admin.promote_success",
        "User {name} has been promoted to Group Admin"
    ),
    "api.admin.demote_success": TranslationKey(
        "api.admin.demote_success",
        "User {name} has been demoted from Group Admin"
    ),
    "api.admin.invalid_admin_password": TranslationKey(
        "api.admin.invalid_admin_password",
        "Admin password is incorrect"
    ),
    "api.admin.example_user_password_blocked": TranslationKey(
        "api.admin.example_user_password_blocked",
        "Example users' passwords cannot be set by an administrator"
    ),
}