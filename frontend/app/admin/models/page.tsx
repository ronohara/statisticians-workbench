"use client";

// Admin → Models (plan Item 18).
//
// The page the abandoned "Provider Models" surface becomes. Provider was the axis
// there: you picked a provider, then edited that provider's copy of a model. But a
// model is one thing however many providers serve it, and a per-provider copy is
// exactly what let `enabled` mean different things in different places. So the list
// is models, the switch is on the model, and the servers that can reach it are a
// derived column rather than a selector.
//
// WHAT THIS PAGE DOES NOT OFFER, DELIBERATELY
//
// No "refresh models" button. Discovery against a provider's catalogue was a second
// path to the same fact, keyed by provider rather than by connection, and a refresh
// through one Ollama host deleted another host's findings. Discovery now belongs to
// the connection it was run against (plan Item 31), and a button here that triggered
// it per provider would reintroduce the defect.
//
// No enable/disable per connection. The design settles that the decision is made
// once, on the model; a control here offering it per server would be the drift the
// redesign removed.

import { useCallback, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { ProtectedRoute } from "@/components/protected-route";
import { TestStateBadge, type TestState } from "@/components/test-state-badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Dialog, DialogContent, DialogDescription, DialogHeader, DialogTitle } from "@/components/ui/dialog";
import { toast } from "sonner";
import { Loader2, Pencil, Check, XCircle, Lock, UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";

import { ADMIN } from "../translations";
import { COMMON } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";
import { AI_TESTING } from "@/app/aitesting/translations";

/** One server whose discovery has seen this model. Derived, never stored. */
interface ModelServer {
    name: string;
    provider: string;
    // The pair's other half. The server list is per MODEL, so naming a connection
    // without its id left an administrator able to see that a connection has the
    // model but not which (connection, model) pair to tune.
    connectionId: number;
}

/** A model's capability entry as the API returns it. */
interface TestEntry {
    state?: TestState;
    testedAt?: string | null;
    reason?: string;
}

interface AdminModel {
    id: string;
    modelName: string;
    enabled: boolean;
    preferred: boolean;
    comment: string | null;
    testResults: Record<string, TestEntry>;
    servers: ModelServer[];
    createdAt: string | null;
    updatedAt: string | null;
}

/**
 * The three tests, in the order the design presents them. The ids are data — they
 * are the keys results are filed under — so they never change and never translate.
 * The labels below are what a reader sees and do translate.
 */
const TEST_IDS = ["competence", "tools", "turn"] as const;

function AdminModelsContent() {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const router = useRouter();

    const [models, setModels] = useState<AdminModel[]>([]);
    const [loading, setLoading] = useState(true);
    const [updating, setUpdating] = useState<string | null>(null);
    const [editingComment, setEditingComment] = useState<string | null>(null);
    const [commentValue, setCommentValue] = useState<string>("");
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    // Which (connection, model) pair the tuning dialog is open for, or null.
    const [tuningTarget, setTuningTarget] = useState<TuningTarget | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [userRole, setUserRole] = useState<{ isAdmin: boolean; isGroupAdmin: boolean; isExampleUser: boolean } | null>(null);
    const [loadingRole, setLoadingRole] = useState(true);

    // Filters, applied by the API rather than in the browser: 419 models is the
    // measured size of the abandoned catalogue, and rendering all of them to show
    // eight is work nobody asked for.
    const [search, setSearch] = useState("");
    const [enabledFilter, setEnabledFilter] = useState("any");
    const [testFilter, setTestFilter] = useState("any");
    const [resultFilter, setResultFilter] = useState("any");

    const isExampleUser = userRole?.isExampleUser === true;
    const isAdmin = userRole?.isAdmin === true;
    const filtersActive = search.trim() !== "" || enabledFilter !== "any" || testFilter !== "any";

    const dismissError = () => setErrorMessage(null);
    const dismissSuccess = () => setSuccessMessage(null);

    const loadModels = useCallback(async () => {
        setLoading(true);
        setErrorMessage(null);
        try {
            const params = new URLSearchParams();
            if (search.trim()) params.set("search", search.trim());
            if (enabledFilter !== "any") params.set("enabled", enabledFilter);
            if (testFilter !== "any" && resultFilter !== "any") {
                params.set("test", testFilter);
                params.set("result", resultFilter);
            }
            const qs = params.toString();
            const res = await apiFetch(`/api/admin/models${qs ? `?${qs}` : ""}`);
            if (!res.ok) {
                let data: unknown = {};
                try {
                    const text = await res.text();
                    if (text) data = JSON.parse(text);
                } catch {
                    // A body that is not JSON leaves the fallback message in place.
                }
                throw new Error(getErrorMessageFromData(translate, data, ADMIN.models.load_models_error));
            }
            const data = await res.json();
            setModels(data.models ?? []);
        } catch (error) {
            setErrorMessage(
                error instanceof Error ? error.message : translate(ADMIN.models.load_models_error),
            );
        } finally {
            setLoading(false);
        }
    }, [search, enabledFilter, testFilter, resultFilter, translate]);

    useEffect(() => {
        const fetchUserRole = async () => {
            try {
                const res = await apiFetch("/api/user/role");
                if (res.ok) {
                    setUserRole(await res.json());
                }
            } catch {
                // The gate below refuses what it cannot verify; nothing to say
                // here that the page cannot say better once it knows.
            } finally {
                setLoadingRole(false);
            }
        };
        fetchUserRole();
    }, []);

    useEffect(() => {
        if (!loadingRole && userRole) {
            loadModels();
        }
    }, [loadingRole, userRole, loadModels]);

    /**
     * Write one field on one model.
     *
     * Nothing is disabled to pre-empt a mistake: the action runs and the refusal is
     * reported in the page. A disabled control tells the reader nothing about why it
     * is unavailable, and this project settled that trade in favour of a message.
     */
    const patchModel = async (model: AdminModel, field: "enabled" | "preferred" | "comment", value: unknown) => {
        setUpdating(model.id);
        setErrorMessage(null);
        setSuccessMessage(null);
        try {
            const res = await apiFetch("/api/admin/models", {
                method: "PATCH",
                body: JSON.stringify({ id: model.id, [field]: value }),
            });
            if (!res.ok) {
                let data: unknown = {};
                try {
                    const text = await res.text();
                    if (text) data = JSON.parse(text);
                } catch {
                    // fall through to the fallback message
                }
                throw new Error(
                    getErrorMessageFromData(
                        translate,
                        data,
                        field === "comment" ? ADMIN.models.update_error : ADMIN.models.toggle_error,
                    ),
                );
            }
            const data = await res.json();
            setModels((current) =>
                current.map((m) => (m.id === data.model.id ? { ...m, ...data.model } : m)),
            );
            const msg = translate(ADMIN.models.update_success);
            setSuccessMessage(msg);
            toast.success(msg);
            setEditingComment(null);
        } catch (error) {
            const msg = error instanceof Error ? error.message : translate(ADMIN.models.toggle_error);
            // Persistent, in the page, beside the list it is about — a toast alone
            // would be gone before the reader could act on it.
            setErrorMessage(msg);
            toast.error(msg);
        } finally {
            setUpdating(null);
        }
    };

    const clearFilters = () => {
        setSearch("");
        setEnabledFilter("any");
        setTestFilter("any");
        setResultFilter("any");
    };

    if (!isLanguageLoaded || loadingRole) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (userRole && !isAdmin && !isExampleUser) {
        return (
            <div className="max-w-lg mx-auto py-12">
                <Card>
                    <CardContent className="pt-6">
                        <p className="text-center text-red-500">{translate(COMMON.no_permission)}</p>
                        <Button className="mt-4 w-full" onClick={() => router.push("/")}>
                            {translate(COMMON.back)}
                        </Button>
                    </CardContent>
                </Card>
            </div>
        );
    }

    const modelRow = (model: AdminModel) => (
        <div key={model.id} className="p-3 border rounded-md hover:bg-muted/50 transition-colors space-y-3">
            <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-3">
                <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-3 flex-wrap">
                        <span className="font-medium break-all">{model.modelName}</span>
                        {model.preferred && (
                            <span className="text-xs rounded-full bg-blue-100 text-blue-800 px-2 py-0.5">
                                {translate(ADMIN.models.preferred)}
                            </span>
                        )}
                        {isExampleUser && (
                            <span className="text-xs text-muted-foreground italic">
                                {translate(ADMIN.groups.readonly_badge)}
                            </span>
                        )}
                    </div>

                    {editingComment === model.id ? (
                        <div className="flex items-center gap-2 mt-2">
                            <Input
                                dir="auto"
                                value={commentValue}
                                onChange={(e) => setCommentValue(e.target.value)}
                                className="w-full max-w-md h-8 text-sm"
                                placeholder={translate(ADMIN.models.comment_placeholder)}
                                autoFocus
                            />
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => patchModel(model, "comment", commentValue)}
                                aria-label={translate(ADMIN.models.edit_comment)}
                            >
                                {updating === model.id ? (
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                ) : (
                                    <Check className="h-3 w-3" />
                                )}
                            </Button>
                            <Button
                                variant="ghost"
                                size="icon"
                                className="h-8 w-8"
                                onClick={() => setEditingComment(null)}
                                aria-label={translate(COMMON.cancel)}
                            >
                                <XCircle className="h-3 w-3" />
                            </Button>
                        </div>
                    ) : (
                        <div className="flex items-center gap-2 text-sm text-muted-foreground mt-1">
                            <span className="break-all">
                                {model.comment || translate(ADMIN.models.no_comment)}
                            </span>
                            {isAdmin && (
                                <button
                                    onClick={() => {
                                        setEditingComment(model.id);
                                        setCommentValue(model.comment ?? "");
                                    }}
                                    className="text-muted-foreground hover:text-foreground"
                                    title={translate(ADMIN.models.edit_comment)}
                                >
                                    <Pencil className="h-3 w-3" />
                                </button>
                            )}
                        </div>
                    )}

                    <div className="mt-2 text-xs text-muted-foreground">
                        <span className="font-medium">{translate(ADMIN.models.servers_title)}: </span>
                        {model.servers.length === 0 ? (
                            <span>{translate(ADMIN.models.no_servers)}</span>
                        ) : (
                            <span className="inline-flex flex-wrap gap-x-2 gap-y-1">
                                {model.servers.map((s) => (
                                    // Always enabled. A reader whose click is refused gets a
                                    // message explaining why; a disabled control explains
                                    // nothing, which is this project's standing trade.
                                    <button
                                        key={`${s.connectionId}`}
                                        type="button"
                                        className="underline decoration-dotted underline-offset-2 hover:text-foreground"
                                        onClick={() =>
                                            setTuningTarget({
                                                connectionId: s.connectionId,
                                                modelId: model.id,
                                                modelName: model.modelName,
                                                serverName: s.name,
                                            })
                                        }
                                        title={translate(ADMIN.models.tuning_title)}
                                    >
                                        {s.name}
                                    </button>
                                ))}
                            </span>
                        )}
                    </div>
                </div>

                <div className="flex items-center gap-4 flex-wrap">
                    <div className="flex items-center gap-1">
                        <Switch
                            checked={model.enabled}
                            onCheckedChange={() =>
                                isAdmin &&
                                patchModel(model, "enabled", !model.enabled)
                            }
                            aria-label={translate(ADMIN.models.enabled)}
                        />
                        <span className="text-xs text-muted-foreground">
                            {model.enabled ? translate(ADMIN.models.enabled) : translate(ADMIN.models.disabled)}
                        </span>
                    </div>
                    <div className="flex items-center gap-1">
                        <Switch
                            checked={model.preferred}
                            onCheckedChange={() =>
                                isAdmin &&
                                patchModel(model, "preferred", !model.preferred)
                            }
                            aria-label={translate(ADMIN.models.preferred)}
                        />
                        <span className="text-xs text-muted-foreground">
                            {model.preferred ? translate(ADMIN.models.preferred) : translate(ADMIN.models.not_preferred)}
                        </span>
                    </div>
                </div>
            </div>

            <div className="flex flex-wrap gap-6 pt-2 border-t">
                {TEST_IDS.map((testId) => {
                    const entry = model.testResults?.[testId];
                    return (
                        <div key={testId} className="flex flex-col gap-1">
                            <span className="text-[11px] uppercase tracking-wide text-muted-foreground">
                                {translate(AI_TESTING[`test_${testId}` as keyof typeof AI_TESTING])}
                            </span>
                            <TestStateBadge
                                state={(entry?.state ?? "unknown") as TestState}
                                testedAt={entry?.testedAt ?? null}
                            />
                        </div>
                    );
                })}
            </div>
        </div>
    );

    return (
        <div className="max-w-6xl mx-auto space-y-6">
            <div>
                <h1 className="text-3xl font-bold">{translate(COMMON.ai_models)}</h1>
                <p className="text-sm text-muted-foreground">{translate(ADMIN.models.description)}</p>
            </div>

            {isExampleUser && (
                <div className="p-6 bg-orange-50 border border-orange-200 rounded-md text-orange-800 text-center">
                    <Lock className="h-10 w-10 mx-auto mb-3 text-orange-600" />
                    <p className="text-sm mb-4">{translate(COMPONENTS.readonly_wrapper)}</p>
                    <Link href="/register">
                        <Button>
                            <UserPlus className="h-4 w-4 me-2" />
                            {translate(COMPONENTS.example_user_banner.register_button)}
                        </Button>
                    </Link>
                </div>
            )}

            {errorMessage && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
                    <span className="text-sm">{errorMessage}</span>
                    <button onClick={dismissError} className="text-red-500 hover:text-red-700" aria-label={translate(COMMON.dismiss)}>
                        <XCircle className="h-5 w-5" />
                    </button>
                </div>
            )}

            {successMessage && (
                <div className="p-3 bg-green-50 border border-green-200 rounded-md text-green-800 flex items-center justify-between">
                    <span className="text-sm">{successMessage}</span>
                    <button onClick={dismissSuccess} className="text-green-500 hover:text-green-700" aria-label={translate(COMMON.dismiss)}>
                        <span className="text-xl">&times;</span>
                    </button>
                </div>
            )}

            <div className="flex flex-wrap items-end gap-3">
                <div className="w-full md:w-64">
                    <Label htmlFor="model-search">{translate(ADMIN.models.search_placeholder)}</Label>
                    <Input
                        id="model-search"
                        value={search}
                        onChange={(e) => setSearch(e.target.value)}
                        placeholder={translate(ADMIN.models.search_placeholder)}
                    />
                </div>

                <div className="w-40">
                    <Label htmlFor="enabled-filter">{translate(ADMIN.models.filter_state)}</Label>
                    <Select value={enabledFilter} onValueChange={(v) => v !== null && setEnabledFilter(v)}>
                        <SelectTrigger id="enabled-filter">
                            <SelectValue>
                                {(value: string) =>
                                    value === "true"
                                        ? translate(ADMIN.models.enabled)
                                        : value === "false"
                                          ? translate(ADMIN.models.disabled)
                                          : translate(ADMIN.models.filter_any)}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent className="min-w-max">
                            <SelectItem value="any">{translate(ADMIN.models.filter_any)}</SelectItem>
                            <SelectItem value="true">{translate(ADMIN.models.enabled)}</SelectItem>
                            <SelectItem value="false">{translate(ADMIN.models.disabled)}</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                <div className="w-44">
                    <Label htmlFor="test-filter">{translate(ADMIN.models.filter_test)}</Label>
                    <Select
                        value={testFilter}
                        onValueChange={(v) => {
                            if (v === null) return;
                            setTestFilter(v);
                            // A test with no result chosen filters nothing; clearing
                            // the result keeps the pair consistent rather than
                            // leaving a state the API would silently ignore.
                            if (v === "any") setResultFilter("any");
                        }}
                    >
                        <SelectTrigger id="test-filter">
                            <SelectValue>
                                {(value: string) =>
                                    value === "any"
                                        ? translate(ADMIN.models.filter_any)
                                        : translate(AI_TESTING[`test_${value}` as keyof typeof AI_TESTING])}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent className="min-w-max">
                            <SelectItem value="any">{translate(ADMIN.models.filter_any)}</SelectItem>
                            {TEST_IDS.map((id) => (
                                <SelectItem key={id} value={id}>
                                    {translate(AI_TESTING[`test_${id}` as keyof typeof AI_TESTING])}
                                </SelectItem>
                            ))}
                        </SelectContent>
                    </Select>
                </div>

                <div className="w-36">
                    <Label htmlFor="result-filter">{translate(ADMIN.models.filter_result)}</Label>
                    <Select value={resultFilter} onValueChange={(v) => v !== null && setResultFilter(v)}>
                        <SelectTrigger id="result-filter">
                            <SelectValue>
                                {(value: string) =>
                                    value === "pass"
                                        ? translate(AI_TESTING.state_pass)
                                        : value === "fail"
                                          ? translate(AI_TESTING.state_fail)
                                          : translate(ADMIN.models.filter_any)}
                            </SelectValue>
                        </SelectTrigger>
                        <SelectContent className="min-w-max">
                            <SelectItem value="any">{translate(ADMIN.models.filter_any)}</SelectItem>
                            <SelectItem value="pass">{translate(AI_TESTING.state_pass)}</SelectItem>
                            <SelectItem value="fail">{translate(AI_TESTING.state_fail)}</SelectItem>
                        </SelectContent>
                    </Select>
                </div>

                <Button variant="outline" onClick={clearFilters}>
                    {translate(ADMIN.models.filter_clear)}
                </Button>
            </div>

            <Card>
                <CardHeader>
                    <CardTitle>
                        {loading
                            ? translate(COMMON.ai_models)
                            : translate(ADMIN.models.model_count).replace("{count}", String(models.length))}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {loading ? (
                        <div className="flex items-center justify-center h-32">
                            <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
                        </div>
                    ) : models.length === 0 ? (
                        <p className="text-muted-foreground text-center py-4">
                            {filtersActive
                                ? translate(ADMIN.models.no_matches)
                                : translate(ADMIN.models.no_models)}
                        </p>
                    ) : (
                        <div className="space-y-3">{models.map(modelRow)}</div>
                    )}
                </CardContent>
            </Card>

            <ModelTuningDialog
                target={tuningTarget}
                onClose={() => setTuningTarget(null)}
            />
        </div>
    );
}

