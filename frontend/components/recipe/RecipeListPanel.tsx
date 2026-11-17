"use client";

import { useState, useMemo } from "react";
import Link from "next/link";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate } from "@/lib/translation-helpers";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { ArrowRight, Loader2, Plus, Search, Users, Trash2 } from "lucide-react";
import { RECIPES } from "@/app/recipes/translations";
import { formatDate } from "@/lib/date-format";

// Whether a recipe is ready to run is decided by the server, which marks every
// recipe in the list response (`ready`, `crud._recipe_ready`) with the verdict of
// the same validation the executor's pre-flight uses. This panel used to work it
// out for itself, and got it wrong: a switch here asked chi-square stages for
// `factorColumn`/`responseColumn`, which the model never declares for that
// algorithm, so no chi-square recipe built in the editor could read as ready
// (docs/code-quirks.md, 2026-09-25). One definition — on the server — is the fix.

// Derive an analysis type label from the recipe's stages.
function getAnalysisType(stages: any[]): string | null {
    if (!stages || !Array.isArray(stages)) return null;
    const statsStage = stages.find((s: any) => s.type === "statistics");
    if (!statsStage?.config) return null;
    const cfg = statsStage.config;
    // Common technique field names
    return cfg.technique || cfg.analysisType || cfg.method || cfg.test || null;
}

// Derive whether a recipe is "complete" — has dataset, algorithm configured, output configured.

export interface RecipeListRecipe {
    id: string;
    name: string;
    description: string | null;
    datasetName?: string | null;
    stages: any[];
    isOwn: boolean;
    isShared: boolean;
    /** Decided by the server for the list response — see statusColor above. */
    ready?: boolean | null;
    updatedAt: string;
    user?: { name: string | null };
}

interface RecipeListPanelProps {
    recipes: RecipeListRecipe[];
    loading: boolean;
    selectedRecipeId?: string | null;
    onSelectRecipe: (id: string) => void;
    onNewRecipe: () => void;
    onDeleteRecipe?: (id: string) => void;
}

export default function RecipeListPanel({
    recipes,
    loading,
    selectedRecipeId,
    onSelectRecipe,
    onNewRecipe,
    onDeleteRecipe,
}: RecipeListPanelProps) {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const [searchQuery, setSearchQuery] = useState("");

    const filtered = useMemo(() => {
        if (!searchQuery.trim()) return recipes;
        const q = searchQuery.toLowerCase();
        return recipes.filter(
            (r) =>
                r.name.toLowerCase().includes(q) ||
                (r.description && r.description.toLowerCase().includes(q)) ||
                (r.datasetName && r.datasetName.toLowerCase().includes(q))
        );
    }, [recipes, searchQuery]);

    const myRecipes = filtered.filter((r) => r.isOwn === true);
    const sharedRecipes = filtered.filter((r) => r.isOwn === false && r.isShared === true);

    if (!isLanguageLoaded || loading) {
        return (
            <div className="flex items-center justify-center h-full py-12">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="flex flex-col h-full border-e bg-background">
            {/* Header: search + new button */}
            <div className="p-3 space-y-2 border-b">
                <div className="relative">
                    <Search className="absolute start-2.5 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
                    <Input dir="auto"
                        placeholder={translate(RECIPES.panel_search)}
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="ps-8 h-9 text-sm"
                    />
                </div>
                <Button
                    onClick={onNewRecipe}
                    size="sm"
                    className="w-full"
                >
                    <Plus className="me-1.5 h-4 w-4" />
                    {translate(RECIPES.panel_new_button)}
                </Button>
            </div>

            {/* Recipe list */}
            <div className="flex-1 overflow-y-auto">
                {myRecipes.length === 0 && sharedRecipes.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-8 px-4">
                        {searchQuery.trim()
                            ? translate(RECIPES.panel_no_results)
                            : translate(RECIPES.panel_no_recipes)}
                    </p>
                ) : (
                    <>
                        {/* My Recipes section */}
                        {myRecipes.length > 0 && (
                            <div>
                                <div className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider">
                                    {translate(RECIPES.panel_my_recipes)}
                                </div>
                                {myRecipes.map((recipe) => (
                                    <RecipeCard
                                        key={recipe.id}
                                        recipe={recipe}
                                        isSelected={selectedRecipeId === recipe.id}
                                        onClick={() => onSelectRecipe(recipe.id)}
                                        onDelete={onDeleteRecipe ? () => onDeleteRecipe(recipe.id) : undefined}
                                        translate={translate}
                                    />
                                ))}
                            </div>
                        )}

                        {/* Shared Recipes section */}
                        {sharedRecipes.length > 0 && (
                            <div>
                                <div className="px-3 py-2 text-xs font-semibold text-muted-foreground uppercase tracking-wider flex items-center gap-1.5">
                                    <Users className="h-3 w-3" />
                                    {translate(RECIPES.panel_shared_recipes)}
                                </div>
                                {sharedRecipes.map((recipe) => (
                                    <RecipeCard
                                        key={recipe.id}
                                        recipe={recipe}
                                        isSelected={selectedRecipeId === recipe.id}
                                        onClick={() => onSelectRecipe(recipe.id)}
                                        translate={translate}
                                    />
                                ))}
                            </div>
                        )}
                    </>
                )}
            </div>
        </div>
    );
}

