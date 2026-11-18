# src/routers/common/translations.py
# ============================================================
# COMMON BACKEND TRANSLATIONS
# Keys used across multiple routers.
# ============================================================

from dataclasses import dataclass


@dataclass
class TranslationKey:
    """A translation key with an English fallback."""
    key: str
    fallback: str


# ============================================================
# COMMON UI
# ============================================================

COMMON = {
    "common.loading": TranslationKey("common.loading", "Loading..."),
    "common.save": TranslationKey("common.save", "Save"),
    "common.cancel": TranslationKey("common.cancel", "Cancel"),
    "common.delete": TranslationKey("common.delete", "Delete"),
    "common.edit": TranslationKey("common.edit", "Edit"),
    "common.back": TranslationKey("common.back", "Back"),
    "common.next": TranslationKey("common.next", "Next"),
    "common.saving": TranslationKey("common.saving", "Saving..."),
    "common.deleting": TranslationKey("common.deleting", "Deleting..."),
    "common.dismiss": TranslationKey("common.dismiss", "Dismiss"),
    "common.view": TranslationKey("common.view", "View"),
    "common.copy": TranslationKey("common.copy", "Copy"),
    "common.clear": TranslationKey("common.clear", "Clear"),
    "common.testing": TranslationKey("common.testing", "Testing..."),
    "common.sending": TranslationKey("common.sending", "Sending..."),
    "common.uploading": TranslationKey("common.uploading", "Uploading..."),
    "common.generating": TranslationKey("common.generating", "Generating..."),
    "common.verifying": TranslationKey("common.verifying", "Verifying..."),
    "common.restoring": TranslationKey("common.restoring", "Restoring..."),
    "common.cannot_undo": TranslationKey("common.cannot_undo", "This action cannot be undone."),
    "common.unknown": TranslationKey("common.unknown", "Unknown"),
}


# ============================================================
# DATABASE
# ============================================================

DATABASE = {
    "database.pool_not_initialized": TranslationKey("database.pool_not_initialized", "Database pool not initialized"),
    "database.insert_failed": TranslationKey("database.insert_failed", "Database error: {error}"),
    "database.decryption_failed": TranslationKey("database.decryption_failed", "Failed to decrypt connection password: {error}"),
    "database.connection_failed": TranslationKey("database.connection_failed", "Failed to connect to database: {error}"),
    "database.query_failed": TranslationKey("database.query_failed", "Database query failed: {error}"),
    "database.type_not_supported": TranslationKey("database.type_not_supported", "Database type '{type}' is not yet supported"),
    "database.feature_required": TranslationKey("database.feature_required", "This database type is not enabled by your licence."),
}


# ============================================================
# VALIDATION
# ============================================================

VALIDATION = {
    "validation.error": TranslationKey("validation.error", "Validation error: {count} issue(s) found"),
    "validation.password.min_length": TranslationKey("validation.password.min_length", "Password must be at least {min} characters long."),
    "validation.password.require_uppercase": TranslationKey("validation.password.require_uppercase", "Password must contain at least one uppercase letter."),
    "validation.password.require_lowercase": TranslationKey("validation.password.require_lowercase", "Password must contain at least one lowercase letter."),
    "validation.password.require_digit": TranslationKey("validation.password.require_digit", "Password must contain at least one digit."),
    "validation.password.require_special": TranslationKey("validation.password.require_special", "Password must contain at least one special character."),
    "validation.password.too_weak": TranslationKey("validation.password.too_weak", "Password is too weak. Please choose a stronger password."),
}


# ============================================================
# AUTH
# ============================================================

AUTH = {
    "auth.unauthorized": TranslationKey("auth.unauthorized", "Unauthorized"),
    "auth.invalid_credentials": TranslationKey("auth.invalid_credentials", "Invalid credentials"),
    "auth.invalid_token_missing_user_id": TranslationKey("auth.invalid_token_missing_user_id", "Invalid token: missing user id"),
    "auth.invalid_token_error": TranslationKey("auth.invalid_token_error", "Invalid token: {error}"),
    "auth.email_not_verified": TranslationKey("auth.email_not_verified", "Email not verified. Please check your inbox and SPAM folder."),
    "auth.account_deleted": TranslationKey("auth.account_deleted", "This account has been deleted."),
    "auth.example_user_blocked": TranslationKey("auth.example_user_blocked", "Password functions are disabled for example users"),
    "auth.example_user_reset_blocked": TranslationKey("auth.example_user_reset_blocked", "Password reset is disabled for example users"),
    "auth.example_user_forgot_blocked": TranslationKey("auth.example_user_forgot_blocked", "Password reset is disabled for example users"),
}


