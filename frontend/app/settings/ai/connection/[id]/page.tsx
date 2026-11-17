// frontend/app/settings/ai/connection/[id]/page.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter, useParams } from "next/navigation";
import { useForm } from "react-hook-form";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { ProtectedRoute } from "@/components/protected-route";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, useTranslateWithParams, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { useAI, AIProvider, AIConnection } from "@/lib/ai-context";
import { Eye, EyeOff } from "lucide-react";

// Import translations for this module
import { AI_CONNECTION_FORM } from "@/app/settings/ai/translations";
import { COMMON } from "@/app/common/translations";
import { VALIDATION } from "@/app/common/translations";

interface FormData {
  name: string;
  provider: AIProvider | "";
  apiKey: string;
  endpoint: string;
  shared: boolean;
  aiConnectionGroup: string;
  // The two connection timeouts (plan workbench-AI-timeout-policy-plan.html, Item 3).
  // Strings because they are form fields: an empty box is "inherit the workbench
  // default", which is what the API receives as null. A number type here would turn
  // the empty box into 0 and make "inherit" unreachable.
  connectTimeoutSeconds?: string;
  probeTimeoutSeconds?: string;
}

interface Model {
  id: number;
  modelCode: string;
  modelName: string;
  enabled: boolean;
}

interface ProviderMetadata {
  code: string;
  name: string;
  isLocal: boolean;
  requiresApiKey: boolean;
  defaultEndpoint: string | null;
}

interface GroupInfo {
  userGroup: string;
  groupDescription: string;
}

interface UserRole {
  isAdmin: boolean;
  isGroupAdmin: boolean;
  isExampleUser: boolean;
}

