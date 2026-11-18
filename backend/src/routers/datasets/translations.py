# src/routers/datasets/translations.py
# ============================================================
# DATASETS ROUTER TRANSLATIONS
# All translation keys used by the datasets router.
# ============================================================

from dataclasses import dataclass


@dataclass
class TranslationKey:
    """A translation key with an English fallback."""
    key: str
    fallback: str


# ============================================================
# LIST / CRUD
# ============================================================

DATASETS = {
    "datasets.list_error": TranslationKey("datasets.list_error", "Failed to load datasets"),
    "datasets.not_found": TranslationKey("datasets.not_found", "Dataset '{id}' not found or not accessible"),
    "datasets.not_owned": TranslationKey("datasets.not_owned", "Dataset '{id}' not found or you do not own it"),
    "datasets.unknown_source": TranslationKey("datasets.unknown_source", "Unknown source type: {source_type}"),
    "datasets.delete.success": TranslationKey("datasets.delete.success", "Dataset '{id}' deleted successfully"),
    "datasets.share.toggled": TranslationKey("datasets.share.toggled", "Sharing for dataset '{id}' updated successfully"),
    "datasets.share.error": TranslationKey("datasets.share.error", "Failed to update sharing"),
    # ---- Inline keys migrated from router call sites (P2) ----
    "chat.ai_provider_error": TranslationKey(
        "chat.ai_provider_error",
        "AI provider error: {error}"
    ),
    "error.ai.call_failed": TranslationKey(
        "error.ai.call_failed",
        "AI call failed: {error}"
    ),
    "virtual_chat.chat_session_not_found": TranslationKey(
        "virtual_chat.chat_session_not_found",
        "Chat session not found"
    ),
    "dataclean_chat.chat_session_not_found": TranslationKey(
        "dataclean_chat.chat_session_not_found",
        "Data cleaning chat session not found"
    ),
    "dataclean_chat.create_error": TranslationKey(
        "dataclean_chat.create_error",
        "Failed to create data cleaning session"
    ),
    "dataclean_chat.message_required": TranslationKey(
        "dataclean_chat.message_required",
        "Message is required"
    ),
    "dataclean_chat.empty_response": TranslationKey(
        "dataclean_chat.empty_response",
        "I couldn't generate a response. Please try again."
    ),
    "dataclean_chat.dataset_id_required": TranslationKey(
        "dataclean_chat.dataset_id_required",
        "datasetId is required"
    ),
    "dataclean_tools.no_rules_to_apply": TranslationKey(
        "dataclean_tools.no_rules_to_apply",
        "No rules to apply"
    ),
    "dataclean_tools.no_rules_to_preview": TranslationKey(
        "dataclean_tools.no_rules_to_preview",
        "No rules to preview"
    ),
    "datasets.browse.columns_failed": TranslationKey(
        "datasets.browse.columns_failed",
        "Failed to get columns: {error}"
    ),
    "database.connection_failed": TranslationKey(
        "database.connection_failed",
        "Failed to connect to database: {error}"
    ),
    "datasets.auto_create.connection_id_required": TranslationKey(
        "datasets.auto_create.connection_id_required",
        "connectionId is required"
    ),
    "datasets.auto_create.connection_not_found": TranslationKey(
        "datasets.auto_create.connection_not_found",
        "Connection not found"
    ),
    "datasets.auto_create.created": TranslationKey(
        "datasets.auto_create.created",
        "Datasets created"
    ),
    "datasets.auto_create.no_tables_discovered": TranslationKey(
        "datasets.auto_create.no_tables_discovered",
        "No tables or views discovered. Check that the database server is running and accessible."
    ),
    "chat.connection_not_found": TranslationKey(
        "chat.connection_not_found",
        "AI connection not found or not accessible"
    ),
    "database.connection_not_found": TranslationKey(
        "database.connection_not_found",
        "Database connection not found or not accessible"
    ),
    "virtual_chat.connection_not_found": TranslationKey(
        "virtual_chat.connection_not_found",
        "Database connection not found or access denied"
    ),
    "database.decryption_failed": TranslationKey(
        "database.decryption_failed",
        "Failed to decrypt connection password: {error}"
    ),
    "error.dataset.delete_failed_2": TranslationKey(
        "error.dataset.delete_failed_2",
        "Failed to delete dataset: {error}"
    ),
    "datasets.browse.discover_failed": TranslationKey(
        "datasets.browse.discover_failed",
        "Failed to discover tables: {error}"
    ),
    "virtual.execute_failed": TranslationKey(
        "virtual.execute_failed",
        "Execution failed: {error}"
    ),
    "virtual_chat.introspection_failed": TranslationKey(
        "virtual_chat.introspection_failed",
        "Introspection failed: {error}"
    ),
    "auth.invalid_token_error": TranslationKey(
        "auth.invalid_token_error",
        "Invalid token: {error}"
    ),
    "auth.invalid_token_missing_user_id": TranslationKey(
        "auth.invalid_token_missing_user_id",
        "Invalid token: missing user id"
    ),
    "virtual_chat.llm_call_failed": TranslationKey(
        "virtual_chat.llm_call_failed",
        "LLM call failed: {error}"
    ),
    "virtual_chat.llm_returned_error": TranslationKey(
        "virtual_chat.llm_returned_error",
        "LLM returned HTTP {status_code}"
    ),
    "virtual_chat.save_success": TranslationKey(
        "virtual_chat.save_success",
        "✅ Dataset **{name}** saved successfully. You can find it in the Existing Datasets list. Use Edit to refine it or Clone to create a variation."
    ),
    "virtual_chat.save_parse_error": TranslationKey(
        "virtual_chat.save_parse_error",
        "⚠️ Could not save dataset: {error}"
    ),
    "virtual_chat.save_no_sources": TranslationKey(
        "virtual_chat.save_no_sources",
        "⚠️ Unable to save: no data sources were introspected. Try mentioning table names like 'products' or 'orders' in your earlier messages."
    ),
    "virtual_chat.save_draft_success": TranslationKey(
        "virtual_chat.save_draft_success",
        "✅ Virtual dataset saved as draft: **{name}**.\n\nYou can view and edit it on the Datasets page. Use the Define tab to refine the SQL, joins, and output columns."
    ),
    "virtual_chat.save_failed": TranslationKey(
        "virtual_chat.save_failed",
        "⚠️ Save failed: {error}"
    ),
    "virtual_chat.empty_response": TranslationKey(
        "virtual_chat.empty_response",
        "I'm not sure how to respond to that. Could you rephrase or provide more detail?"
    ),
    "virtual.no_credentials_mysql": TranslationKey(
        "virtual.no_credentials_mysql",
        "No credentials found for MySQL connection {conn_id}"
    ),
    "virtual.no_credentials_postgresql": TranslationKey(
        "virtual.no_credentials_postgresql",
        "No credentials found for PostgreSQL connection {conn_id}"
    ),
    "error.dataset.not_found_3": TranslationKey(
        "error.dataset.not_found_3",
        "Dataset not found or not accessible: {error}"
    ),
    "error.dataset.not_found_2": TranslationKey(
        "error.dataset.not_found_2",
        "Dataset '{id}' not found"
    ),
    "datasets.not_found_2": TranslationKey(
        "datasets.not_found_2",
        "Dataset not found"
    ),
    "datasets.not_owner": TranslationKey(
        "datasets.not_owner",
        "You can only edit your own datasets"
    ),
    "database.pool_not_initialized": TranslationKey(
        "database.pool_not_initialized",
        "Database pool not initialized"
    ),
    "datasets.browse.preview_failed": TranslationKey(
        "datasets.browse.preview_failed",
        "Failed to preview table: {error}"
    ),
    "virtual.preview_failed": TranslationKey(
        "virtual.preview_failed",
        "Preview failed: {error}"
    ),
    "virtual.validate.no_sources": TranslationKey(
        "virtual.validate.no_sources",
        "No sources defined"
    ),
    "virtual.validate.dataset_id_required": TranslationKey(
        "virtual.validate.dataset_id_required",
        "Source '{alias}': datasetId required for dataset source"
    ),
    "virtual.validate.dataset_not_found": TranslationKey(
        "virtual.validate.dataset_not_found",
        "Source '{alias}': dataset {dataset_id} not found or access denied"
    ),
    "virtual.validate.connection_id_required": TranslationKey(
        "virtual.validate.connection_id_required",
        "Source '{alias}': connectionId required for {storage_type} source"
    ),
    "virtual.validate.connection_not_found": TranslationKey(
        "virtual.validate.connection_not_found",
        "Source '{alias}': connection {conn_id} not found or access denied"
    ),
    "virtual.validate.join_left_source_not_found": TranslationKey(
        "virtual.validate.join_left_source_not_found",
        "Join {j_idx}: left source '{left_alias}' not found"
    ),
    "virtual.validate.join_right_source_not_found": TranslationKey(
        "virtual.validate.join_right_source_not_found",
        "Join {j_idx}: right source '{right_alias}' not found"
    ),
    "virtual.validate.column_source_not_found": TranslationKey(
        "virtual.validate.column_source_not_found",
        "Column {c_idx}: source '{src_alias}' not found"
    ),
    # The checks that were promised and never made (Item 8). A definition that
    # named a column which is not there used to validate as valid and fail later
    # as a database error; these say which column, on which source.
    "virtual.validate.join_column_not_found": TranslationKey(
        "virtual.validate.join_column_not_found",
        "Join {j_idx}: source '{alias}' has no column '{column}'"
    ),
    "virtual.validate.output_column_not_found": TranslationKey(
        "virtual.validate.output_column_not_found",
        "Column {c_idx}: source '{src_alias}' has no column '{column}'"
    ),
    "virtual.save.invalid_definition": TranslationKey(
        "virtual.save.invalid_definition",
        "This dataset cannot be saved: {errors}"
    ),
    # ---- Scoreboard: the question each piece asks, and what would unblock it.
    # virtual_scoreboard.py returns these KEYS rather than rendered text (it is
    # pure and cannot read the Translation table); the prompt builder and the
    # page resolve them. '{source}' is the source alias.
    "virtual.scoreboard.sources.what": TranslationKey(
        "virtual.scoreboard.sources.what",
        "Which table should this dataset be built from?"
    ),
    # The columns OF A SOURCE piece is a `read` piece: the assistant fetches it with
    # get_columns and nobody is asked anything. The old text — "Which columns of
    # '{source}' should the result include?" — was the OUTPUT COLUMNS question
    # attached to the wrong piece, so the model reading it took it as licence to
    # ask. This is the design's own words for the piece (§4, piece table).
    "virtual.scoreboard.columns.what": TranslationKey(
        "virtual.scoreboard.columns.what",
        "What is inside '{source}'?"
    ),
    "virtual.scoreboard.columns.needs_failed": TranslationKey(
        "virtual.scoreboard.columns.needs_failed",
        "The columns of '{source}' could not be read."
    ),
    "virtual.scoreboard.columns.needs_empty": TranslationKey(
        "virtual.scoreboard.columns.needs_empty",
        "'{source}' has no columns to choose from."
    ),
    "virtual.scoreboard.joins.what": TranslationKey(
        "virtual.scoreboard.joins.what",
        "How should the sources be joined?"
    ),
    # Asked once per dataset, before save. The answer decides whether a table is
    # built when the dataset is defined — the choice the concierge never collected
    # until 2026-11-06.
    "virtual.scoreboard.storage.what": TranslationKey(
        "virtual.scoreboard.storage.what",
        "Should this be a live view, or a saved table?"
    ),
    # The two answers, as chips. Declared here so the scoreboard can name them and
    # `_resolve_scoreboard_texts` can translate them — a chip whose label is still
    # a key renders as the key.
    "virtual.scoreboard.storage.live": TranslationKey(
        "virtual.scoreboard.storage.live",
        "Live view"
    ),
    "virtual.scoreboard.storage.table": TranslationKey(
        "virtual.scoreboard.storage.table",
        "Saved table"
    ),
    "virtual.scoreboard.joins.needs": TranslationKey(
        "virtual.scoreboard.joins.needs",
        "Two or more sources, with their columns read."
    ),
    "virtual.scoreboard.output_columns.what": TranslationKey(
        "virtual.scoreboard.output_columns.what",
        "Which columns should the result contain?"
    ),
    "virtual.scoreboard.output_columns.needs": TranslationKey(
        "virtual.scoreboard.output_columns.needs",
        "One source, with its columns read."
    ),
    "virtual.scoreboard.name.what": TranslationKey(
        "virtual.scoreboard.name.what",
        "What should this dataset be called?"
    ),
    "virtual.join_suggestions.invalid_sources": TranslationKey(
        "virtual.join_suggestions.invalid_sources",
        "Join suggestions need a list of sources, each with an alias and a name ({error})."
    ),
    # The decision endpoint (Item 7). Each names what the caller got wrong, or
    # whose failure it was — never a generic "something went wrong".
    "virtual.decision.unknown_piece": TranslationKey(
        "virtual.decision.unknown_piece",
        "'{piece}' is not a decision this endpoint can apply."
    ),
    "virtual.decision.missing_value": TranslationKey(
        "virtual.decision.missing_value",
        "The '{piece}' decision needs a value."
    ),
    "virtual.decision.invalid_value": TranslationKey(
        "virtual.decision.invalid_value",
        "The '{piece}' decision could not be applied: {error}"
    ),
    "virtual.decision.no_connection": TranslationKey(
        "virtual.decision.no_connection",
        "Your choice was saved. The assistant could not respond because no AI connection is available."
    ),
    "virtual.decision.model_failed": TranslationKey(
        "virtual.decision.model_failed",
        "Your choice was saved. The assistant could not respond: {error}"
    ),
    # The docked source panel's fold (Item 14). Only a real boolean is accepted:
    # a string "false" would be truthy in the stored jsonb, so the caller is told
    # rather than given the opposite of what it asked for.
    "virtual.panel.collapsed_required": TranslationKey(
        "virtual.panel.collapsed_required",
        "The panel's folded state must be true or false."
    ),
    # Ticking a column in the tree (Item 14a). Each names what the caller got
    # wrong, so a click that cannot be applied says why instead of failing blank.
    "virtual.column.unknown_action": TranslationKey(
        "virtual.column.unknown_action",
        "'{action}' is not a column action. Use tick or untick."
    ),
    "virtual.column.missing_column": TranslationKey(
        "virtual.column.missing_column",
        "No column was named."
    ),
    "virtual.column.missing_source": TranslationKey(
        "virtual.column.missing_source",
        "A column needs its source: a dataset id, or a connection and a table name."
    ),
    "database.query_failed": TranslationKey(
        "database.query_failed",
        "Database query failed: {error}"
    ),
    "database.type_not_supported": TranslationKey(
        "database.type_not_supported",
        "Database type '{type}' is not yet supported"
    ),
    "common.unknown": TranslationKey(
        "common.unknown",
        "Unknown"
    ),
}

