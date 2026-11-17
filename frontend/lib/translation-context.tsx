// frontend/lib/translation-context.tsx
"use client";

import { createContext, useContext, useEffect, useState, useRef, useCallback } from "react";
import { useSession } from "next-auth/react";
import { Loader2 } from "lucide-react";
import { RTL_LANGS } from "@/lib/rtl";
import { SUPPORTED_LANGUAGES } from "@/lib/supported-languages";
import { apiFetch } from "@/lib/api";

type Translations = Record<string, string>;

interface TranslationContextType {
  t: (key: string, fallback?: string) => string;
  setLanguage: (lang: string) => void;
  language: string;
  isLoading: boolean;
  isLanguageLoaded: boolean;
}

const TranslationContext = createContext<TranslationContextType | null>(null);

function getBrowserLanguage(): string | null {
  if (typeof document === "undefined") return null;
  // Check cookie first (set by static website language switcher)
  const cookieMatch = document.cookie.match(/(?:^|;\s*)lang=(\w+)/);
  if (cookieMatch && SUPPORTED_LANGUAGES.includes(cookieMatch[1])) {
    return cookieMatch[1];
  }
  // Fall back to browser preference
  if (typeof navigator !== "undefined" && navigator.language) {
    const lang = navigator.language.slice(0, 2);
    if (SUPPORTED_LANGUAGES.includes(lang)) return lang;
  }
  return null;
}

export function TranslationProvider({ 
  children, 
  defaultLanguage = "en" 
}: { 
  children: React.ReactNode; 
  defaultLanguage?: string;
}) {
  const { data: session, status } = useSession();
  const [language, setLanguageState] = useState(() => getBrowserLanguage() || defaultLanguage);
  const [translations, setTranslations] = useState<Translations>({});
  const [servedLanguage, setServedLanguage] = useState("en");
  const [isLoading, setIsLoading] = useState(true);
  const [isLanguageLoaded, setIsLanguageLoaded] = useState(false);
  const saveTimeoutRef = useRef<NodeJS.Timeout | null>(null);
  const isAuthenticated = status === "authenticated";
  const isExampleUser = (session?.user as any)?.isExampleUser === true;
  const sessionLanguage = (session?.user as any)?.language;

  // For Example Users, use the session language override if available
  const effectiveLanguage = isExampleUser && sessionLanguage 
    ? sessionLanguage 
    : language;

  // Load translations whenever the effective language changes
  useEffect(() => {
    setIsLoading(true);
    fetch(`/api/translations?language=${effectiveLanguage}`)
      .then(res => res.json())
      .then(async data => {
        // Future-proofing: an effective language with no shipped
        // translations (e.g. a browser-detected code that was never
        // translated) is served in English — strings and direction both.
        if (data && typeof data === "object" &&
            Object.keys(data).length === 0 &&
            effectiveLanguage !== "en") {
          const enData = await fetch("/api/translations?language=en")
            .then(r => r.json());
          setTranslations(enData);
          setServedLanguage("en");
        } else {
          setTranslations(data || {});
          setServedLanguage(effectiveLanguage);
        }
        setIsLoading(false);
      })
      .catch(err => {
        console.error("Failed to load translations:", err);
        setIsLoading(false);
      });
  }, [effectiveLanguage]);

  // Document direction: mirror the served language onto <html dir/lang>.
  // Post-hydration mutation of the document element — outside React's tree,
  // so no hydration mismatch (same pattern as dark-mode-provider).
  useEffect(() => {
    const dir = RTL_LANGS.includes(servedLanguage) ? "rtl" : "ltr";
    document.documentElement.setAttribute("dir", dir);
    document.documentElement.setAttribute("lang", servedLanguage);
  }, [servedLanguage]);

  // Load user's saved language when authenticated (but don't override Example User session language)
  useEffect(() => {
    if (isAuthenticated && session?.user?.id) {
      setIsLoading(true);
      apiFetch("/api/user-settings")
        .then(res => res.json())
        .then(data => {
          // For Example Users, session language takes precedence
          if (isExampleUser && sessionLanguage) {
            // Use session language - already set
            setIsLanguageLoaded(true);
            setIsLoading(false);
            return;
          }
          // Regular users: use saved language
          if (data.language) {
            setLanguageState(data.language);
          }
          setIsLanguageLoaded(true);
          setIsLoading(false);
        })
        .catch(err => {
          console.error("Failed to load user language:", err);
          setIsLanguageLoaded(true);
          setIsLoading(false);
        });
    } else if (status === "unauthenticated") {
      // Only override if the lazy initializer didn't already detect a browser language
      setLanguageState(prev => {
        if (prev !== defaultLanguage) return prev; // already detected, keep it
        const browserLang = getBrowserLanguage();
        return browserLang || defaultLanguage;
      });
      setIsLanguageLoaded(true);
      setIsLoading(false);
    }
  }, [isAuthenticated, session, status, defaultLanguage, isExampleUser, sessionLanguage]);

  // Save language to database when it changes (for authenticated users - but skip Example Users)
  useEffect(() => {
    // Skip saving for Example Users (they can't change their profile)
    if (isExampleUser) return;
    
    if (isAuthenticated && session?.user?.id && isLanguageLoaded) {
      // Clear any pending save
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
      // Debounce to avoid excessive saves
      saveTimeoutRef.current = setTimeout(async () => {
        try {
          const response = await apiFetch("/api/user-settings", {
            method: "POST",
            body: JSON.stringify({ language }),
          });
          if (!response.ok) {
            console.error("Failed to save language:", await response.text());
          }
        } catch (err) {
          console.error("Failed to save language:", err);
        }
      }, 500);
    }
    return () => {
      if (saveTimeoutRef.current) {
        clearTimeout(saveTimeoutRef.current);
      }
    };
  }, [language, isAuthenticated, session, isLanguageLoaded, isExampleUser]);

  const t = useCallback((key: string, fallback?: string): string => {
    const translated = translations[key];
    if (translated) return translated;
    if (fallback !== undefined) return fallback;
    return key;
  }, [translations]);

  const setLanguage = (lang: string) => {
    if (lang === language) return;
    setLanguageState(lang);
  };

  // Wait for language to be loaded before rendering
  if (!isLanguageLoaded && isAuthenticated) {
    return (
      <TranslationContext.Provider 
        value={{ 
          t, 
          setLanguage, 
          language: servedLanguage, 
          isLoading: true,
          isLanguageLoaded: false,
        }}
      >
        <div className="flex items-center justify-center h-screen">
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
        </div>
      </TranslationContext.Provider>
    );
  }

  return (
    <TranslationContext.Provider 
      value={{ 
        t, 
        setLanguage, 
        language: servedLanguage, 
        isLoading: false,
        isLanguageLoaded: true,
      }}
    >
      {children}
    </TranslationContext.Provider>
  );
}

export function useTranslation() {
  const ctx = useContext(TranslationContext);
  if (!ctx) throw new Error("useTranslation must be used within TranslationProvider");
  return ctx;
}