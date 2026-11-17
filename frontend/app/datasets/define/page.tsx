"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { useDB } from "@/lib/db-context";
import { ProtectedRoute } from "@/components/protected-route";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, Database, ArrowLeft, ArrowRight, CheckCircle, XCircle, Table, Eye, RefreshCw } from "lucide-react";

// Import translations for this module
import { DEFINE } from "./translations";
import { DATASETS } from "../translations";
import { COMMON } from "@/app/common/translations";
import { formatDate } from "@/lib/date-format";

interface DatabaseConnection {
  id: string;
  connectionId: number;
  name: string;
  type: string;
  host: string;
  port: number;
  database: string;
  username: string;
  dbConnectionGroup: string;
  userId: string;
  isOwn: boolean;
  isShared: boolean;
}

interface TableSchema {
  name: string;
  type: string;
  nullable: boolean;
  is_primary?: boolean;
}

interface PreviewData {
  columns: string[];
  rows: any[][];
}

function ConnectDatabaseContent() {
  const { t, isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const { defaultConnectionId } = useDB();
  const router = useRouter();
  const { data: session } = useSession();
  const [step, setStep] = useState(1);
  const [loading, setLoading] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Step 1: Select Connection
  const [connections, setConnections] = useState<DatabaseConnection[]>([]);
  const [loadingConnections, setLoadingConnections] = useState(true);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string>("");

  // Step 2: Select Source Type (Table or View)
  const [sourceType, setSourceType] = useState<"table" | "view">("table");
  const [sources, setSources] = useState<string[]>([]);
  const [loadingSources, setLoadingSources] = useState(false);
  const [selectedSource, setSelectedSource] = useState<string>("");

  // Step 3: Verify and Preview
  const [schema, setSchema] = useState<TableSchema[]>([]);
  const [preview, setPreview] = useState<PreviewData | null>(null);
  const [loadingSchema, setLoadingSchema] = useState(false);
  const [verifying, setVerifying] = useState(false);

  // Step 4: Name and Save
  const [datasetName, setDatasetName] = useState("");
  const [datasetDescription, setDatasetDescription] = useState("");
  const [shared, setShared] = useState(false);
  const [groupInfo, setGroupInfo] = useState<{ userGroup: string; groupDescription: string } | null>(null);

  // Existing table/view datasets sidebar
  const [tableDatasets, setTableDatasets] = useState<any[]>([]);
  const [loadingTableDatasets, setLoadingTableDatasets] = useState(true);

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  const getSourceTypeName = (type: string) => {
    const names: Record<string, string> = {
      table: translate(DEFINE.table),
      view: translate(DEFINE.view),
    };
    return names[type] || type;
  };

  const getConnectionLabel = (conn: DatabaseConnection) => {
    const isShared = conn.isShared === true;
    const label = `${conn.name} (${conn.type})`;
    return isShared ? `* ${label}` : label;
  };

  // Get the selected connection name for display in the closed state
  const getSelectedConnectionName = () => {
    if (!selectedConnectionId) return "";
    const conn = connections.find(c => c.id === selectedConnectionId);
    return conn ? getConnectionLabel(conn) : "";
  };

  const fetchTableDatasets = async () => {
    setLoadingTableDatasets(true);
    try {
      const res = await apiFetch("/api/datasets");
      if (res.ok) {
        const data = await res.json();
        const ownTableDatasets = (data.datasets || []).filter(
          (ds: any) => (ds.sourceType === "table" || ds.sourceType === "view") && ds.isOwn !== false
        );
        setTableDatasets(ownTableDatasets);
      }
    } catch (error) {
      console.error("Error fetching table datasets:", error);
    } finally {
      setLoadingTableDatasets(false);
    }
  };

  // Fetch connections on load
  useEffect(() => {
    const fetchConnections = async () => {
      try {
        setLoadingConnections(true);
        const res = await apiFetch("/api/user/database-connections/available");
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
          const errorMsg = getErrorMessageFromData(translate, errorData, DEFINE.load_connections_error);
          throw new Error(errorMsg);
        }
        const data = await res.json();
        setConnections(data.connections || []);
        if (data.connections && data.connections.length > 0) {
          setSelectedConnectionId(data.connections[0].id);
        }
      } catch (error: any) {
        console.error("Error fetching connections:", error);
        const msg = error.message || translate(DEFINE.load_connections_error);
        setErrorMessage(msg);
        toast.error(msg);
      } finally {
        setLoadingConnections(false);
      }
    };

    const fetchGroupInfo = async () => {
      try {
        const res = await apiFetch("/api/groups/user/me");
        if (res.ok) {
          const data = await res.json();
          setGroupInfo({
            userGroup: data.user_group,
            groupDescription: data.group_description,
          });
        }
      } catch (error) {
        console.error("Failed to fetch group info:", error);
      }
    };

    fetchConnections();
    fetchGroupInfo();
    fetchTableDatasets();
  }, []);

  // Auto-select the default AI connection when it becomes known
  useEffect(() => {
    if (defaultConnectionId && connections.length > 0) {
      const defaultConn = connections.find(c => c.id === defaultConnectionId);
      if (defaultConn) {
        setSelectedConnectionId(defaultConnectionId);
      }
    }
  }, [defaultConnectionId, connections]);

  // Fetch tables/views when connection or source type changes
  useEffect(() => {
    if (selectedConnectionId) {
      fetchSources();
    }
  }, [selectedConnectionId, sourceType]);

  const fetchSources = async () => {
    if (!selectedConnectionId) return;
    setLoadingSources(true);
    setSources([]);
    setSelectedSource("");
    setSchema([]);
    setPreview(null);
    setErrorMessage(null);

    try {
      const selectedConn = connections.find(c => c.id === selectedConnectionId);
      if (!selectedConn) {
        throw new Error("Connection not found");
      }

      const endpoint = sourceType === "table" 
        ? `/api/datasets/connection/${selectedConn.connectionId}/tables`
        : `/api/datasets/connection/${selectedConn.connectionId}/views`;

      const res = await apiFetch(endpoint);

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
        const errorMsg = getErrorMessageFromData(translate, errorData, DEFINE.load_sources_error);
        throw new Error(errorMsg);
      }

      const data = await res.json();
      setSources(data.sources || []);
      if (data.sources && data.sources.length > 0) {
        setSelectedSource(data.sources[0]);
      }
    } catch (error: any) {
      console.error("Error fetching sources:", error);
      const msg = error.message || translate(DEFINE.load_sources_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setLoadingSources(false);
    }
  };

  const handleVerify = async () => {
    if (!selectedSource) {
      const msg = translate(DEFINE.select_source_first);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }

    setVerifying(true);
    setErrorMessage(null);
    setSchema([]);
    setPreview(null);

    try {
      const selectedConn = connections.find(c => c.id === selectedConnectionId);
      if (!selectedConn) {
        throw new Error("Connection not found");
      }

      const res = await apiFetch(`/api/datasets/connection/${selectedConn.connectionId}/schema/${selectedSource}`);

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
        const errorMsg = getErrorMessageFromData(translate, errorData, DEFINE.verify_error);
        throw new Error(errorMsg);
      }

      const data = await res.json();
      setSchema(data.schema || []);
      setPreview(data.preview || null);
      setStep(3);
      setSuccessMessage(translate(DEFINE.verify_success));
      toast.success(translate(DEFINE.verify_success));
    } catch (error: any) {
      const msg = error.message || translate(DEFINE.verify_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setVerifying(false);
    }
  };

  const handleSave = async () => {
    if (!datasetName.trim()) {
      const msg = translate(DEFINE.name_required);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }

    setSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const selectedConn = connections.find(c => c.id === selectedConnectionId);
      if (!selectedConn) {
        throw new Error("Connection not found");
      }

      const payload = {
        name: datasetName,
        description: datasetDescription || null,
        sourceType: sourceType,
        connectionId: selectedConn.connectionId,
        tableName: selectedSource,
        shared: shared,
      };

      const res = await apiFetch("/api/datasets/define", {
        method: "POST",
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
        const errorMsg = getErrorMessageFromData(translate, errorData, DEFINE.save_error);
        throw new Error(errorMsg);
      }

      const data = await res.json();
      setSuccessMessage(translate(DEFINE.save_success));
      toast.success(translate(DEFINE.save_success));
      fetchTableDatasets();
      setTimeout(() => {
        router.push("/datasets/manage");
      }, 1500);
    } catch (error: any) {
      const msg = error.message || translate(DEFINE.save_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
    }
  };

  const handleBack = () => {
    if (step > 1) {
      setStep(step - 1);
      setErrorMessage(null);
      setSuccessMessage(null);
    } else {
      router.push("/datasets/manage");
    }
  };

  if (!isLanguageLoaded || loadingConnections) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (connections.length === 0) {
    return (
      <div className="max-w-lg mx-auto py-12">
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2">
              <Database className="h-6 w-6" />
              {translate(DEFINE.title)}
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-muted-foreground">
              {translate(DEFINE.no_connections_message)}
            </p>
            <Button onClick={() => router.push("/settings/database")} className="w-full">
              {translate(DEFINE.go_to_db_settings)}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isAdminUser = session?.user?.isAdmin === true;
  const showSharedToggle = isAdminUser || (groupInfo && groupInfo.userGroup !== "00");

  return (
    <div className="max-w-6xl mx-auto py-8">
      <div className="flex items-center gap-4 mb-6">
        <Button variant="ghost" size="icon" onClick={() => router.push("/datasets/manage")}>
          <ArrowLeft className="h-4 w-4" />
        </Button>
        <h1 className="text-3xl font-bold">{translate(DEFINE.title)}</h1>
      </div>

      <div className="flex gap-6 max-lg:flex-col">
        {/* Sidebar: Existing datasets */}
        <div className="hidden lg:block w-72 flex-shrink-0">
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">
                {translate(DEFINE.existing_title)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loadingTableDatasets ? (
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  {translate(COMMON.loading)}
                </div>
              ) : tableDatasets.length === 0 ? (
                <p className="text-sm text-muted-foreground">{translate(DEFINE.existing_none)}</p>
              ) : (
                <div className="space-y-1">
                  {tableDatasets.map((ds: any) => (
                    <div
                      key={ds.id}
                      className="flex items-center justify-between p-2 rounded-md hover:bg-muted/50 transition-colors cursor-pointer"
                      onClick={() => router.push(`/datasets/${ds.id}`)}
                    >
                      <div className="min-w-0">
                        <div className="text-sm font-medium truncate">{ds.name}</div>
                        <div className="text-xs text-muted-foreground">
                          {formatDate(ds.createdAt)}
                        </div>
                      </div>
                      <span className="text-xs text-muted-foreground bg-muted px-1.5 py-0.5 rounded flex-shrink-0 ms-2">
                        {ds.sourceType === "view" ? translate(DEFINE.view) : translate(DEFINE.table)}
                      </span>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>
        </div>

        {/* Main wizard column */}
        <div className="flex-1 min-w-0">
      {/* Progress Steps */}
      <div className="mb-8">
        <div className="flex justify-between mb-2">
          <div className="flex flex-col items-center">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${step >= 1 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
              1
            </div>
            <span className="text-xs mt-1 text-muted-foreground">{translate(DEFINE.step_connection)}</span>
          </div>
          <div className="flex flex-col items-center">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${step >= 2 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
              2
            </div>
            <span className="text-xs mt-1 text-muted-foreground">{translate(DEFINE.step_source)}</span>
          </div>
          <div className="flex flex-col items-center">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${step >= 3 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
              3
            </div>
            <span className="text-xs mt-1 text-muted-foreground">{translate(DEFINE.step_verify)}</span>
          </div>
          <div className="flex flex-col items-center">
            <div className={`w-8 h-8 rounded-full flex items-center justify-center text-sm font-medium ${step >= 4 ? "bg-primary text-primary-foreground" : "bg-muted text-muted-foreground"}`}>
              4
            </div>
            <span className="text-xs mt-1 text-muted-foreground">{translate(DEFINE.step_save)}</span>
          </div>
        </div>
        <div className="w-full h-2 bg-muted rounded-full overflow-hidden">
          <div className="h-full bg-primary transition-all duration-300" style={{ width: `${(step / 4) * 100}%` }} />
        </div>
      </div>

      {errorMessage && (
        <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
          <span className="text-sm">{errorMessage}</span>
          <button onClick={dismissError} className="text-red-500 hover:text-red-700">
            <XCircle className="h-5 w-5" />
          </button>
        </div>
      )}

      {successMessage && (
        <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md text-green-800 flex items-center justify-between">
          <span className="text-sm">{successMessage}</span>
          <button onClick={dismissSuccess} className="text-green-500 hover:text-green-700">
            <CheckCircle className="h-5 w-5" />
          </button>
        </div>
      )}

      <Card>
        <CardContent className="pt-6">
          {/* Step 1: Select Connection */}
          {step === 1 && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">{translate(DEFINE.step1_title)}</h2>
              <p className="text-sm text-muted-foreground">
                {translate(DEFINE.step1_description)}
              </p>
              <div className="space-y-2">
                <Label htmlFor="connection" className="flex items-center">
                  {translate(DEFINE.connection_label)}
                  <span className="text-red-500 ms-1">*</span>
                </Label>
                <div className="relative flex items-center">
                  <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                  <Select
                    value={selectedConnectionId}
                    onValueChange={(val) => setSelectedConnectionId(val || "")}
                  >
                    <SelectTrigger id="connection" className="flex-1">
                      <SelectValue placeholder={translate(DEFINE.select_connection)}>
                        {getSelectedConnectionName()}
                      </SelectValue>
                    </SelectTrigger>
                    <SelectContent>
                      {connections.map((conn) => (
                        <SelectItem key={conn.id} value={conn.id}>
                          {getConnectionLabel(conn)}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                </div>
              </div>
            </div>
          )}

          {/* Step 2: Select Source */}
          {step === 2 && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">{translate(DEFINE.step2_title)}</h2>
              <p className="text-sm text-muted-foreground">
                {translate(DEFINE.step2_description)}
              </p>
              <div className="space-y-2">
                <Label className="flex items-center">
                  {translate(DEFINE.source_type_label)}
                  <span className="text-red-500 ms-1">*</span>
                </Label>
                <div className="flex gap-2">
                  <Button
                    variant={sourceType === "table" ? "default" : "outline"}
                    onClick={() => setSourceType("table")}
                    className="flex-1"
                  >
                    <Table className="h-4 w-4 me-2" />
                    {translate(DEFINE.table)}
                  </Button>
                  <Button
                    variant={sourceType === "view" ? "default" : "outline"}
                    onClick={() => setSourceType("view")}
                    className="flex-1"
                  >
                    <Eye className="h-4 w-4 me-2" />
                    {translate(DEFINE.view)}
                  </Button>
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="source" className="flex items-center">
                  {translate(DEFINE.source_label)}
                  <span className="text-red-500 ms-1">*</span>
                </Label>
                {loadingSources ? (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Loader2 className="h-4 w-4 animate-spin" />
                    {translate(COMMON.loading)}
                  </div>
                ) : sources.length === 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {translate(DEFINE.no_sources)}
                  </p>
                ) : (
                  <div className="relative flex items-center">
                    <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                    <Select
                      value={selectedSource}
                      onValueChange={(val) => setSelectedSource(val || "")}
                    >
                      <SelectTrigger id="source" className="flex-1">
                        <SelectValue placeholder={translate(DEFINE.select_source)} />
                      </SelectTrigger>
                      <SelectContent>
                        {sources.map((source) => (
                          <SelectItem key={source} value={source}>
                            {source}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )}
              </div>
              <Button
                onClick={handleVerify}
                disabled={!selectedSource || verifying}
                className="w-full"
              >
                {verifying ? (
                  <>
                    <Loader2 className="h-4 w-4 animate-spin me-2" />
                    {translate(COMMON.verifying)}
                  </>
                ) : (
                  <>
                    <RefreshCw className="h-4 w-4 me-2" />
                    {translate(DEFINE.verify_button)}
                  </>
                )}
              </Button>
            </div>
          )}

          {/* Step 3: Verify and Preview */}
          {step === 3 && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">{translate(DEFINE.step3_title)}</h2>
              <p className="text-sm text-muted-foreground">
                {translate(DEFINE.step3_description)}
              </p>
              {schema.length > 0 && (
                <p className="text-sm text-green-600 flex items-center gap-1">
                  <CheckCircle className="h-4 w-4" />
                  {translate(DEFINE.verify_success)}
                </p>
              )}
            </div>
          )}

          {/* Step 4: Name and Save */}
          {step === 4 && (
            <div className="space-y-4">
              <h2 className="text-xl font-semibold">{translate(DEFINE.step4_title)}</h2>
              <p className="text-sm text-muted-foreground">
                {translate(DEFINE.step4_description)}
              </p>
              <div className="space-y-2">
                <Label htmlFor="datasetName" className="flex items-center">
                  {translate(DEFINE.dataset_name)}
                  <span className="text-red-500 ms-1">*</span>
                </Label>
                <div className="relative flex items-center">
                  <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                  <Input dir="auto"
                    id="datasetName"
                    value={datasetName}
                    onChange={(e) => setDatasetName(e.target.value)}
                    placeholder={translate(DEFINE.dataset_name_placeholder)}
                    className="flex-1"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">{translate(DEFINE.description_label)}</Label>
                <Input dir="auto"
                  id="description"
                  value={datasetDescription}
                  onChange={(e) => setDatasetDescription(e.target.value)}
                  placeholder={translate(DEFINE.description_placeholder)}
                />
              </div>
              {showSharedToggle && (
                <div className="flex items-center justify-between p-3 bg-muted/30 rounded-md border border-muted">
                  <div>
                    <Label>{translate(DEFINE.shared_label)}</Label>
                    <p className="text-sm text-muted-foreground">
                      {translate(DEFINE.shared_description)}
                    </p>
                  </div>
                  <Switch
                    checked={shared}
                    onCheckedChange={(checked) => setShared(checked)}
                  />
                </div>
              )}
            </div>
          )}

          {/* Navigation Buttons */}
          <div className="flex justify-between mt-6 pt-4 border-t">
            <Button variant="outline" onClick={handleBack}>
              {step === 1 ? translate(COMMON.cancel) : translate(COMMON.back)}
            </Button>
            {step < 3 ? (
              <Button
                onClick={() => {
                  if (step === 1 && selectedConnectionId) {
                    setStep(2);
                  } else if (step === 2 && selectedSource) {
                    handleVerify();
                  }
                }}
                disabled={(step === 1 && !selectedConnectionId) || (step === 2 && (!selectedSource || verifying))}
              >
                {step === 2 ? translate(DEFINE.verify_button) : translate(COMMON.next)}
                {step !== 2 && <ArrowRight className="ms-2 h-4 w-4" />}
              </Button>
            ) : step === 3 ? (
              <Button onClick={() => setStep(4)}>
                {translate(COMMON.next)}
                <ArrowRight className="ms-2 h-4 w-4" />
              </Button>
            ) : (
              <Button onClick={handleSave} disabled={submitting}>
                {submitting ? (
                  <>
                    <Loader2 className="me-2 h-4 w-4 animate-spin" />
                    {translate(COMMON.saving)}
                  </>
                ) : (
                  translate(DEFINE.save_button)
                )}
              </Button>
            )}
          </div>

          {/* Verify Source Details — shown after verification */}
          {schema.length > 0 && (
            <div className="mt-6 pt-4 border-t space-y-4">
              {/* Schema */}
              <div>
                <Label>{translate(DEFINE.schema_label)}</Label>
                <div className="mt-1 border rounded-md overflow-hidden">
                  <table className="w-full text-sm">
                    <thead className="bg-muted">
                      <tr>
                        <th className="text-start px-3 py-2">{translate(DEFINE.column_name)}</th>
                        <th className="text-start px-3 py-2">{translate(DEFINE.column_type)}</th>
                        <th className="text-start px-3 py-2">{translate(DEFINE.nullable)}</th>
                      </tr>
                    </thead>
                    <tbody>
                      {schema.map((col, index) => (
                        <tr key={index} className={index % 2 === 0 ? "bg-background" : "bg-muted/30"}>
                          <td className="px-3 py-1.5 font-mono text-xs">{col.name}</td>
                          <td className="px-3 py-1.5 text-xs">{col.type}</td>
                          <td className="px-3 py-1.5 text-xs">{translate(col.nullable ? COMMON.true_label : COMMON.false_label)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>

              {/* Preview Data */}
              {preview && preview.rows && preview.rows.length > 0 && (
                <div>
                  <Label>{translate(DEFINE.preview_label)}</Label>
                  <div className="mt-1 border rounded-md overflow-x-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-muted">
                        <tr>
                          {preview.columns.map((col) => (
                            <th key={col} className="text-start px-3 py-2">{col}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {preview.rows.map((row, rowIndex) => (
                          <tr key={rowIndex} className={rowIndex % 2 === 0 ? "bg-background" : "bg-muted/30"}>
                            {row.map((cell, cellIndex) => (
                              <td key={cellIndex} className="px-3 py-1.5 text-xs">
                                {cell !== null && cell !== undefined ? String(cell) : ""}
                              </td>
                            ))}
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </CardContent>
      </Card>
        </div>
      </div>
    </div>
  );
}

export default function ConnectDatabasePage() {
  return (
    <ProtectedRoute>
      <ConnectDatabaseContent />
    </ProtectedRoute>
  );
}