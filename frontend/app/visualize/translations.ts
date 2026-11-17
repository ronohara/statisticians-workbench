// app/visualize/translations.ts
// ============================================================
// VISUALIZE MODULE TRANSLATIONS
// All translation keys used by the visualization sandbox page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const VISUALIZE = {
    load_error: { key: "visualize.load_error", fallback: "Failed to load visualization types" },
    sample_generated: { key: "visualize.sample_generated", fallback: "Sample data generated" },
    download_success: { key: "visualize.download_success", fallback: "Table downloaded as PNG" },
    download_error: { key: "visualize.download_error", fallback: "Failed to download table" },
    no_data: { key: "visualize.no_data", fallback: "No data to visualize. Generate sample data or paste JSON." },
    unsupported: { key: "visualize.unsupported", fallback: "Visualization type not yet implemented" },
    invalid_data: { key: "visualize.invalid_data", fallback: "Invalid data for text table. Expected columns and rows." },
    download_png: { key: "visualize.download_png", fallback: "Download as PNG" },
    save_no_data: { key: "visualize.save_no_data", fallback: "No data to save. Please generate or paste data." },
    save_error: { key: "visualize.save_error", fallback: "Failed to save" },
    save_success: { key: "visualize.save_success", fallback: "Visualization saved successfully" },
    title: { key: "visualize.title", fallback: "Visualization Sandbox" },
    no_types: { key: "visualize.no_types", fallback: "No visualization types defined. Please contact an administrator." },
    description: { key: "visualize.description", fallback: "Select a visualization type, generate sample data, adjust parameters, and preview." },
    config: { key: "visualize.config", fallback: "Configuration" },
    type: { key: "visualize.type", fallback: "Visualization Type" },
    select_type: { key: "visualize.select_type", fallback: "Select type" },
    data: { key: "visualize.data", fallback: "Data (JSON)" },
    generate_sample: { key: "visualize.generate_sample", fallback: "Generate Sample" },
    data_placeholder: { key: "visualize.data_placeholder", fallback: "Paste JSON data here or generate sample" },
    parameters: { key: "visualize.parameters", fallback: "Parameters" },
    unsupported_parameter: { key: "visualize.unsupported_parameter", fallback: "Unsupported type" },
    preview: { key: "visualize.preview", fallback: "Preview" },
    save_instance: { key: "visualize.save_instance", fallback: "Save Instance" },

    // Sample data labels
    sample_sales: { key: "visualize.sample_sales", fallback: "Sales" },
    sample_expenses: { key: "visualize.sample_expenses", fallback: "Expenses" },
    sample_item: { key: "visualize.sample_item", fallback: "Item" },
    sample_value: { key: "visualize.sample_value", fallback: "Value" },
} as const;