"use client";

import { useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useTranslate, type TranslationKey } from "@/lib/translation-helpers";
import { COMPONENTS } from "@/components/translations";
import { COMMON } from "@/app/common/translations";
import { X } from "lucide-react";

export default function ReturnBanner({
    fallbackHref,
    fallbackText,
    contextName,
    contextLink,
}: {
    /** Where the box points when the page carries no returnTo — the page's own way
     *  back. Without it, no returnTo means no banner at all. */
    fallbackHref?: string;
    /** The label for that fallback target. */
    fallbackText?: TranslationKey;
    /** What the return goes back to, when the caller knows it (a recipe's name). */
    contextName?: string | null;
    /** The link label for that case — a declaration carrying {name}. */
    contextLink?: TranslationKey;
} = {}) {
    const searchParams = useSearchParams();
    const translate = useTranslate();
    const returnTo = searchParams?.get("returnTo") || "";
    const [dismissed, setDismissed] = useState(false);

    useEffect(() => {
        if (typeof window !== "undefined" && returnTo) {
            const key = `return-banner-dismissed-${returnTo}`;
            if (sessionStorage.getItem(key) === "1") {
                setDismissed(true);
            }
        }
    }, [returnTo]);

    // Three shapes reach this banner. The AI recipe editor sends a slug
    // ("ai-recipe-<session id>", to the datasets pages), which is not a URL and has
    // to be turned into its route; both recipe editors send a plain path to the
    // transforms editor, which is navigable as it stands; and a page with no
    // returnTo can offer its own way back through fallbackHref — the transforms
    // editor's route in from My Data.
    const fromAiRecipe = returnTo.startsWith("ai-recipe-");
    const usingFallback = !returnTo && !!fallbackHref;
    const targetUrl = fromAiRecipe
        ? `/ai/recipe?session=${returnTo.replace("ai-recipe-", "")}`
        : returnTo || fallbackHref || "";

    if (!targetUrl || dismissed) return null;

    const text = fromAiRecipe
        ? COMPONENTS.return_banner.text
        : usingFallback
            ? fallbackText ?? COMPONENTS.return_banner.recipe_text
            : COMPONENTS.return_banner.recipe_text;
    const link = fromAiRecipe
        ? COMPONENTS.return_banner.link
        : usingFallback
            ? COMPONENTS.return_banner.fallback_link
            : COMPONENTS.return_banner.recipe_link;
    // "Back to Recipe: {name}" when the caller knows the name, so the box says
    // which recipe it returns to rather than only that there was one.
    const linkLabel = contextName && contextLink
        ? translate(contextLink).replace("{name}", contextName)
        : translate(link);

    function handleDismiss(e: React.MouseEvent) {
        e.preventDefault();
        e.stopPropagation();
        if (typeof window !== "undefined") {
            sessionStorage.setItem(`return-banner-dismissed-${returnTo}`, "1");
        }
        setDismissed(true);
    }

    return (
        <a
            href={targetUrl}
            style={{
                display: "flex",
                alignItems: "center",
                background: "#dbeafe",
                border: "2px solid #3b82f6",
                borderRadius: "6px",
                padding: "0.65rem 1rem",
                gap: "0.5rem",
                fontSize: "0.9rem",
                fontWeight: 500,
                color: "#1e40af",
                textDecoration: "none",
                margin: "0 1rem 1rem 1rem",
                cursor: "pointer",
            }}
        >
            <span style={{ marginRight: "0.25rem" }}>↩</span>
            <span style={{ flex: 1 }}>
                {translate(text)}{" "}
                <span style={{ fontWeight: 700, textDecoration: "underline" }}>
                    {linkLabel}
                </span>
            </span>
            {/* Never offered on the fallback target: dismissing a way back would
                leave that entry point with no route out but the browser. */}
            {!usingFallback && (
                <span
                    onClick={handleDismiss}
                    title={translate(COMMON.dismiss)}
                    style={{
                        cursor: "pointer",
                        padding: "4px",
                        borderRadius: "3px",
                        display: "flex",
                        alignItems: "center",
                    }}
                >
                    <X style={{ width: 16, height: 16 }} />
                </span>
            )}
        </a>
    );
}