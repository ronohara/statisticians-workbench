// frontend/app/admin/setup/options/page.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Input } from "@/components/ui/input";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessage, type TranslationKey } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { Lock, UserPlus } from "lucide-react";
import Link from "next/link";

import { OPTIONS_SETTINGS } from "./translations";
import { COMMON } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";

// Base UI's Select.Value renders the raw value unless it is given children, so
// each select's code → description mapping is declared once here and used by both
// the closed trigger and the option list.
const PASSWORD_POLICY_LABELS: Record<string, TranslationKey> = {
  low: OPTIONS_SETTINGS.password_policy.low,
  medium: OPTIONS_SETTINGS.password_policy.medium,
  high: OPTIONS_SETTINGS.password_policy.high,
  custom: OPTIONS_SETTINGS.password_policy.custom,
};

const REGISTRATION_MODE_LABELS: Record<string, TranslationKey> = {
  "0": OPTIONS_SETTINGS.registration_mode.mode_0,
  "1": OPTIONS_SETTINGS.registration_mode.mode_1,
  "2": OPTIONS_SETTINGS.registration_mode.mode_2,
  "4": OPTIONS_SETTINGS.registration_mode.mode_4,
};

export default function OptionsPage() {
  const router = useRouter();
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();

  const [emailSender, setEmailSender] = useState<string>("no-reply@replace-with-your-domain");
  const [publicUrl, setPublicUrl] = useState<string>("https://replace-with-your-external-host-name");
  const [welcome, setWelcome] = useState<string>("");
  const [passwordPolicy, setPasswordPolicy] = useState<string>("medium");
  const [registrationMode, setRegistrationMode] = useState<number>(0);
  const [customRules, setCustomRules] = useState({
    minLength: 8,
    requireUppercase: true,
    requireLowercase: true,
    requireDigit: true,
    requireSpecial: false,
    minStrength: 2,
  });
  const [isLoading, setIsLoading] = useState(true);
  const [isSaving, setIsSaving] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<{ isAdmin: boolean; isGroupAdmin: boolean; isExampleUser: boolean } | null>(null);
  const [loadingRole, setLoadingRole] = useState(true);

  const initialFetchDone = useRef(false);

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  const isExampleUser = userRole?.isExampleUser === true;

  useEffect(() => {
    apiFetch("/api/user/role")
      .then(res => res.ok ? res.json() : null)
      .then(data => { if (data) setUserRole(data); })
      .catch(() => {})
      .finally(() => setLoadingRole(false));
  }, []);

  useEffect(() => {
    if (initialFetchDone.current) return;
    initialFetchDone.current = true;
    setErrorMessage(null);
    apiFetch("/api/global-settings")
      .then(async res => {
        if (!res.ok) {
          const msg = await getErrorMessage(translate, res, OPTIONS_SETTINGS.load_error);
          throw new Error(msg);
        }
        return res.json();
      })
      .then(data => {
        setEmailSender(data.emailSender ?? "no-reply@replace-with-your-domain");
        setPublicUrl(data.publicUrl ?? "https://replace-with-your-external-host-name");
        setWelcome(data.welcome ?? "");
        setPasswordPolicy(data.passwordPolicy || "medium");
        setRegistrationMode(typeof data.registrationMode === "number" ? data.registrationMode : 0);
        if (data.passwordPolicyCustom) {
          setCustomRules(data.passwordPolicyCustom);
        }
      })
      .catch((error: any) => {
        const msg = error.message || translate(OPTIONS_SETTINGS.load_error);
        setErrorMessage(msg);
        toast.error(msg);
      })
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handlePasswordPolicyChange = (value: string | null) => {
    if (value) {
      setPasswordPolicy(value);
      if (value !== "custom") {
        setCustomRules({
          minLength: 8,
          requireUppercase: true,
          requireLowercase: true,
          requireDigit: true,
          requireSpecial: false,
          minStrength: 2,
        });
      }
    }
  };

  const handleRegistrationModeChange = (value: string | null) => {
    if (value !== null) {
      setRegistrationMode(parseInt(value, 10));
    }
  };

  const handleCustomRuleChange = (key: string, value: any) => {
    setCustomRules(prev => ({ ...prev, [key]: value }));
  };

  const handleSave = async () => {
    setIsSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      let policyCustom = null;
      if (passwordPolicy === "custom") {
        policyCustom = customRules;
      }

      const res = await apiFetch("/api/admin/global-settings", {
        method: "POST",
        body: JSON.stringify({
          emailSender,
          publicUrl,
          welcome,
          passwordPolicy,
          passwordPolicyCustom: policyCustom,
          registrationMode,
        }),
      });
      if (!res.ok) {
        const errorMsg = await getErrorMessage(translate, res, OPTIONS_SETTINGS.save_error);
        throw new Error(errorMsg);
      }
      const msg = translate(OPTIONS_SETTINGS.save_success);
      setSuccessMessage(msg);
      toast.success(msg);
    } catch (error: any) {
      const msg = error.message || translate(OPTIONS_SETTINGS.save_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsSaving(false);
    }
  };

  if (!isLanguageLoaded || isLoading || loadingRole) {
    return <div className="max-w-2xl mx-auto py-8">{translate(COMMON.loading)}</div>;
  }

  const isAdmin = userRole?.isAdmin === true;

  if (!isAdmin && !isExampleUser) {
    return <div className="max-w-2xl mx-auto py-8 text-center text-muted-foreground">{translate(COMMON.access_denied_admin)}</div>;
  }

  if (isExampleUser) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold">{translate(OPTIONS_SETTINGS.title)}</h1>
        <div className="p-6 bg-orange-50 border border-orange-200 rounded-md text-orange-800 text-center">
          <Lock className="h-10 w-10 mx-auto mb-3 text-orange-600" />
          <p className="text-sm mb-4">{translate(COMPONENTS.readonly_wrapper)}</p>
          <Link href="/register">
            <Button><UserPlus className="h-4 w-4 me-2" />{translate(COMPONENTS.example_user_banner.register_button)}</Button>
          </Link>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{translate(OPTIONS_SETTINGS.title)}</CardTitle>
            <CardDescription>{translate(OPTIONS_SETTINGS.description)}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 opacity-60">
            <div className="space-y-2">
              <Label>{translate(OPTIONS_SETTINGS.email_sender.label)}</Label>
              <Input dir="ltr" type="email" value={emailSender} disabled />
            </div>
            <div className="space-y-2">
              <Label>{translate(OPTIONS_SETTINGS.public_url.label)}</Label>
              <Input dir="ltr" type="url" value={publicUrl} disabled />
            </div>
            <div className="space-y-2">
              <Label>{translate(OPTIONS_SETTINGS.welcome.label)}</Label>
              <textarea dir="auto" value={welcome} disabled rows={4} className="w-full rounded-md border border-input bg-muted px-3 py-2 text-sm" />
            </div>
            <div className="space-y-2">
              <Label>{translate(OPTIONS_SETTINGS.password_policy.label)}</Label>
              <Select value={passwordPolicy} disabled>
                <SelectTrigger><SelectValue /></SelectTrigger>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{translate(OPTIONS_SETTINGS.registration_mode.label)}</Label>
              <Select value={String(registrationMode)} disabled>
                <SelectTrigger><SelectValue /></SelectTrigger>
              </Select>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">{translate(OPTIONS_SETTINGS.title)}</h1>

      {errorMessage && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 text-sm flex items-center justify-between">
          <span>{errorMessage}</span>
          <button onClick={dismissError} className="text-red-600 hover:text-red-800">&times;</button>
        </div>
      )}
      {successMessage && (
        <div className="p-3 bg-green-50 border border-green-200 rounded-md text-green-800 text-sm flex items-center justify-between">
          <span>{successMessage}</span>
          <button onClick={dismissSuccess} className="text-green-600 hover:text-green-800">&times;</button>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{translate(OPTIONS_SETTINGS.title)}</CardTitle>
          <CardDescription>{translate(OPTIONS_SETTINGS.description)}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Email Sender */}
          <div className="space-y-2">
            <Label>{translate(OPTIONS_SETTINGS.email_sender.label)}</Label>
            <Input dir="ltr"
              type="email"
              value={emailSender}
              onChange={(e) => setEmailSender(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">{translate(OPTIONS_SETTINGS.email_sender.hint)}</p>
          </div>

          {/* Public URL */}
          <div className="space-y-2">
            <Label>{translate(OPTIONS_SETTINGS.public_url.label)}</Label>
            <Input dir="ltr"
              type="url"
              value={publicUrl}
              onChange={(e) => setPublicUrl(e.target.value)}
            />
            <p className="text-xs text-muted-foreground">{translate(OPTIONS_SETTINGS.public_url.hint)}</p>
          </div>

          {/* Welcome Message */}
          <div className="space-y-2">
            <Label>{translate(OPTIONS_SETTINGS.welcome.label)}</Label>
            <textarea dir="auto"
              value={welcome}
              onChange={(e) => setWelcome(e.target.value)}
              rows={4}
              placeholder={translate(OPTIONS_SETTINGS.welcome.placeholder)}
              className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
            />
            <p className="text-xs text-muted-foreground">{translate(OPTIONS_SETTINGS.welcome.hint)}</p>
          </div>

          {/* Password Policy */}
          <div className="space-y-2">
            <Label>{translate(OPTIONS_SETTINGS.password_policy.label)}</Label>
            <Select value={passwordPolicy} onValueChange={handlePasswordPolicyChange}>
              <SelectTrigger>
                <SelectValue>
                  {(value: string) => {
                    const label = PASSWORD_POLICY_LABELS[value];
                    return label ? translate(label) : translate(OPTIONS_SETTINGS.password_policy.select);
                  }}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="low">{translate(OPTIONS_SETTINGS.password_policy.low)}</SelectItem>
                <SelectItem value="medium">{translate(OPTIONS_SETTINGS.password_policy.medium)}</SelectItem>
                <SelectItem value="high">{translate(OPTIONS_SETTINGS.password_policy.high)}</SelectItem>
                <SelectItem value="custom">{translate(OPTIONS_SETTINGS.password_policy.custom)}</SelectItem>
              </SelectContent>
            </Select>
            {passwordPolicy === "custom" && (
              <div className="space-y-2 mt-2 p-3 border rounded-md">
                <div className="flex items-center justify-between">
                  <span className="text-sm">{translate(OPTIONS_SETTINGS.password_policy.min_length)}</span>
                  <Input dir="ltr"
                    type="number"
                    value={customRules.minLength}
                    onChange={(e) => handleCustomRuleChange("minLength", parseInt(e.target.value) || 6)}
                    className="w-20 h-8 text-sm"
                    min="6"
                  />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">{translate(OPTIONS_SETTINGS.password_policy.require_uppercase)}</span>
                  <Switch checked={customRules.requireUppercase} onCheckedChange={(val) => handleCustomRuleChange("requireUppercase", val)} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">{translate(OPTIONS_SETTINGS.password_policy.require_lowercase)}</span>
                  <Switch checked={customRules.requireLowercase} onCheckedChange={(val) => handleCustomRuleChange("requireLowercase", val)} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">{translate(OPTIONS_SETTINGS.password_policy.require_digit)}</span>
                  <Switch checked={customRules.requireDigit} onCheckedChange={(val) => handleCustomRuleChange("requireDigit", val)} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">{translate(OPTIONS_SETTINGS.password_policy.require_special)}</span>
                  <Switch checked={customRules.requireSpecial} onCheckedChange={(val) => handleCustomRuleChange("requireSpecial", val)} />
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-sm">{translate(OPTIONS_SETTINGS.password_policy.min_strength)}</span>
                  <Input dir="ltr"
                    type="number"
                    value={customRules.minStrength}
                    onChange={(e) => handleCustomRuleChange("minStrength", parseInt(e.target.value) || 0)}
                    className="w-20 h-8 text-sm"
                    min="0"
                    max="4"
                  />
                </div>
              </div>
            )}
            <p className="text-xs text-muted-foreground">{translate(OPTIONS_SETTINGS.password_policy.hint)}</p>
          </div>

          {/* Registration Mode */}
          <div className="space-y-2">
            <Label>{translate(OPTIONS_SETTINGS.registration_mode.label)}</Label>
            <Select value={String(registrationMode)} onValueChange={handleRegistrationModeChange}>
              <SelectTrigger>
                <SelectValue>
                  {(value: string) => {
                    const label = REGISTRATION_MODE_LABELS[value];
                    return label ? translate(label) : translate(OPTIONS_SETTINGS.registration_mode.select);
                  }}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="0">{translate(OPTIONS_SETTINGS.registration_mode.mode_0)}</SelectItem>
                <SelectItem value="1">{translate(OPTIONS_SETTINGS.registration_mode.mode_1)}</SelectItem>
                <SelectItem value="2">{translate(OPTIONS_SETTINGS.registration_mode.mode_2)}</SelectItem>
                <SelectItem value="4">{translate(OPTIONS_SETTINGS.registration_mode.mode_4)}</SelectItem>
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">{translate(OPTIONS_SETTINGS.registration_mode.hint)}</p>
          </div>

          <div className="flex gap-3 pt-4">
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? translate(COMMON.saving) : translate(OPTIONS_SETTINGS.save_button)}
            </Button>
            <Button variant="outline" onClick={() => router.push("/")}>
              {translate(COMMON.cancel)}
            </Button>
          </div>
        </CardContent>
      </Card>
    </div>
  );
}