export default function AdminModelsPage() {
    return (
        <ProtectedRoute>
            <AdminModelsContent />
        </ProtectedRoute>
    );
}


/** Which pair the tuning dialog is open for. */
interface TuningTarget {
    connectionId: number;
    modelId: string;
    modelName: string;
    serverName: string;
}

/**
 * Read and edit one (connection, model) pair's AI settings.
 *
 * WHY THIS LIVES IN THIS FILE. It is a dialog for this page's list, not a component
 * anything else uses, and keeping it here means the page's data shapes stay in one
 * place. If a second surface ever needs it — the user's own connection page is the
 * obvious candidate — it moves out then, with two callers to design against.
 *
 * WHERE THE LABELS COME FROM. The three field labels and the workbench-level refusal
 * already exist on the limits page, and identical fallback text under two keys is a
 * duplicate the linter reports. They are imported rather than redeclared: one string,
 * one key, wherever it is shown. Only the strings this panel alone says — its title,
 * hints, errors and inherited tooltip — are declared under `admin.models`.
 *
 * WHAT IS ALWAYS ENABLED. Save and Cancel are never disabled to pre-empt a mistake.
 * Pressing Save with an empty temperature sends null, which clears the override —
 * each field's own "Clear" does the same for one field. If the caller may not write,
 * the API answers 404 and that message is shown INLINE and stays: a disabled button
 * would have explained nothing.
 *
 * THE LOAD IS A SEPARATE ERROR FROM THE SAVE, in separate state, because "I could not
 * read it" and "I could not write it" are different problems with different fixes.
 */