// ---- Recipe Card ----

function statusColor(recipe: RecipeListRecipe): string {
    if (recipe.isOwn === false) return "border-s-blue-500"; // shared
    if (recipe.ready === true) return "border-s-green-500"; // complete
    return "border-s-amber-500"; // incomplete / draft
}

function RecipeCard({
    recipe,
    isSelected,
    onClick,
    onDelete,
    translate,
}: {
    recipe: RecipeListRecipe;
    isSelected: boolean;
    onClick: () => void;
    onDelete?: () => void;
    translate: (key: any) => string;
}) {
    const analysisType = getAnalysisType(recipe.stages);
    const ready = recipe.ready === true;
    const shared = recipe.isOwn === false;

    return (
        <div
            onClick={onClick}
            className={`px-3 py-2.5 border-s-[3px] cursor-pointer transition-colors
                ${statusColor(recipe)}
                ${isSelected
                    ? "bg-accent/10 border-e-2 border-e-accent"
                    : "hover:bg-muted/50 border-e-2 border-e-transparent"
                }`}
        >
            {/* Row 1: name + status badges */}
            <div className="flex items-center gap-1.5 min-w-0">
                <span className="font-medium text-sm truncate flex-1">
                    {recipe.name}
                </span>
                {/* Run the recipe. It sits before the status badges, so it is left of
                    the Ready badge on your own recipes and left of the Shared badge on
                    someone else's — a shared recipe is runnable by its group. Always
                    shown, incomplete included: the run reports what is wrong rather than
                    the link being absent. stopPropagation keeps the row's own select
                    handler from firing on the way past. */}
                <Link
                    href={`/recipes/${recipe.id}/execute`}
                    onClick={(e) => e.stopPropagation()}
                    title={translate(RECIPES.editor_run)}
                    className="p-0.5 rounded hover:bg-green-100 text-green-600 hover:text-green-700 shrink-0"
                >
                    <ArrowRight className="h-3.5 w-3.5" />
                </Link>
                {shared && (
                    <span className="text-[10px] bg-blue-100 text-blue-700 px-1.5 py-0.5 rounded font-medium shrink-0">
                        {translate(RECIPES.panel_shared_recipes)}
                    </span>
                )}
                {!shared && (
                    <span
                        className={`text-[10px] px-1.5 py-0.5 rounded font-medium shrink-0 ${
                            ready
                                ? "bg-green-100 text-green-700"
                                : "bg-amber-100 text-amber-700"
                        }`}
                    >
                        {ready
                            ? translate(RECIPES.panel_complete)
                            : translate(RECIPES.panel_incomplete)}
                    </span>
                )}
                {onDelete && (
                    <button
                        type="button"
                        onClick={(e) => {
                            e.stopPropagation();
                            onDelete();
                        }}
                        className="p-0.5 rounded hover:bg-destructive/10 text-muted-foreground hover:text-destructive shrink-0"
                        title={translate(RECIPES.delete)}
                    >
                        <Trash2 className="h-3.5 w-3.5" />
                    </button>
                )}
            </div>

            {/* Row 2: dataset + analysis type */}
            <div className="flex items-center gap-2 mt-0.5 min-w-0">
                {recipe.datasetName && (
                    <span className="text-xs text-muted-foreground truncate">
                        {recipe.datasetName}
                    </span>
                )}
                {analysisType && (
                    <span className="text-[10px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded shrink-0">
                        {analysisType}
                    </span>
                )}
                {!recipe.isOwn && recipe.user?.name && (
                    <span className="text-xs text-muted-foreground truncate">
                        {translate(RECIPES.by_label)} {recipe.user.name}
                    </span>
                )}
            </div>

            {/* Row 3: last updated + description */}
            <div className="flex items-center gap-2 mt-0.5 min-w-0">
                <span className="text-[11px] text-muted-foreground/70 shrink-0">
                    {translate(RECIPES.panel_updated)}{" "}
                    {formatDate(recipe.updatedAt)}
                </span>
                {recipe.description && (
                    <span className="text-[11px] text-muted-foreground/60 truncate">
                        {recipe.description}
                    </span>
                )}
            </div>
        </div>
    );
}
