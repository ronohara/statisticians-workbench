// app/recipes/executions/[id]/translations.ts
// ============================================================
// RECIPE EXECUTION RESULTS MODULE TRANSLATIONS
// All translation keys used by the execution results page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const EXECUTION_RESULTS = {
    // Page title
    execution_title: { key: "recipes.execution_title", fallback: "Execution Results" },
    recipe_label: { key: "recipes.recipe_label", fallback: "Recipe" },

    // Status
    execution_status: { key: "recipes.execution_status", fallback: "Status" },
    execution_progress: { key: "recipes.execution_progress", fallback: "Progress" },
    execution_started: { key: "recipes.execution_started", fallback: "Started" },
    execution_error: { key: "recipes.execution_error", fallback: "Error" },

    // Status badges
    status_pending: { key: "recipes.status.pending", fallback: "Pending" },
    status_running: { key: "recipes.status.running", fallback: "Running" },
    status_completed: { key: "recipes.status.completed", fallback: "Completed" },
    status_failed: { key: "recipes.status.failed", fallback: "Failed" },
    status_cancelled: { key: "recipes.status.cancelled", fallback: "Cancelled" },

    // Preparation rules
    preparation_rules_applied: { key: "recipes.preparation_rules_applied", fallback: "Preparation Rules Applied" },
    preparation_rules_applied_title: { key: "recipes.preparation_rules_applied_title", fallback: "Preparation Rules Applied" },
    preparation_rules_applied_description: { key: "recipes.preparation_rules_applied_description", fallback: "Rules were applied in the order shown below before analysis stages." },
    rows_before: { key: "recipes.rows_before", fallback: "Rows" },
    rows_after: { key: "recipes.rows_after", fallback: "Rows after" },
    columns_before: { key: "recipes.columns_before", fallback: "Columns" },
    columns_after: { key: "recipes.columns_after", fallback: "Columns" },
    total_rules_applied: { key: "recipes.total_rules_applied", fallback: "Total rules applied" },
    rules_applied_label: { key: "recipes.rules_applied_label", fallback: "{count} rules applied:" },

    // Stage results
    execution_stage_results: { key: "recipes.execution_stage_results", fallback: "Stage Results" },
    stage_number: { key: "recipes.stage_number", fallback: "Stage {number}" },

    // Visualisation
    no_visualisation_data: { key: "recipes.no_visualisation_data", fallback: "No visualisation data available" },
    visualisation_raw_data: { key: "recipes.visualisation_raw_data", fallback: "Visualisation data:" },
    visualisation_distribution: { key: "recipes.visualisation.distribution", fallback: "Distribution" },
    visualisation_trend: { key: "recipes.visualisation.trend", fallback: "Trend" },
    visualisation_data_points: { key: "recipes.visualisation.data_points", fallback: "Data points" },
    visualisation_type_label: { key: "recipes.visualisation.type_label", fallback: "Type" },
    visualisation_columns_label: { key: "recipes.visualisation.columns_label", fallback: "Columns" },
    chart_x_axis: { key: "recipes.chart.x_axis", fallback: "X" },
    chart_y_axis: { key: "recipes.chart.y_axis", fallback: "Y" },
    chart_value: { key: "recipes.chart.value", fallback: "Value" },
    chart_count: { key: "recipes.chart.count", fallback: "Count" },
    chart_category: { key: "recipes.chart.category", fallback: "Category" },

    // Buttons
    back_to_recipe: { key: "recipes.back_to_recipe", fallback: "Back to Recipe" },
    export_results: { key: "recipes.export_results", fallback: "Export Results" },
    cancel_button: { key: "recipes.cancel_button", fallback: "Kill" },
    cancel_success: { key: "recipes.cancel_success", fallback: "Execution cancelled" },
    cancel_error: { key: "recipes.cancel_error", fallback: "Failed to cancel execution" },

    // Error messages
    execution_not_found: { key: "recipes.execution_not_found", fallback: "Execution '{id}' not found" },
    execution_load_error: { key: "recipes.execution_load_error", fallback: "Failed to load execution: {error}" },
} as const;