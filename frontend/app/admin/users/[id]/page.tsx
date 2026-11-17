"use client";

import { useState, useEffect } from "react";
import { useRouter, useParams } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import type { TranslationKey } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { validatePassword, type PasswordPolicy } from "@/lib/password-validation";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, XCircle, Lock, UserPlus, Eye, EyeOff } from "lucide-react";
import Link from "next/link";

// Import translations for this module
import { ADMIN } from "../../translations";
import { COMMON, GLOBAL, PASSWORD_STRENGTH } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";
// The Set Password card's two password-field labels and its mismatch message are
// reused from the profile module rather than re-declared: the Translation table is
// keyed by the key string, so a second key carrying the same English text is drift
// — and the existing key is already translated.
import { PROFILE_SETTINGS } from "@/app/settings/profile/translations";

interface Language {
  code: string;
  name: string;
}

interface Group {
  groupId: string;
  groupDescription: string;
}

interface UserDetails {
  id: string;
  email: string;
  name: string | null;
  isAdmin: boolean;
  isGroupAdmin: boolean;
  userGroup: string;
  maxUploadSizeMB: number;
  maxUploadCount: number;
  emailNotifications: boolean;
  darkMode: boolean;
  language: string;
  defaultAIConnectionId: string | null;
}

const uploadSizeOptions = [
  { value: "0", label: GLOBAL.upload.size_unlimited },
  { value: "1", label: GLOBAL.upload.size_1_mb },
  { value: "5", label: GLOBAL.upload.size_5_mb },
  { value: "10", label: GLOBAL.upload.size_10_mb },
  { value: "25", label: GLOBAL.upload.size_25_mb },
  { value: "50", label: GLOBAL.upload.size_50_mb },
  { value: "100", label: GLOBAL.upload.size_100_mb },
  { value: "250", label: GLOBAL.upload.size_250_mb },
  { value: "500", label: GLOBAL.upload.size_500_mb },
  { value: "1024", label: GLOBAL.upload.size_1_gb },
];

const uploadCountOptions = [
  { value: "0", label: GLOBAL.upload.count_unlimited },
  { value: "1", label: GLOBAL.upload.count_1 },
  { value: "5", label: GLOBAL.upload.count_5 },
  { value: "10", label: GLOBAL.upload.count_10 },
  { value: "25", label: GLOBAL.upload.count_25 },
  { value: "50", label: GLOBAL.upload.count_50 },
  { value: "100", label: GLOBAL.upload.count_100 },
  { value: "250", label: GLOBAL.upload.count_250 },
  { value: "500", label: GLOBAL.upload.count_500 },
  { value: "1000", label: GLOBAL.upload.count_1000 },
];

