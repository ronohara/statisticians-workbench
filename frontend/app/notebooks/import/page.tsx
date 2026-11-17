"use client";

import { useState, useCallback, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, useTranslateKeyWithParams } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { Loader2, Upload, FileJson, BookOpen, Table, Users } from "lucide-react";
import { Switch } from "@/components/ui/switch";
import { DataValue } from "@/components/ui/data-value";

import { NOTEBOOKS } from "../translations";
import { COMMON } from "@/app/common/translations";
import { formatDateTime } from "@/lib/date-format";

async function getToken(): Promise<string> {
    const res = await fetch("/api/auth/token", { credentials: "include" });
    if (!res.ok) throw new Error("Unauthorized");
    const data = await res.json();
    return data.token;
}

interface DataFramePreview {
    index: number;
    columns: string[];
    rows: number;
    cols: number;
    sample: Record<string, any>[];
}

interface NotebookPreview {
    valid: boolean;
    metadata: {
        title: string;
        kernelspec: any;
        language_info: any;
    };
    dataframes: DataFramePreview[];
    dataframe_count: number;
    markdown_preview: string;
    cell_count: number;
    file_size_kb: number;
}

interface ImportResult {
    success: boolean;
    import_id: string;
    notebook_name: string;
    metadata: any;
    tables: { name: string; rows: number; cols: number }[];
    table_count: number;
    imported_at: string;
    storage_type: string;
    dataset_ids?: string[];
}

