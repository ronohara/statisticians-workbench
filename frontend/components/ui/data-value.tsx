"use client";

import sanitizeHtml from "sanitize-html";

import { useTranslate } from "@/lib/translation-helpers";

import { ALLOWED_URL_SCHEMES, HTML_POLICY, detectRenderKind } from "./html-policy";
import { DATA_VALUE } from "./translations";

/**
 * The gate — the one place a database value is allowed to become markup.
 *
 * Everything a result table draws as a cell passes through here. It renders the
 * value as the sanitised markup, or exactly as the plain text it renders today,
 * and nothing else in the product may inject HTML: this file holds the product's
 * only HTML sink, and it is fed only by the sanitiser's output — never by the raw
 * value, which is not in scope on that branch.
 *
 * Three things this component is deliberate about:
 *
 * - **Sanitising happens on every render.** Not once at load, not memoised across
 *   values: the value may change in place, and a cached decision would be handed
 *   to the sink alongside a string it was not made about.
 * - **It fails closed.** If the sanitiser throws, the value renders as text. A
 *   sanitiser that cannot answer must never be assumed to have allowed something.
 * - **No props beyond the value, no configuration, no context.** The policy lives
 *   in `./html-policy` and is applied here; a caller chooses which value to pass
 *   and nothing else. Its null and empty-cell behaviour stays at the call site,
 *   because that differs per surface.
 *
 * This is a client module, because the marker's text is user-visible and is
 * resolved through `useTranslate()`. That does not change the prerender — client
 * components are prerendered on the server too, which is precisely why the
 * sanitiser has to be DOM-free — it only means the gate needs a client boundary,
 * and every one of the five surfaces already provides one.
 *
 * Decided 2026-09-25 — see
 * `workbench-documents/workbench-rendering-html-data-tables.html`.
 */

/**
 * Asked only to answer "did the policy drop anything?" — its output is compared and
 * never rendered. Everything the policy refuses is permitted here, so whatever
 * differs between the two outputs is exactly what the gate removed. Two details are
 * load-bearing: `allowedSchemes: false` does **not** permit every scheme — the
 * dangerous ones have to be named — and `allowVulnerableTags` is what lets a
 * `<script>` survive the comparison at all, so that its removal is seen rather than
 * silently matching.
 */
const NOTHING_DROPPED: Parameters<typeof sanitizeHtml>[1] = {
    ...HTML_POLICY,
    allowedTags: false,
    allowedAttributes: false,
    allowedSchemes: [...ALLOWED_URL_SCHEMES, "javascript", "data", "vbscript", "file"],
    allowVulnerableTags: true,
    nonTextTags: [] as string[],
};

/** Did the policy drop anything from the string that is about to be rendered? */
function wasAnythingRemoved(value: string, sanitised: string): boolean {
    try {
        return sanitised !== sanitizeHtml(value, NOTHING_DROPPED);
    } catch {
        // Cannot tell — make no claim rather than a false one.
        return false;
    }
}

function DataValue({ value }: { value: string }) {
    const translate = useTranslate();

    let sanitised: string | null = null;

    try {
        sanitised = sanitizeHtml(value, HTML_POLICY);
    } catch {
        sanitised = null;
    }

    if (sanitised === null || detectRenderKind(value, sanitised) !== "markup") {
        // React escapes this, so `a < b` renders exactly as it is typed — and the whole
        // value is on screen, so nothing was withheld and no marker belongs here.
        return <>{value}</>;
    }

    const removed = wasAnythingRemoved(value, sanitised);

    return (
        <>
            <span dangerouslySetInnerHTML={{ __html: sanitised }} />
            {removed && (
                <span className="ms-1 inline-block text-[10px] bg-muted text-muted-foreground px-1.5 py-0.5 rounded font-medium">
                    {translate(DATA_VALUE.some_content_not_shown)}
                </span>
            )}
        </>
    );
}

export { DataValue };
