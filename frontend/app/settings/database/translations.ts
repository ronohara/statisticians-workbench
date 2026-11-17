// app/settings/database/translations.ts
// ============================================================
// DATABASE SETTINGS MODULE TRANSLATIONS
// All translation keys used by database settings pages.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

// ============================================================
// DATABASE CONNECTION FORM
// ============================================================

export const DB_CONNECTION_FORM = {
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
    test_incomplete: { key: "database.connection.test_incomplete", fallback: "Please fill all fields before testing" },
    test_failed: { key: "database.connection.test_failed", fallback: "Connection failed" },
    test_success: { key: "database.connection.test_success", fallback: "Connection successful!" },
    test_network_error: { key: "database.connection.test_network_error", fallback: "Network error while testing connection." },

    add_success: { key: "database.connection.add_success", fallback: "Connection added successfully" },
    update_success: { key: "database.connection.update_success", fallback: "Connection updated successfully" },
    save_error: { key: "database.connection.save_error", fallback: "Failed to save connection" },
    not_found: { key: "database.connection.not_found", fallback: "Connection not found" },
    shared_readonly_message: { key: "database.connection.shared_readonly_message", fallback: "This connection is shared with you. You can view it, but editing is restricted to the owner." },
    group_label: { key: "database.connection.group_label", fallback: "Group" },
    deleted: { key: "database.connection.deleted", fallback: "Connection deleted" },
    delete_error: { key: "database.connection.delete_error", fallback: "Failed to delete connection" },
    default_set: { key: "database.connection.default_set", fallback: "Default connection updated" },
    load_error: { key: "database.connection.load_error", fallback: "Failed to load connections" },
    add_new: { key: "database.connection.add_new", fallback: "Add New Connection" },
    no_connections: { key: "database.connection.no_connections", fallback: "No database connections saved yet." },
    add_first: { key: "database.connection.add_first", fallback: "Add your first connection" },
    default_badge: { key: "database.connection.default_badge", fallback: "Default" },
    shared_badge: { key: "database.connection.shared_badge", fallback: "Shared" },
    db_create_badge: { key: "database.connection.db_create_badge", fallback: "DB create" },
    tables_badge: { key: "database.connection.tables_badge", fallback: "Tables" },
    by_label: { key: "database.connection.by_label", fallback: "by" },
    unknown_user: { key: "database.connection.unknown_user", fallback: "Unknown" },
    set_default: { key: "database.connection.set_default", fallback: "Set as Default" },
    clear_default: { key: "database.connection.clear_default", fallback: "Clear Default" },
    default_cleared: { key: "database.connection.default_cleared", fallback: "Default connection cleared" },
    shared_readonly: { key: "database.connection.shared_readonly", fallback: "Shared" },
    delete_title: { key: "database.connection.delete_title", fallback: "Delete Connection" },
    delete_confirmation: { key: "database.connection.delete_confirmation", fallback: "Are you sure you want to delete the connection" },
    delete_button: { key: "database.connection.delete_button", fallback: "Delete" },
    file_path_label: { key: "database.connection.file_path_label", fallback: "File Path" },
    jet_host_label: { key: "database.connection.jet_host_label", fallback: "Jet Server Host" },
    jet_port_label: { key: "database.connection.jet_port_label", fallback: "Jet Server Port" },
    browse_tables: { key: "database.connection.browse_tables", fallback: "Browse Tables" },
    auto_create_title: { key: "database.connection.auto_create_title", fallback: "Auto-Create Datasets" },
    auto_create_tables: { key: "database.connection.auto_create_tables", fallback: "Auto-create table datasets" },
    auto_create_views: { key: "database.connection.auto_create_views", fallback: "Auto-create view datasets" },
    datasets_created: { key: "database.connection.datasets_created", fallback: "{n} datasets created" },
    auto_create_warnings_title: { key: "database.connection.auto_create_warnings_title", fallback: "Connection saved, but dataset auto-creation had warnings:" },
} as const;

// ============================================================
// DATABASE SETTINGS LIST
// ============================================================

