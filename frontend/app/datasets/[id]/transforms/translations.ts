// app/datasets/[id]/transforms/translations.ts
// ============================================================
// TRANSFORMS EDITOR TRANSLATIONS
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const TRANSFORMS_EDITOR = {
    // Layout — left pane
    back_to_data: { key: "transforms.back_to_data", fallback: "Back to My Data" },
    search_placeholder: { key: "transforms.search_placeholder", fallback: "Search transforms…" },
    new_transform: { key: "transforms.new_transform", fallback: "New Transform" },
    no_transforms: { key: "transforms.no_transforms", fallback: "No transforms defined for this dataset." },
    no_search_results: { key: "transforms.no_search_results", fallback: "No transforms match your search" },
    operations_count: { key: "transforms.operations_count", fallback: "{count} operations" },

    // Layout — empty right pane
    empty_title: { key: "transforms.empty_title", fallback: "Select a transform from the list or create a new one." },
    empty_hint: { key: "transforms.empty_hint", fallback: "Operations are applied in list order when the transform runs." },

    // Editor
    name_label: { key: "transforms.name_label", fallback: "Name" },
    name_placeholder: { key: "transforms.name_placeholder", fallback: "Transform name" },
    description_label: { key: "transforms.description_label", fallback: "Description" },
    description_placeholder: { key: "transforms.description_placeholder", fallback: "Description (optional)" },
    name_required: { key: "transforms.name_required", fallback: "Transform name is required." },
    save_button: { key: "transforms.save_button", fallback: "Save" },
    delete_button: { key: "transforms.delete_button", fallback: "Delete" },
    save_success: { key: "transforms.save_success", fallback: "Transform saved." },
    delete_success: { key: "transforms.delete_success", fallback: "Transform deleted." },
    delete_confirm: { key: "transforms.delete_confirm", fallback: "Delete this transform?" },
    load_error: { key: "transforms.load_error", fallback: "Failed to load transform" },

    // Operation builder labels
    op_add: { key: "transforms.op.add", fallback: "Add Operation" },
    op_remove: { key: "transforms.op.remove", fallback: "Remove" },
    op_type_placeholder: { key: "transforms.op.type_placeholder", fallback: "Operation type" },
    op_column_placeholder: { key: "transforms.op.column_placeholder", fallback: "Select column" },
    op_operator_placeholder: { key: "transforms.op.operator_placeholder", fallback: "Operator" },
    op_value_placeholder: { key: "transforms.op.value_placeholder", fallback: "Value" },
    op_method_placeholder: { key: "transforms.op.method_placeholder", fallback: "Method" },
    op_target_type_placeholder: { key: "transforms.op.target_type_placeholder", fallback: "Target type" },
    op_target_numeric: { key: "transforms.op.target_numeric", fallback: "Numeric" },
    op_target_datetime: { key: "transforms.op.target_datetime", fallback: "Datetime" },
    op_target_string: { key: "transforms.op.target_string", fallback: "String" },
    op_target_boolean: { key: "transforms.op.target_boolean", fallback: "Boolean" },
    op_new_name_placeholder: { key: "transforms.op.new_name_placeholder", fallback: "New name" },
    op_encoding_placeholder: { key: "transforms.op.encoding_placeholder", fallback: "Encoding" },
    op_encoding_onehot: { key: "transforms.op.encoding_onehot", fallback: "One-hot" },
    op_encoding_label: { key: "transforms.op.encoding_label", fallback: "Label" },
    op_empty_hint: { key: "transforms.op.empty_hint", fallback: "Add an operation to start building your transform." },
    op_operations_label: { key: "transforms.op.operations_label", fallback: "Operations" },

    // Operation type labels
    op_filter: { key: "transforms.op.type.filter", fallback: "Filter rows" },
    op_fill_missing: { key: "transforms.op.type.fill_missing", fallback: "Fill missing values" },
    op_drop_column: { key: "transforms.op.type.drop_column", fallback: "Drop column" },
    op_convert_type: { key: "transforms.op.type.convert_type", fallback: "Convert type" },
    op_normalize: { key: "transforms.op.type.normalize", fallback: "Normalize" },
    op_standardize: { key: "transforms.op.type.standardize", fallback: "Standardize" },
    op_rename_column: { key: "transforms.op.type.rename_column", fallback: "Rename column" },
    op_drop_duplicates: { key: "transforms.op.type.drop_duplicates", fallback: "Drop duplicates" },
    op_encode_category: { key: "transforms.op.type.encode_category", fallback: "Encode category" },

    // Filter operator labels
    filter_op_gt: { key: "transforms.filter.op_gt", fallback: ">" },
    filter_op_lt: { key: "transforms.filter.op_lt", fallback: "<" },
    filter_op_eq: { key: "transforms.filter.op_eq", fallback: "=" },
    filter_op_neq: { key: "transforms.filter.op_neq", fallback: "!=" },
    filter_op_contains: { key: "transforms.filter.op_contains", fallback: "contains" },
    filter_op_is_null: { key: "transforms.filter.op_is_null", fallback: "is null" },
    filter_op_is_not_null: { key: "transforms.filter.op_is_not_null", fallback: "is not null" },

    // Fill method labels
    fill_mean: { key: "transforms.fill.mean", fallback: "Mean" },
    fill_median: { key: "transforms.fill.median", fallback: "Median" },
    fill_mode: { key: "transforms.fill.mode", fallback: "Mode" },
    fill_constant: { key: "transforms.fill.constant", fallback: "Constant" },
    fill_drop_rows: { key: "transforms.fill.drop_rows", fallback: "Drop rows" },

    // Recipe-aware mode (Phase 4.5.4)
    back_to_recipe: { key: "transforms.back_to_recipe", fallback: "Back to Recipe: {name}" },
    for_recipe: { key: "transforms.for_recipe", fallback: "Recipe: {name}" },
    connected_to_recipe: { key: "transforms.connected_to_recipe", fallback: "Connected to: {name}" },
    connect_transform: { key: "transforms.connect_transform", fallback: "Connect to recipe" },
    disconnect_transform: { key: "transforms.disconnect_transform", fallback: "Disconnect from recipe" },
    connected_count: { key: "transforms.connected_count", fallback: "{count} connected" },
    connect_error: { key: "transforms.connect_error", fallback: "Failed to connect transform" },
    disconnect_error: { key: "transforms.disconnect_error", fallback: "Failed to disconnect transform" },
    operations_heading: { key: "transforms.operations_heading", fallback: "Operations" },
    empty_state: { key: "transforms.empty_state", fallback: "Add an operation to start building your transform." },
} as const;
