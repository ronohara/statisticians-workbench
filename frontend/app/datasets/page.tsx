"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { useTranslation } from "@/lib/translation-context";
import { formatDateTime } from "@/lib/date-format";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { useAI } from "@/lib/ai-context";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Upload, Loader2, FileText, CheckCircle, XCircle, Trash2, Lock, UserPlus } from "lucide-react";
import Link from "next/link";

// Import translations for this module
import { DATASETS } from "./translations";
import { DATASET_UPLOAD } from "./upload/translations";
import { COMMON } from "@/app/common/translations";
import { CHAT } from "@/app/chat/translations";
import { COMPONENTS } from "@/components/translations";

interface GroupInfo {
  userGroup: string;
  groupDescription: string;
}

async function getToken(): Promise<string> {
  const res = await fetch("/api/auth/token", { credentials: "include" });
  if (!res.ok) throw new Error("Unauthorized");
  const data = await res.json();
  if (!data.token) throw new Error("No token in response");
  return data.token;
}

interface Dataset {
  id: string;
  name: string;
  filePath: string | null;
  description: string | null;
  createdAt: string;
  datasetGroup: string;
  userId: string;
  isOwn: boolean;
  isShared: boolean;
  sourceType: string;
}

interface Model {
  id: number;
  modelCode: string;
  modelName: string;
}

interface AvailableConnection {
  id: string;
  connectionId: number;
  name: string;
  provider: string;
  aiConnectionGroup: string;
  userId: string;
  userName: string;
  isOwn: boolean;
}