# ============================================================
# ADMIN
# ============================================================

ADMIN = {
    "admin.insufficient_permissions": TranslationKey("admin.insufficient_permissions", "Insufficient permissions for this action"),
    "admin.only_full_admin": TranslationKey("admin.only_full_admin", "Only Full Admins can perform this action"),
    "admin.user_not_found": TranslationKey("admin.user_not_found", "User not found"),
    "admin.cannot_delete_self": TranslationKey("admin.cannot_delete_self", "Cannot delete your own account"),
    "admin.group_not_found": TranslationKey("admin.group_not_found", "Group not found"),
    "admin.invalid_group_id": TranslationKey("admin.invalid_group_id", "Invalid group_id. Must be 00-99"),
    "admin.description_required": TranslationKey("admin.description_required", "Description cannot be empty"),
    "admin.provider_not_found": TranslationKey("admin.provider_not_found", "Provider not found"),
    "admin.missing_fields": TranslationKey("admin.missing_fields", "Missing required fields"),
    "admin.slug_exists": TranslationKey("admin.slug_exists", "Slug already exists"),
    "admin.missing_user_id": TranslationKey("admin.missing_user_id", "Missing userId"),
    "admin.no_fields": TranslationKey("admin.no_fields", "No valid fields to update"),
    "admin.update_error": TranslationKey("admin.update_error", "Failed to update user"),
    "admin.delete_error": TranslationKey("admin.delete_error", "Failed to delete user"),
    "admin.users_load_error": TranslationKey("admin.users_load_error", "Failed to load users"),
    "admin.user_load_error": TranslationKey("admin.user_load_error", "Failed to load user"),
    "admin.invalid_upload_size": TranslationKey("admin.invalid_upload_size", "maxUploadSizeMB must be a non-negative integer (0 for unlimited)."),
    "admin.invalid_upload_count": TranslationKey("admin.invalid_upload_count", "maxUploadCount must be a non-negative integer (0 for unlimited)."),
    "admin.groups_load_error": TranslationKey("admin.groups_load_error", "Failed to load groups"),
    "admin.groups_stats_error": TranslationKey("admin.groups_stats_error", "Failed to load group statistics"),
    "admin.group_users_load_error": TranslationKey("admin.group_users_load_error", "Failed to load group users"),
    "admin.no_group": TranslationKey("admin.no_group", "User has no group assigned"),
    "admin.example_blocked": TranslationKey("admin.example_blocked", "Example users cannot perform admin actions"),
    "admin.cannot_promote_example": TranslationKey("admin.cannot_promote_example", "Cannot promote an Example User"),
    "admin.already_group_admin": TranslationKey("admin.already_group_admin", "User is already a Group Admin"),
    "admin.already_full_admin": TranslationKey("admin.already_full_admin", "User is already a Full Admin"),
    "admin.cannot_demote_self": TranslationKey("admin.cannot_demote_self", "You cannot demote yourself"),
    "admin.cannot_demote_full_admin": TranslationKey("admin.cannot_demote_full_admin", "Cannot demote a Full Admin"),
    "admin.not_group_admin": TranslationKey("admin.not_group_admin", "User is not a Group Admin"),
    "admin.promote_error": TranslationKey("admin.promote_error", "Failed to promote user"),
    "admin.demote_error": TranslationKey("admin.demote_error", "Failed to demote user"),
    "admin.providers_load_error": TranslationKey("admin.providers_load_error", "Failed to load providers"),
    "admin.provider_update_error": TranslationKey("admin.provider_update_error", "Failed to update provider"),
    "admin.provider_delete_error": TranslationKey("admin.provider_delete_error", "Failed to delete provider"),
    "admin.missing_id": TranslationKey("admin.missing_id", "Missing id"),
    "admin.missing_provider_code": TranslationKey("admin.missing_provider_code", "Missing providerCode parameter"),
    "admin.models_load_error": TranslationKey("admin.models_load_error", "Failed to load models"),
    "admin.model_update_error": TranslationKey("admin.model_update_error", "Failed to update model"),
    "admin.missing_model_id": TranslationKey("admin.missing_model_id", "Missing model id"),
    "admin.viz_types_load_error": TranslationKey("admin.viz_types_load_error", "Failed to load visualization types"),
    "admin.viz_type_create_error": TranslationKey("admin.viz_type_create_error", "Failed to create visualization type"),
    "admin.viz_type_update_error": TranslationKey("admin.viz_type_update_error", "Failed to update visualization type"),
    "admin.viz_type_delete_error": TranslationKey("admin.viz_type_delete_error", "Failed to delete visualization type"),
    "admin.invalid_id": TranslationKey("admin.invalid_id", "Invalid id"),
    "admin.missing_group_id": TranslationKey("admin.missing_group_id", "Missing group ID"),
}


