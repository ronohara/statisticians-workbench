# src/routers/recipes/translations.py
# ============================================================
# RECIPES ROUTER TRANSLATIONS
# All translation keys used by the recipes router.
# ============================================================

from dataclasses import dataclass


@dataclass
class TranslationKey:
    """A translation key with an English fallback."""
    key: str
    fallback: str


# Error messages
recipes_not_found = TranslationKey(
    "recipes.not_found",
    "Recipe '{id}' not found"
)
recipes_not_owned = TranslationKey(
    "recipes.not_owned",
    "Recipe '{id}' not found or you do not own it"
)
recipes_invalid_stage = TranslationKey(
    "recipes.invalid_stage",
    "Invalid stage for recipe"
)
recipes_no_updates = TranslationKey(
    "recipes.no_updates",
    "No fields to update"
)
recipes_dataset_required = TranslationKey(
    "recipes.dataset_required",
    "Please select a dataset"
)
recipes_name_required = TranslationKey(
    "recipes.name_required",
    "Recipe name is required"
)
recipes_load_error = TranslationKey(
    "recipes.load_error",
    "Failed to load recipes: {error}"
)
recipes_delete_error = TranslationKey(
    "recipes.delete_error",
    "Failed to delete recipe: {error}"
)
recipes_update_error = TranslationKey(
    "recipes.update_error",
    "Failed to update recipe: {error}"
)
recipes_load_datasets_error = TranslationKey(
    "recipes.load_datasets_error",
    "Failed to load datasets: {error}"
)
recipes_schema_error = TranslationKey(
    "recipes.schema_error",
    "Failed to load column schema: {error}"
)
recipes_no_dataset = TranslationKey(
    "recipes.no_dataset",
    "No dataset associated with this recipe"
)
recipes_columns_required = TranslationKey(
    "recipes.columns_required",
    "Please select at least one column"
)
recipes_no_columns_exist = TranslationKey(
    "recipes.no_columns_exist",
    "None of the selected columns exist in the dataset"
)
recipes_visualisation_columns_required = TranslationKey(
    "recipes.visualisation_columns_required",
    "At least one column is required for visualisation"
)
recipes_unknown_stage = TranslationKey(
    "recipes.unknown_stage",
    "Unknown stage type: {stage_type}"
)
recipes_no_stages = TranslationKey(
    "recipes.no_stages",
    "Recipe must have at least one stage"
)
recipes_invalid_stage_type = TranslationKey(
    "recipes.invalid_stage_type",
    "Invalid stage type: {type}. Must be one of: {types}"
)
recipes_stage_not_implemented = TranslationKey(
    "recipes.stage_not_implemented",
    "{stage_type} stage coming soon"
)
recipes_dataset_not_found = TranslationKey(
    "recipes.dataset_not_found",
    "Dataset not found"
)
recipes_execution_not_found = TranslationKey(
    "recipes.execution_not_found",
    "Execution '{id}' not found"
)
recipes_execution_load_error = TranslationKey(
    "recipes.execution_load_error",
    "Failed to load execution: {error}"
)
recipes_executions_load_error = TranslationKey(
    "recipes.executions_load_error",
    "Failed to load executions: {error}"
)
recipes_execute_error = TranslationKey(
    "recipes.execute_error",
    "Failed to execute recipe: {error}"
)

# Success messages
recipes_create_success = TranslationKey(
    "recipes.create_success",
    "Recipe '{name}' created successfully"
)
recipes_update_success = TranslationKey(
    "recipes.update_success",
    "Recipe '{id}' updated successfully"
)
recipes_delete_success = TranslationKey(
    "recipes.delete_success",
    "Recipe '{id}' deleted successfully"
)
recipes_execution_completed = TranslationKey(
    "recipes.execution_completed",
    "Execution completed successfully"
)
recipes_execution_failed = TranslationKey(
    "recipes.execution_failed",
    "Execution failed"
)

