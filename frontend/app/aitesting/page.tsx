// frontend/app/aitesting/page.tsx
"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
    Select,
    SelectContent,
    SelectItem,
    SelectTrigger,
    SelectValue,
} from "@/components/ui/select";
import { Check, Loader2, Play, RefreshCw, Square, X } from "lucide-react";
import { toast } from "sonner";
import { TestStateBadge, type TestState } from "@/components/test-state-badge";
import { apiFetch } from "@/lib/api";
import { useAI } from "@/lib/ai-context";
import { useTranslation } from "@/lib/translation-context";
import {
    useTranslate,
    useTranslateWithParams,
    getErrorMessageFromData,
} from "@/lib/translation-helpers";
import { ProtectedRoute } from "@/components/protected-route";

import { AI_TESTING } from "./translations";
import { CHAT } from "@/app/chat/translations";
import { COMMON } from "@/app/common/translations";

interface RegisteredTest {
    id: string;
    duration: string;
    requiresDataset: boolean;
}

interface ProviderModelRow {
    id: number;
    modelCode: string;
    modelName: string;
    enabled: boolean;
    preferred: boolean;
    comment: string | null;
    testResults: Record<
        string,
        {
            state: TestState;
            testedAt?: string;
            reason?: string;
        }
    >;
    /**
     * What THIS connection measured, keyed by test id — a different record from
     * `testResults`, and deliberately so.
     *
     * Capability lives on the model (`testResults`) because it is a fact about the
     * model. Performance lives on the connection-model pairing
     * (`connectionTestResults`) because how long a run took is a fact about the host
     * that ran it. A model that passed in 4.6 s on one machine and took 189 s on
     * another is `pass` in both, with two durations, and neither contradicts the
     * other.
     */
    connectionTestResults?: Record<
        string,
        { durationMs?: number; outcome?: string; at?: string }
    >;
}

/** A run waiting for its second press, after the cost warning. */
type PendingConfirm =
    | { kind: "model"; modelId: number; runs: number }
    | { kind: "bulk"; runs: number };

/**
 * Whether this model has a capability verdict for a test.
 *
 * `pass` and `fail` are verdicts; everything else is an absence of evidence. The
 * page must use this rather than a truthiness test on the row, because an
 * INCONCLUSIVE run leaves a record that is truthy but carries no state — see the
 * note in `runOne`. Counting that as "tested" would make a sweep skip the one model
 * it most needs to retry.
 */
const hasVerdict = (model: ProviderModelRow, testId: string): boolean => {
    const state = model.testResults?.[testId]?.state;
    return state === "pass" || state === "fail";
};

interface AvailableConnection {
    id: string;
    connectionId: number;
    name: string;
    provider: string;
    isOwn: boolean;
}

