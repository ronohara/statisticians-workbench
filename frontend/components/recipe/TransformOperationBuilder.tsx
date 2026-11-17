"use client";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Plus, GripVertical, X } from "lucide-react";

/** A single transform operation. */
export interface TransformOp {
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

export interface ColumnInfo {
    name: string;
    dtype?: string;
    is_numeric?: boolean;
    is_categorical?: boolean;
    is_datetime?: boolean;
}

/** Operation type definitions (value-only keys — labels come from the labels prop). */
export const OPERATION_TYPE_KEYS = [
    "filter", "fill_missing", "drop_column", "convert_type",
    "normalize", "standardize", "rename_column", "drop_duplicates", "encode_category",
] as const;

export type OperationTypeKey = typeof OPERATION_TYPE_KEYS[number];

/** Labels passed in for translation. */
export interface OperationBuilderLabels {
    addOperation: string;
    removeOperation: string;
    typePlaceholder: string;
    columnPlaceholder: string;
    columnsPlaceholder: string;
    operatorPlaceholder: string;
    valuePlaceholder: string;
    methodPlaceholder: string;
    targetTypePlaceholder: string;
    targetNumeric: string;
    targetDatetime: string;
    targetString: string;
    targetBoolean: string;
    newNamePlaceholder: string;
    encodingPlaceholder: string;
    encodingOnehot: string;
    encodingLabel: string;
    filterOperators: { value: string; label: string }[];
    fillMethods: { value: string; label: string }[];
    opTypeLabels: Record<string, string>;
    operationsHeading?: string;
    emptyStateText?: string;
}

export const DEFAULT_LABELS: OperationBuilderLabels = {
    addOperation: "Add Operation",
    removeOperation: "Remove",
    typePlaceholder: "Operation type",
    columnPlaceholder: "Select column",
    columnsPlaceholder: "Select columns",
    operatorPlaceholder: "Operator",
    valuePlaceholder: "Value",
    methodPlaceholder: "Method",
    targetTypePlaceholder: "Target type",
    targetNumeric: "Numeric",
    targetDatetime: "Datetime",
    targetString: "String",
    targetBoolean: "Boolean",
    newNamePlaceholder: "New name",
    encodingPlaceholder: "Encoding",
    encodingOnehot: "One-hot",
    encodingLabel: "Label",
    filterOperators: [
        { value: ">", label: ">" },
        { value: "<", label: "<" },
        { value: "=", label: "=" },
        { value: "!=", label: "!=" },
        { value: "contains", label: "contains" },
        { value: "is_null", label: "is null" },
    ],
    fillMethods: [
        { value: "mean", label: "Mean" },
        { value: "median", label: "Median" },
        { value: "mode", label: "Mode" },
        { value: "constant", label: "Constant" },
        { value: "drop", label: "Drop rows" },
    ],
    opTypeLabels: {
        filter: "Filter rows",
        fill_missing: "Fill missing values",
        drop_column: "Drop column",
        convert_type: "Convert type",
        normalize: "Normalize",
        standardize: "Standardize",
        rename_column: "Rename column",
        drop_duplicates: "Drop duplicates",
        encode_category: "Encode category",
    },
};

interface TransformOperationBuilderProps {
    operations: TransformOp[];
    columns: ColumnInfo[];
    onChange: (ops: TransformOp[]) => void;
    labels?: Partial<OperationBuilderLabels>;
    disabled?: boolean;
}

export default function TransformOperationBuilder({
    operations,
    columns,
    onChange,
    labels: partialLabels,
    disabled = false,
}: TransformOperationBuilderProps) {
    const lbl = { ...DEFAULT_LABELS, ...partialLabels };

    const addOperation = () => {
        onChange([...operations, { type: "", column: null }]);
    };

    const updateOperation = (index: number, update: Partial<TransformOp>) => {
        onChange(operations.map((op, i) => (i === index ? { ...op, ...update } : op)));
    };

    const removeOperation = (index: number) => {
        onChange(operations.filter((_, i) => i !== index));
    };

    const getFilteredColumns = (opType: string): ColumnInfo[] => {
        if (!opType) return columns;
        switch (opType) {
            case "fill_missing":
            case "normalize":
            case "standardize":
                return columns.filter((c) => c.is_numeric || c.is_numeric === undefined);
            case "encode_category":
                return columns.filter((c) => c.is_categorical);
            default:
                return columns;
        }
    };

    return (
        <div className="space-y-3">
            <div className="flex items-center justify-between">
                <h3 className="font-medium text-sm">{lbl.operationsHeading || "Operations"}</h3>
                <Button variant="outline" size="sm" onClick={addOperation} disabled={disabled}>
                    <Plus className="h-4 w-4 me-1" />
                    {lbl.addOperation}
                </Button>
            </div>

            <div className="space-y-3">
                {operations.map((op, i) => {
                    const filteredCols = getFilteredColumns(op.type);
                    return (
                        <div key={i} className="border rounded-lg p-3 space-y-2 bg-muted/20">
                            <div className="flex items-center gap-2">
                                <GripVertical className="h-4 w-4 text-muted-foreground cursor-grab" />
                                <span className="text-xs font-mono text-muted-foreground">{i + 1}.</span>

                                {/* Operation type */}
                                <select
                                    value={op.type}
                                    onChange={(e) => updateOperation(i, { type: e.target.value, column: null, columns: null, operator: null, value: null, method: null, target_type: null, new_name: null, encoding: null })}
                                    className="text-sm border rounded px-2 py-1 bg-background flex-1"
                                    disabled={disabled}
                                >
                                    <option value="">{lbl.typePlaceholder}</option>
                                    {OPERATION_TYPE_KEYS.map((key) => (
                                        <option key={key} value={key}>{lbl.opTypeLabels[key] || key}</option>
                                    ))}
                                </select>

                                <button
                                    type="button"
                                    onClick={() => removeOperation(i)}
                                    className="text-muted-foreground hover:text-destructive shrink-0"
                                    title={lbl.removeOperation}
                                    disabled={disabled}
                                >
                                    <X className="h-4 w-4" />
                                </button>
                            </div>

                            {/* Column selector — show for all types that need a column */}
                            {op.type && op.type !== "drop_duplicates" && op.type !== "normalize" && op.type !== "standardize" && (
                                <div className="ms-8">
                                    <select
                                        value={op.column || ""}
                                        onChange={(e) => updateOperation(i, { column: e.target.value || null })}
                                        className="text-sm border rounded px-2 py-1 bg-background w-48"
                                        disabled={disabled}
                                    >
                                        <option value="">{lbl.columnPlaceholder}</option>
                                        {filteredCols.map((c) => (
                                            <option key={c.name} value={c.name}>{c.name}</option>
                                        ))}
                                    </select>
                                </div>
                            )}

                            {/* Columns (plural) for normalize/standardize */}
                            {(op.type === "normalize" || op.type === "standardize") && (
                                <div className="ms-8">
                                    <select
                                        multiple
                                        value={op.columns || []}
                                        onChange={(e) => updateOperation(i, { columns: Array.from(e.target.selectedOptions, (o) => o.value) })}
                                        className="text-sm border rounded px-2 py-1 bg-background"
                                        disabled={disabled}
                                    >
                                        {filteredCols.map((c) => (
                                            <option key={c.name} value={c.name}>{c.name}</option>
                                        ))}
                                    </select>
                                </div>
                            )}

                            {op.type === "filter" && op.column && (
                                <div className="ms-8 flex gap-2">
                                    <select
                                        value={op.operator || ""}
                                        onChange={(e) => updateOperation(i, { operator: e.target.value })}
                                        className="text-sm border rounded px-2 py-1 bg-background"
                                        disabled={disabled}
                                    >
                                        <option value="">{lbl.operatorPlaceholder}</option>
                                        {lbl.filterOperators.map((fo) => (
                                            <option key={fo.value} value={fo.value}>{fo.label}</option>
                                        ))}
                                    </select>
                                    {op.operator !== "is_null" && (
                                        <Input dir="auto"
                                            value={op.value != null ? String(op.value) : ""}
                                            onChange={(e) => updateOperation(i, { value: e.target.value })}
                                            className="text-sm h-8 w-32"
                                            placeholder={lbl.valuePlaceholder}
                                            disabled={disabled}
                                        />
                                    )}
                                </div>
                            )}

                            {op.type === "fill_missing" && op.column && (
                                <div className="ms-8">
                                    <select
                                        value={op.method || ""}
                                        onChange={(e) => updateOperation(i, { method: e.target.value })}
                                        className="text-sm border rounded px-2 py-1 bg-background"
                                        disabled={disabled}
                                    >
                                        <option value="">{lbl.methodPlaceholder}</option>
                                        {lbl.fillMethods.map((fm) => (
                                            <option key={fm.value} value={fm.value}>{fm.label}</option>
                                        ))}
                                    </select>
                                </div>
                            )}

                            {op.type === "convert_type" && op.column && (
                                <div className="ms-8">
                                    <select
                                        value={op.target_type || ""}
                                        onChange={(e) => updateOperation(i, { target_type: e.target.value })}
                                        className="text-sm border rounded px-2 py-1 bg-background"
                                        disabled={disabled}
                                    >
                                        <option value="">{lbl.targetTypePlaceholder}</option>
                                        <option value="numeric">{lbl.targetNumeric}</option>
                                        <option value="datetime">{lbl.targetDatetime}</option>
                                        <option value="string">{lbl.targetString}</option>
                                        <option value="boolean">{lbl.targetBoolean}</option>
                                    </select>
                                </div>
                            )}

                            {op.type === "rename_column" && op.column && (
                                <div className="ms-8">
                                    <Input dir="auto"
                                        value={op.new_name || ""}
                                        onChange={(e) => updateOperation(i, { new_name: e.target.value })}
                                        className="text-sm h-8 w-48"
                                        placeholder={lbl.newNamePlaceholder}
                                        disabled={disabled}
                                    />
                                </div>
                            )}

                            {op.type === "encode_category" && op.column && (
                                <div className="ms-8">
                                    <select
                                        value={op.encoding || ""}
                                        onChange={(e) => updateOperation(i, { encoding: e.target.value })}
                                        className="text-sm border rounded px-2 py-1 bg-background"
                                        disabled={disabled}
                                    >
                                        <option value="">{lbl.encodingPlaceholder}</option>
                                        <option value="one_hot">{lbl.encodingOnehot}</option>
                                        <option value="label">{lbl.encodingLabel}</option>
                                    </select>
                                </div>
                            )}
                        </div>
                    );
                })}

                {operations.length === 0 && (
                    <p className="text-sm text-muted-foreground text-center py-3">
                        {lbl.emptyStateText || "Add an operation to start building your transform."}
                    </p>
                )}
            </div>
        </div>
    );
}
