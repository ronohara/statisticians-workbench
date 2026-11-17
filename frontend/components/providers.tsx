"use client";

import { SessionProvider } from "next-auth/react";
import { DBProvider } from "@/lib/db-context";
import { AIProvider } from "@/lib/ai-context";
import { Toaster } from "sonner";
import { DarkModeProvider } from "@/components/dark-mode-provider";
import DemoIndicatorsComponent from "@/components/demo-indicators";
import { ExampleUserBanner } from "@/components/example-user-banner";
import BannerStack from "@/components/banner-stack";
import { TranslationProvider, useTranslation } from "@/lib/translation-context";
import { FeatureProvider } from "@/components/feature-gate";
import { RTL_LANGS } from "@/lib/rtl";

// Toast corner follows the document direction: RTL languages get their
// toasts in the top-left, mirroring the LTR top-right default.
function DirectionAwareToaster() {
  const { language } = useTranslation();
  const isRtl = RTL_LANGS.includes(language);
  return <Toaster position={isRtl ? "top-left" : "top-right"} richColors />;
}

export function Providers({ children }: { children: React.ReactNode }) {
  return (
    <SessionProvider>
      <DBProvider>
        <AIProvider>
          <DarkModeProvider>
            <TranslationProvider defaultLanguage="en">
              <FeatureProvider>
                {children}
                {/* One fixed strip for both indicator banners, so they stack when
                    both are present instead of covering each other. Demo first: it
                    is the louder of the two and used to win on z-index. */}
                <BannerStack>
                  <DemoIndicatorsComponent />
                  <ExampleUserBanner />
                </BannerStack>
                <DirectionAwareToaster />
              </FeatureProvider>
            </TranslationProvider>
          </DarkModeProvider>
        </AIProvider>
      </DBProvider>
    </SessionProvider>
  );
}