"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Rocket, Zap, Shield } from "lucide-react";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate } from "@/lib/translation-helpers";
import { isDemoSystem } from "@/lib/demo";

// Import translations for this module
import { ABOUT } from "./translations";
import { COMMON } from "@/app/common/translations";

function AboutContent() {
  const translate = useTranslate();

  return (
    <div className="space-y-6">
      <section className="text-center py-12">
        <h1 className="text-4xl font-bold tracking-tight">
          {translate(ABOUT.title)}
        </h1>
        <p className="mt-4 text-lg text-muted-foreground max-w-2xl mx-auto">
          {translate(ABOUT.description)}
        </p>
        <Button className="mt-6" size="lg" onClick={() => window.open("https://www.sentuny.com", "_blank")}>
          {translate(ABOUT.get_started)}
        </Button>
      </section>

      <div className="grid gap-6 md:grid-cols-3">
        <Card>
          <CardHeader>
            <Rocket className="h-8 w-8 mb-2" />
            <CardTitle>{translate(ABOUT.fast_title)}</CardTitle>
            <CardDescription>
              {translate(ABOUT.fast_desc)}
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <Zap className="h-8 w-8 mb-2" />
            <CardTitle>{translate(ABOUT.modern_title)}</CardTitle>
            <CardDescription>
              {translate(ABOUT.modern_desc)}
            </CardDescription>
          </CardHeader>
        </Card>
        <Card>
          <CardHeader>
            <Shield className="h-8 w-8 mb-2" />
            <CardTitle>{translate(ABOUT.secure_title)}</CardTitle>
            <CardDescription>
              {translate(ABOUT.secure_desc)}
            </CardDescription>
          </CardHeader>
        </Card>
      </div>
    </div>
  );
}

export default function AboutPage() {
  const router = useRouter();
  const { data: session, status } = useSession();
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const [demoMode, setDemoMode] = useState<boolean | null>(null);

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

  if (!isLanguageLoaded) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
          <p className="mt-2 text-sm text-muted-foreground">{translate(COMMON.loading)}</p>
        </div>
      </div>
    );
  }

  if (demoMode === null && status !== "authenticated") {
    return <div className="flex items-center justify-center h-screen">{translate(COMMON.loading)}</div>;
  }

  return <AboutContent />;
}