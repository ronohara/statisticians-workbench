// frontend/app/admin/setup/tuning/translations.ts
//
// The AI tuning defaults (plan Item 4b of workbench-AI-timeout-policy-plan.html).
//
// THE KEYS ARE `setup.tuning.*` AND THAT RENAME WAS FREE — the extract → translate →
// import pipeline has not run over them, so no translated row was orphaned. After it
// runs, renaming would cost a re-translation of every key here.
//
// The key must name its declaration path (the linter's R1/R3): a leaf `seconds` under
// TUNING_SETTINGS carries `setup.tuning.seconds`. Keeping the old `setup.limits.*`
// strings would have been readable but non-compliant, and the linter said so.
//
// THE THREE SHARED LABELS ARE NOT HERE. Temperature, maximum output tokens and
// maximum AI time appear on this page AND on the per-connection tuning dialog in
// admin/models, so they live in app/common/translations.ts.
//
// Neither are "Reset to defaults" and "Cancel": both already exist in COMMON, and a
// second key with the same fallback is what DUPLICATE-FALLBACK reports. This module
// references the existing ones.

import type { TranslationKey } from "@/lib/translation-helpers";

export const TUNING_SETTINGS = {
    description: {
        key: "setup.tuning.description",
        fallback:
            "Defaults for AI behaviour and time limits. These are usually suitable as they are — a per-user or per-connection setting can differ, and the value here is what applies when neither does.",
    },

    // The preamble's second half, kept separate so the page can render it as a
    // distinct paragraph. It says what these numbers are NOT, which is the part an
    // administrator needs before touching them.
    preamble_detail: {
        key: "setup.tuning.preamble_detail",
        fallback:
            "Every AI request uses these unless a connection overrides them. Changing one affects every model that has no setting of its own; it does not change a connection you have already tuned.",
    },

    save: { key: "setup.tuning.save", fallback: "Save settings" },
    saving: { key: "setup.tuning.saving", fallback: "Saving…" },
    saved: { key: "setup.tuning.saved", fallback: "Tuning settings saved" },
    save_error: { key: "setup.tuning.save_error", fallback: "Could not save the tuning settings" },
    load_error: { key: "setup.tuning.load_error", fallback: "Could not load the tuning settings" },
    forbidden: {
        key: "setup.tuning.forbidden",
        fallback: "Only a full administrator can change these settings.",
    },

    // Reset (plan Item 4b). The confirm text says what will be overwritten, because
    // "reset" alone does not tell an administrator whether their per-connection
    // overrides are included — they are not.
    reset_confirm_title: { key: "setup.tuning.reset_confirm_title", fallback: "Reset these six to their defaults?" },
    reset_confirm_body: {
        key: "setup.tuning.reset_confirm_body",
        fallback:
            "Every value on this page goes back to the default it shipped with. Per-connection overrides are not affected. This cannot be undone, and you will have to set any value you had changed again.",
    },
    reset_confirm_action: { key: "setup.tuning.reset_confirm_action", fallback: "Reset" },
    reset_done: { key: "setup.tuning.reset_done", fallback: "Tuning settings reset to their defaults" },
    reset_error: { key: "setup.tuning.reset_error", fallback: "Could not reset the tuning settings" },
    resetting: { key: "setup.tuning.resetting", fallback: "Resetting…" },

    // --- the slow-model threshold -------------------------------------------
    // Not a timeout. It is the number a recorded duration is compared against to
    // show "too slow", which is why the page's preamble says "time limits" rather
    // than "timeouts" — the label below is the only place the distinction shows.
    // FLAT, not nested under `model_test_seconds`. R1 permits one level of nesting
    // only where the intermediate name adds something the key does not already say;
    // here `model_test_seconds.label` under key `...model_test_seconds.label` repeats
    // itself, which the linter reports. Three leaves, three keys, no intermediate.
    slow_threshold_label: {
        key: "setup.tuning.slow_threshold_label",
        fallback: "Slow-model threshold",
    },
    slow_threshold_hint: {
        key: "setup.tuning.slow_threshold_hint",
        fallback:
            "A model test taking longer than this is reported as too slow. Users may raise their own limit; none may lower theirs below 1.",
    },
    // One "seconds" for this page. Two keys with the same fallback is what
    // DUPLICATE-FALLBACK reports, and there are already two elsewhere in the tree
    // (`profile.slow_threshold.seconds`, `licence.delete_no`-style neighbours) —
    // this page adds one rather than three call sites of one.
    seconds: { key: "setup.tuning.seconds", fallback: "seconds" },
    invalid_model_test_seconds: {
        key: "setup.tuning.invalid_model_test_seconds",
        fallback: "Please enter a whole number of seconds, at least 1",
    },

    // --- AI generation ------------------------------------------------------
    ai_section_label: { key: "setup.tuning.ai_section_label", fallback: "AI generation" },
    ai_section_hint: {
        key: "setup.tuning.ai_section_hint",
        fallback:
            "Defaults for every AI request. A single connection and model may override them where the tuning is specific to that pair.",
    },
    ai_temperature_hint: {
        key: "setup.tuning.ai_temperature_hint",
        fallback:
            "How varied the answers are: 0 is as repeatable as the model allows, 2 is the most varied. Values outside 0 to 2 are rejected by the provider, not by this system.",
    },
    ai_max_tokens_hint: {
        key: "setup.tuning.ai_max_tokens_hint",
        fallback:
            "The longest answer a single request may produce. A description needs roughly 500 tokens; 4000 leaves ample room.",
    },
    ai_timeout_hint: {
        key: "setup.tuning.ai_timeout_hint",
        fallback:
            "How long one AI request may run before it is abandoned. Too low and chat fails quietly; too high and a stalled model holds a worker. Local models on a CPU can need several minutes.",
    },
    invalid_ai_timeout: {
        key: "setup.tuning.invalid_ai_timeout",
        fallback: "The AI time limit must be a whole number of seconds, at least 1",
    },
    ai_tokens: { key: "setup.tuning.ai_tokens", fallback: "tokens" },
    invalid_temperature: {
        key: "setup.tuning.invalid_temperature",
        fallback: "Temperature must be a number from 0 to 2",
    },
    invalid_max_tokens: {
        key: "setup.tuning.invalid_max_tokens",
        fallback: "Please enter a whole number of tokens, at least 1",
    },

    // --- the two connection timeouts ---------------------------------------
    invalid_connect_timeout: {
        key: "setup.tuning.invalid_connect_timeout",
        fallback: "The connect timeout must be a whole number of seconds, at least 1 and at most 60",
    },
    invalid_probe_timeout: {
        key: "setup.tuning.invalid_probe_timeout",
        fallback: "The test timeout must be a whole number of seconds, at least 1 and at most 1200",
    },
    connect_timeout_hint: {
        key: "setup.tuning.connect_timeout_hint",
        fallback:
            "How long the network may take to accept a connection before the endpoint is treated as unreachable. A value below what the network needs turns a working endpoint into a dead one.",
    },
    probe_timeout_hint: {
        key: "setup.tuning.probe_timeout_hint",
        fallback:
            "How long one suitability test may run. A CPU-hosted model takes minutes, so a short limit here records a false failure rather than saving time.",
    },
} as const satisfies Record<string, TranslationKey | Record<string, TranslationKey>>;
