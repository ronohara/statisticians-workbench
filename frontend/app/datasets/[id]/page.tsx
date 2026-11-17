"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData, type TranslationKey } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { ProtectedRoute } from "@/components/protected-route";
import ReturnBanner from "@/components/return-banner";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, ArrowLeft, XCircle, Plus, Pencil, Trash2, Eye, ChevronDown, ChevronRight, FlaskConical, ArrowRight } from "lucide-react";
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

// Import translations for this module
import { DATASET_DETAIL } from "./translations";
import { DATASETS } from "../translations";
import { COMMON } from "@/app/common/translations";
import { formatDateTime } from "@/lib/date-format";

interface Dataset {
  id: string;
  name: string;
  description: string | null;
  datasetGroup: string;
  userId: string;
  isOwn: boolean;
  isShared: boolean;
  sourceType: string;
  sourceOrigin?: string | null;
  sourceDatasetId?: string | null;
  sourceDatasetName?: string | null;
  /** The materialisation choice, its outcome, and why it failed when it did.
   *  The three travel together: `materialized` says a table was asked for,
   *  `materializedAt` that one was built, and `materializeError` that the build
   *  was attempted and did not succeed. Until 2026-11-06 the response carried
   *  none of them, so this page rendered a materialised dataset exactly as it
   *  would a live one. */
  materialized?: boolean;
  materializedAt?: string | null;
  materializeError?: string | null;
  dataSnapshot: any;
  createdAt: string;
  updatedAt: string;
  user?: {
    name: string | null;
  };
  descriptions: {
    id: string;
    description: string;
    generatedAt: string;
    usedModel: string;
  }[];
  preparation_rules: PreparationRule[];
}

interface PreparationRule {
  id: string;
  name: string;
  description: string | null;
  ruleGroup: string;
  userId: string;
  isOwn: boolean;
  user_name?: string | null;
  operations: PreparationOperation[];
}

interface PreparationOperation {
  type: string;
  column?: string;
  columns?: string[];
  operator?: string;
  value?: any;
  method?: string;
  target_type?: string;
  new_name?: string;
  encoding?: string;
}

interface PreviewResult {
  rule_name: string;
  original: {
    rows: number;
    columns: string[];
    preview: Record<string, any>;
  };
  transformed: {
    rows: number;
    columns: string[];
    preview: Record<string, any>;
  };
  row_count_before: number;
  row_count_after: number;
  rows_removed: number;
}

interface ColumnSchema {
  name: string;
  dtype: string;
  is_numeric: boolean;
  is_categorical: boolean;
  is_datetime: boolean;
  unique_count: number;
  null_count: number;
  sample_values: any[];
}

interface DatasetSchema {
  dataset_id: string;
  columns: ColumnSchema[];
  total_rows: number;
  total_columns: number;
  /** Whether `total_rows` is a count or merely a placeholder zero.
   *  A live virtual dataset cannot be counted without running its join, so the
   *  route answers `total_rows: 0` beside `row_count_known: false` and a
   *  `warning`. Without this flag the page printed "0" for a dataset holding
   *  4,722 rows — measured 2026-11-06 on vd_d31158c13fc04527. */
  row_count_known?: boolean;
  warning?: string | null;
  unread?: { alias: string; reason: string }[];
}

