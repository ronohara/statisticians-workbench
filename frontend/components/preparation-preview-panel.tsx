"use client";

import { useState, useEffect, useRef } from "react";
import { Loader2, Table } from "lucide-react";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate } from "@/lib/translation-helpers";
import { PREP } from "@/app/datasets/preparation/translations";
import { COMPONENTS } from "@/components/translations";
import { DataValue } from "@/components/ui/data-value";

async function getToken(): Promise<string> {
    const res = await fetch("/api/auth/token", { credentials: "include" });
    if (!res.ok) throw new Error("Unauthorized");
    const data = await res.json();
    return data.token;
}

interface Operation {
    type: string;
    column?: string | null;
    columns?: string[] | null;
    operator?: string | null;
    value?: any;
    method?: string | null;
    target_type?: string | null;
    new_name?: string | null;
    encoding?: string | null;
}

interface PreviewResult {
    before_rows: number;
    after_rows: number;
    before_nulls: Record<string, number>;
    after_nulls: Record<string, number>;
    sample: Record<string, any>[];
}

interface PreparationPreviewPanelProps {
    operations: Operation[];
    datasetId: string;
}

export default function PreparationPreviewPanel({ operations, datasetId }: PreparationPreviewPanelProps) {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const [preview, setPreview] = useState<PreviewResult | null>(null);
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState<string | null>(null);
    const timerRef = useRef<ReturnType<typeof setTimeout> | null>(null);

    useEffect(() => {
        if (!datasetId || operations.length === 0) {
            setPreview(null);
            setError(null);
            return;
        }

        if (timerRef.current) clearTimeout(timerRef.current);

        timerRef.current = setTimeout(async () => {
            setLoading(true);
            setError(null);
            try {
                const token = await getToken();
                const res = await fetch(`/api/datasets/${datasetId}/preparation/preview`, {
                    method: "POST",
                    headers: {
                        "Content-Type": "application/json",
                        Authorization: `Bearer ${token}`,
                    },
                    body: JSON.stringify({ operations }),
                });
                if (!res.ok) throw new Error(await res.text());
                const data = await res.json();
                setPreview(data);
            } catch (e: any) {
                // Try to extract the detail message from the JSON response
                let msg = e.message || "";
                try {
                    const parsed = JSON.parse(msg);
                    if (parsed.detail) msg = typeof parsed.detail === "string" ? parsed.detail : JSON.stringify(parsed.detail);
                } catch { /* not JSON, use raw message */ }
                setError(msg || translate(PREP.preview_error));
            } finally {
                setLoading(false);
            }
        }, 600); // debounce 600ms

        return () => {
            if (timerRef.current) clearTimeout(timerRef.current);
        };
    }, [operations, datasetId, translate]);

    if (!isLanguageLoaded) return null;
    if (operations.length === 0) return null;

    return (
        <div className="border rounded-md p-4 space-y-3 bg-muted/30">
            <h3 className="font-medium text-sm">{translate(PREP.live_preview)}</h3>

            {loading && (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="animate-spin h-4 w-4" />
                    {translate(PREP.preview_loading)}
                </div>
            )}

            {error && (
                <div className="text-sm text-red-600">{error}</div>
            )}

            {preview && !loading && (
                <>
                    <div className="flex items-center gap-4 text-sm">
                        <span>
                            <span className="font-medium">{translate(PREP.before)}:</span>{" "}
                            {preview.before_rows} {translate(PREP.rows)}
                        </span>
                        <span className="text-muted-foreground">→</span>
                        <span>
                            <span className="font-medium">{translate(PREP.after)}:</span>{" "}
                            {preview.after_rows} {translate(PREP.rows)}
                        </span>
                        {preview.before_rows !== preview.after_rows && (
                            <span className="text-xs text-muted-foreground">
                                ({translate(COMPONENTS.preparation_preview.rows_removed).replace("{0}", String(preview.before_rows - preview.after_rows))})
                            </span>
                        )}
                    </div>

                    {preview.sample && preview.sample.length > 0 && (() => {
                            // Prioritise columns referenced in operations (filter, fill_missing, etc.) first
                            const allKeys = Object.keys(preview.sample[0]);
                            const filterCols = new Set<string>();
                            for (const op of operations) {
                                if (op.column) filterCols.add(op.column);
                                if (op.columns) for (const c of op.columns) filterCols.add(c);
                            }
                            const ordered = [...filterCols].filter(k => allKeys.includes(k));
                            const remaining = allKeys.filter(k => !filterCols.has(k));
                            const displayKeys = [...ordered, ...remaining];

                            // Two-axis scroller, as on the notebook preview: the box keeps its
                            // footprint however wide or long the table is, and the header row
                            // stays put while the rows scroll under it (decided 2026-09-25).
                            return (
                        <div className="max-h-96 overflow-auto">
                            <table className="text-xs border-collapse w-full">
                                <thead>
                                    <tr className="bg-muted">
                                        {displayKeys.map((key) => (
                                            <th key={key} className="border px-2 py-1 text-start font-medium sticky top-0 z-10 bg-muted">
                                                {key}
                                            </th>
                                        ))}
                                    </tr>
                                </thead>
                                <tbody>
                                    {preview.sample.map((row, i) => (
                                        <tr key={i} className={i % 2 === 0 ? "bg-white" : "bg-muted/20"}>
                                            {displayKeys.map((key) => (
                                                <td key={key} className="border px-2 py-1 truncate max-w-[120px]" title={row[key] === null ? undefined : String(row[key])}>
                                                    {row[key] === null ? (
                                                        <span className="text-muted-foreground italic">{translate(COMPONENTS.preparation_preview.null_value)}</span>
                                                    ) : (
                                                        <DataValue value={String(row[key])} />
                                                    )}
                                                </td>
                                            ))}
                                        </tr>
                                    ))}
                                </tbody>
                            </table>
                        </div>
                            ); })()}
                </>
            )}
        </div>
    );
}
