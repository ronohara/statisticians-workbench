"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { formatDateTime } from "@/lib/date-format";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Loader2, BookOpen, Trash2, Table } from "lucide-react";
import { toast } from "sonner";

import { NOTEBOOKS } from "./translations";

interface ImportEntry {
    id: string;
    notebook_name: string;
    imported_at: string;
    status: string;
    tables_created: string[];
    storage_type: string;
    title: string;
    table_count: number;
    notebook_group?: string;
    isShared?: boolean;
    is_owner?: boolean;
}

function NotebookListContent() {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const router = useRouter();

    const [imports, setImports] = useState<ImportEntry[]>([]);
    const [loading, setLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);

    const dismissError = () => setErrorMessage(null);
    const dismissSuccess = () => setSuccessMessage(null);

    const fetchImports = useCallback(async () => {
        setLoading(true);
        setErrorMessage(null);
        try {
            const res = await apiFetch("/api/notebooks/imports");
            if (!res.ok) throw new Error(translate(NOTEBOOKS.fetch_error));
            const data = await res.json();
            setImports(data.imports || []);
        } catch (e: any) {
            setErrorMessage(e.message);
        } finally {
            setLoading(false);
        }
    }, [translate]);

    useEffect(() => {
        fetchImports();
    }, [fetchImports]);

    const handleDelete = async (id: string, name: string) => {
        if (!confirm(translate(NOTEBOOKS.delete_confirm).replace("{name}", name))) return;
        try {
            const res = await apiFetch(`/api/notebooks/imports/${id}`, {
                method: "DELETE",
            });
            if (!res.ok) throw new Error(translate(NOTEBOOKS.delete_failed));
            setImports((prev) => prev.filter((imp) => imp.id !== id));
            toast.success(translate(NOTEBOOKS.import_deleted));
        } catch (e: any) {
            setErrorMessage(e.message || translate(NOTEBOOKS.delete_failed));
            toast.error(e.message || translate(NOTEBOOKS.delete_failed));
        }
    };

    const handleToggleShared = async (importId: string, makeShared: boolean) => {
        try {
            const res = await apiFetch(`/api/notebooks/imports/${importId}`, {
                method: "PATCH",
                body: JSON.stringify({ shared: makeShared }),
            });
            if (!res.ok) throw new Error(translate(NOTEBOOKS.share_error));
            const result = await res.json();
            setImports((prev) =>
                prev.map((imp) =>
                    imp.id === importId
                        ? { ...imp, isShared: makeShared, notebook_group: result.notebook_group }
                        : imp
                )
            );
            setErrorMessage(null);
            setSuccessMessage(makeShared ? translate(NOTEBOOKS.shared) : translate(NOTEBOOKS.unshared));
            toast.success(makeShared ? translate(NOTEBOOKS.shared) : translate(NOTEBOOKS.unshared));
        } catch (e: any) {
            setSuccessMessage(null);
            setErrorMessage(e.message || translate(NOTEBOOKS.share_error));
            toast.error(e.message || translate(NOTEBOOKS.share_error));
        }
    };

    if (!isLanguageLoaded || loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="animate-spin h-8 w-8 mx-auto" />
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                    <BookOpen className="h-7 w-7" />
                    <h1 className="text-3xl font-bold">{translate(NOTEBOOKS.list_title)}</h1>
                </div>
            </div>

            {errorMessage && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between text-sm">
                    <span>{errorMessage}</span>
                    <button onClick={dismissError} className="text-red-500 hover:text-red-700">&times;</button>
                </div>
            )}

            {successMessage && (
                <div className="p-3 bg-green-50 border border-green-200 rounded-md text-green-800 flex items-center justify-between text-sm">
                    <span>{successMessage}</span>
                    <button onClick={dismissSuccess} className="text-green-500 hover:text-green-700">&times;</button>
                </div>
            )}

            {imports.length === 0 ? (
                <Card>
                    <CardContent className="py-12 text-center">
                        <BookOpen className="h-12 w-12 mx-auto mb-3 text-muted-foreground opacity-50" />
                        <p className="text-muted-foreground">{translate(NOTEBOOKS.no_imports)}</p>
                    </CardContent>
                </Card>
            ) : (
                <Card>
                    <CardContent className="pt-6">
                        <div className="space-y-1">
                            {imports.map((imp) => {
                                const isShared = !!(imp.isShared);
                                const isOwner = imp.is_owner !== false;
                                return (
                                    <div
                                        key={imp.id}
                                        className="flex items-center justify-between p-3 rounded-md hover:bg-muted/50 transition-colors border border-transparent hover:border-muted"
                                    >
                                        <div className="flex-1 min-w-0">
                                            <div className="flex items-center gap-2">
                                                <BookOpen className="h-4 w-4 text-muted-foreground" />
                                                <span className="font-medium truncate">
                                                    {imp.title || imp.notebook_name}
                                                </span>
                                                {isShared && (
                                                    <span className="text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded">
                                                        {translate(NOTEBOOKS.shared_badge)}
                                                    </span>
                                                )}
                                                <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                                                    {imp.storage_type}
                                                </span>
                                            </div>
                                            <div className="flex items-center gap-2 mt-0.5 text-xs text-muted-foreground">
                                                <Table className="h-3 w-3" />
                                                <span>
                                                    {translate(NOTEBOOKS.table_count)
                                                        .replace("{count}", String(imp.table_count))
                                                        .replace("{plural}", imp.table_count !== 1 ? "s" : "")}
                                                </span>
                                                <span>·</span>
                                                <span>{formatDateTime(imp.imported_at)}</span>
                                                {imp.tables_created.length > 0 && (
                                                    <>
                                                        <span>·</span>
                                                        <span className="font-mono text-xs truncate max-w-xs">
                                                            {imp.tables_created.map(t => t.split(".").pop()).join(", ")}
                                                        </span>
                                                    </>
                                                )}
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-1 flex-shrink-0 ms-4">
                                            <span className="text-xs text-muted-foreground">{translate(NOTEBOOKS.share_label)}</span>
                                            <Switch
                                                checked={isShared}
                                                onCheckedChange={(checked) => handleToggleShared(imp.id, checked)}
                                                disabled={!isOwner}
                                                aria-label={translate(NOTEBOOKS.share_label)}
                                                title={translate(NOTEBOOKS.share_label)}
                                                className="scale-75"
                                            />
                                            <Button
                                                variant="ghost"
                                                size="icon"
                                                className="h-8 w-8 text-muted-foreground hover:text-destructive"
                                                onClick={() => handleDelete(imp.id, imp.notebook_name)}
                                                title={translate(NOTEBOOKS.delete_title)}
                                            >
                                                <Trash2 className="h-4 w-4" />
                                            </Button>
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}
        </div>
    );
}

export default function NotebookListPage() {
    return (
        <ProtectedRoute>
            <NotebookListContent />
        </ProtectedRoute>
    );
}
