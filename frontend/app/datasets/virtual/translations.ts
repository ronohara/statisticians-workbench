// app/datasets/virtual/translations.ts
// ============================================================
// VIRTUAL DATASETS MODULE TRANSLATIONS
// All translation keys used by the virtual datasets page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const VIRTUAL = {
    title: { key: "virtual.title", fallback: "Virtual Datasets" },
    new_chat: { key: "virtual.new_chat", fallback: "New Virtual Dataset" },
    existing_title: { key: "virtual.existing_title", fallback: "Existing Datasets" },
    existing_none: { key: "virtual.existing_none", fallback: "None" },
    edit: { key: "virtual.edit", fallback: "Edit" },
    clone: { key: "virtual.clone", fallback: "Clone" },
    verbose: { key: "virtual.verbose", fallback: "Verbose" },
    send: { key: "virtual.send", fallback: "Send" },
    placeholder: { key: "virtual.placeholder", fallback: "Describe what you want to do..." },
    welcome: { key: "virtual.welcome", fallback: "Welcome to the Virtual Datasets assistant. If this is new to you, you might like to know how to start.\n\nAsk me to explain how statisticians use datasets as input to analysis recipes, and then use the output to create reports and visualisations.\n\nOr ask me to browse your actual datasets so we can start selecting data from them to use.\n\nJust say \"hello\" if you're unsure." },
    stage: { key: "virtual.stage", fallback: "Stage" },
    loading: { key: "virtual.loading", fallback: "Loading..." },
    error: { key: "virtual.error", fallback: "An error occurred" },
    deleted: { key: "virtual.deleted", fallback: "Dataset deleted" },
    draft_badge: { key: "virtual.draft_badge", fallback: "Draft" },
    ready_badge: { key: "virtual.ready_badge", fallback: "Ready" },
    recent_chats: { key: "virtual.recent_chats", fallback: "Recent Chats" },
    more: { key: "virtual.more", fallback: "more" },
    preview_title: { key: "virtual.preview_title", fallback: "Dataset preview" },
    preview_name: { key: "virtual.preview_name", fallback: "Name" },
    preview_sources: { key: "virtual.preview_sources", fallback: "Sources" },
    preview_joins: { key: "virtual.preview_joins", fallback: "Joins" },
    preview_columns: { key: "virtual.preview_columns", fallback: "Output columns" },
    // The progress strip reads the scoreboard's decided-piece count (Item 15),
    // never a stage position. Parameterised so both numbers come from one
    // declaration and word order can differ per language.
    progress_decided: { key: "virtual.progress_decided", fallback: "{decided} of {total} decided" },

    // The docked source panel (Item 14). The tab carries the panel's own heading
    // — that is SOURCE_PANEL.title, not a second key for the same words — and
    // these are the count beside it and the one failure it can report.
    // Flat, and the key matches: a nested `panel:` here would repeat what the
    // key already says, which is R1's objection. The panel's *controls* live in
    // SOURCE_PANEL beside the component, because the control is in its header.
    panel_columns: { key: "virtual.panel_columns", fallback: "{count} col." },
    panel_fold_error: { key: "virtual.panel_fold_error", fallback: "The panel's folded state could not be saved, so it will be open again next time." },

    // Ticking in the docked tree (Item 14a). A tick is a server write, so both a
    // session that does not exist yet and a write that failed need saying.
    panel_tick_no_session: { key: "virtual.panel_tick_no_session", fallback: "Send a message first — the tree records your ticks in the session." },
    panel_tick_error: { key: "virtual.panel_tick_error", fallback: "That column could not be ticked." },

    // A chip click (Item 15). The chip set is the server's own closed list, so a
    // failure is either the session or the write — both are worth naming.
    chip_error: { key: "virtual.chip_error", fallback: "That choice could not be applied." },
    confirm_selection: { key: "virtual.confirm_selection", fallback: "Use these" },
    // The two name-suggestion labels used to live here. They moved to
    // `app/common/translations.ts` as flat declarations when the recipe concierge
    // gained the same affordance: two call sites in two modules is the reuse rule's
    // case, and the key strings are unchanged so the Translation table needed no
    // re-import. Read them as `name_suggestion_heading` / `name_suggestion_accept`.
    // No `name_suggestion_placeholder`: `virtual.manual.name_label` already
    // carries "Dataset name", and a second key with an identical fallback is the
    // duplicate the linter forbids. The call site names that declaration.
    selection_hint: {
        key: "virtual.selection_hint",
        fallback: "Untick anything you do not want, then use them together.",
    },
    suggestion_applied: {
        key: "virtual.suggestion_applied",
        fallback: "Applied",
    },
    act_sources: { key: "virtual.act.sources", fallback: "Accepted {count} tables" },
    act_sources_short: { key: "virtual.act.sources_short", fallback: "Accepted {count} tables: {tables}" },
    act_join: { key: "virtual.act.join", fallback: "Joined {pair}" },
    act_named: { key: "virtual.act.named", fallback: "Named it \u201c{name}\u201d" },
    act_applied: { key: "virtual.act.applied", fallback: "Applied {piece}" },
    chip_load_error: { key: "virtual.chip_load_error", fallback: "The choices could not be refreshed, so these may be out of date." },

    // Piece labels (Item 22) are NOT declared here. Four of the five already
    // exist as the preview card's own labels — `preview_sources`, `preview_joins`,
    // `preview_columns` ("Output columns") and `preview_name` — and the fifth,
    // "Columns", is `DATASETS.schema.columns` in app/datasets/translations.ts.
    // AGENTS.md: reuse one key whenever the fallback text is identical, and a
    // second key with the same fallback must never exist. The page's
    // PIECE_LABELS map names these; nothing is re-declared to point at them.
    //
    // Storage and goal have no label on purpose: storage is satisfied by its
    // default and never pending (§4.2), and goal never blocks, so neither can
    // be the piece the strip reports. A label for either would be the orphan
    // this item exists to prevent.

    // Chip headings (Item 22, design §11). A heading above a chip row the
    // assistant placed. The component has carried a `heading` prop since Item
    // 15 with no caller; these are the callers' words, chosen by the piece the
    // chips answer.
    // Flat, with the property name matching the key's tail: a nested
    // `chip_heading: {}` would make the property path repeat a segment the key
    // already carries, which is R1's objection.
    // "Use these tables" rather than "Choose a table": the row arrives pre-ticked,
    // so there is usually nothing to choose — what the user does is accept it, or
    // adjust it and accept. A question mark beside one pre-ticked option read as a
    // prompt to pick something that was already picked.
    heading_choose_table: { key: "virtual.heading_choose_table", fallback: "Use these tables" },
    heading_choose_columns: { key: "virtual.heading_choose_columns", fallback: "Choose columns" },
    heading_match_columns: { key: "virtual.heading_match_columns", fallback: "Match these columns" },
    heading_materialised: { key: "virtual.heading_materialised", fallback: "Live or materialised?" },

    // The join editor (format A). The joins are in the draft by the time the
    // block renders, so this is an editor over what the agent wrote, not an
    // offer: "Apply" re-states the edited set, and a block whose rows still
    // match the draft closes without a request.
    //
    // Flat, and the property name is the key's tail: a `joins: {}` table here
    // would make the path repeat a segment the key already carries (R3).
    //
    // "Done" and "Remove this join" are NOT declared here — both texts already
    // exist (`AI.ai_recipe_done`, `MANUAL.remove_join`) and a second key with an
    // identical fallback is the duplicate the linter forbids. The call sites
    // name those declarations instead.
    joins_apply: { key: "virtual.joins_apply", fallback: "Apply" },
    joins_hint: {
        key: "virtual.joins_hint",
        fallback: "Change any column or join type, then continue.",
    },
    joins_coverage: {
        key: "virtual.joins_coverage",
        fallback: "{connected} of {total} tables connected",
    },
    joins_unjoined: { key: "virtual.joins_unjoined", fallback: "Not joined: {tables}" },
    joins_unsaved: {
        key: "virtual.joins_unsaved",
        // "Done" no longer closes without a request, so this must not offer it as
        // a way out: both buttons now send the set, and the label only says
        // whether anything changed.
        fallback: "These rows differ from the dataset. Apply them, or fix the empty row first.",
    },
    join_type_label: { key: "virtual.join_type_label", fallback: "Join type" },
    act_joins: { key: "virtual.act_joins", fallback: "Joined {count} pairs" },
} as const;