# Validation error messages (constraint matrix enforcement)
recipes_validation_failed = TranslationKey(
    "recipes.validation.failed",
    "Recipe validation failed:\n{errors}"
)
recipes_validation_algorithm_required = TranslationKey(
    "recipes.validation.algorithm_required",
    "No analysis method is selected. Choose one in the analysis panel — a recipe needs a statistics stage with an algorithm."
)
recipes_validation_unknown_algorithm = TranslationKey(
    "recipes.validation.unknown_algorithm",
    "'{type}' is not a recognised analysis method. Choose one of: {options}."
)
recipes_validation_unknown_output = TranslationKey(
    "recipes.validation.unknown_output",
    "'{type}' is not a recognised output type. Choose one of: {options}."
)
recipes_validation_unknown_field = TranslationKey(
    "recipes.validation.unknown_field",
    "'{field}' is not a recognised setting for '{type}'. Recognised settings: {options}."
)
recipes_validation_missing_algo_field = TranslationKey(
    "recipes.validation.missing_algo_field",
    "Analysis '{algo}' is missing its '{field}' setting ({label}). Select a column for '{field}' in the analysis panel."
)
recipes_validation_missing_output_field = TranslationKey(
    "recipes.validation.missing_output_field",
    "Output '{output}' is missing its '{field}' setting ({label}). Select a column for '{field}' in the output panel."
)
recipes_validation_unknown_columns = TranslationKey(
    "recipes.validation.unknown_columns",
    "The {stage} stage references column(s) '{columns}' that don't exist in this dataset. Available columns: {available}. Select from the available ones."
)
recipes_validation_wrong_column_type = TranslationKey(
    "recipes.validation.wrong_column_type",
    "Column '{column}' must be {expected} for '{field}' ({label})."
)
recipes_validation_incompatible_algo_output = TranslationKey(
    "recipes.validation.incompatible_algo_output",
    "Analysis '{algo}' produces {result_type} results and cannot be displayed as a '{output}' chart. Change the output type to one compatible with '{algo}': {options}."
)
recipes_validation_insufficient_columns_algo = TranslationKey(
    "recipes.validation.insufficient_columns_algo",
    "This dataset doesn't have the right column types for '{algo}' ({requirement}). Dataset has: {columns}. Choose a dataset with {requirement}, or switch to: {options}."
)
recipes_validation_insufficient_columns_output = TranslationKey(
    "recipes.validation.insufficient_columns_output",
    "This dataset doesn't have the right column types for '{output}' ({requirement}). Dataset has: {columns}. Choose a dataset with {requirement}, or switch to: {options}."
)

# ---- Field labels (used in missing-field validation messages) ----
recipes_field_label_factorColumn = TranslationKey(
    "recipes.field_label.factorColumn",
    "Factor column (grouping variable)"
)
recipes_field_label_responseColumn = TranslationKey(
    "recipes.field_label.responseColumn",
    "Response column (numeric measurement)"
)
recipes_field_label_responseColumn2 = TranslationKey(
    "recipes.field_label.responseColumn2",
    "Second response column (paired measurement)"
)
recipes_field_label_dependentColumn = TranslationKey(
    "recipes.field_label.dependentColumn",
    "Dependent / outcome column"
)
recipes_field_label_independentColumns = TranslationKey(
    "recipes.field_label.independentColumns",
    "Independent / predictor columns"
)
recipes_field_label_xColumn = TranslationKey(
    "recipes.field_label.xColumn",
    "X-axis column"
)
recipes_field_label_yColumn = TranslationKey(
    "recipes.field_label.yColumn",
    "Y-axis column"
)
recipes_field_label_categoryColumn = TranslationKey(
    "recipes.field_label.categoryColumn",
    "Category column (labels)"
)
recipes_field_label_factorColumn2 = TranslationKey(
    "recipes.field_label.factorColumn2",
    "Second factor column (grouping variable)"
)
recipes_field_label_columns = TranslationKey(
    "recipes.field_label.columns",
    "Columns"
)

