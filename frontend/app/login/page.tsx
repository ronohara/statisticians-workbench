// frontend/app/login/page.tsx
"use client";

import { useState, useEffect } from "react";
import { signIn } from "next-auth/react";
import { useRouter, useSearchParams } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { LanguageSelector } from "@/components/language-selector";
import { Eye, EyeOff } from "lucide-react";

// Import translations for this module
import { LOGIN } from "./translations";
import { COMMON } from "@/app/common/translations";
import { APP } from "@/app/common/translations";

interface SignInError {
  code: string;
  message: string;
  language: string;
}

export default function LoginPage() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { language, setLanguage, isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [formData, setFormData] = useState({ email: "", password: "" });
  const [version, setVersion] = useState<string>("");
  const [showPassword, setShowPassword] = useState(false);
  const [welcome, setWelcome] = useState<string>("");
  const [registrationMode, setRegistrationMode] = useState<number | null>(null);
  // Track the language that the page should be using
  const [pageLanguage, setPageLanguage] = useState(language);

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  // When the context language changes, update the page language
  useEffect(() => {
    setPageLanguage(language);
  }, [language]);

  // Fetch version
  useEffect(() => {
    fetch("/api/version")
      .then(res => res.json())
      .then(data => setVersion(data.version))
      .catch(() => setVersion("0.0.1"));
  }, []);

  // Fetch welcome message from global settings
  useEffect(() => {
    const fetchWelcome = async () => {
      try {
        const res = await fetch("/api/public-settings");
        if (!res.ok) {
          throw new Error(`HTTP ${res.status}`);
        }
        const data = await res.json();
        const welcomeText = data.welcome || "";
        setWelcome(welcomeText);
        setRegistrationMode(typeof data.registrationMode === "number" ? data.registrationMode : 0);
      } catch (err) {
        console.error("Failed to fetch welcome message:", err);
        setWelcome("");
      }
    };
    fetchWelcome();
  }, []);

  // Handle URL parameters for verification
  useEffect(() => {
    const verified = searchParams.get("verified");
    const error = searchParams.get("error");

    if (verified === "true") {
      setSuccessMessage(translate(LOGIN.email_verified));
    } else if (error === "api.auth.invalid_token") {
      setErrorMessage(translate(LOGIN.invalid_token));
    } else if (error === "api.auth.token_expired") {
      setErrorMessage(translate(LOGIN.token_expired));
    } else if (error === "api.auth.missing_token") {
      setErrorMessage(translate(LOGIN.missing_token));
    }
  }, [searchParams, translate]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setFormData({ ...formData, [e.target.id]: e.target.value });
    if (errorMessage) setErrorMessage(null);
    if (successMessage) setSuccessMessage(null);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setIsLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    const result = await signIn("credentials", {
      email: formData.email,
      password: formData.password,
      language: language,
      redirect: false,
    });

    if (result?.error) {
      setIsLoading(false);

      try {
        const errorData = JSON.parse(result.error) as SignInError;
        if (errorData.message && errorData.language) {
          setLanguage(errorData.language);
          setErrorMessage(errorData.message);
          toast.error(errorData.message);
          return;
        }
      } catch {
        // Not JSON, use as-is
      }

      setErrorMessage(result.error);
      toast.error(result.error);
    } else {
      // Check if admin user needs to configure required global settings
      try {
        const roleRes = await fetch("/api/user/role");
        if (roleRes.ok) {
          const roleData = await roleRes.json();
          if (roleData.isAdmin) {
            const settingsRes = await apiFetch("/api/global-settings");
            if (settingsRes.ok) {
              const settingsData = await settingsRes.json();
              const needsSetup =
                settingsData.emailSender === "no-reply@replace-with-your-domain" ||
                settingsData.publicUrl === "https://replace-with-your-external-host-name";
              if (needsSetup) {
                router.push("/admin/setup/options?setup=required");
                setIsLoading(false);
                return;
              }
            }
          }
        }
      } catch {
        // Ignore errors — proceed with normal login
      }
      const successMsg = translate(LOGIN.success);
      router.push("/?toast=login_success");
      setIsLoading(false);
    }
  };

  // Check if the error is an email not verified error
  const isEmailNotVerifiedError = (() => {
    if (!errorMessage) return false;
    try {
      const errorData = JSON.parse(errorMessage) as SignInError;
      return errorData.code === "EMAIL_NOT_VERIFIED";
    } catch {
      try {
        const expectedMessage = translate(LOGIN.email_not_verified);
        return errorMessage.toLowerCase().includes(expectedMessage.toLowerCase());
      } catch {
        return false;
      }
    }
  })();

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

  return (
    <div key={pageLanguage} className="max-w-md mx-auto py-12 relative pt-28">
      <div className="absolute top-8 end-4">
        <LanguageSelector />
      </div>

      <Card>
        <CardHeader>
          <CardTitle>{translate(LOGIN.title)}</CardTitle>
          <CardDescription>{translate(LOGIN.description)}</CardDescription>
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
                <span className="text-xl">&times;</span>
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
                  value={formData.email}
                  onChange={handleChange}
                  required
                  className="flex-1"
                />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">{translate(LOGIN.password)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="ltr"
                  id="password"
                  type={showPassword ? "text" : "password"}
                  value={formData.password}
                  onChange={handleChange}
                  required
                  className="flex-1 pe-10"
                />
                <button
                  type="button"
                  onClick={() => setShowPassword(!showPassword)}
                  className="absolute inset-y-0 end-0 flex items-center pe-3 text-muted-foreground hover:text-foreground"
                  tabIndex={-1}
                >
                  {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {registrationMode === 4 && (
              <div className="text-end">
                <Link href="/forgot-password" className="text-sm text-primary hover:underline">
                  {translate(LOGIN.forgot_password)}
                </Link>
              </div>
            )}

            {isEmailNotVerifiedError && registrationMode === 4 && (
              <div className="text-center">
                <Link href="/resend-verification" className="text-sm text-primary hover:underline">
                  {translate(LOGIN.resend_link)}
                </Link>
              </div>
            )}

            <Button type="submit" disabled={isLoading} className="w-full">
              {isLoading ? translate(LOGIN.signing_in) : translate(LOGIN.submit)}
            </Button>
          </form>
          {registrationMode !== 1 && (
            <p className="text-center text-sm mt-4">
              {translate(LOGIN.no_account)}{" "}
              <Link href="/register" className="text-primary underline">
                {translate(LOGIN.register_link)}
              </Link>
            </p>
          )}
        </CardContent>
      </Card>

      {welcome && welcome.trim().length > 0 && (
        <div className="mt-6 p-4 bg-muted/50 rounded-md text-center text-sm text-muted-foreground whitespace-pre-wrap border border-muted">
          {welcome}
        </div>
      )}

      <div className="text-center text-xs text-muted-foreground mt-4">
        <a href="https://workbench-docs.sentuny.com" target="_blank" rel="noopener noreferrer" className="hover:underline">
          workbench-docs.sentuny.com
        </a>
        {" "}{translate(LOGIN.docs_more_info)}
      </div>

      <div className="text-center text-xs text-muted-foreground mt-8">
        {translate(APP.version)} {version}
      </div>
    </div>
  );
}