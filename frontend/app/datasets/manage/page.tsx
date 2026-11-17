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
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, Table, Trash2, Upload, Database, Users, FlaskConical, Filter } from "lucide-react";
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
import { DATASET_UPLOAD } from "../upload/translations";
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
    storageType?: string | null;
    sourceOrigin?: string | null;
    sourceDatasetId?: string | null;
    databaseName?: string | null;
    userName?: string | null;
    /** The materialisation choice, and whether the table it asks for exists. */
    materialized?: boolean;
    materializedAt?: string | null;
    materializeError?: string | null;
}

function ManageDatasetsContent() {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const router = useRouter();

    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [loading, setLoading] = useState(true);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [groupMap, setGroupMap] = useState<Record<string, string>>({});
    const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
    const [deleteTarget, setDeleteTarget] = useState<{ id: string; name: string } | null>(null);
    const [deleting, setDeleting] = useState(false);
    const [filter, setFilter] = useState<string>("all");

    const dismissError = () => setErrorMessage(null);

    const fetchDatasets = useCallback(async () => {
        setLoading(true);
        setErrorMessage(null);
        try {
            const res = await apiFetch("/api/datasets");
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                const msg = getErrorMessageFromData(translate, errorData, DATASETS.list_error);
                throw new Error(msg);
            }
            const data = await res.json();
            setDatasets(data.datasets || []);
        } catch (error: any) {
            const msg = error.message || translate(DATASETS.list_error);
            setErrorMessage(msg);
            toast.error(msg);
        } finally {
            setLoading(false);
        }
    }, [translate]);

    useEffect(() => {
        fetchDatasets();
        fetchGroups();
    }, [fetchDatasets]);

    const fetchGroups = useCallback(async () => {
        try {
            const res = await apiFetch("/api/groups");
            if (res.ok) {
                const data = await res.json();
                const map: Record<string, string> = {};
                (data.groups || []).forEach((g: { groupId: string; groupDescription: string }) => {
                    map[g.groupId] = g.groupDescription || g.groupId;
                });
                setGroupMap(map);
            }
        } catch { /* non-critical */ }
    }, []);

    const handleToggleShared = async (datasetId: string, makeShared: boolean) => {
        try {
            const res = await apiFetch(`/api/datasets/${datasetId}/share`, {
                method: "PATCH",
                body: JSON.stringify({ shared: makeShared }),
            });
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(getErrorMessageFromData(translate, errorData, DATASETS.share_error));
            }
            const result = await res.json();
            setDatasets((prev) =>
                prev.map((ds) =>
                    ds.id === datasetId
                        ? { ...ds, datasetGroup: result.datasetGroup, isShared: makeShared }
                        : ds
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
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(getErrorMessageFromData(translate, errorData, DATASETS.delete.error));
            }
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

    const datasetCategory = (ds: Dataset): string => {
        const key = ds.sourceOrigin || ds.sourceType;
        if (key === "table" || key === "view") {
            return ds.storageType || "postgresql";
        }
        return key;
    };

    const sourceLabel = (category: string) => {
        switch (category) {
            case "upload": return translate(DATASETS.type.upload);
            case "table": return translate(DATASETS.type.table);
            case "view": return translate(DATASETS.type.view);
            case "virtual": return translate(DATASETS.type.virtual);
            case "notebook": return translate(DATASETS.type.notebook);
            case "postgresql": return translate(DATASETS.type.postgresql);
            case "mysql": return translate(DATASETS.type.mysql);
            case "mssql": return translate(DATASETS.type.mssql);
            case "access": return translate(DATASETS.type.access);
            default: return category;
        }
    };

    // The type chip describes what the row *is*; where its data came from is carried by the
    // "Created from" line beneath it, where the parent is known. A cleaned copy is written as
    // sourceType='upload' — its own table in workbench_data — with sourceOrigin set to the
    // root it was cleaned from, so labelling it by datasetCategory called that table
    // "Virtual" (or "PostgreSQL") while nothing about it was virtual.
    const datasetType = (ds: Dataset): string => {
        if (ds.sourceOrigin) return translate(DATASETS.type.cleaned_copy);
        return sourceLabel(datasetCategory(ds));
    };

    const matchesFilter = (ds: Dataset, f: string): boolean => {
        switch (f) {
            case "all": return true;
            case "cleaned": return !!ds.sourceOrigin;
            case "shared": return ds.isShared === true;
            case "not_shared": return ds.isShared !== true;
            default: return datasetCategory(ds) === f;
        }
    };

    const visibleDatasets = datasets.filter((ds) => matchesFilter(ds, filter));

    const parentName = (ds: Dataset): string | null => {
        if (!ds.sourceDatasetId) return null;
        const parent = datasets.find((d) => d.id === ds.sourceDatasetId);
        return parent ? parent.name : null;
    };

    if (!isLanguageLoaded || loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-center">
                    <Loader2 className="animate-spin h-8 w-8 mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">{translate(COMMON.loading)}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="flex items-center justify-between">
                <h1 className="text-3xl font-bold flex items-center gap-2">
                    <Table className="h-7 w-7" />
                    {translate(DATASETS.all_datasets)}
                </h1>
                <div className="flex gap-2">
                    <Link href="/datasets/upload">
                        <Button variant="outline" size="sm">
                            <Upload className="h-4 w-4 me-1" />
                            {translate(DATASETS.upload_button)}
                        </Button>
                    </Link>
                    <Link href="/datasets/define">
                        <Button variant="outline" size="sm">
                            <Database className="h-4 w-4 me-1" />
                            {translate(DATASETS.define_button)}
                        </Button>
                    </Link>
                </div>
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
                        <Table className="h-12 w-12 mx-auto mb-3 text-muted-foreground opacity-50" />
                        <p className="text-muted-foreground mb-4">{translate(DATASETS.no_datasets)}</p>
                        <div className="flex gap-2 justify-center">
                            <Link href="/datasets/upload">
                                <Button>{translate(DATASETS.upload_first)}</Button>
                            </Link>
                            <Link href="/datasets/define">
                                <Button variant="outline">{translate(DATASETS.define_button)}</Button>
                            </Link>
                        </div>
                    </CardContent>
                </Card>
            ) : (
                <Card>
                    <CardHeader className="flex flex-row items-center justify-between space-y-0">
                        <CardTitle>
                            {translate(DATASETS.all_datasets)} ({visibleDatasets.length})
                        </CardTitle>
                        <div className="flex items-center gap-2">
                            <Filter className="h-4 w-4 text-muted-foreground" />
                            <Select value={filter} onValueChange={(value) => setFilter(value || "all")}>
                                <SelectTrigger className="w-44">
                                    <SelectValue placeholder={translate(DATASETS.filter.all)} />
                                </SelectTrigger>
                                <SelectContent alignItemWithTrigger={false}>
                                    <SelectItem value="all">{translate(DATASETS.filter.all)}</SelectItem>
                                    <SelectItem value="virtual">{translate(DATASETS.filter.virtual)}</SelectItem>
                                    <SelectItem value="upload">{translate(DATASETS.filter.uploads)}</SelectItem>
                                    <SelectItem value="notebook">{translate(DATASETS.filter.notebooks)}</SelectItem>
                                    <SelectItem value="postgresql">{translate(DATASETS.filter.postgresql)}</SelectItem>
                                    <SelectItem value="mysql">{translate(DATASETS.filter.mysql)}</SelectItem>
                                    <SelectItem value="mssql">{translate(DATASETS.filter.mssql)}</SelectItem>
                                    <SelectItem value="access">{translate(DATASETS.filter.access)}</SelectItem>
                                    <SelectItem value="cleaned">{translate(DATASETS.filter.cleaned)}</SelectItem>
                                    <SelectItem value="shared">{translate(DATASETS.filter.shared)}</SelectItem>
                                    <SelectItem value="not_shared">{translate(DATASETS.filter.not_shared)}</SelectItem>
                                </SelectContent>
                            </Select>
                        </div>
                    </CardHeader>
                    <CardContent>
                        <div className="space-y-1">
                            {visibleDatasets.map((ds) => {
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
                                                    <>
                                                        <span className="text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded flex items-center gap-1">
                                                            <Users className="h-3 w-3" />
                                                            {translate(DATASETS.shared_badge)}
                                                        </span>
                                                        {ds.materialized && !ds.materializedAt && (
                                                            // A failed build shown only at save time is
                                                            // invisible by the next morning. This is where
                                                            // a user finds it later.
                                                            <span
                                                                className="rounded px-1.5 py-0.5 text-xs font-medium bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300"
                                                                title={ds.materializeError || undefined}
                                                            >
                                                                {translate(DATASETS.table_not_built)}
                                                            </span>
                                                        )}
                                                        {ds.datasetGroup && groupMap[ds.datasetGroup] && (
                                                            <span className="text-xs text-muted-foreground">
                                                                {ds.datasetGroup}: {groupMap[ds.datasetGroup]}
                                                            </span>
                                                        )}
                                                    </>
                                                )}
                                                <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded">
                                                    {datasetType(ds)}
                                                </span>
                                                {ds.databaseName && (
                                                    <span className="text-xs text-muted-foreground">
                                                        {translate(DATASETS.database_label)}: {ds.databaseName}
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
                                                {ds.sourceDatasetId && (
                                                    <span className="text-xs text-muted-foreground">
                                                        {translate(DATASETS.created_from).replace("{name}", parentName(ds) || translate(DATASETS.source_unavailable))}
                                                    </span>
                                                )}
                                                <span className="text-xs text-muted-foreground">{formatDateTime(ds.createdAt)}</span>
                                            </div>
                                        </div>
                                        <div className="flex items-center gap-2 flex-shrink-0 ms-4">
                                            <Button
                                                variant="ghost"
                                                size="sm"
                                                className="h-8 text-xs"
                                                onClick={() => router.push(`/datasets/${ds.id}/transforms`)}
                                            >
                                                <FlaskConical className="h-4 w-4 me-1" />
                                                {translate(DATASETS.transform_button)}
                                            </Button>
                                            {isOwn && (
                                                <Switch
                                                    checked={isShared}
                                                    onCheckedChange={() => handleToggleShared(ds.id, !isShared)}
                                                    className="scale-75"
                                                    title={isShared ? translate(DATASETS.unshare) : translate(DATASETS.share)}
                                                />
                                            )}
                                            {isOwn && (
                                                <Button
                                                    variant="ghost"
                                                    size="icon"
                                                    className="h-8 w-8 text-muted-foreground hover:text-destructive"
                                                    onClick={() => { setDeleteTarget({ id: ds.id, name: ds.name }); setDeleteDialogOpen(true); }}
                                                    title={translate(DATASETS.delete.title)}
                                                >
                                                    <Trash2 className="h-4 w-4" />
                                                </Button>
                                            )}
                                        </div>
                                    </div>
                                );
                            })}
                            {visibleDatasets.length === 0 && (
                                <p className="text-muted-foreground py-4 text-center">{translate(DATASETS.filter.no_match)}</p>
                            )}
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

export default function ManageDatasetsPage() {
    return (
        <ProtectedRoute>
            <ManageDatasetsContent />
        </ProtectedRoute>
    );
}
