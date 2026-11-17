// frontend/app/admin/setup/limits/page.tsx
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
import { useTranslate, getErrorMessage, getErrorMessageFromData, type TranslationKey } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { Lock, UserPlus } from "lucide-react";
import Link from "next/link";

import { LIMITS_SETTINGS } from "./translations";
import { COMMON } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";

export default function LimitsPage() {
  const router = useRouter();
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();

  const [demoMode, setDemoMode] = useState(false);
  const [maxRegistrations, setMaxRegistrations] = useState<string>("unlimited");
  const [defaultMaxUploadSizeMB, setDefaultMaxUploadSizeMB] = useState<string>("0");
  const [defaultMaxUploadCount, setDefaultMaxUploadCount] = useState<string>("0");
  const [emailVerificationTimeout, setEmailVerificationTimeout] = useState<string>("24");
  const [registrationGracePeriodHours, setRegistrationGracePeriodHours] = useState<string>("24");
  // The six AI tuning values moved to /admin/setup/tuning (plan Item 4b). They are
  // not here, and their state is not here, because this page posts every field it
  // holds: while both pages shared one endpoint, a save from here overwrote whatever
  // had been set there with this page's stale copy.
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

  const uploadSizeOptions = [
    { value: "0", label: LIMITS_SETTINGS.upload.size_unlimited },
    { value: "1", label: LIMITS_SETTINGS.upload.size_1_mb },
    { value: "5", label: LIMITS_SETTINGS.upload.size_5_mb },
    { value: "10", label: LIMITS_SETTINGS.upload.size_10_mb },
    { value: "25", label: LIMITS_SETTINGS.upload.size_25_mb },
    { value: "50", label: LIMITS_SETTINGS.upload.size_50_mb },
    { value: "100", label: LIMITS_SETTINGS.upload.size_100_mb },
    { value: "250", label: LIMITS_SETTINGS.upload.size_250_mb },
    { value: "500", label: LIMITS_SETTINGS.upload.size_500_mb },
    { value: "1024", label: LIMITS_SETTINGS.upload.size_1_gb },
  ];

  const uploadCountOptions = [
    { value: "0", label: LIMITS_SETTINGS.upload.count_unlimited },
    { value: "1", label: LIMITS_SETTINGS.upload.count_1 },
    { value: "5", label: LIMITS_SETTINGS.upload.count_5 },
    { value: "10", label: LIMITS_SETTINGS.upload.count_10 },
    { value: "25", label: LIMITS_SETTINGS.upload.count_25 },
    { value: "50", label: LIMITS_SETTINGS.upload.count_50 },
    { value: "100", label: LIMITS_SETTINGS.upload.count_100 },
    { value: "250", label: LIMITS_SETTINGS.upload.count_250 },
    { value: "500", label: LIMITS_SETTINGS.upload.count_500 },
    { value: "1000", label: LIMITS_SETTINGS.upload.count_1000 },
  ];

  // Base UI's Select.Value renders the raw value unless it is given children, so
  // each select resolves the same description its option list offers. A value set
  // outside the list (the API accepts any number) reads as itself, never as an
  // unset control; an empty one keeps the prompt the placeholder used to show.
  const registrationLimits = ["5", "10", "25", "50", "100", "250", "500", "1000"];

  const registrationLabel = (value: string) => {
    if (value === "unlimited") {
      return translate(LIMITS_SETTINGS.max_registrations.unlimited);
    }
    if (registrationLimits.includes(value)) {
      return `${value} ${translate(LIMITS_SETTINGS.max_registrations.users)}`;
    }
    return value || translate(LIMITS_SETTINGS.max_registrations.placeholder);
  };

  const optionLabel = (
    options: { value: string; label: TranslationKey }[],
    empty: TranslationKey,
    value: string,
  ) => {
    if (!value) return translate(empty);
    const option = options.find((opt) => opt.value === value);
    return option ? translate(option.label) : value;
  };

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
          const msg = await getErrorMessage(translate, res, LIMITS_SETTINGS.load_error);
          throw new Error(msg);
        }
        return res.json();
      })
      .then(data => {
        setDemoMode(data.demoMode ?? false);
        const max = data.maxRegistrations;
        setMaxRegistrations(max === null || max === undefined ? "unlimited" : max.toString());
        setEmailVerificationTimeout(data.emailVerificationTimeout?.toString() ?? "24");
        setRegistrationGracePeriodHours(data.registrationGracePeriodHours?.toString() ?? "24");
        setDefaultMaxUploadSizeMB(data.defaultMaxUploadSizeMB?.toString() ?? "0");
        setDefaultMaxUploadCount(data.defaultMaxUploadCount?.toString() ?? "0");
      })
      .catch((error: any) => {
        const msg = error.message || translate(LIMITS_SETTINGS.load_error);
        setErrorMessage(msg);
        toast.error(msg);
      })
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSave = async () => {
    setIsSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      let maxValue: number | null = null;
      if (maxRegistrations !== "unlimited") {
        const num = parseInt(maxRegistrations, 10);
        if (isNaN(num) || num < 1) {
          const msg = translate(LIMITS_SETTINGS.invalid_registration_max);
          setErrorMessage(msg);
          toast.error(msg);
          setIsSaving(false);
          return;
        }
        maxValue = num;
      }

      const timeoutValue = parseInt(emailVerificationTimeout, 10);
      if (isNaN(timeoutValue) || timeoutValue < 1) {
        const msg = translate(LIMITS_SETTINGS.invalid_timeout);
        setErrorMessage(msg);
        toast.error(msg);
        setIsSaving(false);
        return;
      }

      const graceValue = parseInt(registrationGracePeriodHours, 10);
      if (isNaN(graceValue) || graceValue < 1) {
        const msg = translate(LIMITS_SETTINGS.invalid_grace_period);
        setErrorMessage(msg);
        toast.error(msg);
        setIsSaving(false);
        return;
      }

      // The six AI tuning values are not validated here because they are not saved
      // here (plan Item 4b). Their fields, their validation and their POST all live
      // on /admin/setup/tuning, and this endpoint refuses them by name if a stale
      // client sends one.

      const res = await apiFetch("/api/admin/global-settings", {
        method: "POST",
        body: JSON.stringify({
          demoMode,
          maxRegistrations: maxValue,
          emailVerificationTimeout: timeoutValue,
          registrationGracePeriodHours: graceValue,
          defaultMaxUploadSizeMB: parseInt(defaultMaxUploadSizeMB, 10),
          defaultMaxUploadCount: parseInt(defaultMaxUploadCount, 10),
          // ONLY the fields this endpoint owns (plan Item 4b). Sending the six tuning
          // values here is what caused last-writer-wins between two pages; the endpoint
          // now refuses them, so this body must not name them.
        }),
      });
      if (!res.ok) {
        const errorMsg = await getErrorMessage(translate, res, LIMITS_SETTINGS.save_error);
        throw new Error(errorMsg);
      }
      const msg = translate(LIMITS_SETTINGS.save_success);
      setSuccessMessage(msg);
      toast.success(msg);
    } catch (error: any) {
      const msg = error.message || translate(LIMITS_SETTINGS.save_error);
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
        <h1 className="text-3xl font-bold">{translate(LIMITS_SETTINGS.title)}</h1>
        <div className="p-6 bg-orange-50 border border-orange-200 rounded-md text-orange-800 text-center">
          <Lock className="h-10 w-10 mx-auto mb-3 text-orange-600" />
          <p className="text-sm mb-4">{translate(COMPONENTS.readonly_wrapper)}</p>
          <Link href="/register">
            <Button><UserPlus className="h-4 w-4 me-2" />{translate(COMPONENTS.example_user_banner.register_button)}</Button>
          </Link>
        </div>
        <Card>
          <CardHeader>
            <CardTitle>{translate(LIMITS_SETTINGS.title)}</CardTitle>
            <CardDescription>{translate(LIMITS_SETTINGS.description)}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 opacity-60">
            <div className="flex items-center justify-between">
              <div>
                <Label>{translate(LIMITS_SETTINGS.demo_mode.label)}</Label>
                <p className="text-sm text-muted-foreground">{translate(LIMITS_SETTINGS.demo_mode.description)}</p>
              </div>
              <Switch checked={demoMode} disabled />
            </div>
            <div className="space-y-2">
              <Label>{translate(LIMITS_SETTINGS.max_registrations.label)}</Label>
              <Select value={maxRegistrations} disabled>
                <SelectTrigger>
                  <SelectValue>
                    {(value: string) => registrationLabel(value)}
                  </SelectValue>
                </SelectTrigger>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{translate(LIMITS_SETTINGS.email_timeout.label)}</Label>
              <Input dir="ltr" type="number" value={emailVerificationTimeout} disabled />
            </div>
            <div className="space-y-2">
              <Label>{translate(LIMITS_SETTINGS.grace_period.label)}</Label>
              <Input dir="ltr" type="number" value={registrationGracePeriodHours} disabled />
            </div>
            <div className="space-y-2">
              <Label>{translate(LIMITS_SETTINGS.upload.default_size_label)}</Label>
              <Select value={defaultMaxUploadSizeMB} disabled>
                <SelectTrigger>
                  <SelectValue>
                    {(value: string) => optionLabel(uploadSizeOptions, LIMITS_SETTINGS.upload.select_size, value)}
                  </SelectValue>
                </SelectTrigger>
              </Select>
            </div>
            <div className="space-y-2">
              <Label>{translate(LIMITS_SETTINGS.upload.default_count_label)}</Label>
              <Select value={defaultMaxUploadCount} disabled>
                <SelectTrigger>
                  <SelectValue>
                    {(value: string) => optionLabel(uploadCountOptions, LIMITS_SETTINGS.upload.select_count, value)}
                  </SelectValue>
                </SelectTrigger>
              </Select>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">{translate(LIMITS_SETTINGS.title)}</h1>

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
          <CardTitle>{translate(LIMITS_SETTINGS.title)}</CardTitle>
          <CardDescription>{translate(LIMITS_SETTINGS.description)}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          {/* Demo Mode */}
          <div className="flex items-center justify-between">
            <div>
              <Label>{translate(LIMITS_SETTINGS.demo_mode.label)}</Label>
              <p className="text-sm text-muted-foreground">{translate(LIMITS_SETTINGS.demo_mode.description)}</p>
            </div>
            <Switch checked={demoMode} onCheckedChange={setDemoMode} />
          </div>

          {/* Max Registrations */}
          <div className="space-y-2">
            <Label>{translate(LIMITS_SETTINGS.max_registrations.label)}</Label>
            <Select value={maxRegistrations} onValueChange={(v) => v && setMaxRegistrations(v)}>
              <SelectTrigger>
                <SelectValue>
                  {(value: string) => registrationLabel(value)}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="unlimited">{registrationLabel("unlimited")}</SelectItem>
                {registrationLimits.map((value) => (
                  <SelectItem key={value} value={value}>{registrationLabel(value)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">{translate(LIMITS_SETTINGS.max_registrations.hint)}</p>
          </div>

          {/* Email Verification Timeout */}
          <div className="space-y-2">
            <Label>{translate(LIMITS_SETTINGS.email_timeout.label)}</Label>
            <Input dir="ltr"
              type="number"
              value={emailVerificationTimeout}
              onChange={(e) => setEmailVerificationTimeout(e.target.value)}
              min="1"
            />
            <p className="text-xs text-muted-foreground">{translate(LIMITS_SETTINGS.email_timeout.hint)}</p>
          </div>

          {/* Registration Grace Period */}
          <div className="space-y-2">
            <Label>{translate(LIMITS_SETTINGS.grace_period.label)}</Label>
            <Input dir="ltr"
              type="number"
              value={registrationGracePeriodHours}
              onChange={(e) => setRegistrationGracePeriodHours(e.target.value)}
              min="1"
            />
            <p className="text-xs text-muted-foreground">{translate(LIMITS_SETTINGS.grace_period.hint)}</p>
          </div>

          {/* The six AI tuning values moved to /admin/setup/tuning (plan Item 4b).
              Everything remaining on this page is a cap on what a user may do; those
              six are how the AI behaves, and two pages posting to one endpoint made
              last-writer-wins a client-side discipline rather than an impossibility. */}

          {/* Default Max Upload Size */}
          <div className="space-y-2">
            <Label>{translate(LIMITS_SETTINGS.upload.default_size_label)}</Label>
            <Select value={defaultMaxUploadSizeMB} onValueChange={(v) => v && setDefaultMaxUploadSizeMB(v)}>
              <SelectTrigger>
                <SelectValue>
                  {(value: string) => optionLabel(uploadSizeOptions, LIMITS_SETTINGS.upload.select_size, value)}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {uploadSizeOptions.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>{translate(opt.label)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">{translate(LIMITS_SETTINGS.upload.size_hint)}</p>
          </div>

          {/* Default Max Upload Count */}
          <div className="space-y-2">
            <Label>{translate(LIMITS_SETTINGS.upload.default_count_label)}</Label>
            <Select value={defaultMaxUploadCount} onValueChange={(v) => v && setDefaultMaxUploadCount(v)}>
              <SelectTrigger>
                <SelectValue>
                  {(value: string) => optionLabel(uploadCountOptions, LIMITS_SETTINGS.upload.select_count, value)}
                </SelectValue>
              </SelectTrigger>
              <SelectContent>
                {uploadCountOptions.map((opt) => (
                  <SelectItem key={opt.value} value={opt.value}>{translate(opt.label)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
            <p className="text-xs text-muted-foreground">{translate(LIMITS_SETTINGS.upload.count_hint)}</p>
          </div>

          <div className="flex gap-3 pt-4">
            <Button onClick={handleSave} disabled={isSaving}>
              {isSaving ? translate(COMMON.saving) : translate(LIMITS_SETTINGS.save_button)}
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
