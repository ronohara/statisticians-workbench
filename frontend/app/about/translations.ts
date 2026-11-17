// app/about/translations.ts
// ============================================================
// ABOUT MODULE TRANSLATIONS
// All translation keys used by the about page.
// ============================================================

import type { TranslationKey } from "@/lib/translation-helpers";

export const ABOUT = {
    title: { key: "about.title", fallback: "About Statisticians Workbench" },
    description: { key: "about.description", fallback: "Build amazing experiences with shadcn/ui and Next.js. Clean design, fast performance." },
    get_started: { key: "about.get_started", fallback: "Get Started" },
    fast_title: { key: "about.fast_title", fallback: "Fast" },
    fast_desc: { key: "about.fast_desc", fallback: "Built on Next.js App Router for optimal performance." },
    modern_title: { key: "about.modern_title", fallback: "Modern UI" },
    modern_desc: { key: "about.modern_desc", fallback: "Accessible components from shadcn/ui, styled with Tailwind CSS." },
    secure_title: { key: "about.secure_title", fallback: "Secure" },
    secure_desc: { key: "about.secure_desc", fallback: "Type‑safe and customizable – you own the component code." },
} as const;