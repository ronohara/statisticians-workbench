// app/datasets/preparation/translations.ts
// ============================================================
// DATA PREPARATION MODULE TRANSLATIONS
// All translation keys used by preparation rule UI pages.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const PREP = {
    // Page titles
    title: { key: "preparation.title", fallback: "Transforms — {dataset}" },
    edit_title: { key: "preparation.edit_title", fallback: "Edit Rule: {name}" },
    new_title: { key: "preparation.new_title", fallback: "New Transform" },

    // Actions
    new_rule: { key: "preparation.new_rule", fallback: "New Rule" },
    save: { key: "preparation.save", fallback: "Save Rule" },
    saving: { key: "preparation.saving", fallback: "Saving..." },
    cancel: { key: "preparation.cancel", fallback: "Cancel" },
    edit: { key: "preparation.edit", fallback: "Edit" },
    delete: { key: "preparation.delete", fallback: "Delete" },
    duplicate: { key: "preparation.duplicate", fallback: "Duplicate" },
    preview: { key: "preparation.preview", fallback: "Preview" },
    back_to_list: { key: "preparation.back_to_list", fallback: "Back to rules" },

    // Empty states
    no_rules: { key: "preparation.no_rules", fallback: "No transforms yet" },
    create_first: { key: "preparation.create_first", fallback: "Create your first transform to clean and prepare this dataset before analysis." },

    // Rule list
    rules_for: { key: "preparation.rules_for", fallback: "Rules for {dataset}" },
    operations_count: { key: "preparation.operations_count", fallback: "{count} operation{itemize}" },
    duplicate_suffix: { key: "preparation.duplicate_suffix", fallback: "(copy)" },

    // Rule editor
    name_label: { key: "preparation.name_label", fallback: "Name" },
    description_label: { key: "preparation.description_label", fallback: "Description (optional)" },
    operations_label: { key: "preparation.operations_label", fallback: "Operations" },
    add_operation: { key: "preparation.add_operation", fallback: "Add Operation" },
    column_label: { key: "preparation.column_label", fallback: "Column" },
    select_column: { key: "preparation.select_column", fallback: "-- Select column --" },
    type_label: { key: "preparation.type_label", fallback: "Operation" },
    select_type: { key: "preparation.select_type", fallback: "-- Select operation --" },

    // Operation type names
    op_filter: { key: "preparation.op.filter", fallback: "Filter" },
    op_fill_missing: { key: "preparation.op.fill_missing", fallback: "Fill Missing" },
    op_drop_column: { key: "preparation.op.drop_column", fallback: "Drop Column" },
    op_convert_type: { key: "preparation.op.convert_type", fallback: "Convert Type" },
    op_normalize: { key: "preparation.op.normalize", fallback: "Normalize" },
    op_standardize: { key: "preparation.op.standardize", fallback: "Standardize" },
    op_rename_column: { key: "preparation.op.rename_column", fallback: "Rename Column" },
    op_drop_duplicates: { key: "preparation.op.drop_duplicates", fallback: "Drop Duplicates" },
    op_encode_category: { key: "preparation.op.encode_category", fallback: "Encode Category" },

    // Operation parameters
    operator_label: { key: "preparation.operator_label", fallback: "Operator" },
    value_label: { key: "preparation.value_label", fallback: "Value" },
    strategy_label: { key: "preparation.strategy_label", fallback: "Strategy" },
    target_type_label: { key: "preparation.target_type_label", fallback: "Target type" },
    method_label: { key: "preparation.method_label", fallback: "Method" },
    new_name_label: { key: "preparation.new_name_label", fallback: "New name" },
    encoding_param_label: { key: "preparation.encoding_param_label", fallback: "Encoding" },
    constant_value_label: { key: "preparation.constant_value_label", fallback: "Constant value" },

    // Strategy options
    strategy_mean: { key: "preparation.strategy.mean", fallback: "Mean" },
    strategy_median: { key: "preparation.strategy.median", fallback: "Median" },
    strategy_mode: { key: "preparation.strategy.mode", fallback: "Mode" },
    strategy_constant: { key: "preparation.strategy.constant", fallback: "Constant" },
    strategy_drop_row: { key: "preparation.strategy.drop_row", fallback: "Drop row" },
    method_zscore: { key: "preparation.method.zscore", fallback: "Z-Score" },
    method_minmax: { key: "preparation.method.minmax", fallback: "Min-Max" },
    encoding_onehot: { key: "preparation.encoding.onehot", fallback: "One-Hot" },
    encoding_label: { key: "preparation.encoding.label", fallback: "Label" },

    // Preview panel
    live_preview: { key: "preparation.live_preview", fallback: "Live Preview" },
    before: { key: "preparation.before", fallback: "Before" },
    after: { key: "preparation.after", fallback: "After" },
    rows: { key: "preparation.rows", fallback: "rows" },
    cols: { key: "preparation.cols", fallback: "cols" },
    nulls: { key: "preparation.nulls", fallback: "nulls" },
    sample_data: { key: "preparation.sample_data", fallback: "Sample data" },
    preview_loading: { key: "preparation.preview_loading", fallback: "Previewing..." },
    preview_error: { key: "preparation.preview_error", fallback: "Preview failed" },
    preview_no_ops: { key: "preparation.preview_no_ops", fallback: "Add operations to see preview" },

    // Messages
    rule_saved: { key: "preparation.rule_saved", fallback: "Rule saved" },
    rule_deleted: { key: "preparation.rule_deleted", fallback: "Rule deleted" },
    rule_duplicated: { key: "preparation.rule_duplicated", fallback: "Rule duplicated" },
    delete_confirm: { key: "preparation.delete_confirm", fallback: "Delete rule \"{name}\"? This cannot be undone." },
    save_error: { key: "preparation.save_error", fallback: "Failed to save rule" },
    load_error: { key: "preparation.load_error", fallback: "Failed to load data" },
    schema_error: { key: "preparation.schema_error", fallback: "Failed to load dataset schema" },
    name_required: { key: "preparation.name_required", fallback: "Rule name is required" },
    ops_required: { key: "preparation.ops_required", fallback: "At least one operation is required" },
    row_impact: { key: "preparation.row_impact", fallback: "{before} → {after} rows" },

    // Column type badges
    col_numeric: { key: "preparation.col.numeric", fallback: "numeric" },
    col_categorical: { key: "preparation.col.categorical", fallback: "categorical" },
    col_datetime: { key: "preparation.col.datetime", fallback: "datetime" },
    col_nulls: { key: "preparation.col.nulls", fallback: "{percent}% null" },
} as const;
