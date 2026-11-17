// app/datasets/browse/translations.ts
// ============================================================
// BROWSE DATABASE MODULE TRANSLATIONS
// ============================================================

import { TranslationKey } from "@/lib/translation-helpers";

export const BROWSE = {
    // Navigation
    back: { key: "datasets.browse.back", fallback: "Back" } as TranslationKey,
    connections: { key: "datasets.browse.connections", fallback: "Connections" } as TranslationKey,
    browse_tables: { key: "datasets.browse.browse_tables", fallback: "Browse Tables" } as TranslationKey,
    tables_count: { key: "datasets.browse.tables_count", fallback: "{count} tables" } as TranslationKey,

    // Table list
    tables: { key: "datasets.browse.tables", fallback: "Tables" } as TranslationKey,
    select_table_hint: { key: "datasets.browse.select_table_hint", fallback: "Select a table to view its columns and preview data." } as TranslationKey,

    // Column headers
    columns_title: { key: "datasets.browse.columns_title", fallback: "Columns — {table}" } as TranslationKey,
    column: { key: "datasets.browse.column", fallback: "Column" } as TranslationKey,
    type: { key: "datasets.browse.type", fallback: "Type" } as TranslationKey,
    nullable: { key: "datasets.browse.nullable", fallback: "Nullable" } as TranslationKey,

    // Preview
    preview: { key: "datasets.browse.preview", fallback: "Preview" } as TranslationKey,
    load_preview: { key: "datasets.browse.load_preview", fallback: "Load Preview" } as TranslationKey,
    preview_hint: { key: "datasets.browse.preview_hint", fallback: "Click \"Load Preview\" to see sample rows." } as TranslationKey,

    // Errors
    load_tables_error: { key: "datasets.browse.load_tables_error", fallback: "Failed to load tables" } as TranslationKey,
    load_columns_error: { key: "datasets.browse.load_columns_error", fallback: "Failed to load columns" } as TranslationKey,
    load_preview_error: { key: "datasets.browse.load_preview_error", fallback: "Failed to load preview" } as TranslationKey,
};
