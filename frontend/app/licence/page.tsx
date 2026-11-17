"use client";

/**
 * Golden Screwdriver — Licence Management Page.
 *
 * Full licence lifecycle: view status, upload + preview, install,
 * and delete. Admin only. Fetches from GET /api/features and
 * manages licences via /api/licence endpoints.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { useSession } from "next-auth/react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useTranslate } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { Key, Building2, Calendar, Users, Shield, Upload, Trash2, FileJson } from "lucide-react";

import { LICENCE } from "./translations";
import { COMMON } from "@/app/common/translations";
import { formatDate } from "@/lib/date-format";

interface LicenceInfo {
    tier: string;
    features: string[];
    issued_to?: string;
    issued_at?: string;
    expires_at?: string;
    max_users?: number;
}

interface PreviewResult {
    valid: boolean;
    error?: string;
    tier?: string;
    features?: string[];
    issued_to?: string;
    issued_at?: string;
    expires_at?: string;
    max_users?: number;
}



export default function LicencePage() {
    const translate = useTranslate();
    const { data: session, status } = useSession();
    const router = useRouter();
    const fileInputRef = useRef<HTMLInputElement>(null);

    const [info, setInfo] = useState<LicenceInfo | null>(null);
    const [loading, setLoading] = useState(true);
    const [error, setError] = useState<string | null>(null);

    // Upload / preview state
    const [preview, setPreview] = useState<PreviewResult | null>(null);
    const [uploading, setUploading] = useState(false);
    const [actionError, setActionError] = useState<string | null>(null);
    const [actionSuccess, setActionSuccess] = useState<string | null>(null);
    const [showDeleteConfirm, setShowDeleteConfirm] = useState(false);

    const fetchLicenceInfo = useCallback(() => {
        fetch("/api/features")
            .then((r) => {
                if (!r.ok) throw new Error(`HTTP ${r.status}`);
                return r.json();
            })
            .then((data: LicenceInfo) => {
                setInfo(data);
                setLoading(false);
            })
            .catch((err) => {
                setError(err.message);
                setLoading(false);
            });
    }, []);

    useEffect(() => {
        fetchLicenceInfo();
    }, [fetchLicenceInfo]);

    // ── Actions ──────────────────────────────────────────────────

    const handleFile = async (file: File) => {
        setActionError(null);
        setActionSuccess(null);
        setPreview(null);
        setUploading(true);

        try {
            const content = await file.text();
            const res = await apiFetch("/api/licence/preview", {
                method: "POST",
                body: JSON.stringify({ content }),
            });
            const data = await res.json();
            setPreview(data);
            if (!data.valid) {
                setActionError(data.error ?? translate(LICENCE.preview_invalid));
            }
        } catch {
            setActionError(translate(LICENCE.preview_error));
        } finally {
            setUploading(false);
        }
    };

    const handleInstall = async () => {
        if (!preview?.valid) return;
        setActionError(null);
        setActionSuccess(null);
        setUploading(true);

        try {
            // Re-read the file from the input
            const file = fileInputRef.current?.files?.[0];
            if (!file) {
                setActionError(translate(LICENCE.install_no_file));
                setUploading(false);
                return;
            }
            const content = await file.text();
            const res = await apiFetch("/api/licence/install", {
                method: "POST",
                body: JSON.stringify({ content }),
            });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail ?? "Install failed");
            }
            setActionSuccess(translate(LICENCE.install_success));
            setPreview(null);
            if (fileInputRef.current) fileInputRef.current.value = "";
            fetchLicenceInfo();
        } catch (e: unknown) {
            setActionError(e instanceof Error ? e.message : translate(LICENCE.install_error));
        } finally {
            setUploading(false);
        }
    };

    const handleDelete = async () => {
        setActionError(null);
        setActionSuccess(null);
        setShowDeleteConfirm(false);

        try {
            const res = await apiFetch("/api/licence", { method: "DELETE" });
            if (!res.ok) {
                const err = await res.json();
                throw new Error(err.detail ?? "Delete failed");
            }
            setActionSuccess(translate(LICENCE.delete_success));
            fetchLicenceInfo();
        } catch (e: unknown) {
            setActionError(e instanceof Error ? e.message : translate(LICENCE.delete_error));
        }
    };

    // ── Auth guard ───────────────────────────────────────────────

    if (status === "loading") {
        return (
            <div className="flex items-center justify-center h-screen">
                <p className="text-muted-foreground">{translate(COMMON.loading)}</p>
            </div>
        );
    }

    if (!session) {
        router.push("/login");
        return null;
    }

    if (!session.user?.isAdmin) {
        return (
            <div className="flex items-center justify-center h-screen">
                <p className="text-muted-foreground">{translate(LICENCE.admin_required)}</p>
            </div>
        );
    }

    if (loading) {
        return (
            <div className="max-w-2xl mx-auto py-8 px-4">
                <p className="text-muted-foreground">{translate(COMMON.loading)}</p>
            </div>
        );
    }

    if (error || !info) {
        return (
            <div className="max-w-2xl mx-auto py-8 px-4">
                <p className="text-destructive">{translate(LICENCE.load_error)}</p>
            </div>
        );
    }

    const isLicensed = info.tier !== "open_source";

    return (
        <div className="max-w-2xl mx-auto py-8 px-4 space-y-6">
            <div>
                <h1 className="text-2xl font-bold">{translate(LICENCE.title)}</h1>
                <p className="text-muted-foreground mt-1">{translate(LICENCE.description)}</p>
            </div>

            {/* Success / error banners */}
            {actionSuccess && (
                <div className="bg-green-50 border border-green-200 text-green-800 px-4 py-3 rounded text-sm">
                    {actionSuccess}
                </div>
            )}
            {actionError && (
                <div className="bg-red-50 border border-red-200 text-red-800 px-4 py-3 rounded text-sm">
                    {actionError}
                </div>
            )}

            {/* Upload section */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <Upload className="h-5 w-5" />
                        {translate(LICENCE.upload_title)}
                    </CardTitle>
                </CardHeader>
                <CardContent className="space-y-3">
                    <input dir="ltr"
                        ref={fileInputRef}
                        type="file"
                        accept=".json,application/json"
                        onChange={(e) => {
                            const file = e.target.files?.[0];
                            if (file) handleFile(file);
                        }}
                        className="block w-full text-sm text-muted-foreground
                            file:me-4 file:py-2 file:px-4 file:rounded file:border-0
                            file:text-sm file:font-medium file:bg-blue-50 file:text-blue-700
                            hover:file:bg-blue-100"
                    />
                    {uploading && (
                        <p className="text-sm text-muted-foreground">{translate(COMMON.loading)}</p>
                    )}
                </CardContent>
            </Card>

            {/* Preview card */}
            {preview && (
                <Card>
                    <CardHeader className="pb-3">
                        <CardTitle className="text-lg flex items-center gap-2">
                            <FileJson className="h-5 w-5" />
                            {translate(LICENCE.preview_title)}
                        </CardTitle>
                    </CardHeader>
                    <CardContent className="space-y-3">
                        {preview.valid ? (
                            <>
                                <div className="flex items-center gap-2">
                                    <span className="text-sm text-muted-foreground">{translate(LICENCE.tier_label)}:</span>
                                    <span className="text-sm font-medium px-2 py-0.5 rounded bg-blue-100 text-blue-800">
                                        {preview.tier ?? "corporate"}
                                    </span>
                                </div>
                                {preview.issued_to && (
                                    <div className="flex items-center gap-2 text-sm">
                                        <Building2 className="h-4 w-4 text-muted-foreground" />
                                        <span className="text-muted-foreground">{translate(LICENCE.issued_to_label)}:</span>
                                        <span className="font-medium">{preview.issued_to}</span>
                                    </div>
                                )}
                                {preview.expires_at && (
                                    <div className="flex items-center gap-2 text-sm">
                                        <Calendar className="h-4 w-4 text-muted-foreground" />
                                        <span className="text-muted-foreground">{translate(LICENCE.expires_at_label)}:</span>
                                        <span className="font-medium">
                                            {formatDate(preview.expires_at)}
                                        </span>
                                    </div>
                                )}
                                {preview.features && preview.features.length > 0 && (
                                    <div className="flex flex-wrap gap-2">
                                        {preview.features.map((f) => (
                                            <span key={f} className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded border">{f}</span>
                                        ))}
                                    </div>
                                )}
                                <Button
                                    onClick={handleInstall}
                                    disabled={uploading}
                                    className="w-full"
                                >
                                    {translate(LICENCE.install_button)}
                                </Button>
                            </>
                        ) : (
                            <p className="text-sm text-red-600">{preview.error ?? translate(LICENCE.preview_invalid)}</p>
                        )}
                    </CardContent>
                </Card>
            )}

            {/* Current status */}
            <Card>
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2">
                        <Shield className="h-5 w-5" />
                        {translate(LICENCE.tier_label)}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    <span className={`text-sm px-3 py-1 rounded ${isLicensed ? "bg-blue-100 text-blue-800" : "bg-gray-100 text-gray-600"}`}>
                        {translate({ key: `licence.tier.${info.tier}`, fallback: info.tier })}
                    </span>
                    {!isLicensed && (
                        <p className="text-sm text-muted-foreground mt-3">
                            {translate(LICENCE.open_source_message)}
                        </p>
                    )}
                </CardContent>
            </Card>

            {isLicensed && (
                <>
                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-lg flex items-center gap-2">
                                <Key className="h-5 w-5" />
                                {translate(LICENCE.features_label)}
                            </CardTitle>
                        </CardHeader>
                        <CardContent>
                            {info.features.length === 0 ? (
                                <p className="text-sm text-muted-foreground">{translate(LICENCE.no_features)}</p>
                            ) : (
                                <div className="flex flex-wrap gap-2">
                                    {info.features.map((f) => (
                                        <span key={f} className="text-xs bg-gray-100 text-gray-700 px-2 py-0.5 rounded border">{f}</span>
                                    ))}
                                </div>
                            )}
                        </CardContent>
                    </Card>

                    <Card>
                        <CardHeader className="pb-3">
                            <CardTitle className="text-lg">{translate(LICENCE.details_label)}</CardTitle>
                        </CardHeader>
                        <CardContent className="space-y-3">
                            {info.issued_to && (
                                <div className="flex items-center gap-2 text-sm">
                                    <Building2 className="h-4 w-4 text-muted-foreground" />
                                    <span className="text-muted-foreground">{translate(LICENCE.issued_to_label)}:</span>
                                    <span className="font-medium">{info.issued_to}</span>
                                </div>
                            )}
                            {info.issued_at && (
                                <div className="flex items-center gap-2 text-sm">
                                    <Calendar className="h-4 w-4 text-muted-foreground" />
                                    <span className="text-muted-foreground">{translate(LICENCE.issued_at_label)}:</span>
                                    <span className="font-medium">{formatDate(info.issued_at)}</span>
                                </div>
                            )}
                            {info.expires_at && (
                                <div className="flex items-center gap-2 text-sm">
                                    <Calendar className="h-4 w-4 text-muted-foreground" />
                                    <span className="text-muted-foreground">{translate(LICENCE.expires_at_label)}:</span>
                                    <span className="font-medium">{formatDate(info.expires_at)}</span>
                                </div>
                            )}
                            {info.max_users !== undefined && info.max_users !== null && (
                                <div className="flex items-center gap-2 text-sm">
                                    <Users className="h-4 w-4 text-muted-foreground" />
                                    <span className="text-muted-foreground">{translate(LICENCE.max_users_label)}:</span>
                                    <span className="font-medium">{info.max_users}</span>
                                </div>
                            )}
                        </CardContent>
                    </Card>
                </>
            )}

            {/* Delete section */}
            <Card className="border-red-200">
                <CardHeader className="pb-3">
                    <CardTitle className="text-lg flex items-center gap-2 text-red-700">
                        <Trash2 className="h-5 w-5" />
                        {translate(LICENCE.delete_title)}
                    </CardTitle>
                </CardHeader>
                <CardContent>
                    {showDeleteConfirm ? (
                        <div className="space-y-3">
                            <p className="text-sm text-red-700">{translate(LICENCE.delete_confirm)}</p>
                            <div className="flex gap-2">
                                <Button variant="destructive" onClick={handleDelete} disabled={uploading}>
                                    {translate(LICENCE.delete_yes)}
                                </Button>
                                <Button variant="outline" onClick={() => setShowDeleteConfirm(false)}>
                                    {translate(LICENCE.delete_no)}
                                </Button>
                            </div>
                        </div>
                    ) : (
                        <Button variant="outline" onClick={() => setShowDeleteConfirm(true)} className="border-red-300 text-red-700 hover:bg-red-50">
                            <Trash2 className="h-4 w-4 me-2" />
                            {translate(LICENCE.delete_button)}
                        </Button>
                    )}
                </CardContent>
            </Card>
        </div>
    );
}
