"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
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
import { Loader2, Plus, Pencil, Trash2, XCircle, Lock, UserPlus } from "lucide-react";
import Link from "next/link";

// Import translations for this module
import { ADMIN } from "../translations";
import { COMMON } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";

interface VisualizationType {
  id: number;
  name: string;
  slug: string;
  description: string | null;
  renderer: string;
  inputSchema: any;
  parameterSchema: any;
  defaultParameters: any;
  enabled: boolean;
}

function AdminVisualizationTypesContent() {
  const { t, isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const router = useRouter();
  const [types, setTypes] = useState<VisualizationType[]>([]);
  const [loading, setLoading] = useState(true);
  const [editingType, setEditingType] = useState<VisualizationType | null>(null);
  const [isAdding, setIsAdding] = useState(false);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [typeToDelete, setTypeToDelete] = useState<VisualizationType | null>(null);
  const [submitting, setSubmitting] = useState(false);
  const [togglingId, setTogglingId] = useState<number | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);
  const [userRole, setUserRole] = useState<{ isAdmin: boolean; isGroupAdmin: boolean; isExampleUser: boolean } | null>(null);
  const [loadingRole, setLoadingRole] = useState(true);

  const [formData, setFormData] = useState({
    name: "",
    slug: "",
    description: "",
    renderer: "client",
    inputSchema: "",
    parameterSchema: "",
    defaultParameters: "",
    enabled: true,
  });

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  const isExampleUser = userRole?.isExampleUser === true;
  const isAdmin = userRole?.isAdmin === true;

  const fetchTypes = async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const res = await apiFetch("/api/admin/visualization-types");
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.visualization_types.fetch_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      setTypes(data.types);
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.visualization_types.fetch_error);
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
    fetchTypes();
  }, []);

  const resetForm = () => {
    setFormData({
      name: "",
      slug: "",
      description: "",
      renderer: "client",
      inputSchema: "",
      parameterSchema: "",
      defaultParameters: "",
      enabled: true,
    });
    setEditingType(null);
    setIsAdding(false);
    setErrorMessage(null);
    setSuccessMessage(null);
  };

  const handleEdit = (type: VisualizationType) => {
    setEditingType(type);
    setFormData({
      name: type.name,
      slug: type.slug,
      description: type.description || "",
      renderer: type.renderer,
      inputSchema: JSON.stringify(type.inputSchema, null, 2),
      parameterSchema: JSON.stringify(type.parameterSchema, null, 2),
      defaultParameters: JSON.stringify(type.defaultParameters, null, 2),
      enabled: type.enabled,
    });
    setIsAdding(true);
    setErrorMessage(null);
    setSuccessMessage(null);
  };

  const handleDeleteClick = (type: VisualizationType) => {
    setTypeToDelete(type);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!typeToDelete) return;
    setSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const res = await apiFetch(`/api/admin/visualization-types/${typeToDelete.id}`, {
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.visualization_types.delete_error);
        throw new Error(errorMsg);
      }
      const msg = translate(ADMIN.visualization_types.delete_success);
      setSuccessMessage(msg);
      toast.success(msg);
      fetchTypes();
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.visualization_types.delete_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
      setDeleteDialogOpen(false);
      setTypeToDelete(null);
    }
  };

  const handleToggleEnabled = async (id: number, currentEnabled: boolean) => {
    setTogglingId(id);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      const res = await apiFetch(`/api/admin/visualization-types/${id}`, {
        method: "PATCH",
        body: JSON.stringify({ enabled: !currentEnabled }),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.visualization_types.toggle_error);
        throw new Error(errorMsg);
      }
      setTypes(prev =>
        prev.map(t => (t.id === id ? { ...t, enabled: !currentEnabled } : t))
      );
      const msg = translate(ADMIN.visualization_types.update_success);
      setSuccessMessage(msg);
      toast.success(msg);
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.visualization_types.toggle_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setTogglingId(null);
    }
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSubmitting(true);
    setErrorMessage(null);
    setSuccessMessage(null);
    try {
      let inputSchema, parameterSchema, defaultParameters;
      try {
        inputSchema = JSON.parse(formData.inputSchema);
        parameterSchema = JSON.parse(formData.parameterSchema);
        defaultParameters = JSON.parse(formData.defaultParameters);
      } catch (err) {
        const msg = translate(ADMIN.visualization_types.invalid_json);
        setErrorMessage(msg);
        toast.error(msg);
        setSubmitting(false);
        return;
      }

      const payload = {
        name: formData.name,
        slug: formData.slug,
        description: formData.description || null,
        renderer: formData.renderer,
        inputSchema,
        parameterSchema,
        defaultParameters,
        enabled: formData.enabled,
      };

      let url = "/api/admin/visualization-types";
      let method = "POST";
      if (editingType) {
        url = `/api/admin/visualization-types/${editingType.id}`;
        method = "PATCH";
      }

      const res = await apiFetch(url, {
        method,
        body: JSON.stringify(payload),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.visualization_types.save_error);
        throw new Error(errorMsg);
      }
      const msg = editingType
        ? translate(ADMIN.visualization_types.update_success)
        : translate(ADMIN.visualization_types.create_success);
      setSuccessMessage(msg);
      toast.success(msg);
      resetForm();
      fetchTypes();
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.visualization_types.save_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setSubmitting(false);
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
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold">{translate(ADMIN.visualization_types.title)}</h1>
          <Button disabled>
            <Plus className="me-2 h-4 w-4" />
            {translate(ADMIN.visualization_types.add_button)}
          </Button>
        </div>

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
            <CardTitle>{translate(ADMIN.visualization_types.list_title)}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {types.length === 0 ? (
                <p className="text-muted-foreground text-center py-4">
                  {translate(ADMIN.visualization_types.no_types)}
                </p>
              ) : (
                types.map((type) => (
                  <div
                    key={type.id}
                    className="flex items-center justify-between p-3 border rounded-md hover:bg-muted/50 transition-colors opacity-60"
                  >
                    <div>
                      <div className="font-medium">{type.name}</div>
                      <div className="text-xs text-muted-foreground">
                        <span className="me-3">{translate(ADMIN.visualization_types.slug_label)}: {type.slug}</span>
                        <span className="me-3">{translate(ADMIN.visualization_types.renderer_label)}: {type.renderer}</span>
                        {type.description && <span>{type.description}</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1">
                        <Switch checked={type.enabled} disabled />
                        <span className="text-xs text-muted-foreground">
                          {type.enabled ? translate(ADMIN.visualization_types.enabled) : translate(ADMIN.visualization_types.disabled)}
                        </span>
                      </div>
                      <span className="text-xs text-muted-foreground italic">
                        {translate(ADMIN.groups.readonly_badge)}
                      </span>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>
      </div>
    );
  }

  // Admin user - full access
  if (isAdmin) {
    return (
      <div className="max-w-6xl mx-auto space-y-6">
        <div className="flex justify-between items-center">
          <h1 className="text-3xl font-bold">{translate(ADMIN.visualization_types.title)}</h1>
          <Button onClick={() => { resetForm(); setIsAdding(true); }}>
            <Plus className="me-2 h-4 w-4" />
            {translate(ADMIN.visualization_types.add_button)}
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

        {isAdding && (
          <Card>
            <CardHeader>
              <CardTitle>
                {editingType
                  ? translate(ADMIN.visualization_types.edit_title)
                  : translate(ADMIN.visualization_types.add_title)}
              </CardTitle>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleSubmit} className="space-y-4">
                <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
                  <div className="space-y-2">
                    <Label htmlFor="name">{translate(ADMIN.visualization_types.name)}</Label>
                    <div className="relative flex items-center">
                      <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                      <Input dir="auto"
                        id="name"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        required
                        className="flex-1"
                      />
                    </div>
                  </div>
                  <div className="space-y-2">
                    <Label htmlFor="slug">{translate(ADMIN.visualization_types.slug)}</Label>
                    <div className="relative flex items-center">
                      <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                      <Input dir="ltr"
                        id="slug"
                        value={formData.slug}
                        onChange={(e) => setFormData({ ...formData, slug: e.target.value })}
                        required
                        className="flex-1"
                      />
                    </div>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="description">{translate(ADMIN.visualization_types.description)}</Label>
                  <Input dir="auto"
                    id="description"
                    value={formData.description}
                    onChange={(e) => setFormData({ ...formData, description: e.target.value })}
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="renderer">{translate(ADMIN.visualization_types.renderer)}</Label>
                  <div className="relative flex items-center">
                    <span className="text-red-500 font-bold text-lg me-1" aria-hidden="true">*</span>
                    <select
                      id="renderer"
                      value={formData.renderer}
                      onChange={(e) => setFormData({ ...formData, renderer: e.target.value })}
                      className="flex-1 w-full rounded-md border border-input bg-background px-3 py-2 text-sm"
                    >
                      <option value="client">{translate(ADMIN.visualization_types.renderer_client)}</option>
                      <option value="server">{translate(ADMIN.visualization_types.renderer_server)}</option>
                    </select>
                  </div>
                </div>
                <div className="space-y-2">
                  <Label htmlFor="inputSchema">{translate(ADMIN.visualization_types.input_schema)}</Label>
                  <textarea dir="ltr"
                    id="inputSchema"
                    value={formData.inputSchema}
                    onChange={(e) => setFormData({ ...formData, inputSchema: e.target.value })}
                    rows={5}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="parameterSchema">{translate(ADMIN.visualization_types.parameter_schema)}</Label>
                  <textarea dir="ltr"
                    id="parameterSchema"
                    value={formData.parameterSchema}
                    onChange={(e) => setFormData({ ...formData, parameterSchema: e.target.value })}
                    rows={5}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </div>
                <div className="space-y-2">
                  <Label htmlFor="defaultParameters">{translate(ADMIN.visualization_types.default_parameters)}</Label>
                  <textarea dir="ltr"
                    id="defaultParameters"
                    value={formData.defaultParameters}
                    onChange={(e) => setFormData({ ...formData, defaultParameters: e.target.value })}
                    rows={5}
                    className="w-full rounded-md border border-input bg-background px-3 py-2 text-sm font-mono ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
                  />
                </div>
                <div className="flex items-center space-x-2">
                  <Switch
                    id="enabled"
                    checked={formData.enabled}
                    onCheckedChange={(checked) => setFormData({ ...formData, enabled: checked })}
                  />
                  <Label htmlFor="enabled">{translate(ADMIN.visualization_types.enabled)}</Label>
                </div>
                <div className="flex gap-4">
                  <Button type="submit" disabled={submitting}>
                    {submitting ? translate(COMMON.saving) : translate(COMMON.save)}
                  </Button>
                  <Button type="button" variant="outline" onClick={resetForm}>
                    {translate(COMMON.cancel)}
                  </Button>
                </div>
              </form>
            </CardContent>
          </Card>
        )}

        <Card>
          <CardHeader>
            <CardTitle>{translate(ADMIN.visualization_types.list_title)}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2">
              {types.length === 0 ? (
                <p className="text-muted-foreground text-center py-4">
                  {translate(ADMIN.visualization_types.no_types)}
                </p>
              ) : (
                types.map((type) => (
                  <div
                    key={type.id}
                    className="flex items-center justify-between p-3 border rounded-md hover:bg-muted/50 transition-colors"
                  >
                    <div>
                      <div className="font-medium">{type.name}</div>
                      <div className="text-xs text-muted-foreground">
                        <span className="me-3">{translate(ADMIN.visualization_types.slug_label)}: {type.slug}</span>
                        <span className="me-3">{translate(ADMIN.visualization_types.renderer_label)}: {type.renderer}</span>
                        {type.description && <span>{type.description}</span>}
                      </div>
                    </div>
                    <div className="flex items-center gap-2">
                      <div className="flex items-center gap-1">
                        <Switch
                          checked={type.enabled}
                          onCheckedChange={() => handleToggleEnabled(type.id, type.enabled)}
                          disabled={togglingId === type.id}
                        />
                        <span className="text-xs text-muted-foreground">
                          {type.enabled ? translate(ADMIN.visualization_types.enabled) : translate(ADMIN.visualization_types.disabled)}
                        </span>
                      </div>
                      <Button variant="ghost" size="icon" onClick={() => handleEdit(type)} title={translate(ADMIN.visualization_types.edit)}>
                        <Pencil className="h-4 w-4" />
                      </Button>
                      <Button variant="ghost" size="icon" onClick={() => handleDeleteClick(type)} className="text-muted-foreground hover:text-destructive" title={translate(ADMIN.visualization_types.delete)}>
                        <Trash2 className="h-4 w-4" />
                      </Button>
                    </div>
                  </div>
                ))
              )}
            </div>
          </CardContent>
        </Card>

        <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>
                {translate(ADMIN.visualization_types.delete_title)}
              </AlertDialogTitle>
              <AlertDialogDescription>
                {translate(ADMIN.visualization_types.delete_confirmation).replace("{name}", typeToDelete?.name || "")}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{translate(COMMON.cancel)}</AlertDialogCancel>
              <AlertDialogAction onClick={confirmDelete}>
                {translate(ADMIN.visualization_types.delete_button)}
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

export default function AdminVisualizationTypesPage() {
  return (
    <ProtectedRoute>
      <AdminVisualizationTypesContent />
    </ProtectedRoute>
  );
}