function AITestingContent() {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    const translateWithParams = useTranslateWithParams();
    const router = useRouter();
    // The user's default AI connection, resolved once by the context from
    // `/api/user-settings`. Read from the context rather than fetched here: the
    // settings page writes it, the context is what every other page reads it
    // through, and a second fetch would be a second definition of "the default".
    const { defaultConnectionId } = useAI();

    const [connections, setConnections] = useState<AvailableConnection[]>([]);
    const [tests, setTests] = useState<RegisteredTest[]>([]);
    const [models, setModels] = useState<ProviderModelRow[]>([]);
    const [loadingModels, setLoadingModels] = useState(false);
    const [selectedId, setSelectedId] = useState<string | null>(null);
    const [loading, setLoading] = useState(true);
    // Persistent, not a toast: the project rule is that an error stays visible
    // until the user acts on it.
    const [loadError, setLoadError] = useState<string | null>(null);
    const [modelsError, setModelsError] = useState<string | null>(null);
    // Discovery state, kept separate from modelsError: one says "the list could not
    // be read", the other says "the server was asked and here is what it said".
    const [discovering, setDiscovering] = useState(false);
    const [discoverError, setDiscoverError] = useState<string | null>(null);
    const [discoverNote, setDiscoverNote] = useState<string | null>(null);
    // Bumped after a successful discovery so the models effect re-runs. A counter
    // rather than a direct reload call: the effect already owns the loading flags,
    // the cancelled guard and the error shape, and a second copy of that fetch
    // would be a second place for them to drift.
    const [discoverVersion, setDiscoverVersion] = useState(0);
    // The user's effective slow-model limit, in seconds. Null means "not known", and
    // that is shown rather than assumed: without it nothing can be marked too slow, and
    // silently marking nothing would look like "every model is fast enough".
    const [slowLimitSeconds, setSlowLimitSeconds] = useState<number | null>(null);
    const [slowLimitError, setSlowLimitError] = useState<string | null>(null);
    // A limit for THIS page and THIS session, so a reader who is testing a slow
    // model can stop every cell reading "over your 30 s limit" without changing a
    // stored setting that applies to everyone. Deliberately not persisted and not
    // sent anywhere: writing it would need a save, a permission and a decision,
    // and the thing being asked for is a view, not a preference.
    const [sessionLimit, setSessionLimit] = useState<string>("");

    // What the badges compare against: the session value when it is a usable
    // number, otherwise the saved one. Derived rather than stored, so clearing the
    // field returns to the saved limit with no second piece of state to keep true.
    const effectiveLimitSeconds: number | null = (() => {
        const trimmed = sessionLimit.trim();
        if (trimmed === "") return slowLimitSeconds;
        const n = Number(trimmed);
        return Number.isFinite(n) && n > 0 ? n : slowLimitSeconds;
    })();

    // Which cells and rows are in flight. Keys are `${modelId}:${testId}` for a
    // single test, and a Set rather than a flag so two runs can proceed
    // independently — starting a quick `tools` should not block the UI while a
    // slow `turn` is still going.
    const [runningCells, setRunningCells] = useState<Set<string>>(new Set());
    const [runningModel, setRunningModel] = useState<number | null>(null);
    const [bulkRunning, setBulkRunning] = useState(false);
    // Cancellation is a flag the sequence checks between steps, not an
    // AbortController: what must be stoppable is the *sequence*, and results
    // already recorded stay recorded because each request completes before the
    // next begins.
    const cancelRequested = useRef(false);
    // Per-cell error text, persistent until that cell is re-run (D9).
    const [runErrors, setRunErrors] = useState<Record<string, string>>({});
    // The cost warning's second press (Item 14: "require a second press").
    const [pendingConfirm, setPendingConfirm] = useState<PendingConfirm | null>(null);

    useEffect(() => {
        let cancelled = false;
        const loadConnections = async () => {
            try {
                const res = await apiFetch("/api/user/ai-connections/available");
                if (!res.ok) {
                    throw new Error(String(res.status));
                }
                const data = await res.json();
                if (cancelled) return;
                setConnections(data.connections || []);
            } catch (error) {
                if (cancelled) return;
                setLoadError(
                    translateWithParams(
                        AI_TESTING.load_error.key,
                        AI_TESTING.load_error.fallback,
                        { detail: error instanceof Error ? error.message : "" },
                    ),
                );
            } finally {
                if (!cancelled) setLoading(false);
            }
        };
        /**
         * The user's effective slow-model limit, read from the settings endpoint that
         * already resolves it.
         *
         * Resolved, not derived here: `modelSlowThresholdEffectiveSeconds` comes from
         * the same function the profile page shows and the admin page writes, so this
         * page cannot disagree with either about what the limit is. A second derivation
         * would be the drift that function exists to prevent.
         */
        const loadSlowLimit = async () => {
            try {
                const res = await apiFetch("/api/user-settings");
                if (!res.ok) throw new Error(String(res.status));
                const data = await res.json();
                if (cancelled) return;
                const effective = data?.modelSlowThresholdEffectiveSeconds;
                if (typeof effective === "number") {
                    setSlowLimitSeconds(effective);
                    setSlowLimitError(null);
                } else {
                    // The endpoint answered but without the field: say so rather than
                    // treating "absent" as "no limit exists".
                    setSlowLimitError(
                        translate(AI_TESTING.slow_limit_unavailable),
                    );
                }
            } catch (error) {
                if (cancelled) return;
                // Not fatal: the table still works. But it is said out loud, because a
                // page that marks nothing as too slow looks like one where nothing is.
                setSlowLimitError(
                    translateWithParams(
                        AI_TESTING.slow_limit_failed.key,
                        AI_TESTING.slow_limit_failed.fallback,
                        { detail: error instanceof Error ? error.message : String(error) },
                    ),
                );
            }
        };

        loadConnections();
        void loadSlowLimit();
        return () => {
            cancelled = true;
        };
        // translate is stable for a loaded language; re-running on it would
        // refetch every time the language changed.
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    /**
     * WHICH connection opens selected.
     *
     * The default is selected, not the first row: `/available` returns connections
     * in creation order, so `connections[0]` is the OLDEST one — the least likely
     * to be the one in use. Measured 2026-11-19: the admin's default was connection
     * 4 and this page opened on connection 3.
     *
     * A separate effect rather than part of the loader, because the default arrives
     * from its own request inside the AI context and may land after the connections
     * do. As a loader dependency it would re-fetch the list and the slow limit for a
     * value that only decides a `useState`; here it costs one render.
     *
     * `prev ?? choice` is what stops a slow settings response from overwriting a
     * connection the user has already picked. And the default must also BE in this
     * list — the context reads `/api/user-ai-connections` while this page reads
     * `/available`, and those sets differ — because a selected value with no matching
     * option renders a blank trigger, which is a worse fault than opening on the
     * first row. A default that is absent therefore falls back rather than being set.
     */
    useEffect(() => {
        if (connections.length === 0) return;
        const byDefault = defaultConnectionId
            ? connections.find(c => c.id === String(defaultConnectionId))
            : undefined;
        const choice = byDefault ?? connections[0];
        setSelectedId(prev => prev ?? choice?.id ?? null);
    }, [connections, defaultConnectionId]);

    // The model rows and the registered tests come from one response: the
    // page needs both, and a second request for a list that never changes
    // mid-session is cost without benefit.
    //
    // `?enabled=true` is deliberately NOT sent: a disabled model's results are
    // still worth seeing here, and the table shows an Enabled column so the
    // difference is visible rather than implied.
    useEffect(() => {
        if (!selectedId) {
            setModels([]);
            return;
        }
        let cancelled = false;
        setLoadingModels(true);
        setModelsError(null);
        // Switching connection invalidates everything the previous one produced.
        // A per-cell error belongs to a model on the OLD connection, and leaving
        // it rendered shows a failure beside a table it does not describe; a
        // pending cost confirmation was computed from the old row count.
        setRunErrors({});
        setPendingConfirm(null);
        setDiscoverError(null);
        setDiscoverNote(null);
        cancelRequested.current = false;
        const load = async () => {
            try {
                const res = await apiFetch(`/api/user/ai-connections/${selectedId}/models`);
                if (!res.ok) throw new Error(String(res.status));
                const data = await res.json();
                if (cancelled) return;
                setModels(data.models || []);
                setTests(data.tests || []);
            } catch (error) {
                if (cancelled) return;
                setModelsError(
                    translateWithParams(
                        AI_TESTING.load_error.key,
                        AI_TESTING.load_error.fallback,
                        { detail: error instanceof Error ? error.message : "" },
                    ),
                );
                setModels([]);
            } finally {
                if (!cancelled) setLoadingModels(false);
            }
        };
        load();
        return () => {
            cancelled = true;
        };
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, [selectedId, discoverVersion]);

    /**
     * Ask this connection's server what it serves, and record the answer.
     *
     * The route is POST /{id}/models/discover — the walk that was built in Item 15
     * and, until Item 31, reached by nothing. It answers COUNTS rather than a list,
     * so the table is re-read afterwards instead of being filled from the response:
     * one shape of "what does this connection serve" is enough.
     *
     * A failure is shown beside the button and stays there, rather than as a toast
     * that disappears — the message names what the server said, which is the thing
     * a user needs in order to act on it.
     */
    const discoverModels = async () => {
        if (!selectedId || discovering) return;
        setDiscovering(true);
        setDiscoverError(null);
        setDiscoverNote(null);
        try {
            const res = await apiFetch(
                `/api/user/ai-connections/${selectedId}/models/discover`,
                { method: "POST" },
            );
            const data = await res.json().catch(() => ({}));
            if (!res.ok) {
                throw new Error(
                    getErrorMessageFromData(translate, data, AI_TESTING.discover_failed),
                );
            }
            setDiscoverNote(
                translateWithParams(
                    AI_TESTING.discover_result.key,
                    AI_TESTING.discover_result.fallback,
                    {
                        seen: data.modelsSeen ?? 0,
                        created: data.connectionModelsCreated ?? 0,
                        refreshed: data.connectionModelsRefreshed ?? 0,
                        pruned: data.connectionModelsPruned ?? 0,
                    },
                ),
            );
            // Re-read the table through the effect that already owns it.
            setDiscoverVersion((v) => v + 1);
        } catch (error) {
            setDiscoverError(error instanceof Error ? error.message : String(error));
        } finally {
            setDiscovering(false);
        }
    };

    const cellKey = (modelId: number, testId: string) => `${modelId}:${testId}`;

    const setCellRunning = (key: string, on: boolean) =>
        setRunningCells((prev) => {
            const next = new Set(prev);
            if (on) next.add(key);
            else next.delete(key);
            return next;
        });

    /**
     * Run one test for one model.
     *
     * Returns true when a result was recorded and false when the request failed,
     * because the two outcomes need different handling: a recorded `fail` is a
     * result and updates the cell, while a failed *request* leaves the cell as it
     * was. Collapsing them would show a stale result as though the model had
     * just been re-tested.
     */
    const runOne = async (model: ProviderModelRow, testId: string): Promise<boolean> => {
        if (!selectedId) return false;
        const key = cellKey(model.id, testId);
        setCellRunning(key, true);
        // Clear the previous error for this cell only; another cell's error is
        // still true and must stay visible.
        setRunErrors((prev) => {
            if (!(key in prev)) return prev;
            const next = { ...prev };
            delete next[key];
            return next;
        });

        try {
            const res = await apiFetch(
                `/api/user/ai-connections/${selectedId}/models/test`,
                {
                    method: "POST",
                    body: JSON.stringify({ model: model.modelName, test: testId }),
                },
            );
            const data = await res.json().catch(() => ({}));

            if (!res.ok) {
                // A transport failure: the model was never asked, so the cell
                // keeps whatever it had and the reason is shown beside it.
                const detail = data?.message || String(res.status);
                const msg = translateWithParams(
                    AI_TESTING.run_failed.key,
                    AI_TESTING.run_failed.fallback,
                    { detail },
                );
                setRunErrors((prev) => ({ ...prev, [key]: msg }));
                toast.error(msg);
                return false;
            }

            const state = (data.state ?? null) as TestState | null;
            setModels((prev) =>
                prev.map((m) =>
                    m.id === model.id
                        ? {
                              ...m,
                              // A capability cell is written only when the run
                              // produced a VERDICT. The backend's gate already
                              // works this way: `state: null` means no capability
                              // result was recorded, and the response still carries
                              // `durationMs` because the run did cost time.
                              //
                              // Writing the cell unconditionally was a defect: an
                              // inconclusive run (the budget-spent shape, 200 with
                              // `state: null`) left a truthy entry with no state, so
                              // `runUntested` and `countUntested` treated the model
                              // as tested and skipped the one cell that still needs
                              // running. Leaving it absent keeps the sweep honest and
                              // matches what a reload would show.
                              ...(state === "pass" || state === "fail"
                                  ? {
                                        testResults: {
                                            ...m.testResults,
                                            [testId]: {
                                                state: state as TestState,
                                                testedAt: data.result?.testedAt,
                                                reason: data.outcome,
                                            },
                                        },
                                    }
                                  : {}),
                              // The duration goes to the CONNECTION's record, not the
                              // model's — the response carries `performance` from the
                              // intersect row and `durationMs` for the run that just
                              // finished, and putting it under `testResults` would
                              // attribute this host's speed to the model.
                              connectionTestResults: {
                                  ...(m.connectionTestResults ?? {}),
                                  [testId]: {
                                      durationMs:
                                          data.performance?.durationMs ?? data.durationMs,
                                      outcome: data.outcome,
                                      at: data.performance?.at,
                                  },
                              },
                          }
                        : m,
                ),
            );
            return true;
        } catch (error) {
            const msg = translateWithParams(
                AI_TESTING.run_failed.key,
                AI_TESTING.run_failed.fallback,
                { detail: error instanceof Error ? error.message : String(error) },
            );
            setRunErrors((prev) => ({ ...prev, [key]: msg }));
            toast.error(msg);
            return false;
        } finally {
            setCellRunning(key, false);
        }
    };

    /** Every test for one model, in registration order, stoppable between steps. */
    const runModel = async (model: ProviderModelRow) => {
        setRunningModel(model.id);
        cancelRequested.current = false;
        let stopped = false;
        try {
            for (const t of tests) {
                if (cancelRequested.current) {
                    stopped = true;
                    break;
                }
                await runOne(model, t.id);
            }
        } finally {
            setRunningModel(null);
            setPendingConfirm(null);
            if (stopped) toast.info(translate(AI_TESTING.cancelled));
        }
    };

    /** Every test on every model with no recorded result, stoppable between steps. */
    const runUntested = async () => {
        setBulkRunning(true);
        cancelRequested.current = false;
        let stopped = false;
        try {
            for (const m of models) {
                for (const t of tests) {
                    if (cancelRequested.current) {
                        stopped = true;
                        break;
                    }
                    if (hasVerdict(m, t.id)) continue;
                    await runOne(m, t.id);
                }
                if (stopped) break;
            }
        } finally {
            setBulkRunning(false);
            setPendingConfirm(null);
            if (stopped) toast.info(translate(AI_TESTING.cancelled));
        }
    };

    const countUntested = () =>
        models.reduce(
            (n, m) => n + tests.filter((t) => !hasVerdict(m, t.id)).length,
            0,
        );

    /**
     * The cost gate. Anything touching `turn` is minutes per model on CPU, so a
     * run that includes one asks for a second press rather than starting twenty
     * minutes of work on one click.
     */
    const confirmThenRun = (pending: PendingConfirm) => {
        // `runs` is what the warning is about, so the caller passes it rather
        // than this function recomputing a number that may have changed.
        const includesSlow = tests.some((t) => t.duration === "minutes");
        if (includesSlow && pending.runs > 1) {
            setPendingConfirm(pending);
            return;
        }
        startPending(pending);
    };

    const startPending = (pending: PendingConfirm) => {
        if (pending.kind === "model") {
            const model = models.find((m) => m.id === pending.modelId);
            if (model) void runModel(model);
        } else {
            void runUntested();
        }
    };

    const testLabel = (id: string) => {
        // Ids are data; the labels are translations. An unknown id falls back to
        // the id itself rather than to an empty cell, so a newly registered test
        // is visible on the page before its label is translated.
        const map: Record<string, string> = {
            tools: translate(AI_TESTING.test_tools),
            competence: translate(AI_TESTING.test_competence),
            turn: translate(AI_TESTING.test_turn),
        };
        return map[id] ?? id;
    };

    const connectionLabel = (conn: AvailableConnection) => {
        const name = conn.name || conn.provider || String(conn.connectionId);
        // A leading asterisk marks a connection shared with the user's group,
        // matching how the other AI pages label one.
        return conn.isOwn ? `${name} (${conn.provider})` : `* ${name} (${conn.provider})`;
    };

    if (!isLanguageLoaded || loading) {
        return (
            <div className="flex items-center justify-center h-64">
                <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
            </div>
        );
    }

    return (
        <div className="max-w-4xl mx-auto space-y-6">
            <div>
                <h1 className="text-3xl font-bold">{translate(AI_TESTING.title)}</h1>
                <p className="text-muted-foreground mt-2 leading-relaxed">
                    {translate(AI_TESTING.explanation)}
                </p>
            </div>

            {loadError && (
                <div
                    role="alert"
                    className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
                >
                    {loadError}
                </div>
            )}

            {connections.length === 0 ? (
                <Card>
                    <CardHeader>
                        <CardTitle>{translate(AI_TESTING.no_connections_heading)}</CardTitle>
                        <CardDescription>
                            {translate(AI_TESTING.no_connections_body)}
                        </CardDescription>
                    </CardHeader>
                    <CardContent>
                        {/* `Button` is the Base UI primitive and takes no
                            `asChild`; the datasets page links the same way. */}
                        <Button onClick={() => router.push("/settings/ai")}>
                            {translate(AI_TESTING.no_connections_link)}
                        </Button>
                    </CardContent>
                </Card>
            ) : (
                <>
                    {/* The selector and discovery share a line: the button acts on
                        the connection chosen beside it, and a user reading "which
                        connection" is one glance from "make it list its models".
                        items-end aligns the button with the trigger, because the
                        Label occupies the row above the control, not beside it. */}
                    <div className="flex items-end gap-2">
                        <div className="min-w-0 flex-1 max-w-sm">
                            <Label htmlFor="ai-testing-connection">
                                {translate(AI_TESTING.connection_label)}
                            </Label>
                            <Select value={selectedId} onValueChange={setSelectedId}>
                                <SelectTrigger id="ai-testing-connection" className="mt-1">
                                    <SelectValue placeholder={translate(CHAT.select_connection_placeholder)}>
                                        {selectedId
                                            ? connectionLabel(
                                                  connections.find((c) => c.id === selectedId)!,
                                              )
                                            : ""}
                                    </SelectValue>
                                </SelectTrigger>
                                <SelectContent className="min-w-max">
                                    {connections.map((conn) => (
                                        <SelectItem key={conn.id} value={conn.id}>
                                            {connectionLabel(conn)}
                                        </SelectItem>
                                    ))}
                                </SelectContent>
                            </Select>
                        </div>
                        {/* Enabled with an empty table on purpose: that is the case it
                            exists for, and a control greyed out exactly when it is
                            needed gives the user nothing to try. */}
                        <Button
                            variant="outline"
                            size="sm"
                            className="mb-0.5"
                            disabled={discovering || !selectedId}
                            onClick={discoverModels}
                        >
                            {discovering ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                                <RefreshCw className="h-3 w-3" />
                            )}
                            <span className="ms-1">
                                {translate(
                                    discovering
                                        ? AI_TESTING.discover_running
                                        : AI_TESTING.discover_models,
                                )}
                            </span>
                        </Button>
                    </div>

                    {/* The limit the badges compare against is READ here and SET
                        elsewhere, so this offers a session-only value beside the
                        link that persists one. Without it the page said "over your
                        30 s limit" and gave the reader nowhere to go. */}
                    <div className="mt-3 flex flex-wrap items-end gap-3 rounded-md border border-border/60 bg-muted/30 px-3 py-2">
                        <div>
                            <Label htmlFor="ai-testing-session-limit" className="text-xs">
                                {translate(AI_TESTING.slow_limit_session_label)}
                            </Label>
                            <Input
                                id="ai-testing-session-limit"
                                value={sessionLimit}
                                onChange={(e) => setSessionLimit(e.target.value)}
                                placeholder={
                                    slowLimitSeconds != null ? String(slowLimitSeconds) : ""
                                }
                                inputMode="numeric"
                                className="mt-1 h-8 w-20"
                            />
                        </div>
                        <p className="pb-1 text-[11px] text-muted-foreground">
                            {translate(AI_TESTING.slow_limit_session_hint)}
                        </p>
                        {sessionLimit.trim() !== "" && (
                            <Button
                                variant="ghost"
                                size="sm"
                                className="h-8"
                                onClick={() => setSessionLimit("")}
                            >
                                {translate(AI_TESTING.slow_limit_session_reset)}
                            </Button>
                        )}
                        <Link
                            href="/settings/profile"
                            className="pb-1.5 text-xs text-muted-foreground underline hover:text-foreground"
                        >
                            {translate(AI_TESTING.slow_limit_session_link)}
                        </Link>
                    </div>

                    {/* One column per REGISTERED test, from the API rather
                        than a list in this file: the set grows, and a frontend
                        list would drift the first time a test was added. */}
                    {modelsError && (
                        <div
                            role="alert"
                            className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
                        >
                            {modelsError}
                        </div>
                    )}

                    {/* The catalogue-wide action lives above the table, where a
                        user looks before scrolling into it. */}
                    <div className="flex flex-wrap items-center gap-2">
                        <Button
                            variant="outline"
                            size="sm"
                            disabled={bulkRunning || countUntested() === 0}
                            onClick={() =>
                                confirmThenRun({ kind: "bulk", runs: countUntested() })
                            }
                        >
                            {bulkRunning ? (
                                <Loader2 className="h-3 w-3 animate-spin" />
                            ) : (
                                <Play className="h-3 w-3" />
                            )}
                            <span className="ms-1">
                                {translate(AI_TESTING.run_all_untested)}
                            </span>
                        </Button>
                        {(bulkRunning || runningModel !== null) && (
                            <Button
                                variant="destructive"
                                size="sm"
                                onClick={() => {
                                    cancelRequested.current = true;
                                }}
                            >
                                <Square className="h-3 w-3" />
                                <span className="ms-1">{translate(COMMON.cancel)}</span>
                            </Button>
                        )}
                    </div>

                    {/* What the server said, or why it could not be asked.
                        Rendered inline and left there: a toast would disappear before
                        a reader finished it, and this message is the whole evidence
                        that discovery ran. A result can be good news ("12 new"), so
                        it is not styled as an error. */}
                    {discoverNote && (
                        <div
                            role="status"
                            className="rounded-md border border-emerald-400/40 bg-emerald-50 px-4 py-3 text-sm text-emerald-900 dark:bg-emerald-900/20 dark:text-emerald-200"
                        >
                            {discoverNote}
                        </div>
                    )}
                    {discoverError && (
                        <div
                            role="alert"
                            className="rounded-md border border-destructive/40 bg-destructive/10 px-4 py-3 text-sm text-destructive"
                        >
                            {discoverError}
                        </div>
                    )}

                    {/* The second press the cost warning asks for. It states the
                        number of runs, because "some tests" is not a cost. */}
                    {pendingConfirm && (
                        <div className="rounded-md border border-amber-400/50 bg-amber-50 px-4 py-3 text-sm text-amber-900 dark:bg-amber-900/20 dark:text-amber-200">
                            <p>
                                {translateWithParams(
                                    AI_TESTING.cost_warning.key,
                                    AI_TESTING.cost_warning.fallback,
                                    { count: pendingConfirm.runs },
                                )}
                            </p>
                            <div className="mt-2 flex gap-2">
                                <Button size="sm" onClick={() => startPending(pendingConfirm)}>
                                    {translate(AI_TESTING.cost_confirm)}
                                </Button>
                                <Button
                                    size="sm"
                                    variant="ghost"
                                    onClick={() => setPendingConfirm(null)}
                                >
                                    {translate(COMMON.cancel)}
                                </Button>
                            </div>
                        </div>
                    )}

                    <Card>
                        <CardHeader>
                            <CardTitle>{translate(AI_TESTING.models_heading)}</CardTitle>
                        </CardHeader>
                        <CardContent>
                            {/* Said once, not per cell: a model can hold a capability
                                result from another connection, and repeating that in
                                every row would be a wall of the same sentence. */}
                            {tests.some((t) =>
                                models.some(
                                    (m) =>
                                        m.testResults?.[t.id] &&
                                        m.connectionTestResults?.[t.id]?.durationMs == null,
                                ),
                            ) && (
                                <p className="mb-3 text-xs text-muted-foreground">
                                    {translate(AI_TESTING.elsewhere_note)}
                                </p>
                            )}
                            {slowLimitError && (
                                <p role="alert" className="mb-3 text-xs text-destructive">
                                    {slowLimitError}
                                </p>
                            )}
                            {loadingModels ? (
                                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                                    <Loader2 className="h-4 w-4 animate-spin" />
                                    {translate(AI_TESTING.models_heading)}
                                </div>
                            ) : models.length === 0 ? (
                                <p className="text-sm text-muted-foreground">
                                    {translate(AI_TESTING.no_models)}
                                </p>
                            ) : (
                                // Scrolls rather than wraps below 640px; the
                                // table is wider than a phone and a wrapped row
                                // would put a state under the wrong heading.
                                <div className="w-full overflow-x-auto">
                                    <table className="w-full min-w-[700px] border-collapse text-sm">
                                        <thead>
                                            <tr className="border-b text-left">
                                                <th className="py-2 pr-3 font-medium">
                                                    {translate(AI_TESTING.column_model)}
                                                </th>
                                                <th className="py-2 pr-3 font-medium">
                                                    {translate(AI_TESTING.column_enabled)}
                                                </th>
                                                {tests.map((t) => (
                                                    <th key={t.id} className="py-2 pr-3 font-medium">
                                                        {testLabel(t.id)}
                                                    </th>
                                                ))}
                                                <th className="py-2 font-medium">
                                                    {translate(AI_TESTING.column_actions)}
                                                </th>
                                            </tr>
                                        </thead>
                                        <tbody>
                                            {models.map((m) => (
                                                <tr key={m.id} className="border-b last:border-0">
                                                    <td className="py-2 pr-3 font-mono text-xs">
                                                        {m.modelName}
                                                    </td>
                                                    <td className="py-2 pr-3">
                                                        {/* A tick and a cross, not a tick and a
                                                            dash: a dash reads as "not applicable",
                                                            which a disabled model is not. Green
                                                            and red because the column is a
                                                            yes/no, and colour is the fastest
                                                            thing to scan in a dense table. */}
                                                        {m.enabled ? (
                                                            <Check
                                                                className="h-4 w-4 text-green-600 dark:text-green-400"
                                                                aria-label={translate(AI_TESTING.enabled_yes)}
                                                            />
                                                        ) : (
                                                            <X
                                                                className="h-4 w-4 text-red-600 dark:text-red-400"
                                                                aria-label={translate(AI_TESTING.enabled_no)}
                                                            />
                                                        )}
                                                    </td>
                                                    {tests.map((t) => {
                                                        const result = m.testResults?.[t.id];
                                                        return (
                                                            <td key={t.id} className="py-2 pr-3 align-top">
                                                                <TestStateBadge
                                                                    state={(result?.state ?? "unknown") as TestState}
                                                                    testedAt={result?.testedAt}
                                                                    reason={result?.reason}
                                                                    durationMs={
                                                                        m.connectionTestResults?.[t.id]
                                                                            ?.durationMs ?? null
                                                                    }
                                                                    limitSeconds={effectiveLimitSeconds}
                                                                />
                                                                <Button
                                                                    variant="ghost"
                                                                    size="sm"
                                                                    className="mt-1 h-6 px-2 text-xs"
                                                                    disabled={runningCells.has(cellKey(m.id, t.id))}
                                                                    onClick={() => void runOne(m, t.id)}
                                                                >
                                                                    {runningCells.has(cellKey(m.id, t.id)) ? (
                                                                        <Loader2 className="h-3 w-3 animate-spin" />
                                                                    ) : (
                                                                        <Play className="h-3 w-3" />
                                                                    )}
                                                                    <span className="ms-1">
                                                                        {runningCells.has(cellKey(m.id, t.id))
                                                                            ? translate(AI_TESTING.running)
                                                                            : translate(AI_TESTING.run_test)}
                                                                    </span>
                                                                </Button>
                                                                {/* The error stays until this cell is re-run:
                                                                    a failed request must not look like a
                                                                    result, and a toast alone would vanish. */}
                                                                {runErrors[cellKey(m.id, t.id)] && (
                                                                    <p
                                                                        role="alert"
                                                                        className="mt-1 max-w-[16rem] text-[11px] leading-tight text-destructive"
                                                                    >
                                                                        {runErrors[cellKey(m.id, t.id)]}
                                                                    </p>
                                                                )}
                                                            </td>
                                                        );
                                                    })}
                                                    <td className="py-2 align-top">
                                                        <Button
                                                            variant="outline"
                                                            size="sm"
                                                            className="h-7 px-2 text-xs"
                                                            disabled={runningModel === m.id || bulkRunning}
                                                            onClick={() =>
                                                                confirmThenRun({
                                                                    kind: "model",
                                                                    modelId: m.id,
                                                                    runs: tests.length,
                                                                })
                                                            }
                                                        >
                                                            {runningModel === m.id ? (
                                                                <Loader2 className="h-3 w-3 animate-spin" />
                                                            ) : (
                                                                <Play className="h-3 w-3" />
                                                            )}
                                                            <span className="ms-1">
                                                                {translate(AI_TESTING.run_all_for_model)}
                                                            </span>
                                                        </Button>
                                                    </td>
                                                </tr>
                                            ))}
                                        </tbody>
                                    </table>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </>
            )}
        </div>
    );
}

export default function AITestingPage() {
    return (
        <ProtectedRoute>
            <AITestingContent />
        </ProtectedRoute>
    );
}
