"use client";

import { Suspense, useState, useRef, useEffect, useCallback, useMemo } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, useTranslateWithParams } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import {
    fetchRecipeModel,
    validateRecipe,
    type RecipeModel,
    type ValidationResult,
    type ModelColumn,
    type ModelAlgorithmState,
    type ModelOutputState,
} from "@/lib/recipe-model";
import { ProtectedRoute } from "@/components/protected-route";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAI } from "@/lib/ai-context";
import { Loader2, Send, Bot, User, PlusCircle, PanelRightClose, PanelRightOpen, Volume2, Square, Filter } from "lucide-react";
import CopyButton from "@/components/copy-button";
import MarkdownContent from "@/components/markdown-content";
import { SuggestionChips } from "@/components/chat/suggestion-chips";
import { NameSuggestion } from "@/components/chat/name-suggestion";
import { name_suggestion_accept, name_suggestion_heading } from "@/app/common/translations";
import AudioToggle from "@/components/audio-toggle";
import AudioSettingsDialog from "@/components/audio-settings-dialog";
import { useSpeechOutput } from "@/hooks/use-speech";
import { useSpeechInput } from "@/hooks/use-speech-input";
import { getCachedSettings, setCachedSettings } from "@/lib/audio-settings";

import SessionsSidebar from "./components/SessionsSidebar";
import {
    AI,
    ai_recipe_chip_collapse,
    ai_recipe_chip_expand,
    ai_recipe_chip_superseded,
    ai_recipe_chip_withheld,
    ai_recipe_progress_next,
    ai_recipe_unread_sources,
} from "../translations";
import { COMMON } from "@/app/common/translations";
import { RECIPES } from "@/app/recipes/translations";
import { DATASETS } from "@/app/datasets/translations";

/* ------------------------------------------------------------------ */
/*  Types                                                              */
/* ------------------------------------------------------------------ */

interface AISession {
    sessionId: string;
    datasetId: string | null;
    stage: string;
    status: string;
    createdAt: string;
    updatedAt: string;
    isManualRecipe?: boolean;
    recipeName?: string;
    displayName?: string | null;
}

interface DatasetSuggestion {
    id: string;
    name: string;
    sourceType?: string | null;
    storageType?: string | null;
}

/** A single field choice inside a proposal: what the model put forward together. */
interface ProposalField {
    piece: string;
    field: string;
    column: string;
}

/** A source the schema reader could not read.
 *
 *  `stateText` is the translated sentence for the failure class — the same class
 *  on both backends, so the same words on screen whichever one answered. `reason`
 *  is the driver's own text: it is pgx's wording on Go and asyncpg's on Python for
 *  one failure, so it is a diagnostic rather than something to translate, and it
 *  is rendered beneath, smaller. */
interface UnreadSource {
    alias: string;
    state?: string;
    stateText?: string;
    reason: string;
}

interface Suggestion {
    piece: string;
    /** The chip's text, for a `proposal` row only. Written by the model in this
     *  turn, in the user's language, and rendered verbatim — deliberately not a
     *  declared key, because a key resolves from the stored language column while
     *  the model answers in the language the user writes in (design §3.12a). */
    label?: string;
    /** The field choices a `proposal` chip applies together. */
    fields?: ProposalField[];
    /** The chip row's choices — capped at the backend's CHIP_SET_LIMIT (six). */
    choices: string[];
    /** How many choices the cap left out, so a short row never reads as complete.
     *  Zero on an exactly-full row, stated rather than omitted. Rendered beside the
     *  row, through `ai_recipe_chip_withheld`. */
    withheld?: number;
    /** The choices the cap left out. They travel so the row can expand — a count
     *  alone cannot be acted on, and a hidden choice that cannot be reached is
     *  missing rather than withheld. */
    overflow?: string[];
    /** The row's heading, resolved at the boundary from the piece it asks about —
     *  the same key-then-sentence shape as `what`/`whatText` on the scoreboard. */
    heading?: string;
    headingText?: string;
    field?: string;
    columnType?: string;
    multi?: boolean;
}

interface ChatMessage {
    role: "user" | "assistant";
    content: string;
    suggestions?: DatasetSuggestion[];
    suggestion?: Suggestion;
}

/** One entry as it is stored — the model's conversation, not a display record:
 *  it carries tool results and assistant turns that exist only to hold
 *  tool_calls. */
interface StoredMessage {
    role: string;
    content?: string;
    tool_calls?: unknown[];
    suggestions?: DatasetSuggestion[];
    suggestion?: Suggestion;
}

const DECISION_MARKER = /\[DECISION:[^\]]*\]/g;

// Output type key → label. The output defs in the recipe model carry no label
// (they map to the DB's visualisation types), so the clickable output chips
// resolve their names from the RECIPES declarations.
const OUTPUT_LABELS: Record<string, { key: string; fallback: string }> = {
    bar: RECIPES.visualisation_bar,
    hbar: RECIPES.visualisation_hbar,
    pie: RECIPES.visualisation_pie,
    donut: RECIPES.visualisation_donut,
    line: RECIPES.visualisation_line,
    area: RECIPES.visualisation_area,
    scatter: RECIPES.visualisation_scatter,
    distribution: RECIPES.visualisation_distribution,
    histogram: RECIPES.visualisation_histogram,
    table: RECIPES.visualisation_table,
    none: RECIPES.no_visualisation,
};

// The stored array is the model's conversation; the chat shows the
// human-readable projection of it. Tool results and the empty tool-call turns
// are dropped, and the assistant text loses the [DECISION:…] markers the
// backend strips for a live reply — same pattern and same trailing trim as
// backend ai_agent.py _strip_decision_markers.
function displayMessages(raw: unknown): ChatMessage[] {
    const stored = (raw as StoredMessage[] | undefined) || [];
    return stored
        .filter(
            (m) =>
                m.role === "user" ||
                (m.role === "assistant" && (m.content || "").trim() !== ""),
        )
        .map((m) => ({
            role: m.role as ChatMessage["role"],
            content: (m.content || "").replace(DECISION_MARKER, "").trim(),
            suggestions: m.suggestions,
            suggestion: m.suggestion,
        }));
}

// Slug → canonical output-type key (mirrors OutputComponent's SLUG_TO_OUTPUT).
const SLUG_TO_OUTPUT: Record<string, string> = {
    text_table: "table",
    bar_chart: "bar",
    horizontal_bar: "hbar",
    pie_chart: "pie",
    donut_chart: "donut",
    line_chart: "line",
    area_chart: "area",
    scatter_plot: "scatter",
    histogram: "histogram",
    distribution: "distribution",
};

interface RecipeStage {
    type: string;
    config?: Record<string, unknown>;
}

interface RecipeState {
    goal: string | null;
    expertise_level: string;
    stages: RecipeStage[];
}

interface Scoreboard {
    // No `valid` flag: every entry here is decided, valid and complete, which is
    // what makes `crystallised.length` the decided count (constraints.py §3.3).
    crystallised: { piece: string; [key: string]: unknown }[];
    /** `what` is the declared translation key; `whatText` the boundary's sentence for
     *  it. Both travel, deliberately: the page renders the sentence, and the key stays
     *  in the payload so a missing translation row can be diagnosed rather than showing
     *  as an empty string. `whatText` may be absent on an older session. */
    pending: { piece: string; what: string; whatText?: string; choices: string[] }[];
    /** Pieces that cannot be decided yet — an unchosen parent, never asked about.
     *  They carry `blocked_by` and `unblocked_by` (`unblockedByText` once the
     *  boundary has resolved it) so a renderer can say what the piece waits on.
     *  Nothing on this page renders them yet: Item 18 is their consumer, in the
     *  prompt. Declared here so the wire shape is stated once rather than
     *  rediscovered. A blocked piece is never also pending. */
    blocked?: { piece: string; blocked_by: string; unblocked_by: string; unblockedByText?: string }[];
    complete: boolean;
    errors: unknown[];
    warnings: unknown[];
    /** The denominator for the progress label, sent by the backend. Six from the
     *  first turn — a count of what is visible would say four on an empty draft and
     *  grow to six, moving the goalposts mid-task. Never type the number here. */
    total: number;
}

interface TransformRef {
    id: string;
    name: string;
    description: string | null;
}

/* ------------------------------------------------------------------ */
/*  Helpers                                                            */
/* ------------------------------------------------------------------ */

/* ------------------------------------------------------------------ */
/*  Component                                                          */
/* ------------------------------------------------------------------ */

