// frontend/components/test-state-badge.tsx
"use client";

import { useTranslate, useTranslateWithParams } from "@/lib/translation-helpers";

import { AI_TESTING } from "@/app/aitesting/translations";
import { COMMON } from "@/app/common/translations";
import { formatDate } from "@/lib/date-format";

/** The three states a test can hold for a model (plan Item 9, D8). */
export type TestState = "unknown" | "pass" | "fail";

interface TestStateBadgeProps {
    state: TestState;
    /** When the result was observed, ISO string. Absent for `unknown`. */
    testedAt?: string | null;
    /**
     * How long this connection took, in milliseconds — the performance record, which
     * is a different fact from the capability state beside it.
     *
     * A model can hold `pass` from one connection and carry no duration here, because
     * capability is recorded on the model and performance on the connection that
     * produced it. When that happens the badge still shows the state and the timing
     * says the run did not happen here; showing “untested” instead would contradict
     * the badge.
     */
    durationMs?: number | null;
    /** The user's effective slow-model limit, in seconds. Absent when unknown. */
    limitSeconds?: number | null;
    /**
     * Why the test reached this state — the record's own `reason`, stored beside
     * the state since Item 9 and never shown until now.
     *
     * `fail` on its own is a verdict a reader cannot act on: it does not say
     * whether the model fabricated an answer, ignored the tool it was given, or
     * described the problem instead of solving it. Three different problems with
     * three different next steps, all rendering as the same two letters.
     *
     * Shown only for `fail`. A pass has a reason too ("ok"), and printing it under
     * every green pill would train the eye to skip the line that matters.
     */
    reason?: string | null;
}

/**
 * One test's state, with the date it was observed.
 *
 * Takes the state as a prop rather than fetching: the page already holds the
 * model rows, and a badge that fetched would be a second read of the same fact
 * and could disagree with the table around it.
 *
 * `unknown` and `fail` must not look alike. One is an absence of evidence and
 * the other is evidence, and a shared grey pill would erase the distinction the
 * whole feature exists to record.
 */
export function TestStateBadge({ state, testedAt, durationMs, limitSeconds, reason }: TestStateBadgeProps) {
    const translate = useTranslate();
    const translateWithParams = useTranslateWithParams();

    const label =
        state === "pass"
            ? translate(AI_TESTING.state_pass)
            : state === "fail"
              ? translate(AI_TESTING.state_fail)
              : translate(COMMON.unknown);

    const tone =
        state === "pass"
            ? "bg-green-100 text-green-800 border-green-300 dark:bg-green-900/30 dark:text-green-300 dark:border-green-800"
            : state === "fail"
              ? "bg-red-100 text-red-800 border-red-300 dark:bg-red-900/30 dark:text-red-300 dark:border-red-800"
              : "bg-muted text-muted-foreground border-border";

    return (
        <div className="flex flex-col gap-0.5">
            <span
                className={`inline-flex w-fit items-center rounded-full border px-2 py-0.5 text-xs font-medium ${tone}`}
            >
                {label}
            </span>
            {testedAt && (
                // The date is shown, not an age: "tested 3 days ago" needs a
                // clock the server and the browser may disagree about, and the
                // record is what matters.
                <span className="text-[11px] text-muted-foreground">
                    {formatDate(testedAt)}
                </span>
            )}
            {/* The reason sits directly under the state, before the timing: what
                happened is more useful than how long it took. */}
            {state === "fail" && reason && (
                <span className="text-[11px] text-red-700 dark:text-red-400">
                    {translateWithParams(
                        AI_TESTING.failure_reason.key,
                        AI_TESTING.failure_reason.fallback,
                        { reason },
                    )}
                </span>
            )}
            {durationMs != null ? (
                <span
                    className={
                        isOverLimit(durationMs, limitSeconds)
                            ? "text-[11px] font-medium text-amber-700 dark:text-amber-400"
                            : "text-[11px] text-muted-foreground"
                    }
                >
                    {formatDuration(durationMs, translateWithParams)}
                    {isOverLimit(durationMs, limitSeconds) && (
                        <>
                            {" \u2014 "}
                            {translateWithParams(
                                AI_TESTING.too_slow.key,
                                AI_TESTING.too_slow.fallback,
                                { seconds: limitSeconds },
                            )}
                        </>
                    )}
                </span>
            ) : (
                // A state with no duration on this connection is not an absence of
                // evidence about the model — it is an absence of a measurement here.
                state !== "unknown" && (
                    <span className="text-[11px] text-muted-foreground">
                        {translate(AI_TESTING.no_duration_here)}
                    </span>
                )
            )}
        </div>
    );
}

/**
 * Whether this measurement is over the user's limit.
 *
 * Exported and pure so the comparison can be exercised without a browser: the branch
 * that shows "over your N s limit" is the one acceptance clause no live data currently
 * reaches, because every recorded duration here is under the limit in force.
 *
 * Strictly greater, not greater-or-equal: a run that took exactly the limit did not
 * exceed it, and calling that "too slow" would make the boundary itself a failure.
 */
export function isOverLimit(durationMs: number | null | undefined, limitSeconds: number | null | undefined): boolean {
    if (durationMs == null || limitSeconds == null) return false;
    return durationMs / 1000 > limitSeconds;
}

/**
 * Milliseconds as the reader would say them: whole seconds past 10 s, one decimal
 * from 1 s, and milliseconds below that.
 *
 * The boundary is where the number stops being worth a fraction: 1.1 s and 4.6 s are
 * useful, 189.4 s is not, and the fixtures that drove this design are 4.6 s and 189 s.
 */
function formatDuration(
    ms: number,
    translateWithParams: (key: string, fallback: string, params?: Record<string, unknown>) => string,
): string {
    if (ms < 1000) {
        return translateWithParams(AI_TESTING.duration_ms.key, AI_TESTING.duration_ms.fallback, {
            ms: Math.round(ms),
        });
    }
    const seconds = ms / 1000;
    return translateWithParams(
        AI_TESTING.duration_seconds.key,
        AI_TESTING.duration_seconds.fallback,
        { seconds: seconds >= 10 ? Math.round(seconds) : seconds.toFixed(1) },
    );
}
