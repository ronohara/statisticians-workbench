// components/translations.ts
// ============================================================
// COMPONENTS TRANSLATIONS
// All translation keys used by shared components.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const COMPONENTS = {
    example_user_badge: { key: "components.example_user_badge", fallback: "Example User" },
    example_user_badge_tooltip: { key: "components.example_user_badge_tooltip", fallback: "Register for full access" },
    example_user_banner: {
        title: { key: "components.example_user_banner.title", fallback: "EXAMPLE USER MODE" },
        message: { key: "components.example_user_banner.message", fallback: "You are viewing the system in read-only mode. Register for full access to create and modify resources." },
        message_short: { key: "components.example_user_banner.message_short", fallback: "Read-only mode - Register for full access" },
        register_button: { key: "components.example_user_banner.register_button", fallback: "Register for Full Access" },
        register_short: { key: "components.example_user_banner.register_short", fallback: "Register" },
    },
    group_admin_badge: { key: "components.group_admin_badge", fallback: "Group Admin" },
    readonly_wrapper: { key: "components.readonly_wrapper.message", fallback: "Read-only mode - Register for full access to modify this content" },
    audio_settings_dialog: {
        title: { key: "components.audio_settings_dialog.title", fallback: "Audio Settings" },
        voice: { key: "components.audio_settings_dialog.voice", fallback: "Voice" },
        system_default: { key: "components.audio_settings_dialog.system_default", fallback: "System default" },
        speed_label: { key: "components.audio_settings_dialog.speed_label", fallback: "Speed: {0}x" },
        pitch_label: { key: "components.audio_settings_dialog.pitch_label", fallback: "Pitch: {0}" },
        reset_to_defaults: { key: "components.audio_settings_dialog.reset_to_defaults", fallback: "Reset to defaults" },
        close: { key: "components.audio_settings_dialog.close", fallback: "Close" },
    },
    feature_gate: {
        upgrade_title: { key: "components.feature_gate.upgrade_title", fallback: "Corporate Feature" },
        upgrade_message: { key: "components.feature_gate.upgrade_message", fallback: "This feature requires a corporate licence. Contact Sentuny for upgrade options." },
    },
    preparation_preview: {
        rows_removed: { key: "components.preparation_preview.rows_removed", fallback: "{0} removed" },
        more_columns: { key: "components.preparation_preview.more_columns", fallback: "+{0} more" },
        null_value: { key: "components.preparation_preview.null_value", fallback: "null" },
    },
    active_checkmark: { key: "components.active_checkmark", fallback: " ✓" },
    return_banner: {
        text: { key: "components.return_banner.text", fallback: "You were working on an AI recipe." },
        link: { key: "components.return_banner.link", fallback: "Return to your session" },
        // The same banner reached by a plain path rather than the AI slug — the
        // transforms editor, which both recipe editors send a returnTo path to.
        recipe_text: { key: "components.return_banner.recipe_text", fallback: "You were working on a recipe." },
        recipe_link: { key: "components.return_banner.recipe_link", fallback: "Return to your recipe" },
        // The link label when there is no returnTo at all — the page's own way
        // back, which has no recipe to name. "Return" alone, not "Back": the
        // fallback text beside it already says where the return lands.
        fallback_link: { key: "components.return_banner.fallback_link", fallback: "Return" },
    },
} as const;