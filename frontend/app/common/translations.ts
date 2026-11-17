// app/common/translations.ts
// ============================================================
// COMMON TRANSLATIONS
// Keys used across multiple modules.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

// ============================================================
// COMMON UI
// ============================================================

export const COMMON = {
    loading: { key: "common.loading", fallback: "Loading..." },
    // The two connection-timeout labels (plan workbench-AI-timeout-policy-plan.html,
    // Item 3). Here rather than in either page's own file because BOTH pages show
    // them — the admin default and the per-connection override name the same two
    // settings. The unit is part of the label: two "seconds" keys already exist and a
    // third duplicate is what the reuse rule forbids.
    connect_timeout_label: { key: "common.connect_timeout_label", fallback: "Connection timeout (seconds)" },
    // These three are shown on TWO surfaces: the global tuning page and the
    // per-connection tuning dialog on admin/models. Shared, so they live here.
    //
    // Renaming their keys to `common.*` is safe only because the extract → translate
    // → import pipeline has not yet run over them; after that it would orphan every
    // translated row. The key must name its declaration path, which is what R3 checks.
    ai_temperature_label: { key: "common.ai_temperature_label", fallback: "Temperature" },
    ai_max_tokens_label: { key: "common.ai_max_tokens_label", fallback: "Maximum output tokens" },
    ai_timeout_label: { key: "common.ai_timeout_label", fallback: "Maximum AI time" },
    probe_timeout_label: { key: "common.probe_timeout_label", fallback: "Model test timeout (seconds)" },
    dismiss: { key: "common.dismiss", fallback: "Dismiss" },
    restoring: { key: "common.restoring", fallback: "Restoring..." },
    cancel: { key: "common.cancel", fallback: "Cancel" },
    // One label, two places: the admin page's title and the nav link that opens it.
    // Declared here because COMMON is the shared namespace, and because two keys
    // carrying the same fallback is the duplication the lint rule forbids — the
    // nav said "Provider Models" for months precisely because these were two
    // declarations that could drift apart.
    ai_models: { key: "common.ai_models", fallback: "AI Models" },
    sending: { key: "common.sending", fallback: "Sending..." },
    deleting: { key: "common.deleting", fallback: "Deleting..." },
    saving: { key: "common.saving", fallback: "Saving..." },
    edit: { key: "common.edit", fallback: "Edit" },
    save: { key: "common.save", fallback: "Save" },
    back: { key: "common.back", fallback: "Back" },
    delete: { key: "common.delete", fallback: "Delete" },
    verifying: { key: "common.verifying", fallback: "Verifying..." },
    next: { key: "common.next", fallback: "Next" },
    uploading: { key: "common.uploading", fallback: "Uploading..." },
    generating: { key: "common.generating", fallback: "Generating..." },
    copy: { key: "common.copy", fallback: "Copy" },
    clear: { key: "common.clear", fallback: "Clear" },
    view: { key: "common.view", fallback: "View" },
    cannot_undo: { key: "common.cannot_undo", fallback: "This action cannot be undone." },
    testing: { key: "common.testing", fallback: "Testing..." },
    no_permission: { key: "common.no_permission", fallback: "You do not have permission to view this page." },
    email_features_unavailable: { key: "common.email_features_unavailable", fallback: "Email-based account features are not available." },
    copied: { key: "common.copied", fallback: "Copied!" },
    copy_to_clipboard: { key: "common.copy_to_clipboard", fallback: "Copy to clipboard" },
    close: { key: "common.close", fallback: "Close" },
    open_navigation: { key: "common.open_navigation", fallback: "Open navigation" },
    close_navigation: { key: "common.close_navigation", fallback: "Close navigation" },
    select_language: { key: "common.select_language", fallback: "Select language" },
    microphone_on: { key: "common.microphone_on", fallback: "Microphone on" },
    microphone_off: { key: "common.microphone_off", fallback: "Microphone off" },
    speaker_on: { key: "common.speaker_on", fallback: "Speaker on" },
    speaker_off: { key: "common.speaker_off", fallback: "Speaker off" },
    audio_settings: { key: "common.audio_settings", fallback: "Audio settings" },
    audio_resume: { key: "common.audio_resume", fallback: "Resume" },
    audio_pause: { key: "common.audio_pause", fallback: "Pause" },
    audio_stop: { key: "common.audio_stop", fallback: "Stop" },
    speech_input_unsupported: { key: "common.speech_input_unsupported", fallback: "Speech input is not supported in your browser. Compatible browsers: Google Chrome, Microsoft Edge, Opera, Samsung Internet." },
    speech_output_unsupported: { key: "common.speech_output_unsupported", fallback: "Speech output is not supported in your browser. Compatible browsers: Google Chrome, Microsoft Edge, Mozilla Firefox, Apple Safari, Opera, Samsung Internet." },
    speech_recognition_error: { key: "common.speech_recognition_error", fallback: "Speech recognition error: {error}. Try again." },
    speech_mic_denied: { key: "common.speech_mic_denied", fallback: "Microphone access was denied. Please allow microphone access in your browser settings." },
    speech_network_error: { key: "common.speech_network_error", fallback: "Speech recognition network error — check your internet connection and try again." },
    speech_mic_failed: { key: "common.speech_mic_failed", fallback: "Failed to start microphone: {error}." },
    unknown: { key: "common.unknown", fallback: "Unknown" },
    untitled: { key: "common.untitled", fallback: "Untitled" },
    true_label: { key: "common.true_label", fallback: "True" },
    false_label: { key: "common.false_label", fallback: "False" },
    success_label: { key: "common.success_label", fallback: "Success" },
    error_label: { key: "common.error_label", fallback: "Error" },
    no_answer: { key: "common.no_answer", fallback: "No answer returned" },
    dismiss_error: { key: "common.dismiss_error", fallback: "Dismiss error" },
    dismiss_success: { key: "common.dismiss_success", fallback: "Dismiss success" },
    reset_to_defaults: { key: "common.reset_to_defaults", fallback: "Reset to defaults" },
    voice: { key: "common.voice", fallback: "Voice" },
    system_default: { key: "common.system_default", fallback: "System default" },
    view_dataset: { key: "common.view_dataset", fallback: "View dataset" },
    delete_chat: { key: "common.delete_chat", fallback: "Delete chat" },
    has_more_information: { key: "common.has_more_information", fallback: "has more information" },
    access_denied_admin: { key: "common.access_denied_admin", fallback: "Access denied — admin only." },
    unknown_error: { key: "common.unknown_error", fallback: "Unknown error" },
} as const;

