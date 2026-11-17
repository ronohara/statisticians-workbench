// components/recipe/translations.ts
// ============================================================
// RECIPE COMPONENT MODULE TRANSLATIONS
// Shared user-visible strings for recipe components.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const VISUALISATION_RESULT = {
    no_visualisation_data: { key: "recipes.no_visualisation_data", fallback: "No visualisation data available" },
    visualisation_raw_data: { key: "recipes.visualisation_raw_data", fallback: "Visualisation data:" },
    visualisation_distribution: { key: "recipes.visualisation.distribution", fallback: "Distribution" },
    visualisation_trend: { key: "recipes.visualisation.trend", fallback: "Trend" },
    visualisation_data_points: { key: "recipes.visualisation.data_points", fallback: "Data points" },
    chart_x_axis: { key: "recipes.chart.x_axis", fallback: "X" },
    chart_y_axis: { key: "recipes.chart.y_axis", fallback: "Y" },
    chart_value: { key: "recipes.chart.value", fallback: "Value" },
    chart_count: { key: "recipes.chart.count", fallback: "Count" },
    chart_category: { key: "recipes.chart.category", fallback: "Category" },
} as const;
