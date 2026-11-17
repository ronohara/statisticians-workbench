// frontend/lib/recipe-model.ts
// ============================================================
// Client-side recipe constraint model + pure validator.
//
// This is the frontend twin of `backend/src/routers/recipes/constraints.py`.
// The model is fetched once from `GET /api/recipes/recipe-model` and the
// validator runs entirely over that served data — no per-technique branches,
// no hardcoded column config. It returns the same `{errors, warnings}` shape
// the backend produces, with every issue carrying `{key, fallback, params}`
// for translation.
// ============================================================

// ============================================================
// Model types (mirror the `/api/recipes/recipe-model` JSON)
// ============================================================

export interface TranslationRef {
    key: string;
    fallback: string;
}

export interface FieldDef {
    label: TranslationRef;
    columnType: "numeric" | "categorical" | "any";
    multi: boolean;
}

export interface AlgorithmDef {
    label: TranslationRef;
    description: TranslationRef;
    fields: string[];
    minCategorical: number;
    minNumeric: number;
    compatibleOutputs: string[];
}

export interface OutputDef {
    description: TranslationRef;
    fields: string[];
    minCategorical: number;
    minNumeric: number;
}

export interface RecipeModel {
    fields: Record<string, FieldDef>;
    algorithms: Record<string, AlgorithmDef>;
    outputs: Record<string, OutputDef>;
}

// ============================================================
// Input state types (structurally compatible with
// `components/recipe/types.ts` RecipeColumn / RecipeAlgorithmState /
// RecipeOutputState).
// ============================================================

export interface ModelColumn {
    name: string;
    isNumeric: boolean;
    isCategorical: boolean;
}

export interface ModelAlgorithmState {
    algorithmType?: string | null;
    config?: Record<string, unknown> | null;
}

export interface ModelOutputState {
    outputType?: string | null;
    config?: Record<string, unknown> | null;
}

export interface RecipeValidationState {
    columns: ModelColumn[];
    algorithm: ModelAlgorithmState | null;
    output: ModelOutputState | null;
}

// ============================================================
// Issue / result types (mirror constraints.ValidationIssue)
// ============================================================

export type IssueSource = "dataset" | "algorithm" | "output" | "compatibility";

export interface ValidationIssue {
    source: IssueSource;
    field?: string;
    key: string;
    fallback: string;
    params?: Record<string, unknown>;
}

export interface ValidationResult {
    errors: ValidationIssue[];
    warnings: ValidationIssue[];
}

// ============================================================
// Fetch-once model cache
// ============================================================

let cachedModel: RecipeModel | null = null;
let pendingFetch: Promise<RecipeModel> | null = null;

export async function fetchRecipeModel(): Promise<RecipeModel> {
    if (cachedModel) return cachedModel;
    if (!pendingFetch) {
        pendingFetch = fetch("/api/recipes/recipe-model", { credentials: "include" })
            .then((res) => {
                if (!res.ok) throw new Error(`recipe-model request failed: ${res.status}`);
                return res.json() as Promise<RecipeModel>;
            })
            .then((model) => {
                cachedModel = model;
                return model;
            })
            .catch((err) => {
                pendingFetch = null;
                throw err;
            });
    }
    return pendingFetch;
}

/** Drop the cached model (test/refresh hook). */
export function resetRecipeModel(): void {
    cachedModel = null;
    pendingFetch = null;
}

// ============================================================
// Message templates + nested type labels.
// These key/fallback pairs MUST match `recipes/translations.py`.
// ============================================================

const MSG = {
    noAlgorithm: {
        key: "recipes.validation.algorithm_required",
        fallback: "No analysis method is selected. Choose one in the analysis panel — a recipe needs a statistics stage with an algorithm.",
    },
    unknownAlgorithm: {
        key: "recipes.validation.unknown_algorithm",
        fallback: "'{type}' is not a recognised analysis method. Choose one of: {options}.",
    },
    missingAlgoField: {
        key: "recipes.validation.missing_algo_field",
        fallback: "Analysis '{algo}' is missing its '{field}' setting ({label}). Select a column for '{field}' in the analysis panel.",
    },
    unknownOutput: {
        key: "recipes.validation.unknown_output",
        fallback: "'{type}' is not a recognised output type. Choose one of: {options}.",
    },
    missingOutputField: {
        key: "recipes.validation.missing_output_field",
        fallback: "Output '{output}' is missing its '{field}' setting ({label}). Select a column for '{field}' in the output panel.",
    },
    unknownColumns: {
        key: "recipes.validation.unknown_columns",
        fallback: "The {stage} stage references column(s) '{columns}' that don't exist in this dataset. Available columns: {available}. Select from the available ones.",
    },
    wrongColumnType: {
        key: "recipes.validation.wrong_column_type",
        fallback: "Column '{column}' must be {expected} for '{field}' ({label}).",
    },
    incompatibleAlgoOutput: {
        key: "recipes.validation.incompatible_algo_output",
        fallback: "Analysis '{algo}' produces {result_type} results and cannot be displayed as a '{output}' chart. Change the output type to one compatible with '{algo}': {options}.",
    },
    insufficientColumnsAlgo: {
        key: "recipes.validation.insufficient_columns_algo",
        fallback: "This dataset doesn't have the right column types for '{algo}' ({requirement}). Dataset has: {columns}. Choose a dataset with {requirement}, or switch to: {options}.",
    },
    insufficientColumnsOutput: {
        key: "recipes.validation.insufficient_columns_output",
        fallback: "This dataset doesn't have the right column types for '{output}' ({requirement}). Dataset has: {columns}. Choose a dataset with {requirement}, or switch to: {options}.",
    },
};

