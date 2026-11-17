// components/recipe/types.ts
// ============================================================
// Shared recipe state types used by the three-component pipeline
// editor (Dataset/Transform, Algorithm, Output).
// ============================================================

/** A single transform rule referenced by a recipe. */
export interface RecipeTransformRef {
    id: string;
    name: string;
    description: string | null;
}

/** Column schema for a dataset. */
export interface RecipeColumn {
    name: string;
    type: string;
    isNumeric: boolean;
    isCategorical: boolean;
}

/** The dataset selection within a recipe. */
export interface RecipeDatasetState {
    datasetId: string | null;
    datasetName: string | null;
    columns: RecipeColumn[];
    transformIds: string[];
}

/** Configuration for a specific algorithm. */
export interface AlgorithmConfig {
    technique?: string | null;
    factorColumn?: string | null;
    responseColumn?: string | null;
    responseColumn2?: string | null;
    independentColumns?: string[] | null;
    dependentColumn?: string | null;
    groupByColumn?: string | null;
    [key: string]: unknown;
}

/** The algorithm selection within a recipe. */
export interface RecipeAlgorithmState {
    algorithmType: string | null;
    config: AlgorithmConfig;
}

/** Configuration for a specific output type. */
export interface OutputConfig {
    categoryColumn?: string | null;
    xColumn?: string | null;
    yColumn?: string | null;
    [key: string]: unknown;
}

/** The output type selection within a recipe. */
export interface RecipeOutputState {
    outputType: string | null;
    config: OutputConfig;
}

/** The full recipe state passed between pipeline components. */
export interface RecipeState {
    name: string;
    description: string | null;
    dataset: RecipeDatasetState;
    algorithm: RecipeAlgorithmState;
    output: RecipeOutputState;
    status: "draft" | "complete";
}

/** Initial empty recipe state for creating a new recipe. */
export const EMPTY_RECIPE_STATE: RecipeState = {
    name: "",
    description: null,
    dataset: {
        datasetId: null,
        datasetName: null,
        columns: [],
        transformIds: [],
    },
    algorithm: {
        algorithmType: null,
        config: {},
    },
    output: {
        outputType: null,
        config: {},
    },
    status: "draft",
};
