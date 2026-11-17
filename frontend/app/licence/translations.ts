// app/licence/translations.ts
// ============================================================
// LICENCE PAGE TRANSLATIONS
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const LICENCE = {
    title: { key: "licence.title", fallback: "Licence Status" },
    description: { key: "licence.description", fallback: "Current feature licence and tier information." },
    load_error: { key: "licence.load_error", fallback: "Failed to load licence information." },
    admin_required: { key: "licence.admin_required", fallback: "You must be an admin to view licence information." },
    tier_label: { key: "licence.tier_label", fallback: "Tier" },
    open_source_message: { key: "licence.open_source_message", fallback: "This installation is running in open-source mode. Contact Sentuny to upgrade to a corporate licence." },
    features_label: { key: "licence.features_label", fallback: "Enabled Features" },
    no_features: { key: "licence.no_features", fallback: "No gated features are currently enabled." },
    details_label: { key: "licence.details_label", fallback: "Licence Details" },
    issued_to_label: { key: "licence.issued_to_label", fallback: "Issued to" },
    issued_at_label: { key: "licence.issued_at_label", fallback: "Issued" },
    expires_at_label: { key: "licence.expires_at_label", fallback: "Expires" },
    max_users_label: { key: "licence.max_users_label", fallback: "Licensed users" },

    // Upload / management
    upload_title: { key: "licence.upload_title", fallback: "Upload Licence File" },
    preview_title: { key: "licence.preview_title", fallback: "Licence Preview" },
    preview_invalid: { key: "licence.preview_invalid", fallback: "Invalid licence file." },
    preview_error: { key: "licence.preview_error", fallback: "Failed to validate licence file." },
    install_button: { key: "licence.install_button", fallback: "Install Licence" },
    install_no_file: { key: "licence.install_no_file", fallback: "No file selected." },
    install_success: { key: "licence.install_success", fallback: "Licence installed successfully." },
    install_error: { key: "licence.install_error", fallback: "Failed to install licence." },
    delete_title: { key: "licence.delete_title", fallback: "Remove Licence" },
    delete_button: { key: "licence.delete_button", fallback: "Remove Licence" },
    delete_confirm: { key: "licence.delete_confirm", fallback: "This will revert the system to open-source mode. All gated features will be disabled. You can restore them by installing a new licence." },
    delete_yes: { key: "licence.delete_yes", fallback: "Yes, remove licence" },
    delete_no: { key: "licence.delete_no", fallback: "Cancel" },
    delete_success: { key: "licence.delete_success", fallback: "Licence removed. Running in open-source mode." },
    delete_error: { key: "licence.delete_error", fallback: "Failed to remove licence." },
} as const;