const COLUMN_TYPE = {
    categorical: { key: "recipes.column_type.categorical", fallback: "categorical" },
    numeric: { key: "recipes.column_type.numeric", fallback: "numeric" },
} as const;

const RESULT_TYPE = {
    tabular: { key: "recipes.result_type.tabular", fallback: "tabular" },
    numeric: { key: "recipes.result_type.numeric", fallback: "numeric" },
} as const;

const INFERENCE_ALGOS = new Set([
    "t_test_independent",
    "t_test_paired",
    "anova_one_way",
    "anova_two_way",
    "chi_square",
]);

// ============================================================
// Internal helpers (no strings)
// ============================================================

function satisfiesRequirement(
    columns: ModelColumn[],
    minCategorical: number,
    minNumeric: number,
): boolean {
    if (!columns || columns.length === 0) return false;
    const cat = columns.filter((c) => c.isCategorical).length;
    const num = columns.filter((c) => c.isNumeric).length;
    if (cat < minCategorical) return false;
    if (num < minNumeric) return false;
    return true;
}

function getAvailableAlgorithms(model: RecipeModel, columns: ModelColumn[]): string[] {
    if (!columns || columns.length === 0) return [];
    return Object.keys(model.algorithms).filter((a) => {
        const d = model.algorithms[a];
        return satisfiesRequirement(columns, d.minCategorical, d.minNumeric);
    });
}

function getAvailableOutputs(model: RecipeModel, columns: ModelColumn[]): string[] {
    if (!columns || columns.length === 0) return Object.keys(model.outputs);
    return Object.keys(model.outputs).filter((o) => {
        const d = model.outputs[o];
        return satisfiesRequirement(columns, d.minCategorical, d.minNumeric);
    });
}

// ============================================================
// Validity highlighting (Item 14)
// ============================================================

/** Whether an algorithm will work given the current dataset columns and the
 * currently-chosen output. Column-count is permissive when no columns are
 * selected yet; compatibility applies only when an output is chosen (and is
 * not "none"). */
export function isAlgorithmValid(
    model: RecipeModel,
    algorithmType: string,
    columns: ModelColumn[],
    outputType: string | null | undefined,
): boolean {
    const defn = model.algorithms[algorithmType];
    if (!defn) return false;
    if (columns.length > 0 && !satisfiesRequirement(columns, defn.minCategorical, defn.minNumeric)) {
        return false;
    }
    if (outputType && outputType !== "none" && !defn.compatibleOutputs.includes(outputType)) {
        return false;
    }
    return true;
}

/** Whether an output will work given the current dataset columns and the
 * currently-chosen algorithm. Column-count is permissive when no columns are
 * selected yet; compatibility applies only when an algorithm is chosen (and
 * the output is not "none"). */
export function isOutputValid(
    model: RecipeModel,
    outputType: string,
    columns: ModelColumn[],
    algorithmType: string | null | undefined,
): boolean {
    const defn = model.outputs[outputType];
    if (!defn) return false;
    if (columns.length > 0 && !satisfiesRequirement(columns, defn.minCategorical, defn.minNumeric)) {
        return false;
    }
    if (algorithmType && outputType !== "none") {
        const algo = model.algorithms[algorithmType];
        if (algo && !algo.compatibleOutputs.includes(outputType)) {
            return false;
        }
    }
    return true;
}

/** The first 12 columns as plain objects (mirrors Python's `columns[:12]`). */
function toColumnList(columns: ModelColumn[]): { name: string; isNumeric: boolean; isCategorical: boolean }[] {
    return columns.slice(0, 12).map((c) => ({
        name: c.name,
        isNumeric: c.isNumeric,
        isCategorical: c.isCategorical,
    }));
}

