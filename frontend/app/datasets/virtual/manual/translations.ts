// app/datasets/virtual/manual/translations.ts
// ============================================================
// MANUAL VIRTUAL DATASET EDITOR
// The non-AI editor for virtual datasets. Prototype: reachable by URL only.
//
// Only text that does not already exist elsewhere is declared here. The dataset
// nouns this page shares with the AI page come from ../translations (VIRTUAL),
// and the generic verbs come from app/common/translations (COMMON) — the
// duplicate-fallback rule wants one declaration per fallback text, not one per
// page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const MANUAL = {
    title: { key: "virtual.manual.title", fallback: "Virtual dataset editor" },
    intro: { key: "virtual.manual.intro", fallback: "Build a virtual dataset from the columns you choose, or open one that already exists to change it." },

    new_dataset: { key: "virtual.manual.new_dataset", fallback: "Start a new dataset" },
    open_label: { key: "virtual.manual.open_label", fallback: "Open an existing dataset" },
    open_none: { key: "virtual.manual.open_none", fallback: "There is no virtual dataset to open yet." },
    loaded_note: { key: "virtual.manual.loaded_note", fallback: "Opened an existing definition — saving updates it." },
    loaded_note_shared: { key: "virtual.manual.loaded_note_shared", fallback: "Opened an existing shared definition — read only - no update allowed" },
    load_error: { key: "virtual.manual.load_error", fallback: "That dataset's definition could not be loaded." },

    // The source tree's own strings moved to components/datasets/translations.ts with the
    // component (plan Item 13).

    joins_title: { key: "virtual.manual.joins_title", fallback: "How the sources are joined" },
    joins_hint: { key: "virtual.manual.joins_hint", fallback: "Two or more sources need a join between them. One source needs none." },
    add_join: { key: "virtual.manual.add_join", fallback: "Add a join" },
    suggested: { key: "virtual.manual.suggested", fallback: "Suggested" },
    need_join: { key: "virtual.manual.need_join", fallback: "Two sources are selected, but nothing joins them." },
    column_placeholder: { key: "virtual.manual.column_placeholder", fallback: "Choose a column" },
    complete_join: { key: "virtual.manual.complete_join", fallback: "Fill in the unfinished join" },
    remove_join: { key: "virtual.manual.remove_join", fallback: "Remove this join" },
    unattached_sources: { key: "virtual.manual.unattached_sources", fallback: "Not joined to the rest: {sources}. Add a join that connects them." },
    bridge: { key: "virtual.manual.bridge", fallback: "Bridge" },
    bridge_choose_columns: { key: "virtual.manual.bridge_choose_columns", fallback: "no matching columns found — add the join and pick them" },
    bridge_no_columns: { key: "virtual.manual.bridge_no_columns", fallback: "columns not read yet — expand the source, or add the join and pick them" },

    output_title: { key: "virtual.manual.output_title", fallback: "What the dataset exposes" },
    output_hint: { key: "virtual.manual.output_hint", fallback: "The columns this dataset will expose, in order." },
    // Accessible names for icon-only buttons, so each says what it does to this
    // column rather than what it looks like. Distinct phrasing also keeps them
    // from duplicating another module's "Move up" / "Remove" — one key per
    // fallback text, which is what the duplicate-fallback rule asks for.
    move_up: { key: "virtual.manual.move_up", fallback: "Move this column up one place" },
    move_down: { key: "virtual.manual.move_down", fallback: "Move this column down one place" },
    remove: { key: "virtual.manual.remove", fallback: "Remove this column from the output" },
    alias_label: { key: "virtual.manual.alias_label", fallback: "Alias" },
    aggregation_note: { key: "virtual.manual.aggregation_note", fallback: "An aggregation carried by an old definition is kept as it is, but the join does not apply it." },

    name_label: { key: "virtual.manual.name_label", fallback: "Dataset name" },
    description_label: { key: "virtual.manual.description_label", fallback: "Dataset description" },
    materialized_label: { key: "virtual.manual.materialized_label", fallback: "Materialise the result" },
    materialized_hint: { key: "virtual.manual.materialized_hint", fallback: "Writes a table instead of a live join. Leave it off while prototyping." },

    validate: { key: "virtual.manual.validate", fallback: "Validate the definition" },
    test_join: { key: "virtual.manual.test_join", fallback: "Test the join" },
    update_dataset: { key: "virtual.manual.update_dataset", fallback: "Update this dataset" },
    validate_ok: { key: "virtual.manual.validate_ok", fallback: "The definition is structurally valid." },
    validate_errors: { key: "virtual.manual.validate_errors", fallback: "The definition has problems:" },

    need_name: { key: "virtual.manual.need_name", fallback: "Give the dataset a name before saving." },
    need_columns: { key: "virtual.manual.need_columns", fallback: "Tick at least one column to include." },
    alias_taken: { key: "virtual.manual.alias_taken", fallback: "That alias is already used by another source." },
    incomplete_join: { key: "virtual.manual.incomplete_join", fallback: "Finish or remove the join that has no columns chosen yet." },
    save_success: { key: "virtual.manual.save_success", fallback: "Virtual dataset saved." },
    // The build failed but the definition is saved — a different message from a
    // save failure, because the user's work is intact and the problem is
    // operational.
    materialize_failed: {
        key: "virtual.manual.materialize_failed",
        fallback: "Saved, but the table could not be built:",
    },
    materialize_retry: { key: "virtual.manual.materialize_retry", fallback: "Retry" },
    materialize_done: {
        key: "virtual.manual.materialize_done",
        fallback: "Table built.",
    },
    save_error: { key: "virtual.manual.save_error", fallback: "The virtual dataset could not be saved." },
    preview_error: { key: "virtual.manual.preview_error", fallback: "The join could not run." },
    preview_rows: { key: "virtual.manual.preview_rows", fallback: "{count} row(s) returned" },
    preview_empty: { key: "virtual.manual.preview_empty", fallback: "The join returned no rows." },
    test_pulls_every_source: { key: "virtual.manual.test_pulls_every_source", fallback: "Testing the join reads every source in full, so it can be slow." },
} as const;

export type ManualKey = TranslationKey;