// ============================================================
// APP
// ============================================================

export const APP = {
    name: { key: "app.name", fallback: "Statisticians Workbench" },
    version: { key: "app.version", fallback: "Version" },
    access_denied_admin: { key: "common.access_denied_admin", fallback: "Access denied — admin only." },
    unknown_error: { key: "common.unknown_error", fallback: "Unknown error" },
} as const;

// ============================================================
// DEMO
// ============================================================

export const DEMO = {
    banner: {
        title: { key: "demo.banner.title", fallback: "⚠️ DEMO MODE" },
        message: { key: "demo.banner.message", fallback: "This is a demonstration system. Data may be reset periodically." },
    },
    badge: { key: "demo.badge", fallback: "DEMO" },
    access_denied_admin: { key: "common.access_denied_admin", fallback: "Access denied — admin only." },
    unknown_error: { key: "common.unknown_error", fallback: "Unknown error" },
} as const;

// ============================================================
// HOME
// ============================================================

export const HOME = {
    welcome_placeholder: { key: "home.welcome_placeholder", fallback: "Welcome to the Statisticians Workbench" },
    access_denied_admin: { key: "common.access_denied_admin", fallback: "Access denied — admin only." },
    unknown_error: { key: "common.unknown_error", fallback: "Unknown error" },
} as const;

// ============================================================
// NAVIGATION
// ============================================================