# ============================================================
# UPLOAD
# ============================================================

UPLOAD = {
    "datasets.upload.error": TranslationKey("datasets.upload.error", "Failed to upload dataset"),
    "datasets.upload.success": TranslationKey("datasets.upload.success", "Dataset '{name}' uploaded successfully"),
    "datasets.upload.unsupported_file": TranslationKey("datasets.upload.unsupported_file", "Unsupported file type. Please upload one of: {extensions}"),
    "datasets.upload.limit_reached_count": TranslationKey("datasets.upload.limit_reached_count", "Upload limit reached. Maximum {count} datasets allowed."),
    "datasets.upload.limit_reached_size": TranslationKey("datasets.upload.limit_reached_size", "Upload size limit exceeded. Maximum {size} MB total storage."),
    "datasets.upload.user_not_found": TranslationKey("datasets.upload.user_not_found", "User not found"),
    "datasets.upload.file_processing_failed": TranslationKey("datasets.upload.file_processing_failed", "Failed to process file: {error}"),
    "datasets.upload.dbf_memo_unsupported": TranslationKey("datasets.upload.dbf_memo_unsupported", "This .dbf file contains memo fields. Their values are stored in a separate file, which a single-file upload cannot carry."),
    "datasets.upload.dbf_field_unsupported": TranslationKey("datasets.upload.dbf_field_unsupported", "This .dbf file declares field types that cannot be read: {types}"),
    # ---- Inline keys migrated from router call sites (P2) ----
    "error.database.insert_failed": TranslationKey(
        "error.database.insert_failed",
        "Database error: {error}"
    ),
    "error.database.pool_not_initialized": TranslationKey(
        "error.database.pool_not_initialized",
        "Database pool not initialized"
    ),
}