# ---- Requirement descriptions (used in insufficient-columns messages) ----
recipes_requirement_descriptive = TranslationKey(
    "recipes.requirement.descriptive",
    "at least 1 numeric column"
)
recipes_requirement_correlation = TranslationKey(
    "recipes.requirement.correlation",
    "at least 2 numeric columns"
)
recipes_requirement_t_test_independent = TranslationKey(
    "recipes.requirement.t_test_independent",
    "1 categorical column (for groups) and 1 numeric column (to compare)"
)
recipes_requirement_t_test_paired = TranslationKey(
    "recipes.requirement.t_test_paired",
    "2 numeric columns (paired measurements)"
)
recipes_requirement_anova_one_way = TranslationKey(
    "recipes.requirement.anova_one_way",
    "1 categorical column (factor) and 1 numeric column (response)"
)
recipes_requirement_anova_two_way = TranslationKey(
    "recipes.requirement.anova_two_way",
    "2 categorical columns (two factors) and 1 numeric column (response)"
)
recipes_requirement_linear_regression = TranslationKey(
    "recipes.requirement.linear_regression",
    "at least 2 numeric columns (predictors and outcome)"
)
recipes_requirement_chi_square = TranslationKey(
    "recipes.requirement.chi_square",
    "2 categorical columns"
)
recipes_requirement_bar = TranslationKey(
    "recipes.requirement.bar",
    "1 categorical column (x-axis) and 1 numeric column (y-axis)"
)
recipes_requirement_pie = TranslationKey(
    "recipes.requirement.pie",
    "1 categorical column (labels)"
)
recipes_requirement_line = TranslationKey(
    "recipes.requirement.line",
    "2 numeric columns (x and y)"
)
recipes_requirement_scatter = TranslationKey(
    "recipes.requirement.scatter",
    "2 numeric columns (x and y)"
)
recipes_requirement_distribution = TranslationKey(
    "recipes.requirement.distribution",
    "1 numeric column"
)
recipes_requirement_histogram = TranslationKey(
    "recipes.requirement.histogram",
    "1 numeric column (x-axis)"
)
recipes_requirement_table = TranslationKey(
    "recipes.requirement.table",
    "any columns"
)
recipes_requirement_none = TranslationKey(
    "recipes.requirement.none",
    "no output required"
)
recipes_requirement_area = TranslationKey(
    "recipes.requirement.area",
    "2 numeric columns (x and y)"
)
recipes_requirement_donut = TranslationKey(
    "recipes.requirement.donut",
    "1 categorical column (labels)"
)
recipes_requirement_hbar = TranslationKey(
    "recipes.requirement.hbar",
    "1 categorical column (y-axis) and 1 numeric column (x-axis)"
)

# ---- Column type labels ----
recipes_column_type_categorical = TranslationKey(
    "recipes.column_type.categorical",
    "categorical"
)
recipes_column_type_numeric = TranslationKey(
    "recipes.column_type.numeric",
    "numeric"
)

# ---- Result type labels (for cross-stage compatibility messages) ----
recipes_result_type_tabular = TranslationKey(
    "recipes.result_type.tabular",
    "tabular"
)
recipes_result_type_numeric = TranslationKey(
    "recipes.result_type.numeric",
    "numeric"
)

# ---- Technique names (algorithm labels) ----
# Reuses the frontend's `recipes.technique_*` keys — identical key + fallback,
# so the two codebases share one DB row (no drift).
recipes_technique_descriptive = TranslationKey(
    "recipes.technique_descriptive",
    "Descriptive Statistics"
)
recipes_technique_correlation = TranslationKey(
    "recipes.technique_correlation",
    "Correlation Matrix"
)
recipes_technique_t_test_independent = TranslationKey(
    "recipes.technique_t_test_independent",
    "Independent t-test"
)
recipes_technique_t_test_paired = TranslationKey(
    "recipes.technique_t_test_paired",
    "Paired t-test"
)
recipes_technique_anova_one_way = TranslationKey(
    "recipes.technique_anova_one_way",
    "One-way ANOVA"
)
recipes_technique_anova_two_way = TranslationKey(
    "recipes.technique_anova_two_way",
    "Two-way ANOVA"
)
recipes_technique_linear_regression = TranslationKey(
    "recipes.technique_linear_regression",
    "Linear Regression"
)
recipes_technique_chi_square = TranslationKey(
    "recipes.technique_chi_square",
    "Chi-square Test"
)

