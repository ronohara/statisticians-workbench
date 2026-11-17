"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, useTranslateWithParams } from "@/lib/translation-helpers";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RECIPES } from "@/app/recipes/translations";
import { fetchRecipeModel, isOutputValid, type RecipeModel, type FieldDef, type ValidationIssue } from "@/lib/recipe-model";
import type { RecipeOutputState, RecipeColumn } from "./types";

// Sandbox slug → recipe output type name mapping (names come from the DB;
// this only bridges the two identifiers, it is not constraint knowledge).
const SLUG_TO_OUTPUT: Record<string, string> = {
    text_table: "table",
    bar_chart: "bar",
    horizontal_bar: "hbar",
    pie_chart: "pie",
    donut_chart: "donut",
    line_chart: "line",
    area_chart: "area",
    scatter_plot: "scatter",
    histogram: "histogram",
    distribution: "distribution",
};

interface VizType {
    id: number;
    name: string;
    slug: string;
    description: string | null;
    inputSchema: unknown;
    parameterSchema: unknown;
    defaultParameters: unknown;
}

interface OutputComponentProps {
    value: RecipeOutputState;
    onChange: (state: RecipeOutputState) => void;
    columns: RecipeColumn[];
    issues?: ValidationIssue[];
    algorithmType?: string | null;
}

/** Whether a column matches a field's required columnType (false → show ⚠). */
function columnMatches(fdef: FieldDef, c: RecipeColumn): boolean {
    if (fdef.columnType === "numeric") return c.isNumeric;
    if (fdef.columnType === "categorical") return c.isCategorical;
    return true;
}

export default function OutputComponent({
    value,
    onChange,
    columns,
    issues = [],
    algorithmType,
}: OutputComponentProps) {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const translateParams = useTranslateWithParams();
    const [vizTypes, setVizTypes] = useState<VizType[]>([]);
    const [model, setModel] = useState<RecipeModel | null>(null);

    useEffect(() => {
        fetch("/api/visualization-types")
            .then((res) => res.json())
            .then((data) => setVizTypes(data.types || []))
            .catch(() => setVizTypes([]));
    }, []);

    useEffect(() => {
        let cancelled = false;
        fetchRecipeModel()
            .then((m) => {
                if (!cancelled) setModel(m);
            })
            .catch(() => {
                /* keep the panel usable without the model */
            });
        return () => {
            cancelled = true;
        };
    }, []);

    if (!isLanguageLoaded || !model) return null;

    // Build output type list from API types + hardcoded "none"
    const outputTypes = vizTypes
        .filter((t) => t.slug in SLUG_TO_OUTPUT)
        .map((t) => ({
            value: SLUG_TO_OUTPUT[t.slug],
            label: t.name,
        }));

    const outputFields = value.outputType ? (model.outputs[value.outputType]?.fields ?? []) : [];

    const setField = (field: string, val: unknown) => {
        const cleaned = val === "" || val === null ? undefined : val;
        onChange({ ...value, config: { ...value.config, [field]: cleaned } });
    };

    const selectedLabel =
        value.outputType === "none"
            ? translate(RECIPES.no_visualisation)
            : outputTypes.find((o) => o.value === value.outputType)?.label || value.outputType || "";

    return (
        <div className="space-y-3">
            <Select
                value={value.outputType || ""}
                onValueChange={(type) => onChange({ outputType: type || null, config: {} })}
            >
                <SelectTrigger className="h-8 text-sm">
                    <SelectValue>
                        {value.outputType ? selectedLabel : translate(RECIPES.output_placeholder)}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {outputTypes.map((out) => {
                        const valid = isOutputValid(model, out.value, columns, algorithmType);
                        return (
                            <SelectItem key={out.value} value={out.value}>
                                {valid && <span className="text-green-600 me-1" aria-hidden>●</span>}
                                {out.label}
                            </SelectItem>
                        );
                    })}
                    <SelectItem value="none">{translate(RECIPES.no_visualisation)}</SelectItem>
                </SelectContent>
            </Select>

            {issues.length > 0 && (
                <div className="text-xs text-amber-600 bg-amber-50 rounded px-2 py-1 space-y-0.5">
                    {issues.map((issue, i) => (
                        <div key={i}>{translateParams(issue.key, issue.fallback, issue.params)}</div>
                    ))}
                </div>
            )}

            {value.outputType && value.outputType !== "none" && outputFields.length > 0 && (
                <div className="space-y-2">
                    {outputFields.map((field) => {
                        const fdef = model.fields[field];
                        if (!fdef) return null;
                        const label = translate(fdef.label);
                        const cfgValue = (value.config[field] as string) || "";

                        return (
                            <div key={field}>
                                <label className="text-xs text-muted-foreground block mb-0.5">
                                    {label}
                                </label>
                                <Select value={cfgValue} onValueChange={(col) => setField(field, col)}>
                                    <SelectTrigger className="h-7 text-xs">
                                        <SelectValue placeholder="—" />
                                    </SelectTrigger>
                                    <SelectContent>
                                        {columns.map((c) => (
                                            <SelectItem key={c.name} value={c.name}>
                                                {c.name}
                                                {columnMatches(fdef, c) ? null : (
                                                    <span className="text-red-500 ms-1">⚠</span>
                                                )}
                                            </SelectItem>
                                        ))}
                                    </SelectContent>
                                </Select>
                            </div>
                        );
                    })}
                </div>
            )}
        </div>
    );
}