# ============================================================
# DEFINE
# ============================================================

DEFINE = {
    "datasets.define.name_required": TranslationKey("datasets.define.name_required", "Dataset name is required"),
    "datasets.define.connection_required": TranslationKey("datasets.define.connection_required", "connectionId is required"),
    "datasets.define.table_name_required": TranslationKey("datasets.define.table_name_required", "tableName is required"),
    "datasets.define.invalid_source_type": TranslationKey("datasets.define.invalid_source_type", "sourceType must be 'table' or 'view'"),
    "datasets.define.connection_not_found": TranslationKey("datasets.define.connection_not_found", "Database connection not found or not accessible"),
    "datasets.define.connection_details_not_found": TranslationKey("datasets.define.connection_details_not_found", "Connection details not found"),
    "datasets.define.connection_test_failed": TranslationKey("datasets.define.connection_test_failed", "Database connection test failed"),
    "datasets.define.connection_successful": TranslationKey("datasets.define.connection_successful", "Connection successful"),
    "datasets.define.connection_timed_out": TranslationKey("datasets.define.connection_timed_out", "Connection timed out after 15 seconds"),
    "datasets.define.connection_missing_db_note": TranslationKey("datasets.define.connection_missing_db_note", "Note: PostgreSQL returns this error for missing databases AND for insufficient permissions. If the database exists, check that the user has CONNECT permission on the database."),
    "datasets.define.database_connection_failed": TranslationKey("datasets.define.database_connection_failed", "Failed to connect to database: {error}"),
    "datasets.define.permission_denied": TranslationKey("datasets.define.permission_denied", "Permission denied: User '{user}' does not have access to table '{table}'. Please grant SELECT permission."),
    "datasets.define.table_not_found": TranslationKey("datasets.define.table_not_found", "Table/view '{table}' not found in database '{database}'"),
    "datasets.define.table_access_failed": TranslationKey("datasets.define.table_access_failed", "Failed to access table '{table}': {error}"),
    "datasets.define.preview_failed": TranslationKey("datasets.define.preview_failed", "Failed to read data from table '{table}': {error}"),
    "datasets.define.verification_failed": TranslationKey("datasets.define.verification_failed", "Failed to verify table/view: {error}"),
    "datasets.define.dataset_created": TranslationKey("datasets.define.dataset_created", "Dataset '{name}' defined successfully"),
    # ---- Inline keys migrated from router call sites (P2) ----
    "error.define.dataset_creation_failed": TranslationKey(
        "error.define.dataset_creation_failed",
        "Failed to create dataset record: {error}"
    ),
    "error.connection.decryption_failed": TranslationKey(
        "error.connection.decryption_failed",
        "Failed to decrypt connection password: {error}"
    ),
    "error.database.pool_not_initialized": TranslationKey(
        "error.database.pool_not_initialized",
        "Database pool not initialized"
    ),
    "error.connection.type_not_supported": TranslationKey(
        "error.connection.type_not_supported",
        "Database type '{type}' is not yet supported"
    ),
}

