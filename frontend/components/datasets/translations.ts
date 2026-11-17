// components/datasets/translations.ts
// ============================================================
// DATASET COMPONENT MODULE TRANSLATIONS
// User-visible strings for the dataset components.
//
// The source tree's strings moved here with the component (plan Item 13). Their
// key strings are still `virtual.manual.*` deliberately: the Translation table
// is keyed by (key, language), and these nine are already translated there, so
// renaming them to match the new home would orphan every one of those rows and
// drop nine strings back to English until the extract → translate → import
// pipeline was next run. The prefix records where the strings were first
// written, not where the declaration lives now.
// ============================================================

export const SOURCE_TREE = {
    sources_title: { key: "virtual.manual.sources_title", fallback: "Where the data comes from" },
    sources_hint: { key: "virtual.manual.sources_hint", fallback: "Expand a connection or a dataset, then tick the columns to include." },

    select_all: { key: "virtual.manual.select_all", fallback: "Select all" },
    select_none: { key: "virtual.manual.select_none", fallback: "Select none" },
    loading_columns: { key: "virtual.manual.loading_columns", fallback: "Reading the columns…" },
    columns_error: { key: "virtual.manual.columns_error", fallback: "The columns could not be read." },
    tables_error: { key: "virtual.manual.tables_error", fallback: "The tables could not be read." },

    no_sources: { key: "virtual.manual.no_sources", fallback: "No connections or datasets are available to use." },
    no_match: { key: "virtual.manual.no_match", fallback: "Nothing here matches the filter." },
};

// The docked panel's own controls (Item 14). A separate table because these are
// the only strings here that are not the manual editor's: the manual page has no
// collapse control, and its keys carry `virtual.manual.*`. The panel's are
// `virtual.panel.*`, so filing them under SOURCE_TREE would put two key
// prefixes beneath one table path — which R3 reports, correctly.
export const SOURCE_PANEL = {
    collapse: { key: "virtual.panel.collapse", fallback: "Fold the source panel away" },
    expand: { key: "virtual.panel.expand", fallback: "Show the source panel" },
};
