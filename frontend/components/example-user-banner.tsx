"use client";

import { useSession } from "next-auth/react";
import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import { X, UserPlus } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import Link from "next/link";

// Import translations for this module
import { COMPONENTS } from "./translations";
import { COMMON } from "@/app/common/translations";

export function ExampleUserBanner() {
  const { data: session, status } = useSession();
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const pathname = usePathname();
  const [isExampleUser, setIsExampleUser] = useState(false);
  const [loading, setLoading] = useState(true);
  const [bannerVisible, setBannerVisible] = useState(true);

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

  const isAuthPage = pathname === "/login" || pathname === "/register"
    || pathname === "/forgot-password" || pathname === "/reset-password"
    || pathname === "/verify-email" || pathname === "/resend-verification";

  if (loading || !isLanguageLoaded || !isExampleUser || !bannerVisible || isAuthPage) {
    return null;
  }

  return (
    <div className="pointer-events-auto w-full bg-orange-500 text-black dark:bg-orange-600 dark:text-white shadow-md">
      <div className="flex items-center justify-between px-4 py-2 mx-auto max-w-7xl">
        <div className="flex items-center gap-3">
          <span className="font-bold">🔒 {translate(COMPONENTS.example_user_banner.title)}</span>
          <span className="text-sm hidden sm:inline">
            {translate(COMPONENTS.example_user_banner.message)}
          </span>
          <span className="text-sm sm:hidden">
            {translate(COMPONENTS.example_user_banner.message_short)}
          </span>
        </div>
        <div className="flex items-center gap-2">
          <Link href="/register">
            <Button
              variant="default"
              size="sm"
              className="bg-white text-orange-700 hover:bg-orange-100 dark:bg-white dark:text-orange-700 dark:hover:bg-orange-100"
            >
              <UserPlus className="h-4 w-4 me-1" />
              <span className="hidden xs:inline">{translate(COMPONENTS.example_user_banner.register_button)}</span>
              <span className="xs:hidden">{translate(COMPONENTS.example_user_banner.register_short)}</span>
            </Button>
          </Link>
          <Button
            variant="ghost"
            size="icon"
            className="h-7 w-7 text-black dark:text-white hover:bg-orange-400 dark:hover:bg-orange-700"
            onClick={() => setBannerVisible(false)}
            aria-label={translate(COMMON.dismiss)}
          >
            <X className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </div>
  );
}