# ---- Recipe-transform association endpoints (4.5.1) ----
recipes_transforms_connect_success = TranslationKey(
    "recipes.transforms.connect_success",
    "Transform connected to recipe"
)
recipes_transforms_disconnect_success = TranslationKey(
    "recipes.transforms.disconnect_success",
    "Transform disconnected from recipe"
)
recipes_transforms_not_found = TranslationKey(
    "recipes.transforms.not_found",
    "Transform '{id}' not found or does not belong to this recipe's dataset"
)
recipes_transforms_dataset_mismatch = TranslationKey(
    "recipes.transforms.dataset_mismatch",
    "Transform '{id}' does not belong to dataset '{dataset_id}'"
)
recipes_transforms_load_error = TranslationKey(
    "recipes.transforms.load_error",
    "Failed to load connected transforms"
)

# ---- Data preparation stage execution (Phase 5) ----
recipes_preparation_rule_not_found = TranslationKey(
    "recipes.preparation.rule_not_found",
    "Rule '{rule_id}' not found"
)
recipes_preparation_rule_failed = TranslationKey(
    "recipes.preparation.rule_failed",
    "Rule '{rule_id}': {error}"
)
recipes_preparation_all_rules_failed = TranslationKey(
    "recipes.preparation.all_rules_failed",
    "All rules failed: {errors}"
)
recipes_preparation_rules_applied = TranslationKey(
    "recipes.preparation.rules_applied",
    "Applied {count} preparation rules"
)

# ---- Execution pipeline errors ----
recipes_execution_preparation_failed = TranslationKey(
    "recipes.execution.preparation_failed",
    "Preparation stage failed"
)
recipes_execution_preparation_error = TranslationKey(
    "recipes.execution.preparation_error",
    "Preparation stage failed: {error}"
)
recipes_execution_unknown_stage = TranslationKey(
    "recipes.execution.unknown_stage",
    "Unknown stage type: {stage_type}"
)
recipes_execution_error = TranslationKey(
    "recipes.execution.error",
    "Recipe execution error: {error}"
)