export const NAV = {
    home: { key: "nav.home", fallback: "Home" },
    ai_chat: { key: "nav.ai_chat", fallback: "AI Tools" },
    ai_general: { key: "nav.ai_general", fallback: "General" },
    ai_testing: { key: "nav.ai_testing", fallback: "AI testing" },
    ai_database_design: { key: "nav.ai_database_design", fallback: "Database design" },
    ai_virtual_datasets: { key: "nav.ai_virtual_datasets", fallback: "Virtual Datasets" },
    ai_dataset_cleaning: { key: "nav.ai_dataset_cleaning", fallback: "Dataset cleaning" },
    ai_analysis_rules: { key: "nav.ai_analysis_rules", fallback: "Recipe Editor" },
    about: { key: "nav.about", fallback: "About" },
    admin: { key: "nav.admin", fallback: "Admin" },
    admin_panel: { key: "nav.admin_panel", fallback: "User Management" },
    admin_providers: { key: "nav.admin_providers", fallback: "AI Providers" },
    // "AI Models", matching the page it opens (admin.models.title). The old label
    // described ProviderModel — the abandoned table, dropped 2026-11-02 — and the
    // page has listed LLMModel since Item 18, so the nav was naming a catalogue
    // that no longer exists. The KEY is left as it is: renaming it would retire a
    // translated string in 20 languages for a label change, and the key is opaque.
    // The "AI Models" link uses COMMON.ai_models directly. It was
    // nav.admin_provider_models with its own "Provider Models" fallback, which is
    // how a renamed page left a stale label in the nav for months: two
    // declarations for one thing, and only one updated.
    admin_visualization_types: { key: "nav.admin_visualization_types", fallback: "Visualization Types" },
    admin_groups: { key: "nav.admin_groups", fallback: "Group Descriptions" },
    admin_licence: { key: "nav.admin_licence", fallback: "Licence" },
    admin_setup: { key: "nav.admin_setup", fallback: "Setup" },
    admin_setup_limits: { key: "nav.admin_setup_limits", fallback: "Limits" },
    // Plan Item 4b: the AI tuning defaults, which are not limits.
    admin_setup_tuning: { key: "nav.admin_setup_tuning", fallback: "Tuning" },
    admin_setup_options: { key: "nav.admin_setup_options", fallback: "Options" },
    admin_setup_internal: { key: "nav.admin_setup_internal", fallback: "Internal" },
    user: { key: "nav.user", fallback: "User" },
    logout: { key: "nav.logout", fallback: "Logout" },
    access_denied_admin: { key: "common.access_denied_admin", fallback: "Access denied — admin only." },
    unknown_error: { key: "common.unknown_error", fallback: "Unknown error" },
} as const;

// ============================================================
// ABOUT
// ============================================================

export const ABOUT = {
    title: { key: "about.title", fallback: "About Statisticians Workbench" },
    description: { key: "about.description", fallback: "Build amazing experiences with shadcn/ui and Next.js. Clean design, fast performance." },
    get_started: { key: "about.get_started", fallback: "Get Started" },
    fast_title: { key: "about.fast_title", fallback: "Fast" },
    fast_desc: { key: "about.fast_desc", fallback: "Built on Next.js App Router for optimal performance." },
    modern_title: { key: "about.modern_title", fallback: "Modern UI" },
    modern_desc: { key: "about.modern_desc", fallback: "Accessible components from shadcn/ui, styled with Tailwind CSS." },
    secure_title: { key: "about.secure_title", fallback: "Secure" },
    secure_desc: { key: "about.secure_desc", fallback: "Type‑safe and customizable – you own the component code." },
    access_denied_admin: { key: "common.access_denied_admin", fallback: "Access denied — admin only." },
    unknown_error: { key: "common.unknown_error", fallback: "Unknown error" },
} as const;

// ============================================================
// TOOLS
// ============================================================

export const TOOLS = {
    title: { key: "tools.title", fallback: "Other Tools" },
    visualize: { key: "tools.visualize", fallback: "Visualization Sandbox" },
    my_data: { key: "tools.my_data", fallback: "My Data" },
    upload_data: { key: "tools.upload_data", fallback: "Upload Data" },
    connect_database: { key: "tools.connect_database", fallback: "Connect Database" },
    description: { key: "tools.description", fallback: "Additional utilities and analysis tools will appear here." },
    placeholder: { key: "tools.placeholder", fallback: "Tools page coming soon." },
    access_denied_admin: { key: "common.access_denied_admin", fallback: "Access denied — admin only." },
    unknown_error: { key: "common.unknown_error", fallback: "Unknown error" },
} as const;

