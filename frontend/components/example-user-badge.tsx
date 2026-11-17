"use client";

import { useSession } from "next-auth/react";
import { useState, useEffect } from "react";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";

// Import translations for this module
import { COMPONENTS } from "./translations";
import { COMMON } from "@/app/common/translations";

export function ExampleUserBadge() {
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

  if (loading || !isLanguageLoaded || !isExampleUser) {
    return null;
  }

  return (
    <span
      className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800 border border-orange-200 cursor-help"
      title={translate(COMPONENTS.example_user_badge_tooltip)}
    >
      <span className="me-1">🔒</span>
      {translate(COMPONENTS.example_user_badge)}
    </span>
  );
}