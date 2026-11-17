"use client";

import { useEffect, useState, Suspense, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { signOut, useSession } from "next-auth/react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { buttonVariants } from "@/components/ui/button";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate } from "@/lib/translation-helpers";
import { cn } from "@/lib/utils";

// Import translations for this module
import { VERIFY_EMAIL } from "./translations";
import { COMMON } from "@/app/common/translations";
import { LanguageSelector } from "@/components/language-selector";

function VerifyEmailContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const { status: sessionStatus } = useSession();
  const [status, setStatus] = useState<"loading" | "success" | "error" | "expired" | "missing">("loading");
  const [errorMessage, setErrorMessage] = useState<string>("");
  const hasVerified = useRef(false);
  const [registrationMode, setRegistrationMode] = useState<number | null>(null);

  // Auto-logout if an authenticated user visits this page
  useEffect(() => {
    if (sessionStatus === "authenticated") {
      signOut({ redirect: false });
    }
  }, [sessionStatus]);

  useEffect(() => {
    fetch("/api/public-settings")
      .then(res => res.json())
      .then(data => setRegistrationMode(typeof data.registrationMode === "number" ? data.registrationMode : 0))
      .catch(() => setRegistrationMode(0));
  }, []);

  useEffect(() => {
    // Prevent double verification
    if (hasVerified.current) {
      return;
    }

    const token = searchParams.get("token");

    if (!token) {
      setStatus("missing");
      return;
    }

    const verifyToken = async () => {
      try {
        const response = await fetch(`/api/auth/verify-email?token=${token}`);
        const data = await response.json();

        if (data.success) {
          setStatus("success");
          setTimeout(() => router.push("/login?verified=true"), 2000);
        } else if (data.error === "api.auth.invalid_token") {
          setStatus("error");
          setErrorMessage(translate(VERIFY_EMAIL.invalid_token));
        } else if (data.error === "api.auth.token_expired") {
          setStatus("expired");
        } else {
          setStatus("error");
          setErrorMessage(data.error || translate(VERIFY_EMAIL.unknown_error));
        }
      } catch (error) {
        console.error("Verification error:", error);
        setStatus("error");
        setErrorMessage(translate(VERIFY_EMAIL.network_error));
      }
    };

    hasVerified.current = true;
    verifyToken();
  }, [searchParams, router, translate]);

  if (!isLanguageLoaded || registrationMode === null || status === "loading") {
    return (
      <div className="max-w-md mx-auto py-12 relative pt-28">
        <div className="absolute top-8 end-4">
          <LanguageSelector />
        </div>
        <Card>
          <CardContent className="pt-6">
            <p className="text-center">{translate(COMMON.loading)}</p>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (registrationMode !== 4) {
    return (
      <div className="max-w-md mx-auto py-24 px-4 text-center">
        <p className="text-sm text-muted-foreground">{translate(COMMON.email_features_unavailable)}</p>
      </div>
    );
  }

  if (status === "success") {
    return (
      <div className="max-w-md mx-auto py-12 relative pt-28">
        <div className="absolute top-8 end-4">
          <LanguageSelector />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{translate(VERIFY_EMAIL.success_title)}</CardTitle>
            <CardDescription>
              {translate(VERIFY_EMAIL.success_description)}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              href="/login"
              className={cn(buttonVariants(), "w-full")}
            >
              {translate(VERIFY_EMAIL.login_button)}
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === "expired") {
    return (
      <div className="max-w-md mx-auto py-12 relative pt-28">
        <div className="absolute top-8 end-4">
          <LanguageSelector />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{translate(VERIFY_EMAIL.expired_title)}</CardTitle>
            <CardDescription>
              {translate(VERIFY_EMAIL.expired_description)}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <p className="text-sm text-muted-foreground">
              {translate(VERIFY_EMAIL.expired_message)}
            </p>
            <Link
              href="/resend-verification"
              className={cn(buttonVariants(), "w-full")}
            >
              {translate(VERIFY_EMAIL.resend_button)}
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  if (status === "missing") {
    return (
      <div className="max-w-md mx-auto py-12 relative pt-28">
        <div className="absolute top-8 end-4">
          <LanguageSelector />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{translate(VERIFY_EMAIL.missing_title)}</CardTitle>
            <CardDescription>
              {translate(VERIFY_EMAIL.missing_description)}
            </CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              href="/resend-verification"
              className={cn(buttonVariants(), "w-full")}
            >
              {translate(VERIFY_EMAIL.resend_button)}
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto py-12 relative pt-28">
      <div className="absolute top-8 end-4">
        <LanguageSelector />
      </div>
      <Card>
        <CardHeader>
          <CardTitle>{translate(VERIFY_EMAIL.error_title)}</CardTitle>
          <CardDescription>{errorMessage || translate(VERIFY_EMAIL.error_description)}</CardDescription>
        </CardHeader>
        <CardContent>
          <Link
            href="/resend-verification"
            className={cn(buttonVariants(), "w-full")}
          >
            {translate(VERIFY_EMAIL.resend_button)}
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}

function LoadingFallback() {
  const translate = useTranslate();
  return (
    <div className="max-w-md mx-auto py-12 relative pt-28">
      <div className="absolute top-8 end-4">
        <LanguageSelector />
      </div>
      <Card><CardContent className="pt-6"><p className="text-center">{translate(COMMON.loading)}</p></CardContent></Card>
    </div>
  );
}

export default function VerifyEmailPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <VerifyEmailContent />
    </Suspense>
  );
}