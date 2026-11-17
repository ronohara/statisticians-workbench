"use client";

import { useSession } from "next-auth/react";
import { useState, useEffect, ReactNode } from "react";
import { Lock, UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import Link from "next/link";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";

// Import translations for this module
import { COMPONENTS } from "./translations";
import { COMMON } from "@/app/common/translations";

interface ExampleUserReadonlyWrapperProps {
  children: ReactNode;
  fallback?: ReactNode;
}

export function ExampleUserReadonlyWrapper({
  children,
  fallback,
}: ExampleUserReadonlyWrapperProps) {
  const { data: session, status } = useSession();
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const [isExampleUser, setIsExampleUser] = useState(false);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const fetchUserRole = async () => {
      if (status === "authenticated" && session?.user?.id) {
        try {
          const res = await apiFetch("/api/user/role");
          if (res.ok) {
            const data = await res.json();
            setIsExampleUser(data.isExampleUser === true);
          }
        } catch (error) {
          console.error("Failed to fetch user role:", error);
        } finally {
          setLoading(false);
        }
      } else if (status === "unauthenticated") {
        setLoading(false);
      } else {
        setLoading(false);
      }
    };

    fetchUserRole();
  }, [session, status]);

  if (loading || !isLanguageLoaded) {
    return <div className="animate-pulse">{translate(COMMON.loading)}</div>;
  }

  // If user is an Example User, show read-only message or fallback
  if (isExampleUser) {
    if (fallback) {
      return <>{fallback}</>;
    }
    return (
      <div className="relative">
        <div className="absolute inset-0 bg-muted/50 rounded-lg flex items-center justify-center z-10">
          <div className="bg-background/90 p-6 rounded-lg shadow-lg max-w-md text-center">
            <Lock className="h-8 w-8 mx-auto text-muted-foreground mb-3" />
            <p className="text-sm text-muted-foreground mb-4">
              {translate(COMPONENTS.readonly_wrapper)}
            </p>
            <Link href="/register">
              <Button size="sm" className="w-full">
                <UserPlus className="h-4 w-4 me-2" />
                {translate(COMPONENTS.example_user_banner.register_button)}
              </Button>
            </Link>
          </div>
        </div>
        <div className="opacity-50 pointer-events-none">{children}</div>
      </div>
    );
  }

  return <>{children}</>;
}