// ============================================================
// PASSWORD STRENGTH
// ============================================================

export const PASSWORD_STRENGTH = {
    weak: { key: "password.strength.weak", fallback: "Weak" },
    fair: { key: "password.strength.fair", fallback: "Fair" },
    good: { key: "password.strength.good", fallback: "Good" },
    strong: { key: "password.strength.strong", fallback: "Strong" },
    access_denied_admin: { key: "common.access_denied_admin", fallback: "Access denied — admin only." },
    unknown_error: { key: "common.unknown_error", fallback: "Unknown error" },
} as const;

// ============================================================
// SETTINGS
// ============================================================

export const SETTINGS = {
    title: { key: "settings.title", fallback: "Settings" },
    profile: { title: { key: "settings.profile.title", fallback: "Preferences" } },
    database: { title: { key: "settings.database.title", fallback: "Database Connections" } },
    ai: { title: { key: "settings.ai.title", fallback: "AI Connections" } },
    access_denied_admin: { key: "common.access_denied_admin", fallback: "Access denied — admin only." },
    unknown_error: { key: "common.unknown_error", fallback: "Unknown error" },
} as const;

// ============================================================
// COMPONENTS
// ============================================================

export const COMPONENTS = {
    example_user_badge: { key: "components.example_user_badge", fallback: "Example User" },
    example_user_banner: {
        title: { key: "components.example_user_banner.title", fallback: "EXAMPLE USER MODE" },
        message: { key: "components.example_user_banner.message", fallback: "You are viewing the system in read-only mode. Register for full access to create and modify resources." },
    },
    group_admin_badge: { key: "components.group_admin_badge", fallback: "Group Admin" },
    readonly_wrapper: { key: "components.readonly_wrapper.message", fallback: "Read-only mode - Register for full access to modify this content" },
    access_denied_admin: { key: "common.access_denied_admin", fallback: "Access denied — admin only." },
    unknown_error: { key: "common.unknown_error", fallback: "Unknown error" },
} as const;

// ============================================================
// AI (Common)
// ============================================================

export const AI_COMMON = {
    database: {
        title: { key: "ai.database.title", fallback: "Database Design Assistant" },
        description: { key: "ai.database.description", fallback: "Analyze your database design for indexing, normalisation, relationship, data type, and naming issues." },
        placeholder: { key: "ai.database.placeholder", fallback: "Coming soon. This feature will help you design database schemas using AI." },
    },
    dataclean: {
        title: { key: "ai.dataclean.title", fallback: "Dataset Cleaning Assistant" },
        description: { key: "ai.dataclean.description", fallback: "AI-powered dataset cleaning and preparation." },
        placeholder: { key: "ai.dataclean.placeholder", fallback: "Coming soon. This feature will help you clean and prepare datasets using AI." },
    },
    recipe: {
        title: { key: "ai.recipe.title", fallback: "Analysis Rules Assistant" },
        description: { key: "ai.recipe.description", fallback: "AI-powered recipe and analysis rule generation." },
        placeholder: { key: "ai.recipe.placeholder", fallback: "Coming soon. This feature will help you create analysis recipes using AI." },
    },
    access_denied_admin: { key: "common.access_denied_admin", fallback: "Access denied — admin only." },
    unknown_error: { key: "common.unknown_error", fallback: "Unknown error" },
} as const;

// ============================================================
// GLOBAL SETTINGS
// ============================================================