function DatasetsListContent() {
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const { defaultConnectionId } = useAI();
  const router = useRouter();
  const { data: session } = useSession();

  const [connections, setConnections] = useState<AvailableConnection[]>([]);
  const [selectedConnectionId, setSelectedConnectionId] = useState<string | null>(null);
  const [selectedModelCode, setSelectedModelCode] = useState<string | null>(null);
  const [models, setModels] = useState<Model[]>([]);
  const [loadingModels, setLoadingModels] = useState(false);
  const [loadingConnections, setLoadingConnections] = useState(true);

  // Group info for shared toggle
  const [groupInfo, setGroupInfo] = useState<GroupInfo | null>(null);
  const [loadingGroupInfo, setLoadingGroupInfo] = useState(true);

  const [file, setFile] = useState<File | null>(null);
  const [datasetName, setDatasetName] = useState("");
  const [datasetDescription, setDatasetDescription] = useState("");
  const [shared, setShared] = useState(false);
  const [isUploading, setIsUploading] = useState(false);
  const [isGenerating, setIsGenerating] = useState(false);
  const [datasets, setDatasets] = useState<Dataset[]>([]);
  const [selectedDatasetId, setSelectedDatasetId] = useState<string | null>(null);
  const [generatedDesc, setGeneratedDesc] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // The escalation control (AI limits plan, Item 12 / D6) — duplicated from
  // upload/page.tsx deliberately, per D6: "generate description" may be removed and two
  // copies are cheaper to delete than a shared component is to unwind.
  const [escalation, setEscalation] = useState<number | null>(null);
  const [escalationValue, setEscalationValue] = useState<string>("");
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<{ isAdmin: boolean; isGroupAdmin: boolean; isExampleUser: boolean } | null>(null);
  const [loadingRole, setLoadingRole] = useState(true);

  const fileInputRef = useRef<HTMLInputElement>(null);

  // Upload limits
  const [maxUploadCount, setMaxUploadCount] = useState<number>(0);
  const [maxUploadSizeMB, setMaxUploadSizeMB] = useState<number>(0);
  const [currentCount, setCurrentCount] = useState<number>(0);

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  const isExampleUser = userRole?.isExampleUser === true;

  const getConnectionLabel = (conn: AvailableConnection) => {
    const name = conn.name || conn.provider || String(conn.connectionId);
    if (conn.isOwn) {
      return `${name} (${conn.provider})`;
    } else {
      return `* ${name} (${conn.provider})`;
    }
  };

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
    } finally {
      setLoadingGroupInfo(false);
    }
  };

  const fetchAvailableConnections = async () => {
    setLoadingConnections(true);
    try {
      const res = await apiFetch("/api/user/ai-connections/available");
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
        const errorMsg = getErrorMessageFromData(translate, errorData, CHAT.connections_load_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      setConnections(data.connections || []);
      if (data.connections && data.connections.length > 0) {
        setSelectedConnectionId(data.connections[0].id);
      } else {
        setSelectedConnectionId(null);
      }
    } catch (error: any) {
      console.error("Error fetching connections:", error);
      setConnections([]);
      setSelectedConnectionId(null);
    } finally {
      setLoadingConnections(false);
    }
  };

  const fetchModels = async (connectionId: string) => {
    setLoadingModels(true);
    try {
      const res = await apiFetch(`/api/user/ai-connections/${connectionId}/models?enabled=true`);
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
        const errorMsg = getErrorMessageFromData(translate, errorData, CHAT.models_load_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      setModels(data.models || []);
      if (data.models && data.models.length > 0) {
        setSelectedModelCode(data.models[0].modelCode);
      } else {
        setSelectedModelCode(null);
      }
    } catch (error: any) {
      console.error("Error fetching models:", error);
      setModels([]);
      setSelectedModelCode(null);
    } finally {
      setLoadingModels(false);
    }
  };

  const fetchDatasets = async () => {
    try {
      const res = await apiFetch(`/api/datasets/`);
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
        const errorMsg = getErrorMessageFromData(translate, errorData, DATASETS.list_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      const uploadedDatasets = (data.datasets || []).filter(
        (ds: Dataset) => ds.sourceType === "upload"
      );
      setDatasets(uploadedDatasets);
      setCurrentCount(uploadedDatasets.length);
    } catch (error) {
      console.error("Error fetching datasets:", error);
    }
  };

  const fetchUserLimits = async () => {
    try {
      const res = await apiFetch("/api/user-settings");
      if (res.ok) {
        const data = await res.json();
        setMaxUploadCount(data.maxUploadCount || 0);
        setMaxUploadSizeMB(data.maxUploadSizeMB || 0);
      }
    } catch (error) {
      console.error("Error fetching user limits:", error);
    }
  };

  useEffect(() => {
    fetchGroupInfo();
    fetchAvailableConnections();
    fetchDatasets();
    fetchUserLimits();
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

  useEffect(() => {
    if (selectedConnectionId !== null) {
      const conn = connections.find(c => c.id === selectedConnectionId);
      if (conn) {
        fetchModels(selectedConnectionId);
      }
    }
  }, [selectedConnectionId]);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files.length > 0) {
      setFile(e.target.files[0]);
      if (!datasetName) {
        const name = e.target.files[0].name.replace(/\.[^/.]+$/, "");
        setDatasetName(name);
      }
      setErrorMessage(null);
      setSuccessMessage(null);
      setGeneratedDesc(null);
    }
  };

  const resetFileInput = () => {
    if (fileInputRef.current) {
      fileInputRef.current.value = "";
    }
    setFile(null);
  };

  const isCountLimitReached = maxUploadCount > 0 && currentCount >= maxUploadCount;

  const handleToggleShared = async (datasetId: string, newShared: boolean) => {
    try {
      const res = await apiFetch(`/api/datasets/${datasetId}/share`, {
        method: "PATCH",
        body: JSON.stringify({ shared: newShared }),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, DATASETS.share_error);
        throw new Error(errorMsg);
      }
      toast.success(newShared ? translate(DATASETS.shared) : translate(DATASETS.unshared));
      await fetchDatasets();
    } catch (error: any) {
      const msg = error.message || translate(DATASETS.share_error);
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const handleUpload = async () => {
    setErrorMessage(null);
    setSuccessMessage(null);
    setGeneratedDesc(null);

    if (isCountLimitReached) {
      const msg = translate(DATASET_UPLOAD.limit_reached_message).replace("{count}", String(maxUploadCount));
      setErrorMessage(msg);
      toast.error(msg, { duration: 8000 });
      return;
    }

    if (!file) {
      const msg = translate(DATASET_UPLOAD.no_file);
      setErrorMessage(msg);
      toast.error(msg, { duration: 5000 });
      return;
    }
    if (!datasetName.trim()) {
      const msg = translate(DATASET_UPLOAD.no_name);
      setErrorMessage(msg);
      toast.error(msg, { duration: 5000 });
      return;
    }

    setIsUploading(true);
    const formData = new FormData();
    formData.append("file", file);
    formData.append("name", datasetName);
    if (datasetDescription) {
      formData.append("description", datasetDescription);
    }
    formData.append("shared", shared ? "true" : "false");

    try {
      const token = await getToken();
      const res = await fetch(`/api/datasets/upload`, {
        method: "POST",
        headers: { "Authorization": `Bearer ${token}` },
        body: formData,
      });

      let errorData = null;
      let responseText = "";
      let rawText = "";
      try {
        rawText = await res.text();
        responseText = rawText;
        if (rawText) {
          errorData = JSON.parse(rawText);
        }
      } catch (parseErr) {
        responseText = rawText || translate(DATASET_UPLOAD.error);
      }

      if (!res.ok) {
        let errorMsg = translate(DATASET_UPLOAD.error);
        if (errorData) {
          if (errorData.detail) {
            errorMsg = errorData.detail;
          } else if (errorData.error) {
            const errorKey = errorData.error;
            const fallback = errorData.message || translate(DATASET_UPLOAD.error);
            try {
              const errorKeyObj = { key: errorKey, fallback: fallback };
              errorMsg = translate(errorKeyObj);
            } catch {
              errorMsg = fallback;
            }
          } else if (errorData.message) {
            errorMsg = errorData.message;
          }
        } else if (responseText) {
          errorMsg = responseText;
        }
        throw new Error(errorMsg);
      }

      const data = errorData || JSON.parse(responseText);
      const successMsg = translate(DATASET_UPLOAD.success).replace("{name}", datasetName);
      setSuccessMessage(successMsg);
      toast.success(successMsg, { duration: 8000 });
      await fetchDatasets();
      resetFileInput();
      if (data.dataset && data.dataset.id) {
        setSelectedDatasetId(data.dataset.id);
      }
    } catch (error: any) {
      const msg = error.message || translate(DATASET_UPLOAD.error);
      setErrorMessage(msg);
      toast.error(msg, { duration: 8000 });
    } finally {
      setIsUploading(false);
    }
  };

  // `timeoutOverride` is the control's value on a retry. Absent on a first attempt.
  const handleGenerateDescription = async (timeoutOverride?: number) => {
    if (!selectedDatasetId) {
      const msg = translate(DATASET_UPLOAD.select_dataset);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }
    if (selectedConnectionId === null) {
      const msg = translate(CHAT.select_connection_first);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }
    setIsGenerating(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    setGeneratedDesc(null);
    try {
      const conn = connections.find(c => c.id === selectedConnectionId);
      if (!conn) {
        throw new Error(translate(DATASET_UPLOAD.connection_not_found));
      }

      const payload: any = {
        connectionId: Number(conn.connectionId),
      };
      if (selectedModelCode && selectedModelCode.trim() !== "") {
        payload.model = selectedModelCode;
      }
      if (timeoutOverride !== undefined) {
        payload.timeoutSeconds = timeoutOverride;
      }

      const res = await apiFetch(`/api/datasets/${selectedDatasetId}/describe`, {
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
        // A timeout is the only failure a retry can fix, and only with more time. The
        // response says so machine-readably; the preset is computed from the timeout
        // that actually failed, not from whatever this request happened to ask for.
        if (errorData?.reason === "timeout" && typeof errorData?.timeoutSecondsUsed === "number") {
          const used = errorData.timeoutSecondsUsed;
          setEscalation(used);
          // 30% more, or +60 s, whichever is larger — the user's choice of escalation
          // step. Clamped to the backend ceiling so the control cannot preselect a value
          // the API will refuse.
          setEscalationValue(String(Math.min(ESCALATION_CEILING_SECONDS, Math.max(Math.ceil(used * 1.3), used + 60))));
        } else {
          setEscalation(null);
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, DATASETS.description.error);
        throw new Error(errorMsg);
      }

      const data = await res.json();
      const desc = data.description;
      if (!desc || desc.trim() === "") {
        throw new Error(translate(DATASETS.description.empty));
      }
      setGeneratedDesc(desc);
      // A success ends the episode: the control's job is done and its value is not
      // remembered, which is the whole point of a per-request escalation.
      setEscalation(null);
      const successMsg = translate(DATASETS.description.generated);
      setSuccessMessage(successMsg);
      toast.success(successMsg, { duration: 8000 });
    } catch (error: any) {
      const msg = error.message || translate(DATASETS.description.error);
      setErrorMessage(msg);
      toast.error(msg, { duration: 8000 });
    } finally {
      setIsGenerating(false);
    }
  };

  const handleDeleteDataset = async (id: string) => {
    if (!window.confirm(translate(DATASETS.delete.confirm))) return;
    try {
      const res = await apiFetch(`/api/datasets/${id}`, {
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
        const errorMsg = getErrorMessageFromData(translate, errorData, DATASETS.delete.error);
        throw new Error(errorMsg);
      }
      await fetchDatasets();
      if (selectedDatasetId === id) {
        setSelectedDatasetId(null);
        setGeneratedDesc(null);
      }
      const successMsg = translate(DATASETS.delete.success);
      setSuccessMessage(successMsg);
      toast.success(successMsg);
    } catch (error: any) {
      const msg = error.message || translate(DATASETS.delete.error);
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const isAdminUser = userRole?.isAdmin === true;
  const showSharedToggle = isAdminUser || (groupInfo && groupInfo.userGroup !== "00");

  if (!isLanguageLoaded || loadingConnections || loadingGroupInfo || loadingRole) {
    return <div className="flex items-center justify-center h-64">{translate(COMMON.loading)}</div>;
  }

  // If Example User, show read-only view
  if (isExampleUser) {
    return (
      <div className="max-w-6xl mx-auto py-6 space-y-4 flex flex-col md:flex-row gap-6 h-auto md:h-[calc(100vh-100px)]">
        <div className="w-full md:w-64 md:flex-shrink-0 h-auto md:h-full overflow-y-auto">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold">{translate(DATASET_UPLOAD.history)}</h2>
          </div>
          <div className="h-[calc(100%-40px)] overflow-y-auto border rounded-md p-2">
            {datasets.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-4">{translate(DATASET_UPLOAD.no_datasets)}</p>
            ) : (
              datasets.map((ds) => {
                const isShared = ds.isShared === true;
                const isOwn = ds.isOwn !== undefined ? ds.isOwn : true;

                return (
                  <div
                    key={ds.id}
                    className={`p-2 rounded-md cursor-pointer hover:bg-muted transition-colors ${
                      ds.id === selectedDatasetId ? "bg-muted" : ""
                    } opacity-60`}
                    onClick={() => setSelectedDatasetId(ds.id)}
                  >
                    <div className="flex items-center justify-between">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          <span className="text-sm truncate">{ds.name}</span>
                          {isShared && (
                            <span className="text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded">
                              {translate(DATASETS.shared_badge)}
                            </span>
                          )}
                        </div>
                        {ds.filePath && (
                          <span className="text-xs text-muted-foreground truncate block">{ds.filePath}</span>
                        )}
                        <span className="text-xs text-muted-foreground">
                          {formatDateTime(ds.createdAt)}
                        </span>
                      </div>
                    </div>
                  </div>
                );
              })
            )}
          </div>
        </div>

        <div className="flex-1 flex flex-col min-w-0 h-full">
          <h1 className="text-3xl font-bold mb-4">{translate(DATASET_UPLOAD.title)}</h1>

          <div className="p-6 bg-orange-50 border border-orange-200 rounded-md text-orange-800 text-center mb-4">
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
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
              <span className="text-sm">{errorMessage}</span>
              <button
                onClick={dismissError}
                className="text-red-500 hover:text-red-700"
                aria-label={translate(COMMON.dismiss)}
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>
          )}

          {successMessage && (
            <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md text-green-800 flex items-center justify-between">
              <span className="text-sm">{successMessage}</span>
              <button
                onClick={dismissSuccess}
                className="text-green-500 hover:text-green-700"
                aria-label={translate(COMMON.dismiss)}
              >
                <CheckCircle className="h-5 w-5" />
              </button>
            </div>
          )}

          <Card className="flex-1 flex flex-col min-h-0 overflow-hidden opacity-60">
            <CardHeader className="pb-2 flex-shrink-0">
              <CardTitle>{translate(DATASET_UPLOAD.card_title)}</CardTitle>
            </CardHeader>
            <CardContent className="flex-1 flex flex-col overflow-hidden p-4 pt-0">
              <div className="flex-1 overflow-y-auto space-y-4">
                <div className="space-y-2">
                  <Label>{translate(DATASET_UPLOAD.name_label)}</Label>
                  <Input dir="auto" value={datasetName} disabled />
                </div>
                <div className="space-y-2">
                  <Label>{translate(DATASET_UPLOAD.description_label)}</Label>
                  <Input dir="auto" value={datasetDescription} disabled />
                </div>
                <div className="space-y-2">
                  <Label>{translate(DATASET_UPLOAD.file_label)}</Label>
                  <Input dir="ltr" type="file" disabled />
                </div>

                {showSharedToggle && (
                  <div className="flex items-center justify-between p-3 bg-muted/30 rounded-md border border-muted opacity-60">
                    <div>
                      <Label>{translate(DATASET_UPLOAD.shared_label)}</Label>
                      <p className="text-sm text-muted-foreground">
                        {translate(DATASET_UPLOAD.shared_description)}
                      </p>
                    </div>
                    <Switch checked={shared} disabled />
                  </div>
                )}

                <div className="flex flex-wrap items-center gap-4 opacity-60">
                  <div className="w-full md:w-64">
                    <Label>{translate(CHAT.select_connection)}</Label>
                    <Select value={selectedConnectionId || ""} disabled>
                      <SelectTrigger>
                        <SelectValue placeholder={translate(CHAT.select_connection_placeholder)} />
                      </SelectTrigger>
                    </Select>
                  </div>
                  <div className="w-full md:w-64">
                    <Label>{translate(CHAT.select_model)}</Label>
                    <Select value={selectedModelCode || ""} disabled>
                      <SelectTrigger>
                        <SelectValue placeholder={translate(CHAT.select_model_placeholder)} />
                      </SelectTrigger>
                    </Select>
                  </div>
                </div>

                <div className="flex gap-4 opacity-60">
                  <Button disabled>
                    {translate(DATASET_UPLOAD.upload_button)}
                  </Button>
                  <Button disabled>
                    {translate(DATASET_UPLOAD.generate_description)}
                  </Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    );
  }

  // Normal user view - full access
  if (connections.length === 0) {
    return (
      <div className="max-w-lg mx-auto py-12">
        <Card>
          <CardHeader>
            <CardTitle>{translate(DATASET_UPLOAD.title)}</CardTitle>
          </CardHeader>
          <CardContent>
            <p className="text-muted-foreground">
              {translate(DATASET_UPLOAD.no_connections)}
            </p>
            <Button onClick={() => router.push("/settings/ai")} className="mt-4 w-full">
              {translate(CHAT.go_to_ai_settings)}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto py-6 space-y-4 flex flex-col md:flex-row gap-6 h-auto md:h-[calc(100vh-100px)]">
      <div className="w-full md:w-64 md:flex-shrink-0 h-auto md:h-full overflow-y-auto">
        <div className="flex items-center justify-between mb-4">
          <h2 className="text-lg font-semibold">{translate(DATASET_UPLOAD.history)}</h2>
        </div>
        <div className="h-[calc(100%-40px)] overflow-y-auto border rounded-md p-2">
          {datasets.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-4">{translate(DATASET_UPLOAD.no_datasets)}</p>
          ) : (
            datasets.map((ds) => {
              const isShared = ds.isShared === true;
              const isOwn = ds.isOwn !== undefined ? ds.isOwn : true;

              return (
                <div
                  key={ds.id}
                  className={`p-2 rounded-md cursor-pointer hover:bg-muted transition-colors ${
                    ds.id === selectedDatasetId ? "bg-muted" : ""
                  }`}
                  onClick={() => setSelectedDatasetId(ds.id)}
                >
                  <div className="flex items-center justify-between">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2">
                        <span className="text-sm truncate">{ds.name}</span>
                        {isShared && (
                          <span className="text-xs bg-green-100 text-green-800 px-1.5 py-0.5 rounded">
                            {translate(DATASETS.shared_badge)}
                          </span>
                        )}
                      </div>
                      {ds.filePath && (
                        <span className="text-xs text-muted-foreground truncate block">{ds.filePath}</span>
                      )}
                      <span className="text-xs text-muted-foreground">
                        {formatDateTime(ds.createdAt)}
                      </span>
                    </div>
                    <div className="flex items-center gap-1 flex-shrink-0">
                      {isOwn && (
                        <div className="flex items-center gap-1" onClick={(e) => e.stopPropagation()}>
                          <Switch
                            checked={isShared === true}
                            onCheckedChange={() => handleToggleShared(ds.id, !isShared)}
                            className="scale-75"
                            title={isShared ? translate(DATASETS.unshare) : translate(DATASETS.share)}
                          />
                        </div>
                      )}
                      {isOwn && (
                        <button
                          onClick={(e) => { e.stopPropagation(); handleDeleteDataset(ds.id); }}
                          className="text-muted-foreground hover:text-destructive p-0.5"
                          title={translate(DATASETS.delete.title)}
                        >
                          <Trash2 className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>

      <div className="flex-1 flex flex-col min-w-0 h-full">
        <h1 className="text-3xl font-bold mb-4">{translate(DATASET_UPLOAD.title)}</h1>

        {errorMessage && (
          <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
            <span className="text-sm">{errorMessage}</span>
            <button
              onClick={dismissError}
              className="text-red-500 hover:text-red-700"
              aria-label={translate(COMMON.dismiss)}
            >
              <XCircle className="h-5 w-5" />
            </button>
          </div>
        )}

        {successMessage && (
          <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md text-green-800 flex items-center justify-between">
            <span className="text-sm">{successMessage}</span>
            <button
              onClick={dismissSuccess}
              className="text-green-500 hover:text-green-700"
              aria-label={translate(COMMON.dismiss)}
            >
              <CheckCircle className="h-5 w-5" />
            </button>
          </div>
        )}

        <Card className="flex-1 flex flex-col min-h-0 overflow-hidden">
          <CardHeader className="pb-2 flex-shrink-0">
            <CardTitle>{translate(DATASET_UPLOAD.card_title)}</CardTitle>
          </CardHeader>
          <CardContent className="flex-1 flex flex-col overflow-hidden p-4 pt-0">
            <div className="flex-1 overflow-y-auto space-y-4">
              <div className="space-y-2">
                <Label htmlFor="datasetName">{translate(DATASET_UPLOAD.name_label)}</Label>
                <div className="relative flex items-center">
                  <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                  <Input dir="auto"
                    id="datasetName"
                    value={datasetName}
                    onChange={(e) => setDatasetName(e.target.value)}
                    placeholder={translate(DATASET_UPLOAD.name_placeholder)}
                    className="flex-1"
                  />
                </div>
              </div>
              <div className="space-y-2">
                <Label htmlFor="description">{translate(DATASET_UPLOAD.description_label)}</Label>
                <Input dir="auto"
                  id="description"
                  value={datasetDescription}
                  onChange={(e) => setDatasetDescription(e.target.value)}
                  placeholder={translate(DATASET_UPLOAD.description_placeholder)}
                />
              </div>
              <div className="space-y-2">
                <Label htmlFor="file">{translate(DATASET_UPLOAD.file_label)}</Label>
                <div className="relative flex items-center">
                  <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                  <Input dir="ltr"
                    id="file"
                    type="file"
                    accept=".csv,.xlsx,.xls"
                    onChange={handleFileChange}
                    ref={fileInputRef}
                    className="flex-1"
                  />
                </div>
                {file && (
                  <p className="text-sm text-muted-foreground">
                    {translate(DATASET_UPLOAD.file_selected)}: {file.name} ({(file.size / 1024).toFixed(1)} KB)
                  </p>
                )}
              </div>

              {showSharedToggle && (
                <div className="flex items-center justify-between p-3 bg-muted/30 rounded-md border border-muted">
                  <div>
                    <Label>{translate(DATASET_UPLOAD.shared_label)}</Label>
                    <p className="text-sm text-muted-foreground">
                      {translate(DATASET_UPLOAD.shared_description)}
                    </p>
                    {groupInfo && (
                      <p className="text-xs text-muted-foreground mt-1">
                        {translate(DATASET_UPLOAD.shared_group_hint)
                          .replace("{group}", groupInfo.userGroup)
                          .replace("{description}", groupInfo.groupDescription)}
                      </p>
                    )}
                  </div>
                  <Switch
                    checked={shared}
                    onCheckedChange={(checked) => setShared(checked)}
                  />
                </div>
              )}

              <div className="flex flex-wrap items-center gap-4">
                <div className="w-full md:w-64">
                  <Label htmlFor="connection-select">{translate(CHAT.select_connection)}</Label>
                  <div className="relative flex items-center">
                    <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                    <Select
                      value={selectedConnectionId || ""}
                      onValueChange={(val) => {
                        if (val !== null) setSelectedConnectionId(val);
                      }}
                    >
                      <SelectTrigger className="flex-1">
                        <SelectValue placeholder={translate(CHAT.select_connection_placeholder)}>
                          {selectedConnectionId !== null ? getConnectionLabel(connections.find(c => c.id === selectedConnectionId)!) : ""}
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        {connections.map((conn) => {
                          const label = getConnectionLabel(conn);
                          return (
                            <SelectItem key={conn.id} value={conn.id}>
                              {label}
                            </SelectItem>
                          );
                        })}
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                <div className="w-full md:w-64">
                  <Label htmlFor="model-select">{translate(CHAT.select_model)}</Label>
                  <div className="relative flex items-center">
                    <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                    <Select
                      value={selectedModelCode || ""}
                      onValueChange={(val) => {
                        if (val !== null) setSelectedModelCode(val);
                      }}
                      disabled={loadingModels || models.length === 0}
                    >
                      <SelectTrigger className="flex-1">
                        <SelectValue placeholder={translate(CHAT.select_model_placeholder)}>
                          {selectedModelCode ? models.find(m => m.modelCode === selectedModelCode)?.modelName || selectedModelCode : ""}
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent className="min-w-[200px]">
                        {models.map((model) => (
                          <SelectItem key={model.id} value={model.modelCode}>
                            {model.modelName} ({model.modelCode})
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  {loadingModels && <p className="text-xs text-muted-foreground mt-1">{translate(COMMON.loading)}</p>}
                  {!loadingModels && models.length === 0 && (
                    <p className="text-xs text-muted-foreground mt-1">{translate(CHAT.no_models)}</p>
                  )}
                </div>
              </div>

              <div className="flex gap-4">
                <Button onClick={handleUpload} disabled={isUploading || isGenerating || isCountLimitReached}>
                  {isUploading ? (
                    <Loader2 className="me-2 h-4 w-4 animate-spin" />
                  ) : (
                    <Upload className="me-2 h-4 w-4" />
                  )}
                  {isCountLimitReached
                    ? translate(DATASET_UPLOAD.limit_reached)
                    : isUploading
                    ? translate(COMMON.uploading)
                    : translate(DATASET_UPLOAD.upload_button)}
                </Button>
                {/* Wrapped: the handler now takes an optional number, and passing it directly would
                    hand it the MouseEvent as that value. */}
                <Button onClick={() => handleGenerateDescription()} disabled={isGenerating || !selectedDatasetId || selectedConnectionId === null}>
                  {isGenerating ? (
                    <Loader2 className="me-2 h-4 w-4 animate-spin" />
                  ) : (
                    <FileText className="me-2 h-4 w-4" />
                  )}
                  {isGenerating ? translate(COMMON.generating) : translate(DATASET_UPLOAD.generate_description)}
                </Button>
              </div>

              {/* The escalation control (Item 12 / D6). Shown ONLY after a describe call
                  timed out — `escalation` is null otherwise, so it cannot be reached by
                  someone who has not just waited for a failure. Beside the persistent error
                  banner rather than in a dialog: the message and the remedy read together. */}
              {escalation !== null && (
                <div className="mt-4 p-4 border rounded-md bg-muted/20">
                  <p className="text-sm mb-2">
                    {translate(DATASET_UPLOAD.escalation_failed_at).replace("{seconds}", String(escalation))}
                  </p>
                  <div className="flex items-end gap-2 flex-wrap">
                    <div className="space-y-1">
                      <Label htmlFor="escalation-seconds">{translate(DATASET_UPLOAD.escalation_label)}</Label>
                      <div className="flex items-center gap-2">
                        <Input
                          id="escalation-seconds"
                          dir="ltr"
                          type="number"
                          min="1"
                          max={String(ESCALATION_CEILING_SECONDS)}
                          step="1"
                          value={escalationValue}
                          onChange={(e) => setEscalationValue(e.target.value)}
                          className="max-w-[120px]"
                        />
                      </div>
                    </div>
                    <Button
                      onClick={() => {
                        // Validate on click, never by disabling the button: an empty or
                        // out-of-range value gets a message, not a dead control.
                        const n = Number(escalationValue);
                        if (escalationValue.trim() === "" || !/^[0-9]+$/.test(escalationValue.trim())
                            || !Number.isInteger(n) || n < 1 || n > ESCALATION_CEILING_SECONDS) {
                          const msg = translate(DATASET_UPLOAD.escalation_invalid)
                            .replace("{max}", String(ESCALATION_CEILING_SECONDS));
                          setErrorMessage(msg);
                          toast.error(msg);
                          return;
                        }
                        handleGenerateDescription(n);
                      }}
                      disabled={isGenerating}
                    >
                      {isGenerating ? <Loader2 className="me-2 h-4 w-4 animate-spin" /> : null}
                      {translate(DATASET_UPLOAD.escalation_retry)}
                    </Button>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    {translate(DATASET_UPLOAD.escalation_hint)}
                  </p>
                </div>
              )}

              {isCountLimitReached && (
                <div className="p-4 bg-yellow-50 border border-yellow-200 rounded-md text-yellow-800">
                  {translate(DATASET_UPLOAD.limit_reached_message).replace("{count}", String(maxUploadCount))}
                </div>
              )}

              {generatedDesc && (
                <div className="mt-4">
                  <Label>{translate(DATASETS.description.title)}</Label>
                  <div className="p-4 bg-muted/30 rounded-md whitespace-pre-wrap text-sm mt-1">
                    {generatedDesc}
                  </div>
                  <div className="mt-2 flex gap-4">
                    <Button variant="outline" size="sm" onClick={() => navigator.clipboard.writeText(generatedDesc)}>
                      {translate(COMMON.copy)}
                    </Button>
                    <Button variant="outline" size="sm" onClick={() => setGeneratedDesc(null)}>
                      {translate(COMMON.clear)}
                    </Button>
                  </div>
                </div>
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}

// The backend's ceiling, duplicated with upload/page.tsx (see D6). If the backend's
// MAX_TIMEOUT_SECONDS changes, both change together — recorded in the plan's Notes.
const ESCALATION_CEILING_SECONDS = 1200;

export default function DatasetsPage() {
  return (
    <ProtectedRoute>
      <DatasetsListContent />
    </ProtectedRoute>
  );
}