# ============================================================
# SCHEMA
# ============================================================

SCHEMA = {
    "datasets.schema.load_error": TranslationKey("datasets.schema.load_error", "Could not load schema: {error}"),
    "datasets.schema.not_implemented": TranslationKey("datasets.schema.not_implemented", "Schema discovery for this dataset type '{type}' is not yet implemented"),
    "datasets.schema.external_failed": TranslationKey("datasets.schema.external_failed", "Failed to get schema from external database: {error}"),
    "datasets.schema.table_missing": TranslationKey("datasets.schema.table_missing", "Table no longer exists. Please re-upload the dataset."),
    "datasets.schema.from_preview": TranslationKey("datasets.schema.from_preview", "Schema derived from preview data (first 10 rows)"),
    # ---- Inline keys migrated from router call sites (P2) ----
    "error.define.connection_not_found": TranslationKey(
        "error.define.connection_not_found",
        "Database connection not found or not accessible"
    ),
    "error.connection.decryption_failed": TranslationKey(
        "error.connection.decryption_failed",
        "Failed to decrypt connection password: {error}"
    ),
    "error.connection.failed": TranslationKey(
        "error.connection.failed",
        "Failed to connect to database: {error}"
    ),
    # Not a failure to connect — a refusal to try, because the probe already
    # recorded that the host does not answer. The distinction is the point: the
    # caller learns the cached reason instead of waiting out a deadline.
    # A virtual dataset's schema is read from its definition, so the output
    # columns and their types are exact but the row count is not: that one needs
    # the join to run, which is the work a schema read no longer does.
    "datasets.schema.row_count_not_computed": TranslationKey(
        "datasets.schema.row_count_not_computed",
        "Row count is not computed for a virtual dataset without running the join."
    ),
    "datasets.schema.connection_unreachable": TranslationKey(
        "datasets.schema.connection_unreachable",
        "Connection {connection_id} is unreachable: {error}"
    ),
    "error.dataset.not_found_5": TranslationKey(
        "error.dataset.not_found_5",
        "Dataset '{id}' not found"
    ),
    "error.database.pool_not_initialized": TranslationKey(
        "error.database.pool_not_initialized",
        "Database pool not initialized"
    ),
    "error.connection.query_failed_7": TranslationKey(
        "error.connection.query_failed_7",
        "Database query failed: {error}"
    ),
    "error.connection.type_not_supported_2": TranslationKey(
        "error.connection.type_not_supported_2",
        "Database type '{type}' is not yet supported for schema discovery"
    ),
}

