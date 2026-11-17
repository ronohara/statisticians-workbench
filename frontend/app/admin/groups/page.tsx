"use client";

import { useState, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessage, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { ProtectedRoute } from "@/components/protected-route";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Switch } from "@/components/ui/switch";
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select";
import { toast } from "sonner";
import { Loader2, Save, X, XCircle, Users, Shield, User, Trash2, Edit, CheckCircle, Eye } from "lucide-react";
import { ADMIN, ADMIN_USERS, ADMIN_GROUPS, ADMIN_USER_DETAILS } from "../translations";
import { COMMON } from "@/app/common/translations";
import { PROFILE_SETTINGS } from "@/app/settings/profile/translations";
import { COMPONENTS } from "@/components/translations";
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
import { formatDate } from "@/lib/date-format";

interface Group {
  groupId: string;
  groupDescription: string;
}

interface GroupUser {
  id: string;
  email: string;
  name: string | null;
  isAdmin: boolean;
  isGroupAdmin: boolean;
  isExampleUser: boolean;
  emailVerified: string | null;
  createdAt: string;
  deletedAt: string | null;
  userGroup: string;
  maxUploadSizeMB: number;
  maxUploadCount: number;
  emailNotifications: boolean;
  darkMode: boolean;
  language: string;
}

interface UserRole {
  isAdmin: boolean;
  isGroupAdmin: boolean;
  isExampleUser: boolean;
}

interface Language {
  code: string;
  name: string;
}