export const DB_SETTINGS = {
    title: { key: "database.title", fallback: "Database Settings" },
    default_hint: { key: "database.default_hint", fallback: "The default connection is used as a fallback when an analysis recipe does not specify a connection." },
} as const;

// The probe panel's strings.
//
// Flat module-level declarations, not entries in the DB_CONNECTION_FORM table:
// AGENTS.md requires the flat form for every new declaration, and a table entry
// would also give each key a second name for the linter to flag (TABLE-SHAPE,
// R3). The property name is the key's tail, so `probe_check_now` is
// `database.connection.probe_check_now` and nothing has to be mapped.
export const probe_title = { key: "database.connection.probe_title", fallback: "Last check" };
export const probe_checked = { key: "database.connection.probe_checked", fallback: "Checked" };
export const probe_last_succeeded = {
    key: "database.connection.probe_last_succeeded",
    fallback: "Last succeeded",
};
export const probe_never = { key: "database.connection.probe_never", fallback: "Never" };
export const probe_no_success = {
    key: "database.connection.probe_no_success",
    fallback: "no successful probe recorded",
};
export const probe_check_now = { key: "database.connection.probe_check_now", fallback: "Check now" };
// Its own fallback, not `test_network_error`: that one says "while testing
// connection", which is the Test Connection button, and it read wrong when
// the user had pressed Check now.
// The relative label in the panel header, and the reason it exists.
//
// The panel's absolute timestamps are rendered in the house format, which is
// minute resolution. A probe completes in about 0.2 s, so two checks a few
// seconds apart render as the same string — measured 2026-11-06, `04:14:16.444Z`
// and `04:14:18.651Z` both displaying `06/Nov/26 11:14`. The data was updating
// and the display could not show it. These three say "this just happened"
// without a second format for the precise rows.
export const probe_just_now = { key: "database.connection.probe_just_now", fallback: "just now" };
export const probe_minute_ago = {
    key: "database.connection.probe_minute_ago",
    fallback: "1 minute ago",
};
export const probe_minutes_ago = {
    key: "database.connection.probe_minutes_ago",
    fallback: "{count} minutes ago",
};
export const probe_hour_ago = {
    key: "database.connection.probe_hour_ago",
    fallback: "1 hour ago",
};
export const probe_hours_ago = {
    key: "database.connection.probe_hours_ago",
    fallback: "{count} hours ago",
};

export const probe_check_failed = {
    key: "database.connection.probe_check_failed",
    fallback: "Could not check the connection just now.",
};
export const probe_auto_hint = {
    key: "database.connection.probe_auto_hint",
    fallback: "Updated automatically when the connection list loads.",
};
export const probe_unsaved_hint = {
    key: "database.connection.probe_unsaved_hint",
    fallback: "A connection is probed once it is saved.",
};

// The states, as labels. The keys match connection_probe.py's PROBE_* values.
// "Incomplete" is deliberately absent: `recipes.panel_incomplete` already
// declares that word, and a second key with an identical fallback is the
// duplicate the linter forbids — the label map names that declaration instead.
export const probe_state_reachable = { key: "database.connection.probe_state.reachable", fallback: "Reachable" };
export const probe_state_unreachable = { key: "database.connection.probe_state.unreachable", fallback: "Unreachable" };
export const probe_state_auth_failed = { key: "database.connection.probe_state.auth_failed", fallback: "Auth failed" };
export const probe_state_no_database = { key: "database.connection.probe_state.no_database", fallback: "No database" };
export const probe_state_no_permission = { key: "database.connection.probe_state.no_permission", fallback: "No permission" };
// "Incomplete setup", not "Incomplete": the recipe panel's word describes a
// different thing, and borrowing it would both mislead a reader and put a
// table path in this file for the linter to flag.
export const probe_state_incomplete = { key: "database.connection.probe_state.incomplete", fallback: "Incomplete setup" };
export const probe_state_schema_error = { key: "database.connection.probe_state.schema_error", fallback: "Schema unreadable" };
export const probe_state_unknown = { key: "database.connection.probe_state.unknown", fallback: "Not checked" };