# ============================================================
# DESCRIBE (AI Description)
# ============================================================

DESCRIBE = {
    "datasets.describe.ai_connection_error": TranslationKey("datasets.describe.ai_connection_error", "AI connection error: {error}"),
    "datasets.describe.timeout_out_of_range": TranslationKey("datasets.describe.timeout_out_of_range", "The AI time limit must be between 1 and {max_seconds} seconds"),
    "datasets.describe.generation_failed": TranslationKey("datasets.describe.generation_failed", "Description generation failed: {error}"),
    "datasets.describe.empty_description": TranslationKey("datasets.describe.empty_description", "Generated description is empty. Please check the AI provider configuration."),
    "datasets.describe.description_generated": TranslationKey("datasets.describe.description_generated", "Description generated successfully for '{name}'"),
    # ---- Inline keys migrated from router call sites (P2) ----
    "error.describe.ai_connection_error": TranslationKey(
        "error.describe.ai_connection_error",
        "AI connection error: No connection available"
    ),
    "error.describe.ai_connection_error_2": TranslationKey(
        "error.describe.ai_connection_error_2",
        "AI connection error: Failed to decrypt API key"
    ),
    "error.define.connection_not_found": TranslationKey(
        "error.define.connection_not_found",
        "Database connection not found or not accessible"
    ),
    "error.connection.decryption_failed": TranslationKey(
        "error.connection.decryption_failed",
        "Failed to decrypt connection password: {error}"
    ),
    "error.connection.failed": TranslationKey(
        "error.connection.failed",
        "Failed to connect to database: {error}"
    ),
    "error.database.pool_not_initialized": TranslationKey(
        "error.database.pool_not_initialized",
        "Database pool not initialized"
    ),
    "error.connection.query_failed_7": TranslationKey(
        "error.connection.query_failed_7",
        "Database query failed: {error}"
    ),
}