function AIChefContent() {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const translateParams = useTranslateWithParams();
    const searchParams = useSearchParams();
    const resumedSessionRef = useRef(false);

    const [sessions, setSessions] = useState<AISession[]>([]);
    const [activeSessionId, setActiveSessionId] = useState<string | null>(null);
    const [messages, setMessages] = useState<ChatMessage[]>([]);
    const [input, setInput] = useState("");
    const [loading, setLoading] = useState(false);
    const [error, setError] = useState("");
    const [recipeState, setRecipeState] = useState<RecipeState | null>(null);
    const [recipeModel, setRecipeModel] = useState<RecipeModel | null>(null);
    const [vizTypeNames, setVizTypeNames] = useState<Record<string, string>>({});
    const [schemaColumns, setSchemaColumns] = useState<ModelColumn[]>([]);
    const [datasetTransforms, setDatasetTransforms] = useState<TransformRef[]>([]);
    const [scoreboard, setScoreboard] = useState<Scoreboard | null>(null);
    /** Sources the schema reader could not read — persisted so a silent empty
     *  chip row has a visible reason. */
    const [unread, setUnread] = useState<UnreadSource[]>([]);
    const [schemaChanges, setSchemaChanges] = useState<string[]>([]);
    const [rightPanelOpen, setRightPanelOpen] = useState(false);
    const [datasets, setDatasets] = useState<{ id: string; name: string; sourceType?: string; databaseName?: string; tableName?: string; storageType?: string | null; sourceOrigin?: string | null; isShared?: boolean }[]>([]);
    const [selectedDatasetId, setSelectedDatasetId] = useState<string>("");
    const [multiSelect, setMultiSelect] = useState<{ piece: string; field: string; choices: string[]; selected: string[] } | null>(null);
    const [datasetFilter, setDatasetFilter] = useState<string>("all");

    const datasetCategory = (ds: { sourceType?: string; storageType?: string | null; sourceOrigin?: string | null }): string => {
        const key = ds.sourceOrigin || ds.sourceType || "";
        if (key === "table" || key === "view") {
            return ds.storageType || "postgresql";
        }
        return key;
    };

    const matchesFilter = (ds: { sourceType?: string; storageType?: string | null; sourceOrigin?: string | null; isShared?: boolean }, f: string): boolean => {
        switch (f) {
            case "all": return true;
            case "cleaned": return !!ds.sourceOrigin;
            case "shared": return ds.isShared === true;
            case "not_shared": return ds.isShared !== true;
            default: return datasetCategory(ds) === f;
        }
    };

    const visibleDatasets = datasets.filter((ds) => matchesFilter(ds, datasetFilter));
    const [savedRecipeId, setSavedRecipeId] = useState<string>("");
    const [saving, setSaving] = useState(false);
    interface AIConnectionItem { id: string; connectionId: number; name: string; provider: string; isOwn: boolean }
    const [aiConnections, setAIConnections] = useState<AIConnectionItem[]>([]);
    const [selectedAIConnectionId, setSelectedAIConnectionId] = useState<string>("");
    const [models, setModels] = useState<{ modelCode: string; modelName: string }[]>([]);
    const [selectedModelCode, setSelectedModelCode] = useState<string>("");
    const [loadingAIConnections, setLoadingAIConnections] = useState(true);
    const [speakerEnabled, setSpeakerEnabled] = useState(false);
    const [micEnabled, setMicEnabled] = useState(false);
    const [settingsOpen, setSettingsOpen] = useState(false);
    const [speakerMuted, setSpeakerMuted] = useState(false);
    const [speakingMsgIndex, setSpeakingMsgIndex] = useState<number | null>(null);

    const speakMessage = (text: string, index: number) => {
        if (typeof window === "undefined" || !window.speechSynthesis) return;
        const synth = window.speechSynthesis;
        // If already speaking this message, stop
        if (speakingMsgIndex === index && synth.speaking) {
            synth.cancel();
            setSpeakingMsgIndex(null);
            return;
        }
        // Otherwise cancel anything playing and speak this message
        synth.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.onstart = () => setSpeakingMsgIndex(index);
        utterance.onend = () => setSpeakingMsgIndex(null);
        utterance.onerror = () => setSpeakingMsgIndex(null);
        synth.speak(utterance);
    };

    const { defaultConnectionId: defaultAIId } = useAI();

    const messagesEndRef = useRef<HTMLDivElement>(null);
    const inputRef = useRef<HTMLInputElement>(null);

    // Refocus the chat input after any selection (a Select leaves focus on its
    // trigger) and once a send completes and the input is re-enabled.
    useEffect(() => {
        if (!loading) inputRef.current?.focus();
    }, [loading, selectedDatasetId, datasetFilter, selectedAIConnectionId, selectedModelCode]);

    // Audio: speak last assistant message
    const lastAssistantContent = messages.slice().reverse().find(m => m.role !== "user")?.content ?? "";
    const { speechState, pause, resume, stop, volume, setVolume } =
        useSpeechOutput(lastAssistantContent, speakerEnabled, "recipe");
    // Audio: speech-to-text
    const { transcript } = useSpeechInput(micEnabled);

    /* -- scroll to bottom on new messages -- */
    useEffect(() => {
        messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
    }, [messages]);

    // Pipe speech-to-text transcript into input
    useEffect(() => {
        if (transcript) setInput(transcript);
    }, [transcript]);

    /* -- load sessions and datasets on mount -- */
    useEffect(() => {
        loadSessions();
        loadDatasets();
        fetchAIConnections();
    }, []);

    /* -- resume the session named in ?session=… -- */
    // The return banner on the dataset pages links to /ai/recipe?session=<id>,
    // so a session has to be reachable from the URL as well as from the list.
    // It is applied once: from then on the list is the authority, and a later
    // selection must not be undone by the parameter still sitting in the URL.
    useEffect(() => {
        const requested = searchParams.get("session");
        if (!requested || resumedSessionRef.current) return;
        resumedSessionRef.current = true;
        loadSession(requested);
    }, [searchParams]);

    /* -- fetch the constraint model once for draft validation -- */
    useEffect(() => {
        fetchRecipeModel()
            .then(setRecipeModel)
            .catch(() => {});
    }, []);

    /* -- fetch visualization-type names for the output label -- */
    useEffect(() => {
        fetch("/api/visualization-types")
            .then((res) => res.json())
            .then((data) => {
                const map: Record<string, string> = {};
                for (const t of data.types || []) {
                    const key = SLUG_TO_OUTPUT[t.slug];
                    if (key) map[key] = t.name;
                }
                setVizTypeNames(map);
            })
            .catch(() => {});
    }, []);

    // Project the canonical draft (stages) into the read-only preview shape.
    const draft = useMemo(() => {
        const stages = recipeState?.stages || [];
        const dataSel = stages.find((s) => s.type === "data_selection");
        const stats = stages.find((s) => s.type === "statistics");
        const viz = stages.find((s) => s.type === "visualisation");
        const datasetId = (dataSel?.config?.datasetId as string) || null;
        const datasetName =
            (dataSel?.config?.datasetName as string) ||
            (datasetId ? datasets.find((d) => d.id === datasetId)?.name : null) ||
            null;
        return {
            datasetId,
            datasetName,
            columns: ((dataSel?.config?.columns as ModelColumn[]) || []),
            transformIds: ((dataSel?.config?.transformIds as string[]) || []),
            algorithmType: (stats?.config?.algorithmType as string) || null,
            algorithmConfig: ((stats?.config?.config as Record<string, unknown>) || {}),
            outputType: (viz?.config?.outputType as string) || null,
            outputConfig: ((viz?.config?.config as Record<string, unknown>) || {}),
            algorithm: (stats?.config as ModelAlgorithmState) || null,
            output: (viz?.config as ModelOutputState) || null,
        };
    }, [recipeState, datasets]);

    // Fetch the linked dataset's columns when the draft doesn't already carry
    // a schema (AI-built drafts store only the dataset id).
    useEffect(() => {
        const datasetId = draft.datasetId;
        if (!datasetId || draft.columns.length > 0) {
            setSchemaColumns([]);
            return;
        }
        let cancelled = false;
        apiFetch(`/api/datasets/${datasetId}/schema`)
            .then((res) => (res.ok ? res.json() : null))
            .then((data) => {
                if (!cancelled && data) {
                    setSchemaColumns(
                        (data.columns || []).map((c: any) => ({
                            name: c.name || c.column_name || "?",
                            isNumeric: c.is_numeric === true || c.isNumeric === true,
                            isCategorical: c.is_categorical === true || c.isCategorical === true,
                        }))
                    );
                }
            })
            .catch(() => {});
        return () => {
            cancelled = true;
        };
    }, [draft.datasetId, draft.columns.length]);

    // Fetch the linked dataset's transforms for name display in the preview.
    useEffect(() => {
        const datasetId = draft.datasetId;
        if (!datasetId) {
            setDatasetTransforms([]);
            return;
        }
        let cancelled = false;
        apiFetch(`/api/datasets/${datasetId}/transforms`)
            .then((res) => (res.ok ? res.json() : null))
            .then((data) => {
                if (!cancelled && data) {
                    setDatasetTransforms(
                        (data.transforms || []).map((t: any) => ({
                            id: t.id,
                            name: t.name,
                            description: t.description,
                        }))
                    );
                }
            })
            .catch(() => {});
        return () => {
            cancelled = true;
        };
    }, [draft.datasetId]);

    // Selected transforms, in the draft's application order.
    const selectedTransforms: TransformRef[] = (draft.transformIds || [])
        .map((id) => datasetTransforms.find((t) => t.id === id))
        .filter((t): t is TransformRef => Boolean(t));

    // One-click link to the transform editor. After save it is recipe-aware
    // (the same URL the manual editor's ExternalLink button uses); before save
    // it opens the editor and returns to the AI chat.
    const manageTransformsUrl = draft.datasetId
        ? savedRecipeId
            ? `/datasets/${draft.datasetId}/transforms?recipeId=${savedRecipeId}&returnTo=/recipes/${savedRecipeId}`
            : `/datasets/${draft.datasetId}/transforms?returnTo=/ai/recipe`
        : null;

    // Columns to show as chips: the draft's own schema when present
    // (from-recipe), otherwise the fetched schema for the linked dataset.
    const displayColumns: ModelColumn[] = draft.columns.length > 0 ? draft.columns : schemaColumns;

    // Validate the draft against the served model — the same validator the
    // backend save path enforces. Column existence/type checks run against the
    // draft's own schema (from-recipe) or the fetched dataset schema (AI draft).
    const validation: ValidationResult = useMemo(() => {
        if (!recipeModel) return { errors: [], warnings: [] };
        return validateRecipe(recipeModel, {
            columns: displayColumns,
            algorithm: draft.algorithm,
            output: draft.output,
        });
    }, [recipeModel, draft, schemaColumns]);

    // Render a single config value (string or string[]) as display text.
    const fieldValue = (v: unknown): string => {
        if (Array.isArray(v)) return v.length ? v.join(", ") : "—";
        return v == null || v === "" ? "—" : String(v);
    };

    // Localized output-type name, falling back to the raw key.
    const outputLabel = (type: string): string => {
        if (type === "none") return translate(AI.ai_recipe_draft_no_visualisation);
        return vizTypeNames[type] || type;
    };

    // Localized field label, falling back to the raw field key.
    const fieldLabel = (field: string): string => {
        const fdef = recipeModel?.fields[field];
        return fdef ? translate(fdef.label) : field;
    };

    useEffect(() => {
        if (selectedAIConnectionId) fetchModels(selectedAIConnectionId);
    }, [selectedAIConnectionId]);

    async function fetchAIConnections() {
        try {
            const res = await apiFetch("/api/user/ai-connections/available");
            if (res.ok) {
                const data = await res.json();
                const conns: AIConnectionItem[] = data.connections || [];
                setAIConnections(conns);
                if (conns.length > 0 && !selectedAIConnectionId) {
                    const defaultConn = defaultAIId
                        ? conns.find(c => c.id === defaultAIId)
                        : null;
                    setSelectedAIConnectionId(defaultConn ? defaultConn.id : conns[0].id);
                }
            }
        } catch {
            /* silent */
        } finally {
            setLoadingAIConnections(false);
        }
    }

    async function fetchModels(connectionId: string) {
        try {
            const res = await apiFetch(`/api/user/ai-connections/${connectionId}/models?enabled=true`);
            if (res.ok) {
                const data = await res.json();
                const mods = data.models || [];
                setModels(mods);
                if (mods.length > 0) {
                    setSelectedModelCode(mods[0].modelCode);
                }
            }
        } catch {
            /* silent */
        }
    }

    async function loadDatasets() {
        try {
            const res = await apiFetch("/api/datasets");
            if (res.ok) {
                const data = await res.json();
                setDatasets(data.datasets || []);
            }
        } catch {
            setDatasets([]);
        }
    }

    async function loadSessions() {
        try {
            const res = await apiFetch("/api/recipes/ai/sessions");
            if (res.ok) {
                const data = await res.json();
                setSessions(data.sessions || []);
            }
        } catch {
            setSessions([]);
        }
    }

    async function renameSession(sessionId: string, newName: string) {
        try {
            const res = await apiFetch(`/api/recipes/ai/sessions/${sessionId}/name`, {
                method: "PATCH",
                body: JSON.stringify({ name: newName }),
            });
            if (res.ok) {
                // Update the session's displayName in the sessions list
                setSessions(prev => prev.map(s =>
                    s.sessionId === sessionId ? { ...s, displayName: newName } : s
                ));
            }
        } catch {
            /* silent — name edit failure is non-critical */
        }
    }

    async function createSession(datasetId?: string): Promise<string | null> {
        setError("");
        try {
            const res = await apiFetch("/api/recipes/ai/sessions", {
                method: "POST",
                body: JSON.stringify({ datasetId: datasetId ?? (selectedDatasetId || null) }),
            });
            if (res.ok) {
                const data = await res.json();
                // Refresh the session list
                await loadSessions();
                // Set the new session as active directly — no need to
                // fetch an empty session detail for a brand-new session
                setActiveSessionId(data.sessionId);
                setMessages([]);
                setRecipeState(null);
                setScoreboard(null);
                setUnread([]);
                setSavedRecipeId("");
                return data.sessionId;
            }
        } catch {
            setError(translate(AI.ai_recipe_chat_error));
        }
        return null;
    }

    async function loadSession(sessionId: string, isManual?: boolean) {
        setError("");
        // Convert manual recipe to AI session first
        let actualSessionId = sessionId;
        let clonedFromRecipe = false;
        if (isManual) {
            try {
                const res = await apiFetch(`/api/recipes/ai/sessions/from-recipe/${sessionId}`, {
                    method: "POST",
                    body: JSON.stringify({}),
                });
                if (res.ok) {
                    const data = await res.json();
                    actualSessionId = data.sessionId;
                    clonedFromRecipe = true;
                    // Immediately prepend the new session to the list so the UI updates
                    const newSession: AISession = {
                        sessionId: actualSessionId,
                        datasetId: null,
                        stage: data.state?.stages?.length ? "review" : "greeting",
                        status: "active",
                        createdAt: new Date().toISOString(),
                        updatedAt: new Date().toISOString(),
                        isManualRecipe: false,
                        displayName: data.state?.goal || "",
                    };
                    setSessions(prev => {
                        const filtered = prev.filter(s => s.sessionId !== sessionId);
                        return [newSession, ...filtered];
                    });
                    setActiveSessionId(actualSessionId);
                    // Background refresh to sync with server
                    loadSessions();
                } else {
                    setError(translate(AI.ai_recipe_chat_error));
                    return;
                }
            } catch {
                setError(translate(AI.ai_recipe_chat_error));
                return;
            }
        }

        try {
            const res = await apiFetch(`/api/recipes/ai/sessions/${actualSessionId}`);
            if (res.ok) {
                const data = await res.json();
                setActiveSessionId(actualSessionId);
                setMessages(displayMessages(data.messages));
                setRecipeState(data.state || null);
                // The server computes this on open (GET /ai/sessions/{id} returns
                // `scoreboard`), through the same function a turn uses. It was
                // discarded here, so a reopened session showed no progress and no
                // next step until the user spoke, and the resume read as partial.
                setScoreboard(data.scoreboard ?? null);
                setUnread(data.unread ?? []);
                // The save owns `saved_recipe_id` inside `state`, and the load
                // threw it away too — so "Open in editor" vanished on reload even
                // though the id was in the payload just received.
                setSavedRecipeId(data.state?.savedRecipeId || "");
                // The selector keeps its own state and is otherwise set only by
                // its own onChange, so loading a session left it on the
                // previously chosen dataset (or on nothing).
                setSelectedDatasetId(data.datasetId || "");
            }
        } catch {
            setError(translate(AI.ai_recipe_chat_error));
        }

        // A session cloned from a recipe has no conversation of its own — its
        // draft is the recipe. Ask the model to say what it does and offer
        // changes; that reply is also what fills the otherwise empty chat.
        if (clonedFromRecipe) {
            await handleRecipeLoaded(actualSessionId);
        }
    }

    async function deleteSession(sessionId: string) {
        try {
            await apiFetch(`/api/recipes/ai/sessions/${sessionId}`, {
                method: "DELETE",
            });
            if (activeSessionId === sessionId) {
                setActiveSessionId(null);
                setMessages([]);
                setRecipeState(null);
            }
            await loadSessions();
        } catch {
            setError(translate(AI.ai_recipe_chat_error));
        }
    }

    async function saveRecipe() {
        if (!activeSessionId) return;
        setSaving(true);
        setError("");
        try {
            const res = await apiFetch(
                `/api/recipes/ai/sessions/${activeSessionId}/save`,
                {
                    method: "POST",
                    body: JSON.stringify({ name: recipeState?.goal || "" }),
                }
            );
            if (res.ok) {
                const data = await res.json();
                setSavedRecipeId(data.recipeId);
            } else {
                setError(translate(AI.ai_recipe_chat_error));
            }
        } catch {
            setError(translate(AI.ai_recipe_chat_error));
        } finally {
            setSaving(false);
        }
    }

    async function sendMessage() {
        if (!input.trim() || !activeSessionId) return;

        const userMsg: ChatMessage = { role: "user", content: input };
        setMessages((prev) => [...prev, userMsg]);
        setInput("");
        setLoading(true);
        setError("");

        try {
            const res = await apiFetch(
                `/api/recipes/ai/sessions/${activeSessionId}/message`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        message: userMsg.content,
                        connectionId: selectedAIConnectionId
                            ? aiConnections.find(c => c.id === selectedAIConnectionId)?.connectionId ?? null
                            : null,
                        model: selectedModelCode || null,
                    }),
                }
            );
            if (res.ok) {
                const data = await res.json();
                syncMultiSelect(data.suggestion);
                const aiMsg: ChatMessage = { role: "assistant", content: data.response, suggestions: data.dataset_suggestions, suggestion: data.suggestion };
                setMessages((prev) => [...prev, aiMsg]);
                setRecipeState(data.state);
                setScoreboard(data.scoreboard || null);
                setUnread(data.unread || []);
                setSchemaChanges(data.schema_changes || []);
            } else {
                const err = await res.json().catch(() => ({}));
                setError(err.detail || translate(AI.ai_recipe_chat_error));
            }
        } catch {
            setError(translate(AI.ai_recipe_chat_error));
        } finally {
            setLoading(false);
        }
    }

    async function handleDatasetSelected(dsId: string, sessionId?: string) {
        const sid = sessionId ?? activeSessionId;
        if (!sid || !dsId) return;
        setLoading(true);
        setError("");
        try {
            const res = await apiFetch(
                `/api/recipes/ai/sessions/${sid}/dataset-selected`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        connectionId: selectedAIConnectionId
                            ? aiConnections.find(c => c.id === selectedAIConnectionId)?.connectionId ?? null
                            : null,
                        model: selectedModelCode || null,
                    }),
                }
            );
            if (res.ok) {
                const data = await res.json();
                syncMultiSelect(data.suggestion);
                const aiMsg: ChatMessage = { role: "assistant", content: data.response, suggestion: data.suggestion };
                setMessages((prev) => [...prev, aiMsg]);
                setRecipeState(data.state);
                setScoreboard(data.scoreboard || null);
                setUnread(data.unread || []);
                setSchemaChanges(data.schema_changes || []);
            } else {
                const err = await res.json().catch(() => ({}));
                setError(err.detail || translate(AI.ai_recipe_chat_error));
            }
        } catch {
            setError(translate(AI.ai_recipe_chat_error));
        } finally {
            setLoading(false);
        }
    }

    async function selectDataset(dsId: string) {
        // The same flow as the dataset dropdown: set the session's dataset, then
        // run the synthetic re-ground turn. Shared by the dropdown and by the
        // clickable suggestion chips rendered under assistant messages.
        setSelectedDatasetId(dsId);
        if (!dsId) return;
        if (activeSessionId) {
            const res = await apiFetch(`/api/recipes/ai/sessions/${activeSessionId}/dataset`, {
                method: "PATCH",
                body: JSON.stringify({ datasetId: dsId }),
            });
            if (!res.ok) {
                const err = await res.json().catch(() => ({}));
                setError(err.detail || translate(AI.ai_recipe_chat_error));
                return;
            }
            await handleDatasetSelected(dsId);
        } else {
            const newSessionId = await createSession(dsId);
            if (newSessionId) {
                await handleDatasetSelected(dsId, newSessionId);
            }
        }
    }

    async function selectDecision(piece: string, value: string) {
        // The clickable counterpart to typing a choice: apply the decision
        // directly (the /decision endpoint mutates the draft with the same
        // logic the set_* tools use) and re-ground the model.
        if (!activeSessionId || !piece || !value) return;
        setLoading(true);
        setError("");
        try {
            const res = await apiFetch(
                `/api/recipes/ai/sessions/${activeSessionId}/decision`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        piece,
                        value,
                        connectionId: selectedAIConnectionId
                            ? aiConnections.find(c => c.id === selectedAIConnectionId)?.connectionId ?? null
                            : null,
                        model: selectedModelCode || null,
                    }),
                }
            );
            if (res.ok) {
                const data = await res.json();
                syncMultiSelect(data.suggestion);
                const aiMsg: ChatMessage = { role: "assistant", content: data.response, suggestion: data.suggestion };
                setMessages((prev) => [...prev, aiMsg]);
                setRecipeState(data.state);
                setScoreboard(data.scoreboard || null);
                setUnread(data.unread || []);
                setSchemaChanges(data.schema_changes || []);
            } else {
                const err = await res.json().catch(() => ({}));
                setError(err.detail || translate(AI.ai_recipe_chat_error));
            }
        } catch {
            setError(translate(AI.ai_recipe_chat_error));
        } finally {
            setLoading(false);
        }
    }

    async function selectColumn(piece: string, field: string, column: string) {
        // The clickable counterpart to typing a column name: record the choice
        // directly via the /field-column endpoint and re-ground the model.
        if (!activeSessionId || !piece || !field || !column) return;
        setLoading(true);
        setError("");
        try {
            const res = await apiFetch(
                `/api/recipes/ai/sessions/${activeSessionId}/field-column`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        piece,
                        field,
                        column,
                        connectionId: selectedAIConnectionId
                            ? aiConnections.find(c => c.id === selectedAIConnectionId)?.connectionId ?? null
                            : null,
                        model: selectedModelCode || null,
                    }),
                }
            );
            if (res.ok) {
                const data = await res.json();
                syncMultiSelect(data.suggestion);
                const aiMsg: ChatMessage = { role: "assistant", content: data.response, suggestion: data.suggestion };
                setMessages((prev) => [...prev, aiMsg]);
                setRecipeState(data.state);
                setScoreboard(data.scoreboard || null);
                setUnread(data.unread || []);
                setSchemaChanges(data.schema_changes || []);
            } else {
                const err = await res.json().catch(() => ({}));
                setError(err.detail || translate(AI.ai_recipe_chat_error));
            }
        } catch {
            setError(translate(AI.ai_recipe_chat_error));
        } finally {
            setLoading(false);
        }
    }

    async function selectProposal(fields: ProposalField[]) {
        // Accept a proposal the model offered, as one click. Only the fields still
        // undecided are applied — the backend keeps a choice the user has made
        // since the offer, and names it in `skipped` so the reply can say so.
        if (!activeSessionId || !fields || fields.length === 0) return;
        setLoading(true);
        setError("");
        try {
            const res = await apiFetch(
                `/api/recipes/ai/sessions/${activeSessionId}/proposal`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        fields,
                        connectionId: selectedAIConnectionId
                            ? aiConnections.find(c => c.id === selectedAIConnectionId)?.connectionId ?? null
                            : null,
                        model: selectedModelCode || null,
                    }),
                }
            );
            if (res.ok) {
                const data = await res.json();
                syncMultiSelect(data.suggestion);
                const aiMsg: ChatMessage = { role: "assistant", content: data.response, suggestion: data.suggestion };
                setMessages((prev) => [...prev, aiMsg]);
                setRecipeState(data.state);
                setScoreboard(data.scoreboard || null);
                setUnread(data.unread || []);
                setSchemaChanges(data.schema_changes || []);
            } else {
                const err = await res.json().catch(() => ({}));
                setError(err.detail || translate(AI.ai_recipe_chat_error));
            }
        } catch {
            setError(translate(AI.ai_recipe_chat_error));
        } finally {
            setLoading(false);
        }
    }

    function syncMultiSelect(suggestion: Suggestion | undefined | null) {
        // A multi-field column suggestion opens the sticky selection control;
        // any other suggestion (or none) closes it.
        if (suggestion && suggestion.multi && suggestion.field) {
            setMultiSelect({
                piece: suggestion.piece,
                field: suggestion.field,
                choices: suggestion.choices,
                selected: [],
            });
        } else {
            setMultiSelect(null);
        }
    }

    async function toggleColumn(column: string) {
        if (!multiSelect || loading) return;
        // Optimistic local toggle, then a silent persist (no re-ground).
        setMultiSelect((prev) => {
            if (!prev) return prev;
            const selected = prev.selected.includes(column)
                ? prev.selected.filter((c) => c !== column)
                : [...prev.selected, column];
            return { ...prev, selected };
        });
        try {
            await apiFetch(`/api/recipes/ai/sessions/${activeSessionId}/field-column`, {
                method: "POST",
                body: JSON.stringify({
                    piece: multiSelect.piece,
                    field: multiSelect.field,
                    column,
                    action: "toggle",
                    connectionId: selectedAIConnectionId
                        ? aiConnections.find(c => c.id === selectedAIConnectionId)?.connectionId ?? null
                        : null,
                    model: selectedModelCode || null,
                }),
            });
        } catch { /* silent — the local toggle stands; Done reconciles */ }
    }

    async function finishColumnSelection() {
        if (!multiSelect || loading) return;
        const ms = multiSelect;
        setLoading(true);
        setError("");
        try {
            const res = await apiFetch(`/api/recipes/ai/sessions/${activeSessionId}/field-column`, {
                method: "POST",
                body: JSON.stringify({
                    piece: ms.piece,
                    field: ms.field,
                    action: "done",
                    connectionId: selectedAIConnectionId
                        ? aiConnections.find(c => c.id === selectedAIConnectionId)?.connectionId ?? null
                        : null,
                    model: selectedModelCode || null,
                }),
            });
            if (res.ok) {
                const data = await res.json();
                syncMultiSelect(data.suggestion);
                const aiMsg: ChatMessage = { role: "assistant", content: data.response, suggestion: data.suggestion };
                setMessages((prev) => [...prev, aiMsg]);
                setRecipeState(data.state);
                setScoreboard(data.scoreboard || null);
                setUnread(data.unread || []);
                setSchemaChanges(data.schema_changes || []);
            } else {
                const err = await res.json().catch(() => ({}));
                setError(err.detail || translate(AI.ai_recipe_chat_error));
            }
        } catch {
            setError(translate(AI.ai_recipe_chat_error));
        } finally {
            setLoading(false);
        }
    }

    async function handleRecipeLoaded(sessionId: string) {
        // Same shape as handleDatasetSelected: one short turn that re-grounds the
        // model on what the session now holds.
        setLoading(true);
        setError("");
        try {
            const res = await apiFetch(
                `/api/recipes/ai/sessions/${sessionId}/recipe-loaded`,
                {
                    method: "POST",
                    body: JSON.stringify({
                        connectionId: selectedAIConnectionId
                            ? aiConnections.find(c => c.id === selectedAIConnectionId)?.connectionId ?? null
                            : null,
                        model: selectedModelCode || null,
                    }),
                }
            );
            if (res.ok) {
                const data = await res.json();
                const aiMsg: ChatMessage = { role: "assistant", content: data.response };
                setMessages((prev) => [...prev, aiMsg]);
                setRecipeState(data.state);
                setScoreboard(data.scoreboard || null);
                setUnread(data.unread || []);
                setSchemaChanges(data.schema_changes || []);
            } else {
                const err = await res.json().catch(() => ({}));
                setError(err.detail || translate(AI.ai_recipe_chat_error));
            }
        } catch {
            setError(translate(AI.ai_recipe_chat_error));
        } finally {
            setLoading(false);
        }
    }

    const handleKeyDown = (e: React.KeyboardEvent) => {
        if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    };

    const scoreboardProgress = (sb: Scoreboard | null): string => {
        if (!sb) return "";
        if (sb.complete) {
            return translate(AI.ai_recipe_stage_complete);
        }
        const progress = translateParams(
            AI.ai_recipe_progress_decided.key,
            AI.ai_recipe_progress_decided.fallback,
            // `total` travels with the scoreboard; the count is what the draft has
            // decided. Neither number is typed at this call site.
            { count: sb.crystallised.length, total: sb.total },
        );

        // The next piece's sentence, beside the count — "5 of 6 decided · Name the
        // recipe". This is `whatText`'s consumer on the page, and it is the point of
        // the whole key-then-resolve design: an unresolved key would show here as
        // `recipes.scoreboard.name.what`, in a label every session displays, which
        // is the defect made visible rather than invisible.
        //
        // Which piece: the first pending one that carries a resolved sentence, in the
        // order the backend gave. No preference is expressed between pieces here, and
        // `surface` (added in Item 16) is deliberately not consulted: preferring an
        // `ask` piece over a `point` one is a judgement about what to put in front of
        // the user, which is Item 18's subject in the prompt rather than this label's.
        // Selecting on it now would be a behaviour change this item did not ask for.
        //
        // `whatText` may be absent — an older session, a piece the resolver could not
        // name — and then the count renders alone rather than an empty span.
        const next = sb.pending.find(p => p.whatText);
        if (!next?.whatText) return progress;

        return translateParams(
            ai_recipe_progress_next.key,
            ai_recipe_progress_next.fallback,
            { progress, next: next.whatText },
        );
    };

    const [mobileTab, setMobileTab] = useState<"sessions" | "chat">("chat");

    // The newest offer of each kind is the live one. Older chip rows stay visible —
    // they are part of the conversation — but they are inert, because a click on
    // one replays a snapshot the user has since moved past: a technique chip
    // clears every column chosen after it, and a proposal would overwrite choices
    // made since it was offered. `selectProposal` also keeps anything still
    // undecided, so the two rules cover different faults — this stops the
    // accident, that stops the overwrite within a single turn.
    const lastDecisionChipIndex = messages.reduce(
        (acc, m, i) => (m.role === "assistant" && m.suggestion && (m.suggestion.choices?.length ?? 0) > 0 ? i : acc),
        -1,
    );
    const lastDatasetChipIndex = messages.reduce(
        (acc, m, i) => (m.role === "assistant" && m.suggestions && m.suggestions.length > 0 ? i : acc),
        -1,
    );

    if (!isLanguageLoaded) return null;

    return (
        <ProtectedRoute>
            <style>{`
                .ai-recipe-layout {
                    display: grid;
                    grid-template-columns: 250px 1fr;
                    height: calc(100vh - 64px);
                    position: relative;
                    overflow: hidden;
                }
                .ai-recipe-layout > .sessions-panel { overflow: auto; background: var(--card); border-right: 1px solid var(--border); }
                .ai-recipe-layout > .chat-panel { display: flex; flex-direction: column; min-width: 0; overflow: hidden; }
                .ai-recipe-layout > .draft-panel {
                    position: absolute;
                    top: 0; right: 0; bottom: 0;
                    width: 340px;
                    max-width: 92vw;
                    border-left: 1px solid var(--border);
                    background: var(--card);
                    overflow: auto;
                    box-shadow: -6px 0 18px rgba(0, 0, 0, 0.08);
                    transform: translateX(100%);
                    transition: transform 0.25s ease;
                    z-index: 10;
                }
                .ai-recipe-layout > .draft-panel.open {
                    transform: translateX(0);
                }

                .ai-recipe-mobile-tabs { display: none; }
                .ai-recipe-mobile-tabs button {
                    flex: 1; padding: 0.5rem; border: none; background: transparent;
                    font-size: 0.82rem; cursor: pointer; color: var(--muted-foreground);
                    border-bottom: 2px solid transparent;
                }
                .ai-recipe-mobile-tabs button.active {
                    color: var(--primary); border-bottom-color: var(--primary);
                    font-weight: 600;
                }

                @media (max-width: 900px) {
                    .ai-recipe-layout {
                        grid-template-columns: 1fr !important;
                        grid-template-rows: auto 1fr;
                    }
                    .ai-recipe-layout > .sessions-panel { display: none; }
                    .ai-recipe-layout > .sessions-panel.mobile-visible { display: block; border-right: none; }
                    .ai-recipe-layout > .chat-panel.mobile-hidden { display: none; }
                    .ai-recipe-mobile-tabs { display: flex; border-bottom: 1px solid var(--border); background: var(--card); }
                }
            `}</style>
            <div className="ai-recipe-layout">
                {/* Tab bar (mobile only) */}
                <div className="ai-recipe-mobile-tabs" style={{ gridColumn: "1 / -1" }}>
                    <button className={mobileTab === "sessions" ? "active" : ""} onClick={() => setMobileTab("sessions")}>{translate(AI.ai_recipe_tab_sessions)}</button>
                    <button className={mobileTab === "chat" ? "active" : ""} onClick={() => setMobileTab("chat")}>{translate(AI.ai_recipe_tab_chat)}</button>
                    <button className={rightPanelOpen ? "active" : ""} onClick={() => { setRightPanelOpen(true); setMobileTab("chat"); }}>{translate(AI.ai_recipe_tab_draft)}</button>
                </div>

                {/* ============ LEFT: Sessions sidebar ============ */}
                <div className={`sessions-panel ${mobileTab === "sessions" ? "mobile-visible" : ""}`}>
                    <SessionsSidebar
                        sessions={sessions}
                        activeSessionId={activeSessionId}
                        onSelect={(id, isManual) => { loadSession(id, isManual); setMobileTab("chat"); }}
                        onCreateNew={() => createSession()}
                        onDelete={deleteSession}
                        onRename={renameSession}
                    />
                </div>

                {/* ============ CENTER: Chat ============ */}
                <div className={`chat-panel${mobileTab !== "chat" ? " mobile-hidden" : ""}`}>
                    {/* header */}
                    <div className="border-b border-border bg-card">
                        {/* Row 1: title + AI connection + model */}
                        <div style={{ padding: "0.5rem 1rem 0 1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <Bot className="text-primary" style={{ width: 20, height: 20 }} />
                            <span style={{ fontWeight: 600, fontSize: "0.95rem" }}>{translate(AI.ai_recipe_title)}</span>
                            <span className="text-xs text-muted-foreground">
                                {activeSessionId
                                    ? (sessions.find(s => s.sessionId === activeSessionId)?.displayName
                                        || recipeState?.goal
                                        || "")
                                    : translate(AI.ai_recipe_no_session)}
                            </span>
                            <select
                                value={selectedAIConnectionId}
                                onChange={(e) => setSelectedAIConnectionId(e.target.value)}
                                className="text-xs border border-border bg-card text-foreground" style={{ padding: "0.2rem 0.4rem", borderRadius: "4px", marginLeft: "0.5rem", maxWidth: "150px" }}
                            >
                                <option value="">{translate(AI.select_ai_connection_placeholder)}</option>
                                {aiConnections.map((c) => (
                                    <option key={c.id} value={c.id}>{c.name || c.provider}</option>
                                ))}
                            </select>
                            <select
                                value={selectedModelCode}
                                onChange={(e) => setSelectedModelCode(e.target.value)}
                                className="text-xs border border-border bg-card text-foreground" style={{ padding: "0.2rem 0.4rem", borderRadius: "4px", maxWidth: "160px" }}
                            >
                                <option value="">{translate(AI.select_model_placeholder)}</option>
                                {models.map((m) => (
                                    <option key={m.modelCode} value={m.modelCode}>{m.modelName || m.modelCode}</option>
                                ))}
                            </select>
                        </div>
                        {/* Row 2: dataset selector + toggle button */}
                        <div style={{ padding: "0.35rem 1rem 0.5rem 1rem", display: "flex", alignItems: "center", gap: "0.5rem" }}>
                            <select
                                value={selectedDatasetId}
                                onChange={(e) => selectDataset(e.target.value)}
                                className="text-xs border border-border bg-card text-foreground" style={{ padding: "0.2rem 0.4rem", borderRadius: "4px", maxWidth: "260px" }}
                            >
                                <option value="">{translate(AI.ai_recipe_select_dataset)}</option>
                                {visibleDatasets.map((d) => {
                                    const extra = [d.sourceType, d.databaseName].filter(Boolean).join(" · ");
                                    return (
                                        <option key={d.id} value={d.id}>
                                            {extra ? `${d.name}  —  ${extra}` : d.name}
                                        </option>
                                    );
                                })}
                            </select>
                            <Filter className="text-muted-foreground" style={{ width: 14, height: 14, flexShrink: 0 }} />
                            <select
                                value={datasetFilter}
                                onChange={(e) => setDatasetFilter(e.target.value || "all")}
                                className="text-xs border border-border bg-card text-foreground"
                                style={{ padding: "0.2rem 0.4rem", borderRadius: "4px" }}
                            >
                                <option value="all">{translate(DATASETS.filter.all)}</option>
                                <option value="virtual">{translate(DATASETS.filter.virtual)}</option>
                                <option value="upload">{translate(DATASETS.filter.uploads)}</option>
                                <option value="notebook">{translate(DATASETS.filter.notebooks)}</option>
                                <option value="postgresql">{translate(DATASETS.filter.postgresql)}</option>
                                <option value="mysql">{translate(DATASETS.filter.mysql)}</option>
                                <option value="mssql">{translate(DATASETS.filter.mssql)}</option>
                                <option value="access">{translate(DATASETS.filter.access)}</option>
                                <option value="cleaned">{translate(DATASETS.filter.cleaned)}</option>
                                <option value="shared">{translate(DATASETS.filter.shared)}</option>
                                <option value="not_shared">{translate(DATASETS.filter.not_shared)}</option>
                            </select>
                            {/* The progress label is its OWN element, never a fallback behind the
                                session name and the goal. As a third `||` branch it rendered only
                                for a session with neither — a session nobody has used — so a reader
                                never saw the count or the next step.

                                The colours are the app's own tokens, not invented ones: `--accent`
                                here is a *hover grey* (oklch 0.97) and `--accent-light` does not
                                exist, so `color: var(--accent)` rendered near-white text on a
                                transparent pill — invisible, though present in the DOM and
                                measuring 238x19 px. Measured in the browser, not guessed.
                                `bg-primary text-primary-foreground` is defined in both themes. */}
                            {activeSessionId && scoreboard && (
                                <span
                                    data-testid="recipe-progress"
                                    className="text-xs bg-primary text-primary-foreground"
                                    style={{
                                        borderRadius: 999,
                                        padding: "0.15rem 0.6rem",
                                        whiteSpace: "nowrap",
                                        flexShrink: 0,
                                    }}
                                >
                                    {scoreboardProgress(scoreboard)}
                                </span>
                            )}
                            <div style={{ flex: 1 }} />
                            <Button variant="ghost" size="icon" onClick={() => setRightPanelOpen(!rightPanelOpen)} title={translate(AI.ai_recipe_toggle_panel)}>
                                {rightPanelOpen ? <PanelRightClose style={{ width: 18, height: 18 }} /> : <PanelRightOpen style={{ width: 18, height: 18 }} />}
                            </Button>
                        </div>
                    </div>

                    {/* messages */}
                    <div style={{ flex: 1, overflow: "auto", padding: "1rem" }}>
                        {!loadingAIConnections && aiConnections.length === 0 && (
                            <div style={{ background: "#fee2e2", border: "1px solid #ef4444", borderRadius: "6px", padding: "0.75rem 1rem", marginBottom: "0.75rem", fontSize: "0.85rem", color: "#991b1b" }}>
                                {translate(AI.no_ai_connections)}
                            </div>
                        )}
                        {schemaChanges.length > 0 && (
                            <div style={{ background: "#fef3c7", border: "1px solid #f59e0b", borderRadius: "6px", padding: "0.5rem 0.75rem", marginBottom: "0.75rem", fontSize: "0.82rem" }}>
                                ⚠ {translate(AI.ai_recipe_schema_changes)} {schemaChanges.join("; ")}
                            </div>
                        )}
                        {!activeSessionId && messages.length === 0 && (
                            <div className="text-muted-foreground" style={{ textAlign: "center", padding: "3rem 1rem" }}>
                                <Bot style={{ width: 48, height: 48, marginBottom: "1rem", opacity: 0.3 }} />
                                <p style={{ fontSize: "0.95rem" }}>{translate(AI.ai_recipe_welcome)}</p>
                                <p style={{ fontSize: "0.82rem", marginTop: "0.5rem" }}>{translate(AI.ai_recipe_create_prompt)}</p>
                                <Button onClick={() => createSession()} style={{ marginTop: "1rem" }}>
                                    <PlusCircle style={{ width: 16, height: 16, marginRight: 6 }} />
                                    {translate(AI.ai_recipe_new_session)}
                                </Button>
                            </div>
                        )}
                        {messages.map((msg, i) => (
                            <div key={i} style={{ display: "flex", gap: "0.75rem", marginBottom: "1rem", justifyContent: msg.role === "user" ? "flex-end" : "flex-start" }}>
                                {msg.role === "assistant" && (
                                    <div className="bg-muted" style={{ width: 32, height: 32, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                                        <Bot className="text-primary" style={{ width: 18, height: 18 }} />
                                    </div>
                                )}
                                <div style={{
                                    maxWidth: "75%",
                                    borderRadius: "8px",
                                    fontSize: "0.9rem",
                                    lineHeight: 1.5,
                                    background: msg.role === "user" ? "var(--primary)" : "var(--secondary)",
                                    color: msg.role === "user" ? "var(--primary-foreground)" : "var(--secondary-foreground)",
                                }}>
                                    <div style={{ padding: "0.6rem 0.6rem 0.6rem 0.85rem" }}>
                                        <div className="text-sm"><MarkdownContent>{msg.content}</MarkdownContent></div>
                                        {msg.role === "assistant" && msg.suggestions && msg.suggestions.length > 0 && (
                                            <div style={{ marginTop: "0.5rem" }}>
                                                {/* The chip row is shared with the virtual-dataset page
                                                    (Item 15). The caller decides what a chip means and
                                                    what it reads; the row is the component's. */}
                                                <SuggestionChips
                                                    items={msg.suggestions.map((s) => ({ key: s.id, label: s.name }))}
                                                    onPick={selectDataset}
                                                    disabled={loading || i !== lastDatasetChipIndex}
                                                />
                                                {i !== lastDatasetChipIndex && (
                                                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
                                                        {translate(ai_recipe_chip_superseded)}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                        {msg.role === "assistant" && msg.suggestion && msg.suggestion.piece === "name" && (
                                            <div style={{ marginTop: "0.5rem" }}>
                                                {/* The same affordance the virtual concierge uses, and for
                                                    the same recorded reason: a single chip makes the offer
                                                    look like a closed set, so the user has no obvious way to
                                                    supply their own. An editable field holding the proposal
                                                    makes accepting one click and replacing it one edit — and
                                                    with no proposal it is simply an empty field to type in,
                                                    which is the fallback that guarantees a way to name. */}
                                                <NameSuggestion
                                                    suggestion={(msg.suggestion.choices && msg.suggestion.choices[0]) || ""}
                                                    onAccept={(name) => selectDecision("name", name)}
                                                    disabled={loading}
                                                    labels={{
                                                        heading: translate(name_suggestion_heading),
                                                        accept: translate(name_suggestion_accept),
                                                        placeholder: translate(RECIPES.editor_name_placeholder),
                                                    }}
                                                />
                                            </div>
                                        )}
                                        {msg.role === "assistant" && msg.suggestion && msg.suggestion.piece === "proposal" && msg.suggestion.choices && msg.suggestion.choices.length > 0 && (
                                            <div style={{ marginTop: "0.5rem" }}>
                                                {/* One chip, labelled by the model in this turn's
                                                    language. Deliberately not a declared key: a key
                                                    resolves from the stored language column while the
                                                    model answers in the language the user writes in,
                                                    so the two could disagree on screen (§3.12a). */}
                                                <SuggestionChips
                                                    items={[{ key: "proposal", label: msg.suggestion.label || msg.suggestion.choices[0] }]}
                                                    onPick={() => selectProposal(msg.suggestion!.fields || [])}
                                                    disabled={loading || i !== lastDecisionChipIndex}
                                                />
                                                {i !== lastDecisionChipIndex && (
                                                    <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
                                                        {translate(ai_recipe_chip_superseded)}
                                                    </div>
                                                )}
                                            </div>
                                        )}
                                        {msg.role === "assistant" && msg.suggestion && msg.suggestion.piece !== "proposal" && msg.suggestion.piece !== "name" && msg.suggestion.choices && msg.suggestion.choices.length > 0 && !msg.suggestion.multi && (() => {
                                            const sg = msg.suggestion!;
                                            const isField = sg.piece === "technique_fields" || sg.piece === "output_fields";
                                            // What a chip READS stays here: the labels differ per piece and
                                            // resolving them needs the recipe model, which the row has no
                                            // business knowing.
                                            const chipItem = (key: string) => ({
                                                key,
                                                label: isField
                                                    ? key
                                                    : (sg.piece === "technique"
                                                        ? (recipeModel?.algorithms?.[key]?.label ? translate(recipeModel.algorithms[key].label) : key)
                                                        : (OUTPUT_LABELS[key] ? translate(OUTPUT_LABELS[key]) : key)),
                                            });
                                            const items = sg.choices.map(chipItem);
                                            // The cap's remainder, resolved through the same
                                            // mapping — an expanded row must not show a raw key
                                            // where the collapsed one showed a name.
                                            const overflow = (sg.overflow || []).map(chipItem);
                                            return (
                                                <div style={{ marginTop: "0.5rem" }}>
                                                    <SuggestionChips
                                                        items={items}
                                                        onPick={(key) => (isField
                                                            ? selectColumn(sg.piece, sg.field!, key)
                                                            : selectDecision(sg.piece, key))}
                                                        disabled={loading || i !== lastDecisionChipIndex}
                                                        heading={sg.headingText}
                                                        withheld={sg.withheld}
                                                        overflowItems={overflow}
                                                        expandLabel={translateParams(
                                                            ai_recipe_chip_expand.key,
                                                            ai_recipe_chip_expand.fallback,
                                                            { count: sg.withheld ?? 0 },
                                                        )}
                                                        collapseLabel={translate(ai_recipe_chip_collapse)}
                                                        withheldLabel={sg.withheld
                                                            ? translateParams(
                                                                ai_recipe_chip_withheld.key,
                                                                ai_recipe_chip_withheld.fallback,
                                                                { count: sg.withheld },
                                                            )
                                                            : undefined}
                                                    />
                                                    {i !== lastDecisionChipIndex && (
                                                        <div style={{ fontSize: "0.72rem", color: "var(--text-muted)", marginTop: "0.2rem" }}>
                                                            {translate(ai_recipe_chip_superseded)}
                                                        </div>
                                                    )}
                                                </div>
                                            );
                                        })()}
                                        <div style={{ display: "flex", justifyContent: "flex-end", gap: "0.25rem", marginTop: "0.35rem" }}>
                                            {msg.role === "assistant" && (
                                                <button
                                                    onClick={() => speakMessage(msg.content, i)}
                                                    style={{
                                                        border: "none", background: "transparent", cursor: "pointer",
                                                        padding: "2px", borderRadius: "3px", opacity: 0.5,
                                                    }}
                                                    title={speakingMsgIndex === i ? "Stop" : "Read aloud"}
                                                >
                                                    {speakingMsgIndex === i
                                                        ? <Square style={{ width: 14, height: 14 }} />
                                                        : <Volume2 style={{ width: 14, height: 14 }} />
                                                    }
                                                </button>
                                            )}
                                            <CopyButton text={msg.content} />
                                        </div>
                                    </div>
                                </div>
                                {msg.role === "user" && (
                                    <div style={{ width: 32, height: 32, borderRadius: "50%", background: "var(--primary)", display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0 }}>
                                        <User style={{ width: 18, height: 18, color: "var(--primary-foreground)" }} />
                                    </div>
                                )}
                            </div>
                        ))}
                        {loading && (
                            <div className="text-progress" style={{ display: "flex", alignItems: "center", gap: "0.5rem", padding: "0.5rem", fontSize: "0.85rem" }}>
                                <Loader2 style={{ width: 16, height: 16, animation: "spin 1s linear infinite" }} />
                                {translate(AI.thinking)}
                            </div>
                        )}
                        <div ref={messagesEndRef} />
                    </div>

                    {/* multi-column selection — a sticky control opened by a multi-field suggestion */}
                    {multiSelect && (
                        <div style={{ borderTop: "1px solid var(--border)", background: "var(--card)", padding: "0.5rem 1rem" }}>
                            <div style={{ fontSize: "0.7rem", color: "var(--muted-foreground)", textTransform: "uppercase", letterSpacing: "0.02em", marginBottom: "0.25rem" }}>
                                {translate(AI.ai_recipe_stage_columns)}
                            </div>
                            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.4rem" }}>
                                {multiSelect.choices.map((col) => {
                                    const isSelected = multiSelect.selected.includes(col);
                                    return (
                                        <button
                                            key={col}
                                            onClick={() => toggleColumn(col)}
                                            disabled={loading}
                                            style={{
                                                border: isSelected ? "1px solid var(--primary)" : "1px solid var(--border)",
                                                background: isSelected ? "var(--primary)" : "var(--card)",
                                                color: isSelected ? "var(--primary-foreground)" : "var(--foreground)",
                                                borderRadius: "999px",
                                                padding: "0.25rem 0.7rem",
                                                fontSize: "0.78rem",
                                                lineHeight: 1.4,
                                                cursor: loading ? "not-allowed" : "pointer",
                                            }}
                                        >
                                            {col}
                                        </button>
                                    );
                                })}
                                <button
                                    onClick={() => finishColumnSelection()}
                                    disabled={loading}
                                    style={{
                                        border: "1px solid var(--primary)",
                                        background: "var(--primary)",
                                        color: "var(--primary-foreground)",
                                        borderRadius: "999px",
                                        padding: "0.25rem 0.7rem",
                                        fontSize: "0.78rem",
                                        lineHeight: 1.4,
                                        fontWeight: 600,
                                        cursor: loading ? "not-allowed" : "pointer",
                                    }}
                                >
                                    {translate(AI.ai_recipe_done)}
                                </button>
                            </div>
                        </div>
                    )}

                    {/* persistent error — pinned above the input so it stays in view */}
                    {unread.length > 0 && (
                        <div style={{ background: "#fef3c7", border: "1px solid #f59e0b", padding: "0.5rem 1rem", fontSize: "0.82rem", color: "#92400e" }}>
                            <div>{translate(ai_recipe_unread_sources)}</div>
                            <ul style={{ margin: "0.25rem 0 0 1rem", padding: 0, fontSize: "0.75rem" }}>
                                {unread.map((u, idx) => (
                                    <li key={`${u.alias}-${idx}`}>
                                        <strong>{u.alias}</strong>: {u.stateText || u.reason}
                                        {/* The driver's own words, demoted. It is the one
                                            string no translation can render — two backends,
                                            two drivers, two sentences for one failure — so
                                            it stays as the diagnostic a support question
                                            needs, not as the sentence the reader acts on. */}
                                        {u.stateText && u.reason && (
                                            <span style={{ display: "block", opacity: 0.7, fontSize: "0.7rem" }}>
                                                {u.reason}
                                            </span>
                                        )}
                                    </li>
                                ))}
                            </ul>
                        </div>
                    )}

                    {error && (
                        <div style={{ background: "#fee2e2", border: "1px solid #ef4444", padding: "0.5rem 1rem", fontSize: "0.82rem", color: "#991b1b" }}>
                            {error}
                        </div>
                    )}

                    {/* input */}
                    {activeSessionId && (
                        <div className="border-t border-border bg-card" style={{ padding: "0.75rem 1rem", display: "flex", gap: "0.5rem" }}>
                            <AudioToggle
                                micEnabled={micEnabled}
                                onMicChange={setMicEnabled}
                                speakerEnabled={speakerEnabled}
                                onSpeakerChange={setSpeakerEnabled}
                                volume={volume}
                                onVolumeChange={setVolume}
                                speakerMuted={speakerMuted}
                                onSpeakerMuteToggle={() => {
                                    const next = !speakerMuted;
                                    setSpeakerMuted(next);
                                    setSpeakerEnabled(!next);
                                    const s = getCachedSettings("recipe");
                                    s.speakerMuted = next;
                                    setCachedSettings("recipe", s);
                                }}
                                speechState={speechState}
                                onPause={pause}
                                onResume={resume}
                                onStop={stop}
                                onSettingsClick={() => setSettingsOpen(true)}
                            />
                            <Input dir="auto"
                                ref={inputRef}
                                key={activeSessionId}
                                value={input}
                                onChange={(e) => setInput(e.target.value)}
                                onKeyDown={handleKeyDown}
                                placeholder={translate(AI.ai_recipe_input_placeholder) || "Ask about your data..."}
                                disabled={loading}
                                autoFocus
                                style={{ flex: 1 }}
                            />
                            <Button onClick={sendMessage} disabled={loading || !input.trim()} size="icon">
                                <Send style={{ width: 16, height: 16 }} />
                            </Button>
                        </div>
                    )}
                    <AudioSettingsDialog open={settingsOpen} onClose={() => setSettingsOpen(false)} chatType="recipe" />
                </div>

                {/* ============ RIGHT: Recipe draft preview (slide-out drawer) ============ */}
                <div className={`draft-panel${rightPanelOpen ? " open" : ""}`} style={{ padding: "1rem", fontSize: "0.85rem" }}>
                    <div style={{ display: "flex", alignItems: "center", justifyContent: "space-between", marginBottom: "0.75rem" }}>
                        <h3 className="text-primary" style={{ fontSize: "0.9rem", fontWeight: 600, margin: 0 }}>{translate(AI.ai_recipe_draft_title)}</h3>
                        <div style={{ display: "flex", alignItems: "center", gap: "0.4rem" }}>
                            {recipeState && (
                                <span style={{
                                    fontSize: "0.68rem",
                                    padding: "0.1rem 0.45rem",
                                    borderRadius: "3px",
                                    fontWeight: 600,
                                    textTransform: "uppercase",
                                    background: recipeState.expertise_level === "expert" ? "#dcfce7" : recipeState.expertise_level === "intermediate" ? "#dbeafe" : "#f1f5f9",
                                    color: recipeState.expertise_level === "expert" ? "#16a34a" : recipeState.expertise_level === "intermediate" ? "#1d4ed8" : "#94a3b8",
                                }}>
                                    {recipeState.expertise_level}
                                </span>
                            )}
                            <Button variant="ghost" size="icon" onClick={() => setRightPanelOpen(false)} title={translate(AI.ai_recipe_toggle_panel)}>
                                <PanelRightClose style={{ width: 16, height: 16 }} />
                            </Button>
                        </div>
                    </div>
                    {!recipeState || !recipeState.stages?.length ? (
                        <p className="text-muted-foreground" style={{ fontSize: "0.8rem" }}>
                            {translate(AI.ai_recipe_draft_empty)}
                        </p>
                    ) : (
                        <div style={{ display: "flex", flexDirection: "column", gap: "0.7rem" }}>
                            {recipeState.goal && (
                                <div className="text-muted-foreground" style={{ fontSize: "0.82rem" }}>{recipeState.goal}</div>
                            )}

                            {/* Dataset */}
                            <section>
                                <div className="text-muted-foreground" style={{ fontWeight: 600, fontSize: "0.72rem", textTransform: "uppercase", marginBottom: "2px" }}>{translate(AI.ai_recipe_draft_dataset)}</div>
                                <div style={{ fontWeight: 600 }}>{draft.datasetName || "—"}</div>
                                {displayColumns.length > 0 && (
                                    <div style={{ display: "flex", flexWrap: "wrap", gap: "0.25rem", marginTop: "0.35rem" }}>
                                        {displayColumns.map((c, i) => (
                                            <span key={i} className="bg-muted text-primary" style={{ fontSize: "0.7rem", padding: "0.05rem 0.45rem", borderRadius: "999px" }}>{c.name}</span>
                                        ))}
                                    </div>
                                )}
                                {manageTransformsUrl && (
                                    <div style={{ marginTop: "0.5rem" }}>
                                        <div className="text-muted-foreground" style={{ fontWeight: 600, fontSize: "0.72rem", textTransform: "uppercase", marginBottom: "2px" }}>{translate(RECIPES.transforms_label)}</div>
                                        {selectedTransforms.length > 0 ? (
                                            <div style={{ display: "flex", flexWrap: "wrap", gap: "0.25rem" }}>
                                                {selectedTransforms.map((t) => (
                                                    <span key={t.id} title={t.description || undefined} className="bg-muted text-primary" style={{ fontSize: "0.7rem", padding: "0.05rem 0.45rem", borderRadius: "999px" }}>{t.name}</span>
                                                ))}
                                            </div>
                                        ) : (
                                            <span className="text-muted-foreground" style={{ fontSize: "0.78rem" }}>—</span>
                                        )}
                                        <a href={manageTransformsUrl} className="text-primary underline" style={{ display: "inline-block", marginTop: "0.35rem", fontSize: "0.78rem" }}>{translate(RECIPES.transforms_manage_button)}</a>
                                    </div>
                                )}
                            </section>

                            {/* Algorithm */}
                            {draft.algorithmType && (
                                <section>
                                    <div className="text-muted-foreground" style={{ fontWeight: 600, fontSize: "0.72rem", textTransform: "uppercase", marginBottom: "2px" }}>{translate(AI.ai_recipe_draft_algorithm)}</div>
                                    <div style={{ fontWeight: 600 }}>{recipeModel?.algorithms[draft.algorithmType]?.label ? translate(recipeModel.algorithms[draft.algorithmType].label) : draft.algorithmType}</div>
                                    {(recipeModel?.algorithms[draft.algorithmType]?.fields || []).map((field) => (
                                        <div key={field} style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", marginTop: "0.25rem" }}>
                                            <span className="text-muted-foreground">{fieldLabel(field)}</span>
                                            <span style={{ textAlign: "right" }}>{fieldValue(draft.algorithmConfig[field])}</span>
                                        </div>
                                    ))}
                                </section>
                            )}

                            {/* Output */}
                            {draft.outputType && (
                                <section>
                                    <div className="text-muted-foreground" style={{ fontWeight: 600, fontSize: "0.72rem", textTransform: "uppercase", marginBottom: "2px" }}>{translate(AI.ai_recipe_draft_output)}</div>
                                    <div style={{ fontWeight: 600 }}>{outputLabel(draft.outputType)}</div>
                                    {draft.outputType !== "none" && (recipeModel?.outputs[draft.outputType]?.fields || []).map((field) => (
                                        <div key={field} style={{ display: "flex", justifyContent: "space-between", gap: "0.5rem", marginTop: "0.25rem" }}>
                                            <span className="text-muted-foreground">{fieldLabel(field)}</span>
                                            <span style={{ textAlign: "right" }}>{fieldValue(draft.outputConfig[field])}</span>
                                        </div>
                                    ))}
                                </section>
                            )}

                            {validation.errors.length > 0 && (
                                <div style={{ background: "#fef2f2", border: "1px solid #ef4444", borderRadius: "6px", padding: "0.5rem" }}>
                                    <div style={{ fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase", color: "#dc2626", marginBottom: "4px" }}>{translate(AI.ai_recipe_errors_heading)}</div>
                                    <ul style={{ margin: 0, paddingLeft: "1rem", fontSize: "0.78rem", color: "#7f1d1d" }}>
                                        {validation.errors.map((issue, i) => (
                                            <li key={i}>{translateParams(issue.key, issue.fallback, issue.params)}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            {validation.warnings.length > 0 && (
                                <div style={{ background: "#fffbeb", border: "1px solid #f59e0b", borderRadius: "6px", padding: "0.5rem" }}>
                                    <div style={{ fontSize: "0.72rem", fontWeight: 600, textTransform: "uppercase", color: "#b45309", marginBottom: "4px" }}>{translate(AI.ai_recipe_warnings_heading)}</div>
                                    <ul style={{ margin: 0, paddingLeft: "1rem", fontSize: "0.78rem", color: "#78350f" }}>
                                        {validation.warnings.map((issue, i) => (
                                            <li key={i}>{translateParams(issue.key, issue.fallback, issue.params)}</li>
                                        ))}
                                    </ul>
                                </div>
                            )}
                            {validation.errors.length === 0 && !savedRecipeId && (
                                <Button onClick={saveRecipe} disabled={saving} size="sm" style={{ marginTop: "0.5rem", width: "100%" }}>
                                    {saving ? translate(AI.ai_recipe_saving) : translate(AI.ai_recipe_save)}
                                </Button>
                            )}
                            {savedRecipeId && (
                                <div style={{ marginTop: "0.5rem", background: "#dcfce7", border: "1px solid #16a34a", borderRadius: "6px", padding: "0.5rem", fontSize: "0.8rem" }}>
                                    {translate(AI.ai_recipe_saved)}
                                    <a href={`/recipes/${savedRecipeId}`} className="text-primary" style={{ marginLeft: "0.25rem", fontWeight: 600 }}>
                                        {translate(AI.ai_recipe_open)}
                                    </a>
                                </div>
                            )}
                        </div>
                    )}
                </div>
            </div>
        </ProtectedRoute>
    );
}

// useSearchParams() client-side renders the tree up to the nearest Suspense
// boundary, so the boundary belongs here, around the content — the same shape
// app/recipes/page.tsx uses.
export default function AIChefPage() {
    return (
        <Suspense fallback={null}>
            <AIChefContent />
        </Suspense>
    );
}