# ---- AI Recipe Session endpoints (Phase 1.4) ----
recipes_ai_session_not_found = TranslationKey(
    "recipes.ai_session.not_found",
    "AI recipe session not found"
)
recipes_ai_session_unauthorized = TranslationKey(
    "recipes.ai_session.unauthorized",
    "You do not have access to this AI recipe session"
)
recipes_ai_session_create_error = TranslationKey(
    "recipes.ai_session.create_error",
    "Failed to create AI recipe session"
)
recipes_ai_session_load_error = TranslationKey(
    "recipes.ai_session.load_error",
    "Failed to load AI recipe session"
)
recipes_ai_session_delete_error = TranslationKey(
    "recipes.ai_session.delete_error",
    "Failed to delete AI recipe session"
)
recipes_ai_session_save_error = TranslationKey(
    "recipes.ai_session.save_error",
    "Failed to save recipe from AI session"
)
# ---- Inline keys migrated from router call sites (P1) ----
ai_recipe_session_name_required = TranslationKey(
    "ai_recipe.session_name_required",
    "A name is required"
)
ai_recipe_invalid_decision = TranslationKey(
    "ai_recipe.invalid_decision",
    "Invalid decision."
)
ai_recipe_llm_error = TranslationKey(
    "ai_recipe.llm_error",
    "AI service error: {error}"
)
recipes_share_enabled = TranslationKey(
    "recipes.share.enabled",
    "Recipe shared successfully"
)
recipes_share_disabled = TranslationKey(
    "recipes.share.disabled",
    "Recipe is now private"
)
statistics_anova_computation_failed = TranslationKey(
    "statistics.anova_computation_failed",
    "Two-way ANOVA computation failed: {error}"
)
statistics_anova_needs_three_groups = TranslationKey(
    "statistics.anova_needs_three_groups",
    "One-way ANOVA requires 3 or more groups (found {n}). For 2 groups, use the independent t-test."
)
error_execution_cannot_cancel = TranslationKey(
    "error.execution.cannot_cancel",
    "Cannot cancel an execution that is already {status}"
)
statistics_column_must_be_numeric = TranslationKey(
    "statistics.column_must_be_numeric",
    "Column '{col}' must be numeric"
)
statistics_column_not_found = TranslationKey(
    "statistics.column_not_found",
    "Column '{col}' not found"
)
statistics_computation_failed = TranslationKey(
    "statistics.computation_failed",
    "Statistics computation failed: {error}"
)
recipes_data_selection_error = TranslationKey(
    "recipes.data_selection_error",
    "Data selection failed: {error}"
)
statistics_each_group_two_observations = TranslationKey(
    "statistics.each_group_two_observations",
    "Each group must have at least 2 observations"
)
execution_executing_stage = TranslationKey(
    "execution.executing_stage",
    "Executing stage: {stage}"
)
statistics_factor_column_not_found = TranslationKey(
    "statistics.factor_column_not_found",
    "Factor {factor} column '{col}' not found"
)
statistics_group_column_required_anova = TranslationKey(
    "statistics.group_column_required_anova",
    "A categorical group column with 3 or more levels is required for one-way ANOVA"
)
statistics_group_column_required_ttest = TranslationKey(
    "statistics.group_column_required_ttest",
    "A categorical group column with exactly two levels is required for independent t-test"
)
statistics_group_fewer_than_two = TranslationKey(
    "statistics.group_fewer_than_two",
    "Group '{group}' has fewer than 2 observations"
)
statistics_group_must_have_two_levels = TranslationKey(
    "statistics.group_must_have_two_levels",
    "Group column '{group}' must have exactly 2 levels (found {n})"
)
error_dataset_load_failed = TranslationKey(
    "error.dataset.load_failed",
    "Failed to load dataset: {error}"
)
execution_loaded_rows = TranslationKey(
    "execution.loaded_rows",
    "Loaded {rows} rows, {columns} columns"
)
execution_loading_dataset = TranslationKey(
    "execution.loading_dataset",
    "Loading dataset..."
)
ai_recipe_message_required = TranslationKey(
    "ai_recipe.message_required",
    "A message is required"
)
statistics_need_five_observations_chi = TranslationKey(
    "statistics.need_five_observations_chi",
    "Need at least 5 complete observations"
)
statistics_need_observations_regression = TranslationKey(
    "statistics.need_observations_regression",
    "Need at least {n} complete observations"
)
statistics_need_ten_observations_anova = TranslationKey(
    "statistics.need_ten_observations_anova",
    "Need at least 10 complete observations for two-way ANOVA"
)
statistics_need_three_pairs = TranslationKey(
    "statistics.need_three_pairs",
    "Need at least 3 complete pairs for paired t-test"
)
statistics_need_two_categories_chi = TranslationKey(
    "statistics.need_two_categories_chi",
    "Both columns need at least 2 categories"
)
statistics_need_two_numeric_correlation = TranslationKey(
    "statistics.need_two_numeric_correlation",
    "Need at least 2 numeric columns for correlation"
)
statistics_need_two_valid_numeric = TranslationKey(
    "statistics.need_two_valid_numeric",
    "Need at least 2 valid numeric columns"
)
recipes_preparation_no_db_pool = TranslationKey(
    "recipes.preparation.no_db_pool",
    "Database pool not available for preparation stage"
)
statistics_no_valid_data_after_dropna = TranslationKey(
    "statistics.no_valid_data_after_dropna",
    "No valid data after dropping NaN"
)
statistics_no_valid_numeric = TranslationKey(
    "statistics.no_valid_numeric",
    "No valid numeric columns provided"
)
statistics_non_numeric_column = TranslationKey(
    "statistics.non_numeric_column",
    "Non-numeric column"
)
statistics_not_computed = TranslationKey(
    "statistics.not_computed",
    "Not computed"
)
error_dataset_not_found = TranslationKey(
    "error.dataset.not_found",
    "Dataset '{id}' not found or not accessible"
)
execution_not_found = TranslationKey(
    "execution.not_found",
    "Execution not found"
)
error_database_pool_not_initialized = TranslationKey(
    "error.database.pool_not_initialized",
    "Database pool not initialized"
)
error_preparation_rule_not_found = TranslationKey(
    "error.preparation.rule_not_found",
    "Preparation rule '{id}' not found for this dataset"
)
statistics_select_dependent_independent = TranslationKey(
    "statistics.select_dependent_independent",
    "Select at least 2 numeric columns: first = dependent, remaining = independent"
)
statistics_select_dependent_var = TranslationKey(
    "statistics.select_dependent_var",
    "Select one numeric dependent variable column"
)
statistics_select_one_numeric_ttest = TranslationKey(
    "statistics.select_one_numeric_ttest",
    "Select one numeric column for the independent t-test"
)
statistics_select_two_categorical_chi = TranslationKey(
    "statistics.select_two_categorical_chi",
    "Select exactly two categorical columns"
)
statistics_select_two_numeric_paired = TranslationKey(
    "statistics.select_two_numeric_paired",
    "Select exactly two numeric columns for the paired t-test"
)
execution_starting_analysis = TranslationKey(
    "execution.starting_analysis",
    "Starting analysis stages..."
)
statistics_two_factors_required = TranslationKey(
    "statistics.two_factors_required",
    "Two factors are required for two-way ANOVA"
)
recipes_unsupported_chart_type = TranslationKey(
    "recipes.unsupported_chart_type",
    "Unsupported chart type: {chart_type}"
)
recipes_visualisation_error = TranslationKey(
    "recipes.visualisation_error",
    "Visualisation failed: {error}"
)
recipes_visualisation_generated = TranslationKey(
    "recipes.visualisation_generated",
    "Visualisation generated successfully"
)
recipes_scatter_two_numeric = TranslationKey(
    "recipes.scatter_two_numeric",
    "Scatter plot requires two numeric columns"
)
recipes_scatter_two_columns = TranslationKey(
    "recipes.scatter_two_columns",
    "Scatter plot requires at least two columns"
)
recipes_histogram_numeric = TranslationKey(
    "recipes.histogram_numeric",
    "Histogram requires a numeric column"
)
recipes_histogram_no_columns = TranslationKey(
    "recipes.histogram_no_columns",
    "Histogram requires at least one column"
)
recipes_distribution_no_columns = TranslationKey(
    "recipes.distribution_no_columns",
    "Distribution chart requires at least one column"
)