# ============================================================
# USER
# ============================================================

USER = {
    "user.example_blocked": TranslationKey("user.example_blocked", "Example users cannot perform this action"),
    "user.connection_not_found": TranslationKey("user.connection_not_found", "Connection not found"),
    "user.connection_name_exists": TranslationKey("user.connection_name_exists", "A connection with this name already exists"),
    "user.provider_not_found": TranslationKey("user.provider_not_found", "Provider not found"),
    "user.api_key_required": TranslationKey("user.api_key_required", "API key is required for this provider"),
    "user.missing_fields": TranslationKey("user.missing_fields", "Missing required fields"),
    "user.internal_error": TranslationKey("user.internal_error", "Internal server error"),
    "user.user_not_found": TranslationKey("user.user_not_found", "User not found"),
}


# ============================================================
# API
# ============================================================

API = {
    "auth": AUTH,
    "admin": ADMIN,
    "user": USER,
}


# ============================================================
# CHAT
# ============================================================

CHAT = {
    "chat.connection_not_found": TranslationKey("chat.connection_not_found", "AI connection not found or not accessible"),
    "chat.connection_error": TranslationKey("chat.connection_error", "Connection error: {error}"),
    "chat.timeout_out_of_range": TranslationKey(
        "chat.timeout_out_of_range",
        "The AI time limit must be between 1 and {max_seconds} seconds"
    ),
    "chat.ai_provider_error": TranslationKey("chat.ai_provider_error", "AI provider error: {error}"),
    "chat.ai_repeat_loop": TranslationKey("chat.ai_repeat_loop", "The AI model got stuck and couldn't finish responding. Please try again."),
    "chat.ai_service_failed": TranslationKey("chat.ai_service_failed", "The AI service failed to respond. Please try again."),
    "chat.ai_timeout": TranslationKey("chat.ai_timeout", "The AI model is taking too long to respond. Please try again."),
    "chat.send_failed": TranslationKey("chat.send_failed", "Failed to send message: {error}"),
    "chat.internal_error": TranslationKey("chat.internal_error", "Internal server error: {error}"),
    "chat.not_found": TranslationKey("chat.not_found", "Chat '{id}' not found"),
    "chat.not_found_or_not_owned": TranslationKey("chat.not_found_or_not_owned", "Chat '{id}' not found or you do not own it"),
    "chat.list_failed": TranslationKey("chat.list_failed", "Failed to list chats: {error}"),
    "chat.get_failed": TranslationKey("chat.get_failed", "Failed to get chat: {error}"),
    "chat.update_failed": TranslationKey("chat.update_failed", "Failed to update chat: {error}"),
    "chat.delete_failed": TranslationKey("chat.delete_failed", "Failed to delete chat: {error}"),
    "chat.generate_title_failed": TranslationKey("chat.generate_title_failed", "Failed to generate title: {error}"),
    "chat.title_updated": TranslationKey("chat.title_updated", "Chat title updated successfully"),
    "chat.deleted": TranslationKey("chat.deleted", "Chat '{id}' deleted successfully"),
    # ---- Inline keys migrated from router call sites (P2) ----
    "auth.invalid_token_error": TranslationKey(
        "auth.invalid_token_error",
        "Invalid token: {error}"
    ),
    "auth.invalid_token_missing_user_id": TranslationKey(
        "auth.invalid_token_missing_user_id",
        "Invalid token: missing user id"
    ),
    "database.pool_not_initialized": TranslationKey(
        "database.pool_not_initialized",
        "Database pool not initialized"
    ),
}


# ============================================================
# RECIPES
# ============================================================

# (No RECIPES dict here.) Every recipes.* key is declared once, as a flat
# TranslationKey in src/routers/recipes/translations.py — the module that uses
# it. This dict re-declared all 33 of them and nothing read it; both copies
# reached the Translation table, and the second import decided the row.




