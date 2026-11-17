// app/aitesting/translations.ts
// ============================================================
// AI TESTING TRANSLATIONS
// Keys for the AI Test page: the explanation, the connection
// selector, and the empty state.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const AI_TESTING = {
    title: { key: "ai.testing.title", fallback: "AI Testing" },

    // The approved copy, supplied by the user on 2026-10-29, as ONE key so the
    // sentence keeps its shape through translation and the copy has one home.
    explanation: {
        key: "ai.testing.explanation",
        fallback:
            "The Workbench's AI concierges are built for models that act. A model that merely talks — however politely, however large — will leave the recipe editor responding while doing nothing. The fix is the model, not the code. The tool on this page lets you test if a model is suitable.",
    },

    connection_label: {
        key: "ai.testing.connection_label",
        fallback: "AI connection",
    },
    // NOT re-declared here: "Select an AI connection" is already the fallback
    // of chat.select_connection_placeholder, and the rule is to reuse a key
    // whose text is identical rather than declare a second one. The page
    // imports that key from app/chat/translations.

    no_connections_heading: {
        key: "ai.testing.no_connections_heading",
        fallback: "No AI connection yet",
    },
    no_connections_body: {
        key: "ai.testing.no_connections_body",
        fallback:
            "Testing a model needs an AI connection. Add one, then come back to this page.",
    },
    no_connections_link: {
        key: "ai.testing.no_connections_link",
        fallback: "Go to AI connections",
    },

    models_heading: {
        key: "ai.testing.models_heading",
        fallback: "Models",
    },

    // The three states a test can hold. Declared once and referenced by every
    // cell, so "Pass" cannot be translated two ways in one product.
    // NOT declared here: "Unknown" is already common.unknown, and "Run" is
    // recipes.editor.run. Reuse beats re-declaration — the linter reports both
    // as duplicate fallbacks, and a second key with identical text drifts.
    state_pass: { key: "ai.testing.state_pass", fallback: "Pass" },
    state_fail: { key: "ai.testing.state_fail", fallback: "Fail" },

    // Test names. The ids (`tools`, `competence`, `turn`) are data and are never
    // translated; these are the labels the page renders for them.
    // The column headings, worded for someone choosing a model rather than
    // someone reading the test design. The IDs behind them stay `tools`,
    // `competence` and `turn` — those are stored data and never change.
    test_tools: { key: "ai.testing.test_tools", fallback: "uses Tools" },
    test_competence: { key: "ai.testing.test_competence", fallback: "Competence" },
    test_turn: { key: "ai.testing.test_turn", fallback: "Complexity" },

    column_model: { key: "ai.testing.column_model", fallback: "Model" },
    column_enabled: { key: "ai.testing.column_enabled", fallback: "Enabled" },
    // Screen-reader labels for the icons: a tick has no text, so without these
    // the column is silent to anyone not looking at it. The wording names the
    // MODEL rather than repeating the column header — "Enabled" was already
    // declared by admin.models.enabled, and a second key with identical text is
    // the duplicate the linter reports.
    enabled_yes: { key: "ai.testing.enabled_yes", fallback: "Model enabled" },
    enabled_no: { key: "ai.testing.enabled_no", fallback: "Model disabled" },
    column_actions: { key: "ai.testing.column_actions", fallback: "Test" },

    run_all_for_model: {
        key: "ai.testing.run_all_for_model",
        fallback: "Run all for this model",
    },
    run_all_untested: {
        key: "ai.testing.run_all_untested",
        fallback: "Run every test on untested models",
    },
    running: { key: "ai.testing.running", fallback: "Running…" },
    // "Run test", not "Run": "Run" is already recipes.editor.run, and reaching
    // into another module's table for one word adds a TABLE-SHAPE-USE finding to
    // a table that already has 81 of its own.
    run_test: { key: "ai.testing.run_test", fallback: "Run test" },
    // Cancel is common.cancel; not re-declared here.
    cancelled: {
        key: "ai.testing.cancelled",
        fallback: "Stopped. Results already recorded were kept.",
    },
    run_failed: {
        key: "ai.testing.run_failed",
        fallback: "The test could not run: {detail}",
    },
    cost_warning: {
        key: "ai.testing.cost_warning",
        fallback:
            "This runs {count} test(s), and the turn test takes minutes per model on CPU. Press again to start.",
    },
    cost_confirm: {
        key: "ai.testing.cost_confirm",
        fallback: "Start the run",
    },
    // Discovery asks THIS connection's server what it serves and records the
    // answer. It is not a refresh of a shared catalogue: two connections to one
    // provider can front different servers, which is why the button sits beside
    // the connection selector rather than on a provider page.
    discover_models: {
        key: "ai.testing.discover_models",
        fallback: "Discover models",
    },
    discover_running: {
        key: "ai.testing.discover_running",
        fallback: "Asking the server…",
    },
    discover_result: {
        key: "ai.testing.discover_result",
        fallback:
            "The server listed {seen} model(s): {created} new, {refreshed} already known, {pruned} no longer served",
    },
    discover_failed: {
        key: "ai.testing.discover_failed",
        fallback: "Could not discover models: {detail}",
    },

    // The list is the CONNECTION's discovered models, not the provider's catalogue:
    // two connections to one provider can front different servers with different
    // models, so a catalogue claim here would be the wrong fact.
    no_models: {
        key: "ai.testing.no_models",
        fallback: "No models have been discovered on this connection yet.",
    },

    load_error: {
        key: "ai.testing.load_error",
        fallback: "Could not load your AI connections. {detail}",
    },

    // --- the duration beside a capability state (Item 23) -------------------
    //
    // A capability cell answers "what did this model do". These answer "how long did
    // it take here" — the connection's measurement, not the model's — and the two are
    // deliberately separate facts: a model that passed in 4.6 s on one host and took
    // 189 s on another shows `pass` in both and different durations, and that is the
    // design working rather than a contradiction.
    duration_ms: {
        key: "ai.testing.duration_ms",
        fallback: "{ms} ms",
    },
    duration_seconds: {
        key: "ai.testing.duration_seconds",
        fallback: "{seconds} s",
    },
    // The limit is named because "too slow" alone tells the reader nothing about
    // whether the model or their own setting is the reason.
    too_slow: {
        key: "ai.testing.too_slow",
        fallback: "Over your {seconds} s limit",
    },
    // The limit is shown on this page but set elsewhere, so the page offers a
    // session-only override beside a link to the place that persists one. The
    // alternative — a page that says "over your N s limit" and nothing more — is
    // what made a reader ask where N comes from, which is the report this answers.
    slow_limit_session_label: {
        key: "ai.testing.slow_limit_session_label",
        fallback: "Slow-model limit",
    },
    slow_limit_session_hint: {
        key: "ai.testing.slow_limit_session_hint",
        fallback: "Applies to this page only — not saved.",
    },
    slow_limit_session_link: {
        key: "ai.testing.slow_limit_session_link",
        fallback: "Set it permanently in your profile",
    },
    slow_limit_session_reset: {
        key: "ai.testing.slow_limit_session_reset",
        fallback: "Use my saved limit",
    },
    // A verdict without its reason is a verdict a reader cannot act on: "fail" on
    // its own does not say whether the model fabricated, ignored the tool or
    // answered something else. The reason is already stored; this is its label.
    failure_reason: {
        key: "ai.testing.failure_reason",
        fallback: "Reason: {reason}",
    },
    // Shown when the model has a capability result but this connection has no
    // duration for it: the run happened somewhere else, and saying "untested"
    // without qualification would contradict the state shown beside it.
    no_duration_here: {
        key: "ai.testing.no_duration_here",
        fallback: "Not run on this connection",
    },
    // The limit could not be read. Said out loud because a page that marks nothing as
    // too slow is indistinguishable from one where nothing is too slow.
    slow_limit_failed: {
        key: "ai.testing.slow_limit_failed",
        fallback:
            "Could not read your slow-model limit, so no model is marked as too slow. {detail}",
    },
    slow_limit_unavailable: {
        key: "ai.testing.slow_limit_unavailable",
        fallback:
            "Your settings did not include a slow-model limit, so no model is marked as too slow.",
    },
    // Said once, above the table, rather than in every cell.
    elsewhere_note: {
        key: "ai.testing.elsewhere_note",
        fallback:
            "A model can hold a capability result from another connection. The duration beside each state is this connection's own measurement, so a model may show a state here with no duration.",
    },
} as const;
