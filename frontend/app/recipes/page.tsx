"use client";

import { Suspense, useCallback, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import RecipeEditorPanel from "@/components/recipe/RecipeEditorPanel";
import { RECIPES } from "./translations";
import { ProtectedRoute } from "@/components/protected-route";
import { toast } from "sonner";

function RecipesPageContent() {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const searchParams = useSearchParams();
    const router = useRouter();
    const isNew = searchParams.get("new") === "true";
    const [saveError, setSaveError] = useState<string | null>(null);

    const handleSave = useCallback(async (name: string, stages: any[] = [], afterSaveRoute?: string) => {
        setSaveError(null);
        const dataSelection = stages.find((s) => s?.type === "data_selection");
        try {
            const res = await apiFetch("/api/recipes", {
                method: "POST",
                body: JSON.stringify({
                    name,
                    description: "",
                    stages,
                    datasetId: dataSelection?.config?.datasetId || null,
                    shared: false,
                    recipeGroup: "00",
                    preparationRuleIds: dataSelection?.config?.transformIds || [],
                }),
            });
            if (!res.ok) {
                let errorData: any = {};
                try { const text = await res.text(); if (text) errorData = JSON.parse(text); } catch {}
                const msg = getErrorMessageFromData(translate, errorData, { key: "recipes.save_error", fallback: "Failed to save recipe" });
                setSaveError(msg);
                throw new Error(msg);
            }
            const data = await res.json();
            toast.success(translate({ key: "recipes.save_success", fallback: "Recipe saved" }));
            router.push(afterSaveRoute ? `/recipes/${data.recipe_id}/execute` : `/recipes/${data.recipe_id}`);
        } catch (err: any) {
            const msg = err.message || translate({ key: "recipes.save_error", fallback: "Failed to save recipe" });
            if (!saveError) setSaveError(msg);
            toast.error(msg);
        }
    }, [translate, router, saveError]);

    if (!isLanguageLoaded) return null;

    if (isNew) {
        return (
            <RecipeEditorPanel
                recipe={{
                    id: "",
                    name: "",
                    description: null,
                    stages: [],
                }}
                loading={false}
                isCreate
                onSave={handleSave}
                saveError={saveError}
            />
        );
    }

    return (
        <div className="flex items-center justify-center h-full">
            <p className="text-muted-foreground text-sm whitespace-pre-line text-center max-w-md leading-relaxed">
                {translate(RECIPES.editor_placeholder)}
            </p>
        </div>
    );
}

export default function RecipesPage() {
    return (
        <ProtectedRoute>
            <Suspense fallback={null}>
                <RecipesPageContent />
            </Suspense>
        </ProtectedRoute>
    );
}
