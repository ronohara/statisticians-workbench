// frontend/app/settings/database/connection/[id]/page.tsx
"use client";

import { useState, useEffect } from "react";
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
import { useTranslate, useTranslateKeyWithParams, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { formatDateTime } from "@/lib/date-format";
import { useDB, DatabaseType, type DatabaseConnection } from "@/lib/db-context";
import { useFeature } from "@/components/feature-gate";
import { Eye, EyeOff, Loader2 } from "lucide-react";

// Import translations for this module
import {
  DB_CONNECTION_FORM,
  probe_title, probe_checked, probe_last_succeeded, probe_never, probe_no_success,
  probe_check_now, probe_auto_hint, probe_check_failed,
  probe_just_now, probe_minute_ago, probe_minutes_ago, probe_hour_ago, probe_hours_ago,
  probe_state_reachable, probe_state_unreachable, probe_state_auth_failed,
  probe_state_no_database, probe_state_no_permission, probe_state_incomplete, probe_state_schema_error,
  probe_state_unknown,
} from "@/app/settings/database/translations";
import { COMMON } from "@/app/common/translations";
import { VALIDATION } from "@/app/common/translations";

interface FormData {
  name: string;
  type: DatabaseType | "";
  host: string;
  port: number;
  database: string;
  username: string;
  password: string;
  shared: boolean;
  dbConnectionGroup: string;
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

/**
 * How long ago, in whole units — "just now", "5 minutes ago", "3 hours ago".
 *
 * Past a day it returns `null`, and the caller shows the house date format
 * instead: "2 days ago" is less useful than the date itself once the answer is
 * that old, and a relative label that counts days starts to sound like an excuse.
 *
 * `now` is passed in rather than read here so the caller can drive it from a
 * ticking clock — see `nowTick`.
 */
function relativeAge(
  value: string | null | undefined,
  now: number,
  t: {
    justNow: string;
    minuteAgo: string;
    minutesAgo: (count: number) => string;
    hourAgo: string;
    hoursAgo: (count: number) => string;
  },
): string | null {
  if (!value) return null;
  const then = new Date(value).getTime();
  if (Number.isNaN(then)) return null;

  // A clock skew between the browser and the server can put `then` slightly in
  // the future; that is "just now", not a negative age.
  const seconds = Math.max(0, Math.floor((now - then) / 1000));

  if (seconds < 60) return t.justNow;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return minutes === 1 ? t.minuteAgo : t.minutesAgo(minutes);
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return hours === 1 ? t.hourAgo : t.hoursAgo(hours);
  return null;
}

/**
 * The probe state → badge colour, and the whole of the colour policy.
 *
 * Green means the data path works. Amber means it works and the data cannot be
 * read, or the connection is not complete enough to ask — a distinction a red
 * badge would erase. Red means the connection itself failed. `unknown` — no probe
 * has run — is grey, because it is not a verdict.
 */
const PROBE_TONE: Record<string, "ok" | "warn" | "bad" | "none"> = {
  reachable: "ok",
  unreachable: "bad",
  auth_failed: "bad",
  no_database: "bad",
  no_permission: "warn",
  incomplete: "warn",
  schema_error: "warn",
  unknown: "none",
};

const PROBE_BADGE: Record<"ok" | "warn" | "bad" | "none", string> = {
  ok: "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-300",
  warn: "bg-amber-100 text-amber-800 dark:bg-amber-900/30 dark:text-amber-300",
  bad: "bg-red-100 text-red-800 dark:bg-red-900/30 dark:text-red-300",
  none: "bg-muted text-muted-foreground",
};

/**
 * The declaration for a probe state's label.
 *
 * An unrecognised state maps to `unknown` rather than falling through to a blank:
 * a state the server sends and this page does not know is still a state the user
 * has to see.
 */
function probeStateLabel(state: string | null | undefined) {
  switch (state) {
    case "reachable": return probe_state_reachable;
    case "unreachable": return probe_state_unreachable;
    case "auth_failed": return probe_state_auth_failed;
    case "no_database": return probe_state_no_database;
    case "no_permission": return probe_state_no_permission;
    // "Incomplete setup" — a connection missing a required field, which is not
    // the recipe panel's "Incomplete" and must not borrow that word.
    case "incomplete": return probe_state_incomplete;
    case "schema_error": return probe_state_schema_error;
    default: return probe_state_unknown;
  }
}

function ConnectionFormContent() {
  const router = useRouter();
  const params = useParams();
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const tx = useTranslateKeyWithParams();
  const { data: session } = useSession();
  const { connections, addConnection, updateConnection, loading: dbLoading } = useDB();
  const [isTesting, setIsTesting] = useState(false);
  const [testResult, setTestResult] = useState<{ success: boolean; message: string } | null>(null);
  /**
   * The probe result on screen, and whether a manual check is running.
   *
   * Seeded from the connection the page already loaded; replaced by whatever Check
   * now returns. Kept apart from `existingConnection` so a re-probe updates the
   * panel without the form being reloaded underneath the user's edits.
   */
  const [probe, setProbe] = useState<{
    state?: string | null;
    detail?: string | null;
    probedAt?: string | null;
    successAt?: string | null;
  } | null>(null);
  const [probing, setProbing] = useState(false);
  /**
   * A clock that ticks, so the relative label ages instead of freezing.
   *
   * The panel needs "how long ago", and a value computed once when the response
   * arrived would say "just now" for as long as the page stayed open. Half a
   * minute is frequent enough for a label that never shows seconds and cheap
   * enough to be free — one setState per 30 s, only while the page is mounted.
   */
  const [nowTick, setNowTick] = useState(() => Date.now());
  useEffect(() => {
    const timer = setInterval(() => setNowTick(Date.now()), 30_000);
    return () => clearInterval(timer);
  }, []);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [canCreateDatabase, setCanCreateDatabase] = useState(false);
  const [canCreateTables, setCanCreateTables] = useState(false);
  const [autoCreateTables, setAutoCreateTables] = useState(true);
  const [autoCreateViews, setAutoCreateViews] = useState(false);

  const [groupInfo, setGroupInfo] = useState<GroupInfo | null>(null);
  const [loadingGroupInfo, setLoadingGroupInfo] = useState(true);
  const [availableGroups, setAvailableGroups] = useState<Array<{ groupId: string; groupDescription: string }>>([]);
  const [directConnection, setDirectConnection] = useState<DatabaseConnection | null>(null);
  const [fetchingDirect, setFetchingDirect] = useState(false);

  // User role for Example User detection
  const [userRole, setUserRole] = useState<UserRole | null>(null);
  const [loadingRole, setLoadingRole] = useState(true);

  const id = params.id as string;
  const isNew = id === "new";
  const contextConnection = isNew ? null : connections.find(c => c.id === id || String(c.connectionId) === id);
  const existingConnection = contextConnection || directConnection;
  const isOwner = !existingConnection || existingConnection.isOwn !== false;

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
      type: "",
      host: "localhost",
      port: 5432,
      database: "",
      username: "",
      password: "",
      shared: false,
      dbConnectionGroup: "00",
    },
  });

  const selectedType = watch("type");
  const sharedValue = watch("shared");
  const accessEnabled = useFeature("access_db");
  const mssqlEnabled = useFeature("mssql_db");

  const getDatabaseTypeName = (type: string) => {
    const names: Record<string, string> = {
      postgresql: "PostgreSQL",
      mysql: "MySQL",
      mssql: "MS SQL Server",
      access: "Microsoft Access (.accdb / .mdb)",
    };
    return names[type] || type;
  };

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

  // Fetch connection directly from API as fallback when context hasn't loaded it
  useEffect(() => {
    if (isNew || directConnection || dbLoading) return;
    // Only fetch if the connection isn't already in context
    const inContext = connections.find(c => c.id === id || String(c.connectionId) === id);
    if (inContext) return;

    let cancelled = false;
    setFetchingDirect(true);
    apiFetch("/api/user/database-connections/available")
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
  }, [id, isNew, dbLoading, connections]);

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

  const isAdminUser = userRole?.isAdmin === true;

  // Who may edit this connection: its owner, or an administrator. Everyone else
  // sees it read-only. The backend enforces the same rule.
  const canManage = isOwner || isAdminUser;

  // Fetch available groups for admin users
  useEffect(() => {
    const fetchGroups = async () => {
      try {
        const res = await apiFetch("/api/admin/groups");
        if (res.ok) {
          const data = await res.json();
          setAvailableGroups(data.groups || data || []);
        }
      } catch (error) {
        console.error("Failed to fetch groups:", error);
      }
    };
    if (isAdminUser) {
      fetchGroups();
    }
  }, [isAdminUser]);
  const showSharedToggle = isAdminUser || (groupInfo && groupInfo.userGroup !== "00");

  useEffect(() => {
    if (existingConnection) {
      setValue("name", existingConnection.name);
      setValue("type", existingConnection.type);
      setValue("host", existingConnection.host);
      setValue("port", existingConnection.port);
      setValue("database", existingConnection.database);
      setValue("username", existingConnection.username);
      setValue("password", existingConnection.password);
      const isShared = existingConnection.isShared === true;
      setValue("shared", isShared);
      setValue("dbConnectionGroup", existingConnection.dbConnectionGroup || "00");
      setCanCreateDatabase(existingConnection.canCreateDatabase === true);
      setCanCreateTables(existingConnection.canCreateTables === true);
    }
  }, [existingConnection, setValue]);

  useEffect(() => {
    if (selectedType === "mysql") {
      setValue("port", 3306);
    } else if (selectedType === "postgresql") {
      setValue("port", 5432);
    } else if (selectedType === "mssql") {
      setValue("port", 1433);
    } else if (selectedType === "access") {
      setValue("port", 9432);
      setValue("host", "127.0.0.1");
    }
  }, [selectedType, setValue]);

  const validateForm = (data: FormData): boolean => {
    let isValid = true;
    clearErrors();

    if (!data.type) {
      setError("type", { message: translate(VALIDATION.type_required) });
      isValid = false;
    }
    if (!data.name.trim()) {
      setError("name", { message: translate(VALIDATION.name_required) });
      isValid = false;
    }
    if (!data.host.trim()) {
      setError("host", { message: translate(VALIDATION.host_required) });
      isValid = false;
    }
    if (!data.port || data.port < 1 || data.port > 65535) {
      setError("port", { message: translate(VALIDATION.port_invalid) });
      isValid = false;
    }
    if (!data.database.trim()) {
      setError("database", { message: translate(VALIDATION.database_required) });
      isValid = false;
    }
    if (!data.username.trim()) {
      setError("username", { message: translate(VALIDATION.username_required) });
      isValid = false;
    }
    if (!data.password.trim()) {
      setError("password", { message: translate(VALIDATION.password_required) });
      isValid = false;
    }
    return isValid;
  };

  const onTest = async () => {
    const values = getValues();
    if (!values.host || !values.port || !values.database || !values.username || !values.password) {
      toast.error(translate(DB_CONNECTION_FORM.test_incomplete));
      return;
    }
    setIsTesting(true);
    setTestResult(null);
    setErrorMessage(null);
    try {
      const response = await apiFetch("/api/test-connection", {
        method: "POST",
        body: JSON.stringify({
          type: values.type,
          host: values.host,
          port: values.port,
          database: values.database,
          username: values.username,
          password: values.password,
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
        const errorMsg = getErrorMessageFromData(translate, errorData, DB_CONNECTION_FORM.test_failed);
        setTestResult({ success: false, message: errorMsg });
        toast.error(errorMsg);
        return;
      }
      
      const data = await response.json();
      if (data.success) {
        setCanCreateDatabase(data.canCreateDatabase === true);
        setCanCreateTables(data.canCreateTables === true);
        const successMsg = translate(DB_CONNECTION_FORM.test_success);
        toast.success(successMsg);
        setTestResult({ success: true, message: successMsg });
      } else {
        const errorMsg = data.error || data.message || translate(DB_CONNECTION_FORM.test_failed);
        toast.error(errorMsg);
        setTestResult({ success: false, message: errorMsg });
      }
    } catch (error: any) {
      // Test Connection keeps its own message: this branch is the network test,
      // not the probe, and the two buttons say different things.
      const errorMsg = error.message || translate(DB_CONNECTION_FORM.test_network_error);
      setTestResult({ success: false, message: errorMsg });
      toast.error(errorMsg);
    } finally {
      setIsTesting(false);
    }
  };

  const onSubmit = async (data: FormData) => {
    if (!validateForm(data)) return;
    setIsSubmitting(true);
    setErrorMessage(null);
    try {
      const payload: any = {
        name: data.name,
        type: data.type,
        host: data.host,
        port: data.port,
        database: data.database,
        username: data.username,
        password: data.password,
        shared: data.shared,
        canCreateDatabase: canCreateDatabase,
        canCreateTables: canCreateTables,
        auto_create_tables: autoCreateTables,
        auto_create_views: autoCreateViews,
      };

      // Admin users can select a group from the dropdown; others use their own group
      if (data.shared && isAdminUser) {
        payload.dbConnectionGroup = data.dbConnectionGroup || "00";
      } else if (data.shared && groupInfo && groupInfo.userGroup !== "00") {
        payload.dbConnectionGroup = groupInfo.userGroup;
      } else {
        payload.dbConnectionGroup = "00";
      }

      if (isNew) {
        await addConnection(payload);
        toast.success(translate(DB_CONNECTION_FORM.add_success));
      } else if (existingConnection) {
        await updateConnection(existingConnection.id, payload);
        toast.success(translate(DB_CONNECTION_FORM.update_success));
      }
      router.push("/settings/database");
    } catch (error: any) {
      const msg = error.message || translate(DB_CONNECTION_FORM.save_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  /**
   * Ask the server to probe this connection again, and show what it recorded.
   *
   * Its own request rather than a save: the definition is unchanged, and pressing
   * Check now must not write the form. `force` is implicit — the point of the
   * button is to ask again now rather than be handed the cached answer.
   */
  const handleCheckNow = async () => {
    if (!id || probing) return;
    setProbing(true);
    try {
      const res = await apiFetch(`/api/user/database-connections/${id}/probe`, { method: "POST" });
      if (!res.ok) {
        // This route answers `{error, message}` on failure — the coded envelope
        // `_error` builds — while the rest of the API answers `{detail}`. The
        // message is what a reader needs; the code is the fallback, never the
        // primary, or the panel would display `api.user.connection_not_found`.
        let shown = "";
        try {
          const body = await res.json();
          shown = body?.message || body?.detail || body?.error || "";
        } catch { /* keep the fallback */ }
        throw new Error(shown || translate(probe_check_failed));
      }
      const data = await res.json();
      setProbe({
        state: data.probeState,
        detail: data.probeDetail,
        probedAt: data.probedAt,
        successAt: data.probeSuccessAt,
      });
    } catch (e: unknown) {
      // A failed *request* is not a probe result, so it must not be shown as one.
      // The panel keeps its last known state, and this says the check did not run.
      setTestResult({
        success: false,
        message: e instanceof Error ? e.message : translate(probe_check_failed),
      });
    } finally {
      setProbing(false);
    }
  };

  const handleCancel = () => {
    router.push("/settings/database");
  };

  const dismissError = () => setErrorMessage(null);

  const isCurrentlyShared = existingConnection 
    ? existingConnection.isShared === true
    : false;

  if (dbLoading || fetchingDirect || loadingGroupInfo || loadingRole) {
    return <div className="max-w-lg mx-auto py-8">{translate(COMMON.loading)}</div>;
  }

  if (!isNew && !existingConnection && !dbLoading) {
    return (
      <div className="max-w-lg mx-auto py-8">
        <Card>
          <CardContent className="pt-6">
            <p className="text-center text-red-500">{translate(DB_CONNECTION_FORM.not_found)}</p>
            <Button className="mt-4 w-full" onClick={handleCancel}>
              {translate(COMMON.back)}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-lg mx-auto py-8">
      <Card>
        <CardHeader>
          <CardTitle>
            {isNew ? translate(DB_CONNECTION_FORM.add_title) : translate(DB_CONNECTION_FORM.edit_title)}
          </CardTitle>
          <CardDescription>
            {translate(DB_CONNECTION_FORM.form_description)}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {errorMessage && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
              <span className="text-sm">{errorMessage}</span>
              <button
                onClick={dismissError}
                className="text-red-500 hover:text-red-700"
                aria-label={translate(COMMON.dismiss_error)}
              >
                <span className="text-xl">&times;</span>
              </button>
            </div>
          )}

          {/* autoComplete="off" on the form and on every field, and
              "new-password" on the credential field: this form has text inputs
              (host, port, database, username) immediately before a
              type="password" field, which is the shape browsers use to identify
              a login form. Without these, Firefox fills the saved Workbench
              login into those text slots and the saved password into the
              credential field — the same defect found on the AI connection page
              on 2026-11-11. */}
          <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" autoComplete="off">
            <div className="space-y-2">
              <Label htmlFor="name">{translate(DB_CONNECTION_FORM.name_label)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="auto"
                  id="name"
                  autoComplete="off"
                  {...register("name")}
                  placeholder={translate(DB_CONNECTION_FORM.name_placeholder)}
                  className="flex-1"
                  disabled={isExampleUser || !canManage}
                />
              </div>
              {errors.name && <p className="text-sm text-red-500">{errors.name.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="type">{translate(DB_CONNECTION_FORM.type_label)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Select
                  value={selectedType}
                  onValueChange={(val) => {
                    if (val === null) return;
                    setValue("type", val as DatabaseType);
                    clearErrors("type");
                  }}
                  disabled={isExampleUser || !canManage}
                >
                  <SelectTrigger className="flex-1">
                    <SelectValue placeholder={translate(DB_CONNECTION_FORM.select_type)}>
                      {getDatabaseTypeName(selectedType)}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="" disabled>{translate(DB_CONNECTION_FORM.select_type)}</SelectItem>
                    <SelectItem value="postgresql">PostgreSQL</SelectItem>
                    <SelectItem value="mysql">MySQL</SelectItem>
                    {accessEnabled && (
                      <SelectItem value="access">Microsoft Access (.accdb / .mdb)</SelectItem>
                    )}
                    {mssqlEnabled && (
                      <SelectItem value="mssql">MS SQL Server</SelectItem>
                    )}
                  </SelectContent>
                </Select>
              </div>
              {errors.type && <p className="text-sm text-red-500">{errors.type.message}</p>}
            </div>

            {selectedType === "access" ? (
              <>
                <div className="space-y-2">
                  <Label htmlFor="database">{translate(DB_CONNECTION_FORM.file_path_label)}</Label>
                  <div className="relative flex items-center">
                    <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                    <Input dir="ltr"
                      id="database"
                      autoComplete="off"
                      {...register("database")}
                      placeholder="C:\Users\...\database.accdb"
                      className="flex-1"
                      disabled={isExampleUser || !canManage}
                    />
                  </div>
                  {errors.database && <p className="text-sm text-red-500">{errors.database.message}</p>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="host">{translate(DB_CONNECTION_FORM.jet_host_label)}</Label>
                  <div className="relative flex items-center">
                    <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                    <Input dir="ltr"
                      id="host"
                      autoComplete="off"
                      {...register("host")}
                      placeholder="127.0.0.1"
                      className="flex-1"
                      disabled={isExampleUser || !canManage}
                    />
                  </div>
                  {errors.host && <p className="text-sm text-red-500">{errors.host.message}</p>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="port">{translate(DB_CONNECTION_FORM.jet_port_label)}</Label>
                  <div className="relative flex items-center">
                    <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                    <Input dir="ltr"
                      id="port"
                      autoComplete="off"
                      type="number"
                      {...register("port", { valueAsNumber: true })}
                      className="flex-1"
                      disabled={isExampleUser || !canManage}
                    />
                  </div>
                  {errors.port && <p className="text-sm text-red-500">{errors.port.message}</p>}
                </div>
              </>
            ) : (
              <>
                <div className="space-y-2">
                  <Label htmlFor="host">{translate(DB_CONNECTION_FORM.host_label)}</Label>
                  <div className="relative flex items-center">
                    <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                    <Input dir="ltr"
                      id="host"
                      autoComplete="off"
                      {...register("host")}
                      placeholder="localhost"
                      className="flex-1"
                      disabled={isExampleUser || !canManage}
                    />
                  </div>
                  {errors.host && <p className="text-sm text-red-500">{errors.host.message}</p>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="port">{translate(DB_CONNECTION_FORM.port_label)}</Label>
                  <div className="relative flex items-center">
                    <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                    <Input dir="ltr"
                      id="port"
                      autoComplete="off"
                      type="number"
                      {...register("port", { valueAsNumber: true })}
                      className="flex-1"
                      disabled={isExampleUser || !canManage}
                    />
                  </div>
                  {errors.port && <p className="text-sm text-red-500">{errors.port.message}</p>}
                </div>

                <div className="space-y-2">
                  <Label htmlFor="database">{translate(DB_CONNECTION_FORM.database_label)}</Label>
                  <div className="relative flex items-center">
                    <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                    <Input dir="ltr"
                      id="database"
                      autoComplete="off"
                      {...register("database")}
                      className="flex-1"
                      disabled={isExampleUser || !canManage}
                    />
                  </div>
                  {errors.database && <p className="text-sm text-red-500">{errors.database.message}</p>}
                </div>
              </>
            )}

            <div className="space-y-2">
              <Label htmlFor="username">{translate(DB_CONNECTION_FORM.username_label)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="ltr"
                  id="username"
                  autoComplete="off"
                  {...register("username")}
                  className="flex-1"
                  disabled={isExampleUser || !canManage}
                />
              </div>
              {errors.username && <p className="text-sm text-red-500">{errors.username.message}</p>}
            </div>

            <div className="space-y-2">
              <Label htmlFor="password">{translate(DB_CONNECTION_FORM.password_label)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="ltr"
                  id="password"
                  type={showPassword ? "text" : "password"}
                  autoComplete="new-password"
                  {...register("password")}
                  className="flex-1 pe-10"
                  disabled={isExampleUser || !canManage}
                />
                {!isExampleUser ? (
                  <button
                    type="button"
                    onClick={() => setShowPassword(!showPassword)}
                    disabled={!canManage}
                    className="absolute inset-y-0 end-0 flex items-center pe-3 text-muted-foreground hover:text-foreground disabled:opacity-50 disabled:cursor-not-allowed disabled:hover:text-muted-foreground"
                    tabIndex={-1}
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                ) : (
                  <span className="absolute inset-y-0 end-0 z-10 flex items-center pe-3 text-xs text-muted-foreground">
                    🔒
                  </span>
                )}
              </div>
              {errors.password && <p className="text-sm text-red-500">{errors.password.message}</p>}
            </div>

            {!isNew && !canManage && existingConnection && (
              <div className="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-md text-blue-800 text-sm">
                {translate(DB_CONNECTION_FORM.shared_readonly_message)}
              </div>
            )}
            {showSharedToggle && (
              <div className="flex items-center justify-between p-3 bg-muted/30 rounded-md border border-muted">
                <div>
                  <Label>
                    {translate(DB_CONNECTION_FORM.shared_label)}
                    {!isAdminUser && groupInfo && (
                      <span className="text-muted-foreground font-normal ms-1">
                        ({groupInfo.userGroup}{groupInfo.groupDescription ? ` \u2014 ${groupInfo.groupDescription}` : ''})
                      </span>
                    )}
                  </Label>
                  <p className="text-sm text-muted-foreground">
                    {translate(DB_CONNECTION_FORM.shared_description)}
                  </p>
                  {!isNew && (
                    <p className="text-xs font-medium mt-1">
                      {isCurrentlyShared 
                        ? translate(DB_CONNECTION_FORM.currently_shared)
                        : translate(DB_CONNECTION_FORM.currently_not_shared)}
                    </p>
                  )}
                  {isAdminUser && availableGroups.length > 0 && (
                    <div className="mt-2">
                      <Label className="text-xs">{translate(DB_CONNECTION_FORM.group_label)}</Label>
                      <Select
                        value={watch("dbConnectionGroup")}
                        onValueChange={(val) => setValue("dbConnectionGroup", val || "00")}
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
                  disabled={isExampleUser || !canManage}
                />
              </div>
            )}

            {isNew && (
              <div className="space-y-3 pt-2 border-t">
                <p className="text-sm font-medium text-muted-foreground">{translate(DB_CONNECTION_FORM.auto_create_title)}</p>
                <div className="flex items-center justify-between">
                  <Label className="text-sm">{translate(DB_CONNECTION_FORM.auto_create_tables)}</Label>
                  <Switch checked={autoCreateTables} onCheckedChange={setAutoCreateTables} />
                </div>
                <div className="flex items-center justify-between">
                  <Label className="text-sm">{translate(DB_CONNECTION_FORM.auto_create_views)}</Label>
                  <Switch checked={autoCreateViews} onCheckedChange={setAutoCreateViews} />
                </div>
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
              <Button type="button" variant="outline" onClick={onTest} disabled={isTesting || isExampleUser || !canManage}>
                {isTesting ? translate(COMMON.testing) : translate(DB_CONNECTION_FORM.test_button)}
              </Button>
              <Button type="submit" disabled={isSubmitting || isExampleUser || !canManage}>
                {isSubmitting ? translate(COMMON.saving) : translate(COMMON.save)}
              </Button>
              <Button type="button" variant="outline" onClick={handleCancel}>
                {translate(COMMON.cancel)}
              </Button>
            </div>

            {/* The probe's stored result, below the buttons: the status answers the
                thing you just pressed, so it sits after the actions rather than
                competing with the form above them. */}
            {!isNew && existingConnection && (() => {
              // The freshest answer wins: a manual check replaces what the page
              // loaded; the loaded value is the fallback.
              const state = probe?.state ?? existingConnection.probeState;
              const detail = probe?.detail ?? existingConnection.probeDetail;
              const checkedAt = probe?.probedAt ?? existingConnection.probedAt;
              const successAt = probe ? probe.successAt : existingConnection.probeSuccessAt;
              return (
                <div className="mt-4 rounded-lg border bg-muted/20 overflow-hidden">
                  <div className="flex flex-wrap items-center gap-2 px-3 py-2 border-b bg-background/60">
                    <span
                      className={`inline-flex items-center gap-1.5 rounded-full px-2 py-0.5 text-xs font-semibold ${
                        PROBE_BADGE[PROBE_TONE[state ?? "unknown"] ?? "none"]
                      }`}
                    >
                      <span className="size-1.5 rounded-full bg-current" />
                      {translate(probeStateLabel(state))}
                    </span>
                    <span className="text-xs font-semibold">{translate(probe_title)}</span>
                    {checkedAt && (
                      // Relative, because the absolute format is minute-resolution
                      // and a probe finishes in a fraction of a second — two checks
                      // a few seconds apart rendered as the same string and the
                      // click looked like it did nothing.
                      <span className="ms-auto text-xs text-muted-foreground">
                        {relativeAge(checkedAt, nowTick, {
                          justNow: translate(probe_just_now),
                          minuteAgo: translate(probe_minute_ago),
                          minutesAgo: (count) => tx(probe_minutes_ago, { count }),
                          hourAgo: translate(probe_hour_ago),
                          hoursAgo: (count) => tx(probe_hours_ago, { count }),
                        }) ?? formatDateTime(checkedAt)}
                      </span>
                    )}
                  </div>

                  <div className="px-3 py-2.5 space-y-1.5 text-xs">
                    <div className="grid grid-cols-[7.5rem_1fr] gap-x-3 gap-y-1">
                      <span className="text-muted-foreground">{translate(probe_checked)}</span>
                      <span>{checkedAt ? formatDateTime(checkedAt) : translate(probe_never)}</span>
                      <span className="text-muted-foreground">{translate(probe_last_succeeded)}</span>
                      <span>
                        {successAt ? (
                          formatDateTime(successAt)
                        ) : (
                          <>
                            <span className="font-semibold text-amber-700 dark:text-amber-400">
                              {translate(probe_never)}
                            </span>
                            <span className="text-muted-foreground"> &middot; {translate(probe_no_success)}</span>
                          </>
                        )}
                      </span>
                    </div>

                    {detail && state !== "reachable" && (
                      // Persistent and inline, and it stays: a failure described in
                      // a toast is gone by the next visit, which is why this panel
                      // exists at all.
                      <p className="rounded border border-red-200 bg-red-50 px-2 py-1.5 font-mono text-[0.7rem] text-red-900 dark:border-red-900 dark:bg-red-950/40 dark:text-red-200 break-words">
                        {detail}
                      </p>
                    )}

                    <div className="flex items-center gap-2 pt-1.5 border-t">
                      <Button
                        type="button"
                        variant="outline"
                        size="sm"
                        className="h-7 text-xs"
                        onClick={handleCheckNow}
                        disabled={probing}
                      >
                        {probing && <Loader2 className="size-3.5 animate-spin me-1" />}
                        {translate(probe_check_now)}
                      </Button>
                      <span className="text-xs text-muted-foreground">{translate(probe_auto_hint)}</span>
                    </div>
                  </div>
                </div>
              );
            })()}
          </form>
        </CardContent>
      </Card>
    </div>
  );
}

export default function ConnectionPage() {
  return (
    <ProtectedRoute>
      <ConnectionFormContent />
    </ProtectedRoute>
  );
}