// frontend/app/admin/setup/tuning/page.tsx
//
// The AI tuning defaults (plan Item 4b of workbench-AI-timeout-policy-plan.html).
//
// WHAT THIS PAGE IS, AND WHY IT IS NOT ON THE LIMITS PAGE
//
// Everything on /admin/setup/limits is a cap on what a user may do. These six are
// how the AI behaves: the slow-model threshold, temperature, maximum output tokens,
// maximum AI time, and the connection and model-test timeouts. Putting them together
// made one page answer two questions.
//
// AND THE REASON THE ENDPOINTS HAD TO SPLIT WITH THEM. The limits page posts every
// field it holds on every save. While both pages shared POST /api/admin/global-settings,
// a save from Limits overwrote whatever had been set here with the stale copy in its
// own state — last writer wins, silently, with a success toast. Two endpoints make
// that impossible: this page posts to /api/admin/tuning, which accepts only these six,
// and the limits endpoint refuses any of them by name.
//
// THE PREAMBLE IS NOT DECORATION. These values are usually right as they are, and an
// administrator who does not know that will "tune" without a reason. It also says what
// these are NOT: a per-user or per-connection setting can differ, so the global is a
// default rather than a ceiling.
"use client";

import { useState, useEffect, useRef } from "react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { Input } from "@/components/ui/input";
import { toast } from "sonner";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessage } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { RotateCcw } from "lucide-react";

import { TUNING_SETTINGS } from "./translations";
// The error text comes from lib/translation-helpers, not from a local copy. There WAS
// a local copy here, and it is how a Next.js 404 page ended up rendered in the error
// banner: its non-JSON branch returned the raw body. The shared helper had the same
// flaw and is now fixed, so one implementation serves every page.
import { COMMON, NAV } from "@/app/common/translations";