# ============================================================
# GROUPS
# ============================================================

GROUPS = {
    "groups.admin_required": TranslationKey("groups.admin_required", "Admin access required"),
    "groups.not_found": TranslationKey("groups.not_found", "Group '{id}' not found"),
    "groups.user_not_found": TranslationKey("groups.user_not_found", "User not found"),
    "groups.not_authorized": TranslationKey("groups.not_authorized", "Not authorized to view this user's group"),
    "groups.invalid_group_id": TranslationKey("groups.invalid_group_id", "Invalid user_group. Must be 00-99"),
    "groups.insufficient_permissions": TranslationKey("groups.insufficient_permissions", "Insufficient permissions to manage groups"),
    "groups.cannot_delete_self": TranslationKey("groups.cannot_delete_self", "Cannot delete your own account"),
    "groups.description_required": TranslationKey("groups.description_required", "Description cannot be empty"),
    "groups.update_failed": TranslationKey("groups.update_failed", "Failed to update group"),
    "groups.update_success": TranslationKey("groups.update_success", "Group '{id}' description updated"),
    "groups.user_updated": TranslationKey("groups.user_updated", "User's group updated successfully"),
    "groups.missing_id": TranslationKey("groups.missing_id", "Missing resource id"),
    "groups.resource_not_found": TranslationKey("groups.resource_not_found", "Resource not found"),
    # ---- Inline keys migrated from router call sites (P2) ----
    "error.groups.invalid_group_id": TranslationKey(
        "error.groups.invalid_group_id",
        "Invalid group_id. Must be 00-99"
    ),
    "auth.invalid_token_error": TranslationKey(
        "auth.invalid_token_error",
        "Invalid token: {error}"
    ),
    "auth.invalid_token_missing_user_id": TranslationKey(
        "auth.invalid_token_missing_user_id",
        "Invalid token: missing user id"
    ),
    "common.unknown": TranslationKey(
        "common.unknown",
        "Unknown"
    ),
}


# ============================================================
# STATISTICS
# ============================================================

STATISTICS = {
    "statistics.cache_not_found": TranslationKey("statistics.cache_not_found", "Cache key '{key}' not found"),
    "statistics.compute_failed": TranslationKey("statistics.compute_failed", "Failed to compute statistics: {error}"),
    "statistics.cache_cleared": TranslationKey("statistics.cache_cleared", "Cache key '{key}' cleared"),
    # ---- Inline keys migrated from router call sites (P2) ----
    "auth.invalid_token_error": TranslationKey(
        "auth.invalid_token_error",
        "Invalid token: {error}"
    ),
    "auth.invalid_token_missing_user_id": TranslationKey(
        "auth.invalid_token_missing_user_id",
        "Invalid token: missing user id"
    ),
}


# ============================================================
# SYSTEM
# ============================================================

SYSTEM = {
    "system.hello_world": TranslationKey("system.hello_world", "Hello, World!"),
    "system.cache_cleanup_completed": TranslationKey("system.cache_cleanup_completed", "Cache cleanup completed: {removed} entries removed"),
}


# ============================================================
# DATASETS
# ============================================================

DATASETS = {
    "datasets.not_found": TranslationKey("datasets.not_found", "Dataset '{id}' not found or not accessible"),
    "datasets.not_owner": TranslationKey("datasets.not_owner", "You can only edit your own datasets"),
}


# ============================================================
# VIRTUAL
# ============================================================

VIRTUAL = {
    "virtual.preview_failed": TranslationKey("virtual.preview_failed", "Preview failed: {error}"),
    "virtual.execute_failed": TranslationKey("virtual.execute_failed", "Execution failed: {error}"),
    "virtual.no_credentials_postgresql": TranslationKey("virtual.no_credentials_postgresql", "No credentials found for PostgreSQL connection {conn_id}"),
    "virtual.no_credentials_mysql": TranslationKey("virtual.no_credentials_mysql", "No credentials found for MySQL connection {conn_id}"),
}


# ============================================================
# SCHEMA
# ============================================================