function AIConnectionFormContent() {
  const router = useRouter();
  const params = useParams();
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const translateWithParams = useTranslateWithParams();
  const { data: session } = useSession();
  const { connections, addConnection, updateConnection, loading: aiLoading } = useAI();
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showApiKey, setShowApiKey] = useState(false);
  const isInitialMount = useRef(true);
  const [demoMode, setDemoMode] = useState(false);
  const [loadingDemoMode, setLoadingDemoMode] = useState(true);
  const [models, setModels] = useState<Model[]>([]);
  const [providerMetadata, setProviderMetadata] = useState<ProviderMetadata | null>(null);
  const [providerMetadataError, setProviderMetadataError] = useState<string | null>(null);
  const [loadingProviderMetadata, setLoadingProviderMetadata] = useState(false);
  const [availableProviders, setAvailableProviders] = useState<ProviderMetadata[]>([]);
  const [loadingProviders, setLoadingProviders] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  const [groupInfo, setGroupInfo] = useState<GroupInfo | null>(null);
  const [loadingGroupInfo, setLoadingGroupInfo] = useState(true);
  const [availableGroups, setAvailableGroups] = useState<{groupId: string; groupDescription: string}[]>([]);

  // Fetched directly from the API when the AI context has not got the row.
  // The mirror of the database connection page's directConnection: the context
  // list is loaded once by AIProvider and can be empty or stale (a session that
  // predates a seed, a failed first fetch), and this page would otherwise report
  // "Connection not found" for a row the backend answers for.
  const [directConnection, setDirectConnection] = useState<AIConnection | null>(null);
  const [fetchingDirect, setFetchingDirect] = useState(false);

  // User role for Example User detection
  const [userRole, setUserRole] = useState<UserRole | null>(null);
  const [loadingRole, setLoadingRole] = useState(true);

  const id = params.id as string;
  const isNew = id === "new";
  const contextConnection = isNew ? null : connections.find(c => c.id === id || String(c.connectionId) === id);
  const existingConnection = contextConnection || directConnection;
  const isOwner = !existingConnection || existingConnection.userId === session?.user?.id;

  const isExampleUser = userRole?.isExampleUser === true;

  const {
    register,
    handleSubmit,
    setValue,
    watch,
    getValues,
    setError,
    clearErrors,
    formState: { errors },
  } = useForm<FormData>({
    defaultValues: {
      name: "",
      provider: "",
      apiKey: "",
      endpoint: "",
      shared: false,
      aiConnectionGroup: "00",
      connectTimeoutSeconds: "",
      probeTimeoutSeconds: "",
    },
  });

  const selectedProvider = watch("provider");
  const sharedValue = watch("shared");
  const requiresApiKey = providerMetadata?.requiresApiKey ?? false;

  // Fetch user role for Example User detection
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

  // Fetch group info for the current user
  useEffect(() => {
    const fetchGroupInfo = async () => {
      try {
        setLoadingGroupInfo(true);
        const res = await apiFetch(`/api/groups/user/me`);
        if (res.ok) {
          const data = await res.json();
          setGroupInfo({
            userGroup: data.user_group,
            groupDescription: data.group_description,
          });
        } else {
          console.error("Failed to fetch group info:", res.status);
        }
      } catch (error) {
        console.error("Failed to load group info:", error);
      } finally {
        setLoadingGroupInfo(false);
      }
    };
    if (session?.user?.id) {
      fetchGroupInfo();
    }
  }, [session?.user?.id]);

  // Fetch connection directly from API as fallback when context hasn't loaded it.
  //
  // Deliberately the same shape as the database connection page's fallback, so the
  // two settings pages answer the same way when the context list is short: ask the
  // endpoint that returns own rows plus rows shared to the user's group, and match
  // by either identifier the API sends. Without this, the detail page depended
  // entirely on one provider-level fetch that it does not control.
  useEffect(() => {
    if (isNew || directConnection || aiLoading) return;
    // Only fetch if the connection isn't already in context
    if (contextConnection) return;

    let cancelled = false;
    setFetchingDirect(true);
    apiFetch("/api/user/ai-connections/available")
      .then(res => res.ok ? res.json() : Promise.reject(res))
      .then(data => {
        if (cancelled) return;
        const found = (data.connections || []).find(
          (c: any) => c.id === id || String(c.connectionId) === id
        );
        if (found) setDirectConnection(found);
      })
      .catch(() => {})
      .finally(() => { if (!cancelled) setFetchingDirect(false); });

    return () => { cancelled = true; };
  }, [id, isNew, aiLoading, contextConnection, directConnection]);

  const isAdminUser = userRole?.isAdmin === true;

  // Who may edit this connection: its owner, or an administrator. Everyone else
  // sees it read-only. The backend enforces the same rule.
  const canManage = isOwner || isAdminUser;
  const showSharedToggle = isAdminUser || (groupInfo && groupInfo.userGroup !== "00");

  // Fetch all groups for admin dropdown
  useEffect(() => {
    if (!isAdminUser) return;
    const fetchGroups = async () => {
      try {
        const res = await apiFetch("/api/admin/groups");
        if (res.ok) {
          const data = await res.json();
          setAvailableGroups(data.groups || []);
        }
      } catch (e) { /* non-critical */ }
    };
    fetchGroups();
  }, [isAdminUser]);

  // Fetch enabled providers
  useEffect(() => {
    const fetchProviders = async () => {
      try {
        setLoadingProviders(true);
        const res = await fetch("/api/ai-providers");
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
          const errorMsg = getErrorMessageFromData(translate, errorData, AI_CONNECTION_FORM.load_providers_error);
          throw new Error(errorMsg);
        }
        const data = await res.json();
        let providers = data.providers || [];
        if (existingConnection) {
          const hasProvider = providers.some((p: ProviderMetadata) => p.code === existingConnection.provider);
          if (!hasProvider) {
            const allRes = await apiFetch("/api/admin/ai-providers");
            if (allRes.ok) {
              const allData = await allRes.json();
              const found = allData.providers.find((p: ProviderMetadata) => p.code === existingConnection.provider);
              if (found) {
                providers = [found, ...providers];
              }
            }
          }
        }
        setAvailableProviders(providers);
      } catch (error: any) {
        console.error("Error fetching providers:", error);
        const msg = error.message || translate(AI_CONNECTION_FORM.load_providers_error);
        setErrorMessage(msg);
        toast.error(msg);
      } finally {
        setLoadingProviders(false);
      }
    };
    fetchProviders();
  }, [existingConnection]);

  // Fetch provider metadata
  useEffect(() => {
    if (!selectedProvider) {
      setProviderMetadata(null);
      setProviderMetadataError(null);
      setLoadingProviderMetadata(false);
      return;
    }
    const found = availableProviders.find((p) => p.code === selectedProvider);
    if (found) {
      setProviderMetadata(found);
      setProviderMetadataError(null);
      setLoadingProviderMetadata(false);
    } else {
      setLoadingProviderMetadata(true);
      fetch("/api/ai-providers")
        .then(res => res.json())
        .then(data => {
          const p = data.providers.find((p: ProviderMetadata) => p.code === selectedProvider);
          if (p) {
            setProviderMetadata(p);
            setProviderMetadataError(null);
          } else {
            setProviderMetadataError(`${translate(AI_CONNECTION_FORM.provider_not_found)}: ${selectedProvider}`);
          }
        })
        .catch(err => {
          setProviderMetadataError(err.message || translate(AI_CONNECTION_FORM.metadata_load_error));
        })
        .finally(() => setLoadingProviderMetadata(false));
    }
  }, [selectedProvider, availableProviders]);

  // Fetch demo mode status
  useEffect(() => {
    apiFetch("/api/global-settings")
      .then(res => res.json())
      .then(data => setDemoMode(data.demoMode === true))
      .catch(console.error)
      .finally(() => setLoadingDemoMode(false));
  }, []);

  // Load existing connection data when editing
  useEffect(() => {
    if (existingConnection) {
      setValue("name", existingConnection.name);
      setValue("provider", existingConnection.provider);
      setValue("apiKey", existingConnection.apiKey || "");
      setValue("endpoint", existingConnection.endpoint || "");
      const isShared = existingConnection.isShared === true;
      setValue("shared", isShared);
      setValue("aiConnectionGroup", existingConnection.aiConnectionGroup || "00");
      // Blank, not the resolved default: an inherited value must not read as though
      // the administrator had set it. The same rule Item 10 of the AI-limits plan
      // applied to pair tuning.
      setValue("connectTimeoutSeconds",
        existingConnection.connectTimeoutSeconds == null ? "" : String(existingConnection.connectTimeoutSeconds));
      setValue("probeTimeoutSeconds",
        existingConnection.probeTimeoutSeconds == null ? "" : String(existingConnection.probeTimeoutSeconds));
      if (existingConnection.id) {
        fetchModels(existingConnection.id);
      }
    }
    setTimeout(() => {
      isInitialMount.current = false;
    }, 100);
  }, [existingConnection, setValue]);

  // Auto-fill endpoint when provider changes
  useEffect(() => {
    if (isInitialMount.current) return;
    if (!isNew) return;

    const defaultEndpoint = providerMetadata?.defaultEndpoint || "";

    if (defaultEndpoint) {
      setValue("endpoint", defaultEndpoint);
    }
  }, [selectedProvider, providerMetadata, setValue, isNew]);

  const fetchModels = async (connectionId: string) => {
    try {
      const res = await apiFetch(`/api/user/ai-connections/${connectionId}/models`);
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
        const errorMsg = getErrorMessageFromData(translate, errorData, AI_CONNECTION_FORM.models_load_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      setModels(data.models || []);
    } catch (error: any) {
      console.error("Error fetching models:", error);
      const msg = error.message || translate(AI_CONNECTION_FORM.models_load_error);
      setErrorMessage(msg);
      toast.error(msg);
      setModels([]);
    }
  };

  const syncModels = async (connectionId: string) => {
    try {
      // DISCOVER, not FETCH (plan Item 31). The old route refreshed a provider-wide
      // catalogue keyed by provider code, so a refresh here could delete another
      // host's rows; this one asks THIS server and records against this connection.
      const res = await apiFetch(`/api/user/ai-connections/${connectionId}/models/discover`, {
        method: "POST",
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
        const errorMsg = getErrorMessageFromData(translate, errorData, AI_CONNECTION_FORM.models_sync_error);
        throw new Error(errorMsg);
      }
      // Discovery returns COUNTS, not a model list — the list is a different read.
      // Re-reading it through the loader the page already has keeps one shape of
      // "what models does this connection serve" instead of two.
      const result = await res.json().catch(() => ({}));
      await fetchModels(connectionId);
      toast.success(
        translateWithParams(
          AI_CONNECTION_FORM.models_discovered.key,
          AI_CONNECTION_FORM.models_discovered.fallback,
          {
            seen: result.modelsSeen ?? 0,
            created: result.connectionModelsCreated ?? 0,
            refreshed: result.connectionModelsRefreshed ?? 0,
            pruned: result.connectionModelsPruned ?? 0,
          },
        ),
      );
    } catch (error: any) {
      const msg = error.message || translate(AI_CONNECTION_FORM.models_sync_error);
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const runTest = async (values: FormData): Promise<boolean> => {
    if (!values.provider) {
      toast.error(translate(AI_CONNECTION_FORM.select_provider_first));
      return false;
    }
    setIsTesting(true);
    setTestResult(null);
    setErrorMessage(null);
    try {
      const response = await fetch("/api/test-ai", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          provider: values.provider,
          apiKey: values.apiKey,
          endpoint: values.endpoint,
        }),
      });
      
      if (!response.ok) {
        let errorData: any = {};
        try {
          const text = await response.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, AI_CONNECTION_FORM.test_error);
        setTestResult({ success: false, message: errorMsg });
        toast.error(errorMsg);
        return false;
      }
      
      const data = await response.json();
      if (data.success) {
        const successMsg = data.message || translate(AI_CONNECTION_FORM.test_success);
        setTestResult({ success: true, message: successMsg });
        toast.success(successMsg);
        return true;
      } else {
        const errorMsg = data.error || translate(AI_CONNECTION_FORM.test_error);
        setTestResult({ success: false, message: errorMsg });
        toast.error(errorMsg);
        return false;
      }
    } catch (error: any) {
      const errorMsg = error.message || translate(AI_CONNECTION_FORM.test_error);
      setTestResult({ success: false, message: errorMsg });
      toast.error(errorMsg);
      return false;
    } finally {
      setIsTesting(false);
    }
  };

  const validateForm = (data: FormData): boolean => {
    let isValid = true;
    clearErrors();

    if (!data.name.trim()) {
      setError("name", { message: translate(VALIDATION.name_required) });
      isValid = false;
    }
    if (!data.provider) {
      setError("provider", { message: translate(VALIDATION.provider_required) });
      isValid = false;
    }
    if (requiresApiKey && !data.apiKey) {
      setError("apiKey", { message: translate(VALIDATION.api_key_required) });
      isValid = false;
    }
    // The two timeouts. Blank is legal and means "inherit" — only a non-empty value
    // is range-checked. Validate, don't coerce: a decimal is refused rather than
    // truncated, and the box is never disabled, so a wrong value is attemptable and
    // answered with a persistent message rather than prevented.
    for (const [field, ceiling, key] of [
      ["connectTimeoutSeconds", 60, AI_CONNECTION_FORM.invalid_connect_timeout],
      ["probeTimeoutSeconds", 1200, AI_CONNECTION_FORM.invalid_probe_timeout],
    ] as const) {
      const raw = (data as any)[field] as string | undefined;
      const trimmed = (raw ?? "").trim();
      if (trimmed === "") continue;
      const n = Number(trimmed);
      if (!/^[0-9]+$/.test(trimmed) || !Number.isInteger(n) || n < 1 || n > ceiling) {
        setError(field as any, { message: translate(key) });
        isValid = false;
      }
    }
    // The same cross-check the backend makes, so the administrator is told before a
    // round trip. The backend still refuses independently — this is the earlier
    // answer, not the only one, because the stored pair can become invalid without a
    // write to refuse it.
    const connectRaw = (data.connectTimeoutSeconds ?? "").trim();
    const probeRaw = (data.probeTimeoutSeconds ?? "").trim();
    if (connectRaw !== "" && probeRaw !== "") {
      if (Number(connectRaw) > Number(probeRaw)) {
        setError("connectTimeoutSeconds", {
          message: translate(AI_CONNECTION_FORM.connect_exceeds_probe),
        });
        isValid = false;
      }
    }
    return isValid;
  };

  const onTest = async () => {
    const values = getValues();
    await runTest(values);
  };

  const onSubmit = async (data: FormData) => {
    if (!providerMetadata && selectedProvider) {
      toast.error(translate(AI_CONNECTION_FORM.metadata_loading));
      return;
    }
    if (providerMetadataError) {
      toast.error(providerMetadataError);
      return;
    }

    if (!validateForm(data)) return;

    const testPassed = await runTest(data);
    if (!testPassed) {
      return;
    }

    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const payload = {
        name: data.name,
        provider: data.provider as AIProvider,
        apiKey: data.apiKey || null,
        endpoint: data.endpoint || null,
        shared: data.shared,
        aiConnectionGroup: data.shared ? data.aiConnectionGroup : "00",
        // Blank goes as null, which is "inherit" — an explicit null clears a stored
        // value, and the backend distinguishes it from an absent field.
        connectTimeoutSeconds: (data.connectTimeoutSeconds ?? "").trim() === ""
          ? null : Number(data.connectTimeoutSeconds),
        probeTimeoutSeconds: (data.probeTimeoutSeconds ?? "").trim() === ""
          ? null : Number(data.probeTimeoutSeconds),
      };
      let savedConnection;
      if (isNew) {
        savedConnection = await addConnection(payload);
        toast.success(translate(AI_CONNECTION_FORM.add_success));
      } else if (existingConnection) {
        await updateConnection(existingConnection.id, payload);
        savedConnection = existingConnection;
        toast.success(translate(AI_CONNECTION_FORM.update_success));
      }

      if (savedConnection && savedConnection.id) {
        await syncModels(savedConnection.id);
      }

      router.push("/settings/ai");
    } catch (error: any) {
      const msg = error.message || translate(AI_CONNECTION_FORM.save_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const handleCancel = () => {
    router.push("/settings/ai");
  };

  const dismissError = () => setErrorMessage(null);

  if (aiLoading || fetchingDirect || loadingDemoMode || loadingGroupInfo || loadingRole) {
    return <div className="max-w-lg mx-auto py-8">{translate(COMMON.loading)}</div>;
  }

  if (!isNew && !existingConnection && !aiLoading) {
    return (
      <div className="max-w-lg mx-auto py-8">
        <Card>
          <CardContent className="pt-6">
            <p className="text-center text-red-500">{translate(AI_CONNECTION_FORM.not_found)}</p>
            <Button className="mt-4 w-full" onClick={handleCancel}>
              {translate(COMMON.back)}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const isLocalSelected = selectedProvider === "ollama-local";
  const saveDisabled = isSubmitting || (demoMode && isLocalSelected) || loadingProviderMetadata || !!providerMetadataError || loadingProviders || isExampleUser || !canManage;
  const testDisabled = isTesting || !selectedProvider || loadingProviderMetadata || !!providerMetadataError || loadingProviders || isExampleUser || !canManage;

  const isCurrentlyShared = existingConnection 
    ? existingConnection.isShared === true
    : false;

  return (
    <div className="max-w-lg mx-auto py-8">
      <Card>
        <CardHeader>
          <CardTitle>
            {isNew ? translate(AI_CONNECTION_FORM.add_title) : translate(AI_CONNECTION_FORM.edit_title)}
          </CardTitle>
          <CardDescription>
            {translate(AI_CONNECTION_FORM.form_description)}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {errorMessage && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
              <span className="text-sm">{errorMessage}</span>
              <button
                onClick={dismissError}
                className="text-red-500 hover:text-red-700"
                aria-label={translate(COMMON.dismiss)}
              >
                <span className="text-xl">&times;</span>
              </button>
            </div>
          )}
          {!isNew && !canManage && existingConnection && (
            <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md text-blue-800 text-sm">
              {translate(AI_CONNECTION_FORM.shared_readonly_message)}
            </div>
          )}
 
          {/* autoComplete="off" on the form and on every field: this page has a
              text input (the probe timeout) immediately before a type="password"
              field (the API key), which is the shape browsers use to identify a
              login form. Without these, Firefox filled the saved Workbench login
              into the timeout slot and the saved password into the API key — which
              would then have been stored as a provider credential. Measured on the
              installed .deb, 2026-11-11; the source is identical in dev. */}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" autoComplete="off">
            <div className="space-y-2">
              <Label htmlFor="name">{translate(AI_CONNECTION_FORM.name_label)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="auto"
                  id="name"
                  autoComplete="off"
                  {...register("name")}
                  placeholder={translate(AI_CONNECTION_FORM.name_placeholder)}
                  className="flex-1"
                  disabled={isExampleUser}
                />
              </div>
              {errors.name && <p className="text-sm text-red-500">{errors.name.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="provider">{translate(AI_CONNECTION_FORM.provider_label)}</Label>
              {isNew ? (
                loadingProviders ? (
                  <p className="text-sm text-muted-foreground">{translate(COMMON.loading)}</p>
                ) : (
                  <div className="relative flex items-center">
                    <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                    <Select
                      value={selectedProvider}
                      onValueChange={(val) => {
                        if (val !== null) setValue("provider", val);
                      }}
                      disabled={isExampleUser}
                    >
                      <SelectTrigger className="flex-1">
                        <SelectValue placeholder={translate(AI_CONNECTION_FORM.select_provider)}>
                          {selectedProvider ? (providerMetadata?.name || selectedProvider) : ""}
                        </SelectValue>
                      </SelectTrigger>
                      <SelectContent>
                        {availableProviders.map((p) => (
                          <SelectItem key={p.code} value={p.code}>
                            {p.name}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                )
              ) : (
                <div className="flex h-8 w-full items-center rounded-md border border-input bg-muted px-3 text-sm text-muted-foreground">
                  {providerMetadata?.name || selectedProvider || translate(COMMON.loading)}
                </div>
              )}
              {errors.provider && <p className="text-sm text-red-500">{errors.provider.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="endpoint">{translate(AI_CONNECTION_FORM.endpoint_label)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="ltr"
                  id="endpoint"
                  autoComplete="off"
                  {...register("endpoint")}
                  placeholder="https://api.deepseek.com/v1"
                  className="flex-1"
                  disabled={isExampleUser}
                />
              </div>
              <p className="text-xs text-muted-foreground">
                {translate(AI_CONNECTION_FORM.endpoint_hint)}
              </p>
              {errors.endpoint && <p className="text-sm text-red-500">{errors.endpoint.message}</p>}
            </div>

            {/* The two connection timeouts (plan Item 3). Blank inherits the workbench
                default, which is why neither box is prefilled with the resolved value:
                an inherited number shown as though typed is the misreading Item 10 of
                the AI-limits plan exists to prevent. */}
            <div className="pt-2">
              <h3 className="text-sm font-semibold">{translate(AI_CONNECTION_FORM.timeouts_section_label)}</h3>
              <p className="text-xs text-muted-foreground mt-1">{translate(AI_CONNECTION_FORM.timeouts_section_hint)}</p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="connectTimeoutSeconds">{translate(COMMON.connect_timeout_label)}</Label>
              <div className="flex items-center gap-2">
                <Input dir="ltr"
                  id="connectTimeoutSeconds"
                  autoComplete="off"
                  type="number"
                  min="1"
                  max="60"
                  step="1"
                  placeholder="10"
                  {...register("connectTimeoutSeconds")}
                  className="max-w-[140px]"
                  disabled={isExampleUser}
                />
              </div>
              <p className="text-xs text-muted-foreground">{translate(AI_CONNECTION_FORM.connect_timeout_hint)}</p>
              {errors.connectTimeoutSeconds && <p className="text-sm text-red-500">{errors.connectTimeoutSeconds.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="probeTimeoutSeconds">{translate(COMMON.probe_timeout_label)}</Label>
              <div className="flex items-center gap-2">
                <Input dir="ltr"
                  id="probeTimeoutSeconds"
                  autoComplete="off"
                  type="number"
                  min="1"
                  max="1200"
                  step="1"
                  placeholder="300"
                  {...register("probeTimeoutSeconds")}
                  className="max-w-[140px]"
                  disabled={isExampleUser}
                />
              </div>
              <p className="text-xs text-muted-foreground">{translate(AI_CONNECTION_FORM.probe_timeout_hint)}</p>
              {errors.probeTimeoutSeconds && <p className="text-sm text-red-500">{errors.probeTimeoutSeconds.message}</p>}
            </div>

            {requiresApiKey && (
              <div className="space-y-2">
                <Label htmlFor="apiKey">{translate(AI_CONNECTION_FORM.api_key_label)}</Label>
                <div className="relative flex items-center">
                  <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                  <Input dir="ltr"
                    id="apiKey"
                    type={showApiKey ? "text" : "password"}
                    autoComplete="new-password"
                    {...register("apiKey")}
                    placeholder="sk-..."
                    className="flex-1 pe-10"
                    disabled={isExampleUser}
                  />
                  {!isExampleUser ? (
                    <button
                      type="button"
                      onClick={() => setShowApiKey(!showApiKey)}
                      disabled={!canManage}
                      className="absolute inset-y-0 end-0 z-10 flex items-center pe-3 text-muted-foreground hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:text-muted-foreground"
                      tabIndex={-1}
                    >
                      {showApiKey ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                    </button>
                  ) : (
                    <span className="absolute inset-y-0 end-0 z-10 flex items-center pe-3 text-xs text-muted-foreground">
                      🔒
                    </span>
                  )}
                </div>
                <p className="text-xs text-muted-foreground">
                  {translate(AI_CONNECTION_FORM.api_key_hint)}
                </p>
                {errors.apiKey && <p className="text-sm text-red-500">{errors.apiKey.message}</p>}
              </div>
            )}

            {showSharedToggle && (
              <div className="flex items-center justify-between p-3 bg-muted/30 rounded-md border border-muted">
                <div>
                  <Label>
                    {translate(AI_CONNECTION_FORM.shared_label)}
                    {!isAdminUser && groupInfo && (
                      <span className="text-muted-foreground font-normal ms-1">
                        ({groupInfo.userGroup}{groupInfo.groupDescription ? ` \u2014 ${groupInfo.groupDescription}` : ''})
                      </span>
                    )}
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    {translate(AI_CONNECTION_FORM.shared_description)}
                  </p>
                  {!isNew && (
                    <p className="text-xs font-medium mt-1">
                      {isCurrentlyShared 
                        ? translate(AI_CONNECTION_FORM.currently_shared)
                        : translate(AI_CONNECTION_FORM.currently_not_shared)}
                    </p>
                  )}
                  {isAdminUser && availableGroups.length > 0 && (
                    <div className="mt-2">
                      <Label className="text-xs">{translate(AI_CONNECTION_FORM.group_label)}</Label>
                      <Select
                        value={watch("aiConnectionGroup")}
                        onValueChange={(val) => setValue("aiConnectionGroup", val || "00")}
                      >
                        <SelectTrigger className="mt-1 h-8 text-xs">
                          <SelectValue>
                            {(value: string) => {
                              const group = availableGroups.find(g => g.groupId === value);
                              return group && group.groupDescription
                                ? `${group.groupId} — ${group.groupDescription}`
                                : value;
                            }}
                          </SelectValue>
                        </SelectTrigger>
                        <SelectContent>
                          {availableGroups.map((g) => (
                            <SelectItem key={g.groupId} value={g.groupId}>
                              {g.groupId}{g.groupDescription ? ` — ${g.groupDescription}` : ""}
                            </SelectItem>
                          ))}
                        </SelectContent>
                      </Select>
                    </div>
                  )}
                </div>
                <Switch
                  checked={sharedValue}
                  onCheckedChange={(checked) => setValue("shared", checked)}
                  disabled={isExampleUser}
                />
              </div>
            )}

            {testResult && (
              <div
                className={`p-3 rounded-md text-sm ${
                  testResult.success
                    ? "bg-green-50 text-green-800 border border-green-200"
                    : "bg-red-50 text-red-800 border border-red-200"
                }`}
              >
                {testResult.message}
              </div>
            )}

            <div className="flex gap-4 flex-wrap">
              <Button type="button" variant="outline" onClick={onTest} disabled={testDisabled}>
                {isTesting ? translate(COMMON.testing) : translate(AI_CONNECTION_FORM.test_button)}
              </Button>
              <Button type="submit" disabled={saveDisabled}>
                {isSubmitting ? translate(COMMON.saving) : translate(COMMON.save)}
              </Button>
              <Button type="button" variant="outline" onClick={handleCancel}>
                {translate(COMMON.cancel)}
              </Button>
            </div>
          </form>

          {!isNew && (
            <div className="mt-6">
              <div className="flex items-center justify-between mb-2">
                <h4 className="font-medium">{translate(AI_CONNECTION_FORM.models)}</h4>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  onClick={() => existingConnection && syncModels(existingConnection.id)}
                  disabled={isSubmitting}
                >
                  {translate(AI_CONNECTION_FORM.models_refresh)}
                </Button>
              </div>
              {models.length > 0 ? (
                <ul className="list-disc ps-5 space-y-1">
                  {models.map((model) => (
                    <li key={model.id} className="text-sm flex items-center gap-2">
                      {model.modelName} ({model.modelCode})
                      {!model.enabled && (
                        <span className="text-xs text-red-500 ms-2">{translate(AI_CONNECTION_FORM.models_disabled)}</span>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="text-sm text-muted-foreground">{translate(AI_CONNECTION_FORM.models_none)}</p>
              )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function AIConnectionPage() {
  return (
    <ProtectedRoute>
      <AIConnectionFormContent />
    </ProtectedRoute>
  );
}