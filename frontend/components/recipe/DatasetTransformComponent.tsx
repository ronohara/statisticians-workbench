"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, useTranslateWithParams, getErrorMessageFromData } from "@/lib/translation-helpers";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Button } from "@/components/ui/button";
import { Loader2, Plus, X, ExternalLink } from "lucide-react";
import { RECIPES } from "@/app/recipes/translations";
import { DATASETS } from "@/app/datasets/translations";
import type { ValidationIssue } from "@/lib/recipe-model";
import type { RecipeDatasetState, RecipeColumn, RecipeTransformRef } from "./types";

interface DatasetTransformProps {
    value: RecipeDatasetState;
    onChange: (state: RecipeDatasetState) => void;
    recipeId?: string | null;
    issues?: ValidationIssue[];
    /** The dataset selector's filter, from the editor's section heading. "all"
     *  shows every dataset. */
    filter?: string;
}

interface DatasetOption {
    id: string;
    name: string;
    // Carried so the filter can classify a dataset the way /datasets/manage and
    // the manual virtual-dataset editor do.
    sourceType?: string;
    storageType?: string | null;
    sourceOrigin?: string | null;
    isShared?: boolean;
}

// The classifier and matcher are the ones /datasets/manage uses. Copied rather
// than shared: datasetCategory already lives in three files (manage, the manual
// virtual-dataset editor, the AI recipe page), and hoisting it out of all of them
// is a separate cleanup. Recorded in docs/code-quirks.md.
function datasetCategory(ds: DatasetOption): string {
    const key = ds.sourceOrigin || ds.sourceType;
    if (key === "table" || key === "view") {
        return ds.storageType || "postgresql";
    }
    return key || "";
}

function matchesDatasetFilter(ds: DatasetOption, f: string): boolean {
    switch (f) {
        case "all": return true;
        case "cleaned": return !!ds.sourceOrigin;
        case "shared": return ds.isShared === true;
        case "not_shared": return ds.isShared !== true;
        default: return datasetCategory(ds) === f;
    }
}

async function getToken(): Promise<string> {
    const res = await fetch("/api/auth/token", { credentials: "include" });
    if (!res.ok) throw new Error("Unauthorized");
    const data = await res.json();
    if (!data.token) throw new Error("No token in response");
    return data.token;
}

