"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { useAI } from "@/lib/ai-context";
import { toast } from "sonner";
import { ProtectedRoute } from "@/components/protected-route";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, useTranslateWithParams, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { COMMON } from "@/app/common/translations";
import { AI_SETTINGS, AI_CONNECTION_FORM } from "./translations";
import { Plus, Edit, Trash2, Bot, Users, XCircle, RefreshCw, Loader2 } from "lucide-react";
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

interface AvailableConnection {
  id: string;
  connectionId: number;
  name: string;
  provider: string;
  providerName?: string;
  endpoint: string | null;
  aiConnectionGroup: string;
  userId: string;
  userName: string;
  isOwn: boolean;
  isShared: boolean;
  createdAt: string;
  updatedAt: string;
}

function AISettingsContent() {
  const router = useRouter();
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const translateWithParams = useTranslateWithParams();
  const { connections, defaultConnectionId, setDefaultConnectionId, deleteConnection, loading, refreshConnections } = useAI();
  const [availableConnections, setAvailableConnections] = useState<AvailableConnection[]>([]);
  const [loadingAvailable, setLoadingAvailable] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [connectionToDelete, setConnectionToDelete] = useState<{ id: string; name: string } | null>(null);
  const [syncingConnectionId, setSyncingConnectionId] = useState<number | null>(null);
  const [isExampleUser, setIsExampleUser] = useState(false);
  const [isAdmin, setIsAdmin] = useState(false);
  const [groupDescriptions, setGroupDescriptions] = useState<Record<string, string>>({});

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  useEffect(() => {
    apiFetch("/api/user/role")
      .then(res => res.json())
      .then(data => {
        setIsExampleUser(data.isExampleUser === true);
        setIsAdmin(data.isAdmin === true);
        if (data.isAdmin) {
          apiFetch("/api/admin/groups")
            .then(res => res.json())
            .then(data => {
              const map: Record<string, string> = {};
              (data.groups || []).forEach((g: any) => { map[g.groupId] = g.groupDescription; });
              setGroupDescriptions(map);
            })
            .catch(() => {});
        }
      })
      .catch(() => {});
  }, []);

  const getConnectionDisplayName = (conn: AvailableConnection) => {
    const isShared = conn.isShared === true;
    const providerName = conn.providerName || conn.provider;
    const baseName = `${conn.name} (${providerName})`;
    return isShared ? `* ${baseName}` : baseName;
  };

  const handleAddNew = () => {
    router.push("/settings/ai/connection/new");
  };

  const handleEdit = (connectionId: string) => {
    router.push(`/settings/ai/connection/${connectionId}`);
  };

  const handleRefreshModels = async (connectionId: number, provider: string) => {
    setSyncingConnectionId(connectionId);
    setErrorMessage(null);
    try {
      // DISCOVER, not FETCH (plan Item 31 of the models-testing plan). The old path
      // refreshed a provider-wide catalogue keyed by provider code, so a refresh
      // through one Ollama host deleted the other host's rows. This one asks THIS
      // server what it serves and records it against this connection.
      const res = await apiFetch(`/api/user/ai-connections/${connectionId}/models/discover`, {
        method: "POST",
      });
      if (!res.ok) {
        let errorData: any = {};
        try { const text = await res.text(); if (text) errorData = JSON.parse(text); } catch {}
        throw new Error(getErrorMessageFromData(translate, errorData, AI_CONNECTION_FORM.models_sync_error));
      }
      const data = await res.json().catch(() => ({}));
      const msg = translateWithParams(
        AI_CONNECTION_FORM.models_discovered.key,
        AI_CONNECTION_FORM.models_discovered.fallback,
        {
          seen: data.modelsSeen ?? 0,
          created: data.connectionModelsCreated ?? 0,
          refreshed: data.connectionModelsRefreshed ?? 0,
          pruned: data.connectionModelsPruned ?? 0,
        },
      );
      setSuccessMessage(msg);
      toast.success(msg);
      refreshConnections();
    } catch (error: any) {
      const msg = error.message || translate(AI_CONNECTION_FORM.models_sync_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setSyncingConnectionId(null);
    }
  };

  const handleDeleteClick = (id: string, name: string) => {
    setConnectionToDelete({ id, name });
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (connectionToDelete) {
      try {
        await deleteConnection(connectionToDelete.id);
        const msg = translate(AI_CONNECTION_FORM.deleted);
        setSuccessMessage(msg);
        toast.success(msg);
        await refreshConnections();
        await fetchAvailableConnections();
      } catch (error: any) {
        const msg = error.message || translate(AI_CONNECTION_FORM.delete_error);
        setErrorMessage(msg);
        toast.error(msg);
      }
      setDeleteDialogOpen(false);
      setConnectionToDelete(null);
    }
  };

  const handleSetDefault = (id: string) => {
    setDefaultConnectionId(id);
    const msg = translate(AI_CONNECTION_FORM.default_set);
    setSuccessMessage(msg);
    toast.success(msg);
  };

  const handleClearDefault = () => {
    setDefaultConnectionId(null);
    const msg = translate(AI_CONNECTION_FORM.default_cleared);
    setSuccessMessage(msg);
    toast.success(msg);
  };

  const fetchAvailableConnections = async () => {
    try {
      setLoadingAvailable(true);
      setErrorMessage(null);
      const res = await apiFetch("/api/user/ai-connections/available");
      if (!res.ok) {
        const errorData = await res.json().catch(() => ({}));
        const errorMsg = getErrorMessageFromData(translate, errorData, AI_CONNECTION_FORM.load_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      setAvailableConnections(data.connections || []);
    } catch (error: any) {
      console.error("Error fetching available connections:", error);
      const msg = error.message || translate(AI_CONNECTION_FORM.load_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setLoadingAvailable(false);
    }
  };

  useEffect(() => {
    fetchAvailableConnections();
  }, []);

  if (!isLanguageLoaded || loading || loadingAvailable) {
    return <div className="max-w-3xl mx-auto py-8">{translate(COMMON.loading)}</div>;
  }

  const displayConnections = availableConnections.length > 0 ? availableConnections : [];

  return (
    <div className="max-w-3xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold">{translate(AI_SETTINGS.title)}</h1>
          <p className="text-sm text-muted-foreground mt-1">
            {translate(AI_SETTINGS.default_hint)}
          </p>
        </div>
        <Button onClick={handleAddNew}>
          <Plus className="me-2 h-4 w-4" />
          {translate(AI_CONNECTION_FORM.add_new)}
        </Button>
      </div>

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

      {displayConnections.length === 0 ? (
        <Card>
          <CardContent className="py-8 text-center text-muted-foreground">
            <Bot className="mx-auto h-12 w-12 mb-3 opacity-50" />
            <p>{translate(AI_CONNECTION_FORM.no_connections)}</p>
            <Button variant="outline" className="mt-4" onClick={handleAddNew}>
              {translate(AI_CONNECTION_FORM.add_first)}
            </Button>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-4">
          {displayConnections.map((conn) => {
            const isShared = conn.isShared === true;
            const isOwn = conn.isOwn === true;
            const isDefault = conn.id === defaultConnectionId;

            return (
              <Card key={conn.id} className={isDefault ? "border-primary" : ""}>
                <CardHeader className="pb-3">
                  <div className="flex justify-between items-start">
                    <div>
                      <CardTitle className="flex items-center gap-2">
                        {getConnectionDisplayName(conn)}
                        {isDefault && (
                          <span className="text-xs bg-primary text-primary-foreground px-2 py-0.5 rounded">
                            {translate(AI_CONNECTION_FORM.default_badge)}
                          </span>
                        )}
                        {isShared && (
                          <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded">
                            {translate(AI_CONNECTION_FORM.shared_badge)}
                          </span>
                        )}
                        {isShared && isAdmin && conn.aiConnectionGroup && (
                          <span className="text-xs text-muted-foreground">
                            {conn.aiConnectionGroup}
                            {groupDescriptions[conn.aiConnectionGroup] ? ` \u2014 ${groupDescriptions[conn.aiConnectionGroup]}` : ''}
                          </span>
                        )}
                        {!isOwn && (
                          <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">
                            {translate(AI_CONNECTION_FORM.by_label)} {conn.userName || translate(AI_CONNECTION_FORM.unknown_user)}
                          </span>
                        )}
                      </CardTitle>
                      <CardDescription className="mt-1">
                        <span className="font-medium">{conn.providerName || conn.provider}</span>
                        {conn.endpoint && (
                          <span className="text-xs text-muted-foreground ms-2">({conn.endpoint})</span>
                        )}
                      </CardDescription>
                    </div>
                    <div className="flex gap-2">
                      {(isOwn || isAdmin) ? (
                        <>
                          {isDefault ? (
                            <Button variant="outline" size="sm" onClick={handleClearDefault} disabled={isExampleUser}>
                              {translate(AI_CONNECTION_FORM.clear_default)}
                            </Button>
                          ) : (
                            <Button variant="outline" size="sm" onClick={() => handleSetDefault(conn.id)} disabled={isExampleUser}>
                              {translate(AI_CONNECTION_FORM.set_default)}
                            </Button>
                          )}
<Button variant="outline" size="sm" onClick={() => handleEdit(conn.id)}>
                              <Edit className="h-4 w-4" />
                            </Button>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleRefreshModels(conn.connectionId, conn.provider)}
                              disabled={syncingConnectionId === conn.connectionId}
                              title={translate(AI_CONNECTION_FORM.models_refresh)}
                            >
                              {syncingConnectionId === conn.connectionId ? (
                                <Loader2 className="h-4 w-4 animate-spin" />
                              ) : (
                                <RefreshCw className="h-4 w-4" />
                              )}
                            </Button>
                            <Button variant="destructive" size="sm" onClick={() => handleDeleteClick(conn.id, conn.name)} disabled={isExampleUser}>
                            <Trash2 className="h-4 w-4" />
                          </Button>
                        </>
                      ) : (
                        <>
                          {isDefault ? (
                            <Button variant="outline" size="sm" onClick={handleClearDefault} disabled={isExampleUser}>
                              {translate(AI_CONNECTION_FORM.clear_default)}
                            </Button>
                          ) : (
                            <Button variant="outline" size="sm" onClick={() => handleSetDefault(conn.id)} disabled={isExampleUser}>
                              {translate(AI_CONNECTION_FORM.set_default)}
                            </Button>
                          )}
                          <Button variant="outline" size="sm" onClick={() => handleEdit(conn.id)}>
                            <Users className="h-4 w-4 me-1" />
                            {translate(AI_CONNECTION_FORM.shared_readonly)}
                          </Button>
                        </>
                      )}
                    </div>
                  </div>
                </CardHeader>
              </Card>
            );
          })}
        </div>
      )}

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{translate(AI_CONNECTION_FORM.delete_title)}</AlertDialogTitle>
            <AlertDialogDescription>
              {translate(AI_CONNECTION_FORM.delete_confirmation)}{" "}
              <strong>{connectionToDelete?.name}</strong>? {translate(COMMON.cannot_undo)}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{translate(COMMON.cancel)}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDelete}>{translate(AI_CONNECTION_FORM.delete_button)}</AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function AIPage() {
  return (
    <ProtectedRoute>
      <AISettingsContent />
    </ProtectedRoute>
  );
}