# ============================================================
# PREPARATION (Transformation Rules)
# ============================================================

PREPARATION = {
    "datasets.preparation.duplicate_name": TranslationKey("datasets.preparation.duplicate_name", "A preparation rule with this name already exists for this dataset"),
    "datasets.preparation.already_exists": TranslationKey("datasets.preparation.already_exists", "A preparation rule with these operations already exists ('{name}')"),
    "datasets.preparation.rule_not_found": TranslationKey("datasets.preparation.rule_not_found", "Preparation rule '{id}' not found for this dataset"),
    "datasets.preparation.rule_not_found_or_not_owned": TranslationKey("datasets.preparation.rule_not_found_or_not_owned", "Preparation rule not found or you do not own it"),
    "datasets.preparation.rule_in_use": TranslationKey("datasets.preparation.rule_in_use", "This preparation rule is used by {count} recipe(s): {names}. Delete the recipes first."),
    "datasets.preparation.preview_failed": TranslationKey("datasets.preparation.preview_failed", "Failed to preview rule: {error}"),
    "datasets.preparation.schema_failed": TranslationKey("datasets.preparation.schema_failed", "Failed to read dataset schema: {error}"),
    "api.user.connection_not_found": TranslationKey("api.user.connection_not_found", "Connection not found"),
    "datasets.preparation.no_updates": TranslationKey("datasets.preparation.no_updates", "No fields to update"),
    "datasets.preparation.rule_created": TranslationKey("datasets.preparation.rule_created", "Preparation rule '{name}' created successfully"),
    "datasets.preparation.rule_updated": TranslationKey("datasets.preparation.rule_updated", "Preparation rule updated successfully"),
    "datasets.preparation.rule_deleted": TranslationKey("datasets.preparation.rule_deleted", "Preparation rule deleted successfully"),
    # ---- Inline keys migrated from router call sites (P2) ----
    "error.dataset.load_failed": TranslationKey(
        "error.dataset.load_failed",
        "Failed to load dataset: {error}"
    ),
    "error.dataset.not_found_4": TranslationKey(
        "error.dataset.not_found_4",
        "Dataset '{id}' not found or not accessible"
    ),
    "error.dataset.not_found_or_not_owned": TranslationKey(
        "error.dataset.not_found_or_not_owned",
        "Dataset '{id}' not found or you do not own it"
    ),
    "error.database.pool_not_initialized": TranslationKey(
        "error.database.pool_not_initialized",
        "Database pool not initialized"
    ),
}

