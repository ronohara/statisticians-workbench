"use client";

import { useState, useEffect } from "react";
import { createPortal } from "react-dom";
import { X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate } from "@/lib/translation-helpers";
import { isDemoSystem } from "@/lib/demo";

// Import translations for this module
import { DEMO } from "@/app/common/translations";

function DemoIndicatorsComponent() {
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const [demoMode, setDemoMode] = useState(false);
  const [bannerVisible, setBannerVisible] = useState(true);
  const [loading, setLoading] = useState(true);
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    setMounted(true);
    isDemoSystem()
      .then(setDemoMode)
      .finally(() => setLoading(false));
  }, []);

  if (loading || !demoMode || !mounted || !isLanguageLoaded) return null;

  const Banner = () => {
    if (!bannerVisible) return null;
    return (
      <div className="pointer-events-auto w-full bg-amber-500 text-black dark:bg-amber-600 dark:text-white shadow-md">
        <div className="flex items-center justify-between px-4 py-2 mx-auto">
          <div className="flex items-center gap-2">
            <span className="font-bold">{translate(DEMO.banner.title)}</span>
            <span className="text-sm">{translate(DEMO.banner.message)}</span>
          </div>
          <Button
            variant="ghost"
            size="icon"
            className="h-6 w-6 text-black dark:text-white hover:bg-amber-400 dark:hover:bg-amber-700"
            onClick={() => setBannerVisible(false)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
    );
  };

  const FloatingBadge = () => (
    <div className="fixed bottom-4 right-4 z-[9999] rounded-full bg-amber-500 px-3 py-1 text-xs font-bold text-black shadow-lg dark:bg-amber-600 dark:text-white">
      {translate(DEMO.badge)}
    </div>
  );

  return (
    <>
      {/* The banner renders in place: its parent is the fixed strip in
          banner-stack.tsx, which stacks it with the example-user banner instead
          of the two covering each other. The badge is unrelated to that strip
          and stays portalled. */}
      <Banner />
      {createPortal(<FloatingBadge />, document.body)}
    </>
  );
}

export default DemoIndicatorsComponent;