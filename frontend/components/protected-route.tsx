"use client";

import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { useEffect } from "react";
import { useTranslate } from "@/lib/translation-helpers";
import { COMMON } from "@/app/common/translations";

export function ProtectedRoute({ children }: { children: React.ReactNode }) {
  const translate = useTranslate();
  const { data: session, status } = useSession();
  const router = useRouter();

  useEffect(() => {
    if (status === "loading") return;
    if (!session) {
      router.push("/login");
    }
  }, [session, status, router]);

  if (status === "loading" || !session) {
    return (
      <div className="flex items-center justify-center h-screen">
        {translate(COMMON.loading)}
      </div>
    );
  }

  return <>{children}</>;
}