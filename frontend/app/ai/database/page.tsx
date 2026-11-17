"use client";

import { useState, useEffect, useCallback } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { useAI } from "@/lib/ai-context";
import { useDB } from "@/lib/db-context";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import {
    DropdownMenu,
    DropdownMenuContent,
    DropdownMenuItem,
    DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import {
    Database, ChevronDown, AlertTriangle, CheckCircle2,
    Info, Search, Table2, Key, Type, Hash, ExternalLink,
    Loader2, FileDown, Mail, Globe, PlusCircle,
    TrendingUp, BrainCircuit, GitMerge
} from "lucide-react";
import { toast } from "sonner";
import Link from "next/link";
import AudioToggle from "@/components/audio-toggle";
import AudioSettingsDialog from "@/components/audio-settings-dialog";
import CopyButton from "@/components/copy-button";
import { useSpeechOutput } from "@/hooks/use-speech";
import { useSpeechInput } from "@/hooks/use-speech-input";
import { getCachedSettings, setCachedSettings } from "@/lib/audio-settings";

// Import translations
import { AI } from "../translations";
import { COMMON } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";
import { formatTime } from "@/lib/date-format";

interface DBConnection {
    id: string;
    connectionId: number;
    name: string;
    type: string;
    host: string;
    database: string;
    isOwn: boolean;
}

interface ColumnInfo {
    name: string;
    type: string;
    max_length: number | null;
    nullable: boolean;
    default: string | null;
    position: number;
}

interface FKInfo {
    column: string;
    referenced_table: string;
    referenced_column: string;
}

interface IndexInfo {
    name: string;
    definition: string;
    is_primary_key: boolean;
}

interface TableInfo {
    schema: string;
    name: string;
    comment: string | null;
    columns: ColumnInfo[];
    primary_key: string[];
    foreign_keys: FKInfo[];
    indexes: IndexInfo[];
    row_count: number;
}

interface AnalysisIssue {
    category: string;
    severity: string;
    risk: string;
    table: string;
    column?: string;
    message: string;
    recommendation: string;
}

interface SemiStructuredFinding {
    schema: string;
    table: string;
    column: string;
    sample_count: number;
    has_key_value_pairs?: boolean;
    separator?: string;
    code_systems?: { name: string; domain: string; confidence: number }[];
    keywords?: Record<string, number>;
    unique_keywords?: number;
    categories?: Record<string, string[]>;
    reference_table_potential?: {
        type: string;
        confidence: number;
        description: string;
        recommendation: string;
    };
}

interface AnalysisReport {
    connection_id: number;
    connection_name?: string;
    database_name?: string;
    database_type: string;
    schema: {
        tables: TableInfo[];
        total_tables: number;
        total_columns: number;
        _warnings?: string[];
    };
    analysis: {
        total_issues: number;
        high: number;
        medium: number;
        low: number;
        issues: AnalysisIssue[];
    };
    summary: {
        total_tables: number;
        total_columns: number;
        total_rows: number;
        issue_count: number;
        risk_summary: { high: number; medium: number; low: number };
        top_recommendations: string[];
    };
    semi_structured?: {
        total_text_columns: number;
        columns_with_findings: number;
        findings: SemiStructuredFinding[];
    };
    // AI-augmented sections (available when use_ai=true)
    ai_status?: string;
    health?: {
        score: number;
        top_actions: string[];
    };
    semantic?: {
        columns: { name: string; table: string; meaning: string; confidence: string }[];
        code_systems: { column: string; table: string; system: string; confidence: string }[];
        domains: { table: string; domains: string[]; confidence: string }[];
        table_purposes: { table: string; purpose: string }[];
    } | null;
    integration?: {
        implicit_relationships: { from_table: string; from_column: string; to_table: string; to_column: string; evidence: string; proposed_ddl?: string; confidence: string }[];
        research_capabilities: { study_type: string; supported: boolean; confidence: string; rationale: string }[];
        missing_dimensions: { table: string; missing_feature: string; peer_tables: string[]; likely_explanation?: string }[];
    } | null;

    normalisation_suggestions?: {
        confidence: number;
        description: string;
        business_value?: string;
        proposed_table?: {
            name: string;
            columns: { name: string; type: string; nullable: boolean; default?: string }[];
        };
        proposed_migration?: string;
    }[];
}

async function getToken(): Promise<string> {
    const res = await fetch("/api/auth/token", { credentials: "include" });
    if (!res.ok) throw new Error("Unauthorized");
    const data = await res.json();
    if (!data.token) throw new Error("No token in response");
    return data.token;
}

function DBDatabaseContent() {
    const router = useRouter();
    const { isLanguageLoaded, language } = useTranslation();
    const translate = useTranslate();
    const { defaultConnectionId: defaultAIId } = useAI();
    const { defaultConnectionId: defaultDBId } = useDB();

    // AI connection/model selectors
    const [aiConnections, setAIConnections] = useState<{id: string; connectionId: number; name: string; provider: string; isOwn: boolean}[]>([]);
    const [selectedAIConnectionId, setSelectedAIConnectionId] = useState<string | null>(null);
    const [loadingAIConnections, setLoadingAIConnections] = useState(true);
    const [models, setModels] = useState<{modelCode: string; modelName: string}[]>([]);
    const [selectedModelCode, setSelectedModelCode] = useState<string | null>(null);

    const getAIConnectionLabel = (conn: {name: string; provider: string; connectionId: number; isOwn: boolean}) => {
        const name = conn.name || conn.provider || String(conn.connectionId);
        return conn.isOwn ? `${name} (${conn.provider})` : `* ${name} (${conn.provider})`;
    };

    // DB connections
    const [connections, setConnections] = useState<DBConnection[]>([]);
    const [loadingConns, setLoadingConns] = useState(true);
    const [selectedConnection, setSelectedConnection] = useState<DBConnection | null>(null);
    const [analyzing, setAnalyzing] = useState(false);
    const [report, setReport] = useState<AnalysisReport | null>(null);
    const [expandedTables, setExpandedTables] = useState<Set<string>>(new Set());
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [showIssues, setShowIssues] = useState(true);
    const [logEntries, setLogEntries] = useState<{message: string; phase: string; ts: number}[]>([]);

    // RAG state
    const [ragQuestion, setRagQuestion] = useState("");
    const [ragAnswer, setRagAnswer] = useState("");
    const [ragSources, setRagSources] = useState<{text: string; source: string}[]>([]);
    const [ragLoading, setRagLoading] = useState(false);
    const [speakerEnabled, setSpeakerEnabled] = useState(false);
    const [micEnabled, setMicEnabled] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [speakerMuted, setSpeakerMuted] = useState(false);

    // Report language selector state — independent of page language
    const [reportLanguage, setReportLanguage] = useState<string>(language);
    const [reportTranslations, setReportTranslations] = useState<Record<string, string>>({});

    // Fetch translations for the report language when it changes
    useEffect(() => {
        fetch(`/api/translations?language=${reportLanguage}`)
            .then(res => res.json())
            .then(data => setReportTranslations(data))
            .catch(() => setReportTranslations({}));
    }, [reportLanguage]);

    // Helper to translate a key using report translations, falling back to page translate
    const reportT = (translation: { key: string; fallback: string }): string => {
        return reportTranslations[translation.key] || translate(translation);
    };

    // Language selector dropdown state
    const [langDropdownOpen, setLangDropdownOpen] = useState(false);
    const [languages, setLanguages] = useState<{code: string; name: string}[]>([]);

    useEffect(() => {
        fetch(`/api/languages?viewer=${language}`)
            .then(res => res.json())
            .then(data => setLanguages(data))
            .catch(console.error);
    }, []);

    // Fetch AI connections
    useEffect(() => {
        apiFetch("/api/user/ai-connections/available")
            .then(res => res.ok ? res.json() : null)
            .then(data => {
                if (data?.connections) {
                    setAIConnections(data.connections);
                    if (data.connections.length > 0) setSelectedAIConnectionId(data.connections[0].id);
                }
            })
            .catch(console.error)
            .finally(() => setLoadingAIConnections(false));
    }, []);

    // Auto-select default AI connection
    useEffect(() => {
        if (defaultAIId && aiConnections.length > 0) {
            const conn = aiConnections.find(c => c.id === defaultAIId);
            if (conn) setSelectedAIConnectionId(defaultAIId);
        }
    }, [defaultAIId, aiConnections]);

    // Fetch models when AI connection changes
    useEffect(() => {
        if (!selectedAIConnectionId) { setModels([]); setSelectedModelCode(null); return; }
        apiFetch(`/api/user/ai-connections/${selectedAIConnectionId}/models?enabled=true`)
            .then(res => res.ok ? res.json() : null)
            .then(data => {
                if (data?.models) {
                    setModels(data.models);
                    if (data.models.length > 0) setSelectedModelCode(data.models[0].modelCode);
                }
            })
            .catch(console.error);
    }, [selectedAIConnectionId]);

    const dismissError = () => setErrorMessage(null);

    // Audio output for RAG responses
    const { speechOutputError, speechState, pause, resume, stop, volume, setVolume } =
        useSpeechOutput(ragAnswer, speakerEnabled, "database");

    // Audio input: speech-to-text for RAG question
    const { transcript, speechInputError } = useSpeechInput(micEnabled);

    // Pipe transcript into RAG input field
    useEffect(() => { if (transcript) setRagQuestion(prev => prev + " " + transcript); }, [transcript]);

    // Handle audio errors
    useEffect(() => { if (speechOutputError) setErrorMessage(speechOutputError); }, [speechOutputError]);
    useEffect(() => { if (speechInputError) setErrorMessage(speechInputError); }, [speechInputError]);

    // Fetch database connections
    const fetchConnections = useCallback(async () => {
        try {
            setLoadingConns(true);
            const res = await apiFetch("/api/user/database-connections/available");
            if (res.ok) {
                const data = await res.json();
                setConnections(data.connections || []);
            }
        } catch (error) {
            console.error("Error fetching connections:", error);
        } finally {
            setLoadingConns(false);
        }
    }, []);

    useEffect(() => {
        fetchConnections();
    }, [fetchConnections]);

    // Auto-select default database connection
    useEffect(() => {
        if (defaultDBId && connections.length > 0) {
            const conn = connections.find(c => c.id === defaultDBId);
            if (conn) setSelectedConnection(conn);
        }
    }, [defaultDBId, connections]);

    // Run analysis with SSE streaming progress (fetch + ReadableStream)
    const handleAnalyze = async () => {
        if (!selectedConnection) return;
        setAnalyzing(true);
        setErrorMessage(null);
        setReport(null);
        setLogEntries([]);

        const addLog = (message: string, phase: string) => {
            setLogEntries(prev => [...prev, { message, phase, ts: Date.now() }]);
        };

        const controller = new AbortController();
        const timeoutId = setTimeout(() => {
            controller.abort();
            addLog(translate(AI.database.timeout_log), "error");
            setAnalyzing(false);
            setErrorMessage(translate(AI.database.timeout_error));
        }, 900_000);

        try {
            const token = await getToken();
            const aiConnId = aiConnections.find(c => c.id === selectedAIConnectionId)?.connectionId;
            const params = new URLSearchParams({
                token,
                use_ai: String(!!selectedAIConnectionId),
                language: reportLanguage,
            });
            if (aiConnId) params.set("ai_connection_id", String(aiConnId));
            if (selectedModelCode) params.set("model", selectedModelCode);

            const url = `/api/dbdesign/analyze/${selectedConnection.connectionId}/stream?${params}`;
            const res = await fetch(url, { signal: controller.signal });

            if (!res.ok) {
                throw new Error(`Server returned ${res.status}`);
            }

            const reader = res.body?.getReader();
            if (!reader) throw new Error("No response body");

            const decoder = new TextDecoder();
            let buffer = "";

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;

                buffer += decoder.decode(value, { stream: true });
                const lines = buffer.split("\n");
                buffer = lines.pop() || "";

                for (const line of lines) {
                    if (line.startsWith("data: ")) {
                        try {
                            const data = JSON.parse(line.slice(6));
                            if (data.event === "complete") {
                                clearTimeout(timeoutId);
                                const reportData = data.report;
                                if (reportData.analysis?.issues && !Array.isArray(reportData.analysis.issues)) {
                                    const wrapped = reportData.analysis.issues as any;
                                    reportData.analysis.total_issues = wrapped.total ?? wrapped.items?.length ?? 0;
                                    reportData.analysis.issues = wrapped.items ?? [];
                                }
                                setReport(reportData);
                                setAnalyzing(false);
                                addLog(data.message || "Analysis complete", "complete");
                            } else if (data.event === "ai_skipped") {
                                addLog(data.message, "warning");
                            } else if (data.event === "error") {
                                clearTimeout(timeoutId);
                                setAnalyzing(false);
                                setErrorMessage(data.message);
                                addLog(data.message, "error");
                                toast.error(data.message);
                            } else {
                                addLog(data.message, data.phase || "status");
                            }
                        } catch {
                            // ignore parse errors
                        }
                    }
                }
            }
        } catch (error: any) {
            if (error.name !== "AbortError") {
                setAnalyzing(false);
                const msg = error.message || translate(AI.database.schema_error);
                setErrorMessage(msg);
                addLog(msg, "error");
                toast.error(msg);
            }
        } finally {
            clearTimeout(timeoutId);
        }
    };

    // Download PDF
    const handleDownloadPdf = async () => {
        if (!report) return;
        try {
            const res = await apiFetch("/api/dbdesign/export-pdf", {
                method: "POST",
                body: JSON.stringify({ report, language: reportLanguage }),
            });
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(getErrorMessageFromData(translate, errorData, AI.database.pdf_error));
            }
            const blob = await res.blob();
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement("a");
            a.href = url;
            a.download = `database-analysis-${report.connection_id}.pdf`;
            a.click();
            window.URL.revokeObjectURL(url);
            toast.success(translate(AI.database.pdf_downloaded));
        } catch (error: any) {
            const msg = error.message || translate(AI.database.pdf_error);
            setErrorMessage(msg);
            toast.error(msg);
        }
    };

    // Email PDF
    const handleEmailPdf = async () => {
        if (!report) return;
        try {
            const res = await apiFetch("/api/dbdesign/email-pdf", {
                method: "POST",
                body: JSON.stringify({ report, language: reportLanguage }),
            });
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(getErrorMessageFromData(translate, errorData, AI.database.email_error));
            }
            toast.success(translate(AI.database.email_sent));
        } catch (error: any) {
            const msg = error.message || translate(AI.database.email_error);
            setErrorMessage(msg);
            toast.error(msg);
        }
    };

    // RAG Query
    const handleRagQuery = async () => {
        if (!selectedConnection) {
            setErrorMessage(translate(AI.database.select_connection_first));
            return;
        }
        if (!ragQuestion.trim()) {
            setErrorMessage(translate(AI.database.enter_question));
            return;
        }
        try {
            setRagLoading(true);
            setRagAnswer("");
            setRagSources([]);
            const res = await apiFetch(`/api/dbdesign/rag-query/${selectedConnection.connectionId}`, {
                method: "POST",
                body: JSON.stringify({
                    question: ragQuestion,
                    ai_connection_id: aiConnections.find(c => c.id === selectedAIConnectionId)?.connectionId,
                    model: selectedModelCode || undefined,
                }),
            });
            if (!res.ok) {
                const errorData = await res.json().catch(() => ({}));
                throw new Error(getErrorMessageFromData(translate, errorData, AI.database.rag_error));
            }
            const data = await res.json();
            setRagAnswer(data.answer || translate(COMMON.no_answer));
            setRagSources(data.sources || []);
        } catch (error: any) {
            const msg = error.message || translate(AI.database.rag_error);
            toast.error(msg);
            setErrorMessage(msg);
        } finally {
            setRagLoading(false);
        }
    };

    const toggleTable = (tableName: string) => {
        const next = new Set(expandedTables);
        if (next.has(tableName)) {
            next.delete(tableName);
        } else {
            next.add(tableName);
        }
        setExpandedTables(next);
    };

    const severityColor = (sev: string) => {
        switch (sev) {
            case "CRITICAL": return "text-red-700 bg-red-50 border-red-200";
            case "HIGH": return "text-orange-700 bg-orange-50 border-orange-200";
            case "MEDIUM": return "text-yellow-700 bg-yellow-50 border-yellow-200";
            case "LOW": return "text-blue-700 bg-blue-50 border-blue-200";
            default: return "text-gray-700 bg-gray-50 border-gray-200";
        }
    };

    const categoryIcon = (cat: string) => {
        switch (cat) {
            case "indexing": return <Search className="h-4 w-4" />;
            case "normalisation": return <Table2 className="h-4 w-4" />;
            case "relationships": return <ExternalLink className="h-4 w-4" />;
            case "data_types": return <Type className="h-4 w-4" />;
            case "naming": return <Hash className="h-4 w-4" />;
            default: return <Info className="h-4 w-4" />;
        }
    };

    if (!isLanguageLoaded || loadingConns) {
        return (
            <div className="flex items-center justify-center h-64">
                <div className="text-center">
                    <Loader2 className="animate-spin h-8 w-8 mx-auto mb-2" />
                    <p className="text-sm text-muted-foreground">{translate(COMMON.loading)}</p>
                </div>
            </div>
        );
    }

    return (
        <div className="max-w-5xl mx-auto space-y-6">
            {/* Header */}
            <div>
                <h1 className="text-3xl font-bold flex items-center gap-2">
                    <Database className="h-7 w-7" />
                    {translate(AI.database.title)}
                </h1>
                <p className="text-sm text-muted-foreground mt-1">
                    {translate(AI.database.description)}
                </p>
            </div>

            {/* Error */}
            {errorMessage && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
                    <span className="text-sm">{errorMessage}</span>
                    <button onClick={dismissError} className="text-red-500 hover:text-red-700">
                        &times;
                    </button>
                </div>
            )}

            {/* Top Card: AI Connection / Model / DB Connection / Analyze */}
            <Card>
                <CardContent className="pt-3 pb-2 space-y-3">
                    {/* Row 1: AI connection + model + new session */}
                    <div className="flex flex-col sm:flex-row gap-2 items-end">
                        <div className="flex-1 w-full">
                            <label className="text-sm font-medium mb-2 block">
                                {translate(AI.select_ai_connection)}
                            </label>
                            <select
                                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                value={selectedAIConnectionId || ""}
                                onChange={(e) => setSelectedAIConnectionId(e.currentTarget.value || null)}
                                disabled={loadingAIConnections}
                            >
                                <option value="">{translate(AI.select_ai_connection_placeholder)}</option>
                                {aiConnections.map((conn) => (
                                    <option key={conn.id} value={conn.id}>
                                        {getAIConnectionLabel(conn)}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <div className="w-full sm:w-48">
                            <label className="text-sm font-medium mb-2 block">
                                {translate(AI.select_model)}
                            </label>
                            <select
                                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                value={selectedModelCode || ""}
                                onChange={(e) => setSelectedModelCode(e.currentTarget.value || null)}
                                disabled={!selectedAIConnectionId || models.length === 0}
                            >
                                <option value="">{translate(AI.select_model_placeholder)}</option>
                                {models.map((m) => (
                                    <option key={m.modelCode} value={m.modelCode}>
                                        {m.modelName || m.modelCode}
                                    </option>
                                ))}
                            </select>
                        </div>
                        <Button
                            variant="outline"
                            size="sm"
                            onClick={() => { setReport(null); }}
                            className="flex-shrink-0"
                        >
                            <PlusCircle className="h-4 w-4 me-1" />
                            {translate(AI.new_session)}
                        </Button>
                    </div>
                    {!loadingAIConnections && aiConnections.length === 0 && (
                        <p className="text-sm text-amber-600">
                            {translate(AI.no_ai_connections)}
                        </p>
                    )}

                    {/* Row 2: DB connection + analyze button */}
                    <div className="flex items-end gap-4">
                        <div className="flex-1">
                            <label className="text-sm font-medium mb-2 block">
                                {translate(AI.database.select_connection)}
                            </label>
                            <select
                                className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                                value={selectedConnection?.id || ""}
                                onChange={(e) => {
                                    const val = e.currentTarget.value;
                                    const conn = val ? connections.find(c => c.id === val) : undefined;
                                    setSelectedConnection(conn || null);
                                    setReport(null);
                                }}
                            >
                                <option value="">{translate(AI.database.select_connection_placeholder)}</option>
                                {connections.map((conn) => (
                                    <option key={conn.id} value={conn.id}>
                                        {conn.name} ({conn.type} – {conn.host})
                                    </option>
                                ))}
                            </select>
                        </div>
                        <Button
                            variant="default"
                            onClick={handleAnalyze}
                            disabled={analyzing}
                        >
                            {analyzing ? (
                                <>
                                    <Loader2 className="h-4 w-4 me-2 animate-spin" />
                                    {translate(AI.database.analyzing)}
                                </>
                            ) : (
                                <>
                                    <Search className="h-4 w-4 me-2" />
                                    {translate(AI.database.analyze)}
                                </>
                            )}
                        </Button>
                    </div>
                </CardContent>
            </Card>

            {/* Progress log */}
            {logEntries.length > 0 && (
                <Card>
                    <CardHeader className="pb-2">
                        <CardTitle className="text-sm font-medium flex items-center gap-2">
                            {analyzing && <Loader2 className="h-3 w-3 animate-spin" />}
                            {analyzing ? "Analysis in progress..." : "Analysis log"}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="pb-3">
                        <div className="space-y-1 max-h-64 overflow-y-auto text-xs font-mono">
                            {logEntries.map((entry, i) => (
                                <div
                                    key={i}
                                    className={`flex items-start gap-2 py-0.5 ${
                                        entry.phase === "error"
                                            ? "text-red-600"
                                            : entry.phase === "complete"
                                            ? "text-green-600 font-semibold"
                                            : entry.phase === "warning"
                                            ? "text-amber-600"
                                            : entry.phase === "ai"
                                            ? "text-violet-600"
                                            : "text-muted-foreground"
                                    }`}
                                >
                                    <span className="shrink-0 text-[10px] text-muted-foreground/60 w-14 tabular-nums">
                                        {formatTime(entry.ts, true)}
                                    </span>
                                    <span className="shrink-0 mt-px">
                                        {entry.phase === "error" ? "\u2718" :
                                         entry.phase === "complete" ? "\u2714" :
                                         entry.phase === "warning" ? "\u26A0" :
                                         entry.phase === "ai" ? "\u25C6" :
                                         "\u25B8"}
                                    </span>
                                    <span>{entry.message}</span>
                                </div>
                            ))}
                        </div>
                    </CardContent>
                </Card>
            )}

            {/* Results */}
            {report && (
                <>
                    {/* Summary card */}
                    <Card>
                        <CardHeader>
                            <div className="flex items-center justify-between">
                                <CardTitle className="flex items-center gap-2">
                                    {translate(AI.database.analysis_report)}
                                </CardTitle>
                                <div className="flex gap-2 items-center">
                                    {languages.length > 0 && (
                                        <DropdownMenu open={langDropdownOpen} onOpenChange={setLangDropdownOpen}>
                                            <DropdownMenuTrigger className="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 hover:bg-accent hover:text-accent-foreground h-9 w-9">
                                                <Globe className="h-4 w-4" />
                                            </DropdownMenuTrigger>
                                            <DropdownMenuContent align="end">
                                                {languages.map((lang) => (
                                                    <DropdownMenuItem
                                                        key={lang.code}
                                                        onClick={() => {
                                                            setReportLanguage(lang.code);
                                                            setLangDropdownOpen(false);
                                                        }}
                                                        className={lang.code === reportLanguage ? "bg-muted" : ""}
                                                    >
                                                        {lang.name}
                                                        {lang.code === reportLanguage && " ✓"}
                                                    </DropdownMenuItem>
                                                ))}
                                            </DropdownMenuContent>
                                        </DropdownMenu>
                                    )}
                                    <Button variant="outline" size="sm" onClick={handleDownloadPdf}>
                                        <FileDown className="h-4 w-4 me-1" />
                                        {reportT(AI.database.download_pdf)}
                                    </Button>
                                    <Button variant="outline" size="sm" onClick={handleEmailPdf}>
                                        <Mail className="h-4 w-4 me-1" />
                                        {reportT(AI.database.email_pdf)}
                                    </Button>
                                </div>
                            </div>
                            <CardDescription>
                                {translate(AI.database.analysis_summary)
                                    .replace("{tables}", String(report.summary.total_tables))
                                    .replace("{columns}", String(report.summary.total_columns))
                                    .replace("{issues}", String(report.summary.issue_count))
                                }
                            </CardDescription>
                        </CardHeader>
                        <CardContent>
                            {/* AI Mode Indicator */}
                            {(() => {
                                const aiActive = !!(report.semantic || report.integration);
                                return (
                            <div className={`mb-4 p-3 rounded-lg border flex items-start gap-2 ${
                                aiActive
                                    ? "border-blue-300 bg-blue-50"
                                    : "border-amber-300 bg-amber-50"
                            }`}>
                                {aiActive ? (
                                    <BrainCircuit className="h-5 w-5 text-blue-600 mt-0.5 flex-shrink-0" />
                                ) : (
                                    <AlertTriangle className="h-5 w-5 text-amber-600 mt-0.5 flex-shrink-0" />
                                )}
                                <div>
                                    <p className="text-sm font-semibold">
                                        {aiActive
                                            ? translate(AI.database.ai_augmented)
                                            : translate(AI.database.ai_fallback)
                                        }
                                    </p>
                                    <p className="text-xs text-muted-foreground">
                                        {aiActive
                                            ? translate(AI.database.ai_augmented_desc)
                                            : translate(AI.database.ai_fallback_desc)
                                        }
                                    </p>
                                </div>
                            </div>
                                );
                            })()}
                            {report.schema._warnings && report.schema._warnings.length > 0 && (
                                <div className="mb-4 p-4 rounded-lg border border-yellow-300 bg-yellow-50">
                                    <div className="flex items-start gap-2">
                                        <AlertTriangle className="h-5 w-5 text-yellow-600 mt-0.5 flex-shrink-0" />
                                        <div className="text-sm text-yellow-800 whitespace-pre-wrap">
                                            {report.schema._warnings.map((w: string, i: number) => (
                                                <p key={i}>{w}</p>
                                            ))}
                                        </div>
                                    </div>
                                </div>
                            )}
                            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                                <div className="p-4 rounded-lg border text-center">
                                    <p className="text-2xl font-bold">{report.summary.total_tables}</p>
                                    <p className="text-xs text-muted-foreground">{translate(AI.database.tables_label)}</p>
                                </div>
                                <div className="p-4 rounded-lg border text-center">
                                    <p className="text-2xl font-bold">{report.summary.total_columns}</p>
                                    <p className="text-xs text-muted-foreground">{translate(AI.database.columns_label)}</p>
                                </div>
                                <div className="p-4 rounded-lg border text-center">
                                    <p className="text-2xl font-bold">{report.summary.total_rows}</p>
                                    <p className="text-xs text-muted-foreground">{translate(AI.database.rows_label)}</p>
                                </div>
                                <div className="p-4 rounded-lg border text-center">
                                    <p className="text-2xl font-bold">{report.summary.issue_count}</p>
                                    <p className="text-xs text-muted-foreground">{translate(AI.database.issues_label)}</p>
                                </div>
                            </div>

                            {/* Risk breakdown */}
                            <div className="space-y-2 mb-6">
                                <p className="text-sm font-medium">{translate(AI.database.risk_breakdown)}</p>
                                <div className="flex gap-2">
                                    <span className="px-3 py-1 rounded-full text-xs font-medium bg-red-100 text-red-800">
                                        {translate(AI.database.high_risk)}: {report.summary.risk_summary.high}
                                    </span>
                                    <span className="px-3 py-1 rounded-full text-xs font-medium bg-yellow-100 text-yellow-800">
                                        {translate(AI.database.medium_risk)}: {report.summary.risk_summary.medium}
                                    </span>
                                    <span className="px-3 py-1 rounded-full text-xs font-medium bg-blue-100 text-blue-800">
                                        {translate(AI.database.low_risk)}: {report.summary.risk_summary.low}
                                    </span>
                                </div>
                            </div>

                            {/* Top recommendations */}
                            {report.summary.top_recommendations.length > 0 && (
                                <div>
                                    <p className="text-sm font-medium mb-2">{translate(AI.database.top_recommendations)}</p>
                                    <ol className="list-decimal list-inside space-y-1 text-sm text-muted-foreground">
                                        {report.summary.top_recommendations.map((rec, i) => (
                                            <li key={i}>{rec}</li>
                                        ))}
                                    </ol>
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* RAG Chat */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Search className="h-5 w-5" />
                                {translate(AI.database.rag_chat)}
                            </CardTitle>
                            <CardDescription>
                                {translate(AI.database.rag_chat_desc)}
                            </CardDescription>
                        </CardHeader>
                        <CardContent className="space-y-4">
                            <div className="flex gap-2 items-center">
                                <AudioToggle
                                    micEnabled={micEnabled} onMicChange={setMicEnabled}
                                    speakerEnabled={speakerEnabled} onSpeakerChange={setSpeakerEnabled}
                                    volume={volume} onVolumeChange={setVolume}
                                    speakerMuted={speakerMuted}
                                    onSpeakerMuteToggle={() => { const next = !speakerMuted; setSpeakerMuted(next); setSpeakerEnabled(!next); const s = getCachedSettings("database"); s.speakerMuted = next; setCachedSettings("database", s); }}
                                    speechState={speechState} onPause={pause} onResume={resume} onStop={stop}
                                    onSettingsClick={() => setSettingsOpen(true)}
                                />
                                <input dir="auto"
                                    type="text"
                                    className="flex-1 rounded-md border border-input bg-background px-3 py-2 text-sm"
                                    placeholder={translate(AI.database.rag_placeholder)}
                                    value={ragQuestion}
                                    onChange={(e) => setRagQuestion(e.target.value)}
                                    onKeyDown={(e) => e.key === "Enter" && handleRagQuery()}
                                />
                                <Button onClick={handleRagQuery} disabled={ragLoading}>
                                    {ragLoading ? (
                                        <Loader2 className="h-4 w-4 animate-spin" />
                                    ) : (
                                        translate(AI.database.rag_ask)
                                    )}
                                </Button>
                            </div>
                            {ragAnswer && (
                                <div className="p-4 rounded-lg border bg-muted/30">
                                    <div className="flex items-start gap-1">
                                    <div className="prose prose-sm max-w-none whitespace-pre-wrap text-sm flex-1">
                                        {ragAnswer}
                                    </div>
                                    <CopyButton text={ragAnswer} />
                                </div>
                                    {ragSources && ragSources.length > 0 && (
                                        <div className="mt-4 pt-3 border-t">
                                            <p className="text-xs font-medium text-muted-foreground mb-2">
                                                {translate(AI.database.rag_sources)} ({ragSources.length})
                                            </p>
                                            <div className="space-y-1">
                                                {ragSources.map((s: {text: string; source: string}, i: number) => (
                                                    <div key={i} className="text-xs text-muted-foreground">
                                                        <span className="font-mono text-purple-600">[{s.source}]</span>{" "}
                                                        {s.text.substring(0, 150)}
                                                    </div>
                                                ))}
                                            </div>
                                        </div>
                                    )}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    {/* Issues section */}
                    <Card>
                        <CardHeader
                            className="cursor-pointer"
                            onClick={() => setShowIssues(!showIssues)}
                        >
                            <div className="flex items-center justify-between">
                                <CardTitle className="flex items-center gap-2">
                                    <AlertTriangle className="h-5 w-5 text-yellow-500" />
                                    {translate(AI.database.all_issues)} ({report.analysis.total_issues})
                                </CardTitle>
                                <ChevronDown
                                    className={`h-5 w-5 transition-transform ${showIssues ? "rotate-180" : ""}`}
                                />
                            </div>
                        </CardHeader>
                        {showIssues && (
                            <CardContent className="space-y-3">
                                {report.analysis.issues.length === 0 ? (
                                    <div className="text-center py-8">
                                        <CheckCircle2 className="h-10 w-10 mx-auto mb-2 text-green-500" />
                                        <p className="text-muted-foreground">{translate(AI.database.no_issues)}</p>
                                    </div>
                                ) : (
                                    report.analysis.issues.map((issue, idx) => (
                                        <div
                                            key={idx}
                                            className={`p-3 rounded-lg border ${severityColor(issue.severity)}`}
                                        >
                                            <div className="flex items-start gap-3">
                                                {categoryIcon(issue.category)}
                                                <div className="flex-1 min-w-0">
                                                    <div className="flex items-center gap-2 mb-1">
                                                        <span className="text-xs font-semibold uppercase tracking-wide">
                                                            {issue.category}
                                                        </span>
                                                        <span className="text-xs px-1.5 py-0.5 rounded border">
                                                            {issue.severity}
                                                        </span>
                                                    </div>
                                                    <p className="text-sm font-medium">
                                                        {issue.table}{issue.column ? `.${issue.column}` : ""}
                                                    </p>
                                                    <p className="text-sm mt-1">{issue.message}</p>
                                                    <p className="text-xs mt-1 font-mono opacity-75">
                                                        {issue.recommendation}
                                                    </p>
                                                </div>
                                            </div>
                                        </div>
                                    ))
                                )}
                            </CardContent>
                        )}
                    </Card>

                    {/* Semi-Structured Findings */}
                    {report.semi_structured && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <FileDown className="h-5 w-5 text-purple-500" />
                                    {translate(AI.database.semi_structured)} ({report.semi_structured.columns_with_findings})
                                </CardTitle>
                                <CardDescription>
                                    {translate(AI.database.semi_structured_desc)}
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                {(!report.semi_structured.findings || report.semi_structured.findings.length === 0) ? (
                                    <div className="text-center py-8">
                                        <CheckCircle2 className="h-10 w-10 mx-auto mb-2 text-purple-400" />
                                        <p className="text-muted-foreground">{translate(AI.database.no_semi_structured)}</p>
                                    </div>
                                ) : (
                                    report.semi_structured.findings.map((f: SemiStructuredFinding, idx: number) => (
                                    <div key={idx} className="p-3 rounded-lg border border-purple-200 bg-purple-50/50">
                                        <div className="flex items-start gap-3">
                                            <div className="flex-1">
                                                <p className="text-sm font-semibold">
                                                    {f.schema}.{f.table}.{f.column}
                                                    <span className="text-xs text-muted-foreground ms-2">
                                                        ({f.sample_count} samples)
                                                    </span>
                                                </p>
                                                {f.code_systems && f.code_systems.length > 0 && (
                                                    <div className="mt-2">
                                                        <span className="text-xs font-medium text-purple-700">
                                                            {translate(AI.database.code_systems_detected)}:
                                                        </span>
                                                        <div className="flex flex-wrap gap-1 mt-1">
                                                            {f.code_systems.map((cs: any, i: number) => (
                                                                <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-800">
                                                                    {cs.name} ({cs.domain})
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                                {f.categories && Object.keys(f.categories).length > 0 && (
                                                    <div className="mt-2">
                                                        <span className="text-xs font-medium text-purple-700">
                                                            {translate(AI.database.categories)}:
                                                        </span>
                                                        <div className="flex flex-wrap gap-1 mt-1">
                                                            {Object.keys(f.categories).map((cat, i) => (
                                                                <span key={i} className="text-xs px-2 py-0.5 rounded-full bg-purple-100 text-purple-800">
                                                                    {cat}
                                                                </span>
                                                            ))}
                                                        </div>
                                                    </div>
                                                )}
                                                {f.reference_table_potential && (
                                                    <p className="text-xs mt-2 text-purple-700">
                                                        {f.reference_table_potential.recommendation}
                                                    </p>
                                                )}
                                            </div>
                                        </div>
                                    </div>
                                ))
                                )}
                            </CardContent>
                        </Card>
                    )}

                    {/* Normalisation Suggestions */}
                    {report.normalisation_suggestions && report.normalisation_suggestions.length > 0 && (
                        <Card>
                            <CardHeader>
                                <CardTitle className="flex items-center gap-2">
                                    <Table2 className="h-5 w-5 text-green-600" />
                                    {translate(AI.database.normalisation_suggestions)} ({report.normalisation_suggestions.length})
                                </CardTitle>
                                <CardDescription>
                                    {translate(AI.database.normalisation_suggestions_desc)}
                                </CardDescription>
                            </CardHeader>
                            <CardContent className="space-y-4">
                                <div className="p-3 rounded-lg border border-yellow-300 bg-yellow-50">
                                    <div className="flex items-start gap-2">
                                        <AlertTriangle className="h-4 w-4 text-yellow-600 mt-0.5 flex-shrink-0" />
                                        <p className="text-xs text-yellow-800">{translate(AI.database.normalisation_warning)}</p>
                                    </div>
                                </div>
                                {report.normalisation_suggestions.map((s: any, idx: number) => (
                                    <div key={idx} className="p-4 rounded-lg border border-green-200 bg-green-50/50">
                                        <p className="text-sm font-semibold">{s.description}</p>
                                        {s.proposed_table && (
                                            <div className="mt-2">
                                                <span className="text-xs font-medium text-green-700">
                                                    {translate(AI.database.proposed_reference_table)}: <code className="px-1 py-0.5 rounded bg-green-100">{s.proposed_table.name}</code>
                                                </span>
                                                <div className="mt-1 space-y-1">
                                                    {s.proposed_table.columns.map((col: any, ci: number) => (
                                                        <div key={ci} className="text-xs text-muted-foreground font-mono ms-2">
                                                            {col.name} {col.type}
                                                            {col.nullable === false ? " NOT NULL" : ""}
                                                            {col.default ? ` DEFAULT ${col.default}` : ""}
                                                        </div>
                                                    ))}
                                                </div>
                                            </div>
                                        )}
                                        <div className="mt-2 flex gap-2">
                                            <span className="text-xs px-2 py-0.5 rounded bg-green-100 text-green-800">
                                                {translate(AI.database.confidence)}: {Math.round(s.confidence * 100)}%
                                            </span>
                                            {s.business_value && (
                                                <span className="text-xs text-muted-foreground">
                                                    {translate(AI.database.business_value)}: {s.business_value}
                                                </span>
                                            )}
                                        </div>
                                        {s.proposed_migration && (
                                            <pre className="mt-2 text-xs bg-gray-100 p-2 rounded overflow-x-auto font-mono">
                                                {s.proposed_migration}
                                            </pre>
                                        )}
                                    </div>
                                ))}
                            </CardContent>
                        </Card>
                    )}

                    {/* Tables explorer */}
                    <Card>
                        <CardHeader>
                            <CardTitle className="flex items-center gap-2">
                                <Table2 className="h-5 w-5" />
                                {translate(AI.database.tables_explorer)} ({report.schema.tables.length})
                            </CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            {report.schema.tables.map((table) => (
                                <div key={table.name} className="border rounded-lg">
                                    <div
                                        className="flex items-center justify-between p-3 cursor-pointer hover:bg-muted/50"
                                        onClick={() => toggleTable(table.name)}
                                    >
                                        <div className="flex items-center gap-2">
                                            <Table2 className="h-4 w-4 text-muted-foreground" />
                                            <span className="font-medium">{table.schema}.{table.name}</span>
                                            <span className="text-xs text-muted-foreground">
                                                ({translate(AI.database.cols_rows_format).replace("{cols}", String(table.columns.length)).replace("{rows}", String(table.row_count))})
                                            </span>
                                        </div>
                                        <ChevronDown
                                            className={`h-4 w-4 transition-transform ${expandedTables.has(table.name) ? "rotate-180" : ""}`}
                                        />
                                    </div>
                                    {expandedTables.has(table.name) && (
                                        <div className="border-t px-3 py-2">
                                            {table.comment && (
                                                <p className="text-xs text-muted-foreground mb-2 italic">
                                                    {table.comment}
                                                </p>
                                            )}
                                            {/* Columns */}
                                            <p className="text-xs font-semibold mb-1">{translate(AI.database.columns_label)}</p>
                                            <div className="space-y-1 mb-3">
                                                {table.columns.map((col) => (
                                                    <div key={col.name} className="flex items-center gap-2 text-xs">
                                                        <Key className={`h-3 w-3 ${table.primary_key.includes(col.name) ? "text-yellow-500" : "text-muted-foreground"}`} />
                                                        <span className="font-mono">{col.name}</span>
                                                        <span className="text-muted-foreground">{col.type}</span>
                                                        {col.nullable && <span className="text-muted-foreground">NULL</span>}
                                                        {col.default && (
                                                            <span className="text-muted-foreground font-mono">
                                                                DEFAULT {col.default}
                                                            </span>
                                                        )}
                                                    </div>
                                                ))}
                                            </div>
                                            {/* Foreign Keys */}
                                            {table.foreign_keys.length > 0 && (
                                                <>
                                                    <p className="text-xs font-semibold mb-1">{translate(AI.database.foreign_keys)}</p>
                                                    <div className="space-y-1 mb-2">
                                                        {table.foreign_keys.map((fk, i) => (
                                                            <div key={i} className="text-xs text-muted-foreground">
                                                                {fk.column} → {fk.referenced_table}.{fk.referenced_column}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </>
                                            )}
                                            {/* Indexes */}
                                            {table.indexes.length > 0 && (
                                                <>
                                                    <p className="text-xs font-semibold mb-1">{translate(AI.database.indexes_label)}</p>
                                                    <div className="space-y-1">
                                                        {table.indexes.map((idx) => (
                                                            <div key={idx.name} className="text-xs text-muted-foreground font-mono truncate">
                                                                {idx.is_primary_key && translate(AI.database.pk_prefix)}{idx.name}
                                                            </div>
                                                        ))}
                                                    </div>
                                                </>
                                            )}
                                        </div>
                                    )}
                                </div>
                            ))}
                        </CardContent>
                    </Card>
            {/* ── AI Health Score & Top Actions ── */}
            {report.health && (
                <Card className="border-blue-200 bg-gradient-to-r from-blue-50 to-indigo-50">
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <TrendingUp className="h-5 w-5 text-blue-600" />
                            {translate(AI.database.ai_health_score)}: {report.health.score}/100
                        </CardTitle>
                        <CardDescription>
                            {translate(AI.database.health_score_desc)}
                        </CardDescription>
                    </CardHeader>
                    {report.health.top_actions.length > 0 && (
                        <CardContent>
                            <h4 className="text-sm font-semibold mb-2">{translate(AI.database.priority_actions)}</h4>
                            <ol className="list-decimal ms-4 space-y-1">
                                {report.health.top_actions.map((action, i) => (
                                    <li key={i} className="text-sm">{action}</li>
                                ))}
                            </ol>
                        </CardContent>
                    )}
                </Card>
            )}

            {/* ── Semantic Annotations ── */}
            {report.semantic && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <BrainCircuit className="h-5 w-5 text-violet-600" />
                            {translate(AI.database.semantic_analysis)}
                        </CardTitle>
                        <CardDescription>
                            {translate(AI.database.semantic_analysis_desc)}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* Column Meanings */}
                        {report.semantic.columns && report.semantic.columns.length > 0 && (
                            <div>
                                <h4 className="text-sm font-semibold mb-2">{translate(AI.database.column_meanings)}</h4>
                                <div className="space-y-2">
                                    {report.semantic.columns.map((col, i) => (
                                        <div key={i} className="flex items-start gap-2 p-2 rounded bg-violet-50/50 border border-violet-100">
                                            <span className="text-xs font-mono font-semibold text-violet-800 min-w-[120px]">{col.table}.{col.name}</span>
                                            <span className="text-sm flex-1">{col.meaning}</span>
                                            <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                                                col.confidence === 'high' ? 'bg-green-100 text-green-700' :
                                                col.confidence === 'medium' ? 'bg-yellow-100 text-yellow-700' :
                                                'bg-gray-100 text-gray-600'
                                            }`}>{col.confidence}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Code Systems */}
                        {report.semantic.code_systems && report.semantic.code_systems.length > 0 && (
                            <div>
                                <h4 className="text-sm font-semibold mb-2">{translate(AI.database.code_systems_detected)}</h4>
                                <div className="flex flex-wrap gap-2">
                                    {report.semantic.code_systems.map((cs, i) => (
                                        <span key={i} className="text-xs px-2 py-1 rounded-full bg-violet-100 text-violet-800 font-mono">
                                            {cs.table}.{cs.column} → {cs.system}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* ISIC Domains */}
                        {report.semantic.domains && report.semantic.domains.length > 0 && (
                            <div>
                                <h4 className="text-sm font-semibold mb-2">{translate(AI.database.isic_domains)}</h4>
                                <div className="space-y-1">
                                    {report.semantic.domains.map((d, i) => (
                                        <div key={i} className="flex items-center gap-2 text-sm">
                                            <span className="font-mono font-semibold text-violet-700">{d.table}</span>
                                            <span className="text-muted-foreground">→</span>
                                            <span>{d.domains.join(', ')}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Table Purposes */}
                        {report.semantic.table_purposes && report.semantic.table_purposes.length > 0 && (
                            <div>
                                <h4 className="text-sm font-semibold mb-2">{translate(AI.database.table_purposes)}</h4>
                                <div className="space-y-2">
                                    {report.semantic.table_purposes.map((tp, i) => (
                                        <div key={i} className="p-2 rounded bg-violet-50/50 border border-violet-100">
                                            <span className="text-xs font-mono font-semibold text-violet-800">{tp.table}:</span>
                                            <span className="text-sm ms-2">{tp.purpose}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* ── Integration Findings ── */}
            {report.integration && (
                <Card>
                    <CardHeader>
                        <CardTitle className="flex items-center gap-2">
                            <GitMerge className="h-5 w-5 text-emerald-600" />
                            {translate(AI.database.integration_analysis)}
                        </CardTitle>
                        <CardDescription>
                            {translate(AI.database.integration_analysis_desc)}
                        </CardDescription>
                    </CardHeader>
                    <CardContent className="space-y-4">
                        {/* Implicit Relationships */}
                        {report.integration.implicit_relationships && report.integration.implicit_relationships.length > 0 && (
                            <div>
                                <h4 className="text-sm font-semibold mb-2">{translate(AI.database.implicit_relationships)}</h4>
                                <div className="space-y-2">
                                    {report.integration.implicit_relationships.map((rel, i) => (
                                        <div key={i} className="p-3 rounded bg-emerald-50/50 border border-emerald-200">
                                            <div className="flex items-center gap-2 mb-1">
                                                <span className="text-xs font-mono font-semibold">{rel.from_table}.{rel.from_column}</span>
                                                <span className="text-muted-foreground">→</span>
                                                <span className="text-xs font-mono font-semibold">{rel.to_table}.{rel.to_column}</span>
                                                <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                                                    rel.confidence === 'high' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                                                }`}>{rel.confidence}</span>
                                            </div>
                                            <p className="text-xs text-muted-foreground">{rel.evidence}</p>
                                            {rel.proposed_ddl && (
                                                <pre className="mt-2 text-xs bg-gray-900 text-green-400 p-2 rounded overflow-x-auto">
                                                    {rel.proposed_ddl}
                                                </pre>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Research Capabilities */}
                        {report.integration.research_capabilities && report.integration.research_capabilities.length > 0 && (
                            <div>
                                <h4 className="text-sm font-semibold mb-2">{translate(AI.database.research_capabilities)}</h4>
                                <div className="space-y-2">
                                    {report.integration.research_capabilities.map((rc, i) => (
                                        <div key={i} className="flex items-start gap-2 p-2 rounded bg-emerald-50/50 border border-emerald-100">
                                            <span className={`mt-0.5 ${rc.supported ? 'text-green-600' : 'text-red-500'}`}>
                                                {rc.supported ? '✅' : '❌'}
                                            </span>
                                            <div className="flex-1">
                                                <span className="text-sm font-semibold">{rc.study_type}</span>
                                                <p className="text-xs text-muted-foreground">{rc.rationale}</p>
                                            </div>
                                            <span className={`text-xs px-1.5 py-0.5 rounded-full ${
                                                rc.confidence === 'high' ? 'bg-green-100 text-green-700' : 'bg-yellow-100 text-yellow-700'
                                            }`}>{rc.confidence}</span>
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}

                        {/* Missing Dimensions */}
                        {report.integration.missing_dimensions && report.integration.missing_dimensions.length > 0 && (
                            <div>
                                <h4 className="text-sm font-semibold mb-2">{translate(AI.database.missing_dimensions)}</h4>
                                <div className="space-y-2">
                                    {report.integration.missing_dimensions.map((md, i) => (
                                        <div key={i} className="p-3 rounded bg-amber-50 border border-amber-200">
                                            <p className="text-sm">
                                                <span className="font-mono font-semibold">{md.table}</span>
                                                <span className="text-muted-foreground"> {translate(AI.database.is_missing)} </span>
                                                <span className="font-semibold text-amber-700">{md.missing_feature}</span>
                                            </p>
                                            <p className="text-xs text-muted-foreground mt-1">
                                                {translate(AI.database.peer_tables)} {md.peer_tables.join(', ')}
                                            </p>
                                            {md.likely_explanation && (
                                                <p className="text-xs text-amber-600 mt-1">{md.likely_explanation}</p>
                                            )}
                                        </div>
                                    ))}
                                </div>
                            </div>
                        )}
                    </CardContent>
                </Card>
            )}


                </>
            )}

            {/* Empty state */}
            {!report && !analyzing && (
                <Card>
                    <CardContent className="py-12 text-center">
                        <Database className="h-12 w-12 mx-auto mb-3 text-muted-foreground opacity-50" />
                        <p className="text-muted-foreground">
                            {translate(AI.database.empty_state)}
                        </p>
                        {connections.length === 0 && (
                            <Link href="/settings/database">
                                <Button variant="outline" className="mt-4">
                                    {translate(AI.database.add_connection)}
                                </Button>
                            </Link>
                        )}
                    </CardContent>
                </Card>
            )}
            <AudioSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} chatType="database" />
        </div>
    );
}

export default function DBDatabasePage() {
    return (
        <ProtectedRoute>
            <DBDatabaseContent />
        </ProtectedRoute>
    );
}