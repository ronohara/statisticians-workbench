// app/settings/ai/translations.ts
// ============================================================
// AI SETTINGS MODULE TRANSLATIONS
// All translation keys used by AI settings pages.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

// ============================================================
// AI CONNECTION FORM
// ============================================================

export const AI_CONNECTION_FORM = {
    add_title: { key: "ai.connection.add_title", fallback: "Add New AI Connection" },
    edit_title: { key: "ai.connection.edit_title", fallback: "Edit AI Connection" },
    form_description: { key: "ai.connection.form_description", fallback: "Configure an AI provider connection." },
    name_label: { key: "ai.connection.name_label", fallback: "Connection Name" },
    name_placeholder: { key: "ai.connection.name_placeholder", fallback: "e.g., My AI connection" },
    provider_label: { key: "ai.connection.provider_label", fallback: "Provider" },
    select_provider: { key: "ai.connection.select_provider", fallback: "Choose the AI provider" },
    endpoint_label: { key: "ai.connection.endpoint_label", fallback: "Endpoint URL" },
    endpoint_hint: { key: "ai.connection.endpoint_hint", fallback: "Override the default API endpoint if needed." },

    // The two connection timeouts (plan workbench-AI-timeout-policy-plan.html, Item 3).
    // Leaving a box blank inherits the workbench default, and the hint says so — an
    // empty box that does nothing visible is the failure this wording exists to avoid.
    timeouts_section_label: { key: "ai.connection.timeouts_section_label", fallback: "Connection timeouts" },
    timeouts_section_hint: { key: "ai.connection.timeouts_section_hint", fallback: "Leave a box blank to use the workbench default." },
    connect_timeout_hint: { key: "ai.connection.connect_timeout_hint", fallback: "How long the network may take to accept a connection. A value below what this network needs turns a working endpoint into an unreachable one." },
    probe_timeout_hint: { key: "ai.connection.probe_timeout_hint", fallback: "How long one suitability test may run here. A CPU-hosted model takes minutes." },
    invalid_connect_timeout: { key: "ai.connection.invalid_connect_timeout", fallback: "The connection timeout must be a whole number of seconds, at least 1 and at most 60." },
    invalid_probe_timeout: { key: "ai.connection.invalid_probe_timeout", fallback: "The model test timeout must be a whole number of seconds, at least 1 and at most 1200." },
    connect_exceeds_probe: { key: "ai.connection.connect_exceeds_probe", fallback: "The connection timeout cannot be longer than the model test timeout — a connection cannot be allowed to take longer to establish than the whole test may run." },
    api_key_label: { key: "ai.connection.api_key_label", fallback: "API Key" },
    api_key_hint: { key: "ai.connection.api_key_hint", fallback: "Your API key is encrypted before storage." },
    shared_label: { key: "ai.connection.shared_label", fallback: "Share with group" },
    shared_description: { key: "ai.connection.shared_description", fallback: "Make this connection available to other users in your group." },
    currently_shared: { key: "ai.connection.currently_shared", fallback: "✅ Currently shared with group" },
    currently_not_shared: { key: "ai.connection.currently_not_shared", fallback: "❌ Currently not shared" },
    test_button: { key: "ai.connection.test_button", fallback: "Test Connection" },
    test_error: { key: "ai.connection.test_error", fallback: "Connection failed." },
    test_success: { key: "ai.connection.test_success", fallback: "Connection successful!" },
    models: { key: "ai.connection.models", fallback: "Available Models" },
    add_success: { key: "ai.connection.add_success", fallback: "AI connection added successfully" },
    update_success: { key: "ai.connection.update_success", fallback: "AI connection updated successfully" },
    save_error: { key: "ai.connection.save_error", fallback: "Failed to save AI connection" },
    not_found: { key: "ai.connection.not_found", fallback: "Connection not found" },
    shared_readonly_message: { key: "ai.connection.shared_readonly_message", fallback: "This connection is shared with you. You can view it, but editing is restricted to the owner." },
    group_label: { key: "ai.connection.group_label", fallback: "Group" },
    provider_not_found: { key: "ai.connection.provider_not_found", fallback: "Provider not found" },
    metadata_load_error: { key: "ai.connection.metadata_load_error", fallback: "Failed to load provider metadata" },
    load_providers_error: { key: "ai.connection.load_providers_error", fallback: "Failed to load providers" },
    models_load_error: { key: "ai.connection.models_load_error", fallback: "Failed to load models" },
    models_synced: { key: "ai.connection.models_synced", fallback: "Models synced successfully" },
    // Replaces "Models synced successfully" as the success message now that the
    // button DISCOVERS what this connection serves rather than refreshing a
    // provider-wide catalogue. The counts are the point: "synced" said nothing about
    // what changed, and a discovery that found nothing new should read differently
    // from one that created three.
    models_discovered: {
        key: "ai.connection.models_discovered",
        fallback:
            "Discovered {seen} model(s) on this connection: {created} new, {refreshed} already known, {pruned} no longer served",
    },
    models_sync_error: { key: "ai.connection.models_sync_error", fallback: "Failed to sync models" },
    models_refresh: { key: "ai.connection.models_refresh", fallback: "Refresh models" },
    models_none: { key: "ai.connection.models_none", fallback: "No models synced yet. Click Refresh to fetch models from the provider." },
    select_provider_first: { key: "ai.connection.select_provider_first", fallback: "Please select a provider first" },
    metadata_loading: { key: "ai.connection.metadata_loading", fallback: "Provider information is still loading. Please wait." },
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
    clear_default: { key: "ai.connection.clear_default", fallback: "Clear Default" },
    default_cleared: { key: "ai.connection.default_cleared", fallback: "Default AI connection cleared" },
    shared_readonly: { key: "ai.connection.shared_readonly", fallback: "Shared" },
    delete_title: { key: "ai.connection.delete_title", fallback: "Delete AI Connection" },
    delete_confirmation: { key: "ai.connection.delete_confirmation", fallback: "Are you sure you want to delete the connection" },
    delete_button: { key: "ai.connection.delete_button", fallback: "Delete" },
    models_disabled: { key: "ai.connection.models_disabled", fallback: "Disabled" },
} as const;

// ============================================================
// AI SETTINGS LIST
// ============================================================

export const AI_SETTINGS = {
    title: { key: "ai.title", fallback: "AI Settings" },
    default_hint: { key: "ai.default_hint", fallback: "The default connection is used as a fallback when an analysis recipe does not specify an AI provider." },
} as const;