function DatasetDetail() {
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const router = useRouter();
  const params = useParams();
  const datasetId = params.id as string;
  
  const [dataset, setDataset] = useState<Dataset | null>(null);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [schema, setSchema] = useState<DatasetSchema | null>(null);
  const [loadingSchema, setLoadingSchema] = useState(false);
  
  // Rule management state
  const [rulesExpanded, setRulesExpanded] = useState(true);
  const [showRuleForm, setShowRuleForm] = useState(false);
  const [editingRule, setEditingRule] = useState<PreparationRule | null>(null);
  const [ruleName, setRuleName] = useState("");
  const [ruleDescription, setRuleDescription] = useState("");
  const [ruleShared, setRuleShared] = useState(false);
  const [ruleOperations, setRuleOperations] = useState<PreparationOperation[]>([
    { type: "filter", column: "", operator: ">", value: "" }
  ]);
  
  // Preview state
  const [previewingRule, setPreviewingRule] = useState<string | null>(null);
  const [previewResult, setPreviewResult] = useState<PreviewResult | null>(null);
  const [previewLoading, setPreviewLoading] = useState(false);
  
  // Delete dialog
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [ruleToDelete, setRuleToDelete] = useState<PreparationRule | null>(null);
  const [deleting, setDeleting] = useState(false);
  
  // Submitting state
  const [submitting, setSubmitting] = useState(false);

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  const getOperationTypeName = (type: string): TranslationKey => {
    const names: Record<string, TranslationKey> = {
      filter: DATASET_DETAIL.operation.filter,
      fill_missing: DATASET_DETAIL.operation.fill_missing,
      convert_type: DATASET_DETAIL.operation.convert_type,
      normalize: DATASET_DETAIL.operation.normalize,
      standardize: DATASET_DETAIL.operation.standardize,
      encode: DATASET_DETAIL.operation.encode,
      drop_columns: DATASET_DETAIL.operation.drop_columns,
      rename_column: DATASET_DETAIL.operation.rename_column,
    };
    return names[type] || { key: "datasets.preparation.operation.unknown", fallback: type };
  };

  const getOperatorLabel = (operator: string, columnType: string): TranslationKey => {
    const operators = getFilterOperators(columnType);
    const found = operators.find(op => op.value === operator);
    return found ? found.label : { key: "datasets.preparation.operator.unknown", fallback: operator };
  };

  const fetchDataset = async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      
      if (!datasetId) {
        throw new Error("No dataset ID provided");
      }
      
      const res = await apiFetch(`/api/datasets/${datasetId}`);
      
      if (!res.ok) {
        let errorData: any = {};
        try {
          const text = await res.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, DATASET_DETAIL.load_error);
        throw new Error(errorMsg);
      }
      
      const data = await res.json();
      setDataset(data.dataset);
      setPreviewResult(null);
      setPreviewingRule(null);
      
      // Fetch schema for column dropdown
      await fetchSchema(datasetId);
    } catch (error: any) {
      const msg = error.message || translate(DATASET_DETAIL.load_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const fetchSchema = async (dataset_id: string) => {
    if (!dataset_id) return;
    setLoadingSchema(true);
    try {
      const res = await apiFetch(`/api/datasets/${dataset_id}/schema`);
      if (!res.ok) {
        console.warn("Failed to fetch schema for column dropdown");
        return;
      }
      const data = await res.json();
      setSchema(data);
    } catch (error) {
      console.error("Error fetching schema:", error);
    } finally {
      setLoadingSchema(false);
    }
  };

  useEffect(() => {
    if (datasetId) {
      fetchDataset();
    } else {
      setLoading(false);
      setErrorMessage(translate(DATASET_DETAIL.load_error));
    }
  }, [datasetId]);

  const resetRuleForm = () => {
    setRuleName("");
    setRuleDescription("");
    setRuleShared(false);
    setRuleOperations([{ type: "filter", column: "", operator: ">", value: "" }]);
    setEditingRule(null);
    setShowRuleForm(false);
  };

  const handleEditRule = (rule: PreparationRule) => {
    setEditingRule(rule);
    setRuleName(rule.name);
    setRuleDescription(rule.description || "");
    setRuleShared(rule.ruleGroup !== "00");
    setRuleOperations(rule.operations || [{ type: "filter", column: "", operator: ">", value: "" }]);
    setShowRuleForm(true);
  };

  const handleAddOperation = () => {
    setRuleOperations([
      ...ruleOperations,
      { type: "filter", column: "", operator: ">", value: "" }
    ]);
  };

  const handleRemoveOperation = (index: number) => {
    if (ruleOperations.length > 1) {
      const newOps = [...ruleOperations];
      newOps.splice(index, 1);
      setRuleOperations(newOps);
    }
  };

  const handleOperationChange = (index: number, field: string, value: any) => {
    const newOps = [...ruleOperations];
    newOps[index] = { ...newOps[index], [field]: value };
    setRuleOperations(newOps);
  };

  const getColumnType = (columnName: string): string => {
    if (!schema) return "text";
    const col = schema.columns.find(c => c.name === columnName);
    if (!col) return "text";
    if (col.is_numeric) return "numeric";
    if (col.is_datetime) return "datetime";
    if (col.is_categorical) {
      const sampleValues = col.sample_values || [];
      if (sampleValues.length > 0) {
        const uniqueValues = new Set(sampleValues.map(v => String(v).toLowerCase()));
        const isBoolean = uniqueValues.size <= 2 && 
          [...uniqueValues].every(v => v === "true" || v === "false" || v === "1" || v === "0" || v === "yes" || v === "no");
        if (isBoolean) return "boolean";
      }
      return "categorical";
    }
    return "text";
  };

  const getFilterOperators = (columnType: string): { value: string; label: TranslationKey }[] => {
    const O = DATASET_DETAIL.operator;
    switch (columnType) {
      case "numeric":
        return [
          { value: ">", label: O.greater_than },
          { value: ">=", label: O.greater_than_or_equal },
          { value: "<", label: O.less_than },
          { value: "<=", label: O.less_than_or_equal },
          { value: "==", label: O.equal_to },
          { value: "!=", label: O.not_equal },
        ];
      case "boolean":
        return [
          { value: "==", label: O.equal_to },
          { value: "!=", label: O.not_equal },
        ];
      case "datetime":
        return [
          { value: ">", label: O.after },
          { value: ">=", label: O.on_or_after },
          { value: "<", label: O.before },
          { value: "<=", label: O.on_or_before },
          { value: "==", label: O.equal_to },
          { value: "!=", label: O.not_equal },
        ];
      case "categorical":
        return [
          { value: "==", label: O.equal_to },
          { value: "!=", label: O.not_equal },
          { value: "contains", label: O.contains },
          { value: "not_contains", label: O.not_contains },
          { value: "starts_with", label: O.starts_with },
          { value: "ends_with", label: O.ends_with },
        ];
      case "text":
      default:
        return [
          { value: "==", label: O.equal_to },
          { value: "!=", label: O.not_equal },
          { value: "contains", label: O.contains },
          { value: "not_contains", label: O.not_contains },
          { value: "starts_with", label: O.starts_with },
          { value: "ends_with", label: O.ends_with },
        ];
    }
  };

  const getValuePlaceholder = (columnType: string): TranslationKey => {
    const P = DATASET_DETAIL.placeholder;
    switch (columnType) {
      case "numeric":
        return P.number;
      case "boolean":
        return P.boolean;
      case "datetime":
        return P.datetime;
      case "categorical":
      case "text":
      default:
        return P.value;
    }
  };

  const handleSaveRule = async () => {
    if (!ruleName.trim()) {
      const msg = translate(DATASET_DETAIL.preparation.name_required);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }

    // Validate operations have required fields
    for (let i = 0; i < ruleOperations.length; i++) {
      const op = ruleOperations[i];
      if (op.type === "filter" && (!op.column || op.value === undefined || op.value === "")) {
        const msg = translate(DATASET_DETAIL.preparation.filter_invalid);
        setErrorMessage(msg);
        toast.error(msg);
        return;
      }
      if ((op.type === "fill_missing" || op.type === "convert_type" || op.type === "rename_column") && !op.column) {
        const msg = translate(DATASET_DETAIL.preparation.column_required);
        setErrorMessage(msg);
        toast.error(msg);
        return;
      }
      if ((op.type === "normalize" || op.type === "standardize" || op.type === "drop_columns") && (!op.columns || op.columns.length === 0)) {
        const msg = translate(DATASET_DETAIL.preparation.columns_required);
        setErrorMessage(msg);
        toast.error(msg);
        return;
      }
      if (op.type === "rename_column" && !op.new_name) {
        const msg = translate(DATASET_DETAIL.preparation.new_name_required);
        setErrorMessage(msg);
        toast.error(msg);
        return;
      }
    }

    setSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const payload = {
        name: ruleName,
        description: ruleDescription || null,
        operations: ruleOperations,
        shared: ruleShared,
      };

      let url = `/api/datasets/${datasetId}/preparation`;
      let method = "POST";
      
      if (editingRule) {
        url = `/api/datasets/${datasetId}/preparation/${editingRule.id}`;
        method = "PUT";
      }

      const res = await apiFetch(url, {
        method,
        body: JSON.stringify(payload),
      });

      if (!res.ok) {
        let errorData: any = {};
        try {
          const text = await res.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, DATASET_DETAIL.preparation.save_error);
        throw new Error(errorMsg);
      }

      const msg = editingRule
        ? translate(DATASET_DETAIL.preparation.rule_updated)
        : translate(DATASET_DETAIL.preparation.rule_created);
      setSuccessMessage(msg);
      toast.success(msg);
      resetRuleForm();
      await fetchDataset();
    } catch (error: any) {
      const msg = error.message || translate(DATASET_DETAIL.preparation.save_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleDeleteRule = async (rule: PreparationRule) => {
    setRuleToDelete(rule);
    setDeleteDialogOpen(true);
  };

  const confirmDeleteRule = async () => {
    if (!ruleToDelete) return;
    setDeleting(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await apiFetch(`/api/datasets/${datasetId}/preparation/${ruleToDelete.id}`, {
        method: "DELETE",
      });

      if (!res.ok) {
        let errorData: any = {};
        try {
          const text = await res.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, DATASET_DETAIL.preparation.delete_error);
        throw new Error(errorMsg);
      }

      const msg = translate(DATASET_DETAIL.preparation.rule_deleted);
      setSuccessMessage(msg);
      toast.success(msg);
      setDeleteDialogOpen(false);
      setRuleToDelete(null);
      await fetchDataset();
    } catch (error: any) {
      const msg = error.message || translate(DATASET_DETAIL.preparation.delete_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setDeleting(false);
    }
  };

  const handlePreviewRule = async (ruleId: string) => {
    setPreviewLoading(true);
    setPreviewingRule(ruleId);
    setPreviewResult(null);
    setErrorMessage(null);

    try {
      const res = await apiFetch(`/api/datasets/${datasetId}/preparation/preview`, {
        method: "POST",
        body: JSON.stringify({ rule_id: ruleId, limit: 10 }),
      });

      if (!res.ok) {
        let errorData: any = {};
        try {
          const text = await res.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, DATASET_DETAIL.preparation.preview_error);
        throw new Error(errorMsg);
      }

      const data = await res.json();
      setPreviewResult(data);
    } catch (error: any) {
      const msg = error.message || translate(DATASET_DETAIL.preparation.preview_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setPreviewLoading(false);
    }
  };

  const getOperationLabel = (op: PreparationOperation): TranslationKey => {
    return getOperationTypeName(op.type);
  };

  const getOperationSummary = (op: PreparationOperation) => {
    const parts: string[] = [];
    if (op.column) parts.push(`column: ${op.column}`);
    if (op.columns) parts.push(`columns: ${op.columns.join(", ")}`);
    if (op.operator) {
      const colType = op.column ? getColumnType(op.column) : "text";
      const label = translate(getOperatorLabel(op.operator, colType));
      parts.push(`operator: ${label}`);
    }
    if (op.value !== undefined && op.value !== null && op.value !== "") parts.push(`value: ${String(op.value)}`);
    if (op.method) parts.push(`method: ${op.method}`);
    if (op.target_type) parts.push(`→ ${op.target_type}`);
    if (op.new_name) parts.push(`→ ${op.new_name}`);
    if (op.encoding) parts.push(`encoding: ${op.encoding}`);
    return parts.length > 0 ? ` (${parts.join(", ")})` : "";
  };

  const renderPreviewTable = (preview: Record<string, any>, columns: string[]) => {
    const rows: any[] = [];
    if (preview && typeof preview === 'object') {
      const firstColumn = columns[0];
      if (firstColumn && preview[firstColumn]) {
        const rowCount = preview[firstColumn].length;
        for (let i = 0; i < rowCount; i++) {
          const row: Record<string, any> = {};
          for (const col of columns) {
            row[col] = preview[col]?.[i] ?? null;
          }
          rows.push(row);
        }
      }
    }
    return rows;
  };

    if (loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!dataset) {
    return (
      <div className="max-w-4xl mx-auto">
        <div className="flex items-center gap-4 mb-6">
          <Button variant="ghost" size="icon" onClick={() => router.push("/datasets/manage")}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <h1 className="text-3xl font-bold">{translate(DATASET_DETAIL.not_found)}</h1>
        </div>
        {errorMessage && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
            <span className="text-sm">{errorMessage}</span>
            <button onClick={dismissError} className="text-red-500 hover:text-red-700">
              <XCircle className="h-5 w-5" />
            </button>
          </div>
        )}
        <Card>
          <CardContent className="pt-6">
            <p className="text-muted-foreground">{translate(DATASET_DETAIL.not_found_message)}</p>
            <Button className="mt-4" onClick={() => router.push("/datasets/manage")}>
              {translate(COMMON.back)}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isShared = dataset.isShared === true;
  const isOwn = dataset.isOwn === true;
  const isVirtual = dataset.sourceType === "virtual";
  // The count comes from the schema route, which is the only reader that can
  // answer it: a real COUNT(*) for a materialised dataset, and an explicit
  // "not asked" for a live one, where counting means running the join.
  //
  // This used to print the length of `dataSnapshot`, which is the size of a
  // stored preview and never a count of the dataset — and is NULL for every
  // virtual dataset, so the panel read "Rows: 0" for one holding 4,722. A
  // number that means "I did not count" is worse than saying so, which is what
  // the flag is for.
  const rowCountKnown = schema?.row_count_known === true;
  const rowCount = rowCountKnown ? (schema?.total_rows ?? 0) : 0;

  // The panel's count, in the words that are true of it. `row_count_known` is
  // what makes "0" distinguishable from "nobody counted": the route sets it
  // false for a live virtual dataset, whose count would need the join to run,
  // and true wherever a COUNT(*) was actually taken.
  const renderRowCount = () => {
    if (!rowCountKnown) {
      return (
        <span title={translate(DATASET_DETAIL.rows_not_computed_hint)}>
          {translate(DATASET_DETAIL.rows_not_computed)}
        </span>
      );
    }
    return <span className="text-foreground">{rowCount.toLocaleString()}</span>;
  };

  const rules = dataset.preparation_rules || [];

  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <ReturnBanner />
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push("/datasets/manage")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">{dataset.name}</h1>
          {dataset.sourceOrigin && (
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">
                {translate(DATASETS.cleaned_badge)}
              </span>
              {dataset.sourceDatasetId && (
                <span className="text-xs text-muted-foreground">
                  {translate(DATASETS.created_from).replace("{name}", dataset.sourceDatasetName || translate(DATASETS.source_unavailable))}
                </span>
              )}
            </div>
          )}
          {isShared && (
            <div className="flex items-center gap-2 mt-1">
              <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded">
                {translate(DATASETS.shared_badge)}
              </span>
              {!isOwn && (
                <span className="text-xs text-muted-foreground">
                  {translate(DATASETS.by_label)} {dataset.user?.name || translate(COMMON.unknown)}
                </span>
              )}
            </div>
          )}
        </div>
      </div>

      {errorMessage && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
          <span className="text-sm">{errorMessage}</span>
          <button onClick={dismissError} className="text-red-500 hover:text-red-700">
            <XCircle className="h-5 w-5" />
          </button>
        </div>
      )}

      {successMessage && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-md text-green-800 flex items-center justify-between">
          <span className="text-sm">{successMessage}</span>
          <button onClick={dismissSuccess} className="text-green-500 hover:text-green-700">
            <span className="text-xl">&times;</span>
          </button>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{translate(DATASET_DETAIL.overview)}</CardTitle>
        </CardHeader>
        <CardContent>
          <p className="text-muted-foreground">
            {dataset.description || translate(DATASET_DETAIL.no_description)}
          </p>
          <p className="text-sm text-muted-foreground mt-2">
            {translate(DATASET_DETAIL.created)}: {formatDateTime(dataset.createdAt)}
          </p>
          <p className="text-sm text-muted-foreground">
            {translate(DATASET_DETAIL.rows)}: {renderRowCount()}
          </p>
          {/* Which kind of dataset this is. A virtual one is either a live join
              or a saved table, and the two behave differently enough that
              leaving it unsaid made the page unable to answer the question a
              reader arrives with. */}
          {isVirtual && (
            <p className="mt-1">
              <span className="inline-block rounded bg-muted px-2 py-0.5 text-xs text-muted-foreground">
                {dataset.materialized
                  ? translate(DATASET_DETAIL.storage_table)
                  : translate(DATASET_DETAIL.storage_live)}
              </span>
            </p>
          )}
          {/* A failed build is a state that persists on the row until a retry
              succeeds, so it is shown here rather than as a toast: the value is
              safe, the table is not, and that distinction has to survive a
              reload. */}
          {dataset.materializeError && (
            <p className="text-sm text-amber-700 mt-1">
              {translate(DATASET_DETAIL.materialize_failed)} {dataset.materializeError}
            </p>
          )}
        </CardContent>
      </Card>

      {/* Transformations — link to the transforms editor */}
      {isOwn && (
        <Card className="cursor-pointer hover:bg-muted/30 transition-colors" onClick={() => router.push(`/datasets/${datasetId}/transforms`)}>
          <CardContent className="flex items-center gap-3 py-4">
            <FlaskConical className="h-5 w-5 text-muted-foreground" />
            <span className="font-medium">{translate(DATASET_DETAIL.link_card.title)}</span>
            <span className="text-sm text-muted-foreground flex-1">{translate(DATASET_DETAIL.link_card.description)}</span>
            <ArrowRight className="h-4 w-4 text-muted-foreground" />
          </CardContent>
        </Card>
      )}


      {/* AI Descriptions */}
      {dataset.descriptions && dataset.descriptions.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle>{translate(DATASET_DETAIL.descriptions)}</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {dataset.descriptions.map((desc) => (
              <div key={desc.id} className="border rounded-md p-4">
                <p className="whitespace-pre-wrap">{desc.description}</p>
                <p className="text-xs text-muted-foreground mt-2">
                  {translate(DATASET_DETAIL.generated)}: {formatDateTime(desc.generatedAt)} | {translate(DATASET_DETAIL.model)}: {desc.usedModel}
                </p>
              </div>
            ))}
          </CardContent>
        </Card>
      )}

      {/* Delete Dialog */}
      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{translate(DATASET_DETAIL.preparation.delete_title)}</AlertDialogTitle>
            <AlertDialogDescription>
              {translate(DATASET_DETAIL.preparation.delete_confirmation).replace("{name}", ruleToDelete?.name || "")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{translate(COMMON.cancel)}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteRule} disabled={deleting}>
              {deleting ? translate(COMMON.deleting) : translate(COMMON.delete)}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function DatasetDetailPage() {
  return (
    <ProtectedRoute>
      <DatasetDetail />
    </ProtectedRoute>
  );
}