function NotebookImportContent() {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const tx = useTranslateKeyWithParams();
    const router = useRouter();

    const [file, setFile] = useState<File | null>(null);
    const [preview, setPreview] = useState<NotebookPreview | null>(null);
    const [loading, setLoading] = useState(false);
    const [importing, setImporting] = useState(false);
    const [result, setResult] = useState<ImportResult | null>(null);
    const [error, setError] = useState<string | null>(null);
    const [createDataset, setCreateDataset] = useState(true);
    const [shared, setShared] = useState(false);
    const [isExampleUser, setIsExampleUser] = useState(false);

    const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        const f = e.target.files?.[0] || null;
        setFile(f);
        setPreview(null);
        setResult(null);
        setError(null);
    };

    // Fetch user role for example user check
    useEffect(() => {
        apiFetch("/api/user/role")
            .then(res => res.json())
            .then(data => setIsExampleUser(data.isExampleUser === true))
            .catch(() => {});
    }, []);

    const handlePreview = useCallback(async () => {
        if (!file) {
            setError(translate(NOTEBOOKS.select_file_first));
            return;
        }
        setLoading(true);
        setError(null);
        setResult(null);
        try {
            const token = await getToken();
            const formData = new FormData();
            formData.append("file", file);

            const res = await fetch("/api/notebooks/preview", {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
                body: formData,
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || translate(NOTEBOOKS.parse_error));
            }

            const data: NotebookPreview = await res.json();
            setPreview(data);
            if (data.dataframe_count === 0) {
                setError(translate(NOTEBOOKS.no_dataframes));
            }
        } catch (e: any) {
            setError(e.message);
            setPreview(null);
        } finally {
            setLoading(false);
        }
    }, [file, translate]);

    const handleImport = useCallback(async () => {
        if (!file) {
            setError(translate(NOTEBOOKS.select_file_first));
            return;
        }
        if (!preview) {
            setError(translate(NOTEBOOKS.run_preview_first));
            return;
        }
        if (preview.dataframe_count === 0) {
            setError(translate(NOTEBOOKS.no_dataframes));
            return;
        }
        setImporting(true);
        setError(null);
        try {
            const token = await getToken();
            const formData = new FormData();
            formData.append("file", file);
            formData.append("shared", String(shared));
            formData.append("create_dataset", String(createDataset));
            formData.append("storage_type", "postgresql");
            formData.append("connection_id", "0");
            formData.append("create_database", "false");

            const res = await fetch("/api/notebooks/import", {
                method: "POST",
                headers: { Authorization: `Bearer ${token}` },
                body: formData,
            });

            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                throw new Error(err.detail || tx(NOTEBOOKS.import_failed, { error: `HTTP ${res.status}` }));
            }

            const data: ImportResult = await res.json();
            setResult(data);
            toast.success(translate(NOTEBOOKS.import_success).replace("{count}", String(data.table_count)));
            setTimeout(() => router.push("/notebooks"), 800);
        } catch (e: any) {
            setError(e.message);
            toast.error(e.message);
        } finally {
            setImporting(false);
        }
    }, [file, translate, shared, createDataset, preview]);

    if (!isLanguageLoaded) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="animate-spin h-8 w-8 mx-auto" />
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div className="flex items-center gap-2">
                <BookOpen className="h-7 w-7" />
                <h1 className="text-3xl font-bold">{translate(NOTEBOOKS.import_title)}</h1>
            </div>

            {/* Example user banner */}
            {isExampleUser && (
                <div className="p-3 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-800 text-sm">
                    {translate(NOTEBOOKS.example_banner)}
                </div>
            )}

            {/* File Selection */}
            <Card>
                <CardHeader>
                    <CardTitle className="flex items-center gap-2">
                        <Upload className="h-5 w-5" />
                        {translate(NOTEBOOKS.step1_title)}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                    <Input dir="ltr"
                        type="file"
                        accept=".ipynb"
                        onChange={handleFileChange}
                    />
                    {file && (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground">
                            <FileJson className="h-4 w-4" />
                            <span>{file.name}</span>
                            <span>({(file.size / 1024).toFixed(1)} {translate(NOTEBOOKS.kb_unit)})</span>
                        </div>
                    )}
                    <div className="flex gap-2">
                        <Button
                            onClick={handlePreview}
                        >
                            {loading ? (
                                <><Loader2 className="animate-spin h-4 w-4 me-1" /> {translate(NOTEBOOKS.parsing)}</>
                            ) : (
                                translate(NOTEBOOKS.preview_button)
                            )}
                        </Button>
                    </div>
                    <div className="flex gap-2">
                        <Button
                            onClick={handleImport}
                            variant="default"
                        >
                            {importing ? (
                                <><Loader2 className="animate-spin h-4 w-4 me-1" /> {translate(NOTEBOOKS.importing)}</>
                            ) : (
                                <><Upload className="h-4 w-4 me-1" /> {translate(NOTEBOOKS.import_button)}</>
                            )}
                        </Button>
                    </div>
                    {preview && (
                        <div className="flex items-center gap-2 pt-2 border-t">
                            <Switch
                                checked={shared}
                                onCheckedChange={setShared}
                            />
                            <span className="text-sm">{translate(NOTEBOOKS.share_label)}</span>
                        </div>
                    )}
                    {preview && (
                        <div className="flex items-center gap-2">
                            <Switch
                                checked={createDataset}
                                onCheckedChange={setCreateDataset}
                            />
                            <span className="text-sm">{translate(NOTEBOOKS.create_dataset)}</span>
                        </div>
                    )}
                </CardContent>
            </Card>

            {/* Error */}
            {error && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 text-sm">
                    {error}
                </div>
            )}

            {/* Preview */}
            {preview && (
                <Card>
                    <CardHeader>
                        <CardTitle>{translate(NOTEBOOKS.step2_title)}</CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="grid grid-cols-2 gap-3 text-sm">
                            <div>
                                <span className="font-medium">{translate(NOTEBOOKS.title_label)}</span>{" "}
                                {preview.metadata?.title || translate(COMMON.untitled)}
                            </div>
                            <div>
                                <span className="font-medium">{translate(NOTEBOOKS.kernel_label)}</span>{" "}
                                {preview.metadata?.kernelspec?.display_name || preview.metadata?.kernelspec?.name || translate(COMMON.unknown)}
                            </div>
                            <div>
                                <span className="font-medium">{translate(NOTEBOOKS.cells_label)}</span>{" "}
                                {preview.cell_count}
                            </div>
                            <div>
                                <span className="font-medium">{translate(NOTEBOOKS.dataframes_label)}</span>{" "}
                                {preview.dataframe_count}
                            </div>
                            <div className="col-span-2">
                                <span className="font-medium">{translate(NOTEBOOKS.size_label)}</span>{" "}
                                {preview.file_size_kb} {translate(NOTEBOOKS.kb_unit)}
                            </div>
                        </div>

                        {preview.dataframes.length > 0 && (
                            <div className="space-y-3">
                                <h3 className="font-medium text-sm">{translate(NOTEBOOKS.detected_dataframes)}</h3>
                                {preview.dataframes.map((df) => (
                                    <div key={df.index} className="border rounded-md p-3">
                                        <div className="flex items-center gap-2 mb-2">
                                            <Table className="h-4 w-4 text-muted-foreground" />
                                            <span className="font-mono text-sm">
                                                {translate(NOTEBOOKS.dataframe_prefix)} {df.index + 1}: {translate(NOTEBOOKS.rows_cols_format).replace("{rows}", String(df.rows)).replace("{cols}", String(df.cols))}
                                            </span>
                                        </div>
                                        {/* Two-axis scroller: the box keeps its footprint however
                                            wide or long the DataFrame is — sideways for columns, up
                                            and down for rows (decided 2026-09-25). */}
                                        <div className="max-h-96 overflow-auto">
                                            <table className="text-xs border-collapse w-full">
                                                <thead>
                                                    <tr className="bg-muted">
                                                        {df.columns.map((col) => (
                                                            <th key={col} className="border px-2 py-1 text-start font-medium sticky top-0 z-10 bg-muted">
                                                                {col}
                                                            </th>
                                                        ))}
                                                    </tr>
                                                </thead>
                                                <tbody>
                                                    {df.sample.map((row, i) => (
                                                        <tr key={i}>
                                                            {df.columns.map((col) => (
                                                                <td key={col} className="border px-2 py-1 truncate max-w-[120px]" title={String(row[col] ?? "")}>
                                                                    <DataValue value={String(row[col] ?? "")} />
                                                                </td>
                                                            ))}
                                                        </tr>
                                                    ))}
                                                </tbody>
                                            </table>
                                        </div>
                                    </div>
                                ))}
                            </div>
                        )}

                        {preview.markdown_preview && (
                            <div>
                                <h3 className="font-medium text-sm mb-1">{translate(NOTEBOOKS.doc_preview)}</h3>
                                <div className="text-xs text-muted-foreground bg-muted/50 p-3 rounded-md whitespace-pre-wrap">
                                    {preview.markdown_preview}
                                </div>
                            </div>
                        )}

                        <div className="text-xs text-muted-foreground bg-yellow-50 border border-yellow-200 p-2 rounded">
                            {translate(NOTEBOOKS.sanitised_notice)}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Import Results */}
            {result && (
                <Card className="border-green-200">
                    <CardHeader>
                        <CardTitle className="text-green-700">
                            {translate(NOTEBOOKS.import_complete)}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        <div className="text-sm space-y-1">
                            <div><span className="font-medium">{translate(NOTEBOOKS.notebook_label)}</span> {result.notebook_name}</div>
                            <div><span className="font-medium">{translate(NOTEBOOKS.tables_created_label)}</span> {result.table_count}</div>
                            <div><span className="font-medium">{translate(NOTEBOOKS.storage_label)}</span> {result.storage_type}</div>
                            <div><span className="font-medium">{translate(NOTEBOOKS.imported_at_label)}</span> {formatDateTime(result.imported_at)}</div>
                        </div>
                        {result.dataset_ids && result.dataset_ids.length > 0 && (
                            <div className="bg-green-50 border border-green-200 rounded p-2 text-sm">
                                {translate(NOTEBOOKS.dataset_created)} —{" "}
                                {result.dataset_ids.map((id, i) => (
                                    <span key={id}>
                                        <a href={`/datasets/${id}`} className="text-blue-600 underline">
                                            {translate(COMMON.view_dataset)}
                                        </a>
                                        {i < result.dataset_ids!.length - 1 ? ", " : ""}
                                    </span>
                                ))}
                            </div>
                        )}
                        {result.tables.map((t, i) => (
                            <div key={i} className="border rounded-md p-3">
                                <div className="flex items-center gap-2">
                                    <Table className="h-4 w-4 text-muted-foreground" />
                                    <span className="font-mono text-sm">{t.name.split(".").pop()}</span>
                                    <span className="text-xs text-muted-foreground">
                                        ({translate(NOTEBOOKS.rows_cols_format).replace("{rows}", String(t.rows)).replace("{cols}", String(t.cols))})
                                    </span>
                                </div>
                                <div className="text-xs text-muted-foreground mt-1 font-mono">
                                    {translate(NOTEBOOKS.table_name).replace("{name}", t.name)}
                                </div>
                            </div>
                        ))}
                    </CardContent>
                </Card>
            )}
        </div>
    );
}

export default function NotebookImportPage() {
    return (
        <ProtectedRoute>
            <NotebookImportContent />
        </ProtectedRoute>
    );
}
