// lib/date-format.ts
// ============================================================
// ONE date format for every display in the workbench.
//
//   formatDate     → 06/Nov/26
//   formatDateTime → 06/Nov/26 11:25
//
// WHY A SHARED MODULE
//
// There were three formats in the tree and none of them was chosen centrally.
// Two files formatted explicitly with 'en-GB' (dd/mm/yyyy, 24 h); thirteen called
// `toLocaleString()` with no argument, which renders in *the browser's* locale —
// on an en-US machine that is `11/6/2026, 11:25:17 AM`, which is what a user saw
// on 2026-11-06 and reported. A third rendered `06-November-2026`.
//
// The fix is not a better format string in thirteen places. It is one function,
// imported, so the format exists once and cannot drift file by file again.
//
// WHY THE MONTH IS A NAME
//
// `06/11/26` is the ambiguity that started this: it is 6 November to most of the
// world and 11 June in the United States. A three-letter month makes the date
// unreadable the wrong way round — there is no locale in which `Nov` means a day
// number.
//
// WHY THE ABBREVIATIONS ARE FIXED ENGLISH
//
// `Intl` with a locale would translate them, and the format would then be
// locale-dependent again — the defect being fixed. The three-letter English month
// is the technical convention (ISO 8601 permits it; it is universal in aviation,
// logistics and log files) precisely because a reader of any language recognises
// it. These are the abbreviations a translation system cannot improve on and a
// browser cannot render differently, which is the whole point.
//
// WHY 24-HOUR TIME
//
// The two formats that had been chosen already used it (both 'en-GB' sites passed
// `hour12: false`), and `11:25 PM` vs `23:25` is the same ambiguity in a smaller
// place. It also sorts correctly as text.
// ============================================================

/**
 * Three-letter English month abbreviations, indexed by `Date.getMonth()`.
 *
 * A literal array rather than `Intl.DateTimeFormat`: the values must be identical
 * in every browser, every locale and every Node version, and `Intl` gives "Nov."
 * with a full stop in some locales and "Nov" in others.
 */
const MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"];

/** What every formatter here accepts: an ISO string from the API, or a Date. */
export type DateInput = string | number | Date | null | undefined;

/**
 * Parse, or `null` when the value is absent or unparseable.
 *
 * `new Date("not a date")` does not throw — it produces an Invalid Date whose
 * getters return NaN, so a `try/catch` around it catches nothing. `isNaN(getTime())`
 * is the only reliable test.
 */
function parse(value: DateInput): Date | null {
    if (value === null || value === undefined || value === "") return null;
    const date = value instanceof Date ? value : new Date(value);
    return Number.isNaN(date.getTime()) ? null : date;
}

const pad = (n: number): string => String(n).padStart(2, "0");

/** `06/Nov/26` — the date, with no time. Empty string for an absent value. */
export function formatDate(value: DateInput): string {
    const date = parse(value);
    if (!date) return typeof value === "string" ? value : "";
    return `${pad(date.getDate())}/${MONTHS[date.getMonth()]}/${pad(date.getFullYear() % 100)}`;
}

/** `06/Nov/26 11:25` — date and time in 24-hour form. Empty string for an absent value. */
export function formatDateTime(value: DateInput): string {
    const date = parse(value);
    if (!date) return typeof value === "string" ? value : "";
    return `${formatDate(date)} ${pad(date.getHours())}:${pad(date.getMinutes())}`;
}

/**
 * `11:25:17` — time alone, 24-hour, for a log line that has its own date context.
 *
 * Here because the log viewer used `toLocaleTimeString` with no `hour12`, which
 * renders `11:25:17 AM` on an en-US browser and `11:25:17` elsewhere. A time with
 * no date is not a date display, but it is the same defect.
 */
export function formatTime(value: DateInput, withSeconds = false): string {
    const date = parse(value);
    if (!date) return typeof value === "string" ? value : "";
    const base = `${pad(date.getHours())}:${pad(date.getMinutes())}`;
    return withSeconds ? `${base}:${pad(date.getSeconds())}` : base;
}