function innerConfig(state: { config?: Record<string, unknown> | null } | null | undefined): Record<string, unknown> {
    const cfg = state?.config;
    return cfg && typeof cfg === "object" ? cfg : {};
}

// ============================================================
// Validation steps (driven entirely by the passed model)
// ============================================================

function validateAlgorithmConfig(
    model: RecipeModel,
    algoType: string,
    algorithm: ModelAlgorithmState | null,
): ValidationIssue[] {
    const errors: ValidationIssue[] = [];

    const algoDef = model.algorithms[algoType];
    if (!algoDef) {
        errors.push({
            source: "algorithm",
            key: MSG.unknownAlgorithm.key,
            fallback: MSG.unknownAlgorithm.fallback,
            params: { type: algoType, options: Object.keys(model.algorithms).sort().join(", ") },
        });
        return errors;
    }

    const inner = innerConfig(algorithm);
    for (const field of algoDef.fields) {
        const val = inner[field];
        if (!val || (Array.isArray(val) && val.length === 0)) {
            errors.push({
                source: "algorithm",
                field,
                key: MSG.missingAlgoField.key,
                fallback: MSG.missingAlgoField.fallback,
                params: { algo: algoType, field, label: model.fields[field]?.label },
            });
        }
    }

    return errors;
}

function validateOutputConfig(
    model: RecipeModel,
    outType: string,
    output: ModelOutputState | null,
): ValidationIssue[] {
    const errors: ValidationIssue[] = [];

    if (outType === "none") return errors;

    const outDef = model.outputs[outType];
    if (!outDef) {
        errors.push({
            source: "output",
            key: MSG.unknownOutput.key,
            fallback: MSG.unknownOutput.fallback,
            params: { type: outType, options: Object.keys(model.outputs).sort().join(", ") },
        });
        return errors;
    }

    const inner = innerConfig(output);
    for (const field of outDef.fields) {
        const val = inner[field];
        if (!val || (Array.isArray(val) && val.length === 0)) {
            errors.push({
                source: "output",
                field,
                key: MSG.missingOutputField.key,
                fallback: MSG.missingOutputField.fallback,
                params: { output: outType, field, label: model.fields[field]?.label },
            });
        }
    }

    return errors;
}

function validateAlgorithmOutputCompatibility(
    model: RecipeModel,
    algoType: string | null,
    outType: string | null,
): ValidationIssue[] {
    const warnings: ValidationIssue[] = [];

    if (!algoType || !outType || outType === "none") return warnings;

    const algoDef = model.algorithms[algoType];
    if (!algoDef) return warnings;

    if (!algoDef.compatibleOutputs.includes(outType)) {
        const suggestions = algoDef.compatibleOutputs.filter((o) => o !== "none");
        const resultType = INFERENCE_ALGOS.has(algoType) ? RESULT_TYPE.tabular : RESULT_TYPE.numeric;
        warnings.push({
            source: "compatibility",
            key: MSG.incompatibleAlgoOutput.key,
            fallback: MSG.incompatibleAlgoOutput.fallback,
            params: {
                algo: algoType,
                result_type: resultType,
                output: outType,
                options: suggestions.join(", "),
            },
        });
    }

    return warnings;
}

interface StageConfig {
    type: string;
    config: ModelAlgorithmState | ModelOutputState | null;
}

function buildStageConfigs(
    algorithm: ModelAlgorithmState | null,
    output: ModelOutputState | null,
): StageConfig[] {
    const stages: StageConfig[] = [];
    if (algorithm) stages.push({ type: "statistics", config: algorithm });
    if (output) stages.push({ type: "visualisation", config: output });
    return stages;
}

function validateColumnReferences(
    model: RecipeModel,
    columns: ModelColumn[],
    stageConfigs: StageConfig[],
): ValidationIssue[] {
    if (!columns || columns.length === 0) return [];

    const colNames = new Set(columns.map((c) => c.name));
    const errors: ValidationIssue[] = [];

    for (const stage of stageConfigs) {
        const inner = innerConfig(stage.config);
        const stageType = stage.type;

        const refs = new Set<string>();
        for (const [fieldName, fdef] of Object.entries(model.fields)) {
            const v = inner[fieldName];
            if (fdef.multi) {
                if (Array.isArray(v)) {
                    for (const x of v) if (x) refs.add(String(x));
                }
            } else if (v && typeof v === "string") {
                refs.add(v);
            }
        }

        const missing = [...refs].filter((r) => !colNames.has(r));
        if (missing.length) {
            const sortedNames = [...colNames].sort();
            let available = sortedNames.slice(0, 10).join(", ");
            if (sortedNames.length > 10) available += "…";
            errors.push({
                source: "dataset",
                key: MSG.unknownColumns.key,
                fallback: MSG.unknownColumns.fallback,
                params: { stage: stageType, columns: missing.sort().join(", "), available },
            });
        }
    }

    return errors;
}

