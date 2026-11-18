# src/routers/translations.py
# ============================================================
# LOOSE ROUTER-LEVEL TRANSLATIONS
# Declarations for top-level router files (schema, licence,
# audio presets) that have no owning module directory.
# ============================================================

from dataclasses import dataclass


@dataclass
class TranslationKey:
    """A translation key with an English fallback."""
    key: str
    fallback: str


ROUTERS = {
    # ---- Inline keys migrated from router call sites (P2) ----
    "api.languages_load_error": TranslationKey(
        "api.languages_load_error",
        "Failed to load languages"
    ),
    "api.translations_load_error": TranslationKey(
        "api.translations_load_error",
        "Failed to load translations"
    ),
    "schema.connection_and_table_required": TranslationKey(
        "schema.connection_and_table_required",
        "connection_id and table_name are required for PostgreSQL/MySQL sources"
    ),
    "schema.connection_not_found": TranslationKey(
        "schema.connection_not_found",
        "Database connection not found or access denied"
    ),
    "schema.dataset_id_required": TranslationKey(
        "schema.dataset_id_required",
        "dataset_id is required for source_type=dataset"
    ),
    "schema.dataset_not_found": TranslationKey(
        "schema.dataset_not_found",
        "Dataset not found or access denied"
    ),
    "licence.delete_failed": TranslationKey(
        "licence.delete_failed",
        "Failed to delete licence file: {error}"
    ),
    "schema.introspect_mysql_failed": TranslationKey(
        "schema.introspect_mysql_failed",
        "Failed to introspect MySQL: {error}"
    ),
    "schema.introspect_postgresql_failed": TranslationKey(
        "schema.introspect_postgresql_failed",
        "Failed to introspect PostgreSQL: {error}"
    ),
    "audio_presets.invalid_chat_type": TranslationKey(
        "audio_presets.invalid_chat_type",
        "Invalid chat type: {chat_type}. Must be one of: {valid_types}"
    ),
    "licence.missing_content": TranslationKey(
        "licence.missing_content",
        "Missing 'content' field"
    ),
    "schema.no_table_name": TranslationKey(
        "schema.no_table_name",
        "Dataset has no table name (not yet ingested)"
    ),
    "database.pool_not_initialized": TranslationKey(
        "database.pool_not_initialized",
        "Database pool not initialized"
    ),
    "schema.unsupported_source_type": TranslationKey(
        "schema.unsupported_source_type",
        "Unsupported source_type: {source_type}. Use dataset, postgresql, or mysql."
    ),
    "licence.write_failed": TranslationKey(
        "licence.write_failed",
        "Failed to write licence file: {error}"
    ),
    "licence.delete_success": TranslationKey(
        "licence.delete_success",
        "Licence removed. Running in open-source mode."
    ),
    "licence.no_file_to_delete": TranslationKey(
        "licence.no_file_to_delete",
        "No licence file to delete — already in open-source mode."
    ),
    "licence.install_success": TranslationKey(
        "licence.install_success",
        "Licence installed successfully."
    ),
    # ---- AI providers (item 16, option b) ----
    "ai_providers.unauthorized": TranslationKey(
        "ai_providers.unauthorized",
        "Unauthorized"
    ),
    "ai_providers.forbidden": TranslationKey(
        "ai_providers.forbidden",
        "Forbidden"
    ),
    "ai_providers.missing_id_or_enabled": TranslationKey(
        "ai_providers.missing_id_or_enabled",
        "Missing id or enabled flag"
    ),
    "ai_providers.failed_to_update_provider": TranslationKey(
        "ai_providers.failed_to_update_provider",
        "Failed to update provider"
    ),
    "ai_providers.missing_provider_id": TranslationKey(
        "ai_providers.missing_provider_id",
        "Missing provider id"
    ),
    "ai_providers.invalid_provider_id": TranslationKey(
        "ai_providers.invalid_provider_id",
        "Invalid provider id"
    ),
    "ai_providers.provider_not_found": TranslationKey(
        "ai_providers.provider_not_found",
        "Provider not found"
    ),
    "ai_providers.failed_to_delete_provider": TranslationKey(
        "ai_providers.failed_to_delete_provider",
        "Failed to delete provider"
    ),
    "ai_providers.internal_error": TranslationKey(
        "ai_providers.internal_error",
        "Internal server error"
    ),
    # ---- Visualization types (item 25, option b — canonical-keyed) ----
    "visualization_types.forbidden": TranslationKey(
        "visualization_types.forbidden",
        "Forbidden"
    ),
    "visualization_types.internal_error": TranslationKey(
        "visualization_types.internal_error",
        "Internal server error"
    ),
    "visualization_types.name_and_slug_required": TranslationKey(
        "visualization_types.name_and_slug_required",
        "Name and slug are required"
    ),
    "visualization_types.slug_already_exists": TranslationKey(
        "visualization_types.slug_already_exists",
        "Slug already exists"
    ),
    "visualization_types.type_not_found": TranslationKey(
        "visualization_types.type_not_found",
        "Visualization type not found"
    ),
    # ---- Visualization instances (item 26, option b — canonical-keyed) ----
    "visualization_instances.unauthorized": TranslationKey(
        "visualization_instances.unauthorized",
        "Unauthorized"
    ),
    "visualization_instances.internal_error": TranslationKey(
        "visualization_instances.internal_error",
        "Internal server error"
    ),
    "visualization_instances.viz_type_id_required": TranslationKey(
        "visualization_instances.viz_type_id_required",
        "visualizationTypeId required"
    ),
    "visualization_instances.invalid_viz_type": TranslationKey(
        "visualization_instances.invalid_viz_type",
        "Invalid visualization type"
    ),
    "visualization_instances.invalid_instance_id": TranslationKey(
        "visualization_instances.invalid_instance_id",
        "Invalid instance id"
    ),
    "visualization_instances.instance_not_found": TranslationKey(
        "visualization_instances.instance_not_found",
        "Instance not found"
    ),
    "visualization_instances.viz_type_not_found": TranslationKey(
        "visualization_instances.viz_type_not_found",
        "Visualization type not found"
    ),
    "visualization_instances.no_rendered_output": TranslationKey(
        "visualization_instances.no_rendered_output",
        "No rendered output available"
    ),
}


