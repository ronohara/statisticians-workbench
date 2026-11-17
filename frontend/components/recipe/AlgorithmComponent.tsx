"use client";

import { useEffect, useState } from "react";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, useTranslateWithParams } from "@/lib/translation-helpers";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { RECIPES } from "@/app/recipes/translations";
import { fetchRecipeModel, isAlgorithmValid, type RecipeModel, type FieldDef, type ValidationIssue } from "@/lib/recipe-model";
import type { RecipeAlgorithmState, RecipeColumn } from "./types";

interface AlgorithmComponentProps {
    value: RecipeAlgorithmState;
    onChange: (state: RecipeAlgorithmState) => void;
    columns: RecipeColumn[];
    issues?: ValidationIssue[];
    outputType?: string | null;
}

/** Whether a column matches a field's required columnType (false → show ⚠). */
function columnMatches(fdef: FieldDef, c: RecipeColumn): boolean {
    if (fdef.columnType === "numeric") return c.isNumeric;
    if (fdef.columnType === "categorical") return c.isCategorical;
    return true;
}

export default function AlgorithmComponent({
    value,
    onChange,
    columns,
    issues = [],
    outputType,
}: AlgorithmComponentProps) {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const translateParams = useTranslateWithParams();
    const [model, setModel] = useState<RecipeModel | null>(null);

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

    const algoKeys = Object.keys(model.algorithms);
    const configFields = value.algorithmType ? (model.algorithms[value.algorithmType]?.fields ?? []) : [];

    const setField = (field: string, val: unknown) => {
        const cleaned = val === "" || val === null ? undefined : val;
        onChange({ ...value, config: { ...value.config, [field]: cleaned } });
    };

    return (
        <div className="space-y-3">
            <Select
                value={value.algorithmType || ""}
                onValueChange={(type) => onChange({ algorithmType: type || null, config: {} })}
            >
                <SelectTrigger className="h-8 text-sm">
                    <SelectValue>
                        {value.algorithmType && model.algorithms[value.algorithmType]
                            ? translate(model.algorithms[value.algorithmType].label)
                            : translate(RECIPES.algorithm_placeholder)}
                    </SelectValue>
                </SelectTrigger>
                <SelectContent>
                    {algoKeys.map((alg) => {
                        const valid = isAlgorithmValid(model, alg, columns, outputType);
                        return (
                            <SelectItem key={alg} value={alg}>
                                {valid && <span className="text-green-600 me-1" aria-hidden>●</span>}
                                {translate(model.algorithms[alg].label)}
                            </SelectItem>
                        );
                    })}
                </SelectContent>
            </Select>

            {issues.length > 0 && (
                <div className="text-xs text-amber-600 bg-amber-50 rounded px-2 py-1 space-y-0.5">
                    {issues.map((issue, i) => (
                        <div key={i}>{translateParams(issue.key, issue.fallback, issue.params)}</div>
                    ))}
                </div>
            )}

            {value.algorithmType && configFields.length > 0 && (
                <div className="space-y-2">
                    {configFields.map((field) => {
                        const fdef = model.fields[field];
                        if (!fdef) return null;
                        const label = translate(fdef.label);

                        if (fdef.multi) {
                            const selected = (value.config[field] as string[] | undefined) ?? [];
                            return (
                                <div key={field}>
                                    <label className="text-xs text-muted-foreground block mb-0.5">
                                        {label}
                                    </label>
                                    <select
                                        multiple
                                        value={selected}
                                        onChange={(e) =>
                                            setField(field, Array.from(e.target.selectedOptions, (o) => o.value))
                                        }
                                        className="w-full text-xs border rounded px-2 py-1 bg-background"
                                    >
                                        {columns.map((c) => (
                                            <option key={c.name} value={c.name}>
                                                {c.name} {c.type}
                                                {columnMatches(fdef, c) ? "" : " ⚠"}
                                            </option>
                                        ))}
                                    </select>
                                </div>
                            );
                        }

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