export default function TuningSettingsPage() {
    const { isLanguageLoaded } = useTranslation();
    const translate = useTranslate();

    // Strings, like every numeric field on the limits page: a half-typed value stays
    // visible in the box instead of being coerced on every keystroke.
    const [defaultModelTestSeconds, setDefaultModelTestSeconds] = useState<string>("30");
    const [aiTemperature, setAiTemperature] = useState<string>("0.7");
    const [aiMaxTokens, setAiMaxTokens] = useState<string>("4000");
    const [aiTimeoutSeconds, setAiTimeoutSeconds] = useState<string>("120");
    const [defaultConnectTimeout, setDefaultConnectTimeout] = useState<string>("10");
    const [defaultProbeTimeout, setDefaultProbeTimeout] = useState<string>("300");

    const [isLoading, setIsLoading] = useState(true);
    const [isSaving, setIsSaving] = useState(false);
    const [isResetting, setIsResetting] = useState(false);
    const [confirmReset, setConfirmReset] = useState(false);
    const [errorMessage, setErrorMessage] = useState<string | null>(null);
    const [successMessage, setSuccessMessage] = useState<string | null>(null);
    const [userRole, setUserRole] = useState<{ isAdmin: boolean; isGroupAdmin: boolean; isExampleUser: boolean } | null>(null);
    const [loadingRole, setLoadingRole] = useState(true);
    const initialFetchDone = useRef(false);

    useEffect(() => {
        apiFetch("/api/user/role")
            .then(res => (res.ok ? res.json() : null))
            .then(data => { if (data) setUserRole(data); })
            .catch(() => {})
            .finally(() => setLoadingRole(false));
    }, []);

    useEffect(() => {
        if (initialFetchDone.current) return;
        initialFetchDone.current = true;
        setErrorMessage(null);
        // GET still returns every column (the read tuple is whole), so this page reads
        // the six it owns out of the same response the limits page reads.
        apiFetch("/api/global-settings")
            .then(async res => {
                if (!res.ok) {
                    const msg = await getErrorMessage(translate, res, TUNING_SETTINGS.load_error);
                    throw new Error(msg);
                }
                return res.json();
            })
            .then(data => {
                setDefaultModelTestSeconds(data.defaultModelTestSeconds?.toString() ?? "30");
                setAiTemperature(data.temperature?.toString() ?? "0.7");
                setAiMaxTokens(data.maxTokens?.toString() ?? "4000");
                setAiTimeoutSeconds(data.timeoutSeconds?.toString() ?? "120");
                setDefaultConnectTimeout(data.defaultConnectTimeoutSeconds?.toString() ?? "10");
                setDefaultProbeTimeout(data.defaultProbeTimeoutSeconds?.toString() ?? "300");
            })
            .catch((error: unknown) => {
                const msg = error instanceof Error
                    ? error.message
                    : translate(TUNING_SETTINGS.load_error);
                setErrorMessage(msg);
                toast.error(msg);
            })
            .finally(() => setIsLoading(false));
        // eslint-disable-next-line react-hooks/exhaustive-deps
    }, []);

    const isExampleUser = userRole?.isExampleUser === true;

    const handleSave = async () => {
        setIsSaving(true);
        setErrorMessage(null);
        setSuccessMessage(null);
        try {
            // Validate, don't coerce — and never disable the button. Each field is
            // checked for a whole number in its range, and the first failure names
            // itself. The backend refuses independently; this is the earlier answer.
            const testSeconds = Number(defaultModelTestSeconds);
            if (
                defaultModelTestSeconds.trim() === "" ||
                !/^[0-9]+$/.test(defaultModelTestSeconds.trim()) ||
                !Number.isInteger(testSeconds) ||
                testSeconds < 1
            ) {
                const msg = translate(TUNING_SETTINGS.invalid_model_test_seconds);
                setErrorMessage(msg);
                toast.error(msg);
                return;
            }

            const temperatureValue = Number(aiTemperature);
            if (
                aiTemperature.trim() === "" ||
                !Number.isFinite(temperatureValue) ||
                temperatureValue < 0 ||
                temperatureValue > 2
            ) {
                const msg = translate(TUNING_SETTINGS.invalid_temperature);
                setErrorMessage(msg);
                toast.error(msg);
                return;
            }

            const maxTokensValue = Number(aiMaxTokens);
            if (
                aiMaxTokens.trim() === "" ||
                !/^[0-9]+$/.test(aiMaxTokens.trim()) ||
                !Number.isInteger(maxTokensValue) ||
                maxTokensValue < 1
            ) {
                const msg = translate(TUNING_SETTINGS.invalid_max_tokens);
                setErrorMessage(msg);
                toast.error(msg);
                return;
            }

            const aiTimeoutValue = Number(aiTimeoutSeconds);
            if (
                aiTimeoutSeconds.trim() === "" ||
                !/^[0-9]+$/.test(aiTimeoutSeconds.trim()) ||
                !Number.isInteger(aiTimeoutValue) ||
                aiTimeoutValue < 1
            ) {
                const msg = translate(TUNING_SETTINGS.invalid_ai_timeout);
                setErrorMessage(msg);
                toast.error(msg);
                return;
            }

            const connectTimeoutValue = Number(defaultConnectTimeout);
            if (
                defaultConnectTimeout.trim() === "" ||
                !/^[0-9]+$/.test(defaultConnectTimeout.trim()) ||
                !Number.isInteger(connectTimeoutValue) ||
                connectTimeoutValue < 1 ||
                connectTimeoutValue > 60
            ) {
                const msg = translate(TUNING_SETTINGS.invalid_connect_timeout);
                setErrorMessage(msg);
                toast.error(msg);
                return;
            }

            const probeTimeoutValue = Number(defaultProbeTimeout);
            if (
                defaultProbeTimeout.trim() === "" ||
                !/^[0-9]+$/.test(defaultProbeTimeout.trim()) ||
                !Number.isInteger(probeTimeoutValue) ||
                probeTimeoutValue < 1 ||
                probeTimeoutValue > 1200
            ) {
                const msg = translate(TUNING_SETTINGS.invalid_probe_timeout);
                setErrorMessage(msg);
                toast.error(msg);
                return;
            }

            const res = await apiFetch("/api/admin/tuning", {
                method: "POST",
                body: JSON.stringify({
                    defaultModelTestSeconds: testSeconds,
                    temperature: temperatureValue,
                    maxTokens: maxTokensValue,
                    timeoutSeconds: aiTimeoutValue,
                    defaultConnectTimeoutSeconds: connectTimeoutValue,
                    defaultProbeTimeoutSeconds: probeTimeoutValue,
                }),
            });
            if (!res.ok) {
                const msg = await getErrorMessage(translate, res, TUNING_SETTINGS.save_error);
                throw new Error(msg);
            }
            const msg = translate(TUNING_SETTINGS.saved);
            setSuccessMessage(msg);
            toast.success(msg);
        } catch (error: unknown) {
            const msg = error instanceof Error
                ? error.message
                : translate(TUNING_SETTINGS.save_error);
            setErrorMessage(msg);
            toast.error(msg);
        } finally {
            setIsSaving(false);
        }
    };

    const handleReset = async () => {
        setIsResetting(true);
        setErrorMessage(null);
        setSuccessMessage(null);
        setConfirmReset(false);
        try {
            // The backend writes SET col = DEFAULT for all six in one statement, so
            // there is nothing to send: the DDL is the authority, and a future change
            // to a default is a migration this follows automatically.
            const res = await apiFetch("/api/admin/tuning/reset", { method: "POST" });
            if (!res.ok) {
                const msg = await getErrorMessage(translate, res, TUNING_SETTINGS.reset_error);
                throw new Error(msg);
            }
            // Read the reset values back rather than assuming what the DDL holds.
            const fresh = await apiFetch("/api/global-settings");
            if (fresh.ok) {
                const data = await fresh.json();
                setDefaultModelTestSeconds(data.defaultModelTestSeconds?.toString() ?? "30");
                setAiTemperature(data.temperature?.toString() ?? "0.7");
                setAiMaxTokens(data.maxTokens?.toString() ?? "4000");
                setAiTimeoutSeconds(data.timeoutSeconds?.toString() ?? "120");
                setDefaultConnectTimeout(data.defaultConnectTimeoutSeconds?.toString() ?? "10");
                setDefaultProbeTimeout(data.defaultProbeTimeoutSeconds?.toString() ?? "300");
            }
            const msg = translate(TUNING_SETTINGS.reset_done);
            setSuccessMessage(msg);
            toast.success(msg);
        } catch (error: unknown) {
            const msg = error instanceof Error
                ? error.message
                : translate(TUNING_SETTINGS.reset_error);
            setErrorMessage(msg);
            toast.error(msg);
        } finally {
            setIsResetting(false);
        }
    };

    if (!isLanguageLoaded || isLoading || loadingRole) {
        return <div className="max-w-2xl mx-auto py-8">{translate(COMMON.loading)}</div>;
    }

    const isAdmin = userRole?.isAdmin === true;

    if (!isAdmin && !isExampleUser) {
        return <div className="max-w-2xl mx-auto py-8 text-center text-muted-foreground">{translate(COMMON.access_denied_admin)}</div>;
    }

    // An example user sees the values and can change none of them. Per
    // validate-don't-suppress the controls stay enabled and the save is refused with
    // the message below — a disabled form would tell them nothing about why.
    const handleExampleAttempt = () => {
        const msg = translate(TUNING_SETTINGS.forbidden);
        setErrorMessage(msg);
        toast.error(msg);
    };

    return (
        <div className="max-w-2xl mx-auto space-y-6">
            <div>
                <h1 className="text-3xl font-bold">{translate(NAV.admin_setup_tuning)}</h1>
                <p className="text-muted-foreground mt-2">{translate(TUNING_SETTINGS.description)}</p>
                <p className="text-sm text-muted-foreground mt-2">{translate(TUNING_SETTINGS.preamble_detail)}</p>
            </div>

            {errorMessage && (
                <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 text-sm">
                    {errorMessage}
                </div>
            )}
            {successMessage && (
                <div className="p-3 bg-green-50 border border-green-200 rounded-md text-green-800 text-sm">
                    {successMessage}
                </div>
            )}

            <Card>
                <CardHeader>
                    <CardTitle>{translate(NAV.admin_setup_tuning)}</CardTitle>
                    <CardDescription>{translate(TUNING_SETTINGS.description)}</CardDescription>
                </CardHeader>
                <CardContent className="space-y-6">
                    {/* Slow-model threshold — not a timeout */}
                    <div className="space-y-2">
                        <Label>{translate(TUNING_SETTINGS.slow_threshold_label)}</Label>
                        <div className="flex items-center gap-2">
                            <Input
                                dir="ltr"
                                type="number"
                                value={defaultModelTestSeconds}
                                onChange={(e) => setDefaultModelTestSeconds(e.target.value)}
                                min="1"
                                step="1"
                                className="max-w-[140px]"
                            />
                            <span className="text-sm text-muted-foreground">
                                {translate(TUNING_SETTINGS.seconds)}
                            </span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                            {translate(TUNING_SETTINGS.slow_threshold_hint)}
                        </p>
                    </div>

                    {/* AI generation */}
                    <div className="pt-2">
                        <h3 className="text-sm font-semibold">{translate(TUNING_SETTINGS.ai_section_label)}</h3>
                        <p className="text-xs text-muted-foreground mt-1">{translate(TUNING_SETTINGS.ai_section_hint)}</p>
                    </div>

                    <div className="space-y-2">
                        <Label>{translate(COMMON.ai_temperature_label)}</Label>
                        <Input
                            dir="ltr"
                            type="number"
                            value={aiTemperature}
                            onChange={(e) => setAiTemperature(e.target.value)}
                            min="0"
                            max="2"
                            step="0.1"
                            className="max-w-[140px]"
                        />
                        <p className="text-xs text-muted-foreground">{translate(TUNING_SETTINGS.ai_temperature_hint)}</p>
                    </div>

                    <div className="space-y-2">
                        <Label>{translate(COMMON.ai_max_tokens_label)}</Label>
                        <div className="flex items-center gap-2">
                            <Input
                                dir="ltr"
                                type="number"
                                value={aiMaxTokens}
                                onChange={(e) => setAiMaxTokens(e.target.value)}
                                min="1"
                                step="1"
                                className="max-w-[140px]"
                            />
                            <span className="text-sm text-muted-foreground">{translate(TUNING_SETTINGS.ai_tokens)}</span>
                        </div>
                        <p className="text-xs text-muted-foreground">{translate(TUNING_SETTINGS.ai_max_tokens_hint)}</p>
                    </div>

                    <div className="space-y-2">
                        <Label>{translate(COMMON.ai_timeout_label)}</Label>
                        <div className="flex items-center gap-2">
                            <Input
                                dir="ltr"
                                type="number"
                                value={aiTimeoutSeconds}
                                onChange={(e) => setAiTimeoutSeconds(e.target.value)}
                                min="1"
                                step="1"
                                className="max-w-[140px]"
                            />
                            <span className="text-sm text-muted-foreground">
                                {translate(TUNING_SETTINGS.seconds)}
                            </span>
                        </div>
                        <p className="text-xs text-muted-foreground">{translate(TUNING_SETTINGS.ai_timeout_hint)}</p>
                    </div>

                    {/* The two connection timeouts. Their LABELS are shared with the
                        per-connection form, so they come from COMMON. */}
                    <div className="space-y-2">
                        <Label>{translate(COMMON.connect_timeout_label)}</Label>
                        <Input
                            dir="ltr"
                            type="number"
                            value={defaultConnectTimeout}
                            onChange={(e) => setDefaultConnectTimeout(e.target.value)}
                            min="1"
                            max="60"
                            step="1"
                            className="max-w-[140px]"
                        />
                        <p className="text-xs text-muted-foreground">{translate(TUNING_SETTINGS.connect_timeout_hint)}</p>
                    </div>

                    <div className="space-y-2">
                        <Label>{translate(COMMON.probe_timeout_label)}</Label>
                        <Input
                            dir="ltr"
                            type="number"
                            value={defaultProbeTimeout}
                            onChange={(e) => setDefaultProbeTimeout(e.target.value)}
                            min="1"
                            max="1200"
                            step="1"
                            className="max-w-[140px]"
                        />
                        <p className="text-xs text-muted-foreground">{translate(TUNING_SETTINGS.probe_timeout_hint)}</p>
                    </div>
                </CardContent>
            </Card>

            {/* Reset asks first. It overwrites six values at once and cannot be undone;
                a confirmation is the proportionate control for that, and the dialog
                says explicitly that per-connection overrides are NOT affected — which
                is the first thing an administrator will wonder. */}
            {confirmReset && (
                <div className="p-4 bg-amber-50 border border-amber-200 rounded-md">
                    <p className="font-medium text-amber-900">{translate(TUNING_SETTINGS.reset_confirm_title)}</p>
                    <p className="text-sm text-amber-800 mt-1">{translate(TUNING_SETTINGS.reset_confirm_body)}</p>
                    <div className="flex gap-2 mt-3">
                        <Button
                            variant="destructive"
                            onClick={isExampleUser ? handleExampleAttempt : handleReset}
                            disabled={isResetting}
                        >
                            <RotateCcw className="h-4 w-4 me-2" />
                            {translate(isResetting ? TUNING_SETTINGS.resetting : TUNING_SETTINGS.reset_confirm_action)}
                        </Button>
                        <Button variant="outline" onClick={() => setConfirmReset(false)} disabled={isResetting}>
                            {translate(COMMON.cancel)}
                        </Button>
                    </div>
                </div>
            )}

            <div className="flex gap-2">
                <Button onClick={isExampleUser ? handleExampleAttempt : handleSave} disabled={isSaving}>
                    {translate(isSaving ? TUNING_SETTINGS.saving : TUNING_SETTINGS.save)}
                </Button>
                <Button
                    variant="outline"
                    onClick={() => (isExampleUser ? handleExampleAttempt() : setConfirmReset(true))}
                    disabled={isResetting}
                >
                    <RotateCcw className="h-4 w-4 me-2" />
                    {translate(COMMON.reset_to_defaults)}
                </Button>
            </div>
        </div>
    );
}
