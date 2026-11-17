// frontend/app/settings/profile/page.tsx
"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { ProtectedRoute } from "@/components/protected-route";
import { useDarkMode } from "@/components/dark-mode-provider";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { Eye, EyeOff, Info, Loader2, Lock, UserPlus } from "lucide-react";
import { validatePassword, type PasswordPolicy } from "@/lib/password-validation";
import type { TranslationKey } from "@/lib/translation-helpers";
import { ExampleUserBadge } from "@/components/example-user-badge";
import { GroupAdminBadge } from "@/components/group-admin-badge";

// Import translations for this module
import { PROFILE_SETTINGS } from "./translations";
import { COMMON } from "@/app/common/translations";
import { PASSWORD_STRENGTH } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";

interface Language {
  code: string;
  name: string;
}

interface GroupInfo {
  userGroup: string;
  groupDescription: string;
}

interface UserRole {
  isAdmin: boolean;
  isGroupAdmin: boolean;
  isExampleUser: boolean;
}

function ProfileContent() {
  const router = useRouter();
  const { data: session, update } = useSession();
  const { darkMode, setDarkMode } = useDarkMode();
  const { isLanguageLoaded, setLanguage, language } = useTranslation();
  const translate = useTranslate();
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [emailNotifications, setEmailNotifications] = useState(false);
  const [selectedLanguage, setSelectedLanguage] = useState("en");
  const [languages, setLanguages] = useState<Language[]>([]);
  const [isLoading, setIsLoading] = useState(false);
  const [isLoadingSettings, setIsLoadingSettings] = useState(true);
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [isChangingPassword, setIsChangingPassword] = useState(false);
  const [showCurrentPassword, setShowCurrentPassword] = useState(false);
  const [showNewPassword, setShowNewPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);
  const [policy, setPolicy] = useState<PasswordPolicy | null>(null);
  const [passwordErrors, setPasswordErrors] = useState<TranslationKey[]>([]);
  const [passwordStrength, setPasswordStrength] = useState<{ score: number; feedback: string[] }>({ score: 0, feedback: [] });
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  // The slow-model threshold (plan Item 21): the user's own value (empty = inherit) and the
  // number actually in force. Two values, two questions — and the second is what makes an
  // empty first field honest rather than a hidden default.
  const [slowThresholdOwn, setSlowThresholdOwn] = useState<string>("");
  const [slowThresholdEffective, setSlowThresholdEffective] = useState<number | null>(null);
  const [savingThreshold, setSavingThreshold] = useState(false);
  // Persistent, not a toast: an error the user must act on stays until they act.
  const [thresholdError, setThresholdError] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  const [groupInfo, setGroupInfo] = useState<GroupInfo | null>(null);
  const [loadingGroupInfo, setLoadingGroupInfo] = useState(true);

  // User role for Example User detection
  const [userRole, setUserRole] = useState<UserRole | null>(null);
  const [loadingRole, setLoadingRole] = useState(true);

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  const isExampleUser = userRole?.isExampleUser === true;

  useEffect(() => {
    if (session?.user) {
      setName(session.user.name || "");
      setEmail(session.user.email || "");
    }
  }, [session]);

  useEffect(() => {
    const loadUserRole = async () => {
      try {
        const res = await apiFetch("/api/user/role");
        if (res.ok) {
          const data = await res.json();
          setUserRole(data);
        }
      } catch (error) {
        console.error("Failed to fetch user role:", error);
      } finally {
        setLoadingRole(false);
      }
    };
    loadUserRole();
  }, []);

  useEffect(() => {
    const loadSettings = async () => {
      try {
        const res = await apiFetch("/api/user-settings");
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
          const errorMsg = getErrorMessageFromData(translate, errorData, PROFILE_SETTINGS.load_error);
          throw new Error(errorMsg);
        }
        const data = await res.json();
        setEmailNotifications(data.emailNotifications ?? false);
        const savedLang = data.language || "en";
        setSelectedLanguage(savedLang);

        // The threshold, from the same response. Own is null when the user inherits, which is
        // why it renders as an empty field rather than the inherited number — the page must not
        // turn "inherit" into "pinned to 30".
        const ownThreshold = data.modelSlowThresholdSeconds;
        setSlowThresholdOwn(
          ownThreshold === null || ownThreshold === undefined ? "" : String(ownThreshold),
        );
        setSlowThresholdEffective(
          typeof data.modelSlowThresholdEffectiveSeconds === "number"
            ? data.modelSlowThresholdEffectiveSeconds
            : null,
        );
      } catch (error: any) {
        console.error("Failed to load settings:", error);
        const msg = error.message || translate(PROFILE_SETTINGS.load_error);
        setErrorMessage(msg);
        toast.error(msg);
      }
    };

    const loadLanguages = async () => {
      try {
        const res = await fetch(`/api/languages?viewer=${language}`);
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
          const errorMsg = getErrorMessageFromData(translate, errorData, PROFILE_SETTINGS.languages_load_error);
          throw new Error(errorMsg);
        }
        const data = await res.json();
        setLanguages(data);
      } catch (error: any) {
        console.error("Failed to load languages:", error);
        const msg = error.message || translate(PROFILE_SETTINGS.languages_load_error);
        setErrorMessage(msg);
        toast.error(msg);
      }
    };

    const loadGroupInfo = async () => {
      setLoadingGroupInfo(true);
      try {
        const res = await apiFetch(`/api/groups/user/me`);
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
          const errorMsg = getErrorMessageFromData(translate, errorData, PROFILE_SETTINGS.group_load_error);
          throw new Error(errorMsg);
        }
        const data = await res.json();
        setGroupInfo({
          userGroup: data.user_group,
          groupDescription: data.group_description,
        });
      } catch (error: any) {
        console.error("Failed to load group info:", error);
        const msg = error.message || translate(PROFILE_SETTINGS.group_load_error);
        setErrorMessage(msg);
        toast.error(msg);
      } finally {
        setLoadingGroupInfo(false);
      }
    };

    const loadAll = async () => {
      await loadSettings();
      await loadLanguages();

      // Try to load password policy - if not admin, use default medium policy
      try {
        const res = await apiFetch("/api/global-settings");
        if (res.ok) {
          const data = await res.json();
          setPolicy({
            policy: data.passwordPolicy || "medium",
            custom: data.passwordPolicyCustom || undefined,
          });
        } else {
          // If not authorized (403) or any other error, use default medium policy
          console.log("Using default password policy (admin access required for custom policy)");
          setPolicy({
            policy: "medium",
            custom: undefined,
          });
        }
      } catch (error) {
        console.error("Failed to load password policy:", error);
        // Use default medium policy as fallback
        setPolicy({
          policy: "medium",
          custom: undefined,
        });
      }

      if (session?.user?.id) {
        await loadGroupInfo();
      } else {
        setLoadingGroupInfo(false);
      }

      setIsLoadingSettings(false);
    };

    loadAll();
  }, [session?.user?.id]);

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

  const handleLanguageChange = (value: string | null) => {
    if (value) {
      setSelectedLanguage(value);
    }
  };

  const handleSave = async () => {
    setIsLoading(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const nameRes = await apiFetch("/api/user/profile", {
        method: "PATCH",
        body: JSON.stringify({ name }),
      });
      if (!nameRes.ok) {
        let errorData: any = {};
        try {
          const text = await nameRes.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, PROFILE_SETTINGS.update_error);
        throw new Error(errorMsg);
      }

      const settingsRes = await apiFetch("/api/user-settings", {
        method: "POST",
        body: JSON.stringify({ 
          emailNotifications, 
          language: selectedLanguage, 
          darkMode 
        }),
      });
      if (!settingsRes.ok) {
        let errorData: any = {};
        try {
          const text = await settingsRes.text();
          if (text) {
            errorData = JSON.parse(text);
          }
        } catch {
          // Use empty object
        }
        const errorMsg = getErrorMessageFromData(translate, errorData, PROFILE_SETTINGS.update_error);
        throw new Error(errorMsg);
      }

      setDarkMode(darkMode);
      await update();
      setLanguage(selectedLanguage);
      const msg = translate(PROFILE_SETTINGS.save_success);
      setSuccessMessage(msg);
      toast.success(msg);
    } catch (error: any) {
      const msg = error.message || translate(PROFILE_SETTINGS.save_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsLoading(false);
    }
  };

  const handleChangePassword = async () => {
    setErrorMessage(null);
    setSuccessMessage(null);

    if (isExampleUser) {
      const msg = translate(PROFILE_SETTINGS.password_disabled);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }

    if (newPassword !== confirmPassword) {
      const msg = translate(PROFILE_SETTINGS.password_mismatch);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }
    if (policy) {
      const result = validatePassword(newPassword, policy);
      if (!result.valid) {
        const msg = result.errors.map(e => translate(e)).join(" ");
        setErrorMessage(msg);
        toast.error(msg);
        return;
      }
    }
    if (!currentPassword) {
      const msg = translate(PROFILE_SETTINGS.current_password_required);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }

    setIsChangingPassword(true);
    try {
      const res = await apiFetch("/api/user/change-password", {
        method: "POST",
        body: JSON.stringify({ currentPassword, newPassword }),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, PROFILE_SETTINGS.password_change_failed);
        throw new Error(errorMsg);
      }
      const msg = translate(PROFILE_SETTINGS.password_changed);
      setSuccessMessage(msg);
      toast.success(msg);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setShowCurrentPassword(false);
      setShowNewPassword(false);
      setShowConfirmPassword(false);
    } catch (error: any) {
      const msg = error.message || translate(PROFILE_SETTINGS.password_change_failed);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setIsChangingPassword(false);
    }
  };

  const handleCancel = () => {
    router.push("/settings/profile");
  };

  const getStrengthLabel = (score: number) => {
    if (score === 0) return translate(PASSWORD_STRENGTH.weak);
    if (score === 1) return translate(PASSWORD_STRENGTH.weak);
    if (score === 2) return translate(PASSWORD_STRENGTH.fair);
    if (score === 3) return translate(PASSWORD_STRENGTH.good);
    if (score === 4) return translate(PASSWORD_STRENGTH.strong);
    return "";
  };

  const getLanguageName = (code: string) => {
    const lang = languages.find(l => l.code === code);
    return lang ? lang.name : code;
  };

  if (!isLanguageLoaded || isLoadingSettings || loadingGroupInfo || loadingRole) {
    return <div className="max-w-2xl mx-auto py-8">{translate(COMMON.loading)}</div>;
  }

  // Save the user's own limit. Empty means "inherit": the field is cleared on the server, not
  // set to the current effective value — those are different states, and the column's
  // nullability exists to tell them apart.
  async function saveThreshold() {
    setThresholdError(null);
    const trimmed = slowThresholdOwn.trim();

    if (trimmed !== "" && (!/^[0-9]+$/.test(trimmed) || Number(trimmed) < 1)) {
      setThresholdError(translate(PROFILE_SETTINGS.slow_threshold.invalid));
      return;
    }

    setSavingThreshold(true);
    try {
      const res = await apiFetch("/api/user-settings", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          modelSlowThresholdSeconds: trimmed === "" ? null : Number(trimmed),
        }),
      });
      if (!res.ok) {
        const data = await res.json().catch(() => ({}));
        setThresholdError(
          getErrorMessageFromData(translate, data, PROFILE_SETTINGS.slow_threshold.invalid),
        );
        return;
      }
      // Re-read, so the effective number reflects what the server resolved rather than what we
      // assumed it would.
      const after = await apiFetch("/api/user-settings");
      if (after.ok) {
        const data = await after.json();
        setSlowThresholdEffective(
          typeof data.modelSlowThresholdEffectiveSeconds === "number"
            ? data.modelSlowThresholdEffectiveSeconds
            : null,
        );
      }
      toast.success(translate(PROFILE_SETTINGS.slow_threshold.saved));
    } catch {
      setThresholdError(translate(PROFILE_SETTINGS.slow_threshold.invalid));
    } finally {
      setSavingThreshold(false);
    }
  }

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold flex items-center gap-2">
        {translate(PROFILE_SETTINGS.title)}
        <ExampleUserBadge />
        <GroupAdminBadge />
      </h1>

      {isExampleUser && (
        <div className="p-3 bg-orange-50 border border-orange-200 rounded-md text-orange-800 flex items-center gap-2">
          <Lock className="h-4 w-4" />
          <span className="text-sm">
            {translate(PROFILE_SETTINGS.password_disabled_message)}
          </span>
        </div>
      )}

      {errorMessage && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
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
        <div className="p-3 bg-green-50 border border-green-200 rounded-md text-green-800 flex items-center justify-between">
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

      <Card>
        <CardHeader>
          <CardTitle>{translate(PROFILE_SETTINGS.personal.title)}</CardTitle>
          <CardDescription>
            {translate(PROFILE_SETTINGS.personal.description)}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-6">
          <div className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="name">{translate(PROFILE_SETTINGS.name_label)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="auto"
                  id="name"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder={translate(PROFILE_SETTINGS.name_placeholder)}
                  required
                  disabled={isExampleUser}
                  className="flex-1"
                />
              </div>
              {isExampleUser && (
                <p className="text-xs text-muted-foreground">
                  {translate(PROFILE_SETTINGS.example_user_name_hint)}
                </p>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="email">{translate(PROFILE_SETTINGS.email_label)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="ltr"
                  id="email"
                  type="email"
                  value={email}
                  disabled
                  className="flex-1 bg-muted"
                />
              </div>
              <p className="text-xs text-muted-foreground">{translate(PROFILE_SETTINGS.email_unchangeable)}</p>
            </div>
          </div>

          <div className="border-t" />

          <div className="space-y-4">
            <div className="bg-muted/30 p-4 rounded-md border border-muted">
              <div className="flex items-center gap-2 text-sm font-medium text-muted-foreground mb-2">
                <Info className="h-4 w-4" />
                {translate(PROFILE_SETTINGS.group_info_title)}
              </div>
              <div className="grid grid-cols-2 gap-2 text-sm">
                <div>
                  <span className="text-muted-foreground">{translate(PROFILE_SETTINGS.group_id)}:</span>
                  <span className="ms-2 font-mono font-medium">{groupInfo?.userGroup || "—"}</span>
                </div>
                <div>
                  <span className="text-muted-foreground">{translate(PROFILE_SETTINGS.group_description)}:</span>
                  <span className="ms-2">{groupInfo?.groupDescription || "—"}</span>
                </div>
              </div>
              <p className="text-xs text-muted-foreground mt-2">
                {translate(PROFILE_SETTINGS.group_readonly_hint)}
              </p>
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label>{translate(PROFILE_SETTINGS.email_notifications_label)}</Label>
                <p className="text-sm text-muted-foreground">
                  {translate(PROFILE_SETTINGS.email_notifications_description)}
                </p>
              </div>
              <Switch
                checked={emailNotifications}
                onCheckedChange={setEmailNotifications}
                disabled={isExampleUser}
              />
            </div>
            {isExampleUser && (
              <p className="text-xs text-muted-foreground -mt-2">
                {translate(PROFILE_SETTINGS.example_user_notifications_hint)}
              </p>
            )}

            <div className="flex items-center justify-between">
              <div>
                <Label>{translate(PROFILE_SETTINGS.dark_mode_label)}</Label>
                <p className="text-sm text-muted-foreground">
                  {translate(PROFILE_SETTINGS.dark_mode_description)}
                </p>
              </div>
              <Switch
                checked={darkMode}
                onCheckedChange={setDarkMode}
                disabled={isExampleUser}
              />
            </div>
            {isExampleUser && (
              <p className="text-xs text-muted-foreground -mt-2">
                {translate(PROFILE_SETTINGS.example_user_theme_hint)}
              </p>
            )}

            <div className="space-y-2">
              <Label htmlFor="language">{translate(PROFILE_SETTINGS.language_label)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Select
                  value={selectedLanguage}
                  onValueChange={handleLanguageChange}
                  disabled={isExampleUser}
                >
                  <SelectTrigger className="w-[216px]">
                    <SelectValue placeholder={translate(PROFILE_SETTINGS.language_select_placeholder)}>
                      {getLanguageName(selectedLanguage)}
                    </SelectValue>
                  </SelectTrigger>
                  <SelectContent className="w-[216px]">
                    {languages.map((lang) => (
                      <SelectItem key={lang.code} value={lang.code}>
                        {lang.name}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <p className="text-xs text-muted-foreground">
                {translate(PROFILE_SETTINGS.language_description)}
              </p>
              {isExampleUser && (
                <p className="text-xs text-muted-foreground">
                  {translate(PROFILE_SETTINGS.example_user_language_hint)}
                </p>
              )}
            </div>
          </div>

          <div className="flex gap-4 pt-4">
            <Button onClick={handleSave} disabled={isLoading || isExampleUser}>
              {isLoading ? translate(COMMON.saving) : translate(PROFILE_SETTINGS.save_button)}
            </Button>
            {isExampleUser && (
              <p className="text-xs text-muted-foreground self-center ms-2">
                {translate(PROFILE_SETTINGS.example_user_save_hint)}
              </p>
            )}
            <Button variant="outline" onClick={handleCancel}>
              {translate(COMMON.cancel)}
            </Button>
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{translate(PROFILE_SETTINGS.slow_threshold.title)}</CardTitle>
          <CardDescription>
            {translate(PROFILE_SETTINGS.slow_threshold.description)}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="space-y-2">
            <Label htmlFor="slow-threshold">{translate(PROFILE_SETTINGS.slow_threshold.label)}</Label>
            <div className="flex items-center gap-2">
              <Input
                id="slow-threshold"
                type="number"
                min="1"
                step="1"
                className="max-w-[140px]"
                value={slowThresholdOwn}
                onChange={(e) => {
                  setSlowThresholdOwn(e.target.value);
                  // Clear the error as soon as the user edits: the message describes the
                  // value they are replacing, so leaving it up would describe the wrong thing.
                  setThresholdError(null);
                }}
                placeholder={translate(PROFILE_SETTINGS.slow_threshold.placeholder)}
              />
              <span className="text-sm text-muted-foreground">
                {translate(PROFILE_SETTINGS.slow_threshold.seconds)}
              </span>
              <Button onClick={saveThreshold} disabled={savingThreshold}>
                {savingThreshold ? <Loader2 className="h-4 w-4 animate-spin" /> : null}
                {translate(PROFILE_SETTINGS.slow_threshold.save)}
              </Button>
            </div>
            {/* The number in force. Present whether or not the field is filled, so an empty
                field never leaves the user guessing what applies. */}
            {slowThresholdEffective !== null && (
              <p className="text-sm text-muted-foreground">
                {translate(PROFILE_SETTINGS.slow_threshold.effective)}{" "}
                <span className="font-medium">{slowThresholdEffective}</span>{" "}
                {translate(PROFILE_SETTINGS.slow_threshold.seconds)}
              </p>
            )}
            {/* Persistent, per the project rule: an error the user must act on stays until
                they act. Not a toast alone. */}
            {thresholdError && (
              <p className="text-sm text-red-600" role="alert">
                {thresholdError}
              </p>
            )}
          </div>
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>{translate(PROFILE_SETTINGS.change_password.title)}</CardTitle>
          <CardDescription>
            {translate(PROFILE_SETTINGS.change_password.description)}
            {isExampleUser && " " + translate(PROFILE_SETTINGS.password_disabled)}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {isExampleUser ? (
            <div className="p-4 bg-muted/30 rounded-md border border-muted text-center">
              <Lock className="h-8 w-8 mx-auto text-muted-foreground mb-2" />
              <p className="text-sm text-muted-foreground">
                {translate(PROFILE_SETTINGS.password_disabled)}
              </p>
              <Button
                variant="outline"
                size="sm"
                className="mt-3"
                onClick={() => router.push("/register")}
              >
                <UserPlus className="h-4 w-4 me-2" />
                {translate(COMPONENTS.example_user_banner.register_button)}
              </Button>
            </div>
          ) : (
            <>
              <div className="space-y-2">
                <Label htmlFor="currentPassword">{translate(PROFILE_SETTINGS.current_password)}</Label>
                <div className="relative flex items-center">
                  <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                  <Input dir="ltr"
                    id="currentPassword"
                    type={showCurrentPassword ? "text" : "password"}
                    value={currentPassword}
                    onChange={(e) => setCurrentPassword(e.target.value)}
                    className="flex-1 pe-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowCurrentPassword(!showCurrentPassword)}
                    className="absolute inset-y-0 end-0 z-10 flex items-center pe-3 text-muted-foreground hover:text-foreground"
                    tabIndex={-1}
                  >
                    {showCurrentPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <div className="space-y-2">
                <Label htmlFor="newPassword">{translate(PROFILE_SETTINGS.new_password)}</Label>
                <div className="relative flex items-center">
                  <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                  <Input dir="ltr"
                    id="newPassword"
                    type={showNewPassword ? "text" : "password"}
                    value={newPassword}
                    onChange={(e) => setNewPassword(e.target.value)}
                    className="flex-1 pe-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowNewPassword(!showNewPassword)}
                    className="absolute inset-y-0 end-0 z-10 flex items-center pe-3 text-muted-foreground hover:text-foreground"
                    tabIndex={-1}
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
                <Label htmlFor="confirmPassword">{translate(PROFILE_SETTINGS.confirm_password)}</Label>
                <div className="relative flex items-center">
                  <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                  <Input dir="ltr"
                    id="confirmPassword"
                    type={showConfirmPassword ? "text" : "password"}
                    value={confirmPassword}
                    onChange={(e) => setConfirmPassword(e.target.value)}
                    className="flex-1 pe-10"
                  />
                  <button
                    type="button"
                    onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                    className="absolute inset-y-0 end-0 z-10 flex items-center pe-3 text-muted-foreground hover:text-foreground"
                    tabIndex={-1}
                  >
                    {showConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
              </div>

              <Button onClick={handleChangePassword} disabled={isChangingPassword}>
                {isChangingPassword ? translate(COMMON.saving) : translate(PROFILE_SETTINGS.change_password_button)}
              </Button>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

export default function ProfilePage() {
  return (
    <ProtectedRoute>
      <ProfileContent />
    </ProtectedRoute>
  );
}