function AdminUserDetailsContent() {
  const { isLanguageLoaded, language: viewerLanguage } = useTranslation();
  const translate = useTranslate();
  const router = useRouter();
  const params = useParams();
  const userId = params.id as string;

  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [user, setUser] = useState<UserDetails | null>(null);
  const [groups, setGroups] = useState<Group[]>([]);
  const [languages, setLanguages] = useState<Language[]>([]);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<{ isAdmin: boolean; isGroupAdmin: boolean; isExampleUser: boolean } | null>(null);
  const [loadingRole, setLoadingRole] = useState(true);

  // Editable fields
  const [emailNotifications, setEmailNotifications] = useState(false);
  const [darkMode, setDarkMode] = useState(false);
  const [language, setLanguage] = useState("en");
  const [maxUploadSizeMB, setMaxUploadSizeMB] = useState("0");
  const [maxUploadCount, setMaxUploadCount] = useState("0");
  const [userGroup, setUserGroup] = useState("00");
  const [isGroupAdmin, setIsGroupAdmin] = useState(false);

  // ---- Set Password card ----
  const [pwAdminPassword, setPwAdminPassword] = useState("");
  const [pwNewPassword, setPwNewPassword] = useState("");
  const [pwConfirmPassword, setPwConfirmPassword] = useState("");
  const [pwShowAdminPassword, setPwShowAdminPassword] = useState(false);
  const [pwShowNewPassword, setPwShowNewPassword] = useState(false);
  const [pwShowConfirmPassword, setPwShowConfirmPassword] = useState(false);
  const [pwSubmitting, setPwSubmitting] = useState(false);
  const [pwError, setPwError] = useState<string | null>(null);
  const [pwSuccess, setPwSuccess] = useState<string | null>(null);
  const [pwPolicy, setPwPolicy] = useState<PasswordPolicy | null>(null);
  const [pwRuleErrors, setPwRuleErrors] = useState<TranslationKey[]>([]);
  const [pwStrength, setPwStrength] = useState<{ score: number; feedback: string[] }>({ score: 0, feedback: [] });

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  const isExampleUser = userRole?.isExampleUser === true;
  const isAdmin = userRole?.isAdmin === true;

  // ---- Set Password card ----

  // The policy the card's live validation runs against. The profile page falls back
  // to "medium" when this call is refused; on this page the caller is a full admin,
  // so the call is expected to succeed and the fallback is only a guard.
  useEffect(() => {
    let cancelled = false;
    const loadPolicy = async () => {
      try {
        const res = await apiFetch("/api/global-settings");
        if (!res.ok) throw new Error("settings unavailable");
        const data = await res.json();
        if (!cancelled) {
          setPwPolicy({
            policy: data.passwordPolicy || "medium",
            custom: data.passwordPolicyCustom || undefined,
          });
        }
      } catch {
        if (!cancelled) setPwPolicy({ policy: "medium", custom: undefined });
      }
    };
    loadPolicy();
    return () => { cancelled = true; };
  }, []);

  // Live strength and rule feedback while the new password is typed.
  useEffect(() => {
    if (pwPolicy && pwNewPassword) {
      const result = validatePassword(pwNewPassword, pwPolicy);
      setPwRuleErrors(result.errors);
      setPwStrength({ score: result.score, feedback: result.feedback });
    } else {
      setPwRuleErrors([]);
      setPwStrength({ score: 0, feedback: [] });
    }
  }, [pwNewPassword, pwPolicy]);

  // A message — and a typed password — about one user must not follow to the next.
  useEffect(() => {
    setPwError(null);
    setPwSuccess(null);
    setPwAdminPassword("");
    setPwNewPassword("");
    setPwConfirmPassword("");
  }, [userId]);

  const getStrengthLabel = (score: number) => {
    if (score === 0) return translate(PASSWORD_STRENGTH.weak);
    if (score === 1) return translate(PASSWORD_STRENGTH.weak);
    if (score === 2) return translate(PASSWORD_STRENGTH.fair);
    if (score === 3) return translate(PASSWORD_STRENGTH.good);
    return translate(PASSWORD_STRENGTH.strong);
  };

  const handleSetPassword = async () => {
    setPwError(null);
    setPwSuccess(null);
    if (!user) return;

    if (!pwAdminPassword) {
      const msg = translate(ADMIN.set_password.admin_password_required);
      setPwError(msg);
      toast.error(msg);
      return;
    }
    if (pwNewPassword !== pwConfirmPassword) {
      const msg = translate(PROFILE_SETTINGS.password_mismatch);
      setPwError(msg);
      toast.error(msg);
      return;
    }
    if (pwPolicy) {
      const result = validatePassword(pwNewPassword, pwPolicy);
      if (!result.valid) {
        const msg = result.errors.map((e) => translate(e)).join(" ");
        setPwError(msg);
        toast.error(msg);
        return;
      }
    }

    setPwSubmitting(true);
    try {
      const res = await apiFetch("/api/admin/set-password", {
        method: "POST",
        body: JSON.stringify({
          adminPassword: pwAdminPassword,
          userEmail: user.email,
          newPassword: pwNewPassword,
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.set_password.failed);
        throw new Error(errorMsg);
      }
      const msg = translate(ADMIN.set_password.success);
      setPwSuccess(msg);
      toast.success(msg);
      setPwAdminPassword("");
      setPwNewPassword("");
      setPwConfirmPassword("");
    } catch (err: any) {
      const msg = err.message || translate(ADMIN.set_password.failed);
      setPwError(msg);
      toast.error(msg);
    } finally {
      setPwSubmitting(false);
    }
  };

  const getLanguageName = (code: string) => {
    const lang = languages.find(l => l.code === code);
    return lang ? lang.name : code;
  };

  const getGroupLabel = (groupId: string) => {
    const group = groups.find(g => g.groupId === groupId);
    return group ? `${groupId} - ${group.groupDescription}` : groupId;
  };

  const getUploadSizeLabel = (value: string) => {
    const opt = uploadSizeOptions.find(o => o.value === value);
    return opt ? translate(opt.label) : value;
  };

  const getUploadCountLabel = (value: string) => {
    const opt = uploadCountOptions.find(o => o.value === value);
    return opt ? translate(opt.label) : value;
  };

  useEffect(() => {
    const fetchUserRole = async () => {
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
    fetchUserRole();
  }, []);

  useEffect(() => {
    const fetchData = async () => {
      try {
        // Fetch languages
        const langRes = await fetch(`/api/languages?viewer=${viewerLanguage}`);
        if (langRes.ok) {
          const langData = await langRes.json();
          setLanguages(langData);
        }

        // Fetch groups
        const groupsRes = await apiFetch("/api/groups/");
        if (groupsRes.ok) {
          const groupsData = await groupsRes.json();
          setGroups(groupsData.groups || []);
        }

        // Fetch user details
        const userRes = await apiFetch(`/api/admin/users/${userId}`);
        if (!userRes.ok) {
          let errorData: any = {};
          try {
            const text = await userRes.text();
            if (text) {
              errorData = JSON.parse(text);
            }
          } catch {
            // Use empty object
          }
          const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.user_details.load_error);
          throw new Error(errorMsg);
        }
        const data = await userRes.json();
        setUser(data.user);
        setUserGroup(data.user.userGroup || "00");
        setEmailNotifications(data.user.emailNotifications ?? false);
        setDarkMode(data.user.darkMode ?? false);
        setLanguage(data.user.language ?? "en");
        setMaxUploadSizeMB(data.user.maxUploadSizeMB?.toString() ?? "0");
        setMaxUploadCount(data.user.maxUploadCount?.toString() ?? "0");
        setIsGroupAdmin(data.user.isGroupAdmin ?? false);
      } catch (error: any) {
        console.error(error);
        const msg = error.message || translate(ADMIN.user_details.load_error);
        setErrorMessage(msg);
        toast.error(msg);
      } finally {
        setLoading(false);
      }
    };
    if (userId) {
      fetchData();
    }
  }, [userId, translate]);

  const handleSave = async () => {
    setSaving(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await apiFetch(`/api/admin/users/${userId}`, {
        method: "PATCH",
        body: JSON.stringify({
          emailNotifications,
          darkMode,
          language,
          maxUploadSizeMB: parseInt(maxUploadSizeMB, 10),
          maxUploadCount: parseInt(maxUploadCount, 10),
          userGroup: userGroup,
          isGroupAdmin: isGroupAdmin,
        }),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.user_details.save_error);
        throw new Error(errorMsg);
      }

      const data = await res.json();
      
      // Update local state with the returned user data
      if (data.user) {
        setUser(data.user);
        setUserGroup(data.user.userGroup || "00");
        setEmailNotifications(data.user.emailNotifications ?? false);
        setDarkMode(data.user.darkMode ?? false);
        setLanguage(data.user.language ?? "en");
        setIsGroupAdmin(data.user.isGroupAdmin ?? false);
      }

      const msg = translate(ADMIN.user_details.save_success);
      setSuccessMessage(msg);
      toast.success(msg);
      
      // Refresh the page to ensure data is consistent
      router.refresh();
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.user_details.save_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setSaving(false);
    }
  };

  const handleCancel = () => {
    router.push("/admin");
  };

  if (loading || loadingRole) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  if (!user) {
    return (
      <div className="max-w-lg mx-auto py-12">
        <Card>
          <CardContent className="pt-6">
            <p className="text-center text-red-500">{translate(ADMIN.user_details.not_found)}</p>
            <Button className="mt-4 w-full" onClick={handleCancel}>
              {translate(COMMON.back)}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // If Example User, show read-only view
  if (isExampleUser) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold">{translate(ADMIN.user_details.title)}</h1>

        <div className="p-6 bg-orange-50 border border-orange-200 rounded-md text-orange-800 text-center">
          <Lock className="h-10 w-10 mx-auto mb-3 text-orange-600" />
          <p className="text-sm mb-4">
            {translate(COMPONENTS.readonly_wrapper)}
          </p>
          <Link href="/register">
            <Button>
              <UserPlus className="h-4 w-4 me-2" />
              {translate(COMPONENTS.example_user_banner.register_button)}
            </Button>
          </Link>
        </div>

        <Card>
          <CardHeader>
            <CardTitle>{user.name || translate(ADMIN.user_details.unnamed)}</CardTitle>
            <CardDescription>{user.email}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6 opacity-60">
            <div className="space-y-2">
              <Label>{translate(ADMIN.user_details.name_label)}</Label>
              <div className="text-sm text-muted-foreground">{user.name || "—"}</div>
            </div>
            <div className="space-y-2">
              <Label>{translate(ADMIN.user_details.email_label)}</Label>
              <div className="text-sm text-muted-foreground">{user.email}</div>
            </div>

            <div className="border-t pt-4" />

            <div className="space-y-2">
              <Label>{translate(ADMIN.user_details.user_group)}</Label>
              <Select value={userGroup} disabled>
                <SelectTrigger>
                  <SelectValue placeholder={translate(ADMIN.user_details.select_group)}>
                    {getGroupLabel(userGroup)}
                  </SelectValue>
                </SelectTrigger>
              </Select>
            </div>

            <div className="border-t pt-4" />

            <div className="flex items-center justify-between">
              <div>
                <Label>{translate(ADMIN.user_details.group_admin_label)}</Label>
                <p className="text-sm text-muted-foreground">
                  {translate(ADMIN.user_details.group_admin_description)}
                </p>
              </div>
              <Switch checked={isGroupAdmin} disabled />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label>{translate(ADMIN.user_details.email_notifications_label)}</Label>
                <p className="text-sm text-muted-foreground">
                  {translate(ADMIN.user_details.email_notifications_description)}
                </p>
              </div>
              <Switch checked={emailNotifications} disabled />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label>{translate(ADMIN.user_details.dark_mode_label)}</Label>
                <p className="text-sm text-muted-foreground">
                  {translate(ADMIN.user_details.dark_mode_description)}
                </p>
              </div>
              <Switch checked={darkMode} disabled />
            </div>

            <div className="space-y-2">
              <Label>{translate(ADMIN.user_details.language_label)}</Label>
              <Select value={language} disabled>
                <SelectTrigger>
                  <SelectValue placeholder={translate(ADMIN.user_details.language_select_placeholder)}>
                    {getLanguageName(language)}
                  </SelectValue>
                </SelectTrigger>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>{translate(ADMIN.user_details.max_upload_size_label)}</Label>
              <Select value={maxUploadSizeMB} disabled>
                <SelectTrigger>
                  <SelectValue placeholder={translate(ADMIN.user_details.max_upload_size_placeholder)}>
                    {getUploadSizeLabel(maxUploadSizeMB)}
                  </SelectValue>
                </SelectTrigger>
              </Select>
            </div>

            <div className="space-y-2">
              <Label>{translate(ADMIN.user_details.max_upload_count_label)}</Label>
              <Select value={maxUploadCount} disabled>
                <SelectTrigger>
                  <SelectValue placeholder={translate(ADMIN.user_details.max_upload_count_placeholder)}>
                    {getUploadCountLabel(maxUploadCount)}
                  </SelectValue>
                </SelectTrigger>
              </Select>
            </div>

            <div className="flex gap-4 pt-4">
              <Button disabled>
                {translate(COMMON.save)}
              </Button>
              <Button variant="outline" onClick={handleCancel}>
                {translate(COMMON.cancel)}
              </Button>
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Admin user - full access
  if (isAdmin) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold">{translate(ADMIN.user_details.title)}</h1>

        {/* Persistent Error/Success Messages */}
        {errorMessage && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
            <span className="text-sm">{errorMessage}</span>
            <button onClick={dismissError} className="text-red-500 hover:text-red-700">
              <XCircle className="h-5 w-5" />
            </button>
          </div>
        )}

        {successMessage && (
          <div className="p-3 bg-green-50 border border-green-200 rounded-md text-green-800 flex items-center justify-between">
            <span className="text-sm">{successMessage}</span>
            <button onClick={dismissSuccess} className="text-green-500 hover:text-green-700">
              <XCircle className="h-5 w-5" />
            </button>
          </div>
        )}

        <Card>
          <CardHeader>
            <CardTitle>{user.name || translate(ADMIN.user_details.unnamed)}</CardTitle>
            <CardDescription>{user.email}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-6">
            <div className="space-y-2">
              <Label>{translate(ADMIN.user_details.name_label)}</Label>
              <div className="text-sm text-muted-foreground">{user.name || "—"}</div>
            </div>
            <div className="space-y-2">
              <Label>{translate(ADMIN.user_details.email_label)}</Label>
              <div className="text-sm text-muted-foreground">{user.email}</div>
            </div>

            <div className="border-t pt-4" />

            <div className="space-y-2">
              <Label htmlFor="userGroup">{translate(ADMIN.user_details.user_group)}</Label>
              <Select value={userGroup} onValueChange={(value) => setUserGroup(value || "00")}>
                <SelectTrigger id="userGroup">
                  <SelectValue placeholder={translate(ADMIN.user_details.select_group)}>
                    {getGroupLabel(userGroup)}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent className="max-h-60">
                  {groups.map((group) => (
                    <SelectItem key={group.groupId} value={group.groupId}>
                      {group.groupId} - {group.groupDescription}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {translate(ADMIN.user_details.group_hint)}
              </p>
            </div>

            <div className="border-t pt-4" />

            <div className="flex items-center justify-between">
              <div>
                <Label>{translate(ADMIN.user_details.group_admin_label)}</Label>
                <p className="text-sm text-muted-foreground">
                  {translate(ADMIN.user_details.group_admin_description)}
                </p>
              </div>
              <Switch
                checked={isGroupAdmin}
                onCheckedChange={(checked) => setIsGroupAdmin(checked)}
                disabled={user.isAdmin}
              />
            </div>
            {user.isAdmin && (
              <p className="text-xs text-amber-600">
                {translate(ADMIN.user_details.full_admin_note)}
              </p>
            )}

            <div className="flex items-center justify-between">
              <div>
                <Label>{translate(ADMIN.user_details.email_notifications_label)}</Label>
                <p className="text-sm text-muted-foreground">
                  {translate(ADMIN.user_details.email_notifications_description)}
                </p>
              </div>
              <Switch checked={emailNotifications} onCheckedChange={setEmailNotifications} />
            </div>

            <div className="flex items-center justify-between">
              <div>
                <Label>{translate(ADMIN.user_details.dark_mode_label)}</Label>
                <p className="text-sm text-muted-foreground">
                  {translate(ADMIN.user_details.dark_mode_description)}
                </p>
              </div>
              <Switch checked={darkMode} onCheckedChange={setDarkMode} />
            </div>

            <div className="space-y-2">
              <Label htmlFor="language">{translate(ADMIN.user_details.language_label)}</Label>
              <Select value={language} onValueChange={(value) => setLanguage(value || "en")}>
                <SelectTrigger id="language" className="w-[216px]">
                  <SelectValue placeholder={translate(ADMIN.user_details.language_select_placeholder)}>
                    {getLanguageName(language)}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent className="min-w-[216px]">
                  {languages.map((lang) => (
                    <SelectItem key={lang.code} value={lang.code}>
                      {lang.name}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>

            <div className="space-y-2">
              <Label htmlFor="maxUploadSizeMB">{translate(ADMIN.user_details.max_upload_size_label)}</Label>
              <Select value={maxUploadSizeMB} onValueChange={(value) => setMaxUploadSizeMB(value || "0")}>
                <SelectTrigger id="maxUploadSizeMB">
                  <SelectValue placeholder={translate(ADMIN.user_details.max_upload_size_placeholder)}>
                    {getUploadSizeLabel(maxUploadSizeMB)}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {uploadSizeOptions.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {translate(opt.label)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {translate(ADMIN.user_details.max_upload_size_hint)}
              </p>
            </div>

            <div className="space-y-2">
              <Label htmlFor="maxUploadCount">{translate(ADMIN.user_details.max_upload_count_label)}</Label>
              <Select value={maxUploadCount} onValueChange={(value) => setMaxUploadCount(value || "0")}>
                <SelectTrigger id="maxUploadCount">
                  <SelectValue placeholder={translate(ADMIN.user_details.max_upload_count_placeholder)}>
                    {getUploadCountLabel(maxUploadCount)}
                  </SelectValue>
                </SelectTrigger>
                <SelectContent>
                  {uploadCountOptions.map(opt => (
                    <SelectItem key={opt.value} value={opt.value}>
                      {translate(opt.label)}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <p className="text-xs text-muted-foreground">
                {translate(ADMIN.user_details.max_upload_count_hint)}
              </p>
            </div>

            <div className="flex gap-4 pt-4">
              <Button onClick={handleSave} disabled={saving}>
                {saving ? translate(COMMON.saving) : translate(COMMON.save)}
              </Button>
              <Button variant="outline" onClick={handleCancel}>
                {translate(COMMON.cancel)}
              </Button>
            </div>
          </CardContent>
        </Card>

        {/* Set Password — modelled on the Change Password card on /settings/profile */}
        <Card>
          <CardHeader>
            <CardTitle>{translate(ADMIN.set_password.title)}</CardTitle>
            <CardDescription>{translate(ADMIN.set_password.description)}</CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="adminPassword">
                <span className="bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full text-[11px] font-semibold">
                  {translate(ADMIN.set_password.admin_password)}
                </span>
              </Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="ltr"
                  id="adminPassword"
                  type={pwShowAdminPassword ? "text" : "password"}
                  value={pwAdminPassword}
                  onChange={(e) => setPwAdminPassword(e.target.value)}
                  className="flex-1 pe-10"
                />
                <button
                  type="button"
                  onClick={() => setPwShowAdminPassword(!pwShowAdminPassword)}
                  className="absolute inset-y-0 end-0 z-10 flex items-center pe-3 text-muted-foreground hover:text-foreground"
                  tabIndex={-1}
                >
                  {pwShowAdminPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            <div className="space-y-2">
              <Label htmlFor="setNewPassword">{translate(PROFILE_SETTINGS.new_password)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="ltr"
                  id="setNewPassword"
                  type={pwShowNewPassword ? "text" : "password"}
                  value={pwNewPassword}
                  onChange={(e) => setPwNewPassword(e.target.value)}
                  className="flex-1 pe-10"
                />
                <button
                  type="button"
                  onClick={() => setPwShowNewPassword(!pwShowNewPassword)}
                  className="absolute inset-y-0 end-0 z-10 flex items-center pe-3 text-muted-foreground hover:text-foreground"
                  tabIndex={-1}
                >
                  {pwShowNewPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
              {pwNewPassword && (
                <div className="space-y-1 mt-1">
                  <div className="flex items-center gap-2">
                    <div className="flex-1 h-2 bg-muted rounded-full overflow-hidden">
                      <div
                        className="h-full transition-all duration-300"
                        style={{
                          width: `${(pwStrength.score / 4) * 100}%`,
                          backgroundColor:
                            pwStrength.score < 2 ? "#ef4444" :
                            pwStrength.score < 3 ? "#f59e0b" :
                            "#22c55e",
                        }}
                      />
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {getStrengthLabel(pwStrength.score)}
                    </span>
                  </div>
                  {pwStrength.feedback.length > 0 && (
                    <ul className="text-xs text-muted-foreground list-disc ps-4">
                      {pwStrength.feedback.map((msg, i) => (
                        <li key={i}>{msg}</li>
                      ))}
                    </ul>
                  )}
                  {pwRuleErrors.length > 0 && (
                    <ul className="text-xs text-red-500 list-disc ps-4">
                      {pwRuleErrors.map((err, i) => (
                        <li key={i}>{translate(err)}</li>
                      ))}
                    </ul>
                  )}
                </div>
              )}
            </div>

            <div className="space-y-2">
              <Label htmlFor="setConfirmPassword">{translate(PROFILE_SETTINGS.confirm_password)}</Label>
              <div className="relative flex items-center">
                <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                <Input dir="ltr"
                  id="setConfirmPassword"
                  type={pwShowConfirmPassword ? "text" : "password"}
                  value={pwConfirmPassword}
                  onChange={(e) => setPwConfirmPassword(e.target.value)}
                  className="flex-1 pe-10"
                />
                <button
                  type="button"
                  onClick={() => setPwShowConfirmPassword(!pwShowConfirmPassword)}
                  className="absolute inset-y-0 end-0 z-10 flex items-center pe-3 text-muted-foreground hover:text-foreground"
                  tabIndex={-1}
                >
                  {pwShowConfirmPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                </button>
              </div>
            </div>

            {/* Persistent feedback, inside the card that triggered it. The page's own
                banners above stay with the page's other actions. */}
            {pwError && (
              <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
                <span className="text-sm">{pwError}</span>
                <button
                  onClick={() => setPwError(null)}
                  className="text-red-500 hover:text-red-700"
                  aria-label={translate(COMMON.dismiss)}
                >
                  <XCircle className="h-5 w-5" />
                </button>
              </div>
            )}

            {pwSuccess && (
              <div className="p-3 bg-green-50 border border-green-200 rounded-md text-green-800 flex items-center justify-between">
                <span className="text-sm">{pwSuccess}</span>
                <button
                  onClick={() => setPwSuccess(null)}
                  className="text-green-500 hover:text-green-700"
                  aria-label={translate(COMMON.dismiss)}
                >
                  <XCircle className="h-5 w-5" />
                </button>
              </div>
            )}

            <Button onClick={handleSetPassword} disabled={pwSubmitting}>
              {pwSubmitting ? translate(COMMON.saving) : translate(ADMIN.set_password.title)}
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Non-admin users - redirect or show access denied
  return (
    <div className="max-w-lg mx-auto py-12">
      <Card>
        <CardContent className="pt-6">
          <p className="text-center text-red-500">
            {translate(COMMON.no_permission)}
          </p>
          <Button className="mt-4 w-full" onClick={handleCancel}>
            {translate(COMMON.back)}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default function AdminUserDetailsPage() {
  return (
    <ProtectedRoute>
      <AdminUserDetailsContent />
    </ProtectedRoute>
  );
}