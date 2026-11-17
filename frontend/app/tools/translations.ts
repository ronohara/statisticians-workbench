// app/tools/translations.ts
// ============================================================
// TOOLS MODULE TRANSLATIONS
// All translation keys used by the tools page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const TOOLS = {
    title: { key: "tools.title", fallback: "Other Tools" },
    visualize: { key: "tools.visualize", fallback: "Visualization Sandbox" },
    my_data: { key: "tools.my_data", fallback: "My Data" },
    manage_data: { key: "tools.manage_data", fallback: "Collect Data" },
    all_datasets: { key: "tools.all_datasets", fallback: "All Datasets" },
    uploads_list: { key: "tools.uploads_list", fallback: "Uploads (csv, Excel)" },
    notebooks: { key: "tools.notebooks", fallback: "Notebooks" },
    upload_csv_excel: { key: "tools.upload_csv_excel", fallback: "Upload CSV / Excel" },
    connect_database: { key: "tools.connect_database", fallback: "Connect Database" },
    import_notebook: { key: "tools.import_notebook", fallback: "Import Notebook" },
    description: { key: "tools.description", fallback: "Additional utilities and analysis tools will appear here." },
    placeholder: { key: "tools.placeholder", fallback: "Tools page coming soon." },
} as const;