# ── Scoreboard piece sentences (design §3.2) ────────────────────────────────
#
# The scoreboard is a pure function: it has no pool and no language, so it
# cannot translate. It emits these *keys*, and the boundary — where a pool and a
# language both exist — resolves them. That is why they are declared here and
# referenced from a mapping, rather than being sentences typed inside
# `compute_scoreboard`.
#
# Nine declarations and not seven: the three conditional sentences are three
# different sentences about three different problems ("choose a known analysis
# method" is not "choose the required columns"), so three keys is the honest
# count. The condition is carried by the key name — `output_unknown` versus
# `output_incompatible` — rather than by a reason field every consumer would
# have to interpret.
#
# `recipes.scoreboard.technique_fields.what` and `...output_fields.what` say
# different things ("required columns" versus "output columns") and so are two
# keys; Item 20 later shares one *heading* between them, which is a different
# sentence for a different place.
recipes_scoreboard_dataset_what = TranslationKey(
    "recipes.scoreboard.dataset.what",
    "Select a dataset"
)
recipes_scoreboard_technique_what = TranslationKey(
    "recipes.scoreboard.technique.what",
    "Choose an analysis method"
)
recipes_scoreboard_technique_unknown_what = TranslationKey(
    "recipes.scoreboard.technique_unknown.what",
    "Choose a known analysis method"
)
recipes_scoreboard_technique_fields_what = TranslationKey(
    "recipes.scoreboard.technique_fields.what",
    "Choose the required columns"
)
recipes_scoreboard_output_what = TranslationKey(
    "recipes.scoreboard.output.what",
    "Choose an output type"
)
recipes_scoreboard_output_unknown_what = TranslationKey(
    "recipes.scoreboard.output_unknown.what",
    "Choose a known output type"
)
recipes_scoreboard_output_incompatible_what = TranslationKey(
    "recipes.scoreboard.output_incompatible.what",
    "Choose a compatible output type"
)
recipes_scoreboard_output_fields_what = TranslationKey(
    "recipes.scoreboard.output_fields.what",
    "Choose the output columns"
)
recipes_scoreboard_name_what = TranslationKey(
    "recipes.scoreboard.name.what",
    "Name the recipe"
)


