"use client";

import { useState, useEffect, useMemo } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, useTranslateWithParams, type TranslationKey } from "@/lib/translation-helpers";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Filter, Loader2, Save } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RECIPES } from "@/app/recipes/translations";
import { DATASETS } from "@/app/datasets/translations";
import DatasetTransformComponent from "./DatasetTransformComponent";
import AlgorithmComponent from "./AlgorithmComponent";
import OutputComponent from "./OutputComponent";
import type { RecipeDatasetState, RecipeAlgorithmState, RecipeOutputState } from "./types";
import { fetchRecipeModel, validateRecipe, type RecipeModel, type ValidationIssue } from "@/lib/recipe-model";

interface RecipeEditorPanelProps {
    recipe: RecipeEditorRecipe | null;
    loading: boolean;
    isCreate?: boolean;
    onSave?: (name: string, stages: any[], afterSaveRoute?: string) => Promise<void>;
    saveError?: string | null;
}

export interface RecipeEditorRecipe {
    id: string;
    name: string;
    description: string | null;
    stages: any[];
    preparation_rules?: Array<{ id: string; name: string; description: string | null; order: number }>;
    isShared?: boolean;
    isOwn?: boolean;
    // Whether the backend would accept a save from this caller — can_edit_recipe: the owner,
    // or an administrator when the recipe is shared to the administrator's group. The
    // editor's read-only state follows this rather than isOwn.
    canEdit?: boolean;
    userId?: string;
    user?: { name: string } | null;
}

// The dataset selector's filter. It reuses the /datasets/manage declarations —
// the same vocabulary the manual virtual-dataset editor's filter uses — rather
// than declaring a second label per option.
const DATASET_FILTER_OPTIONS: { value: string; label: TranslationKey }[] = [
    { value: "all", label: DATASETS.filter.all },
    { value: "virtual", label: DATASETS.filter.virtual },
    { value: "upload", label: DATASETS.filter.uploads },
    { value: "notebook", label: DATASETS.filter.notebooks },
    { value: "postgresql", label: DATASETS.filter.postgresql },
    { value: "mysql", label: DATASETS.filter.mysql },
    { value: "mssql", label: DATASETS.filter.mssql },
    { value: "access", label: DATASETS.filter.access },
    { value: "cleaned", label: DATASETS.filter.cleaned },
    { value: "shared", label: DATASETS.filter.shared },
    { value: "not_shared", label: DATASETS.filter.not_shared },
];

async function getToken(): Promise<string> {
    const res = await fetch("/api/auth/token", { credentials: "include" });
    if (!res.ok) throw new Error("Unauthorized");
    const data = await res.json();
    if (!data.token) throw new Error("No token in response");
    return data.token;
}

