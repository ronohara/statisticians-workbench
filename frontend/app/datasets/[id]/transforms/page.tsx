"use client";

import { useTranslation } from "@/lib/translation-context";
import { useTranslate } from "@/lib/translation-helpers";
import { FlaskConical } from "lucide-react";
import { TRANSFORMS_EDITOR } from "./translations";

export default function TransformsPage() {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();
    if (!isLanguageLoaded) return null;

    return (
        <div className="flex items-center justify-center h-full">
            <div className="text-center max-w-xs">
                <FlaskConical className="h-10 w-10 mx-auto text-muted-foreground mb-3 opacity-30" />
                <p className="text-sm text-muted-foreground">
                    {translate(TRANSFORMS_EDITOR.empty_title)}
                </p>
                <p className="text-xs text-muted-foreground mt-1">
                    {translate(TRANSFORMS_EDITOR.empty_hint)}
                </p>
            </div>
        </div>
    );
}
