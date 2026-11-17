"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams, useSearchParams } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Loader2, Save, Trash2 } from "lucide-react";
import {
    AlertDialog, AlertDialogAction, AlertDialogCancel,
    AlertDialogContent, AlertDialogDescription,
    AlertDialogFooter, AlertDialogHeader, AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import TransformOperationBuilder from "@/components/recipe/TransformOperationBuilder";
import type { TransformOp, ColumnInfo } from "@/components/recipe/TransformOperationBuilder";
import PreparationPreviewPanel from "@/components/preparation-preview-panel";
import { DATASETS } from "../../../translations";
import { TRANSFORMS_EDITOR } from "../translations";
import { COMMON } from "@/app/common/translations";

export default function TransformEditorPage() {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const router = useRouter();
    const params = useParams();
    const searchParamsHook = useSearchParams();
    const datasetId = params.id as string;
    const transformId = params.transformId as string;

    const [name, setName] = useState("");
    const [description, setDescription] = useState("");
    const [operations, setOperations] = useState<TransformOp[]>([]);
    const [columns, setColumns] = useState<ColumnInfo[]>([]);
    const [isOwn, setIsOwn] = useState(false);
    const [loading, setLoading] = useState(true);
    const [saving, setSaving] = useState(false);
    const [error, setError] = useState<string | null>(null);

    const [deleteOpen, setDeleteOpen] = useState(false);
    const [deleting, setDeleting] = useState(false);

    useEffect(() => {
        const load = async () => {
            try {
                setLoading(true);
                const [schemaRes, tfRes] = await Promise.all([
                    apiFetch(`/api/datasets/${datasetId}/schema`),
                    apiFetch(`/api/datasets/${datasetId}/transforms/${transformId}`),
                ]);

                if (schemaRes.ok) {
                    const s = await schemaRes.json();
                    setColumns((s.columns || []).map((c: any) => ({
                        name: c.name,
                        dtype: c.type || c.dtype,
                        is_numeric: c.is_numeric,
                        is_categorical: c.is_categorical,
                    })));
                }

                if (!tfRes.ok) {
                    const ed = await tfRes.json().catch(() => ({}));
                    throw new Error(getErrorMessageFromData(translate, ed, TRANSFORMS_EDITOR.load_error));
                }
                const tfData = await tfRes.json();
                const tf = tfData.transform || tfData;
                setName(tf.name || "");
                setDescription(tf.description || "");
                setOperations(Array.isArray(tf.operations) ? tf.operations : []);
                setIsOwn(tf.isOwn === true);
            } catch (err: any) {
                setError(err.message || translate(TRANSFORMS_EDITOR.load_error));
            } finally {
                setLoading(false);
            }
        };
        load();
    }, [datasetId, transformId, translate]);

    const handleSave = async () => {
        if (!name.trim()) {
            setError(translate(TRANSFORMS_EDITOR.name_required));
            return;
        }
        setSaving(true);
        setError(null);
        try {
            const res = await apiFetch(`/api/datasets/${datasetId}/transforms/${transformId}`, {
                method: "PUT",
                body: JSON.stringify({
                    name: name.trim(),
                    description: description.trim() || null,
                    operations: operations.filter((op) => op.type),
                }),
            });
            if (!res.ok) {
                const ed = await res.json().catch(() => ({}));
                throw new Error(ed.detail || translate(DATASETS.transforms_create_error));
            }
            toast.success(translate(TRANSFORMS_EDITOR.save_success));
            // Navigate to list — clears detail pane (visual feedback) and triggers list refresh
            const sq = searchParamsHook.get("returnTo");
            const rq = searchParamsHook.get("recipeId");
            const params = new URLSearchParams();
            if (sq) params.set("returnTo", sq);
            if (rq) params.set("recipeId", rq);
            const qs = params.toString();
            router.push(`/datasets/${datasetId}/transforms${qs ? `?${qs}` : ""}`);
        } catch (err: any) {
            setError(err.message || translate(DATASETS.transforms_create_error));
        } finally {
            setSaving(false);
        }
    };

    const handleDelete = async () => {
        setDeleting(true);
        setError(null);
        try {
            const res = await apiFetch(`/api/datasets/${datasetId}/transforms/${transformId}`, {
                method: "DELETE",
            });
            if (!res.ok) {
                const ed = await res.json().catch(() => ({}));
                throw new Error(ed.detail || translate(DATASETS.transforms_delete_error));
            }
            toast.success(translate(TRANSFORMS_EDITOR.delete_success));
            router.push(`/datasets/${datasetId}/transforms`);
        } catch (err: any) {
            const msg = err.message || translate(DATASETS.transforms_delete_error);
            setError(msg);
            toast.error(msg);
        } finally {
            setDeleting(false);
            setDeleteOpen(false);
        }
    };

    if (!isLanguageLoaded) return null;

    if (loading) {
        return (
            <div className="flex items-center justify-center h-full">
                <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (error && !name) {
        return (
            <div className="flex items-center justify-center h-full">
                <p className="text-sm text-destructive">{error}</p>
            </div>
        );
    }

    return (
        <div className="max-w-2xl mx-auto p-4 space-y-5">
            {error && (
                <p className="text-sm text-destructive bg-destructive/10 rounded px-3 py-2">{error}</p>
            )}

            <div className="space-y-3">
                <div>
                    <label className="text-xs font-medium text-muted-foreground">
                        {translate(TRANSFORMS_EDITOR.name_label)}
                    </label>
                    <Input dir="auto"
                        value={name}
                        onChange={(e) => { setName(e.target.value); setError(null); }}
                        placeholder={translate(TRANSFORMS_EDITOR.name_placeholder)}
                        className="h-9 text-sm mt-0.5"
                    />
                </div>
                <div>
                    <label className="text-xs font-medium text-muted-foreground">
                        {translate(TRANSFORMS_EDITOR.description_label)}
                    </label>
                    <Input dir="auto"
                        value={description}
                        onChange={(e) => setDescription(e.target.value)}
                        placeholder={translate(TRANSFORMS_EDITOR.description_placeholder)}
                        className="h-9 text-sm mt-0.5"
                    />
                </div>
            </div>

            <div className="border rounded-lg p-4">
                <TransformOperationBuilder
                    operations={operations}
                    columns={columns}
                    onChange={setOperations}
                    disabled={!isOwn}
                    labels={{
                        addOperation: translate(TRANSFORMS_EDITOR.op_add),
                        removeOperation: translate(TRANSFORMS_EDITOR.op_remove),
                        typePlaceholder: translate(TRANSFORMS_EDITOR.op_type_placeholder),
                        columnPlaceholder: translate(TRANSFORMS_EDITOR.op_column_placeholder),
                        operatorPlaceholder: translate(TRANSFORMS_EDITOR.op_operator_placeholder),
                        valuePlaceholder: translate(TRANSFORMS_EDITOR.op_value_placeholder),
                        methodPlaceholder: translate(TRANSFORMS_EDITOR.op_method_placeholder),
                        targetTypePlaceholder: translate(TRANSFORMS_EDITOR.op_target_type_placeholder),
                        targetNumeric: translate(TRANSFORMS_EDITOR.op_target_numeric),
                        targetDatetime: translate(TRANSFORMS_EDITOR.op_target_datetime),
                        targetString: translate(TRANSFORMS_EDITOR.op_target_string),
                        targetBoolean: translate(TRANSFORMS_EDITOR.op_target_boolean),
                        newNamePlaceholder: translate(TRANSFORMS_EDITOR.op_new_name_placeholder),
                        encodingPlaceholder: translate(TRANSFORMS_EDITOR.op_encoding_placeholder),
                        encodingOnehot: translate(TRANSFORMS_EDITOR.op_encoding_onehot),
                        encodingLabel: translate(TRANSFORMS_EDITOR.op_encoding_label),
                        opTypeLabels: {
                            filter: translate(TRANSFORMS_EDITOR.op_filter),
                            fill_missing: translate(TRANSFORMS_EDITOR.op_fill_missing),
                            drop_column: translate(TRANSFORMS_EDITOR.op_drop_column),
                            convert_type: translate(TRANSFORMS_EDITOR.op_convert_type),
                            normalize: translate(TRANSFORMS_EDITOR.op_normalize),
                            standardize: translate(TRANSFORMS_EDITOR.op_standardize),
                            rename_column: translate(TRANSFORMS_EDITOR.op_rename_column),
                            drop_duplicates: translate(TRANSFORMS_EDITOR.op_drop_duplicates),
                            encode_category: translate(TRANSFORMS_EDITOR.op_encode_category),
                        },
                        filterOperators: [
                            { value: ">", label: translate(TRANSFORMS_EDITOR.filter_op_gt) },
                            { value: "<", label: translate(TRANSFORMS_EDITOR.filter_op_lt) },
                            { value: "=", label: translate(TRANSFORMS_EDITOR.filter_op_eq) },
                            { value: "!=", label: translate(TRANSFORMS_EDITOR.filter_op_neq) },
                            { value: "contains", label: translate(TRANSFORMS_EDITOR.filter_op_contains) },
                            { value: "is_null", label: translate(TRANSFORMS_EDITOR.filter_op_is_null) },
                            { value: "is_not_null", label: translate(TRANSFORMS_EDITOR.filter_op_is_not_null) },
                        ],
                        fillMethods: [
                            { value: "mean", label: translate(TRANSFORMS_EDITOR.fill_mean) },
                            { value: "median", label: translate(TRANSFORMS_EDITOR.fill_median) },
                            { value: "mode", label: translate(TRANSFORMS_EDITOR.fill_mode) },
                            { value: "constant", label: translate(TRANSFORMS_EDITOR.fill_constant) },
                            { value: "drop", label: translate(TRANSFORMS_EDITOR.fill_drop_rows) },
                        ],
                        operationsHeading: translate(TRANSFORMS_EDITOR.operations_heading),
                        emptyStateText: translate(TRANSFORMS_EDITOR.empty_state),
                    }}
                />
            </div>

            <PreparationPreviewPanel
                operations={operations.filter((op) => op.type)}
                datasetId={datasetId}
            />

            {isOwn && (
                <div className="flex items-center gap-2 pt-2">
                    <Button size="sm" onClick={handleSave} disabled={saving}>
                        {saving && <Loader2 className="h-4 w-4 animate-spin me-1.5" />}
                        <Save className="h-4 w-4 me-1.5" />
                        {translate(TRANSFORMS_EDITOR.save_button)}
                    </Button>
                    <Button
                        size="sm"
                        variant="outline"
                        className="text-destructive hover:text-destructive"
                        onClick={() => setDeleteOpen(true)}
                    >
                        <Trash2 className="h-4 w-4 me-1.5" />
                        {translate(TRANSFORMS_EDITOR.delete_button)}
                    </Button>
                </div>
            )}

            <AlertDialog open={deleteOpen} onOpenChange={setDeleteOpen}>
                <AlertDialogContent>
                    <AlertDialogHeader>
                        <AlertDialogTitle>{translate(TRANSFORMS_EDITOR.delete_confirm)}</AlertDialogTitle>
                        <AlertDialogDescription>
                            {name ? `"${name}" — ` : ""}{translate(COMMON.cannot_undo)}
                        </AlertDialogDescription>
                    </AlertDialogHeader>
                    <AlertDialogFooter>
                        <AlertDialogCancel>{translate(COMMON.cancel)}</AlertDialogCancel>
                        <AlertDialogAction onClick={handleDelete} disabled={deleting}>
                            {deleting ? translate(COMMON.deleting) : translate(COMMON.delete)}
                        </AlertDialogAction>
                    </AlertDialogFooter>
                </AlertDialogContent>
            </AlertDialog>
        </div>
    );
}