function ModelTuningDialog({ target, onClose }: { target: TuningTarget | null; onClose: () => void }) {
    const translate = useTranslate();
    const [loading, setLoading] = useState(false);
    const [saving, setSaving] = useState(false);
    const [loadError, setLoadError] = useState<string | null>(null);
    const [saveError, setSaveError] = useState<string | null>(null);
    const [saved, setSaved] = useState(false);

    const [temperature, setTemperature] = useState("");
    const [maxTokens, setMaxTokens] = useState("");
    const [timeoutSeconds, setTimeoutSeconds] = useState("");
    const [inherited, setInherited] = useState<{ temperature: boolean; maxTokens: boolean; timeoutSeconds: boolean }>({
        temperature: true, maxTokens: true, timeoutSeconds: true,
    });

    useEffect(() => {
        if (!target) return;
        let cancelled = false;
        setLoading(true);
        setLoadError(null);
        setSaveError(null);
        setSaved(false);

        (async () => {
            try {
                const res = await apiFetch(
                    `/api/user/model-tuning/${target.connectionId}/${target.modelId}`,
                );
                const data: any = await res.json().catch(() => ({}));
                if (cancelled) return;
                if (!res.ok) {
                    throw new Error(getErrorMessageFromData(translate, data, ADMIN.models.tuning_load_error));
                }
                // Blank, not "0", for an inherited value: the field has to be empty for
                // the reader to see that nothing is set. A 0 temperature would render as
                // "0" and be indistinguishable from one the admin chose.
                setTemperature(data.temperature === null || data.temperature === undefined ? "" : String(data.temperature));
                setMaxTokens(data.maxTokens === null || data.maxTokens === undefined ? "" : String(data.maxTokens));
                setTimeoutSeconds(data.timeoutSeconds === null || data.timeoutSeconds === undefined ? "" : String(data.timeoutSeconds));
                setInherited(data.inherited ?? { temperature: true, maxTokens: true, timeoutSeconds: true });
            } catch (e) {
                if (!cancelled) setLoadError(e instanceof Error ? e.message : String(e));
            } finally {
                if (!cancelled) setLoading(false);
            }
        })();

        return () => { cancelled = true; };
    }, [target, translate]);

    if (!target) return null;

    const field = (label: string, hint: string | null, value: string, set: (v: string) => void, isInherited: boolean, step: string) => (
        <div className="space-y-1">
            <div className="flex items-center gap-2">
                <Label>{label}</Label>
                {isInherited && (
                    <span className="text-[10px] uppercase tracking-wide text-muted-foreground" title={translate(ADMIN.models.tuning_inherited_title)}>
                        {translate(ADMIN.models.tuning_inherited)}
                    </span>
                )}
            </div>
            <Input dir="ltr" type="number" step={step} value={value} onChange={(e) => set(e.target.value)} className="max-w-[160px]" />
            {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
        </div>
    );

    const save = async () => {
        setSaving(true);
        setSaveError(null);
        setSaved(false);
        try {
            // Blank -> null, which clears the override. The server validates; a bad
            // number is refused there with a coded message that is shown below rather
            // than being pre-empted here.
            const body: Record<string, unknown> = {};
            body.temperature = temperature.trim() === "" ? null : Number(temperature);
            body.maxTokens = maxTokens.trim() === "" ? null : Number(maxTokens);
            body.timeoutSeconds = timeoutSeconds.trim() === "" ? null : Number(timeoutSeconds);

            const res = await apiFetch(`/api/user/model-tuning/${target.connectionId}/${target.modelId}`, {
                method: "PATCH",
                body: JSON.stringify(body),
            });
            const data: any = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(getErrorMessageFromData(translate, data, ADMIN.models.tuning_save_error));
            }
            setSaved(true);
            toast.success(translate(ADMIN.models.tuning_saved));
            onClose();
        } catch (e) {
            setSaveError(e instanceof Error ? e.message : String(e));
        } finally {
            setSaving(false);
        }
    };

    return (
        <Dialog open={!!target} onOpenChange={(open) => { if (!open) onClose(); }}>
            <DialogContent className="max-w-md">
                <DialogHeader>
                    <DialogTitle>{translate(ADMIN.models.tuning_title)}</DialogTitle>
                    <DialogDescription>
                        <span className="font-medium">{target.serverName}</span> &middot; {target.modelName}
                    </DialogDescription>
                </DialogHeader>

                {loading ? (
                    <div className="flex items-center gap-2 text-sm text-muted-foreground">
                        <Loader2 className="h-4 w-4 animate-spin" /> {translate(ADMIN.models.tuning_loading)}
                    </div>
                ) : (
                    <div className="space-y-4">
                        <p className="text-xs text-muted-foreground">{translate(ADMIN.models.tuning_hint)}</p>

                        {field(translate(COMMON.ai_temperature_label), translate(ADMIN.models.tuning_temperature_hint), temperature, setTemperature, inherited.temperature, "0.1")}
                        {field(translate(COMMON.ai_max_tokens_label), null, maxTokens, setMaxTokens, inherited.maxTokens, "1")}
                        {field(translate(COMMON.ai_timeout_label), translate(ADMIN.models.tuning_timeout_hint), timeoutSeconds, setTimeoutSeconds, inherited.timeoutSeconds, "1")}

                        {/* Persistent: stays until the next attempt, not a toast. */}
                        {loadError && (
                            <p className="text-sm text-destructive border-l-2 border-destructive pl-2">{loadError}</p>
                        )}
                        {saveError && (
                            <p className="text-sm text-destructive border-l-2 border-destructive pl-2">{saveError}</p>
                        )}
                        {saved && !saveError && (
                            <p className="text-sm text-emerald-600">{translate(ADMIN.models.tuning_saved)}</p>
                        )}
                    </div>
                )}

                {/* Not DialogFooter: this project's dialog module exports Dialog,
                    DialogTrigger, DialogContent, DialogHeader, DialogTitle and
                    DialogDescription only. A plain flex row does the job and does not
                    require widening a shared primitive for one caller. */}
                <div className="flex justify-end gap-2 pt-2">
                    <Button variant="outline" onClick={onClose} type="button">
                        {translate(COMMON.cancel)}
                    </Button>
                    <Button onClick={save} disabled={saving || loading} type="button">
                        {saving ? <Loader2 className="h-4 w-4 animate-spin" /> : translate(COMMON.save)}
                    </Button>
                </div>
            </DialogContent>
        </Dialog>
    );
}
