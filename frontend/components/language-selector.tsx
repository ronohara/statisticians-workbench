"use client";

import { useState, useEffect } from "react";
import { Globe } from "lucide-react";
import { useTranslation } from "@/lib/translation-context";
import { COMPONENTS } from "@/components/translations";
import { useTranslate } from "@/lib/translation-helpers";
import { COMMON } from "@/app/common/translations";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";

interface Language {
  code: string;
  name: string;
}

export function LanguageSelector() {
  const { language, setLanguage } = useTranslation();
  const translate = useTranslate();
  const [languages, setLanguages] = useState<Language[]>([]);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    fetch(`/api/languages?viewer=${language}`)
      .then(res => res.json())
      .then(data => setLanguages(data))
      .catch(console.error);
  }, []);

  if (languages.length === 0) return null;

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger
        className="inline-flex items-center justify-center rounded-md text-sm font-medium ring-offset-background transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:pointer-events-none disabled:opacity-50 hover:bg-accent hover:text-accent-foreground h-10 w-10"
      >
        <Globe className="h-5 w-5" />
        <span className="sr-only">{translate(COMMON.select_language)}</span>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="min-w-48">
        {languages.map((lang) => (
          <DropdownMenuItem
            key={lang.code}
            onClick={() => {
              console.log("Selected language:", lang.code);
              setLanguage(lang.code);
              setOpen(false);
            }}
            className={lang.code === language ? "bg-muted" : ""}
          >
            {lang.name}
            {lang.code === language && translate(COMPONENTS.active_checkmark)}
          </DropdownMenuItem>
        ))}
      </DropdownMenuContent>
    </DropdownMenu>
  );
}