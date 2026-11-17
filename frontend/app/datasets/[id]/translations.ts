// app/datasets/[id]/translations.ts
// ============================================================
// DATASET DETAIL MODULE TRANSLATIONS
// All translation keys used by the dataset detail page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const DATASET_DETAIL = {
    // Overview
    overview: { key: "datasets.detail.overview", fallback: "Overview" },
    no_description: { key: "datasets.detail.no_description", fallback: "No description" },
    created: { key: "datasets.detail.created", fallback: "Created" },
    rows: { key: "datasets.detail.rows", fallback: "Rows" },
    // The count is not always known. A live virtual dataset has to run its join
    // to be counted, so the route says so rather than answering zero, and these
    // are the words that say it in the panel.
    rows_not_computed: { key: "datasets.detail.rows_not_computed", fallback: "Not computed" },
    rows_not_computed_hint: {
        key: "datasets.detail.rows_not_computed_hint",
        fallback: "The join has not been run, so there is no row count yet.",
    },
    // Live view versus saved table, in the panel's own words.
    storage_live: { key: "datasets.detail.storage_live", fallback: "Live view" },
    storage_table: { key: "datasets.detail.storage_table", fallback: "Saved table" },
    materialize_failed: {
        key: "datasets.detail.materialize_failed",
        fallback: "The saved table could not be built:",
    },

    // AI Descriptions
    descriptions: { key: "datasets.detail.descriptions", fallback: "AI Descriptions" },
    generated: { key: "datasets.detail.generated", fallback: "Generated" },
    model: { key: "datasets.detail.model", fallback: "Model" },

    // Error messages
    load_error: { key: "datasets.detail.load_error", fallback: "Failed to load dataset" },
    not_found: { key: "datasets.detail.not_found", fallback: "Dataset not found" },
    not_found_message: { key: "datasets.detail.not_found_message", fallback: "The dataset you are looking for could not be found." },

    // Operation type labels
    operation: {
        filter: { key: "datasets.preparation.operation.filter", fallback: "Filter" },
        fill_missing: { key: "datasets.preparation.operation.fill_missing", fallback: "Fill Missing" },
        convert_type: { key: "datasets.preparation.operation.convert_type", fallback: "Convert Type" },
        normalize: { key: "datasets.preparation.operation.normalize", fallback: "Normalize" },
        standardize: { key: "datasets.preparation.operation.standardize", fallback: "Standardize" },
        encode: { key: "datasets.preparation.operation.encode", fallback: "Encode" },
        drop_columns: { key: "datasets.preparation.operation.drop_columns", fallback: "Drop Columns" },
        rename_column: { key: "datasets.preparation.operation.rename_column", fallback: "Rename Column" },
    },

    // Filter operator labels
    operator: {
        greater_than: { key: "datasets.preparation.operator.greater_than", fallback: "Greater than (>)" },
        greater_than_or_equal: { key: "datasets.preparation.operator.greater_than_or_equal", fallback: "Greater than or equal (>=)" },
        less_than: { key: "datasets.preparation.operator.less_than", fallback: "Less than (<)" },
        less_than_or_equal: { key: "datasets.preparation.operator.less_than_or_equal", fallback: "Less than or equal (<=)" },
        equal_to: { key: "datasets.preparation.operator.equal_to", fallback: "Equal to (=)" },
        not_equal: { key: "datasets.preparation.operator.not_equal", fallback: "Not equal (!=)" },
        after: { key: "datasets.preparation.operator.after", fallback: "After (>)" },
        on_or_after: { key: "datasets.preparation.operator.on_or_after", fallback: "On or after (>=)" },
        before: { key: "datasets.preparation.operator.before", fallback: "Before (<)" },
        on_or_before: { key: "datasets.preparation.operator.on_or_before", fallback: "On or before (<=)" },
        contains: { key: "datasets.preparation.operator.contains", fallback: "Contains" },
        not_contains: { key: "datasets.preparation.operator.not_contains", fallback: "Does not contain" },
        starts_with: { key: "datasets.preparation.operator.starts_with", fallback: "Starts with" },
        ends_with: { key: "datasets.preparation.operator.ends_with", fallback: "Ends with" },
    },

    // Value input placeholders
    placeholder: {
        number: { key: "datasets.preparation.placeholder.number", fallback: "Enter a number..." },
        boolean: { key: "datasets.preparation.placeholder.boolean", fallback: "true / false" },
        datetime: { key: "datasets.preparation.placeholder.datetime", fallback: "YYYY-MM-DD or timestamp..." },
        value: { key: "datasets.preparation.placeholder.value", fallback: "Enter a value..." },
    },

    // Fill method labels
    fill_method: {
        mean: { key: "datasets.preparation.fill.mean", fallback: "Mean" },
        median: { key: "datasets.preparation.fill.median", fallback: "Median" },
        mode: { key: "datasets.preparation.fill.mode", fallback: "Mode" },
        constant: { key: "datasets.preparation.fill.constant", fallback: "Constant" },
        drop: { key: "datasets.preparation.fill.drop", fallback: "Drop" },
    },

    // Target type labels
    target_type: {
        numeric: { key: "datasets.preparation.type.numeric", fallback: "Numeric" },
        datetime: { key: "datasets.preparation.type.datetime", fallback: "DateTime" },
        string: { key: "datasets.preparation.type.string", fallback: "String" },
        boolean: { key: "datasets.preparation.type.boolean", fallback: "Boolean" },
    },

    // Encode method labels
    encode_method: {
        one_hot: { key: "datasets.preparation.encode.one_hot", fallback: "One-Hot" },
        label: { key: "datasets.preparation.encode.label", fallback: "Label" },
    },

    // UI placeholders (Select trigger placeholders)
    ui: {
        type: { key: "datasets.preparation.ui.type", fallback: "Type" },
        column: { key: "datasets.preparation.ui.column", fallback: "column" },
        operator: { key: "datasets.preparation.ui.operator", fallback: "operator" },
        value: { key: "datasets.preparation.ui.value", fallback: "value" },
        method: { key: "datasets.preparation.ui.method", fallback: "method" },
        target_type: { key: "datasets.preparation.ui.target_type", fallback: "target type" },
        encoding: { key: "datasets.preparation.ui.encoding", fallback: "encoding" },
        columns: { key: "datasets.preparation.ui.columns", fallback: "columns (comma separated)" },
        new_name: { key: "datasets.preparation.ui.new_name", fallback: "new name" },
    },

    // Preparation rules link card
    link_card: {
        title: { key: "datasets.preparation.link.title", fallback: "Transforms" },
        description: { key: "datasets.preparation.link.description", fallback: "Clean and transform this dataset" },
    },

    // Preparation Rules
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
} as const;