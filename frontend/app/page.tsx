"use client";

import { useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { useSession } from "next-auth/react";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate } from "@/lib/translation-helpers";
import { isDemoSystem } from "@/lib/demo";
import { HOME, COMMON } from "@/app/common/translations";
import { LOGIN } from "@/app/login/translations";
import { ExternalLink } from "lucide-react";
import { toast } from "sonner";

function HomeContent() {
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const searchParams = useSearchParams();
  const [toastShown, setToastShown] = useState(false);

  // Handle toast from login page - wait for language to load
  useEffect(() => {
    // Only proceed if language is loaded and toast hasn't been shown yet
    if (!isLanguageLoaded || toastShown) {
      return;
    }

    const toastType = searchParams.get("toast");

    if (toastType === "login_success") {
      // Language is now loaded, show toast in the correct language
      toast.success(translate(LOGIN.success));
      setToastShown(true);

      // Clean up URL parameters
      const newUrl = window.location.pathname;
      window.history.replaceState({}, "", newUrl);
    }
  }, [isLanguageLoaded, searchParams, translate, toastShown]);

  return (
    <div className="flex flex-col items-center justify-center h-full min-h-[60vh] gap-6 px-4">
      <p className="text-muted-foreground text-lg">
        {translate(HOME.welcome_placeholder)}
      </p>
      <div className="flex flex-wrap items-center justify-center gap-3">
        <a
          href="https://www.sentuny.com"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold bg-blue-50 text-blue-700 rounded-md hover:bg-blue-100 transition-colors"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          Sentuny
        </a>
        <a
          href="https://workbench.sentuny.com"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold bg-blue-50 text-blue-700 rounded-md hover:bg-blue-100 transition-colors"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          Workbench
        </a>
        <a
          href="https://replicator.sentuny.com"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold bg-blue-50 text-blue-700 rounded-md hover:bg-blue-100 transition-colors"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          Replicator
        </a>
        <a
          href="https://replicator-ng.sentuny.com"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold bg-blue-50 text-blue-700 rounded-md hover:bg-blue-100 transition-colors"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          Replicator-NG
        </a>
        <a
          href="https://msaccess-endpoint.sentuny.com"
          target="_blank"
          rel="noopener noreferrer"
          className="inline-flex items-center gap-1.5 px-3 py-1.5 text-sm font-semibold bg-blue-50 text-blue-700 rounded-md hover:bg-blue-100 transition-colors"
        >
          <ExternalLink className="h-3.5 w-3.5" />
          MS Access Endpoint
        </a>
      </div>
    </div>
  );
}

export default function HomePage() {
  const router = useRouter();
  const { data: session, status } = useSession();
  const [demoMode, setDemoMode] = useState<boolean | null>(null);
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();

  useEffect(() => {
    if (status === "loading") return;
    if (status === "authenticated") {
      setDemoMode(true);
      return;
    }

    isDemoSystem()
      .then(isDemo => {
        if (!isDemo) {
          router.replace("/login");
        } else {
          setDemoMode(true);
        }
      });
  }, [router, status, session]);

  // Show loading while language is loading
  if ((demoMode === null && status !== "authenticated") || !isLanguageLoaded) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
          <p className="mt-2 text-sm text-muted-foreground">{translate(COMMON.loading)}</p>
        </div>
      </div>
    );
  }

  return <HomeContent />;
}
