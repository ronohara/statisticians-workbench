// frontend/app/admin/setup/internal/page.tsx
"use client";

import { useState, useEffect, useRef } from "react";
import { useRouter } from "next/navigation";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { toast } from "sonner";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate } from "@/lib/translation-helpers";
import { Lock, UserPlus, CheckCircle, XCircle, AlertTriangle } from "lucide-react";
import Link from "next/link";

import { INTERNAL_SETTINGS } from "./translations";
import { COMMON } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";

interface HealthData {
  status: string;
  version: string;
  shared_memory?: { available: boolean; stats?: Record<string, unknown> };
  database?: { pool_initialized: boolean; host?: string | null; port?: number | null };
}

interface FeaturesData {
  tier?: string;
  features?: string[];
  issued_to?: string;
  expiry?: string;
}

export default function InternalPage() {
  const router = useRouter();
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();

  const [health, setHealth] = useState<HealthData | null>(null);
  const [features, setFeatures] = useState<FeaturesData | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<{ isAdmin: boolean; isGroupAdmin: boolean; isExampleUser: boolean } | null>(null);
  const [loadingRole, setLoadingRole] = useState(true);

  const initialFetchDone = useRef(false);

  const dismissError = () => setErrorMessage(null);
  const isExampleUser = userRole?.isExampleUser === true;

  useEffect(() => {
    fetch("/api/user/role")
      .then(res => res.ok ? res.json() : null)
      .then(data => { if (data) setUserRole(data); })
      .catch(() => {})
      .finally(() => setLoadingRole(false));
  }, []);

  useEffect(() => {
    if (initialFetchDone.current) return;
    initialFetchDone.current = true;
    setErrorMessage(null);
    Promise.all([
      fetch("/api/health").then(r => r.ok ? r.json() : null),
      fetch("/api/features").then(r => r.ok ? r.json() : null),
    ])
      .then(([healthData, featuresData]) => {
        setHealth(healthData);
        setFeatures(featuresData);
      })
      .catch((error: any) => {
        const msg = error.message || translate(INTERNAL_SETTINGS.load_error);
        setErrorMessage(msg);
        toast.error(msg);
      })
      .finally(() => setIsLoading(false));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

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
        <h1 className="text-3xl font-bold">{translate(INTERNAL_SETTINGS.title)}</h1>
        <div className="p-6 bg-orange-50 border border-orange-200 rounded-md text-orange-800 text-center">
          <Lock className="h-10 w-10 mx-auto mb-3 text-orange-600" />
          <p className="text-sm mb-4">{translate(COMPONENTS.readonly_wrapper)}</p>
          <Link href="/register">
            <Button><UserPlus className="h-4 w-4 me-2" />{translate(COMPONENTS.example_user_banner.register_button)}</Button>
          </Link>
        </div>
      </div>
    );
  }

  const healthy = health?.status === "healthy";

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-3xl font-bold">{translate(INTERNAL_SETTINGS.title)}</h1>

      {errorMessage && (
        <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 text-sm flex items-center justify-between">
          <span>{errorMessage}</span>
          <button onClick={dismissError} className="text-red-600 hover:text-red-800">&times;</button>
        </div>
      )}

      <Card>
        <CardHeader>
          <CardTitle>{translate(INTERNAL_SETTINGS.system_status.title)}</CardTitle>
          <CardDescription>{translate(INTERNAL_SETTINGS.system_status.description)}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {/* Overall Health */}
          <div className="flex items-center justify-between py-2 border-b">
            <span className="text-sm font-medium">{translate(INTERNAL_SETTINGS.system_status.overall_health)}</span>
            {healthy
              ? <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700"><CheckCircle className="h-3 w-3 me-1" />{translate(INTERNAL_SETTINGS.system_status.healthy)}</span>
              : <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-red-100 text-red-700"><XCircle className="h-3 w-3 me-1" />{translate(INTERNAL_SETTINGS.system_status.unhealthy)}</span>
            }
          </div>

          {/* Version */}
          <div className="flex items-center justify-between py-2 border-b">
            <span className="text-sm font-medium">{translate(INTERNAL_SETTINGS.system_status.version)}</span>
            <span className="text-sm text-muted-foreground font-mono">{health?.version || "—"}</span>
          </div>

          {/* Database Pool */}
          <div className="flex items-center justify-between py-2 border-b">
            <span className="text-sm font-medium">{translate(INTERNAL_SETTINGS.system_status.db_pool)}</span>
            {health?.database?.pool_initialized
              ? <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700"><CheckCircle className="h-3 w-3 me-1" />{translate(INTERNAL_SETTINGS.system_status.initialized)}</span>
              : <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-amber-50 text-amber-700 border border-amber-300"><AlertTriangle className="h-3 w-3 me-1" />{translate(INTERNAL_SETTINGS.system_status.not_initialized)}</span>
            }
          </div>

          {/* Database Cluster — which cluster this backend is pointed at.
              Reported by /api/health from DATABASE_URL, so it answers
              "which cluster am I on?" even when the database is down. */}
          <div className="flex items-center justify-between py-2 border-b">
            <span className="text-sm font-medium">{translate(INTERNAL_SETTINGS.system_status.db_cluster)}</span>
            <span className="text-sm text-muted-foreground font-mono">
              {health?.database?.host && health?.database?.port
                ? `${health.database.host}:${health.database.port}`
                : "—"}
            </span>
          </div>

          {/* Shared Memory */}
          <div className="flex items-center justify-between py-2 border-b">
            <span className="text-sm font-medium">{translate(INTERNAL_SETTINGS.system_status.shared_memory)}</span>
            {health?.shared_memory?.available
              ? <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-100 text-green-700"><CheckCircle className="h-3 w-3 me-1" />{translate(INTERNAL_SETTINGS.system_status.available)}</span>
              : <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-green-50 text-green-700"><CheckCircle className="h-3 w-3 me-1" />{translate(INTERNAL_SETTINGS.system_status.not_required)}</span>
            }
          </div>
        </CardContent>
      </Card>

      {/* Licence & Features */}
      <Card>
        <CardHeader>
          <CardTitle>{translate(INTERNAL_SETTINGS.licence.title)}</CardTitle>
          <CardDescription>{translate(INTERNAL_SETTINGS.licence.description)}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center justify-between py-2 border-b">
            <span className="text-sm font-medium">{translate(INTERNAL_SETTINGS.licence.tier)}</span>
            <span className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium border font-mono">{features?.tier || "open_source"}</span>
          </div>
          {features?.issued_to && (
            <div className="flex items-center justify-between py-2 border-b">
              <span className="text-sm font-medium">{translate(INTERNAL_SETTINGS.licence.issued_to)}</span>
              <span className="text-sm text-muted-foreground">{features.issued_to}</span>
            </div>
          )}
          {features?.expiry && (
            <div className="flex items-center justify-between py-2 border-b">
              <span className="text-sm font-medium">{translate(INTERNAL_SETTINGS.licence.expiry)}</span>
              <span className="text-sm text-muted-foreground font-mono">{features.expiry}</span>
            </div>
          )}
          {features?.features && features.features.length > 0 && (
            <div className="py-2">
              <span className="text-sm font-medium block mb-2">{translate(INTERNAL_SETTINGS.licence.features)}</span>
              <div className="flex flex-wrap gap-2">
                {features.features.map((f: string) => (
                  <span key={f} className="inline-flex items-center px-2 py-0.5 rounded text-xs font-medium bg-secondary text-secondary-foreground font-mono">{f}</span>
                ))}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Placeholder for future diagnostics */}
      <Card className="border-dashed opacity-60">
        <CardHeader>
          <CardTitle className="text-sm">{translate(INTERNAL_SETTINGS.future.title)}</CardTitle>
          <CardDescription className="text-xs">{translate(INTERNAL_SETTINGS.future.description)}</CardDescription>
        </CardHeader>
        <CardContent>
          <ul className="text-xs text-muted-foreground space-y-1 list-disc ms-4">
            <li>{translate(INTERNAL_SETTINGS.future.email_transport)}</li>
            <li>{translate(INTERNAL_SETTINGS.future.cache_config)}</li>
            <li>{translate(INTERNAL_SETTINGS.future.debug_logging)}</li>
            <li>{translate(INTERNAL_SETTINGS.future.pool_stats)}</li>
          </ul>
        </CardContent>
      </Card>

      <div className="flex gap-3">
        <Button variant="outline" onClick={() => router.push("/")}>
          {translate(COMMON.cancel)}
        </Button>
      </div>
    </div>
  );
}