export const GLOBAL = {
    load_error: { key: "global.load_error", fallback: "Failed to load global settings" },
    invalid_number: { key: "global.invalid_number", fallback: "Please enter a valid positive number for max registrations" },
    invalid_timeout: { key: "global.invalid_timeout", fallback: "Please enter a valid positive number for verification timeout (hours)" },
    invalid_grace_period: { key: "global.invalid_grace_period", fallback: "Please enter a valid positive number for deletion delay (hours)" },
    save_success: { key: "global.save_success", fallback: "Global settings saved" },
    title: { key: "global.title", fallback: "Global Settings" },
    save_button: { key: "global.save_button", fallback: "Save Global Settings" },
    system: {
        title: { key: "global.system.title", fallback: "System Configuration" },
        description: { key: "global.system.description", fallback: "Manage global settings that apply to all users (admin only)." },
    },
    demo_mode: {
        label: { key: "global.demo_mode.label", fallback: "Demo Mode" },
        description: { key: "global.demo_mode.description", fallback: "When enabled, the system runs in demo mode." },
    },
    max_registrations: {
        label: { key: "global.max_registrations.label", fallback: "Maximum User Registrations" },
        placeholder: { key: "global.max_registrations.placeholder", fallback: "Select limit" },
        unlimited: { key: "global.max_registrations.unlimited", fallback: "Unlimited" },
        users: { key: "global.max_registrations.users", fallback: "users" },
        custom: { key: "global.max_registrations.custom", fallback: "Custom (enter below)" },
        custom_placeholder: { key: "global.max_registrations.custom_placeholder", fallback: "Enter a positive number" },
        hint: { key: "global.max_registrations.hint", fallback: "Set a limit on how many users can register." },
    },
    email_timeout: {
        label: { key: "global.email_timeout.label", fallback: "Email Verification Timeout (hours)" },
        hint: { key: "global.email_timeout.hint", fallback: "How many hours the email verification link remains valid." },
    },
    email_sender: {
        label: { key: "global.email_sender.label", fallback: "Email Sender Address" },
        hint: { key: "global.email_sender.hint", fallback: "The email address that verification emails will appear to come from." },
    },
    public_url: {
        label: { key: "global.public_url.label", fallback: "Public URL" },
        hint: { key: "global.public_url.hint", fallback: "The base URL used in email verification links (e.g., https://workbench.example.com)." },
    },
    grace_period: {
        label: { key: "global.grace_period.label", fallback: "Deletion delay (hours)" },
        hint: { key: "global.grace_period.hint", fallback: "Hours before soft-deleted accounts are permanently erased." },
    },
    welcome: {
        label: { key: "global.welcome.label", fallback: "Welcome Message" },
        placeholder: { key: "global.welcome.placeholder", fallback: "Enter a welcome message to display on the login page." },
        hint: { key: "global.welcome.hint", fallback: "This message will appear on the login page. Leave empty to hide it." },
    },
    password_policy: {
        label: { key: "global.password_policy.label", fallback: "Password Policy" },
        select: { key: "global.password_policy.select", fallback: "Select policy" },
        low: { key: "global.password_policy.low", fallback: "Low (min 6 chars)" },
        medium: { key: "global.password_policy.medium", fallback: "Medium (min 8, upper, lower, digit)" },
        high: { key: "global.password_policy.high", fallback: "High (min 10, upper, lower, digit, special)" },
        custom: { key: "global.password_policy.custom", fallback: "Custom" },
        min_length: { key: "global.password_policy.min_length", fallback: "Minimum Length" },
        require_uppercase: { key: "global.password_policy.require_uppercase", fallback: "Require Uppercase" },
        require_lowercase: { key: "global.password_policy.require_lowercase", fallback: "Require Lowercase" },
        require_digit: { key: "global.password_policy.require_digit", fallback: "Require Digit" },
        require_special: { key: "global.password_policy.require_special", fallback: "Require Special Character" },
        min_strength: { key: "global.password_policy.min_strength", fallback: "Minimum Strength (zxcvbn score 0-4)" },
        hint: { key: "global.password_policy.hint", fallback: "Choose the password complexity requirements for user registration and password changes." },
    },
    upload: {
        default_size_label: { key: "global.upload.default_size_label", fallback: "Default Max Upload Size per User (MB)" },
        select_size: { key: "global.upload.select_size", fallback: "Select limit" },
        size_hint: { key: "global.upload.size_hint", fallback: "Maximum total storage per user (0 = unlimited). Applied to new users." },
        default_count_label: { key: "global.upload.default_count_label", fallback: "Default Max Upload Count per User" },
        select_count: { key: "global.upload.select_count", fallback: "Select limit" },
        count_hint: { key: "global.upload.count_hint", fallback: "Maximum number of datasets per user (0 = unlimited). Applied to new users." },
        size_unlimited: { key: "global.upload.size_unlimited", fallback: "Unlimited" },
        size_1_mb: { key: "global.upload.size_1_mb", fallback: "1 MB" },
        size_5_mb: { key: "global.upload.size_5_mb", fallback: "5 MB" },
        size_10_mb: { key: "global.upload.size_10_mb", fallback: "10 MB" },
        size_25_mb: { key: "global.upload.size_25_mb", fallback: "25 MB" },
        size_50_mb: { key: "global.upload.size_50_mb", fallback: "50 MB" },
        size_100_mb: { key: "global.upload.size_100_mb", fallback: "100 MB" },
        size_250_mb: { key: "global.upload.size_250_mb", fallback: "250 MB" },
        size_500_mb: { key: "global.upload.size_500_mb", fallback: "500 MB" },
        size_1_gb: { key: "global.upload.size_1_gb", fallback: "1 GB" },
        count_unlimited: { key: "global.upload.count_unlimited", fallback: "Unlimited" },
        count_1: { key: "global.upload.count_1", fallback: "1" },
        count_5: { key: "global.upload.count_5", fallback: "5" },
        count_10: { key: "global.upload.count_10", fallback: "10" },
        count_25: { key: "global.upload.count_25", fallback: "25" },
        count_50: { key: "global.upload.count_50", fallback: "50" },
        count_100: { key: "global.upload.count_100", fallback: "100" },
        count_250: { key: "global.upload.count_250", fallback: "250" },
        count_500: { key: "global.upload.count_500", fallback: "500" },
        count_1000: { key: "global.upload.count_1000", fallback: "1000" },
    },
    access_denied_admin: { key: "common.access_denied_admin", fallback: "Access denied — admin only." },
    unknown_error: { key: "common.unknown_error", fallback: "Unknown error" },
} as const;

