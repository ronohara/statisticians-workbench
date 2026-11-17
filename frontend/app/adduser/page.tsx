"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData, type TranslationKey } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { Eye, EyeOff, XCircle } from "lucide-react";
import { validatePassword, type PasswordPolicy } from "@/lib/password-validation";

import { ADDUSER } from "./translations";
import { COMMON } from "@/app/common/translations";
import { PASSWORD_STRENGTH } from "@/app/common/translations";

interface Language {
  code: string;
  name: string;
}

export default function AddUserPage() {
  const router = useRouter();
  const { language: currentLanguage, isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [selectedLanguage, setSelectedLanguage] = useState<string>("en");
  const [formData, setFormData] = useState({
    name: "",
    email: "",
    password: "",
    confirmPassword: "",
  });
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [policy, setPolicy] = useState<PasswordPolicy | null>(null);
  const [passwordStrength, setPasswordStrength] = useState<{ score: number; feedback: string[] }>({ score: 0, feedback: [] });
  const [passwordErrors, setPasswordErrors] = useState<TranslationKey[]>([]);

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  // Admin gate: only full admins may create users from this page.
  useEffect(() => {
    apiFetch("/api/user/role")
      .then(res => (res.ok ? res.json() : { isAdmin: false }))
      .then((data: any) => setIsAdmin(data.isAdmin === true))
      .catch(() => setIsAdmin(false));
  }, []);

  const getLanguageName = (code: string) => {
    const lang = languages.find(l => l.code === code);
    return lang ? lang.name : code;
  };

  useEffect(() => {
    fetch(`/api/languages?viewer=${currentLanguage}`)
      .then(res => res.json())
      .then(data => setLanguages(data))
      .catch(console.error);

    fetch("/api/public-settings")
      .then(res => res.json())
      .then(data => {
        setPolicy({
          policy: data.passwordPolicy || "medium",
          custom: data.passwordPolicyCustom || undefined,
        });
      })
      .catch(console.error);
  }, [currentLanguage]);

  useEffect(() => {
    setSelectedLanguage(currentLanguage);
  }, [currentLanguage]);

  useEffect(() => {
    if (policy && formData.password) {
      const result = validatePassword(formData.password, policy);
      setPasswordErrors(result.errors);
      setPasswordStrength({ score: result.score, feedback: result.feedback });
    } else {
      setPasswordErrors([]);
      setPasswordStrength({ score: 0, feedback: [] });
    }
  }, [formData.password, policy]);

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

    if (policy) {
      const result = validatePassword(formData.password, policy);
      if (!result.valid) {
        const msg = result.errors.map(e => translate(e)).join(" ");
        setErrorMessage(msg);
        toast.error(msg);
        setIsLoading(false);
        return;
      }
    }

    if (formData.password !== formData.confirmPassword) {
      const msg = translate(ADDUSER.password_mismatch);
      setErrorMessage(msg);
      toast.error(msg);
      setIsLoading(false);
      return;
    }

    try {
      const res = await apiFetch("/api/admin/users", {
        method: "POST",
        body: JSON.stringify({
          name: formData.name,
          email: formData.email,
          password: formData.password,
          language: selectedLanguage,
        }),
      });

      if (!res.ok) {
        let errorData: any = {};
        try {
          const text = await res.text();
          if (text) errorData = JSON.parse(text);
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, ADDUSER.failed);
        throw new Error(errorMsg);
      }

      const msg = translate(ADDUSER.success);
      setSuccessMessage(msg);
      toast.success(msg);
      setFormData({ name: "", email: "", password: "", confirmPassword: "" });
      setShowPassword(false);
      setShowConfirmPassword(false);
      setTimeout(() => router.push("/admin"), 2000);
    } catch (error: any) {
      const msg = error.message || translate(ADDUSER.failed);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleLanguageChange = (value: string | null) => {
    if (value) {
      setSelectedLanguage(value);
    }
  };

  const getStrengthLabel = (score: number) => {
    if (score <= 1) return translate(PASSWORD_STRENGTH.weak);
    if (score === 2) return translate(PASSWORD_STRENGTH.fair);
    if (score === 3) return translate(PASSWORD_STRENGTH.good);
    if (score === 4) return translate(PASSWORD_STRENGTH.strong);
    return "";
  };

  if (!isLanguageLoaded || isAdmin === null) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
          <p className="mt-2 text-sm text-muted-foreground">{translate(COMMON.loading)}</p>
        </div>
      </div>
    );
  }

  if (!isAdmin) {
    return (
      <div className="max-w-md mx-auto py-24 px-4">
        <Card>
          <CardContent className="pt-6 text-center">
            <p className="text-sm text-muted-foreground mb-4">{translate(ADDUSER.not_admin)}</p>
            <Link href="/admin" className="text-primary text-sm underline">
              {translate(ADDUSER.back_to_admin)}
            </Link>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-md mx-auto py-12">
      <Card>
        <CardHeader>
          <CardTitle>{translate(ADDUSER.title)}</CardTitle>
          <CardDescription>{translate(ADDUSER.description)}</CardDescription>
        </CardHeader>
        <CardContent>
          {errorMessage && (
            <div className="mb-4 p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
              <span className="text-sm">{errorMessage}</span>
              <button
                onClick={dismissError}
                className="text-red-500 hover:text-red-700"
                aria-label={translate(COMMON.dismiss_error)}
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
                aria-label={translate(COMMON.dismiss_success)}
              >
                <span className="text-xl">&times;</span>
              </button>
            </div>
          )}

          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">{translate(ADDUSER.name)}</Label>
              <Input dir="auto"
                id="name"
                value={formData.name}
                onChange={handleChange}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">{translate(ADDUSER.email)}</Label>
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
              <Label htmlFor="password">{translate(ADDUSER.password)}</Label>
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
              {formData.password && (
                <div className="pt-1">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-1.5 rounded-full bg-muted">
                      <div
                        style={{
                          width: `${(passwordStrength.score / 4) * 100}%`,
                          backgroundColor:
                            passwordStrength.score < 2 ? "#ef4444" :
                            passwordStrength.score < 3 ? "#f59e0b" :
                            "#22c55e",
                        }}
                        className="h-1.5 rounded-full"
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
              <Label htmlFor="confirmPassword">{translate(ADDUSER.confirm_password)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="ltr"
                  id="confirmPassword"
                  type={showConfirmPassword ? "text" : "password"}
                  value={formData.confirmPassword}
                  onChange={handleChange}
                  required
                  className="flex-1 pe-10"
                />
                <button
                  type="button"
                  onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                  className="absolute inset-y-0 end-0 flex items-center pe-3 text-muted-foreground hover:text-foreground"
                  tabIndex={-1}
                >
                  {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="language">{translate(ADDUSER.language_description)}</Label>
              <Select value={selectedLanguage} onValueChange={handleLanguageChange}>
                <SelectTrigger className="w-full">
                  <SelectValue placeholder={translate(COMMON.loading)}>
                    {getLanguageName(selectedLanguage)}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {languages.map((lang) => (
                    <SelectItem key={lang.code} value={lang.code}>
                      {lang.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <Button type="submit" disabled={isLoading} className="w-full">
              {isLoading ? translate(ADDUSER.creating) : translate(ADDUSER.submit)}
            </Button>
          </form>
          <p className="text-center text-sm mt-4">
            <Link href="/admin" className="text-primary underline">
              {translate(ADDUSER.back_to_admin)}
            </Link>
          </p>
        </CardContent>
      </Card>
    </div>
  );
}