# ============================================================
# TRANSFORMS (Dataset-Level Transform Rules)
# ============================================================

TRANSFORMS = {
    "datasets.transforms.duplicate_name": TranslationKey("datasets.transforms.duplicate_name", "A transform with this name already exists for this dataset"),
    "datasets.transforms.already_exists": TranslationKey("datasets.transforms.already_exists", "A transform with these operations already exists ('{name}')"),
    "datasets.transforms.not_found": TranslationKey("datasets.transforms.not_found", "Transform '{id}' not found for this dataset"),
    "datasets.transforms.not_found_or_not_owned": TranslationKey("datasets.transforms.not_found_or_not_owned", "Transform not found or you do not own it"),
    "datasets.transforms.in_use": TranslationKey("datasets.transforms.in_use", "This transform is used by {count} recipe(s): {names}. Delete the recipes first."),
    "datasets.transforms.no_updates": TranslationKey("datasets.transforms.no_updates", "No fields to update"),
    "datasets.transforms.created": TranslationKey("datasets.transforms.created", "Transform '{name}' created successfully"),
    "datasets.transforms.updated": TranslationKey("datasets.transforms.updated", "Transform updated successfully"),
    "datasets.transforms.deleted": TranslationKey("datasets.transforms.deleted", "Transform deleted successfully"),
    "datasets.transforms.cloned": TranslationKey("datasets.transforms.cloned", "Transform cloned as '{name}'"),
    "datasets.transforms.clone_forbidden": TranslationKey("datasets.transforms.clone_forbidden", "You do not have access to clone this transform"),
    "datasets.transforms.not_accessible": TranslationKey("datasets.transforms.not_accessible", "Dataset '{id}' not found or not accessible"),
    "datasets.transforms.not_owned": TranslationKey("datasets.transforms.not_owned", "Dataset '{id}' not found or you do not own it"),
    # ---- Inline keys migrated from router call sites (P2) ----
    "error.database.pool_not_initialized": TranslationKey(
        "error.database.pool_not_initialized",
        "Database pool not initialized"
    ),
}

