"use client";

import { useState, useEffect, useCallback } from "react";
import { useParams, useRouter, usePathname } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import RecipeListPanel, { type RecipeListRecipe } from "@/components/recipe/RecipeListPanel";
import { RECIPES } from "./translations";
import { COMMON } from "@/app/common/translations";
import { toast } from "sonner";
import {
    AlertDialog,
    AlertDialogAction,
    AlertDialogCancel,
    AlertDialogContent,
    AlertDialogDescription,
    AlertDialogFooter,
    AlertDialogHeader,
    AlertDialogTitle,
} from "@/components/ui/alert-dialog";

export default function RecipesLayout({
    children,
}: {
    children: React.ReactNode;
}) {
    const pathname = usePathname();
    const router = useRouter();
    const params = useParams();
    const translate = useTranslate();

    const [recipes, setRecipes] = useState<RecipeListRecipe[]>([]);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [recipeToDelete, setRecipeToDelete] = useState<string | null>(null);
    const [deleting, setDeleting] = useState(false);

    const selectedId = (params?.id as string) || null;

    const fetchRecipes = useCallback(async () => {
        try {
            setLoading(true);
            setError(null);
            const res = await apiFetch("/api/recipes?include_library=true");
            if (!res.ok) {
                let errorData: any = {};
                try { const text = await res.text(); if (text) errorData = JSON.parse(text); } catch {}
                throw new Error(getErrorMessageFromData(translate, errorData, RECIPES.list_load_error));
            }
            const data = await res.json();
            setRecipes(data.recipes || []);
        } catch (err: any) {
            setError(err.message || translate(RECIPES.list_load_error));
            toast.error(err.message || translate(RECIPES.list_load_error));
        } finally {
            setLoading(false);
        }
    }, [translate]);

    useEffect(() => {
        fetchRecipes();
    }, [fetchRecipes, pathname]);

    const handleSelectRecipe = (id: string) => {
        router.push(`/recipes/${id}`);
    };

    const handleNewRecipe = () => {
        router.push("/recipes?new=true");
    };

    const handleDeleteClick = (id: string) => {
        setRecipeToDelete(id);
        setDeleteDialogOpen(true);
    };

    const confirmDelete = async () => {
        if (!recipeToDelete) return;
        setDeleting(true);
        try {
            const res = await apiFetch(`/api/recipes/${recipeToDelete}`, {
                method: "DELETE",
            });
            if (!res.ok) {
                let errorData: any = {};
                try { const text = await res.text(); if (text) errorData = JSON.parse(text); } catch {}
                throw new Error(getErrorMessageFromData(translate, errorData, RECIPES.delete_error));
            }
            toast.success(translate(RECIPES.delete_success));
            if (selectedId === recipeToDelete) {
                router.push("/recipes");
            }
            await fetchRecipes();
        } catch (err: any) {
            const msg = err.message || translate(RECIPES.delete_error);
            setError(msg);
            toast.error(msg);
        } finally {
            setDeleting(false);
            setDeleteDialogOpen(false);
            setRecipeToDelete(null);
        }
    };

    // Don't wrap the wizard page or other sub-routes that manage their own layout
    const isStandalone = pathname === "/recipes/new";

    if (isStandalone) {
        return <>{children}</>;
    }

    const deleteRecipeName = recipeToDelete
        ? recipes.find((r) => r.id === recipeToDelete)?.name || ""
        : "";

    return (
        <div className="flex h-[calc(100vh-4rem)]">
            {/* Left panel */}
            <div className="w-72 shrink-0 flex flex-col">
                {error && (
                    <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
                        <span className="text-sm">{error}</span>
                    </div>
                )}
                <RecipeListPanel
                    recipes={recipes}
                    loading={loading}
                    selectedRecipeId={selectedId}
                    onSelectRecipe={handleSelectRecipe}
                    onNewRecipe={handleNewRecipe}
                    onDeleteRecipe={handleDeleteClick}
                />
            </div>

            {/* Right panel */}
            <div className="flex-1 min-w-0">
                {children}
            </div>

            <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{translate(RECIPES.delete_title)}</AlertDialogTitle>
                        <AlertDialogDescription>
                            {translate(RECIPES.delete_confirmation).replace("{name}", deleteRecipeName)}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{translate(COMMON.cancel)}</AlertDialogCancel>
                        <AlertDialogAction onClick={confirmDelete} disabled={deleting}>
                            {deleting ? translate(COMMON.deleting) : translate(RECIPES.delete_button)}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