// ============================================================
// VALIDATION
// ============================================================

export const VALIDATION = {
    name_required: { key: "validation.name_required", fallback: "Connection name is required" },
    type_required: { key: "validation.type_required", fallback: "Please select a database type" },
    provider_required: { key: "validation.provider_required", fallback: "Please select a provider" },
    api_key_required: { key: "validation.api_key_required", fallback: "API key is required for this provider" },
    host_required: { key: "validation.host_required", fallback: "Host is required" },
    port_invalid: { key: "validation.port_invalid", fallback: "Port must be between 1 and 65535" },
    database_required: { key: "validation.database_required", fallback: "Database name is required" },
    username_required: { key: "validation.username_required", fallback: "Username is required" },
    password_required: { key: "validation.password_required", fallback: "Password is required" },
    password_min_length: { key: "validation.password.min_length", fallback: "Password must be at least {min} characters long." },
    password_require_uppercase: { key: "validation.password.require_uppercase", fallback: "Password must contain at least one uppercase letter." },
    password_require_lowercase: { key: "validation.password.require_lowercase", fallback: "Password must contain at least one lowercase letter." },
    password_require_digit: { key: "validation.password.require_digit", fallback: "Password must contain at least one digit." },
    password_require_special: { key: "validation.password.require_special", fallback: "Password must contain at least one special character." },
    password_too_weak: { key: "validation.password.too_weak", fallback: "Password is too weak. Please choose a stronger password." },
    access_denied_admin: { key: "common.access_denied_admin", fallback: "Access denied — admin only." },
    unknown_error: { key: "common.unknown_error", fallback: "Unknown error" },
} as const;
/** Heading above a suggested name. Shared by the virtual-dataset concierge and the
 *  recipe concierge: both offer a name as an editable field rather than a chip, so
 *  both need the same three words above it. Flat rather than in a table because two
 *  call sites in two modules read it — the reuse rule's case exactly.
 *
 *  The key string is byte-identical to the declaration this replaced
 *  (`virtual.name_suggestion_heading`), so the Translation table carries the
 *  translations already and no re-import or orphan cleanup is needed. */
export const name_suggestion_heading: TranslationKey = {
    key: "virtual.name_suggestion_heading",
    fallback: "Suggested name — change it if you like",
};

/** The accept button under a suggested name. "Use this name" rather than "Use
 *  these": the field holds one, which is the whole difference from a chip row. */
export const name_suggestion_accept: TranslationKey = {
    key: "virtual.name_suggestion_accept",
    fallback: "Use this name",
};
