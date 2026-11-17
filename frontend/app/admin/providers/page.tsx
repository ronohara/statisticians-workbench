"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Switch } from "@/components/ui/switch";
import { Button } from "@/components/ui/button";
import {
  AlertDialog,
  AlertDialogAction,
  AlertDialogCancel,
  AlertDialogContent,
  AlertDialogDescription,
  AlertDialogFooter,
  AlertDialogHeader,
  AlertDialogTitle,
} from "@/components/ui/alert-dialog";
import { toast } from "sonner";
import { Loader2, Trash2, XCircle, Lock, UserPlus } from "lucide-react";
import Link from "next/link";

// Import translations for this module
import { ADMIN } from "../translations";
import { COMMON } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";

interface AIProvider {
  id: number;
  code: string;
  name: string;
  isLocal: boolean;
  requiresApiKey: boolean;
  defaultEndpoint: string | null;
  enabled: boolean;
}

function AdminProvidersContent() {
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const router = useRouter();
  const [providers, setProviders] = useState<AIProvider[]>([]);
  const [loading, setLoading] = useState(true);
  const [toggling, setToggling] = useState<number | null>(null);
  const [deleting, setDeleting] = useState<number | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [providerToDelete, setProviderToDelete] = useState<AIProvider | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<{ isAdmin: boolean; isGroupAdmin: boolean; isExampleUser: boolean } | null>(null);
  const [loadingRole, setLoadingRole] = useState(true);

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  const isExampleUser = userRole?.isExampleUser === true;
  const isAdmin = userRole?.isAdmin === true;

  const fetchProviders = async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const res = await apiFetch("/api/admin/ai-providers");
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.providers.fetch_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      setProviders(data.providers);
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.providers.fetch_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
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
    fetchProviders();
  }, [translate]);

  // The "refresh from the provider's catalogue" action was removed in Item 32 of
  // the models-testing plan. It called POST /api/admin/provider-models/fetch, which
  // wrote "ProviderModel" — a catalogue keyed by provider code, so a refresh through
  // one Ollama host deleted another host's rows. Learning what a server serves is now
  // discovery, per connection, from the connection's own page.

  const handleToggle = async (id: number, currentEnabled: boolean) => {
    setToggling(id);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const res = await apiFetch("/api/admin/ai-providers", {
        method: "PATCH",
        body: JSON.stringify({ id, enabled: !currentEnabled }),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.providers.toggle_error);
        throw new Error(errorMsg);
      }
      setProviders(prev =>
        prev.map(p => (p.id === id ? { ...p, enabled: !currentEnabled } : p))
      );
      const msg = translate(ADMIN.providers.update_success);
      setSuccessMessage(msg);
      toast.success(msg);
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.providers.toggle_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setToggling(null);
    }
  };

  const handleDeleteClick = (provider: AIProvider) => {
    setProviderToDelete(provider);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!providerToDelete) return;
    setDeleting(providerToDelete.id);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const res = await apiFetch(`/api/admin/ai-providers?id=${providerToDelete.id}`, {
        method: "DELETE",
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.providers.delete_error);
        throw new Error(errorMsg);
      }
      setProviders(prev => prev.filter(p => p.id !== providerToDelete.id));
      const msg = translate(ADMIN.providers.delete_success);
      setSuccessMessage(msg);
      toast.success(msg);
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.providers.delete_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setDeleting(null);
      setDeleteDialogOpen(false);
      setProviderToDelete(null);
    }
  };

  if (!isLanguageLoaded || loading || loadingRole) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  // If Example User, show read-only view
  if (isExampleUser) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold">{translate(ADMIN.providers.title)}</h1>
        <p className="text-sm text-muted-foreground">
          {translate(ADMIN.providers.description)}
        </p>

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
            <CardTitle>{translate(ADMIN.providers.list_title)}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {providers.map(provider => (
                <div
                  key={provider.id}
                  className="flex items-center justify-between p-3 border rounded-md hover:bg-muted/50 transition-colors opacity-60"
                >
                  <div>
                    <div className="font-medium">{provider.name}</div>
                    <div className="text-xs text-muted-foreground">
                      <span className="me-3">{translate(ADMIN.providers.code_label)}: {provider.code}</span>
                      {provider.isLocal && (
                        <span className="me-3 bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full text-[10px]">
                          {translate(ADMIN.providers.local)}
                        </span>
                      )}
                      {provider.requiresApiKey ? (
                        <span className="text-amber-600">{translate(ADMIN.providers.requires_api_key)}</span>
                      ) : (
                        <span className="text-green-600">{translate(ADMIN.providers.no_api_key)}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">
                      {provider.enabled ? translate(ADMIN.providers.enabled) : translate(ADMIN.providers.disabled)}
                    </span>
                    <Switch checked={provider.enabled} disabled />
                    <span className="text-xs text-muted-foreground italic ms-2">
                      {translate(ADMIN.groups.readonly_badge)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Admin user - full access
  if (isAdmin) {
    return (
      <div className="max-w-4xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold">{translate(ADMIN.providers.title)}</h1>
        <p className="text-sm text-muted-foreground">
          {translate(ADMIN.providers.description)}
        </p>

        {errorMessage && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-md text-red-800 flex items-center justify-between">
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
            <CardTitle>{translate(ADMIN.providers.list_title)}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {providers.map(provider => (
                <div
                  key={provider.id}
                  className="flex items-center justify-between p-3 border rounded-md hover:bg-muted/50 transition-colors"
                >
                  <div>
                    <div className="font-medium">{provider.name}</div>
                    <div className="text-xs text-muted-foreground">
                      <span className="me-3">{translate(ADMIN.providers.code_label)}: {provider.code}</span>
                      {provider.isLocal && (
                        <span className="me-3 bg-blue-100 text-blue-800 px-2 py-0.5 rounded-full text-[10px]">
                          {translate(ADMIN.providers.local)}
                        </span>
                      )}
                      {provider.requiresApiKey ? (
                        <span className="text-amber-600">{translate(ADMIN.providers.requires_api_key)}</span>
                      ) : (
                        <span className="text-green-600">{translate(ADMIN.providers.no_api_key)}</span>
                      )}
                    </div>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-sm text-muted-foreground">
                      {provider.enabled ? translate(ADMIN.providers.enabled) : translate(ADMIN.providers.disabled)}
                    </span>
                    <Switch
                      checked={provider.enabled}
                      onCheckedChange={() => handleToggle(provider.id, provider.enabled)}
                      disabled={toggling === provider.id}
                    />
                    <Button
                      variant="ghost"
                      size="icon"
                      onClick={() => handleDeleteClick(provider)}
                      disabled={deleting === provider.id}
                      className="text-muted-foreground hover:text-destructive"
                      title={translate(ADMIN.providers.delete_provider)}
                    >
                      {deleting === provider.id ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Trash2 className="h-4 w-4" />
                      )}
                    </Button>
                  </div>
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {translate(ADMIN.providers.delete_title)}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {translate(ADMIN.providers.delete_confirmation).replace("{name}", providerToDelete?.name || "")}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{translate(COMMON.cancel)}</AlertDialogCancel>
              <AlertDialogAction onClick={confirmDelete}>
                {translate(ADMIN.providers.delete_button)}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>
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
          <Button className="mt-4 w-full" onClick={() => router.push("/")}>
            {translate(COMMON.back)}
          </Button>
        </CardContent>
      </Card>
    </div>
  );
}

export default function AdminProvidersPage() {
  return (
    <ProtectedRoute>
      <AdminProvidersContent />
    </ProtectedRoute>
  );
}