# ============================================================
# TEST-AI ROUTER (item 17)
# ============================================================

TEST_AI = {
    # Error messages (success:false, error)
    "test_ai.unknown_provider": TranslationKey(
        "test_ai.unknown_provider",
        "Unknown provider: {provider}"
    ),
    "test_ai.api_key_required": TranslationKey(
        "test_ai.api_key_required",
        "API key is required for {name}."
    ),
    "test_ai.no_endpoint": TranslationKey(
        "test_ai.no_endpoint",
        "No endpoint configured for this provider."
    ),
    "test_ai.connection_failed": TranslationKey(
        "test_ai.connection_failed",
        "Connection failed: {msg}"
    ),
    "test_ai.connection_timeout_local": TranslationKey(
        "test_ai.connection_timeout_local",
        "Connection timeout. Is {name} running at {baseUrl}?"
    ),
    "test_ai.responded_with_status": TranslationKey(
        "test_ai.responded_with_status",
        "{name} responded with status {status}"
    ),
    "test_ai.fetch_failed": TranslationKey(
        "test_ai.fetch_failed",
        "fetch failed"
    ),
    "test_ai.internal_error": TranslationKey(
        "test_ai.internal_error",
        "Internal server error"
    ),
    # Success messages (success:true, message)
    "test_ai.endpoint_valid": TranslationKey(
        "test_ai.endpoint_valid",
        "Endpoint at {baseUrl} is valid."
    ),
    "test_ai.endpoint_v1_valid": TranslationKey(
        "test_ai.endpoint_v1_valid",
        "Endpoint at {baseUrl}/v1 is valid."
    ),
    "test_ai.server_reachable": TranslationKey(
        "test_ai.server_reachable",
        "{name} server at {baseUrl} is reachable."
    ),
}
