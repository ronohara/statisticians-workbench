"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, useTranslateKeyWithParams, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { Loader2, ArrowLeft, CheckCircle, XCircle, Clock, Download, Lock, UserPlus } from "lucide-react";
import Link from "next/link";

// Import translations for this module
import { EXECUTION_RESULTS } from "./translations";
import { RECIPES } from "../../translations";
import { COMMON } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";
import VisualisationResult from "@/components/recipe/VisualisationResult";
import { formatDateTime } from "@/lib/date-format";

interface Execution {
  id: string;
  recipeId: string;
  status: string;
  progress: number;
  result: Record<string, any> | null;
  error: string | null;
  startedAt: string;
  completedAt: string | null;
  createdAt: string;
  preparation_rules_applied?: number;
  preparation_rules?: PreparationRuleResult[];
}

interface PreparationRuleResult {
  rule_id: string;
  rule_name: string;
  order: number;
  status: "success" | "error";
  rows_after?: number;
  columns_after?: number;
  error?: string;
}

function ExecutionDetailContent() {
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const tx = useTranslateKeyWithParams();
  const router = useRouter();
  const params = useParams();
  const executionId = params.id as string;

  const [execution, setExecution] = useState<Execution | null>(null);
  const [loading, setLoading] = useState(true);
  const [polling, setPolling] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [recipeName, setRecipeName] = useState<string>("");
  const [preparationRules, setPreparationRules] = useState<PreparationRuleResult[]>([]);
  const [userRole, setUserRole] = useState<{ isAdmin: boolean; isGroupAdmin: boolean; isExampleUser: boolean } | null>(null);
  const [loadingRole, setLoadingRole] = useState(true);

  const isExampleUser = userRole?.isExampleUser === true;

  useEffect(() => {
    const fetchUserRole = async () => {
      try {
        const res = await apiFetch("/api/user/role");
        if (res.ok) {
          const data = await res.json();
          setUserRole(data);
        }
      } catch (error) {
        console.error("Failed to fetch user role:", error);
      } finally {
        setLoadingRole(false);
      }
    };
    fetchUserRole();
  }, []);

  const fetchExecution = async () => {
    try {
      const res = await apiFetch(`/api/recipes/executions/${executionId}`);
      if (!res.ok) {
        if (res.status === 404) {
          throw new Error(tx(EXECUTION_RESULTS.execution_not_found, { id: executionId }));
        }
        let errorData: any = {};
        try {
          const text = await res.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(tx, errorData, EXECUTION_RESULTS.execution_load_error, { error: `HTTP ${res.status}` });
        throw new Error(errorMsg);
      }
      const data = await res.json();
      setExecution(data);
      setErrorMessage(null);

      // Extract preparation rule results from stage results (new format)
      if (data.result) {
        const newRuleResults: PreparationRuleResult[] = [];
        for (const [key, value] of Object.entries(data.result)) {
          // Legacy format support: rule_* keys
          if (key.startsWith("rule_")) {
            const ruleData = value as any;
            const orderMatch = key.match(/rule_(\d+)/);
            const order = orderMatch ? parseInt(orderMatch[1]) : 0;
            newRuleResults.push({
              rule_id: ruleData.rule_id || "",
              rule_name: ruleData.rule_name || `Rule ${order + 1}`,
              order: order,
              status: ruleData.status || "success",
              rows_after: ruleData.rows_after,
              columns_after: ruleData.columns_after,
              error: ruleData.error,
            });
          }
          // New format: stage results with rules_detail
          if (key.startsWith("stage_") && (value as any)?.rules_detail) {
            const stageData = value as any;
            const stageOrder = parseInt(key.replace("stage_", "")) || 0;
            if (stageData.rules_detail && Array.isArray(stageData.rules_detail)) {
              stageData.rules_detail.forEach((detail: any, idx: number) => {
                newRuleResults.push({
                  rule_id: detail.rule_id || "",
                  rule_name: detail.rule_name || `Rule ${idx + 1}`,
                  order: stageOrder * 100 + idx,
                  status: "success",
                  rows_after: detail.rows_after,
                  columns_after: detail.columns_after,
                  error: detail.error,
                });
              });
            }
          }
        }
        newRuleResults.sort((a, b) => a.order - b.order);
        setPreparationRules(newRuleResults);
      }

      // Fetch recipe details to get preparation rule names
      if (data.recipeId) {
        await fetchRecipeDetails(data.recipeId);
      }

      return data;
    } catch (error: any) {
      const msg = error.message || tx(EXECUTION_RESULTS.execution_load_error, { error: String(error) });
      setErrorMessage(msg);
      toast.error(msg);
      return null;
    } finally {
      setLoading(false);
    }
  };

  const fetchRecipeDetails = async (recipeId: string) => {
    try {
      const res = await apiFetch(`/api/recipes/${recipeId}`);
      if (res.ok) {
        const data = await res.json();
        setRecipeName(data.name || "");
        // If execution doesn't have preparation_rules, get them from recipe
        if (data.preparation_rules && data.preparation_rules.length > 0) {
          // Only set if not already set from execution results
          if (preparationRules.length === 0) {
            setPreparationRules(
              data.preparation_rules.map((r: any, index: number) => ({
                rule_id: r.id,
                rule_name: r.name,
                order: index,
                status: "success",
              }))
            );
          }
        }
      }
    } catch (error) {
      console.error("Error fetching recipe details:", error);
    }
  };

  useEffect(() => {
    if (executionId) {
      fetchExecution();
    }
  }, [executionId]);

  useEffect(() => {
    // Poll for updates if execution is running
    if (execution?.status === "running") {
      setPolling(true);
      const interval = setInterval(async () => {
        const data = await fetchExecution();
        if (data && data.status !== "running") {
          setPolling(false);
          clearInterval(interval);
        }
      }, 2000);
      return () => clearInterval(interval);
    }
  }, [execution?.status]);

  const handleCancel = async () => {
    try {
      const res = await apiFetch(`/api/recipes/executions/${executionId}/cancel`, {
        method: "POST",
      });
      if (res.ok) {
        setPolling(false);
        await fetchExecution();
        toast.success(translate(EXECUTION_RESULTS.cancel_success));
      } else {
        const data = await res.json();
        const msg = data.detail || translate(EXECUTION_RESULTS.cancel_error);
        setErrorMessage(msg);
        toast.error(msg);
      }
    } catch (error: any) {
      const msg = error.message || translate(EXECUTION_RESULTS.cancel_error);
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const getStatusIcon = (status: string) => {
    switch (status) {
      case "completed":
        return <CheckCircle className="h-8 w-8 text-green-500" />;
      case "failed":
        return <XCircle className="h-8 w-8 text-red-500" />;
      case "running":
        return <Loader2 className="h-8 w-8 animate-spin text-blue-500" />;
      default:
        return <Clock className="h-8 w-8 text-yellow-500" />;
    }
  };

  const getStatusBadge = (status: string) => {
    const classes: Record<string, string> = {
      pending: "bg-yellow-100 text-yellow-800",
      running: "bg-blue-100 text-blue-800",
      completed: "bg-green-100 text-green-800",
      failed: "bg-red-100 text-red-800",
      cancelled: "bg-gray-100 text-gray-800",
    };
    const labels: Record<string, string> = {
      pending: translate(RECIPES.status_pending),
      running: translate(RECIPES.status_running),
      completed: translate(RECIPES.status_completed),
      failed: translate(RECIPES.status_failed),
      cancelled: translate(RECIPES.status_cancelled),
    };
    return classes[status] || "bg-gray-100 text-gray-800";
  };

  const getStatusLabel = (status: string) => {
    const labels: Record<string, string> = {
      pending: translate(RECIPES.status_pending),
      running: translate(RECIPES.status_running),
      completed: translate(RECIPES.status_completed),
      failed: translate(RECIPES.status_failed),
      cancelled: translate(RECIPES.status_cancelled),
    };
    return labels[status] || status;
  };

  const getStageLabel = (type: string) => {
    const labels: Record<string, string> = {
      data_selection: translate(RECIPES.stage_data_selection),
      statistics: translate(RECIPES.stage_statistics),
      visualisation: translate(RECIPES.stage_visualisation),
      data_preparation: translate(RECIPES.stage_preparation),
    };
    return labels[type] || type;
  };

  const getRuleStatusColor = (status: string) => {
    switch (status) {
      case "success":
        return "text-green-600";
      case "error":
        return "text-red-600";
      default:
        return "text-gray-500";
    }
  };

  const getRuleStatusIcon = (status: string) => {
    switch (status) {
      case "success":
        return <CheckCircle className="h-4 w-4 text-green-600" />;
      case "error":
        return <XCircle className="h-4 w-4 text-red-600" />;
      default:
        return <Loader2 className="h-4 w-4 animate-spin text-gray-500" />;
    }
  };


  const renderStageResults = () => {
    if (!execution?.result) return null;

    const stageEntries = Object.entries(execution.result).filter(([stageKey]) => stageKey.startsWith("stage_"));
    if (stageEntries.length === 0) return null;

    return stageEntries.map(([stageKey, stageResult]) => {
      const isVisualisation = stageResult && stageResult.chart_data !== undefined;
      const isPreparation = stageResult && stageResult.rules_detail !== undefined;
      const stageNumber = stageKey.replace("stage_", "");

      return (
        <Card key={stageKey} className="mt-4">
          <CardHeader>
            <CardTitle className="text-lg">
              {isPreparation
                ? translate(RECIPES.stage_preparation)
                : translate(EXECUTION_RESULTS.stage_number).replace("{number}", stageNumber)
              }
              {stageResult.status === "success" && (
                <span className="ms-2 text-sm text-green-600">✅</span>
              )}
              {stageResult.status === "error" && (
                <span className="ms-2 text-sm text-red-600">❌</span>
              )}
            </CardTitle>
          </CardHeader>
          <CardContent>
            {isPreparation ? (
              <div className="space-y-3">
                {stageResult.message && (
                  <p className="text-sm text-muted-foreground">{stageResult.message}</p>
                )}
                <div className="grid grid-cols-2 gap-3 text-sm">
                  <div className="p-2 bg-muted/30 rounded">
                    <span className="text-muted-foreground">{translate(EXECUTION_RESULTS.rows_before)}:</span>{" "}
                    <span className="font-medium">{stageResult.rows_before} → {stageResult.rows_after}</span>
                  </div>
                  <div className="p-2 bg-muted/30 rounded">
                    <span className="text-muted-foreground">{translate(EXECUTION_RESULTS.columns_before)}:</span>{" "}
                    <span className="font-medium">{stageResult.columns_before} → {stageResult.columns_after}</span>
                  </div>
                </div>
                {stageResult.rules_detail && stageResult.rules_detail.length > 0 && (
                  <div className="space-y-2">
                    <p className="text-sm font-medium text-muted-foreground">
                      {translate(EXECUTION_RESULTS.rules_applied_label)
                        .replace("{count}", String(stageResult.rules_applied))}
                    </p>
                    {stageResult.rules_detail.map((rule: any, idx: number) => (
                      <div key={idx} className="flex items-start gap-3 p-2 border rounded-md">
                        <div className="flex-shrink-0 w-6 h-6 rounded-full bg-primary/10 flex items-center justify-center text-xs font-medium mt-0.5">
                          {idx + 1}
                        </div>
                        <div className="flex-1 min-w-0">
                          <span className="text-sm font-medium">{rule.rule_name}</span>
                          <span className="text-xs text-muted-foreground ms-2">
                            {rule.rows_before} → {rule.rows_after} rows
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </div>
            ) : isVisualisation && stageResult.status === "success" ? (
              <div className="space-y-4">
                <VisualisationResult stageResult={stageResult} />
                {stageResult.message && (
                  <p className="text-sm text-muted-foreground">{stageResult.message}</p>
                )}
                <p className="text-xs text-muted-foreground">
                  {translate(EXECUTION_RESULTS.visualisation_type_label)}: {stageResult.type} • {translate(EXECUTION_RESULTS.visualisation_columns_label)}: {stageResult.columns?.join(", ")}
                </p>
              </div>
            ) : stageResult.error ? (
              <p className="text-red-500 text-sm">{stageResult.error}</p>
            ) : (
              <pre className="p-4 bg-muted/30 rounded-md overflow-x-auto text-xs max-h-64">
                {JSON.stringify(stageResult, null, 2)}
              </pre>
            )}
          </CardContent>
        </Card>
      );
    });
  };

  if (!isLanguageLoaded || loading || loadingRole) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!execution) {
    return (
      <div className="max-w-4xl mx-auto py-8">
        <Card>
          <CardContent className="pt-6">
            {errorMessage && (
              <p className="text-center text-red-500 mb-4">{errorMessage}</p>
            )}
            <p className="text-center text-muted-foreground">
              {tx(EXECUTION_RESULTS.execution_not_found, { id: executionId })}
            </p>
            <Button className="mt-4 w-full" onClick={() => router.push("/recipes")}>
              {translate(COMMON.back)}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // If Example User, show read-only view
  if (isExampleUser) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <div className="flex items-center gap-4">
          <Button variant="ghost" size="icon" onClick={() => router.push(`/recipes/${execution.recipeId}`)}>
            <ArrowLeft className="h-4 w-4" />
          </Button>
          <div>
            <h1 className="text-3xl font-bold">{translate(EXECUTION_RESULTS.execution_title)}</h1>
            {recipeName && (
              <p className="text-sm text-muted-foreground">
                {translate(EXECUTION_RESULTS.recipe_label)}: {recipeName}
              </p>
            )}
            {execution.preparation_rules_applied !== undefined && execution.preparation_rules_applied > 0 && (
              <p className="text-sm text-muted-foreground">
                {translate(EXECUTION_RESULTS.preparation_rules_applied)}: {execution.preparation_rules_applied}
              </p>
            )}
          </div>
        </div>

        <div className="p-6 bg-orange-50 border border-orange-200 rounded-md text-orange-800 text-center">
          <Lock className="h-10 w-10 mx-auto mb-3 text-orange-600" />
          <p className="text-sm mb-4">
            {translate(COMPONENTS.readonly_wrapper)}
          </p>
          <Link href="/register">
            <Button>
              <UserPlus className="h-4 w-4 me-2" />
              {translate(COMPONENTS.example_user_banner.register_button)}
            </Button>
          </Link>
        </div>

        {errorMessage && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800">
            <span className="text-sm">{errorMessage}</span>
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle className="flex items-center justify-between">
              <span>{translate(EXECUTION_RESULTS.execution_status)}</span>
              <div className="flex items-center gap-3">
                <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusBadge(execution.status)}`}>
                  {getStatusLabel(execution.status)}
                </span>
                {getStatusIcon(execution.status)}
              </div>
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-4 opacity-60">
              <div>
                <div className="flex justify-between text-sm mb-1">
                  <span>{translate(EXECUTION_RESULTS.execution_progress)}</span>
                  <span>{execution.progress}%</span>
                </div>
                <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary transition-all duration-500"
                    style={{ width: `${execution.progress}%` }}
                  />
                </div>
              </div>

              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground">{translate(EXECUTION_RESULTS.execution_started)}</span>
                  <p>{formatDateTime(execution.startedAt)}</p>
                </div>
                {execution.completedAt && (
                  <div>
                    <span className="text-muted-foreground">{translate(EXECUTION_RESULTS.status_completed)}</span>
                    <p>{formatDateTime(execution.completedAt)}</p>
                  </div>
                )}
              </div>

              {execution.error && (
                <div className="p-4 bg-red-50 border border-red-200 rounded-md text-red-800">
                  <p className="font-medium">{translate(EXECUTION_RESULTS.execution_error)}</p>
                  <p className="text-sm mt-1 whitespace-pre-wrap">{execution.error}</p>
                </div>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Preparation Rules Applied Section */}
        {preparationRules.length > 0 && (
          <Card>
            <CardHeader>
              <CardTitle className="text-lg">
                {translate(EXECUTION_RESULTS.preparation_rules_applied_title)}
              </CardTitle>
              <p className="text-sm text-muted-foreground">
                {translate(EXECUTION_RESULTS.preparation_rules_applied_description)}
              </p>
            </CardHeader>
            <CardContent>
              <div className="space-y-2 opacity-60">
                {preparationRules.map((rule, index) => (
                  <div
                    key={rule.rule_id || index}
                    className="flex items-center gap-3 p-3 border rounded-md hover:bg-muted/50 transition-colors"
                  >
                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-medium">
                      {index + 1}
                    </div>
                    <div className="flex-1">
                      <div className="flex items-center gap-2">
                        <span className="font-medium">{rule.rule_name}</span>
                        <span className={`text-xs ${getRuleStatusColor(rule.status)}`}>
                          {getRuleStatusIcon(rule.status)}
                          {rule.status === "success" ? translate(COMMON.success_label) : translate(COMMON.error_label)}
                        </span>
                      </div>
                      {rule.rows_after !== undefined && (
                        <div className="text-xs text-muted-foreground">
                          {translate(EXECUTION_RESULTS.rows_after)}: {rule.rows_after}
                          {rule.columns_after !== undefined && (
                            <span className="ms-2">
                              • {translate(EXECUTION_RESULTS.columns_after)}: {rule.columns_after}
                            </span>
                          )}
                        </div>
                      )}
                      {rule.error && (
                        <div className="text-xs text-red-500 mt-1">{rule.error}</div>
                      )}
                    </div>
                  </div>
                ))}
              </div>
              {execution.preparation_rules_applied !== undefined && (
                <div className="mt-3 text-sm text-muted-foreground">
                  {translate(EXECUTION_RESULTS.total_rules_applied)}: {execution.preparation_rules_applied}
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Stage Results */}
        {execution.result && (
          <div>
            <h2 className="text-xl font-semibold mb-4">{translate(EXECUTION_RESULTS.execution_stage_results)}</h2>
            {renderStageResults()}
          </div>
        )}

        <div className="flex gap-4">
          <Button variant="outline" onClick={() => router.push(`/recipes/${execution.recipeId}`)}>
            {translate(EXECUTION_RESULTS.back_to_recipe)}
          </Button>
          <Button disabled>
            <Download className="me-2 h-4 w-4" />
            {translate(EXECUTION_RESULTS.export_results)}
          </Button>
        </div>
      </div>
    );
  }

  // Normal user view - full access
  return (
    <div className="max-w-4xl mx-auto space-y-6">
      <div className="flex items-center gap-4">
        <Button variant="ghost" size="icon" onClick={() => router.push(`/recipes/${execution.recipeId}`)}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <div>
          <h1 className="text-3xl font-bold">{translate(EXECUTION_RESULTS.execution_title)}</h1>
          {recipeName && (
            <p className="text-sm text-muted-foreground">
              {translate(EXECUTION_RESULTS.recipe_label)}: {recipeName}
            </p>
          )}
          {execution.preparation_rules_applied !== undefined && execution.preparation_rules_applied > 0 && (
            <p className="text-sm text-muted-foreground">
              {translate(EXECUTION_RESULTS.preparation_rules_applied)}: {execution.preparation_rules_applied}
            </p>
          )}
        </div>
      </div>

      {errorMessage && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800">
          <span className="text-sm">{errorMessage}</span>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center justify-between">
            <span>{translate(EXECUTION_RESULTS.execution_status)}</span>
            <div className="flex items-center gap-3">
              {execution.status === "running" && (
                <Button variant="destructive" size="sm" onClick={handleCancel} className="h-8 text-xs">
                  <XCircle className="me-1 h-3.5 w-3.5" />
                  {translate(EXECUTION_RESULTS.cancel_button)}
                </Button>
              )}
              <span className={`px-3 py-1 rounded-full text-sm font-medium ${getStatusBadge(execution.status)}`}>
                {getStatusLabel(execution.status)}
              </span>
              {getStatusIcon(execution.status)}
            </div>
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-4">
            <div>
              <div className="flex justify-between text-sm mb-1">
                <span>{translate(EXECUTION_RESULTS.execution_progress)}</span>
                <span>{execution.progress}%</span>
              </div>
              <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
                <div
                  className="h-full bg-primary transition-all duration-500"
                  style={{ width: `${execution.progress}%` }}
                />
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">{translate(EXECUTION_RESULTS.execution_started)}</span>
                <p>{formatDateTime(execution.startedAt)}</p>
              </div>
              {execution.completedAt && (
                <div>
                  <span className="text-muted-foreground">{translate(EXECUTION_RESULTS.status_completed)}</span>
                  <p>{formatDateTime(execution.completedAt)}</p>
                </div>
              )}
            </div>

            {execution.error && (
              <div className="p-4 bg-red-50 border border-red-200 rounded-md text-red-800">
                <p className="font-medium">{translate(EXECUTION_RESULTS.execution_error)}</p>
                <p className="text-sm mt-1 whitespace-pre-wrap">{execution.error}</p>
              </div>
            )}
          </div>
        </CardContent>
      </Card>

      {/* Preparation Rules Applied Section */}
      {preparationRules.length > 0 && (
        <Card>
          <CardHeader>
            <CardTitle className="text-lg">
              {translate(EXECUTION_RESULTS.preparation_rules_applied_title)}
            </CardTitle>
            <p className="text-sm text-muted-foreground">
              {translate(EXECUTION_RESULTS.preparation_rules_applied_description)}
            </p>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {preparationRules.map((rule, index) => (
                <div
                  key={rule.rule_id || index}
                  className="flex items-center gap-3 p-3 border rounded-md hover:bg-muted/50 transition-colors"
                >
                  <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center text-sm font-medium">
                    {index + 1}
                  </div>
                  <div className="flex-1">
                    <div className="flex items-center gap-2">
                      <span className="font-medium">{rule.rule_name}</span>
                      <span className={`text-xs ${getRuleStatusColor(rule.status)}`}>
                        {getRuleStatusIcon(rule.status)}
                        {rule.status === "success" ? translate(COMMON.success_label) : translate(COMMON.error_label)}
                      </span>
                    </div>
                    {rule.rows_after !== undefined && (
                      <div className="text-xs text-muted-foreground">
                        {translate(EXECUTION_RESULTS.rows_after)}: {rule.rows_after}
                        {rule.columns_after !== undefined && (
                          <span className="ms-2">
                            • {translate(EXECUTION_RESULTS.columns_after)}: {rule.columns_after}
                          </span>
                        )}
                      </div>
                    )}
                    {rule.error && (
                      <div className="text-xs text-red-500 mt-1">{rule.error}</div>
                    )}
                  </div>
                </div>
              ))}
            </div>
            {execution.preparation_rules_applied !== undefined && (
              <div className="mt-3 text-sm text-muted-foreground">
                {translate(EXECUTION_RESULTS.total_rules_applied)}: {execution.preparation_rules_applied}
              </div>
            )}
          </CardContent>
        </Card>
      )}

      {/* Stage Results */}
      {execution.result && (
        <div>
          <h2 className="text-xl font-semibold mb-4">{translate(EXECUTION_RESULTS.execution_stage_results)}</h2>
          {renderStageResults()}
        </div>
      )}

      <div className="flex gap-4">
        <Button variant="outline" onClick={() => router.push(`/recipes/${execution.recipeId}`)}>
          {translate(EXECUTION_RESULTS.back_to_recipe)}
        </Button>
        {execution.status === "completed" && (
          <Button onClick={() => window.print()}>
            <Download className="me-2 h-4 w-4" />
            {translate(EXECUTION_RESULTS.export_results)}
          </Button>
        )}
      </div>
    </div>
  );
}

export default function ExecutionDetailPage() {
  return (
    <ProtectedRoute>
      <ExecutionDetailContent />
    </ProtectedRoute>
  );
}