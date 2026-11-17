"use client";

import { useState, useEffect, Suspense, useRef } from "react";
import { useSearchParams, useRouter } from "next/navigation";
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
import { Eye, EyeOff, XCircle } from "lucide-react";
import { validatePassword, type PasswordPolicy } from "@/lib/password-validation";
import type { TranslationKey } from "@/lib/translation-helpers";

// Import translations for this module
import { RESET_PASSWORD } from "./translations";
import { COMMON } from "@/app/common/translations";
import { PASSWORD_STRENGTH } from "@/app/common/translations";
import { LanguageSelector } from "@/components/language-selector";

function ResetPasswordContent() {
  const router = useRouter();
  const searchParams = useSearchParams();
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const { status: sessionStatus } = useSession();
  const [token, setToken] = useState<string | null>(null);
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [isSuccess, setIsSuccess] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [policy, setPolicy] = useState<PasswordPolicy | null>(null);
  const [passwordErrors, setPasswordErrors] = useState<TranslationKey[]>([]);
  const [passwordStrength, setPasswordStrength] = useState<{ score: number; feedback: string[] }>({ score: 0, feedback: [] });
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [registrationMode, setRegistrationMode] = useState<number | null>(null);

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  // Auto-logout if an authenticated user visits this page
  useEffect(() => {
    if (sessionStatus === "authenticated") {
      signOut({ redirect: false });
    }
  }, [sessionStatus]);

  useEffect(() => {
    const tokenParam = searchParams.get("token");
    if (!tokenParam) {
      const msg = translate(RESET_PASSWORD.missing_token);
      setErrorMessage(msg);
      toast.error(msg);
      router.push("/login");
    } else {
      setToken(tokenParam);
    }

    // Fetch password policy
    fetch("/api/public-settings")
      .then(res => res.json())
      .then(data => {
        setPolicy({
          policy: data.passwordPolicy || "medium",
          custom: data.passwordPolicyCustom || undefined,
        });
        setRegistrationMode(typeof data.registrationMode === "number" ? data.registrationMode : 0);
      })
      .catch(console.error);
  }, [searchParams, router, translate]);

  useEffect(() => {
    if (policy && newPassword) {
      const result = validatePassword(newPassword, policy);
      setPasswordErrors(result.errors);
      setPasswordStrength({
        score: result.score,
        feedback: result.feedback,
      });
    } else {
      setPasswordErrors([]);
      setPasswordStrength({ score: 0, feedback: [] });
    }
  }, [newPassword, policy]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setErrorMessage(null);
    setSuccessMessage(null);

    if (newPassword !== confirmPassword) {
      const msg = translate(RESET_PASSWORD.password_mismatch);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }

    // Validate password against policy
    if (policy) {
      const result = validatePassword(newPassword, policy);
      if (!result.valid) {
        const msg = result.errors.map(e => translate(e)).join(" ");
        setErrorMessage(msg);
        toast.error(msg);
        return;
      }
    }

    setIsLoading(true);
    try {
      const res = await fetch("/api/auth/reset-password", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ token, newPassword }),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, RESET_PASSWORD.failed);
        throw new Error(errorMsg);
      }
      
      const data = await res.json();
      setIsSuccess(true);
      const msg = translate(RESET_PASSWORD.success);
      setSuccessMessage(msg);
      toast.success(msg);
      setTimeout(() => router.push("/login"), 3000);
    } catch (error: any) {
      const msg = error.message || translate(RESET_PASSWORD.failed);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const getStrengthLabel = (score: number) => {
    if (score === 0) return translate(PASSWORD_STRENGTH.weak);
    if (score === 1) return translate(PASSWORD_STRENGTH.weak);
    if (score === 2) return translate(PASSWORD_STRENGTH.fair);
    if (score === 3) return translate(PASSWORD_STRENGTH.good);
    if (score === 4) return translate(PASSWORD_STRENGTH.strong);
    return "";
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

  if (isSuccess) {
    return (
      <div className="max-w-md mx-auto py-12 relative pt-28">
        <div className="absolute top-8 end-4">
          <LanguageSelector />
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{translate(RESET_PASSWORD.success_title)}</CardTitle>
            <CardDescription>
              {translate(RESET_PASSWORD.success_description)}
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

            <Link
              href="/login"
              className={cn(buttonVariants(), "w-full")}
            >
              {translate(RESET_PASSWORD.login_button)}
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
          <CardTitle>{translate(RESET_PASSWORD.title)}</CardTitle>
          <CardDescription>
            {translate(RESET_PASSWORD.description)}
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
              <Label htmlFor="newPassword">{translate(RESET_PASSWORD.new_password)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="ltr"
                  id="newPassword"
                  type={showNewPassword ? "text" : "password"}
                  value={newPassword}
                  onChange={(e) => setNewPassword(e.target.value)}
                  required
                  className="flex-1 pe-10"
                />
                <button
                  type="button"
                  onClick={() => setShowNewPassword(!showNewPassword)}
                  className="absolute inset-y-0 end-0 flex items-center pe-3 text-muted-foreground hover:text-foreground"
                >
                  {showNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {newPassword && (
                <div className="space-y-1 mt-1">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full transition-all duration-300"
                        style={{
                          width: `${(passwordStrength.score / 4) * 100}%`,
                          backgroundColor:
                            passwordStrength.score < 2 ? "#ef4444" :
                            passwordStrength.score < 3 ? "#f59e0b" :
                            "#22c55e",
                        }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {getStrengthLabel(passwordStrength.score)}
                    </span>
                  </div>
                  {passwordStrength.feedback.length > 0 && (
                    <ul className="text-xs text-muted-foreground list-disc ps-4">
                      {passwordStrength.feedback.map((msg, i) => (
                        <li key={i}>{msg}</li>
                      ))}
                    </ul>
                  )}
                  {passwordErrors.length > 0 && (
                    <ul className="text-xs text-red-500 list-disc ps-4">
                      {passwordErrors.map((err, i) => (
                        <li key={i}>{translate(err)}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirmPassword">{translate(RESET_PASSWORD.confirm_password)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="ltr"
                  id="confirmPassword"
                  type={showConfirmPassword ? "text" : "password"}
                  value={confirmPassword}
                  onChange={(e) => setConfirmPassword(e.target.value)}
                  required
                  className="flex-1 pe-10"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute inset-y-0 end-0 flex items-center pe-3 text-muted-foreground hover:text-foreground"
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>
            <Button type="submit" disabled={isLoading} className="w-full">
              {isLoading ? translate(COMMON.saving) : translate(RESET_PASSWORD.submit)}
            </Button>
          </form>
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

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={<LoadingFallback />}>
      <ResetPasswordContent />
    </Suspense>
  );
}