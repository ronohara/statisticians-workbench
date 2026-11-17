/**
 * The render gate's policy — the allow-list, and the rule that decides whether a
 * data value is markup or text.
 *
 * Both live here, and only here, so the policy is one readable list rather than a
 * configuration at each of the five result tables that draw a data value.
 *
 * Deliberately pure and dependency-free: no React, no DOM, and no import of the
 * sanitiser itself — so the rule can be exercised by hand in a bare node run
 * rather than by mounting a component. The sanitiser is called by the gate
 * component, which hands its output to `detectRenderKind`; the decision and the
 * render must consume the same sanitised string, never the raw one.
 *
 * Decided 2026-09-25, and the record of that decision is
 * `workbench-documents/workbench-rendering-html-data-tables.html` — read it
 * before changing anything below, because the list is the security boundary and
 * every entry added is more of a source database's markup running on screen.
 */

/** Presentation markup only. Adding to this list is a decision, not a detail. */
export const ALLOWED_TAGS: string[] = [
    // blocks
    "p",
    "div",
    "br",
    "hr",
    "ul",
    "ol",
    "li",
    "blockquote",
    "pre",
    "code",
    "h1",
    "h2",
    "h3",
    "h4",
    "h5",
    "h6",
    "table",
    "thead",
    "tbody",
    "tr",
    "td",
    "th",
    // inline
    "span",
    "b",
    "strong",
    "i",
    "em",
    "u",
    "s",
    "sub",
    "sup",
    "small",
    "a",
];

/**
 * Attributes, and the one tag each is allowed on. Everything not named here is
 * dropped — and in particular every `on*` handler, `style`, `class` and `id`, so
 * a source's markup can neither script the page nor restyle the application
 * around it.
 *
 * `target` and `rel` are here for a mechanical reason, not to honour anything a
 * source sends: the sanitiser filters attributes *after* it applies
 * `transformTags` below, so an attribute the gate adds must also be permitted or
 * it is dropped on the way out. The transform overwrites both on every link
 * unconditionally, so a source's own `target` or `rel` is never what renders —
 * measured 2026-09-25: a source `target="_self" rel="opener"` comes out
 * `target="_blank" rel="noreferrer"`. Drop the transform and these two entries
 * must go with it, or source markup starts choosing them.
 */
export const ALLOWED_ATTRIBUTES: Record<string, string[]> = {
    a: ["href", "title", "target", "rel"],
    td: ["colspan", "rowspan"],
    th: ["colspan", "rowspan"],
};

/** `javascript:`, `data:`, `vbscript:` and `file:` are all rejected. */
export const ALLOWED_URL_SCHEMES: string[] = ["http", "https", "mailto"];

/**
 * What the gate component passes to the sanitiser.
 *
 * This list drops content — that is its purpose, and it is stated here rather
 * than discovered. `img` is deliberately absent: an image in a data cell fetches
 * from a third party on render, making it the one entry that reaches out to the
 * network. Anything structural or scriptable (`iframe`, `object`, `embed`,
 * `form`, `input`, `button`, `svg`, `math`) is absent for the same reason.
 */
export const HTML_POLICY = {
    allowedTags: ALLOWED_TAGS,
    allowedAttributes: ALLOWED_ATTRIBUTES,
    allowedSchemes: ALLOWED_URL_SCHEMES,
    // Links open the way the application's own links do — the same override
    // components/markdown-content.tsx already carries. Both values are set
    // unconditionally, so nothing a source sends reaches the rendered link.
    transformTags: {
        a: (tagName: string, attribs: Record<string, string>) => ({
            tagName: "a",
            attribs: { ...attribs, target: "_blank", rel: "noreferrer" },
        }),
    },
};

/** The two things a data value can be. */
export type RenderKind = "text" | "markup";

const VOID_ELEMENTS = new Set(["br", "hr"]);
const ONLY_WHITESPACE = /^\s*$/;
/** One tag. Attribute values are escaped by the sanitiser, so no `>` can hide in one. */
const TAG_PATTERN = /<[^>]*>/g;
/** A tag, and nothing else: `<p>`, `</p>`, `<br />`, `<td colspan="2">`. */
const TAG = /^<\s*(\/?)\s*([a-zA-Z][a-zA-Z0-9-]*)((?:"[^"]*"|'[^']*'|[^"'>])*?)\s*(\/?)>$/;

/**
 * The stricter rule: is the whole value a well-formed element sequence — nothing
 * before the first tag, nothing after the last, every tag balanced?
 *
 * A tag among prose fails this. `Hello <b>world</b>` is text, and its tags are
 * shown as typed, which is the accepted cost of a rule that upgrades whole values
 * only. Text *inside* an element is fine; text outside every element is not.
 */
function isWholeElementSequence(value: string): boolean {
    const text = value.trim();
    if (!text) return false;

    const stack: string[] = [];
    const pattern = new RegExp(TAG_PATTERN.source, "g");
    let cursor = 0;
    let sawTag = false;
    let match: RegExpExecArray | null;

    while ((match = pattern.exec(text)) !== null) {
        // Anything outside an element has to be whitespace between elements.
        if (stack.length === 0 && !ONLY_WHITESPACE.test(text.slice(cursor, match.index))) {
            return false;
        }
        const parsed = TAG.exec(match[0]);
        if (!parsed) return false;
        const name = parsed[2].toLowerCase();
        if (parsed[1]) {
            if (stack[stack.length - 1] !== name) return false;
            stack.pop();
        } else if (!parsed[4] && !VOID_ELEMENTS.has(name)) {
            stack.push(name);
        }
        sawTag = true;
        cursor = match.index + match[0].length;
    }

    if (stack.length === 0 && !ONLY_WHITESPACE.test(text.slice(cursor))) return false;
    return sawTag && stack.length === 0;
}

/**
 * Decide how a value is rendered. `rawValue` is what the column holds;
 * `sanitisedValue` is that same value after the sanitiser, which the caller must
 * pass rather than re-deriving — the render consumes the string this decided on.
 *
 * The caller's contract:
 *
 * - call the sanitiser with `HTML_POLICY` inside a try/catch, and render the raw
 *   value as text if it throws — fail closed, never inject on error;
 * - render the **raw** value as text when this returns `"text"` (React escapes
 *   it, so `a < b` stays exactly as typed);
 * - render the **sanitised** value when this returns `"markup"`, and never the
 *   raw one.
 */
export function detectRenderKind(rawValue: string, sanitisedValue: string): RenderKind {
    try {
        // The overwhelming majority of values stop at this one character test.
        if (typeof rawValue !== "string" || !rawValue.includes("<")) return "text";
        if (typeof sanitisedValue !== "string") return "text";
        return isWholeElementSequence(sanitisedValue) ? "markup" : "text";
    } catch {
        return "text";
    }
}
