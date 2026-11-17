"use client";

import { useState, useRef, useEffect } from "react";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { useAI } from "@/lib/ai-context";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { Loader2, Send, Sparkles, Bot, User, Database, Table2, Lock, UserPlus, PlusCircle, ListChecks, Filter } from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";

// Import translations
import { AI } from "../translations";
import { COMMON, NAV } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";
import { DATASETS } from "@/app/datasets/translations";
import AudioToggle from "@/components/audio-toggle";
import AudioSettingsDialog from "@/components/audio-settings-dialog";
import CopyButton from "@/components/copy-button";
import { useSpeechOutput } from "@/hooks/use-speech";
import { useSpeechInput } from "@/hooks/use-speech-input";
import { getCachedSettings, setCachedSettings } from "@/lib/audio-settings";

interface Dataset {
    id: string;
    name: string;
    description: string | null;
    sourceType: string;
    storageType: string | null;
    sourceOrigin?: string | null;
    isShared?: boolean;
    filePath: string | null;
    tableName: string | null;
    isOwn: boolean;
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
}

interface TransformRule {
    id: string;
    name: string;
    description?: string | null;
    operations?: any[];
}

interface AvailableConnection {
    id: string;
    connectionId: number;
    name: string;
    provider: string;
    isOwn: boolean;
}

interface AIModel {
    modelCode: string;
    modelName: string;
}

interface ChatMessage {
    role: "user" | "assistant";
    content: string;
}

