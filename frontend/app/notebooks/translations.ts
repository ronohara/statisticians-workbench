// app/notebooks/translations.ts
// ============================================================
// NOTEBOOKS MODULE TRANSLATIONS
// All translation keys used by notebook import and list pages.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const NOTEBOOKS = {
    // Import page
    import_title: { key: "notebooks.import_title", fallback: "Jupyter Notebook Import" },
    step1_title: { key: "notebooks.step1_title", fallback: "Step 1: Select File" },
    preview_button: { key: "notebooks.preview_button", fallback: "Preview" },
    parsing: { key: "notebooks.parsing", fallback: "Parsing..." },
    import_button: { key: "notebooks.import_button", fallback: "Import Notebook" },
    importing: { key: "notebooks.importing", fallback: "Importing..." },
    parse_error: { key: "notebooks.parse_error", fallback: "Failed to parse notebook" },
    import_failed: { key: "notebooks.import_failed", fallback: "Notebook import failed: {error}" },
    no_dataframes: { key: "notebooks.no_dataframes", fallback: "No DataFrames found in this notebook" },
    import_success: { key: "notebooks.import_success", fallback: "Imported {count} table(s) successfully" },
    import_complete: { key: "notebooks.import_complete", fallback: "Import Complete" },
    notebook_label: { key: "notebooks.notebook_label", fallback: "Notebook:" },
    tables_created_label: { key: "notebooks.tables_created_label", fallback: "Tables created:" },
    storage_label: { key: "notebooks.storage_label", fallback: "Storage:" },
    imported_at_label: { key: "notebooks.imported_at_label", fallback: "Imported at:" },
    title_label: { key: "notebooks.title_label", fallback: "Title:" },
    kernel_label: { key: "notebooks.kernel_label", fallback: "Kernel:" },
    cells_label: { key: "notebooks.cells_label", fallback: "Cells:" },
    dataframes_label: { key: "notebooks.dataframes_label", fallback: "DataFrames:" },
    size_label: { key: "notebooks.size_label", fallback: "Size:" },
    kb_unit: { key: "notebooks.kb_unit", fallback: "KB" },
    detected_dataframes: { key: "notebooks.detected_dataframes", fallback: "Detected DataFrames:" },
    doc_preview: { key: "notebooks.doc_preview", fallback: "Documentation Preview:" },
    sanitised_notice: { key: "notebooks.sanitised_notice", fallback: "Code cells have been removed for security. Only data outputs and markdown are preserved." },
    step2_title: { key: "notebooks.step2_title", fallback: "Step 2: Preview" },
    rows_cols_format: { key: "notebooks.rows_cols_format", fallback: "{rows} rows \u00d7 {cols} cols" },
    and_more: { key: "notebooks.and_more", fallback: "+{count} more" },
    table_name: { key: "notebooks.table_name", fallback: "Table: {name}" },

    // List page
    list_title: { key: "notebooks.list_title", fallback: "Notebook Imports" },
    no_imports: { key: "notebooks.no_imports", fallback: "No notebook imports yet." },
    table_count: { key: "notebooks.table_count", fallback: "{count} table{plural}" },
    import_deleted: { key: "notebooks.import_deleted", fallback: "Import deleted" },
    delete_failed: { key: "notebooks.delete_failed", fallback: "Failed to delete import" },
    fetch_error: { key: "notebooks.fetch_error", fallback: "Failed to fetch imports" },
    delete_confirm: { key: "notebooks.delete_confirm", fallback: "Delete import \"{name}\" and all its tables?" },
    delete_title: { key: "notebooks.delete_title", fallback: "Delete import" },

    // Sharing
    shared_badge: { key: "notebooks.shared_badge", fallback: "Shared" },
    share_label: { key: "notebooks.share_label", fallback: "Share with group" },
    shared: { key: "notebooks.shared", fallback: "Notebook shared with group" },
    unshared: { key: "notebooks.unshared", fallback: "Notebook unshared" },
    share_error: { key: "notebooks.share_error", fallback: "Only the owner can change sharing settings." },

    // Auto-create dataset
    create_dataset: { key: "notebooks.create_dataset", fallback: "Create dataset automatically" },
    dataset_created: { key: "notebooks.dataset_created", fallback: "Dataset created" },

    // Validation
    select_file_first: { key: "notebooks.select_file_first", fallback: "Please select a .ipynb file" },
    run_preview_first: { key: "notebooks.run_preview_first", fallback: "Run Preview to see what will be imported" },
    select_connection: { key: "notebooks.select_connection", fallback: "Select a database connection" },
    cant_create_tables: { key: "notebooks.cant_create_tables", fallback: "This connection cannot create tables — import denied" },
    connection_unavailable: { key: "notebooks.connection_unavailable", fallback: "Database connection not found or not accessible" },

    // Form labels
    storage_form_label: { key: "notebooks.storage_form_label", fallback: "Storage" },
    connection_form_label: { key: "notebooks.connection_form_label", fallback: "Connection" },
    select_connection_placeholder: { key: "notebooks.select_connection_placeholder", fallback: "Select connection..." },
    create_new_database: { key: "notebooks.create_new_database", fallback: "Create new database" },
    dataframe_prefix: { key: "notebooks.dataframe_prefix", fallback: "DataFrame" },

    // Connection badges
    connection_tables_badge: { key: "notebooks.connection_tables_badge", fallback: "Tables" },
    connection_create_db_badge: { key: "notebooks.connection_create_db_badge", fallback: "DB create" },

    // Example user
    example_blocked: { key: "notebooks.example_blocked", fallback: "Example users cannot import notebooks." },
    example_banner: { key: "notebooks.example_banner", fallback: "You are viewing as an example user. Register to import and manage notebooks." },
    example_register: { key: "notebooks.example_register", fallback: "Register" },
} as const;