SCHEMA = {
    "schema.dataset_id_required": TranslationKey("schema.dataset_id_required", "dataset_id is required for source_type=dataset"),
    "schema.connection_and_table_required": TranslationKey("schema.connection_and_table_required", "connection_id and table_name are required for PostgreSQL/MySQL sources"),
    "schema.unsupported_source_type": TranslationKey("schema.unsupported_source_type", "Unsupported source_type: {source_type}. Use dataset, postgresql, or mysql."),
    "schema.dataset_not_found": TranslationKey("schema.dataset_not_found", "Dataset not found or access denied"),
    "schema.no_table_name": TranslationKey("schema.no_table_name", "Dataset has no table name (not yet ingested)"),
    "schema.connection_not_found": TranslationKey("schema.connection_not_found", "Database connection not found or access denied"),
    "schema.introspect_postgresql_failed": TranslationKey("schema.introspect_postgresql_failed", "Failed to introspect PostgreSQL: {error}"),
    "schema.introspect_mysql_failed": TranslationKey("schema.introspect_mysql_failed", "Failed to introspect MySQL: {error}"),
}


# ============================================================
# VIRTUAL CHAT
# ============================================================

VIRTUAL_CHAT = {
    "virtual_chat.chat_session_not_found": TranslationKey("virtual_chat.chat_session_not_found", "Chat session not found"),
    "virtual_chat.connection_not_found": TranslationKey("virtual_chat.connection_not_found", "Database connection not found or access denied"),
    "virtual_chat.introspection_failed": TranslationKey("virtual_chat.introspection_failed", "Introspection failed: {error}"),
    "virtual_chat.llm_call_failed": TranslationKey("virtual_chat.llm_call_failed", "LLM call failed: {error}"),
    "virtual_chat.llm_returned_error": TranslationKey("virtual_chat.llm_returned_error", "LLM returned HTTP {status_code}"),
}


# ============================================================
# RAG
# ============================================================

RAG = {
    "rag.no_tables": TranslationKey("rag.no_tables", "No tables found in the schema to search."),
    "rag.no_matches": TranslationKey("rag.no_matches", "No matching text found in the database for your question. Try rephrasing or selecting a different data source."),
    "rag.no_ai_provider": TranslationKey("rag.no_ai_provider", "Found {count} matching records. (No AI provider configured for natural-language answers.)"),
    "rag.ai_provider_error": TranslationKey("rag.ai_provider_error", "AI provider error: {error}"),
}


# ============================================================
# AUDIO PRESETS
# ============================================================

AUDIO_PRESETS = {
    "audio_presets.invalid_chat_type": TranslationKey("audio_presets.invalid_chat_type", "Invalid chat type: {chat_type}. Must be one of: {valid_types}"),
}


# ============================================================
# EXECUTION
# ============================================================

# (No EXECUTION dict here.) Every execution.* key is declared once, as a flat
# TranslationKey in src/routers/recipes/translations.py — the module that uses
# it. This dict re-declared all five and nothing read it.




# ============================================================
# NOTEBOOKS STORAGE
# ============================================================

NOTEBOOKS_STORAGE = {
    "notebooks_storage.unsupported_storage_type": TranslationKey("notebooks_storage.unsupported_storage_type", "Unsupported storage type: {type}"),
    "notebooks_storage.no_connection_details": TranslationKey("notebooks_storage.no_connection_details", "No connection details provided"),
    "notebooks_storage.no_connection_details_short": TranslationKey("notebooks_storage.no_connection_details_short", "No connection details"),
    "notebooks_storage.failed_create_table": TranslationKey("notebooks_storage.failed_create_table", "Failed to create table {table}: {error}"),
    "notebooks_storage.failed_create_table_mssql": TranslationKey("notebooks_storage.failed_create_table_mssql", "Failed to create table: {error}"),
}

# ============================================================
# ACCESS ROUTER
# ============================================================

access_licence_required = TranslationKey("access.licence_required", "Access database connections require a corporate licence")
access_file_path_required = TranslationKey("access.file_path_required", "file_path is required")
access_name_and_path_required = TranslationKey("access.name_and_path_required", "name and file_path are required")
access_invalid_port = TranslationKey("access.invalid_port", "Port must be an integer")
access_connection_params_required = TranslationKey("access.connection_params_required", "host, port, user and password are required")
access_encryption_error = TranslationKey("access.encryption_error", "Encryption error: {error}")
access_db_pool_not_initialized = TranslationKey("access.db_pool_not_initialized", "Database pool not initialized")
access_connection_exists = TranslationKey("access.connection_exists", "Connection '{name}' already exists")
access_connection_saved = TranslationKey("access.connection_saved", "Connection saved")
access_connection_not_found = TranslationKey("access.connection_not_found", "Connection not found")
access_connection_deleted = TranslationKey("access.connection_deleted", "Connection deleted")
access_connected_in_ms = TranslationKey("access.connected_in_ms", "Connected in {elapsed}ms")
access_connection_failed = TranslationKey("access.connection_failed", "Connection failed")
access_connection_failed_detail = TranslationKey("access.connection_failed_detail", "Connection failed: {detail}")
access_connection_unavailable = TranslationKey("access.connection_unavailable", "Could not connect to the Access database: {error}")
access_table_not_found = TranslationKey("access.table_not_found", "Table '{table}' not found: {error}")


