"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter, usePathname } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, useTranslateKeyWithParams, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import RecipeEditorPanel, { type RecipeEditorRecipe } from "@/components/recipe/RecipeEditorPanel";
import { RECIPES } from "../translations";
import { toast } from "sonner";
import { Loader2 } from "lucide-react";

export default function RecipeDetailPage() {
    const params = useParams();
    const router = useRouter();
    const translate = useTranslate();
    const tx = useTranslateKeyWithParams();
    const { isLanguageLoaded } = useTranslation();

    const [recipe, setRecipe] = useState<RecipeEditorRecipe | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);
    const [saveError, setSaveError] = useState<string | null>(null);

    const recipeId = params?.id as string;
    const pathname = usePathname();

    useEffect(() => {
        if (!recipeId) return;

        let cancelled = false;

        const fetchRecipe = async () => {
            try {
                setLoading(true);
                setError(null);
                const res = await apiFetch(`/api/recipes/${recipeId}`);
                if (!res.ok) {
                    let errorData: any = {};
                    try { const text = await res.text(); if (text) errorData = JSON.parse(text); } catch {}
                    throw new Error(getErrorMessageFromData(tx, errorData, RECIPES.load_error, { error: `HTTP ${res.status}` }));
                }
                const data = await res.json();
                if (!cancelled) {
                    setRecipe(data);
                }
            } catch (err: any) {
                if (!cancelled) {
                    const msg = err.message || tx(RECIPES.load_error, { error: String(err) });
                    setError(msg);
                    toast.error(msg);
                }
            } finally {
                if (!cancelled) {
                    setLoading(false);
                }
            }
        };

        fetchRecipe();
        return () => { cancelled = true; };
    }, [recipeId, translate, pathname]);

    const handleSave = useCallback(async (name?: string, stages?: any[], afterSaveRoute?: string) => {
        if (!recipe) return;
        setSaveError(null);
        try {
            const resolvedStages = stages || recipe.stages;
            const dataStage = (resolvedStages || []).find((s: any) => s.type === "data_selection");
            const res = await apiFetch(`/api/recipes/${recipeId}`, {
                method: "PUT",
                body: JSON.stringify({
                    name: name || recipe.name,
                    description: recipe.description,
                    datasetId: dataStage?.config?.datasetId || null,
                    stages: resolvedStages,
                    preparationRuleIds: dataStage?.config?.transformIds || [],
                }),
            });
            if (!res.ok) {
                let errorData: any = {};
                try { const text = await res.text(); if (text) errorData = JSON.parse(text); } catch {}
                const msg = getErrorMessageFromData(translate, errorData, RECIPES.editor_save_error);
                setSaveError(msg);
                throw new Error(msg);
            }
            toast.success(translate(RECIPES.editor_save_success));
            router.push(afterSaveRoute || "/recipes");
        } catch (err: any) {
            const msg = err.message || translate(RECIPES.editor_save_error);
            setSaveError(msg);
            toast.error(msg);
        }
    }, [recipe, recipeId, translate]);

    if (!isLanguageLoaded) {
        return (
            <div className="flex items-center justify-center h-full">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (error) {
        return (
            <div className="flex items-center justify-center h-full">
                <p className="text-sm text-destructive">{error}</p>
            </div>
        );
    }

    return (
        <RecipeEditorPanel
            recipe={recipe}
            loading={loading}
            onSave={handleSave}
            saveError={saveError}
        />
    );
}