export default function RecipeEditorPanel({
    recipe,
    loading,
    isCreate = false,
    onSave,
    saveError,
}: RecipeEditorPanelProps) {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const translateParams = useTranslateWithParams();
    const router = useRouter();
    const [draftName, setDraftName] = useState(recipe?.name || "");
    const [saving, setSaving] = useState(false);

    // Sync draftName when recipe loads (e.g. after API fetch in edit mode)
    useEffect(() => {
        if (!isCreate && recipe?.name) {
            setDraftName(recipe.name);
        }
    }, [recipe?.name, isCreate]);

    // Sync pipeline state from recipe.stages when loading an existing recipe
    useEffect(() => {
        if (isCreate || !recipe?.stages?.length) return;
        for (const stage of recipe.stages) {
            if (stage.type === "data_selection") {
                // Start with transformIds from the stage config
                let transformIds: string[] = stage.config?.transformIds || [];
                // If empty, fall back to preparation_rules from the join table
                if (transformIds.length === 0 && recipe.preparation_rules?.length) {
                    transformIds = recipe.preparation_rules.map((r: any) => r.id);
                }
                setDatasetState({
                    datasetId: stage.config?.datasetId || null,
                    datasetName: stage.config?.datasetName || null,
                    columns: stage.config?.columns || [],
                    transformIds,
                });
            } else if (stage.type === "statistics") {
                setAlgorithmState({
                    algorithmType: stage.config?.algorithmType || null,
                    config: stage.config?.config || {},
                });
            } else if (stage.type === "visualisation") {
                setOutputState({
                    outputType: stage.config?.outputType || null,
                    config: stage.config?.config || {},
                });
            }
        }
    }, [isCreate, recipe?.stages, recipe?.preparation_rules]);

    const [validationError, setValidationError] = useState<string | null>(null);
    const [datasetFilter, setDatasetFilter] = useState("all");
    const [datasetState, setDatasetState] = useState<RecipeDatasetState>({
        datasetId: null,
        datasetName: null,
        columns: [],
        transformIds: [],
    });
    const [algorithmState, setAlgorithmState] = useState<RecipeAlgorithmState>({
        algorithmType: null,
        config: {},
    });
    const [outputState, setOutputState] = useState<RecipeOutputState>({
        outputType: null,
        config: {},
    });
    const [model, setModel] = useState<RecipeModel | null>(null);

    useEffect(() => {
        let cancelled = false;
        fetchRecipeModel()
            .then((m) => {
                if (!cancelled) setModel(m);
            })
            .catch(() => {
                /* keep the panel usable without the model */
            });
        return () => {
            cancelled = true;
        };
    }, []);

    // Group info for share toggle display
    const [groupInfo, setGroupInfo] = useState<{ userGroup: string; groupDescription: string } | null>(null);

    useEffect(() => {
        if (!recipe?.isOwn) return;
        let cancelled = false;
        const fetchGroup = async () => {
            try {
                const token = await getToken();
                const res = await fetch("/api/groups/user/me", {
                    headers: { Authorization: `Bearer ${token}` },
                });
                if (res.ok && !cancelled) {
                    const data = await res.json();
                    setGroupInfo({
                        userGroup: data.user_group,
                        groupDescription: data.group_description,
                    });
                }
            } catch {}
        };
        fetchGroup();
        return () => { cancelled = true; };
    }, [recipe?.isOwn]);

    // Run the shared validator against the served model (single source of truth).
    const validation = useMemo(() => {
        if (!model) return { errors: [] as ValidationIssue[], warnings: [] as ValidationIssue[] };
        return validateRecipe(model, {
            columns: datasetState.columns,
            algorithm: algorithmState,
            output: outputState,
        });
    }, [model, datasetState, algorithmState, outputState]);

    const allIssues = [...validation.errors, ...validation.warnings];
    const issuesFor = (source: ValidationIssue["source"]) =>
        allIssues.filter((issue) => issue.source === source);

    const ready = allIssues.length === 0;
    const runBlockers = allIssues.map((issue) =>
        translateParams(issue.key, issue.fallback, issue.params),
    );
    const saveErrors = validation.errors.map((issue) => translateParams(issue.key, issue.fallback, issue.params));

    const handleSave = async (afterSaveRoute?: string) => {
        if (!onSave) return;

        if (!draftName.trim()) {
            setValidationError(translate(RECIPES.editor_name_required));
            return;
        }
        // Save is blocked only by errors; warnings allow a not-ready draft.
        if (saveErrors.length > 0) {
            setValidationError(saveErrors.join(" "));
            return;
        }
        setValidationError(null);
        setSaving(true);
        try {
            const stages = [
                { id: "data", type: "data_selection", config: datasetState },
                { id: "algo", type: "statistics", config: algorithmState },
                { id: "output", type: "visualisation", config: outputState },
            ];
            await onSave(draftName.trim(), stages, afterSaveRoute);
        } finally {
            setSaving(false);
        }
    };

    const handleRun = async () => {
        // A recipe shared to the group but owned by someone else is runnable and
        // not saveable by this user — the Save button is already hidden for it
        // (isReadOnly). Run must not attempt that save: it executes the stored
        // recipe, exactly as the arrow in the recipe list does.
        if (isReadOnly && recipe) {
            router.push(`/recipes/${recipe.id}/execute`);
            return;
        }
        await handleSave(`/recipes/${recipe?.id}/execute`);
    };

    const handleToggleShare = async () => {
        if (!recipe?.id) return;
        try {
            const token = await getToken();
            const res = await fetch(`/api/recipes/${recipe.id}/share`, {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
            });
            if (res.ok) {
                const data = await res.json();
                // Optimistically update local state
                // The parent page will re-fetch on route activation
            }
        } catch {
            // Silently fail — the UI state updates optimistically
        }
    };

    if (!isLanguageLoaded) {
        return (
            <div className="flex items-center justify-center h-full">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    // No recipe selected — placeholder
    if (!recipe) {
        return (
            <div className="flex items-center justify-center h-full">
                <p className="text-muted-foreground text-sm">
                    {translate(RECIPES.editor_placeholder)}
                </p>
            </div>
        );
    }

    // Loading recipe detail
    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <div className="flex flex-col items-center gap-2">
                    <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                        {translate(RECIPES.editor_loading)}
                    </p>
                </div>
            </div>
        );
    }

    const hasName = draftName.trim().length > 0;
    // The backend's own verdict on whether a save would be accepted (can_edit_recipe), so an
    // administrator whose group the recipe is shared to is offered the editor the backend
    // would honour. Ownership still decides the share control, which stays the owner's alone.
    const isReadOnly = !isCreate && recipe?.canEdit === false;

    // Recipe loaded — show three stacked component shells
    return (
        <div className="flex flex-col h-full">
            {/* Recipe header */}
            <div className="px-4 py-3 border-b">
                {isCreate ? (
                    <div>
                        <Input dir="auto"
                            value={draftName}
                            onChange={(e) => {
                                setDraftName(e.target.value);
                                setValidationError(null);
                            }}
                            placeholder={translate(RECIPES.editor_name_placeholder)}
                            className="h-9 text-sm font-semibold"
                        />
                        {!hasName && (
                            <p className="text-[11px] text-muted-foreground mt-1">
                                {translate(RECIPES.editor_name_hint)}
                            </p>
                        )}
                    </div>
                ) : (
                    <div className="flex items-center gap-2">
                        <h2 className="font-semibold text-sm truncate flex-1">{recipe.name}</h2>
                        {recipe.isOwn && !isCreate && (
                            <div className="flex items-center gap-2 shrink-0">
                                <div className="text-end">
                                    <p className="text-xs font-medium">
                                        {recipe.isShared ? translate(RECIPES.share_unshare) : translate(RECIPES.share_button)}
                                    </p>
                                    {groupInfo && (
                                        <p className="text-[10px] text-muted-foreground">
                                            {translate(RECIPES.share_group_info)
                                                .replace("{group}", groupInfo.userGroup)
                                                .replace("{desc}", groupInfo.groupDescription)}
                                        </p>
                                    )}
                                </div>
                                <Switch
                                    checked={recipe.isShared}
                                    onCheckedChange={handleToggleShare}
                                />
                            </div>
                        )}
                        {isReadOnly && recipe.isShared && (
                            <span className="text-xs text-muted-foreground shrink-0">
                                {translate(RECIPES.share_shared_badge)} — {recipe.user?.name || translate(RECIPES.unknown_user)}
                            </span>
                        )}
                    </div>
                )}{/* end isCreate ? ... : ... */}
                {recipe.description && (
                    <p className="text-xs text-muted-foreground mt-0.5 truncate">
                        {recipe.description}
                    </p>
                )}
                {saveError && (
                    <p className="text-xs text-destructive mt-2 bg-destructive/10 rounded px-2 py-1.5 whitespace-pre-wrap">
                        {saveError}
                    </p>
                )}
            </div>

            {/* Pipeline components — plain sections. These were collapsible cards;
                the fold added a click to a mandatory step and could hide a
                section's constraint issues, which render inside the section. */}
            <div className="flex-1 overflow-y-auto p-3 space-y-4">
                <section className="space-y-2">
                    <div className="flex items-center gap-2">
                        <h3 className="text-sm font-medium">
                            {translate(RECIPES.editor_component_dataset)}
                        </h3>
                        <div className="flex items-center gap-2">
                            <Filter className="h-4 w-4 text-muted-foreground" aria-hidden="true" />
                            <Select value={datasetFilter} onValueChange={(v) => setDatasetFilter(v || "all")}>
                                <SelectTrigger className="h-8 w-36 text-sm" aria-label={translate(DATASETS.filter.label)}>
                                    <SelectValue>
                                        {(v: string) => {
                                            const chosen = DATASET_FILTER_OPTIONS.find((o) => o.value === v);
                                            return chosen ? translate(chosen.label) : translate(DATASETS.filter.all);
                                        }}
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent className="min-w-max">
                                    {DATASET_FILTER_OPTIONS.map((o) => (
                                        <SelectItem key={o.value} value={o.value}>
                                            {translate(o.label)}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                    </div>
                    <DatasetTransformComponent
                        value={datasetState}
                        onChange={setDatasetState}
                        recipeId={recipe?.id || null}
                        issues={issuesFor("dataset")}
                        filter={datasetFilter}
                    />
                </section>
                <section className="space-y-2">
                    <h3 className="text-sm font-medium">
                        {translate(RECIPES.editor_component_algorithm)}
                    </h3>
                    <AlgorithmComponent
                        value={algorithmState}
                        onChange={setAlgorithmState}
                        columns={datasetState.columns}
                        issues={issuesFor("algorithm")}
                        outputType={outputState.outputType}
                    />
                </section>
                <section className="space-y-2">
                    <h3 className="text-sm font-medium">
                        {translate(RECIPES.editor_component_output)}
                    </h3>
                    <OutputComponent
                        value={outputState}
                        onChange={setOutputState}
                        columns={datasetState.columns}
                        issues={issuesFor("output")}
                        algorithmType={algorithmState.algorithmType}
                    />
                </section>
            </div>

            {/* Action buttons */}
            <div className="px-4 pb-3 pt-1">
                {validationError && (
                    <p className="text-xs text-destructive mb-2 bg-destructive/10 rounded px-2 py-1.5">
                        {validationError}
                    </p>
                )}
                {issuesFor("compatibility").length > 0 && (
                    <div className="text-xs text-amber-600 bg-amber-50 rounded px-2 py-1.5 mb-2 space-y-0.5">
                        {issuesFor("compatibility").map((issue, i) => (
                            <div key={i}>{translateParams(issue.key, issue.fallback, issue.params)}</div>
                        ))}
                    </div>
                )}
                <div className="flex items-center gap-2">
                    {!isReadOnly && (
                        <Button
                            size="sm"
                            onClick={() => handleSave()}
                            disabled={saving}
                        >
                            {saving ? (
                                <Loader2 className="h-4 w-4 animate-spin me-1.5" />
                            ) : (
                                <Save className="h-4 w-4 me-1.5" />
                            )}
                            {translate(RECIPES.editor_save)}
                        </Button>
                    )}
                    {ready ? (
                    <Button size="sm" variant="default" className="ms-2" onClick={handleRun}>
                        {translate(RECIPES.editor_run)}
                    </Button>
                ) : (
                    <Button size="sm" variant="outline" disabled className="ms-2" title={runBlockers.join("; ")}>
                        {translate(RECIPES.editor_run)}
                    </Button>
                )}
            </div>
        </div>
        </div>
    );
}

