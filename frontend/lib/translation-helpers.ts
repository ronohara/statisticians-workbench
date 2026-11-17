// lib/translation-helpers.ts
// ============================================================
// TRANSLATION HELPERS
// Utility functions for working with TranslationKey objects.
// No translation keys are defined here - they live in module
// translation files.
// ============================================================

import { useCallback } from "react";
import { useTranslation } from "@/lib/translation-context";

/**
 * A translation key with an English fallback.
 * Used throughout the frontend to define translation keys.
 */
export interface TranslationKey {
    key: string;
    fallback: string;
}

/**
 * Translate a TranslationKey object.
 * Usage: const { t } = useTranslation(); const msg = translateKey(t, DATASETS.list_error);
 */
export function translateKey(
    t: (key: string, fallback?: string) => string,
    translation: TranslationKey
): string {
    return t(translation.key, translation.fallback);
}

/**
 * Hook that returns a function to translate TranslationKey objects.
 * This is a hook that must be used within a React component.
 * Usage: const translate = useTranslate(); const msg = translate(DATASETS.list_error);
 */
export function useTranslate() {
    const { t } = useTranslation();
    return useCallback((translation: TranslationKey): string => {
        return t(translation.key, translation.fallback);
    }, [t]);
}

/** True when a value is a `{key, fallback}` translation reference. */
function isTranslationRef(v: unknown): v is TranslationKey {
    return (
        typeof v === "object" &&
        v !== null &&
        "key" in v &&
        "fallback" in v &&
        typeof (v as TranslationKey).key === "string" &&
        typeof (v as TranslationKey).fallback === "string"
    );
}

/** Render a single param value: nested {key,fallback}, column list, or scalar. */
function renderParam(v: unknown, t: (key: string, fallback?: string) => string): string {
    if (isTranslationRef(v)) {
        return t(v.key, v.fallback);
    }
    if (Array.isArray(v)) {
        return v.map((item) => renderColumn(item, t)).join(", ");
    }
    return v == null ? "" : String(v);
}

/** Render a column-list item as `name (type)` using the translated type label. */
function renderColumn(item: unknown, t: (key: string, fallback?: string) => string): string {
    if (item && typeof item === "object" && "name" in item) {
        const c = item as { name: string; isNumeric?: boolean; isCategorical?: boolean };
        const type = c.isNumeric
            ? t("recipes.column_type.numeric", "numeric")
            : c.isCategorical
                ? t("recipes.column_type.categorical", "categorical")
                : "?";
        return `${c.name} (${type})`;
    }
    return String(item);
}

/** Substitute `{var}` placeholders in `text` from `params` (resolving nested
 * `{key, fallback}` refs and column lists along the way). */
export function interpolate(
    text: string,
    params: Record<string, unknown>,
    t: (key: string, fallback?: string) => string,
): string {
    let out = text;
    for (const [k, v] of Object.entries(params)) {
        out = out.split(`{${k}}`).join(renderParam(v, t));
    }
    return out;
}

/** Resolve a key (DB → en → fallback), then substitute `{var}` from `params`.
 * This is the frontend twin of the backend `t()` + `format_recipe_issues`.
 */
export function translate(
    t: (key: string, fallback?: string) => string,
    key: string,
    fallback: string,
    params?: Record<string, unknown>,
): string {
    const resolved = t(key, fallback);
    return params ? interpolate(resolved, params, t) : resolved;
}

/** Hook returning `translate(key, fallback, params?)` for param-substituted
 * strings (issue messages, requirement descriptions, etc.). */
export function useTranslateWithParams() {
    const { t } = useTranslation();
    return useCallback(
        (key: string, fallback: string, params?: Record<string, unknown>): string => {
            return translate(t, key, fallback, params);
        },
        [t],
    );
}

/**
 * Hook returning `(translation, params?)` — the declaration plus its `{var}`
 * values, with no re-typing of `key` or `fallback` at the call site.
 *
 * `useTranslateWithParams` above takes the two fields separately, which is the
 * shape the AGENTS.md translation rule forbids: a call site that writes
 * `translate(key, "English text", …)` repeats the declaration's own fields and
 * drifts from it. This is the same substitution over a `TranslationKey`.
 *
 * Usage: const tx = useTranslateKeyWithParams(); tx(VIRTUAL.progress_decided, { decided: 3, total: 6 })
 */
export function useTranslateKeyWithParams() {
    const { t } = useTranslation();
    return useCallback(
        (translation: TranslationKey, params?: Record<string, unknown>): string => {
            return translate(t, translation.key, translation.fallback, params);
        },
        [t],
    );
}

/**
 * Whether an error body is a markup document rather than a message.
 *
 * A proxy that does not know a route answers with its own 404 page, and the body is a
 * complete HTML document — doctype, script tags, a serialised React payload. Returning
 * that as an "error message" renders a wall of markup in the UI, which is what happened
 * on 2026-11-02 when the tuning page's endpoint was missing from next.config.mjs.
 *
 * The test is deliberately narrow: it looks for markup, not for "not JSON". A backend
 * that refuses in plain text ("the endpoint is not reachable") is worth showing, and a
 * rule that rejected anything unparseable would hide it. Only a document is suppressed.
 */
