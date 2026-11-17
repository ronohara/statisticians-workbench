// app/datasets/upload/translations.ts
// ============================================================
// DATASET UPLOAD MODULE TRANSLATIONS
// All translation keys used by the dataset upload page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const DATASET_UPLOAD = {
        // The escalation control (AI limits plan, Item 12 / D6). It appears only after a
        // describe call timed out, which is why none of these names a "retry" button: the
        // control IS the retry, with a value the user can see and change.
        escalation_label: { key: "datasets.upload.escalation_label", fallback: "Try again with (seconds)" },
        escalation_failed_at: { key: "datasets.upload.escalation_failed_at", fallback: "The description timed out after {seconds} seconds." },
        escalation_hint: { key: "datasets.upload.escalation_hint", fallback: "Only this attempt uses it. If this model usually needs longer, tune the connection's model settings instead of raising this each time." },
        escalation_retry: { key: "datasets.upload.escalation_retry", fallback: "Try again" },
        escalation_invalid: { key: "datasets.upload.escalation_invalid", fallback: "Enter a whole number of seconds between 1 and {max}" },
    title: { key: "datasets.upload.title", fallback: "Upload Data" },
    no_connections: { key: "datasets.upload.no_connections", fallback: "You need to define at least one AI connection to generate descriptions." },
    history: { key: "datasets.upload.history", fallback: "Upload History" },
    no_datasets: { key: "datasets.upload.no_datasets", fallback: "No datasets yet" },
    card_title: { key: "datasets.upload.card_title", fallback: "Upload and Describe" },
    name_label: { key: "datasets.upload.name_label", fallback: "Data Name" },
    name_placeholder: { key: "datasets.upload.name_placeholder", fallback: "My Data" },
    description_label: { key: "datasets.upload.description_label", fallback: "Description (optional)" },
    description_placeholder: { key: "datasets.upload.description_placeholder", fallback: "Brief description of this data" },
    file_label: { key: "datasets.upload.file_label", fallback: "File" },
    file_selected: { key: "datasets.upload.file_selected", fallback: "Selected file" },
    shared_label: { key: "datasets.upload.shared_label", fallback: "Share with group" },
    shared_description: { key: "datasets.upload.shared_description", fallback: "Make this data available to other users in your group." },
    shared_group_hint: { key: "datasets.upload.shared_group_hint", fallback: "Group: {group} - {description}" },
    file_too_large: { key: "datasets.upload.file_too_large", fallback: "File exceeds the maximum upload size of {max}MB. The upload is not allowed." },
    limit_reached: { key: "datasets.upload.limit_reached", fallback: "Limit reached" },
    limit_reached_message: { key: "datasets.upload.limit_reached_message", fallback: "You have reached the maximum number of datasets allowed ({count})." },
    upload_button: { key: "datasets.upload.upload_button", fallback: "Upload" },
    generate_description: { key: "datasets.upload.generate_description", fallback: "Generate Description" },
    no_file: { key: "datasets.upload.no_file", fallback: "Please select a file first." },
    no_name: { key: "datasets.upload.no_name", fallback: "Please enter a dataset name." },
    error: { key: "datasets.upload.error", fallback: "Failed to upload dataset" },
    success: { key: "datasets.upload.success", fallback: "Dataset '{name}' uploaded successfully" },
    select_dataset: { key: "datasets.upload.select_dataset", fallback: "Please upload or select a dataset first." },
    connection_not_found: { key: "datasets.upload.connection_not_found", fallback: "Connection not found. Please select a valid AI connection." },
} as const;