function AdminGroupsContent() {
  const { isLanguageLoaded, language } = useTranslation();
  const translate = useTranslate();
  const router = useRouter();
  const [groups, setGroups] = useState<Group[]>([]);
  const [groupUsers, setGroupUsers] = useState<GroupUser[]>([]);
  const [currentGroupId, setCurrentGroupId] = useState<string>("");
  const [currentGroupDescription, setCurrentGroupDescription] = useState<string>("");
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState<Record<string, boolean>>({});
  const [editing, setEditing] = useState<Record<string, boolean>>({});
  const [editedDescriptions, setEditedDescriptions] = useState<Record<string, string>>({});
  const [userRole, setUserRole] = useState<UserRole | null>(null);
  const [editingUser, setEditingUser] = useState<string | null>(null);
  const [editingUserData, setEditingUserData] = useState<Partial<GroupUser>>({});
  const [languages, setLanguages] = useState<Language[]>([]);
  
  // Persistent error/success messages
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [successMessage, setSuccessMessage] = useState<string | null>(null);

  // Delete dialog
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<GroupUser | null>(null);
  const [deleting, setDeleting] = useState(false);

  const dismissError = () => setErrorMessage(null);
  const dismissSuccess = () => setSuccessMessage(null);

  const fetchLanguages = async () => {
    try {
      const res = await fetch(`/api/languages?viewer=${language}`);
      if (res.ok) {
        const data = await res.json();
        setLanguages(data);
      }
    } catch (error) {
      console.error("Failed to fetch languages:", error);
    }
  };

  const fetchUserRole = async () => {
    try {
      const res = await apiFetch("/api/user/role");
      if (res.ok) {
        const data = await res.json();
        setUserRole(data);
        return data;
      }
    } catch (error) {
      console.error("Failed to fetch user role:", error);
    }
    return null;
  };

  const fetchGroups = async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const res = await apiFetch("/api/groups/");
      if (!res.ok) {
        const errorMsg = await getErrorMessage(translate, res, ADMIN_GROUPS.load_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      setGroups(data.groups || []);
      setSuccessMessage(translate(ADMIN_GROUPS.load_success));
    } catch (error: any) {
      console.error("Error fetching groups:", error);
      const msg = error.message || translate(ADMIN_GROUPS.load_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setLoading(false);
    }
  };

  const fetchGroupUsers = async (groupId: string) => {
    try {
      setErrorMessage(null);
      const res = await apiFetch(`/api/admin/groups/users?groupId=${encodeURIComponent(groupId)}`);
      if (!res.ok) {
        const errorMsg = await getErrorMessage(translate, res, ADMIN_GROUPS.group_users_load_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      setGroupUsers(data.users || []);
      setCurrentGroupId(data.groupId || groupId);
      setCurrentGroupDescription(data.groupDescription || "");
    } catch (error: any) {
      const msg = error.message || translate(ADMIN_GROUPS.group_users_load_error);
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const fetchUserRoleAndData = async () => {
    await fetchLanguages();
    const role = await fetchUserRole();
    if (role) {
      await fetchGroups();
      if (role.isAdmin) {
        const res = await apiFetch("/api/groups/");
        if (res.ok) {
          const data = await res.json();
          if (data.groups && data.groups.length > 0) {
            await fetchGroupUsers(data.groups[0].groupId);
          }
        }
      } else {
        await fetchGroupUsers("");
      }
    }
  };

  useEffect(() => {
    if (isLanguageLoaded) {
      fetchUserRoleAndData();
    }
  }, [isLanguageLoaded]);

  const handleEdit = (groupId: string, groupDescription: string) => {
    setEditing({ ...editing, [groupId]: true });
    setEditedDescriptions({ ...editedDescriptions, [groupId]: groupDescription });
  };

  const handleCancel = (groupId: string) => {
    setEditing({ ...editing, [groupId]: false });
    const original = groups.find(g => g.groupId === groupId);
    if (original) {
      setEditedDescriptions({ ...editedDescriptions, [groupId]: original.groupDescription });
    }
  };

  const handleSave = async (groupId: string) => {
    const newDescription = editedDescriptions[groupId];
    if (!newDescription || newDescription.trim() === "") {
      const msg = translate(ADMIN_GROUPS.description_required);
      setErrorMessage(msg);
      toast.error(msg);
      return;
    }

    setSaving({ ...saving, [groupId]: true });
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await apiFetch("/api/groups/description", {
        method: "PUT",
        body: JSON.stringify({
          group_id: groupId,
          description: newDescription.trim(),
        }),
      });
      if (!res.ok) {
        const errorMsg = await getErrorMessage(translate, res, ADMIN_GROUPS.update_error);
        throw new Error(errorMsg);
      }
      const msg = translate(ADMIN_GROUPS.update_success);
      setSuccessMessage(msg);
      toast.success(msg);
      setEditing({ ...editing, [groupId]: false });
      await fetchGroups();
      await fetchGroupUsers(currentGroupId);
    } catch (error: any) {
      const msg = error.message || translate(ADMIN_GROUPS.update_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setSaving({ ...saving, [groupId]: false });
    }
  };

  const handleEditUser = (user: GroupUser) => {
    setEditingUser(user.id);
    setEditingUserData({
      name: user.name || "",
      emailNotifications: user.emailNotifications,
      darkMode: user.darkMode,
      language: user.language || "en",
      maxUploadSizeMB: user.maxUploadSizeMB,
      maxUploadCount: user.maxUploadCount,
      isGroupAdmin: user.isGroupAdmin,
    });
  };

  const handleCancelEditUser = () => {
    setEditingUser(null);
    setEditingUserData({});
  };

  const handleSaveUser = async (userId: string) => {
    setSaving({ ...saving, [userId]: true });
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await apiFetch("/api/admin/groups/users", {
        method: "PATCH",
        body: JSON.stringify({
          userId,
          ...editingUserData,
        }),
      });
      if (!res.ok) {
        const errorMsg = await getErrorMessage(translate, res, ADMIN_USER_DETAILS.save_error);
        throw new Error(errorMsg);
      }
      const msg = translate(ADMIN_USER_DETAILS.save_success);
      setSuccessMessage(msg);
      toast.success(msg);
      setEditingUser(null);
      setEditingUserData({});
      await fetchGroupUsers(currentGroupId);
    } catch (error: any) {
      const msg = error.message || translate(ADMIN_USER_DETAILS.save_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setSaving({ ...saving, [userId]: false });
    }
  };

  const handleDeleteUser = async (user: GroupUser) => {
    setUserToDelete(user);
    setDeleteDialogOpen(true);
  };

  const confirmDeleteUser = async () => {
    if (!userToDelete) return;
    setDeleting(true);
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await apiFetch(`/api/admin/groups/users?userId=${userToDelete.id}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const errorMsg = await getErrorMessage(translate, res, ADMIN_GROUPS.delete_error);
        throw new Error(errorMsg);
      }
      const msg = translate(ADMIN_USERS.delete_success);
      setSuccessMessage(msg);
      toast.success(msg);
      setDeleteDialogOpen(false);
      setUserToDelete(null);
      await fetchGroupUsers(currentGroupId);
    } catch (error: any) {
      const msg = error.message || translate(ADMIN_USERS.delete_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setDeleting(false);
    }
  };

  const handlePromoteGroupAdmin = async (userId: string) => {
    setSaving({ ...saving, [userId]: true });
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await apiFetch("/api/admin/groups/promote", {
        method: "POST",
        body: JSON.stringify({ userId }),
      });
      if (!res.ok) {
        const errorMsg = await getErrorMessage(translate, res, ADMIN_GROUPS.promote_error);
        throw new Error(errorMsg);
      }
      const msg = translate(ADMIN_GROUPS.promote_success);
      setSuccessMessage(msg);
      toast.success(msg);
      await fetchGroupUsers(currentGroupId);
    } catch (error: any) {
      const msg = error.message || translate(ADMIN_GROUPS.promote_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setSaving({ ...saving, [userId]: false });
    }
  };

  const handleDemoteGroupAdmin = async (userId: string) => {
    setSaving({ ...saving, [userId]: true });
    setErrorMessage(null);
    setSuccessMessage(null);

    try {
      const res = await apiFetch(`/api/admin/groups/promote?userId=${userId}`, {
        method: "DELETE",
      });
      if (!res.ok) {
        const errorMsg = await getErrorMessage(translate, res, ADMIN_GROUPS.demote_error);
        throw new Error(errorMsg);
      }
      const msg = translate(ADMIN_GROUPS.demote_success);
      setSuccessMessage(msg);
      toast.success(msg);
      await fetchGroupUsers(currentGroupId);
    } catch (error: any) {
      const msg = error.message || translate(ADMIN_GROUPS.demote_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setSaving({ ...saving, [userId]: false });
    }
  };

  const handleGroupSelect = (groupId: string) => {
    if (groupId) {
      fetchGroupUsers(groupId);
    }
  };

  const isFullAdmin = userRole?.isAdmin === true;
  const isGroupAdminUser = userRole?.isGroupAdmin === true;
  const isExampleUserFlag = userRole?.isExampleUser === true;

  if (!isLanguageLoaded || loading) {
    return (
      <div className="flex items-center justify-center h-64">
        <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
      </div>
    );
  }

  const canEditGroups = isFullAdmin;

  return (
    <div className="max-w-6xl mx-auto space-y-6">
      <div className="flex justify-between items-center">
        <h1 className="text-3xl font-bold">
          {isExampleUserFlag ? translate(ADMIN_GROUPS.readonly_title) : translate(ADMIN_GROUPS.title)}
        </h1>
        <Button variant="outline" onClick={() => router.push("/admin")}>
          {translate(ADMIN_GROUPS.back_to_admin)}
        </Button>
      </div>

      {isExampleUserFlag && (
        <div className="p-3 bg-orange-50 border border-orange-200 rounded-md text-orange-800">
          <span className="text-sm">{translate(ADMIN_GROUPS.readonly_message)}</span>
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
            <XCircle className="h-5 w-5" />
          </button>
        </div>
      )}

      {isFullAdmin && (
        <Card>
          <CardHeader>
            <CardTitle>{translate(ADMIN_GROUPS.select_group)}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="w-full md:w-64">
              <Select
                value={currentGroupId}
                onValueChange={(value) => handleGroupSelect(value || "")}
              >
                <SelectTrigger>
                  <SelectValue placeholder={translate(ADMIN_GROUPS.select_group_placeholder)} />
                </SelectTrigger>
                <SelectContent>
                  {groups.map((group) => (
                    <SelectItem key={group.groupId} value={group.groupId}>
                      {group.groupId} - {group.groupDescription}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
          </CardContent>
        </Card>
      )}

      {isFullAdmin && (
        <Card>
          <CardHeader>
            <CardTitle>{translate(ADMIN_GROUPS.group_description)}</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-4">
              <div className="flex-shrink-0 w-12 text-center">
                <span className="font-mono text-sm font-medium bg-muted px-2 py-1 rounded">
                  {currentGroupId}
                </span>
              </div>
              <div className="flex-1">
                {editing[currentGroupId] ? (
                  <Input dir="auto"
                    value={editedDescriptions[currentGroupId] || ""}
                    onChange={(e) =>
                      setEditedDescriptions({
                        ...editedDescriptions,
                        [currentGroupId]: e.target.value,
                      })
                    }
                    placeholder={translate(ADMIN_GROUPS.description_placeholder)}
                    className="w-full"
                    autoFocus
                    disabled={isExampleUserFlag}
                  />
                ) : (
                  <span>
                    {currentGroupDescription}
                  </span>
                )}
              </div>
              <div className="flex-shrink-0 flex gap-2">
                {editing[currentGroupId] ? (
                  <>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => handleSave(currentGroupId)}
                      disabled={saving[currentGroupId] || isExampleUserFlag}
                    >
                      {saving[currentGroupId] ? (
                        <Loader2 className="h-4 w-4 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4" />
                      )}
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => handleCancel(currentGroupId)}
                    >
                      <X className="h-4 w-4" />
                    </Button>
                  </>
                ) : (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => handleEdit(currentGroupId, currentGroupDescription)}
                    disabled={!canEditGroups || isExampleUserFlag}
                  >
                    {translate(COMMON.edit)}
                  </Button>
                )}
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle className="flex items-center gap-2">
            <Users className="h-5 w-5" />
            {translate(ADMIN_GROUPS.users_in_group)} {currentGroupId}
            {currentGroupDescription && ` - ${currentGroupDescription}`}
          </CardTitle>
        </CardHeader>
        <CardContent>
          {groupUsers.length === 0 ? (
            <p className="text-center text-muted-foreground py-4">
              {translate(ADMIN_GROUPS.no_users)}
            </p>
          ) : (
            <div className="space-y-4">
              {groupUsers.map((user) => {
                const isEditing = editingUser === user.id;
                const isFullAdminUser = user.isAdmin;
                const isGroupAdminUserFlag = user.isGroupAdmin;
                const isExampleUserFlagUser = user.isExampleUser;
                const isDeleted = user.deletedAt !== null;

                return (
                  <div
                    key={user.id}
                    className={`border rounded-lg p-4 ${
                      isDeleted ? "bg-amber-50/50 border-amber-200" : ""
                    }`}
                  >
                    {isEditing ? (
                      <div className="space-y-3">
                        <div className="flex items-center gap-2">
                          <User className="h-4 w-4 text-muted-foreground" />
                          <Input dir="auto"
                            value={editingUserData.name || ""}
                            onChange={(e) =>
                              setEditingUserData({
                                ...editingUserData,
                                name: e.target.value,
                              })
                            }
                            placeholder={translate(PROFILE_SETTINGS.name_label)}
                            className="w-48"
                            disabled={isExampleUserFlag}
                          />
                          <span className="text-sm text-muted-foreground">{user.email}</span>
                        </div>
                        <div className="flex flex-wrap items-center gap-4">
                          <div className="flex items-center gap-2">
                            <Switch
                              checked={editingUserData.emailNotifications || false}
                              onCheckedChange={(checked) =>
                                setEditingUserData({
                                  ...editingUserData,
                                  emailNotifications: checked,
                                })
                              }
                              disabled={isExampleUserFlag}
                            />
                            <span className="text-sm">{translate(PROFILE_SETTINGS.email_notifications_label)}</span>
                          </div>
                          <div className="flex items-center gap-2">
                            <Switch
                              checked={editingUserData.darkMode || false}
                              onCheckedChange={(checked) =>
                                setEditingUserData({
                                  ...editingUserData,
                                  darkMode: checked,
                                })
                              }
                              disabled={isExampleUserFlag}
                            />
                            <span className="text-sm">{translate(PROFILE_SETTINGS.dark_mode_label)}</span>
                          </div>
                          <Select
                            value={editingUserData.language || "en"}
                            onValueChange={(value) => {
                              if (value) {
                                setEditingUserData({
                                  ...editingUserData,
                                  language: value,
                                });
                              }
                            }}
                            disabled={isExampleUserFlag}
                          >
                            <SelectTrigger className="w-32">
                              <SelectValue placeholder={translate(PROFILE_SETTINGS.language_label)} />
                            </SelectTrigger>
                            <SelectContent>
                              {languages.map((lang) => (
                                <SelectItem key={lang.code} value={lang.code}>
                                  {lang.name}
                                </SelectItem>
                              ))}
                            </SelectContent>
                          </Select>
                        </div>
                        <div className="flex items-center gap-2">
                          <Button
                            size="sm"
                            onClick={() => handleSaveUser(user.id)}
                            disabled={saving[user.id] || isExampleUserFlag}
                          >
                            {saving[user.id] ? (
                              <Loader2 className="h-4 w-4 animate-spin" />
                            ) : (
                              translate(COMMON.save)
                            )}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={handleCancelEditUser}
                          >
                            {translate(COMMON.cancel)}
                          </Button>
                        </div>
                      </div>
                    ) : (
                      <div className="flex flex-wrap justify-between items-center gap-4">
                        <div>
                          <div className="flex items-center gap-2">
                            <span className="font-medium">{user.name || translate(ADMIN_USERS.no_name)}</span>
                            {user.isAdmin && (
                              <span className="text-xs bg-purple-100 text-purple-800 px-2 py-0.5 rounded">
                                {translate(ADMIN_USERS.admin_badge)}
                              </span>
                            )}
                            {user.isGroupAdmin && !user.isAdmin && (
                              <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">
                                {translate(ADMIN_USERS.group_admin_badge)}
                              </span>
                            )}
                            {user.isExampleUser && (
                              <span className="text-xs bg-orange-100 text-orange-800 px-2 py-0.5 rounded">
                                {translate(ADMIN_USERS.example_user_badge)}
                              </span>
                            )}
                            {isDeleted && (
                              <span className="text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded">
                                {translate(ADMIN_USERS.deleted_badge)}
                              </span>
                            )}
                          </div>
                          <p className="text-sm text-muted-foreground">{user.email}</p>
                          <p className="text-xs text-muted-foreground">
                            {translate(ADMIN_USERS.created_label)}: {formatDate(user.createdAt)}
                          </p>
                        </div>
                        <div className="flex items-center gap-2 flex-wrap">
                          {!user.isAdmin && !user.isExampleUser && (
                            <>
                              {user.isGroupAdmin ? (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handleDemoteGroupAdmin(user.id)}
                                  disabled={saving[user.id] || isExampleUserFlag}
                                  className="border-amber-500 text-amber-600 hover:bg-amber-50"
                                >
                                  <Shield className="h-4 w-4 me-1" />
                                  {translate(ADMIN_GROUPS.demote)}
                                </Button>
                              ) : (
                                <Button
                                  variant="outline"
                                  size="sm"
                                  onClick={() => handlePromoteGroupAdmin(user.id)}
                                  disabled={saving[user.id] || isExampleUserFlag}
                                  className="border-blue-500 text-blue-600 hover:bg-blue-50"
                                >
                                  <Shield className="h-4 w-4 me-1" />
                                  {translate(ADMIN_GROUPS.promote)}
                                </Button>
                              )}
                            </>
                          )}
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleEditUser(user)}
                            disabled={isExampleUserFlag}
                          >
                            <Edit className="h-4 w-4 me-1" />
                            {translate(COMMON.edit)}
                          </Button>
                          {!user.isAdmin && !isDeleted && (
                            <Button
                              variant="destructive"
                              size="sm"
                              onClick={() => handleDeleteUser(user)}
                              disabled={isExampleUserFlag}
                            >
                              <Trash2 className="h-4 w-4 me-1" />
                              {translate(COMMON.delete)}
                            </Button>
                          )}
                        </div>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>{translate(ADMIN_GROUPS.delete_title)}</AlertDialogTitle>
            <AlertDialogDescription>
              {translate(ADMIN_GROUPS.delete_confirmation).replace("{name}", userToDelete?.name || userToDelete?.email || "")}
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel>{translate(COMMON.cancel)}</AlertDialogCancel>
            <AlertDialogAction onClick={confirmDeleteUser} disabled={deleting}>
              {deleting ? translate(COMMON.deleting) : translate(COMMON.delete)}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}

export default function AdminGroupsPage() {
  return (
    <ProtectedRoute>
      <AdminGroupsContent />
    </ProtectedRoute>
  );
}