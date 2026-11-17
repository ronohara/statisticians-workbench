"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { formatDateTime } from "@/lib/date-format";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { Loader2, FileSpreadsheet, Trash2, Upload, ExternalLink, Users } from "lucide-react";
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
import Link from "next/link";

import { DATASETS } from "../translations";
import { COMMON } from "@/app/common/translations";

interface Dataset {
    id: string;
    name: string;
    filePath: string | null;
    description: string | null;
    createdAt: string;
    datasetGroup: string;
    userId: string;
    isOwn: boolean;
    isShared: boolean;
    sourceType: string;
    userName?: string | null;
}

function UploadedListContent() {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const router = useRouter();

    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [loading, setLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
    const [deleting, setDeleting] = useState(false);

    const dismissError = () => setErrorMessage(null);

    const fetchDatasets = useCallback(async () => {
        setLoading(true);
        setErrorMessage(null);
        try {
            const res = await apiFetch("/api/datasets");
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(getErrorMessageFromData(translate, errorData, DATASETS.list_error));
            }
            const data = await res.json();
            const uploads = (data.datasets || []).filter((ds: Dataset) => ds.sourceType === "upload");
            setDatasets(uploads);
        } catch (error: any) {
            const msg = error.message || translate(DATASETS.list_error);
            setErrorMessage(msg);
        } finally {
            setLoading(false);
        }
    }, [translate]);

    useEffect(() => { fetchDatasets(); }, [fetchDatasets]);

    const handleToggleShared = async (datasetId: string, makeShared: boolean) => {
        try {
            const res = await apiFetch(`/api/datasets/${datasetId}/share`, {
                method: "PATCH",
                body: JSON.stringify({ shared: makeShared }),
            });
            if (!res.ok) throw new Error(getErrorMessageFromData(translate, await res.json().catch(() => ({})), DATASETS.share_error));
            const result = await res.json();
            setDatasets((prev) =>
                prev.map((ds) =>
                    ds.id === datasetId ? { ...ds, datasetGroup: result.datasetGroup } : ds
                )
            );
            toast.success(makeShared ? translate(DATASETS.shared) : translate(DATASETS.unshared));
        } catch (error: any) {
            const msg = error.message || translate(DATASETS.share_error);
            setErrorMessage(msg);
            toast.error(msg);
        }
    };

    const confirmDeleteDataset = async () => {
        if (!deleteTarget) return;
        setDeleting(true);
        try {
            const res = await apiFetch(`/api/datasets/${deleteTarget.id}`, {
                method: "DELETE",
            });
            if (!res.ok) throw new Error(getErrorMessageFromData(translate, await res.json().catch(() => ({})), DATASETS.delete.error));
            setDatasets((prev) => prev.filter((ds) => ds.id !== deleteTarget.id));
            toast.success(translate(DATASETS.delete.success));
        } catch (error: any) {
            toast.error(error.message || translate(DATASETS.delete.error));
        } finally {
            setDeleting(false);
            setDeleteDialogOpen(false);
            setDeleteTarget(null);
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
                <h1 className="text-3xl font-bold flex items-center gap-2">
                    <FileSpreadsheet className="h-7 w-7" />
                    {translate(DATASETS.uploaded_title)}
                </h1>
                <Link href="/datasets/upload">
                    <Button variant="outline" size="sm">
                        <Upload className="h-4 w-4 me-1" />
                        {translate(DATASETS.upload_new)}
                    </Button>
                </Link>
            </div>

            {errorMessage && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
                    <span className="text-sm">{errorMessage}</span>
                    <button onClick={dismissError} className="text-red-500 hover:text-red-700">&times;</button>
                </div>
            )}

            {datasets.length === 0 ? (
                <Card>
                    <CardContent className="py-12 text-center">
                        <FileSpreadsheet className="h-12 w-12 mx-auto mb-3 text-muted-foreground opacity-50" />
                        <p className="text-muted-foreground mb-4">{translate(DATASETS.no_uploaded)}</p>
                        <Link href="/datasets/upload">
                            <Button>{translate(DATASETS.upload_first_file)}</Button>
                        </Link>
                    </CardContent>
                </Card>
            ) : (
                <Card>
                    <CardHeader>
                        <CardTitle>
                            {translate(DATASETS.upload_count)
                                .replace("{count}", String(datasets.length))
                                .replace("{plural}", datasets.length !== 1 ? "s" : "")}
                        </CardTitle>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-1">
                            {datasets.map((ds) => {
                                const isShared = ds.isShared === true;
                                const isOwn = ds.isOwn !== undefined ? ds.isOwn : true;
                                return (
                                    <div
                                        key={ds.id}
                                        className="flex items-center justify-between p-3 rounded-md hover:bg-muted/50 transition-colors border border-transparent hover:border-muted"
                                    >
                                        <div className="flex-1 min-w-0 cursor-pointer" onClick={() => router.push(`/datasets/${ds.id}`)}>
                                            <div className="flex items-center gap-2">
                                                <span className="font-medium truncate">{ds.name}</span>
                                                {isShared && (
                                                    <span className="text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded flex items-center gap-1">
                                                        <Users className="h-3 w-3" />
                                                        {translate(DATASETS.shared_badge)}
                                                    </span>
                                                )}
                                                {!isOwn && ds.userName && (
                                                    <span className="text-xs text-muted-foreground">
                                                        {translate(DATASETS.by_label)} {ds.userName}
                                                    </span>
                                                )}
                                            </div>
                                            <div className="flex items-center gap-2 mt-0.5">
                                                {ds.description && (
                                                    <span className="text-xs text-muted-foreground truncate max-w-md">{ds.description}</span>
                                                )}
                                                <span className="text-xs text-muted-foreground">{formatDateTime(ds.createdAt)}</span>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2 flex-shrink-0 ms-4">
                                            <Button variant="ghost" size="icon" className="h-8 w-8"
                                                    onClick={() => router.push(`/datasets/${ds.id}`)}
                                                    title={translate(DATASETS.view_dataset_title)}>
                                                <ExternalLink className="h-4 w-4" />
                                            </Button>
                                            {isOwn && (
                                                <Switch checked={isShared || false}
                                                        onCheckedChange={() => handleToggleShared(ds.id, !isShared)}
                                                        className="scale-75"
                                                        title={isShared ? translate(DATASETS.unshare) : translate(DATASETS.share)} />
                                            )}
                                            {isOwn && (
                                                <Button variant="ghost" size="icon"
                                                        className="h-8 w-8 text-muted-foreground hover:text-destructive"
                                                        onClick={() => { setDeleteTarget({ id: ds.id, name: ds.name }); setDeleteDialogOpen(true); }}
                                                        title={translate(DATASETS.delete.title)}>
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                        </div>
                    </CardContent>
                </Card>
            )}

      {/* Delete Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{translate(DATASETS.delete.confirm)}</AlertDialogTitle>
            <AlertDialogDescription>
              {deleteTarget?.name ? `"${deleteTarget.name}" — ` : ""}{translate(COMMON.cannot_undo)}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{translate(COMMON.cancel)}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteDataset} disabled={deleting}>
              {deleting ? translate(COMMON.deleting) : translate(COMMON.delete)}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
        </div>
    );
}

export default function UploadedListPage() {
    return (
        <ProtectedRoute>
            <UploadedListContent />
        </ProtectedRoute>
    );
}