function isMarkupDocument(text: string): boolean {
    const head = text.trimStart().slice(0, 40).toLowerCase();
    return head.startsWith("<!doctype") || head.startsWith("<html") || head.startsWith("<?xml");
}

/**
 * Extract and translate an error from an API response.
 * Usage: const errorMsg = await getErrorMessage(translate, res, DATASETS.list_error);
 */
export async function getErrorMessage(
    translate: (translation: TranslationKey, params?: Record<string, unknown>) => string,
    res: Response,
    defaultKey: TranslationKey,
    params?: Record<string, unknown>,
): Promise<string> {
    try {
        const text = await res.text();
        if (!text) {
            return translate(defaultKey, params);
        }
        
        try {
            const data = JSON.parse(text);
            
            // If we have both error and message, the message wins.
            //
            // `message` is the SERVER's rendering: the backend called t() with the
            // values already substituted, in the user's language. Re-resolving
            // `error` as a key here discarded that and returned the raw table row,
            // whose text still carried its placeholders — and the frontend's t()
            // does no substitution, so `{error}` reached the screen literally.
            //
            // Both fields come from one table, so the lookup could only lose: it
            // re-read the same row without the values that had just been filled in.
            if (data.error && data.message) {
                return typeof data.message === 'string'
                    ? data.message
                    : JSON.stringify(data.message);
            }
            
            // If we have a detail field (FastAPI style)
            if (data.detail) {
                if (typeof data.detail === 'string') {
                    return data.detail;
                }
                return JSON.stringify(data.detail);
            }
            
            // If we have a message field
            if (data.message) {
                if (typeof data.message === 'string') {
                    return data.message;
                }
                return JSON.stringify(data.message);
            }
            
            // If we have an error field — and the decision here is by LOOKUP, not by shape.
            //
            // Same defect as the sibling below, in this same file: `error.includes('.')`
            // treats any dotted string as a translation key, so a driver message
            // carrying an address or a hostname was looked up as a key, missed, and
            // replaced with this caller's default — the page showed its generic text
            // and the real cause disappeared.
            //
            // A bare `error` with no sibling `message` is a VALUE from whatever produced
            // it. It is a key only when the loaded table actually holds it, which the
            // table can answer and punctuation cannot. An empty fallback makes a miss
            // return '', so the raw text survives.
            if (data.error) {
                if (typeof data.error === 'string') {
                    const translated = translate({ key: data.error, fallback: '' });
                    return translated || data.error;
                }
                return JSON.stringify(data.error);
            }
            
            // Not JSON. A markup document is the proxy's 404 page, not a message —
            // fall back to the caller's key. Plain text is kept; it is a refusal.
            return text && !isMarkupDocument(text) ? text : translate(defaultKey, params);
        } catch {
            return text && !isMarkupDocument(text) ? text : translate(defaultKey, params);
        }
    } catch {
        return translate(defaultKey, params);
    }
}

/**
 * Extract and translate an error from a JSON error object.
 * Usage: const errorMsg = getErrorMessageFromData(translate, errorData, DATASETS.list_error);
 */
export function getErrorMessageFromData(
    translate: (translation: TranslationKey, params?: Record<string, unknown>) => string,
    errorData: any,
    defaultKey: TranslationKey,
    params?: Record<string, unknown>,
): string {
    if (!errorData) {
        return translate(defaultKey, params);
    }
    
    // If we have both error and message, the message wins — same reason as in
    // getErrorMessage above: it is the server's rendering, with the values
    // already substituted. Re-looking-up the key discards them.
    if (errorData.error && errorData.message) {
        return typeof errorData.message === 'string'
            ? errorData.message
            : JSON.stringify(errorData.message);
    }
    
    // If we have a detail field (FastAPI style)
    if (errorData.detail) {
        if (typeof errorData.detail === 'string') {
            return errorData.detail;
        }
        return JSON.stringify(errorData.detail);
    }
    
    // If we have a message field
    if (errorData.message) {
        if (typeof errorData.message === 'string') {
            return errorData.message;
        }
        return JSON.stringify(errorData.message);
    }
    
    // If we have an error field — and the decision here is by LOOKUP, not by shape.
    //
    // This branch used to test `error.includes('.')` and treat a dotted string as a
    // translation key. That heuristic cannot tell a coded key from a driver message:
    // `connect ECONNREFUSED 10.160.184.24:5432` contains dots because an IP address
    // does, so pg's own sentence was looked up as a key, missed, and replaced with this
    // helper's default — the user saw "Connection failed" and nothing else.
    //
    // A bare `error` with no sibling `message` is a VALUE from whatever produced it: a
    // driver, a runtime, a proxy. The coded envelope always carries both fields
    // (error = key, message = rendered text), so a lone `error` is a key only when the
    // loaded table actually holds it — which is a question the table can answer and
    // punctuation cannot. An empty fallback makes a miss return '', so the raw text
    // survives.
    if (errorData.error) {
        if (typeof errorData.error === 'string') {
            const translated = translate({ key: errorData.error, fallback: '' });
            return translated || errorData.error;
        }
        return JSON.stringify(errorData.error);
    }
    
    return translate(defaultKey, params);
}