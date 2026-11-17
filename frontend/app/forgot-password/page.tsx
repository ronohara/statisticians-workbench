"use client";

import { useState, useEffect } from "react";
import { signOut, useSession } from "next-auth/react";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { toast } from "sonner";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { buttonVariants } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { XCircle } from "lucide-react";

// Import translations for this module
import { FORGOT_PASSWORD } from "./translations";
import { COMMON } from "@/app/common/translations";
import { LOGIN } from "@/app/login/translations";
import { LanguageSelector } from "@/components/language-selector";

export default function ForgotPasswordPage() {
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const { status } = useSession();
  const [email, setEmail] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [sent, setSent] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [registrationMode, setRegistrationMode] = useState<number | null>(null);

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  // Auto-logout if an authenticated user visits this page
  useEffect(() => {
    if (status === "authenticated") {
      signOut({ redirect: false });
    }
  }, [status]);

  useEffect(() => {
    fetch("/api/public-settings")
      .then(res => res.json())
      .then(data => setRegistrationMode(typeof data.registrationMode === "number" ? data.registrationMode : 0))
      .catch(() => setRegistrationMode(0));
  }, []);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await fetch("/api/auth/forgot-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
      });
      
      if (!res.ok) {
        let errorData: any = {};
        try {
          const text = await res.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, FORGOT_PASSWORD.error);
        throw new Error(errorMsg);
      }
      
      setSent(true);
      const msg = translate(FORGOT_PASSWORD.sent);
      setSuccessMessage(msg);
      toast.success(msg);
    } catch (error: any) {
      const msg = error.message || translate(FORGOT_PASSWORD.error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  if (!isLanguageLoaded || registrationMode === null) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
          <p className="mt-2 text-sm text-muted-foreground">{translate(COMMON.loading)}</p>
        </div>
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

  if (sent) {
    return (
      <div className="max-w-md mx-auto py-12 relative pt-28">
        <div className="absolute top-8 end-4">
          <LanguageSelector />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{translate(FORGOT_PASSWORD.sent_title)}</CardTitle>
            <CardDescription>
              {translate(FORGOT_PASSWORD.sent_description)}
            </CardDescription>
          </CardHeader>
          <CardContent>
            {errorMessage && (
              <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
                <span className="text-sm">{errorMessage}</span>
                <button
                  onClick={dismissError}
                  className="text-red-500 hover:text-red-700"
                  aria-label={translate(COMMON.dismiss)}
                >
                  <XCircle className="h-5 w-5" />
                </button>
              </div>
            )}

            {successMessage && (
              <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md text-green-800 flex items-center justify-between">
                <span className="text-sm">{successMessage}</span>
                <button
                  onClick={dismissSuccess}
                  className="text-green-500 hover:text-green-700"
                  aria-label={translate(COMMON.dismiss)}
                >
                  <span className="text-xl">&times;</span>
                </button>
              </div>
            )}

            <p className="text-sm text-muted-foreground mb-4">
              {translate(FORGOT_PASSWORD.check_spam)}
            </p>
            <Link
              href="/login"
              className={cn(buttonVariants({ variant: "outline" }), "w-full")}
            >
              {translate(FORGOT_PASSWORD.back_to_login)}
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
          <CardTitle>{translate(FORGOT_PASSWORD.title)}</CardTitle>
          <CardDescription>
            {translate(FORGOT_PASSWORD.description)}
          </CardDescription>
        </CardHeader>
        <CardContent>
          {errorMessage && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
              <span className="text-sm">{errorMessage}</span>
              <button
                onClick={dismissError}
                className="text-red-500 hover:text-red-700"
                aria-label={translate(COMMON.dismiss)}
              >
                <XCircle className="h-5 w-5" />
              </button>
            </div>
          )}

          {successMessage && (
            <div className="mb-4 p-3 bg-green-50 border border-green-200 rounded-md text-green-800 flex items-center justify-between">
              <span className="text-sm">{successMessage}</span>
              <button
                onClick={dismissSuccess}
                className="text-green-500 hover:text-green-700"
                aria-label={translate(COMMON.dismiss)}
              >
                <span className="text-xl">&times;</span>
              </button>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="email">{translate(LOGIN.email)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="ltr"
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  required
                  className="flex-1"
                />
              </div>
            </div>
            <Button type="submit" disabled={isLoading} className="w-full">
              {isLoading ? translate(COMMON.sending) : translate(FORGOT_PASSWORD.submit)}
            </Button>
          </form>
          <div className="mt-4 text-center">
            <Link
              href="/login"
              className={cn(buttonVariants({ variant: "link" }), "text-sm")}
            >
              {translate(FORGOT_PASSWORD.back_to_login)}
            </Link>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}