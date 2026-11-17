// app/datasets/translations.ts
// ============================================================
// DATASETS MODULE TRANSLATIONS
// All translation keys used by the datasets module.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

// ============================================================
// LIST PAGE
// ============================================================

export const DATASETS = {
    title: { key: "datasets.title", fallback: "My Data" },
    list_error: { key: "datasets.list_error", fallback: "Failed to load datasets" },
    no_datasets: { key: "datasets.no_datasets", fallback: "No data available." },
    upload_button: { key: "datasets.upload_button", fallback: "Upload Data" },
    define_button: { key: "datasets.define_button", fallback: "Connect Database" },
    upload_first: { key: "datasets.upload_first", fallback: "Upload your first data file" },
    define_first: { key: "datasets.define_first", fallback: "Connect a database" },
    all_datasets: { key: "datasets.all_datasets", fallback: "All Data" },
    shared_badge: { key: "datasets.shared_badge", fallback: "Shared" },
    database_label: { key: "datasets.database_label", fallback: "DB" },
    by_label: { key: "datasets.by_label", fallback: "by" },
    unknown_user: { key: "datasets.unknown_user", fallback: "Unknown" },
    created_label: { key: "datasets.created_label", fallback: "Created" },
    view_schema: { key: "datasets.view_schema", fallback: "View Schema" },
    transform_button: { key: "datasets.transform_button", fallback: "Transform" },
    rules_button: { key: "datasets.rules_button", fallback: "Rules" },

    // Transforms page
    transforms_title: { key: "datasets.transforms.title", fallback: "Transforms" },
    transforms_for: { key: "datasets.transforms.for", fallback: "Transforms for {name}" },
    transforms_no_transforms: { key: "datasets.transforms.no_transforms", fallback: "No transforms defined for this dataset." },
    transforms_create_new: { key: "datasets.transforms.create_new", fallback: "New Transform" },
    transforms_name_label: { key: "datasets.transforms.name_label", fallback: "Name" },
    transforms_description_label: { key: "datasets.transforms.description_label", fallback: "Description (optional)" },
    transforms_create_button: { key: "datasets.transforms.create_button", fallback: "Create" },
    transforms_creating: { key: "datasets.transforms.creating", fallback: "Creating…" },
    transforms_delete_confirm: { key: "datasets.transforms.delete_confirm", fallback: "Delete this transform?" },
    transforms_delete_error: { key: "datasets.transforms.delete_error", fallback: "Failed to delete transform" },
    transforms_create_error: { key: "datasets.transforms.create_error", fallback: "Failed to create transform" },
    transforms_load_error: { key: "datasets.transforms.load_error", fallback: "Failed to load transforms" },
    transforms_back: { key: "datasets.transforms.back", fallback: "Back to My Data" },
    transforms_operations_label: { key: "datasets.transforms.operations_label", fallback: "{count} operation(s)" },
    transforms_created_label: { key: "datasets.transforms.created_label", fallback: "Created" },
    uploaded_title: { key: "datasets.uploaded_title", fallback: "Uploaded Data" },
    upload_new: { key: "datasets.upload_new", fallback: "Upload New File" },
    no_uploaded: { key: "datasets.no_uploaded", fallback: "No uploaded datasets yet." },
    upload_first_file: { key: "datasets.upload_first_file", fallback: "Upload Your First File" },
    view_dataset_title: { key: "datasets.view_dataset_title", fallback: "View dataset" },
    upload_count: { key: "datasets.upload_count", fallback: "{count} upload{plural}" },

    // Delete
    delete: {
        confirm: { key: "datasets.delete.confirm", fallback: "Delete this dataset?" },
        error: { key: "datasets.delete.error", fallback: "Failed to delete dataset" },
        success: { key: "datasets.delete.success", fallback: "Dataset '{id}' deleted successfully" },
        title: { key: "datasets.delete.title", fallback: "Delete" },
    },

    // Types
    type: {
        upload: { key: "datasets.type.upload", fallback: "Uploaded" },
        table: { key: "datasets.type.table", fallback: "Table" },
        view: { key: "datasets.type.view", fallback: "View" },
        virtual: { key: "datasets.type.virtual", fallback: "Virtual" },
        notebook: { key: "datasets.type.notebook", fallback: "Notebook" },
        postgresql: { key: "datasets.type.postgresql", fallback: "PostgreSQL" },
        mysql: { key: "datasets.type.mysql", fallback: "MySQL" },
        mssql: { key: "datasets.type.mssql", fallback: "MS SQL" },
        access: { key: "datasets.type.access", fallback: "MS Access" },
        cleaned_copy: { key: "datasets.type.cleaned_copy", fallback: "Cleaned copy" },
    },

    // Filter
    filter: {
        label: { key: "datasets.filter.label", fallback: "Filter" },
        all: { key: "datasets.filter.all", fallback: "All" },
        virtual: { key: "datasets.filter.virtual", fallback: "Virtual" },
        uploads: { key: "datasets.filter.uploads", fallback: "Uploads" },
        notebooks: { key: "datasets.filter.notebooks", fallback: "Notebooks" },
        postgresql: { key: "datasets.filter.postgresql", fallback: "PostgreSQL" },
        mysql: { key: "datasets.filter.mysql", fallback: "MySQL" },
        mssql: { key: "datasets.filter.mssql", fallback: "MS SQL" },
        access: { key: "datasets.filter.access", fallback: "MS Access" },
        cleaned: { key: "datasets.filter.cleaned", fallback: "Cleaned" },
        shared: { key: "datasets.filter.shared", fallback: "Shared" },
        not_shared: { key: "datasets.filter.not_shared", fallback: "Not Shared" },
        no_match: { key: "datasets.filter.no_match", fallback: "No datasets match this filter." },
    },

    // Provenance
    cleaned_badge: { key: "datasets.cleaned_badge", fallback: "Cleaned" },
    // Shown when a dataset is defined as materialised but no current table
    // exists — the build failed, or the definition changed after it succeeded.
    table_not_built: { key: "datasets.table_not_built", fallback: "Table not built" },
    created_from: { key: "datasets.created_from", fallback: "Created from {name}" },
    source_unavailable: { key: "datasets.source_unavailable", fallback: "source unavailable" },

    // Source
    source: {
        unknown_file: { key: "datasets.source.unknown_file", fallback: "Unknown file" },
    },

    // Schema
    schema: {
        load_error: { key: "datasets.schema.load_error", fallback: "Could not load schema: {error}" },
        title: { key: "datasets.schema.title", fallback: "Schema Preview" },
        total_rows: { key: "datasets.schema.total_rows", fallback: "Total Rows" },
        total_columns: { key: "datasets.schema.total_columns", fallback: "Total Columns" },
        columns: { key: "datasets.schema.columns", fallback: "Columns" },
        column_name: { key: "datasets.schema.column_name", fallback: "Column" },
        column_type: { key: "datasets.schema.column_type", fallback: "Type" },
        null_count: { key: "datasets.schema.null_count", fallback: "Nulls" },
        unique_count: { key: "datasets.schema.unique_count", fallback: "Unique" },
        sample_data: { key: "datasets.schema.sample_data", fallback: "Sample Data (first 5 rows)" },
        no_sample_data: { key: "datasets.schema.no_sample_data", fallback: "No sample data available" },
    },

    // Detail
    detail: {
        load_error: { key: "datasets.detail.load_error", fallback: "Failed to load dataset" },
        not_found: { key: "datasets.detail.not_found", fallback: "Dataset not found" },
        not_found_message: { key: "datasets.detail.not_found_message", fallback: "The dataset you are looking for could not be found." },
        overview: { key: "datasets.detail.overview", fallback: "Overview" },
        no_description: { key: "datasets.detail.no_description", fallback: "No description" },
        created: { key: "datasets.detail.created", fallback: "Created" },
        rows: { key: "datasets.detail.rows", fallback: "Rows" },
        descriptions: { key: "datasets.detail.descriptions", fallback: "AI Descriptions" },
        generated: { key: "datasets.detail.generated", fallback: "Generated" },
        model: { key: "datasets.detail.model", fallback: "Model" },
    },

    // Preparation (Transformation)
    preparation: {
        name_required: { key: "datasets.preparation.name_required", fallback: "Rule name is required" },
        filter_invalid: { key: "datasets.preparation.filter_invalid", fallback: "Filter operation requires column and value" },
        column_required: { key: "datasets.preparation.column_required", fallback: "Operation requires a column" },
        columns_required: { key: "datasets.preparation.columns_required", fallback: "Operation requires at least one column" },
        new_name_required: { key: "datasets.preparation.new_name_required", fallback: "Rename operation requires a new name" },
        save_error: { key: "datasets.preparation.save_error", fallback: "Failed to save transformation rule" },
        rule_updated: { key: "datasets.preparation.rule_updated", fallback: "Preparation rule updated successfully" },
        rule_created: { key: "datasets.preparation.rule_created", fallback: "Preparation rule '{name}' created successfully" },
        delete_error: { key: "datasets.preparation.delete_error", fallback: "Failed to delete transformation rule" },
        rule_deleted: { key: "datasets.preparation.rule_deleted", fallback: "Preparation rule deleted successfully" },
        preview_error: { key: "datasets.preparation.preview_error", fallback: "Failed to preview rule" },
        rules_title: { key: "datasets.preparation.rules_title", fallback: "Transformation Rules" },
        add_rule: { key: "datasets.preparation.add_rule", fallback: "Add Rule" },
        edit_rule: { key: "datasets.preparation.edit_rule", fallback: "Edit Rule" },
        new_rule: { key: "datasets.preparation.new_rule", fallback: "New Rule" },
        rule_name: { key: "datasets.preparation.rule_name", fallback: "Rule Name" },
        rule_name_placeholder: { key: "datasets.preparation.rule_name_placeholder", fallback: "e.g., Clean for Analysis" },
        rule_description: { key: "datasets.preparation.rule_description", fallback: "Description (optional)" },
        rule_description_placeholder: { key: "datasets.preparation.rule_description_placeholder", fallback: "Brief description" },
        shared: { key: "datasets.preparation.shared", fallback: "Share with group" },
        operations: { key: "datasets.preparation.operations", fallback: "Operations" },
        add_operation: { key: "datasets.preparation.add_operation", fallback: "Add Operation" },
        no_rules: { key: "datasets.preparation.no_rules", fallback: "No transformation rules defined for this dataset." },
        operations_count: { key: "datasets.preparation.operations_count", fallback: "operation(s)" },
        preview: { key: "datasets.preparation.preview", fallback: "Preview" },
        preview_title: { key: "datasets.preparation.preview_title", fallback: "Preview" },
        rows_before: { key: "datasets.preparation.rows_before", fallback: "Before" },
        rows_after: { key: "datasets.preparation.rows_after", fallback: "After" },
        rows_removed: { key: "datasets.preparation.rows_removed", fallback: "Removed" },
        original_data: { key: "datasets.preparation.original_data", fallback: "Original Data" },
        transformed_data: { key: "datasets.preparation.transformed_data", fallback: "Transformed Data" },
        delete_title: { key: "datasets.preparation.delete_title", fallback: "Delete Transformation Rule" },
        delete_confirmation: { key: "datasets.preparation.delete_confirmation", fallback: 'Are you sure you want to delete the transformation rule "{name}"? This will also remove it from any recipes that use it.' },
    },

    // Upload
    upload: {
        limit_reached_message: { key: "datasets.upload.limit_reached_message", fallback: "You have reached the maximum number of datasets allowed ({count})." },
        no_file: { key: "datasets.upload.no_file", fallback: "Please select a file first." },
        no_name: { key: "datasets.upload.no_name", fallback: "Please enter a dataset name." },
        error: { key: "datasets.upload.error", fallback: "Failed to upload dataset" },
        success: { key: "datasets.upload.success", fallback: "Dataset '{name}' uploaded successfully" },
        select_dataset: { key: "datasets.upload.select_dataset", fallback: "Please upload or select a dataset first." },
        connection_not_found: { key: "datasets.upload.connection_not_found", fallback: "Connection not found. Please select a valid AI connection." },
        title: { key: "datasets.upload.title", fallback: "Upload Data" },
        no_connections: { key: "datasets.upload.no_connections", fallback: "You need to define at least one AI connection to generate descriptions." },
        history: { key: "datasets.upload.history", fallback: "Upload History" },
        no_datasets: { key: "datasets.upload.no_datasets", fallback: "No datasets yet" },
        card_title: { key: "datasets.upload.card_title", fallback: "Upload and Describe" },
        name_label: { key: "datasets.upload.name_label", fallback: "Data Name" },
        name_placeholder: { key: "datasets.upload.name_placeholder", fallback: "My Data" },
        description_label: { key: "datasets.upload.description_label", fallback: "Description (optional)" },
        description_placeholder: { key: "datasets.upload.description_placeholder", fallback: "Brief description of this data" },
        file_label: { key: "datasets.upload.file_label", fallback: "File" },
        file_selected: { key: "datasets.upload.file_selected", fallback: "Selected file" },
        shared_label: { key: "datasets.upload.shared_label", fallback: "Share with group" },
        shared_description: { key: "datasets.upload.shared_description", fallback: "Make this data available to other users in your group." },
        shared_group_hint: { key: "datasets.upload.shared_group_hint", fallback: "Group: {group} - {description}" },
        limit_reached: { key: "datasets.upload.limit_reached", fallback: "Limit reached" },
        upload_button: { key: "datasets.upload.upload_button", fallback: "Upload" },
        generate_description: { key: "datasets.upload.generate_description", fallback: "Generate Description" },
    },

    // Description
    description: {
        error: { key: "datasets.description.error", fallback: "Failed to generate description." },
        empty: { key: "datasets.description.empty", fallback: "Generated description is empty. Please check the AI provider configuration." },
        generated: { key: "datasets.description.generated", fallback: "Description generated successfully." },
        title: { key: "datasets.description.title", fallback: "Generated Description" },
    },

    // Share
    shared: { key: "datasets.shared", fallback: "Dataset shared" },
    unshared: { key: "datasets.unshared", fallback: "Dataset unshared" },
    share_error: { key: "datasets.share_error", fallback: "Failed to update sharing" },
    unshare: { key: "datasets.unshare", fallback: "Unshare" },
    share: { key: "datasets.share", fallback: "Share" },

    // Define (Connect Database)
    define: {
        title: { key: "define.title", fallback: "Connect Database" },
        no_connections_message: { key: "define.no_connections_message", fallback: "You need to define at least one database connection before you can connect a database." },
        go_to_db_settings: { key: "define.go_to_db_settings", fallback: "Go to Database Settings" },
        load_connections_error: { key: "define.load_connections_error", fallback: "Failed to load connections" },
        step_connection: { key: "define.step_connection", fallback: "Connection" },
        step_source: { key: "define.step_source", fallback: "Source" },
        step_verify: { key: "define.step_verify", fallback: "Verify" },
        step_save: { key: "define.step_save", fallback: "Save" },
        step1_title: { key: "define.step1_title", fallback: "Select Database Connection" },
        step1_description: { key: "define.step1_description", fallback: "Choose a database connection to connect a dataset from." },
        connection_label: { key: "define.connection_label", fallback: "Database Connection" },
        select_connection: { key: "define.select_connection", fallback: "Select a connection" },
        step2_title: { key: "define.step2_title", fallback: "Select Source" },
        step2_description: { key: "define.step2_description", fallback: "Choose whether to use a table or view, then select the source." },
        source_type_label: { key: "define.source_type_label", fallback: "Source Type" },
        table: { key: "define.table", fallback: "Table" },
        view: { key: "define.view", fallback: "View" },
        source_label: { key: "define.source_label", fallback: "Source" },
        no_sources: { key: "define.no_sources", fallback: "No tables or views found in this database." },
        select_source: { key: "define.select_source", fallback: "Select a source" },
        verify_button: { key: "define.verify_button", fallback: "Verify Source" },
        select_source_first: { key: "define.select_source_first", fallback: "Please select a table or view first" },
        verify_error: { key: "define.verify_error", fallback: "Failed to verify table/view" },
        verify_success: { key: "define.verify_success", fallback: "Table/view verified successfully" },
        step3_title: { key: "define.step3_title", fallback: "Verify Source" },
        step3_description: { key: "define.step3_description", fallback: "Review the columns and preview data from the selected source." },
        schema_label: { key: "define.schema_label", fallback: "Schema" },
        column_name: { key: "define.column_name", fallback: "Column" },
        column_type: { key: "define.column_type", fallback: "Type" },
        nullable: { key: "define.nullable", fallback: "Nullable" },
        preview_label: { key: "define.preview_label", fallback: "Preview Data (first 10 rows)" },
        step4_title: { key: "define.step4_title", fallback: "Name and Save" },
        step4_description: { key: "define.step4_description", fallback: "Give your dataset a name and description, then save it." },
        dataset_name: { key: "define.dataset_name", fallback: "Dataset Name" },
        dataset_name_placeholder: { key: "define.dataset_name_placeholder", fallback: "e.g., Customer Data" },
        description_label: { key: "define.description_label", fallback: "Description (optional)" },
        description_placeholder: { key: "define.description_placeholder", fallback: "Brief description of this dataset" },
        shared_label: { key: "define.shared_label", fallback: "Share with group" },
        shared_description: { key: "define.shared_description", fallback: "Make this dataset available to other users in your group." },
        name_required: { key: "define.name_required", fallback: "Dataset name is required" },
        save_error: { key: "define.save_error", fallback: "Failed to create dataset" },
        save_success: { key: "define.save_success", fallback: "Dataset created successfully" },
        save_button: { key: "define.save_button", fallback: "Save Dataset" },
        load_sources_error: { key: "define.load_sources_error", fallback: "Failed to load sources" },
    },
} as const;