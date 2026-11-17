"use client";

import { useState } from "react";
import { Copy, Check } from "lucide-react";
import { useTranslate } from "@/lib/translation-helpers";
import { COMMON } from "@/app/common/translations";

export default function CopyButton({ text }: { text: string }) {
    const translate = useTranslate();
    const [copied, setCopied] = useState(false);

    const handleCopy = async () => {
        try {
            await navigator.clipboard.writeText(text);
            setCopied(true);
            setTimeout(() => setCopied(false), 1500);
        } catch {
            // Clipboard API not available — silently fail
        }
    };

    return (
        <button
            type="button"
            onClick={handleCopy}
            className="flex-shrink-0 p-0.5 rounded hover:bg-white/10 transition-colors"
            title={translate(copied ? COMMON.copied : COMMON.copy_to_clipboard)}
        >
            {copied ? (
                <Check className="h-3 w-3 text-green-400" />
            ) : (
                <Copy className="h-3 w-3 text-yellow-400" />
            )}
        </button>
    );
}