export default function DatasetTransformComponent({
    value,
    onChange,
    recipeId,
    issues = [],
    filter = "all",
}: DatasetTransformProps) {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const translateParams = useTranslateWithParams();
    const router = useRouter();

    const [datasets, setDatasets] = useState<DatasetOption[]>([]);
    const [loadingDatasets, setLoadingDatasets] = useState(true);
    const [datasetError, setDatasetError] = useState<string | null>(null);
    const [columns, setColumns] = useState<RecipeColumn[]>([]);
    const [loadingColumns, setLoadingColumns] = useState(false);
    const [schemaError, setSchemaError] = useState<string | null>(null);

    // Transform display data (names for selected chips)
    const [transforms, setTransforms] = useState<RecipeTransformRef[]>([]);

    // Fetch datasets on mount
    useEffect(() => {
        let cancelled = false;
        const fetchDatasets = async () => {
            try {
                setLoadingDatasets(true);
                setDatasetError(null);
                const token = await getToken();
                const res = await fetch("/api/datasets", {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (!res.ok) {
                    let errorData: any = {};
                    try { const text = await res.text(); if (text) errorData = JSON.parse(text); } catch {}
                    throw new Error(getErrorMessageFromData(translate, errorData, RECIPES.dataset_load_error));
                }
                const data = await res.json();
                if (!cancelled) {
                    const list = Array.isArray(data) ? data : (data.datasets || []);
                    setDatasets(list);
                }
            } catch (err: any) {
                if (!cancelled) {
                    setDatasetError(err.message || translate(RECIPES.dataset_load_error));
                }
            } finally {
                if (!cancelled) setLoadingDatasets(false);
            }
        };
        fetchDatasets();
        return () => { cancelled = true; };
    }, [translate]);

    // Fetch column schema when dataset changes
    useEffect(() => {
        if (!value.datasetId) {
            setColumns([]);
            return;
        }
        let cancelled = false;
        const fetchSchema = async () => {
            try {
                setLoadingColumns(true);
                setSchemaError(null);
                const token = await getToken();
                const res = await fetch(`/api/datasets/${value.datasetId}/schema`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (!res.ok) {
                    let errorData: any = {};
                    try { const text = await res.text(); if (text) errorData = JSON.parse(text); } catch {}
                    const msg = getErrorMessageFromData(translate, errorData, RECIPES.dataset_load_error);
                    throw new Error(msg);
                }
                const data = await res.json();
                if (!cancelled) {
                    const cols: RecipeColumn[] = (data.columns || []).map((c: any) => ({
                        name: c.name || c.column_name,
                        type: c.type || c.dtype || c.data_type || "unknown",
                        isNumeric: c.is_numeric === true || c.isNumeric === true,
                        isCategorical: c.is_categorical === true || c.isCategorical === true,
                    }));
                    setColumns(cols);
                    onChange({ ...value, columns: cols });
                }
            } catch (err: any) {
                if (!cancelled) {
                    setSchemaError(err.message || translate(RECIPES.dataset_load_error));
                }
            } finally {
                if (!cancelled) setLoadingColumns(false);
            }
        };
        fetchSchema();
        return () => { cancelled = true; };
    }, [value.datasetId]);

    // Fetch transforms for name display when dataset changes
    useEffect(() => {
        if (!value.datasetId) {
            setTransforms([]);
            return;
        }
        let cancelled = false;
        const fetchTransforms = async () => {
            try {
                const token = await getToken();
                const res = await fetch(`/api/datasets/${value.datasetId}/transforms`, {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (!res.ok) return;
                const data = await res.json();
                if (!cancelled) {
                    setTransforms(data.transforms || []);
                }
            } catch {
                // Non-critical — transforms just won't be listed by name
            }
        };
        fetchTransforms();
        return () => { cancelled = true; };
    }, [value.datasetId]);

    // Resolve dataset name from loaded datasets when ID is set but name is missing
    useEffect(() => {
        if (value.datasetId && !value.datasetName && datasets.length > 0) {
            const found = datasets.find((d) => d.id === value.datasetId);
            if (found) {
                onChange({ ...value, datasetName: found.name });
            }
        }
    }, [value.datasetId, value.datasetName, datasets, onChange]);

    // Remove a transform from the recipe (optimistic UI + API call)
    const handleRemoveTransform = async (transformId: string) => {
        // Optimistic UI update
        onChange({
            ...value,
            transformIds: value.transformIds.filter((id) => id !== transformId),
        });

        // Sync to join table if we have a recipe context
        if (recipeId) {
            try {
                const token = await getToken();
                await fetch(`/api/recipes/${recipeId}/transforms/${transformId}`, {
                    method: "DELETE",
                    headers: { Authorization: `Bearer ${token}` },
                });
            } catch {
                // Fire-and-forget — the save will reconcile on next PUT
            }
        }
    };

    if (!isLanguageLoaded) return null;

    const selectedTransforms = transforms.filter(
        (t) => value.transformIds.includes(t.id)
    );

    // Build the manage transforms URL. It carries returnTo so the editor comes
    // back here — the recipe's own page once it has been saved, and the create
    // form when it has not, which is the case a new recipe is in (there is no id
    // to return to yet). The AI editor's link mirrors this.
    const manageTransformsUrl = value.datasetId
        ? recipeId
            ? `/datasets/${value.datasetId}/transforms?recipeId=${recipeId}&returnTo=/recipes/${recipeId}`
            : `/datasets/${value.datasetId}/transforms?returnTo=${encodeURIComponent("/recipes?new=true")}`
        : null;

    // The filter narrows the selector, never the selection: the dataset already
    // chosen stays listed even when it falls outside the filter, or the trigger
    // would show a value with no item behind it.
    const visibleDatasets = datasets.filter(
        (ds) => matchesDatasetFilter(ds, filter) || ds.id === value.datasetId,
    );

    return (
        <div className="space-y-3">
            {/* Dataset selector */}
            <div>
                <Select
                    value={value.datasetId || ""}
                    onValueChange={(datasetId) => {
                        const selected = datasets.find((d) => d.id === datasetId);
                        onChange({
                            ...value,
                            datasetId: datasetId || null,
                            datasetName: selected?.name || null,
                            columns: [],
                            transformIds: [],
                        });
                    }}
                    disabled={loadingDatasets}
                >
                    <SelectTrigger className="h-8 text-sm w-full">
                        <SelectValue>
                            {value.datasetName || (
                                loadingDatasets
                                    ? translate(RECIPES.dataset_loading)
                                    : translate(RECIPES.dataset_placeholder)
                            )}
                        </SelectValue>
                    </SelectTrigger>
                    <SelectContent className="min-w-[200px]">
                        {visibleDatasets.map((ds) => (
                            <SelectItem key={ds.id} value={ds.id}>
                                {ds.name}
                            </SelectItem>
                        ))}
                    </SelectContent>
                </Select>
                {datasetError && (
                    <p className="text-xs text-destructive mt-1">{datasetError}</p>
                )}
                {!loadingDatasets && datasets.length === 0 && !datasetError && (
                    <p className="text-xs text-muted-foreground mt-1">
                        {translate(RECIPES.dataset_no_datasets)}
                    </p>
                )}
                {!loadingDatasets && datasets.length > 0 && visibleDatasets.length === 0 && !datasetError && (
                    <p className="text-xs text-muted-foreground mt-1">
                        {translate(DATASETS.filter.no_match)}
                    </p>
                )}
            </div>

            {/* Constraint issues (persistent inline) */}
            {issues.length > 0 && (
                <div className="text-xs text-amber-600 bg-amber-50 rounded px-2 py-1 space-y-0.5">
                    {issues.map((issue, i) => (
                        <div key={i}>{translateParams(issue.key, issue.fallback, issue.params)}</div>
                    ))}
                </div>
            )}

            {/* Column display */}
            {value.datasetId && (
                <div>
                    <div className="text-xs font-medium text-muted-foreground mb-1">
                        {translate(RECIPES.dataset_columns_label)}
                    </div>
                    {loadingColumns ? (
                        <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                            <Loader2 className="h-3 w-3 animate-spin" />
                            {translate(RECIPES.dataset_loading)}
                        </div>
                    ) : schemaError ? (
                        <p className="text-xs text-destructive bg-destructive/10 rounded px-2 py-1">
                            {schemaError}
                        </p>
                    ) : columns.length > 0 ? (
                        <div className="flex flex-wrap gap-1">
                            {columns.map((col) => (
                                <span
                                    key={col.name}
                                    className={`text-[11px] px-1.5 py-0.5 rounded font-medium ${
                                        col.isNumeric
                                            ? "bg-blue-50 text-blue-700"
                                            : col.isCategorical
                                            ? "bg-purple-50 text-purple-700"
                                            : "bg-muted text-muted-foreground"
                                    }`}
                                >
                                    {col.name}
                                    <span className="ms-1 opacity-50">{col.type}</span>
                                </span>
                            ))}
                        </div>
                    ) : (
                        <p className="text-xs text-muted-foreground italic">
                            {translate(RECIPES.dataset_no_datasets)}
                        </p>
                    )}
                </div>
            )}

            {/* Transforms */}
            <div>
                <div className="flex items-center gap-2 mb-1">
                    <span className="text-xs font-medium text-muted-foreground">
                        {translate(RECIPES.transforms_label)}
                    </span>
                    {value.datasetId && (
                        <Button
                            variant="outline"
                            size="xs"
                            className="h-6 px-2 text-xs"
                            onClick={() => manageTransformsUrl && router.push(manageTransformsUrl)}
                        >
                            <ExternalLink className="h-3 w-3 me-1" />
                            {translate(RECIPES.transforms_manage_button)}
                        </Button>
                    )}
                </div>
                {selectedTransforms.length === 0 ? (
                    <p className="text-xs text-muted-foreground italic">
                        {translate(RECIPES.transforms_no_transforms)}
                    </p>
                ) : (
                    <div className="space-y-1">
                        {selectedTransforms.map((t) => (
                            <div
                                key={t.id}
                                className="flex items-center justify-between text-xs bg-muted/50 rounded px-2 py-1"
                            >
                                <span className="truncate">{t.name}</span>
                                <button
                                    type="button"
                                    onClick={() => handleRemoveTransform(t.id)}
                                    className="text-muted-foreground hover:text-destructive shrink-0 ms-1"
                                    title={translate(RECIPES.transforms_remove)}
                                >
                                    <X className="h-3 w-3" />
                                </button>
                            </div>
                        ))}
                    </div>
                )}
            </div>
        </div>
    );
}
