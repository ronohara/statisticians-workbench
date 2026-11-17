"use client";

import { useEffect, useState } from "react";
import { useParams } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { Card, CardContent } from "@/components/ui/card";
import {
  Accordion,
  AccordionContent,
  AccordionHeader,
  AccordionItem,
  AccordionTrigger,
} from "@/components/ui/accordion";
import { DataValue } from "@/components/ui/data-value";
import { Loader2, AlertCircle, CheckCircle, XCircle } from "lucide-react";
import { RECIPES } from "../../translations";
import VisualisationResult from "@/components/recipe/VisualisationResult";

function isTableResult(value: any): boolean {
    const data = value?.chart_data || value;
    return data && typeof data === "object" && data.type === "table" && Array.isArray(data.columns) && Array.isArray(data.rows);
}

function getTableData(value: any) {
    return value?.chart_data || value;
}

interface ExecutionResult {
    execution_id: string;
    recipe_name: string | null;
    status: string;
    progress: number;
    results: Record<string, any> | null;
    errors: string[] | null;
    preparation_rules_applied: number;
    message: string;
}

export default function RecipeExecutePage() {
    const params = useParams();
    const translate = useTranslate();
    const { isLanguageLoaded } = useTranslation();
    const recipeId = params?.id as string;

    const [status, setStatus] = useState<"starting" | "completed" | "failed" | "error">("starting");
    const [result, setResult] = useState<ExecutionResult | null>(null);
    const [error, setError] = useState<string | null>(null);

    useEffect(() => {
        if (!recipeId) return;
        let cancelled = false;

        const startExecution = async () => {
            try {
                const res = await apiFetch("/api/recipes/execute", {
                    method: "POST",
                    body: JSON.stringify({ recipe_id: recipeId }),
                });
                if (!res.ok) {
                    let msg = translate(RECIPES.execution_failed_start);
                    try {
                        const data = await res.json();
                        msg = data.detail || data.message || msg;
                    } catch {}
                    throw new Error(msg);
                }
                const data: ExecutionResult = await res.json();
                if (!cancelled) {
                    setResult(data);
                    setStatus(data.status === "completed" ? "completed" : "failed");
                }
            } catch (err: any) {
                if (!cancelled) {
                    setError(err.message || translate(RECIPES.execution_request_failed));
                    setStatus("error");
                }
            }
        };

        startExecution();
        return () => { cancelled = true; };
    }, [recipeId]);

    if (!isLanguageLoaded) return null;

    const stageLabel = (value: any): string => {
        switch (value?.stage_type) {
            case "data_selection": return translate(RECIPES.stage_data_selection);
            case "data_preparation": return translate(RECIPES.stage_preparation);
            case "statistics": return translate(RECIPES.stage_statistics);
            case "visualisation": return translate(RECIPES.stage_visualisation);
            default: return value?.stage_type || "";
        }
    };

    const renderStageBody = (value: any) => {
        if (isTableResult(value)) {
            const td = getTableData(value);
            return (
                <div className="mt-1 overflow-x-auto max-h-64">
                    <table className="w-full text-[11px] border-collapse">
                        <thead>
                            <tr className="border-b border-border">
                                {td.columns?.map((col: string) => (
                                    <th key={col} className="text-start px-1.5 py-1 font-medium text-muted-foreground whitespace-nowrap">{col}</th>
                                ))}
                            </tr>
                        </thead>
                        <tbody>
                            {td.rows?.map((row: any, ri: number) => (
                                <tr key={ri} className="border-b border-border/50 hover:bg-muted/30">
                                    {td.columns?.map((col: string) => (
                                        <td key={col} className="px-1.5 py-0.5 whitespace-nowrap">{row[col] != null ? <DataValue value={String(row[col])} /> : "—"}</td>
                                    ))}
                                </tr>
                            ))}
                        </tbody>
                    </table>
                    {td.total_rows > td.rows?.length && (
                        <p className="text-[10px] text-muted-foreground mt-1 px-1.5">
                            {translate(RECIPES.execution_showing_rows).replace("{count}", String(td.rows?.length)).replace("{total}", String(td.total_rows?.toLocaleString()))}
                        </p>
                    )}
                </div>
            );
        }
        if (value?.chart_data) {
            return <VisualisationResult stageResult={value} title={result?.recipe_name ?? undefined} />;
        }
        return (
            <pre className="text-xs text-muted-foreground mt-0.5 overflow-x-auto">
                {typeof value === "object" ? JSON.stringify(value, null, 2) : String(value)}
            </pre>
        );
    };

    return (
        <div className="h-full overflow-y-auto p-6">
            <Card className="max-w-3xl mx-auto w-full">
                <CardContent className="pt-6">
                    {status === "starting" && (
                        <div className="flex flex-col items-center gap-3 py-8">
                            <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
                            <p className="text-sm text-muted-foreground">
                                {translate(RECIPES.execution_running)}
                            </p>
                        </div>
                    )}

                    {status === "error" && (
                        <div className="flex flex-col items-center gap-3 py-8">
                            <AlertCircle className="h-8 w-8 text-destructive" />
                            <p className="text-sm text-destructive">{error}</p>
                        </div>
                    )}

                    {(status === "completed" || status === "failed") && result && (
                        <div className="space-y-4">
                            {result.recipe_name && (
                                <h2 className="text-lg font-semibold">{result.recipe_name}</h2>
                            )}
                            <div className="flex items-center gap-2">
                                {status === "completed" ? (
                                    <CheckCircle className="h-5 w-5 text-green-600" />
                                ) : (
                                    <XCircle className="h-5 w-5 text-destructive" />
                                )}
                                <span className="font-medium text-sm">
                                    {result.message}
                                </span>
                            </div>

                            {result.preparation_rules_applied > 0 && (
                                <p className="text-xs text-muted-foreground">
                                    {translate(RECIPES.execution_rules_count).replace("{count}", String(result.preparation_rules_applied))}
                                </p>
                            )}

                            {result.errors && result.errors.length > 0 && (
                                <div className="bg-destructive/10 border border-destructive/20 rounded p-2">
                                    <p className="text-xs font-medium text-destructive mb-1">{translate(RECIPES.execution_errors_label)}</p>
                                    {result.errors.map((e, i) => (
                                        <p key={i} className="text-xs text-destructive">{e}</p>
                                    ))}
                                </div>
                            )}

                            {result.results && Object.keys(result.results).length > 0 && (() => {
                                const entries = Object.entries(result.results);
                                const finalEntry = entries[entries.length - 1];
                                const intermediate = entries.slice(0, -1);
                                return (
                                    <div className="space-y-3">
                                        <div className="rounded-md border bg-card p-3">
                                            <p className="text-sm font-medium mb-2">{stageLabel(finalEntry[1])}</p>
                                            {renderStageBody(finalEntry[1])}
                                        </div>
                                        {intermediate.length > 0 && (
                                            <Accordion multiple>
                                                {intermediate.map(([key, value]) => (
                                                    <AccordionItem key={key} value={key}>
                                                        <AccordionHeader>
                                                            <AccordionTrigger>{stageLabel(value)}</AccordionTrigger>
                                                        </AccordionHeader>
                                                        <AccordionContent>
                                                            {renderStageBody(value)}
                                                        </AccordionContent>
                                                    </AccordionItem>
                                                ))}
                                            </Accordion>
                                        )}
                                    </div>
                                );
                            })()}
                        </div>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