# ============================================================
# EXAMPLE USER BLOCKING
# ============================================================

EXAMPLE_BLOCKED = {
    "datasets.example_blocked.create": TranslationKey("datasets.example_blocked.create", "Example users cannot create datasets"),
    "datasets.example_blocked.update": TranslationKey("datasets.example_blocked.update", "Example users cannot update datasets"),
    "datasets.example_blocked.delete": TranslationKey("datasets.example_blocked.delete", "Example users cannot delete datasets"),
}
# ============================================================
# VIRTUAL CONCIERGE — tool refusals
# ============================================================
#
# Flat module-level declarations (AGENTS.md R6), not table entries.
#
# A piece tool that takes an alias is writing knowledge about a source, so the
# alias has to name one. When it does not, the refusal names the aliases that do
# exist: the model has to be able to correct itself in the next call, and a bare
# "not found" leaves it guessing at names it never saw.

virtual_tool_no_source = TranslationKey(
    "virtual.tool.no_source",
    "No source named '{alias}'. This draft's sources: {aliases}."
)
virtual_tool_no_sources_yet = TranslationKey(
    "virtual.tool.no_sources_yet",
    "There is no source named '{alias}' — the draft has no sources yet. Call add_source first."
)

virtual_decision_applied = TranslationKey(
    "virtual.decision.applied",
    "Use the selection above."
)

virtual_decision_no_reply = TranslationKey(
    "virtual.decision.no_reply",
    "Your choice was saved. The assistant used up its working rounds without "
    "producing a reply — ask it to continue, or check the draft in the tree."
)


# ── Why a source could not be read ────────────────────────────────────────
#
# One key per failure *class*, not per sentence. The class is the vocabulary the
# two backends already share — Python's PROBE_* constants and Go's Probe*
# constants are byte-identical — so the same condition names the same state on
# both sides. The driver's own text still travels, demoted to a diagnostic line
# beneath, because it is the one string a translation can never render: it is
# asyncpg's words on one backend and pgx's on the other, for one failure.
#
# Nothing here covers `unknown`. Neither classifier ever emits it, and a stored
# row that carries it is mapped onto the unreachable declaration at the call
# site — "something stopped us connecting, and we do not know what" is the
# honest reading, and it is the same sentence the honest case already uses.
#
# The two definition reasons are not connection states at all: they describe a
# stored definition that names nothing, or one that recurses. They take keys for
# the same reason — we wrote them, so they are ours to translate.

unread_state_unreachable = TranslationKey(
    "datasets.unread.unreachable",
    "Could not reach this source. Check the host and port, then try again."
)
unread_state_auth_failed = TranslationKey(
    "datasets.unread.auth_failed",
    "The database refused this account's credentials."
)
unread_state_no_database = TranslationKey(
    "datasets.unread.no_database",
    "That database does not exist on the server."
)
unread_state_no_permission = TranslationKey(
    "datasets.unread.no_permission",
    "This account cannot read that source."
)
unread_state_schema_error = TranslationKey(
    "datasets.unread.schema_error",
    "The source answered, but its columns could not be read."
)
unread_state_incomplete = TranslationKey(
    "datasets.unread.incomplete",
    "The check did not finish in time. Try again, or raise the connection timeout."
)
unread_definition_incomplete = TranslationKey(
    "datasets.unread.definition_incomplete",
    "This source names neither a dataset nor a connection table."
)
unread_definition_too_deep = TranslationKey(
    "datasets.unread.definition_too_deep",
    "This dataset references itself more than five levels deep."
)

# The state → declaration map does NOT live here, deliberately. A map inside the
# file that declares the keys gives each one a second name in its own module — the
# alias shape the declaration rules forbid, and the linter reports it as six
# unreferenced keys because a dict value is not a use. It lives in `schema.py`, the
# module that resolves, beside `unreadStateDecl` in Go: the same arrangement as
# CHIP_HEADINGS, where the declarations are imported by name into the file that
# needs them.