function AIDataCleanContent() {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const { defaultConnectionId: defaultAIId } = useAI();

    const [datasets, setDatasets] = useState<Dataset[]>([]);
    const [loadingDatasets, setLoadingDatasets] = useState(true);
    const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
    const [datasetFilter, setDatasetFilter] = useState<string>("all");
    const [schema, setSchema] = useState<DatasetSchema | null>(null);
    const [rules, setRules] = useState<TransformRule[]>([]);
    const [selectedRuleIds, setSelectedRuleIds] = useState<string[]>([]);
    const [loadingSchema, setLoadingSchema] = useState(false);
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [chatId, setChatId] = useState<string | null>(null);
    const [aiConnections, setAIConnections] = useState<AvailableConnection[]>([]);
    const [selectedAIConnectionId, setSelectedAIConnectionId] = useState<string | null>(null);
    const [loadingAIConnections, setLoadingAIConnections] = useState(true);
    const [models, setModels] = useState<AIModel[]>([]);
    const [selectedModelCode, setSelectedModelCode] = useState<string | null>(null);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [summarising, setSummarising] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [schemaError, setSchemaError] = useState<string | null>(null);
    const [speakerEnabled, setSpeakerEnabled] = useState(false);
    const [micEnabled, setMicEnabled] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [speakerMuted, setSpeakerMuted] = useState(false);
    const [userRole, setUserRole] = useState<{ isAdmin: boolean; isGroupAdmin: boolean; isExampleUser: boolean } | null>(null);
    const [cleanName, setCleanName] = useState<string>("");
    const [cleaning, setCleaning] = useState(false);
    const [cleanError, setCleanError] = useState<string | null>(null);
    const [cleanSuccess, setCleanSuccess] = useState<string | null>(null);
    const chatEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    const isExampleUser = userRole?.isExampleUser === true;
    const dismissError = () => setErrorMessage(null);

    // Audio output: speak the last assistant response when speaker is enabled
    const lastAssistantMsg = messages.filter(m => m.role === "assistant").pop()?.content ?? "";
    const { speechOutputError, speechState, pause, resume, stop, volume, setVolume } =
        useSpeechOutput(lastAssistantMsg, speakerEnabled, "dataclean");

    // Audio input: speech-to-text
    const { transcript, speechInputError } = useSpeechInput(micEnabled);

    // Pipe transcript into input field
    useEffect(() => { if (transcript) setInput(transcript); }, [transcript]);

    // Refocus the chat input after any selection (a Select leaves focus on its
    // trigger) and once a send completes and the input is re-enabled.
    useEffect(() => {
        if (!loading && !summarising) inputRef.current?.focus();
    }, [loading, summarising, selectedDatasetId, datasetFilter, selectedAIConnectionId, selectedModelCode]);

    // Handle audio errors
    useEffect(() => { if (speechOutputError) setErrorMessage(speechOutputError); }, [speechOutputError]);
    useEffect(() => { if (speechInputError) setErrorMessage(speechInputError); }, [speechInputError]);

    // Fetch user role
    useEffect(() => {
        apiFetch("/api/user/role")
            .then(res => res.ok ? res.json() : null)
            .then(data => data && setUserRole(data))
            .catch(() => {});
    }, []);

    // Create a stateful data-cleaning session on mount.
    useEffect(() => {
        let cancelled = false;
        const createSession = async () => {
            try {
                const res = await apiFetch("/api/datasets/dataclean/chat", { method: "POST", body: JSON.stringify({}) });
                if (!cancelled && res.ok) {
                    const data = await res.json();
                    setChatId(data.chatId);
                }
            } catch (error) { console.error("Error creating session:", error); }
        };
        createSession();
        return () => { cancelled = true; };
    }, []);

    // Fetch AI connections
    useEffect(() => {
        const fetchAIConnections = async () => {
            try {
                const res = await apiFetch("/api/user/ai-connections/available");
                if (res.ok) {
                    const data = await res.json();
                    setAIConnections(data.connections || []);
                    if (data.connections?.length > 0) setSelectedAIConnectionId(data.connections[0].id);
                }
            } catch (error) { console.error("Error fetching AI connections:", error); }
            finally { setLoadingAIConnections(false); }
        };
        fetchAIConnections();
    }, []);

    // Auto-select default AI connection
    useEffect(() => {
        if (defaultAIId && aiConnections.length > 0) {
            const conn = aiConnections.find(c => c.id === defaultAIId);
            if (conn) setSelectedAIConnectionId(defaultAIId);
        }
    }, [defaultAIId, aiConnections]);

    // Fetch datasets
    useEffect(() => {
        const fetchDatasets = async () => {
            try {
                const res = await apiFetch("/api/datasets");
                if (res.ok) {
                    const data = await res.json();
                    setDatasets(data.datasets || []);
                }
            } catch (error) {
                console.error("Error fetching datasets:", error);
            } finally {
                setLoadingDatasets(false);
            }
        };
        fetchDatasets();
    }, []);

    // Fetch models when AI connection changes
    useEffect(() => {
        if (!selectedAIConnectionId) { setModels([]); setSelectedModelCode(null); return; }
        const fetchModels = async () => {
            try {
                const res = await apiFetch(`/api/user/ai-connections/${selectedAIConnectionId}/models?enabled=true`);
                if (res.ok) {
                    const data = await res.json();
                    setModels(data.models || []);
                    if (data.models?.length > 0) setSelectedModelCode(data.models[0].modelCode);
                }
            } catch (error) { console.error("Error fetching models:", error); }
        };
        fetchModels();
    }, [selectedAIConnectionId]);

    // When a dataset is selected, bind it to the session (proactive summary),
    // then load its schema and preparation rules for the preview panel.
    useEffect(() => {
        if (!selectedDatasetId) {
            setSchema(null);
            setRules([]);
            setSelectedRuleIds([]);
            setSchemaError(null);
            return;
        }
        const loadDataset = async () => {
            setLoadingSchema(true);
            setSchemaError(null);
            try {
                const [schemaRes, rulesRes] = await Promise.all([
                    apiFetch(`/api/datasets/${selectedDatasetId}/schema`),
                    apiFetch(`/api/datasets/${selectedDatasetId}/transforms`),
                ]);
                if (schemaRes.ok) {
                    setSchema(await schemaRes.json());
                } else {
                    const errorData = await schemaRes.json().catch(() => ({}));
                    setSchema(null);
                    setSchemaError(getErrorMessageFromData(translate, errorData, AI.dataclean.schema_error));
                }
                if (rulesRes.ok) {
                    const data = await rulesRes.json();
                    setRules(data.transforms || []);
                    setSelectedRuleIds((data.transforms || []).map((r: TransformRule) => r.id));
                } else {
                    setRules([]);
                    setSelectedRuleIds([]);
                }
                // The schema and its rules are in: the preview is no longer loading.
                // The concierge turn below is what the chat reports as in progress.
                setLoadingSchema(false);
                // Proactive summary turn: bind the dataset and get the concierge's
                // short "shape + issues + plan" reply (only when a session exists).
                if (chatId) {
                    const connId = aiConnections.find(c => c.id === selectedAIConnectionId)?.connectionId;
                    setSummarising(true);
                    try {
                        const selRes = await apiFetch(`/api/datasets/dataclean/chat/${chatId}/dataset-selected`, {
                            method: "POST",
                            body: JSON.stringify({ datasetId: selectedDatasetId, connectionId: connId, model: selectedModelCode || undefined }),
                        });
                        if (selRes.ok) {
                            const data = await selRes.json();
                            setMessages(prev => [...prev, { role: "assistant", content: data.response }]);
                        } else {
                            const errorData = await selRes.json().catch(() => ({}));
                            const msg = getErrorMessageFromData(translate, errorData, AI.dataclean.chat_error);
                            setErrorMessage(msg);
                        }
                    } finally {
                        setSummarising(false);
                    }
                }
            } catch (error) {
                console.error("Error loading dataset:", error);
                setSchema(null);
                setSchemaError(getErrorMessageFromData(translate, null, AI.dataclean.schema_error));
            } finally {
                setLoadingSchema(false);
            }
        };
        loadDataset();
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedDatasetId, chatId]);

    // Auto-scroll chat
    useEffect(() => {
        chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    const datasetCategory = (ds: Dataset): string => {
        const key = ds.sourceOrigin || ds.sourceType;
        if (key === "table" || key === "view") {
            return ds.storageType || "postgresql";
        }
        return key;
    };

    const sourceLabel = (category: string) => {
        switch (category) {
            case "upload": return translate(DATASETS.type.upload);
            case "table": return translate(DATASETS.type.table);
            case "view": return translate(DATASETS.type.view);
            case "virtual": return translate(DATASETS.type.virtual);
            case "notebook": return translate(DATASETS.type.notebook);
            case "postgresql": return translate(DATASETS.type.postgresql);
            case "mysql": return translate(DATASETS.type.mysql);
            case "mssql": return translate(DATASETS.type.mssql);
            case "access": return translate(DATASETS.type.access);
            default: return category;
        }
    };

    const matchesFilter = (ds: Dataset, f: string): boolean => {
        switch (f) {
            case "all": return true;
            case "cleaned": return !!ds.sourceOrigin;
            case "shared": return ds.isShared === true;
            case "not_shared": return ds.isShared !== true;
            default: return datasetCategory(ds) === f;
        }
    };

    const visibleDatasets = datasets.filter((ds) => matchesFilter(ds, datasetFilter));

    const uniqueName = (base: string, list: Dataset[] = datasets): string => {
        const taken = new Set(list.map((d) => d.name));
        if (!taken.has(base)) return base;
        let i = 2;
        while (taken.has(`${base} (${i})`)) i++;
        return `${base} (${i})`;
    };

    // Pre-fill the copy name when the selected dataset changes.
    useEffect(() => {
        const ds = datasets.find(d => d.id === selectedDatasetId);
        setCleanName(ds ? uniqueName(`${ds.name} - cleaned`) : "");
        setCleanError(null);
        setCleanSuccess(null);
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedDatasetId]);

    const toggleRule = (ruleId: string) => {
        setSelectedRuleIds((prev) => (prev.includes(ruleId) ? prev.filter((id) => id !== ruleId) : [...prev, ruleId]));
    };

    const handleClean = async (mode: "copy" | "in_place") => {
        if (!selectedDatasetId) {
            setCleanError(translate(AI.dataclean.no_dataset_selected));
            setCleanSuccess(null);
            return;
        }
        if (selectedRuleIds.length === 0) {
            setCleanError(translate(AI.dataclean.clean_no_rules));
            setCleanSuccess(null);
            return;
        }
        setCleaning(true);
        setCleanError(null);
        setCleanSuccess(null);
        try {
            const body: Record<string, unknown> = { mode, rule_ids: selectedRuleIds };
            if (mode === "copy") {
                const ds = datasets.find(d => d.id === selectedDatasetId);
                body.name = cleanName.trim() || (ds ? uniqueName(`${ds.name} - cleaned`) : "cleaned");
            }
            const res = await apiFetch(`/api/datasets/${selectedDatasetId}/preparation/clean`, {
                method: "POST",
                body: JSON.stringify(body),
            });
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(getErrorMessageFromData(translate, errorData, AI.dataclean.chat_error));
            }
            const data = await res.json();
            if (data.mode === "in_place") {
                setCleanSuccess(translate(AI.dataclean.clean_in_place_success).replace("{name}", data.name));
            } else {
                setCleanSuccess(translate(AI.dataclean.clean_copy_success).replace("{name}", data.name));
            }
            const [rulesRes, datasetsRes] = await Promise.all([
                apiFetch(`/api/datasets/${selectedDatasetId}/transforms`),
                apiFetch("/api/datasets"),
            ]);
            if (rulesRes.ok) {
                const rd = await rulesRes.json();
                setRules(rd.transforms || []);
                setSelectedRuleIds((rd.transforms || []).map((r: TransformRule) => r.id));
            }
            if (datasetsRes.ok) {
                const dd = await datasetsRes.json();
                setDatasets(dd.datasets || []);
                // Reset the copy name to a fresh, unique default for the next clean.
                if (data.mode === "copy") {
                    const src = (dd.datasets || []).find((d: any) => d.id === selectedDatasetId);
                    if (src) setCleanName(uniqueName(`${src.name} - cleaned`, dd.datasets || []));
                }
            }
        } catch (error: any) {
            setCleanError(error.message || translate(AI.dataclean.chat_error));
        } finally {
            setCleaning(false);
        }
    };

    const handleSend = async () => {
        if (loading) return;
        if (!input.trim()) {
            setErrorMessage(translate(AI.dataclean.enter_message));
            return;
        }
        if (!chatId) {
            setErrorMessage(translate(AI.dataclean.chat_error));
            return;
        }

        const userMessage = input.trim();
        setInput("");
        setMessages(prev => [...prev, { role: "user", content: userMessage }]);
        setLoading(true);
        setErrorMessage(null);

        if (!selectedAIConnectionId) {
            setErrorMessage(translate(AI.no_ai_connections));
            toast.error(translate(AI.no_ai_connections));
            setLoading(false);
            return;
        }
        const connId = aiConnections.find(c => c.id === selectedAIConnectionId)?.connectionId;
        if (!connId) { setLoading(false); return; }

        try {
            const res = await apiFetch(`/api/datasets/clean-chat/${chatId}/message`, {
                method: "POST",
                body: JSON.stringify({ message: userMessage, connectionId: connId, model: selectedModelCode || undefined }),
            });

            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                const msg = getErrorMessageFromData(translate, errorData, AI.dataclean.chat_error);
                throw new Error(msg);
            }

            const data = await res.json();
            setMessages(prev => [...prev, { role: "assistant", content: data.response }]);
            if (selectedDatasetId) {
                const rr = await apiFetch(`/api/datasets/${selectedDatasetId}/transforms`);
                if (rr.ok) {
                    const rd = await rr.json();
                    setRules(rd.transforms || []);
                    setSelectedRuleIds((rd.transforms || []).map((r: TransformRule) => r.id));
                }
            }
        } catch (error: any) {
            const msg = error.message || translate(AI.dataclean.chat_error);
            setErrorMessage(msg);
            toast.error(msg);
        } finally {
            setLoading(false);
        }
    };

    const startNewSession = async () => {
        setMessages([]);
        setSelectedDatasetId("");
        setSchema(null);
        setRules([]);
        setInput("");
        setErrorMessage(null);
        setSchemaError(null);
        try {
            const res = await apiFetch("/api/datasets/dataclean/chat", { method: "POST", body: JSON.stringify({}) });
            if (res.ok) {
                const data = await res.json();
                setChatId(data.chatId);
            }
        } catch (error) { console.error("Error creating session:", error); }
    };

    const getConnectionLabel = (conn: AvailableConnection) => {
        const name = conn.name || conn.provider || String(conn.connectionId);
        return conn.isOwn ? `${name} (${conn.provider})` : `* ${name} (${conn.provider})`;
    };

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            handleSend();
        }
    };

    const getColumnTypeBadge = (col: ColumnSchema) => {
        if (col.is_numeric) return "bg-blue-100 text-blue-800";
        if (col.is_datetime) return "bg-purple-100 text-purple-800";
        if (col.is_categorical) return "bg-green-100 text-green-800";
        return "bg-gray-100 text-gray-800";
    };

    const getColumnTypeLabel = (col: ColumnSchema) => {
        if (col.is_numeric) return translate(AI.dataclean.column_type_number);
        if (col.is_datetime) return translate(AI.dataclean.column_type_datetime);
        if (col.is_categorical) return translate(AI.dataclean.column_type_category);
        return translate(AI.dataclean.column_type_text);
    };

    if (!isLanguageLoaded) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    if (isExampleUser) {
        return (
            <div className="max-w-3xl mx-auto py-8">
                <div className="flex items-center gap-4 mb-6">
                    <h1 className="text-3xl font-bold flex items-center gap-2">
                        <Sparkles className="h-8 w-8" />
                        {translate(AI.dataclean.title)}
                    </h1>
                </div>
                <div className="p-6 bg-orange-50 border border-orange-200 rounded-md text-orange-800 text-center mb-6">
                    <Lock className="h-10 w-10 mx-auto mb-3 text-orange-600" />
                    <p className="text-sm mb-4">{translate(COMPONENTS.readonly_wrapper)}</p>
                    <Link href="/register">
                        <Button>
                            <UserPlus className="h-4 w-4 me-2" />
                            {translate(COMPONENTS.example_user_banner.register_button)}
                        </Button>
                    </Link>
                </div>
                <Card>
                    <CardContent className="pt-6">
                        <div className="space-y-4 opacity-60">
                            <p className="text-muted-foreground">{translate(AI.dataclean.description)}</p>
                        </div>
                    </CardContent>
                </Card>
            </div>
        );
    }

    return (
        <div className="dataclean-layout">
            {/* The recipe page's fill: the layout owns a fixed height instead of the page scrolling,
                so the chat takes what is left rather than being held to 600px. The controls keep
                their labels; the page heading is gone, because the nav already names the page. */}
            <style>{`
                .dataclean-layout {
                    display: flex;
                    flex-direction: column;
                    height: calc(100vh - 64px);
                    overflow: hidden;
                }
                .dataclean-layout > .dataclean-row {
                    flex: 1;
                    min-height: 0;
                    display: flex;
                    gap: 1.5rem;
                    padding: 0 1.5rem 1.5rem;
                }
                .dataclean-layout > .dataclean-row > .dataclean-chat {
                    flex: 1;
                    min-width: 0;
                    display: flex;
                    flex-direction: column;
                    gap: 1rem;
                    overflow: hidden;
                }
                .dataclean-layout > .dataclean-row > .dataclean-side {
                    width: 20rem;
                    flex-shrink: 0;
                    overflow: auto;
                }
                @media (max-width: 1023px) {
                    .dataclean-layout { height: auto; overflow: visible; }
                    .dataclean-layout > .dataclean-row { flex-direction: column; }
                    .dataclean-layout > .dataclean-row > .dataclean-side { width: 100%; }
                }
            `}</style>

            <div className="dataclean-row">
                {/* Preview panel (rules + data preview) */}
                <div className="dataclean-side space-y-4">
                    {/* The column's heading, reusing the nav's own key rather than adding one: it is
                        the same two words, and it is already translated everywhere. */}
                    <h2 className="text-sm font-semibold text-muted-foreground">
                        {translate(NAV.ai_dataset_cleaning)}
                    </h2>
                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm flex items-center gap-2">
                                <ListChecks className="h-4 w-4" />
                                {translate(AI.dataclean.rules_title)}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-1.5 text-sm">
                            {rules.length === 0 ? (
                                <p className="text-muted-foreground">{translate(AI.dataclean.no_rules)}</p>
                            ) : (
                                rules.map((rule) => {
                                    const isSelected = selectedRuleIds.includes(rule.id);
                                    return (
                                        <div key={rule.id} className="border-b border-border pb-1.5 last:border-0 last:pb-0">
                                            <label className="flex items-start gap-2 cursor-pointer">
                                                <input
                                                    type="checkbox"
                                                    checked={isSelected}
                                                    onChange={() => toggleRule(rule.id)}
                                                    className="mt-1 h-3.5 w-3.5 accent-primary"
                                                />
                                                <div className="min-w-0">
                                                    <div className="font-medium">{rule.name}</div>
                                                    <div className="text-xs text-muted-foreground">
                                                        {translate(AI.dataclean.operations_count).replace("{count}", String((rule.operations || []).length))}
                                                    </div>
                                                </div>
                                            </label>
                                        </div>
                                    );
                                })
                            )}

                            {selectedDatasetId && (
                                <div className="pt-3 mt-2 border-t border-border space-y-2">
                                    <div>
                                        <Label htmlFor="clean-name" className="text-xs text-muted-foreground">
                                            {translate(AI.dataclean.clean_name_label)}
                                        </Label>
                                        <Input
                                            id="clean-name"
                                            value={cleanName}
                                            onChange={(e) => setCleanName(e.target.value)}
                                            className="mt-1 h-8"
                                        />
                                    </div>
                                    <div className="flex gap-2">
                                        <Button variant="outline" size="sm" className="flex-1" onClick={() => handleClean("copy")} disabled={cleaning}>
                                            {translate(AI.dataclean.clean_copy)}{selectedRuleIds.length > 0 ? ` (${selectedRuleIds.length})` : ""}
                                        </Button>
                                        <Button variant="outline" size="sm" className="flex-1" onClick={() => handleClean("in_place")} disabled={cleaning}>
                                            {translate(AI.dataclean.clean_in_place)}
                                        </Button>
                                    </div>
                                    {cleaning && (
                                        <div className="flex items-center gap-2 text-muted-foreground">
                                            <Loader2 className="h-3 w-3 animate-spin" />
                                            {translate(COMMON.loading)}
                                        </div>
                                    )}
                                    {cleanError && <p className="text-red-700">{cleanError}</p>}
                                    {cleanSuccess && <p className="text-green-700">{cleanSuccess}</p>}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="pb-2">
                            <CardTitle className="text-sm flex items-center gap-2">
                                <Table2 className="h-4 w-4" />
                                {translate(AI.dataclean.preview_title)}
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-1.5">
                            {!selectedDatasetId && (
                                <p className="text-muted-foreground text-sm">{translate(AI.dataclean.no_dataset_selected)}</p>
                            )}
                            {selectedDatasetId && loadingSchema && (
                                <div className="flex items-center gap-2 text-sm text-progress">
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                    {translate(AI.dataclean.loading_schema)}
                                </div>
                            )}
                            {selectedDatasetId && schema && !loadingSchema && (
                                <>
                                    <div className="text-sm">
                                        <span className="font-medium">
                                            {translate(AI.dataclean.schema_summary)
                                                .replace("{rows}", String(schema.total_rows))
                                                .replace("{cols}", String(schema.total_columns))}
                                        </span>
                                    </div>
                                    <div className="flex flex-wrap gap-1.5">
                                        {schema.columns.map((col) => (
                                            <span
                                                key={col.name}
                                                className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${getColumnTypeBadge(col)}`}
                                                title={translate(AI.dataclean.column_tooltip).replace("{type}", getColumnTypeLabel(col)).replace("{null_count}", String(col.null_count)).replace("{unique_count}", String(col.unique_count))}
                                            >
                                                {col.name}
                                            </span>
                                        ))}
                                    </div>
                                </>
                            )}
                            {selectedDatasetId && schemaError && !loadingSchema && (
                                <p className="text-sm text-red-700">{schemaError}</p>
                            )}
                        </CardContent>
                    </Card>
                </div>
                {/* Chat column */}
                <div className="dataclean-chat">
                    {/* Controls: AI connection / model / new session / dataset.
                        A flush band rather than a Card: a Card's rounded box and its 12px inner top
                        inset are what put this page's first line lower than the chat pages that use
                        a header band instead. */}
                    <div className="flex-shrink-0 border-b border-border bg-card px-3 py-2 space-y-3">
                            <div className="flex flex-col sm:flex-row gap-2 items-end">
                                <div className="flex-1 w-full">
                                    <Label>{translate(AI.select_ai_connection)}</Label>
                                    <Select
                                        value={selectedAIConnectionId || ""}
                                        onValueChange={(val) => setSelectedAIConnectionId(val || null)}
                                        disabled={loadingAIConnections}
                                    >
                                        <SelectTrigger className="mt-1">
                                            <SelectValue placeholder={translate(AI.select_ai_connection_placeholder)}>
                                                {selectedAIConnectionId !== null
                                                    ? getConnectionLabel(aiConnections.find(c => c.id === selectedAIConnectionId)!)
                                                    : ""}
                                            </SelectValue>
                                        </SelectTrigger>
                                        <SelectContent>
                                            {aiConnections.map((conn) => (
                                                <SelectItem key={conn.id} value={conn.id}>
                                                    {getConnectionLabel(conn)}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="w-full sm:w-48">
                                    <Label>{translate(AI.select_model)}</Label>
                                    <Select
                                        value={selectedModelCode || ""}
                                        onValueChange={(val) => setSelectedModelCode(val || null)}
                                        disabled={!selectedAIConnectionId || models.length === 0}
                                    >
                                        <SelectTrigger className="mt-1">
                                            <SelectValue placeholder={translate(AI.select_model_placeholder)}>
                                                {selectedModelCode !== null
                                                    ? (models.find(m => m.modelCode === selectedModelCode)?.modelName || selectedModelCode)
                                                    : ""}
                                            </SelectValue>
                                        </SelectTrigger>
                                        <SelectContent>
                                            {models.map((m) => (
                                                <SelectItem key={m.modelCode} value={m.modelCode}>
                                                    {m.modelName || m.modelCode}
                                                </SelectItem>
                                            ))}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <Button variant="outline" size="sm" onClick={startNewSession} className="flex-shrink-0">
                                    <PlusCircle className="h-4 w-4 me-1" />
                                    {translate(AI.new_session)}
                                </Button>
                            </div>
                            {!loadingAIConnections && aiConnections.length === 0 && (
                                <p className="text-sm text-amber-600">
                                    {translate(AI.no_ai_connections)}
                                </p>
                            )}

                            <div className="flex items-end gap-2">
                                <div className="flex-1 w-full">
                                    <Select
                                        value={selectedDatasetId}
                                        onValueChange={(value) => setSelectedDatasetId(value || "")}
                                        disabled={loadingDatasets}
                                    >
                                        <SelectTrigger id="dataset-select" className="mt-1 w-full">
                                            <SelectValue placeholder={translate(AI.dataclean.select_dataset_placeholder)}>
                                                {selectedDatasetId ? (datasets.find(ds => ds.id === selectedDatasetId)?.name || selectedDatasetId) : null}
                                            </SelectValue>
                                        </SelectTrigger>
                                        <SelectContent>
                                            {visibleDatasets.map((ds) => (
                                                <SelectItem key={ds.id} value={ds.id}>
                                                    <span className="flex items-center gap-2">
                                                        <Database className="h-3 w-3" />
                                                        {ds.name}
                                                        {ds.sourceType && (
                                                            <span className="text-xs text-muted-foreground">[{sourceLabel(datasetCategory(ds))}]</span>
                                                        )}
                                                        {!ds.isOwn && (
                                                            <span className="text-xs text-muted-foreground">{translate(AI.dataclean.shared_badge)}</span>
                                                        )}
                                                    </span>
                                                </SelectItem>
                                            ))}
                                            {visibleDatasets.length === 0 && (
                                                <SelectItem value="__none__" disabled>
                                                    {translate(DATASETS.filter.no_match)}
                                                </SelectItem>
                                            )}
                                        </SelectContent>
                                    </Select>
                                </div>
                                <div className="flex items-center gap-2">
                                    <Filter className="h-4 w-4 text-muted-foreground" />
                                    <Select value={datasetFilter} onValueChange={(value) => setDatasetFilter(value || "all")}>
                                        <SelectTrigger className="w-44">
                                            <SelectValue placeholder={translate(DATASETS.filter.all)} />
                                        </SelectTrigger>
                                        <SelectContent alignItemWithTrigger={false}>
                                            <SelectItem value="all">{translate(DATASETS.filter.all)}</SelectItem>
                                            <SelectItem value="virtual">{translate(DATASETS.filter.virtual)}</SelectItem>
                                            <SelectItem value="upload">{translate(DATASETS.filter.uploads)}</SelectItem>
                                            <SelectItem value="notebook">{translate(DATASETS.filter.notebooks)}</SelectItem>
                                            <SelectItem value="postgresql">{translate(DATASETS.filter.postgresql)}</SelectItem>
                                            <SelectItem value="mysql">{translate(DATASETS.filter.mysql)}</SelectItem>
                                            <SelectItem value="mssql">{translate(DATASETS.filter.mssql)}</SelectItem>
                                            <SelectItem value="access">{translate(DATASETS.filter.access)}</SelectItem>
                                            <SelectItem value="cleaned">{translate(DATASETS.filter.cleaned)}</SelectItem>
                                            <SelectItem value="shared">{translate(DATASETS.filter.shared)}</SelectItem>
                                            <SelectItem value="not_shared">{translate(DATASETS.filter.not_shared)}</SelectItem>
                                        </SelectContent>
                                    </Select>
                                </div>
                            </div>
                            {loadingDatasets && (
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <Loader2 className="h-3 w-3 animate-spin" />
                                    {translate(COMMON.loading)}
                                </div>
                            )}
                            {!loadingDatasets && datasets.length === 0 && (
                                <p className="text-sm text-muted-foreground">
                                    {translate(AI.dataclean.no_datasets)}
                                </p>
                            )}
                    </div>

                    {/* Chat - no card chrome, as on the other chat pages: the messages take the
                        height and the input row is pinned below by its own top border */}
                    <div className="flex-1 min-h-0 flex flex-col overflow-hidden">
                        <div className="flex-1 overflow-y-auto pt-4 pb-2 space-y-4">
                            {messages.length === 0 && !loading && (
                                <div className="flex items-center justify-center h-full py-12 text-muted-foreground">
                                    <p>{translate(AI.dataclean.empty_chat)}</p>
                                </div>
                            )}

                            {messages.map((msg, index) => (
                                <div
                                    key={index}
                                    className={`flex gap-3 ${msg.role === "user" ? "justify-end" : "justify-start"}`}
                                >
                                    {msg.role === "assistant" && (
                                        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                                            <Bot className="h-4 w-4" />
                                        </div>
                                    )}
                                    <div className="relative max-w-[80%]">
                                        <div
                                            className={`rounded-lg px-4 py-2 text-sm ${
                                                msg.role === "user"
                                                    ? "bg-primary text-primary-foreground"
                                                    : "bg-muted"
                                            }`}
                                        >
                                            <div className="whitespace-pre-wrap">{msg.content}</div>
                                        </div>
                                        <div className="absolute -bottom-3 -right-2">
                                            <CopyButton text={msg.content} />
                                        </div>
                                    </div>
                                    {msg.role === "user" && (
                                        <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/20 flex items-center justify-center">
                                            <User className="h-4 w-4" />
                                        </div>
                                    )}
                                </div>
                            ))}

                            {(loading || summarising) && (
                                <div className="flex gap-3 justify-start">
                                    <div className="flex-shrink-0 w-8 h-8 rounded-full bg-primary/10 flex items-center justify-center">
                                        <Bot className="h-4 w-4" />
                                    </div>
                                    <div className="max-w-[80%] rounded-lg px-4 py-2 text-sm bg-muted">
                                        <div className="flex items-center gap-2 text-progress">
                                            <Loader2 className="h-3 w-3 animate-spin" />
                                            {translate(AI.thinking)}
                                        </div>
                                    </div>
                                </div>
                            )}

                            <div ref={chatEndRef} />
                        </div>

                        {/* persistent error — pinned above the input so it stays in view */}
                        {errorMessage && (
                            <div className="px-3 py-2 bg-red-50 border-t border-red-200 text-red-800 flex justify-between items-center">
                                <span className="text-sm">{errorMessage}</span>
                                <Button variant="ghost" size="sm" onClick={dismissError} className="text-red-600 hover:text-red-800">
                                    ✕
                                </Button>
                            </div>
                        )}

                        <div className="border-t p-3">
                            <div className="flex gap-2 items-center">
                                <AudioToggle
                                    micEnabled={micEnabled} onMicChange={setMicEnabled}
                                    speakerEnabled={speakerEnabled} onSpeakerChange={setSpeakerEnabled}
                                    volume={volume} onVolumeChange={setVolume}
                                    speakerMuted={speakerMuted}
                                    onSpeakerMuteToggle={() => { const next = !speakerMuted; setSpeakerMuted(next); setSpeakerEnabled(!next); const s = getCachedSettings("dataclean"); s.speakerMuted = next; setCachedSettings("dataclean", s); }}
                                    speechState={speechState} onPause={pause} onResume={resume} onStop={stop}
                                    onSettingsClick={() => setSettingsOpen(true)}
                                />
                                <Input dir="auto"
                                    ref={inputRef}
                                    autoFocus
                                    value={input}
                                    onChange={(e) => setInput(e.target.value)}
                                    onKeyDown={handleKeyDown}
                                    placeholder={translate(AI.dataclean.chat_placeholder)}
                                    disabled={loading}
                                    className="flex-1"
                                />
                                <Button onClick={handleSend} disabled={loading} size="icon">
                                    {loading ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        <Send className="h-4 w-4" />
                                    )}
                                </Button>
                            </div>
                        </div>
                    </div>
                </div>

            </div>

            <AudioSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} chatType="dataclean" />
        </div>
    );
}

export default function AIDataCleanPage() {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();

    if (!isLanguageLoaded) {
        return (
            <div className="flex items-center justify-center h-screen">
                <div className="text-center">
                    <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
                    <p className="mt-2 text-sm text-muted-foreground">{translate(COMMON.loading)}</p>
                </div>
            </div>
        );
    }

    return (
        <ProtectedRoute>
            <AIDataCleanContent />
        </ProtectedRoute>
    );
}