# ============================================================
# SHARED VALIDATION KEYS (flat — used by datasets/validation.py)
# ============================================================

invalid_operation_type = TranslationKey("invalid_operation_type", "Invalid operation type: {type}. Must be one of: {types}")
column_required = TranslationKey("column_required", "Operation '{type}' requires a column")
filter_operator_required = TranslationKey("filter_operator_required", "Filter operation requires an operator")
filter_value_required = TranslationKey("filter_value_required", "Filter operation requires a value")
invalid_fill_method = TranslationKey("invalid_fill_method", "Invalid fill_missing method: {method}. Must be one of: {methods}")
invalid_target_type = TranslationKey("invalid_target_type", "Invalid target_type: {target_type}. Must be one of: {types}")
invalid_encoding = TranslationKey("invalid_encoding", "Invalid encoding: {encoding}. Must be one of: {types}")
encode_column_required = TranslationKey("encode_column_required", "Encode operation requires a column")
columns_required = TranslationKey("columns_required", "Operation '{type}' requires a columns field")
rename_new_name_required = TranslationKey("rename_new_name_required", "Rename column operation requires a new name")

# --- moved from recipes/translations.py (shared data-access keys) ---
error_connection_connect_failed = TranslationKey(
    "error.connection.connect_failed",
    "MySQL connection failed: {error}"
)

error_connection_decryption_failed = TranslationKey(
    "error.connection.decryption_failed",
    "Failed to decrypt connection password: {error}"
)

error_connection_failed = TranslationKey(
    "error.connection.failed",
    "Failed to connect to database: {error}"
)

error_connection_query_failed = TranslationKey(
    "error.connection.query_failed",
    "Failed to query table/view '{table}': {error}"
)

error_connection_query_failed_2 = TranslationKey(
    "error.connection.query_failed_2",
    "Failed to execute compiled SQL: {error}"
)

error_connection_query_failed_3 = TranslationKey(
    "error.connection.query_failed_3",
    "PostgreSQL query failed: {error}"
)

error_connection_query_failed_4 = TranslationKey(
    "error.connection.query_failed_4",
    "MySQL query failed: {error}"
)

error_connection_query_failed_5 = TranslationKey(
    "error.connection.query_failed_5",
    "MSSQL query failed: {error}"
)

error_connection_query_failed_6 = TranslationKey(
    "error.connection.query_failed_6",
    "Access query failed: {error}"
)

error_connection_type_not_supported_3 = TranslationKey(
    "error.connection.type_not_supported_3",
    "Unsupported database type: {type}"
)

error_dataset_load_failed_2 = TranslationKey(
    "error.dataset.load_failed_2",
    "Failed to load data: {error}"
)

error_dataset_load_failed_3 = TranslationKey(
    "error.dataset.load_failed_3",
    "Virtual dataset '{id}' has no SQL definition"
)

error_dataset_load_failed_4 = TranslationKey(
    "error.dataset.load_failed_4",
    "Failed to load virtual dataset '{id}': {error}"
)

error_dataset_not_found_2 = TranslationKey(
    "error.dataset.not_found_2",
    "Dataset '{id}' not found"
)

error_dataset_table_missing = TranslationKey(
    "error.dataset.table_missing",
    "Table '{table}' does not exist"
)

error_dataset_unknown_source = TranslationKey(
    "error.dataset.unknown_source",
    "Unknown source type: {source_type}"
)

error_define_connection_not_found = TranslationKey(
    "error.define.connection_not_found",
    "Database connection not found or not accessible"
)

error_define_connection_not_found_2 = TranslationKey(
    "error.define.connection_not_found_2",
    "Connection not found or not accessible"
)

error_preparation_rule_not_found_2 = TranslationKey(
    "error.preparation.rule_not_found_2",
    "Preparation rule '{id}' not found"
)