#: Which declaration answers which pending piece's `what`.
#
#: The scoreboard emits the *piece name* (`"output"`), not a sentence and not a
#: key — it is pure and knows neither a language nor a pool. This map is how the
#: boundary turns a piece name into the declared key, which is the shape
#: AGENTS.md's dynamic-key rule prescribes: a key that depends on a runtime value
#: is selected from a module-local mapping built from the declarations, never
#: assembled by formatting a string.
#
#: Three names map to sentences that are *not* the piece's own. `technique_unknown`
#: and `output_unknown` are what a piece says once a decision exists but names
#: something no definition knows; `output_incompatible` is what it says when the
#: decision is real but the technique forbids it. Those are three different
#: sentences about three different problems, which is why the vocabulary carries
#: them rather than a single "choose again".
#: Keyed by the **key string**, which is what a pending entry carries in `what`.
#: Not by the piece name: `technique` appears with three different sentences
#: (chosen, unnamed, chosen-but-unknown), so a piece-keyed map would lose two of
#: them. This mirrors `DATASETS[…]` in `datasets/translations.py`, which the
#: virtual scoreboard indexes the same way.
RECIPE_SCOREBOARD_KEYS = {
    recipes_scoreboard_dataset_what.key: recipes_scoreboard_dataset_what,
    recipes_scoreboard_technique_what.key: recipes_scoreboard_technique_what,
    recipes_scoreboard_technique_unknown_what.key: recipes_scoreboard_technique_unknown_what,
    recipes_scoreboard_technique_fields_what.key: recipes_scoreboard_technique_fields_what,
    recipes_scoreboard_output_what.key: recipes_scoreboard_output_what,
    recipes_scoreboard_output_unknown_what.key: recipes_scoreboard_output_unknown_what,
    recipes_scoreboard_output_incompatible_what.key: recipes_scoreboard_output_incompatible_what,
    recipes_scoreboard_output_fields_what.key: recipes_scoreboard_output_fields_what,
    recipes_scoreboard_name_what.key: recipes_scoreboard_name_what,
}


# ---------------------------------------------------------------
# Chip-row headings — one per askable piece
# ---------------------------------------------------------------
#
# Only the four `ask` pieces produce a chip row, and each row needs a heading
# saying what is being asked. Declared here rather than in the page because the
# boundary is where a pool and a language exist: the row receives `headingText`,
# the same way it receives `whatText` for the scoreboard's pending pieces.
#
# Three declarations for four pieces, deliberately. `technique_fields` and
# `output_fields` both ask "Which columns?", and the translation rule is to reuse
# one key when the fallback text is identical — two declarations of one phrase is
# the drift the frontend linter reports as DUPLICATE-FALLBACK. So the map below
# points both at `columns`, and the piece→declaration shape is kept so a piece
# that gains a chip row later fails on a missing entry rather than rendering an
# unheaded row.
recipes_chip_heading_technique = TranslationKey(
    "recipes.chip.heading.technique",
    "Which analysis method?"
)
recipes_chip_heading_output = TranslationKey(
    "recipes.chip.heading.output",
    "Which output?"
)
recipes_chip_heading_columns = TranslationKey(
    "recipes.chip.heading.columns",
    "Which columns?"
)