function validateColumnTypes(
    model: RecipeModel,
    columns: ModelColumn[],
    stageConfigs: StageConfig[],
): ValidationIssue[] {
    if (!columns || columns.length === 0) return [];

    const colByName = new Map(columns.map((c) => [c.name, c]));
    const errors: ValidationIssue[] = [];

    for (const stage of stageConfigs) {
        const inner = innerConfig(stage.config);

        for (const [fieldName, fdef] of Object.entries(model.fields)) {
            if (fdef.columnType === "any") continue;

            const v = inner[fieldName];
            let boundNames: string[] = [];
            if (fdef.multi) {
                if (Array.isArray(v)) boundNames = v.filter((x) => x).map(String);
            } else if (v && typeof v === "string") {
                boundNames = [v];
            }

            for (const colName of boundNames) {
                const col = colByName.get(colName);
                if (!col) continue; // existence handled by validateColumnReferences

                if (fdef.columnType === "numeric" && col.isNumeric) continue;
                if (fdef.columnType === "categorical" && col.isCategorical) continue;

                const expected = fdef.columnType === "numeric" ? COLUMN_TYPE.numeric : COLUMN_TYPE.categorical;
                errors.push({
                    source: "dataset",
                    field: fieldName,
                    key: MSG.wrongColumnType.key,
                    fallback: MSG.wrongColumnType.fallback,
                    params: { field: fieldName, label: fdef.label, column: colName, expected },
                });
            }
        }
    }

    return errors;
}

function validateColumnRequirements(
    model: RecipeModel,
    columns: ModelColumn[],
    algoType: string | null,
    outType: string | null,
): ValidationIssue[] {
    const warnings: ValidationIssue[] = [];
    const colInfo = toColumnList(columns);

    if (algoType && model.algorithms[algoType]) {
        const d = model.algorithms[algoType];
        if (!satisfiesRequirement(columns, d.minCategorical, d.minNumeric)) {
            const available = getAvailableAlgorithms(model, columns);
            const alts = available.filter((a) => a !== algoType);
            warnings.push({
                source: "dataset",
                key: MSG.insufficientColumnsAlgo.key,
                fallback: MSG.insufficientColumnsAlgo.fallback,
                params: {
                    algo: algoType,
                    requirement: d.description,
                    columns: colInfo,
                    options: alts.length ? alts.join(", ") : "…",
                },
            });
        }
    }

    if (outType && outType !== "none" && model.outputs[outType]) {
        const d = model.outputs[outType];
        if (!satisfiesRequirement(columns, d.minCategorical, d.minNumeric)) {
            const available = getAvailableOutputs(model, columns);
            const alts = available.filter((o) => o !== outType && o !== "none");
            warnings.push({
                source: "dataset",
                key: MSG.insufficientColumnsOutput.key,
                fallback: MSG.insufficientColumnsOutput.fallback,
                params: {
                    output: outType,
                    requirement: d.description,
                    columns: colInfo,
                    options: alts.length ? alts.join(", ") : "…",
                },
            });
        }
    }

    return warnings;
}

// ============================================================
// Pure validator — canonical {errors, warnings} shape
// ============================================================

export function validateRecipe(model: RecipeModel, state: RecipeValidationState): ValidationResult {
    const errors: ValidationIssue[] = [];
    const warnings: ValidationIssue[] = [];

    const { columns, algorithm, output } = state;
    const algoType = algorithm?.algorithmType ?? null;
    const outType = output?.outputType ?? null;

    if (algoType) {
        errors.push(...validateAlgorithmConfig(model, algoType, algorithm));
    } else {
        // An algorithm is required — a statistics stage with no method is not a
        // complete recipe, and execution runs the empty stage as the default
        // technique and fails on its missing fields. The backend gate enforces
        // the same rule (recipes/constraints.py, validate_recipe).
        errors.push({
            source: "algorithm",
            key: MSG.noAlgorithm.key,
            fallback: MSG.noAlgorithm.fallback,
        });
    }
    if (outType) {
        errors.push(...validateOutputConfig(model, outType, output));
    }

    warnings.push(...validateAlgorithmOutputCompatibility(model, algoType, outType));

    if (columns && columns.length > 0) {
        const stageConfigs = buildStageConfigs(algorithm, output);
        errors.push(...validateColumnReferences(model, columns, stageConfigs));
        errors.push(...validateColumnTypes(model, columns, stageConfigs));
        warnings.push(...validateColumnRequirements(model, columns, algoType, outType));
    }

    return { errors, warnings };
}
