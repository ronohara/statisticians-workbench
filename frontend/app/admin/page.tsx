"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useSession } from "next-auth/react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Switch } from "@/components/ui/switch";
import { toast } from "sonner";
import { ProtectedRoute } from "@/components/protected-route";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate, getErrorMessageFromData } from "@/lib/translation-helpers";
import { apiFetch } from "@/lib/api";
import { XCircle, RotateCcw, Trash2, Lock, UserPlus } from "lucide-react";
import Link from "next/link";
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

// Import translations for this module
import { ADMIN } from "./translations";
import { COMMON } from "@/app/common/translations";
import { COMPONENTS } from "@/components/translations";
import { formatDate } from "@/lib/date-format";

interface User {
  id: string;
  email: string;
  name: string | null;
  isAdmin: boolean;
  isGroupAdmin: boolean;
  isExampleUser: boolean;
  emailVerified: string | null;
  bccRegistrations: boolean;
  createdAt: string;
  deletedAt: string | null;
}

function AdminContent() {
  const router = useRouter();
  const { data: session } = useSession();
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [restoringUserId, setRestoringUserId] = useState<string | null>(null);
  const [deleteDialogOpen, setDeleteDialogOpen] = useState(false);
  const [userToDelete, setUserToDelete] = useState<User | null>(null);
  const [hardDeleteDialogOpen, setHardDeleteDialogOpen] = useState(false);
  const [userToHardDelete, setUserToHardDelete] = useState<User | null>(null);
  const [userRole, setUserRole] = useState<{ isAdmin: boolean; isGroupAdmin: boolean; isExampleUser: boolean } | null>(null);
  const [loadingRole, setLoadingRole] = useState(true);

  const isExampleUser = userRole?.isExampleUser === true;
  const isAdmin = userRole?.isAdmin === true;

  const fetchUsers = async () => {
    try {
      setLoading(true);
      setErrorMessage(null);
      const res = await apiFetch("/api/admin/users");
      if (res.status === 401 || res.status === 403) {
        router.push("/login");
        return;
      }
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.users.load_error);
        throw new Error(errorMsg);
      }
      const data = await res.json();
      setUsers(data.users);
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.users.load_error);
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
    fetchUsers();
  }, []);

  const handleToggleAdmin = async (userId: string, currentIsAdmin: boolean) => {
    try {
      const res = await apiFetch("/api/admin/users", {
        method: "PATCH",
        body: JSON.stringify({ userId, isAdmin: !currentIsAdmin }),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.users.update_error);
        throw new Error(errorMsg);
      }
      toast.success(translate(ADMIN.users.update_success));
      fetchUsers();
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.users.update_error);
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const handleToggleBcc = async (userId: string, currentValue: boolean) => {
    try {
      const res = await apiFetch("/api/admin/users", {
        method: "PATCH",
        body: JSON.stringify({ userId, bccRegistrations: !currentValue }),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.users.bcc_updated);
        throw new Error(errorMsg);
      }
      toast.success(translate(ADMIN.users.bcc_updated));
      fetchUsers();
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.users.update_error);
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const handleVerifyUser = async (userId: string) => {
    try {
      const res = await apiFetch("/api/admin/users", {
        method: "PATCH",
        body: JSON.stringify({ userId, verify: true }),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.users.verify_error);
        throw new Error(errorMsg);
      }
      toast.success(translate(ADMIN.users.verify_success));
      fetchUsers();
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.users.verify_error);
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const handleRestoreUser = async (userId: string) => {
    setRestoringUserId(userId);
    try {
      const res = await apiFetch("/api/admin/users", {
        method: "PATCH",
        body: JSON.stringify({ userId, restore: true }),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.users.restore_error);
        throw new Error(errorMsg);
      }
      toast.success(translate(ADMIN.users.restore_success));
      fetchUsers();
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.users.restore_error);
      setErrorMessage(msg);
      toast.error(msg);
    } finally {
      setRestoringUserId(null);
    }
  };

  const handleDeleteClick = (user: User) => {
    setUserToDelete(user);
    setDeleteDialogOpen(true);
  };

  const confirmDelete = async () => {
    if (!userToDelete) return;
    try {
      const res = await apiFetch("/api/admin/users", {
        method: "DELETE",
        body: JSON.stringify({ userId: userToDelete.id }),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.users.delete_error);
        throw new Error(errorMsg);
      }
      toast.success(translate(ADMIN.users.delete_success));
      setDeleteDialogOpen(false);
      setUserToDelete(null);
      fetchUsers();
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.users.delete_error);
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const handleHardDeleteClick = (user: User) => {
    setUserToHardDelete(user);
    setHardDeleteDialogOpen(true);
  };

  const confirmHardDelete = async () => {
    if (!userToHardDelete) return;
    try {
      const res = await apiFetch("/api/admin/users", {
        method: "PATCH",
        body: JSON.stringify({ userId: userToHardDelete.id, hardDelete: true }),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.users.hard_delete_error);
        throw new Error(errorMsg);
      }
      toast.success(translate(ADMIN.users.hard_delete_success));
      setHardDeleteDialogOpen(false);
      setUserToHardDelete(null);
      fetchUsers();
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.users.hard_delete_error);
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const handleResendVerification = async (email: string) => {
    try {
      const res = await fetch("/api/auth/verify-request", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ email }),
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
        const errorMsg = getErrorMessageFromData(translate, errorData, ADMIN.users.resend_error);
        throw new Error(errorMsg);
      }
      const baseMsg = translate(ADMIN.users.resend_success);
      const successMsg = baseMsg.replace("{email}", email);
      toast.success(successMsg);
    } catch (error: any) {
      const msg = error.message || translate(ADMIN.users.resend_error);
      setErrorMessage(msg);
      toast.error(msg);
    }
  };

  const dismissError = () => setErrorMessage(null);

  if (!isLanguageLoaded || loading || loadingRole) {
    return <div className="p-8">{translate(COMMON.loading)}</div>;
  }

  // Admin or Example User - show full view (Example Users get disabled controls)
  if (isAdmin || isExampleUser) {
    const activeUsers = users.filter(u => u.deletedAt === null);
    const deletedUsers = users.filter(u => u.deletedAt !== null);

    return (
      <div className="max-w-5xl mx-auto space-y-6">
        <h1 className="text-3xl font-bold">{translate(ADMIN.title)}</h1>

        {isExampleUser && (
          <div className="p-4 bg-orange-50 border border-orange-200 rounded-md text-orange-800 text-center">
            <Lock className="h-6 w-6 mx-auto mb-2 text-orange-600" />
            <p className="text-sm mb-3">
              {translate(COMPONENTS.readonly_wrapper)}
            </p>
            <Link href="/register">
              <Button size="sm">
                <UserPlus className="h-4 w-4 me-2" />
                {translate(COMPONENTS.example_user_banner.register_button)}
              </Button>
            </Link>
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

        <Card>
          <CardHeader className="flex flex-row items-center justify-between">
            <CardTitle>{translate(ADMIN.users.title)}</CardTitle>
            <Link href="/adduser">
              <Button size="sm">
                <UserPlus className="h-4 w-4 me-2" />
                {translate(ADMIN.users.add_user)}
              </Button>
            </Link>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {/* Active Users */}
              <h3 className="text-sm font-medium text-muted-foreground">{translate(ADMIN.users.active_users)}</h3>
              {activeUsers.map((user) => {
                const isVerified = user.emailVerified !== null && user.emailVerified !== "" && user.emailVerified !== "null";
                const isCurrentUser = user.email === session?.user?.email;
                const showBccToggle = isExampleUser || (isVerified && user.isAdmin);

                return (
                  <div
                    key={user.id}
                    className="border rounded-lg p-4 flex flex-wrap justify-between items-center gap-4"
                  >
                    <div>
                      <p className="font-medium">{user.name || translate(ADMIN.users.no_name)}</p>
                      <p className="text-sm text-muted-foreground">{user.email}</p>
                      <p className="text-xs text-muted-foreground">
                        {translate(ADMIN.users.created_label)}: {formatDate(user.createdAt)}
                      </p>
                      {user.isAdmin && (
                        <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">{translate(ADMIN.users.admin_badge)}</span>
                      )}
                      {user.isGroupAdmin && (
                        <span className="inline-flex items-center ms-2 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
                          <span className="me-1">👥</span>
                          {translate(ADMIN.users.group_admin_badge)}
                        </span>
                      )}
                      {user.isExampleUser && (
                        <span className="inline-flex items-center ms-2 px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800 border border-orange-200">
                          <span className="me-1">🔒</span>
                          {translate(ADMIN.users.example_user_badge)}
                        </span>
                      )}
                      {!isVerified && (
                        <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded ms-2">
                          {translate(ADMIN.users.unverified_badge)}
                        </span>
                      )}
                      {isVerified && (
                        <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded ms-2">
                          {translate(ADMIN.users.verified_badge)}
                        </span>
                      )}
                    </div>
                    <div className="flex gap-2 flex-wrap items-center">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => router.push(`/admin/users/${user.id}`)}
                      >
                        {translate(ADMIN.users.more_button)}
                      </Button>

                      {!isVerified && (
                        <>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleVerifyUser(user.id)}
                            disabled={isExampleUser}
                          >
                            {translate(ADMIN.users.verify_button)}
                          </Button>
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleResendVerification(user.email)}
                            disabled={isExampleUser}
                          >
                            {translate(ADMIN.users.resend_button)}
                          </Button>
                        </>
                      )}
                      {showBccToggle && (
                        <div className="flex items-center gap-2">
                          <span className="text-sm">{translate(ADMIN.users.bcc_label)}</span>
                          <Switch
                            checked={user.bccRegistrations}
                            onCheckedChange={() => handleToggleBcc(user.id, user.bccRegistrations)}
                            disabled={isExampleUser}
                          />
                        </div>
                      )}
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => handleToggleAdmin(user.id, user.isAdmin)}
                        disabled={isExampleUser}
                      >
                        {user.isAdmin ? translate(ADMIN.users.remove_admin) : translate(ADMIN.users.make_admin)}
                      </Button>
                      <Button
                        variant="destructive"
                        size="sm"
                        onClick={() => handleDeleteClick(user)}
                        disabled={isExampleUser || isCurrentUser}
                      >
                        {translate(ADMIN.users.delete_button)}
                      </Button>
                    </div>
                  </div>
                );
              })}

              {/* Soft-Deleted Users */}
              {deletedUsers.length > 0 && (
                <>
                  <hr className="my-4" />
                  <h3 className="text-sm font-medium text-amber-600">{translate(ADMIN.users.soft_deleted_users)}</h3>
                  {deletedUsers.map((user) => {
                    const isVerified = user.emailVerified !== null && user.emailVerified !== "" && user.emailVerified !== "null";

                    return (
                      <div
                        key={user.id}
                        className="border rounded-lg p-4 flex flex-wrap justify-between items-center gap-4 bg-amber-50/50 border-amber-200"
                      >
                        <div>
                          <p className="font-medium text-amber-700">{user.name || translate(ADMIN.users.no_name)}</p>
                          <p className="text-sm text-muted-foreground">{user.email}</p>
                          <p className="text-xs text-muted-foreground">
                            {translate(ADMIN.users.deleted_label)}: {user.deletedAt ? formatDate(user.deletedAt) : translate(COMMON.unknown_error)}
                          </p>
                           {user.isAdmin && (
                             <span className="text-xs bg-blue-100 text-blue-800 px-2 py-0.5 rounded">{translate(ADMIN.users.admin_badge)}</span>
                           )}
                           {user.isGroupAdmin && (
                             <span className="inline-flex items-center ms-2 px-2.5 py-0.5 rounded-full text-xs font-medium bg-blue-100 text-blue-800 border border-blue-200">
                               <span className="me-1">👥</span>
                               {translate(ADMIN.users.group_admin_badge)}
                             </span>
                           )}
                           {user.isExampleUser && (
                             <span className="inline-flex items-center ms-2 px-2.5 py-0.5 rounded-full text-xs font-medium bg-orange-100 text-orange-800 border border-orange-200">
                               <span className="me-1">🔒</span>
                               {translate(ADMIN.users.example_user_badge)}
                             </span>
                           )}
                           {!isVerified && (
                             <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-0.5 rounded ms-2">
                               {translate(ADMIN.users.unverified_badge)}
                             </span>
                           )}
                           {isVerified && (
                             <span className="text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded ms-2">
                               {translate(ADMIN.users.verified_badge)}
                             </span>
                           )}
                           <span className="text-xs bg-amber-100 text-amber-800 px-2 py-0.5 rounded ms-2">
                             {translate(ADMIN.users.deleted_badge)}
                           </span>
                        </div>
                        <div className="flex gap-2 flex-wrap items-center">
                          <Button
                            variant="outline"
                            size="sm"
                            onClick={() => handleRestoreUser(user.id)}
                            disabled={isExampleUser || restoringUserId === user.id}
                            className="border-green-500 text-green-600 hover:bg-green-50"
                          >
                            <RotateCcw className="h-4 w-4 me-1" />
                            {restoringUserId === user.id ? translate(COMMON.restoring) : translate(ADMIN.users.restore_button)}
                          </Button>

                          {!isVerified && (
                            <>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleVerifyUser(user.id)}
                                disabled={isExampleUser}
                              >
                                {translate(ADMIN.users.verify_button)}
                              </Button>
                              <Button
                                variant="outline"
                                size="sm"
                                onClick={() => handleResendVerification(user.email)}
                                disabled={isExampleUser}
                              >
                                {translate(ADMIN.users.resend_button)}
                              </Button>
                            </>
                          )}

                          {user.isAdmin && (
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={() => handleToggleAdmin(user.id, user.isAdmin)}
                              disabled={isExampleUser}
                            >
                              {translate(ADMIN.users.remove_admin)}
                            </Button>
                          )}

                          <Button
                            variant="destructive"
                            size="sm"
                            onClick={() => handleHardDeleteClick(user)}
                            disabled={isExampleUser}
                          >
                            <Trash2 className="h-4 w-4 me-1" />
                            {translate(ADMIN.users.hard_delete_button)}
                          </Button>
                        </div>
                      </div>
                    );
                  })}
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Delete Confirmation Dialog (Hard Delete from Admin) */}
        <AlertDialog open={deleteDialogOpen} onOpenChange={setDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{translate(ADMIN.users.delete_title)}</AlertDialogTitle>
              <AlertDialogDescription>
                {translate(ADMIN.users.delete_confirmation).replace("{name}", userToDelete?.name || userToDelete?.email || "this user")}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{translate(COMMON.cancel)}</AlertDialogCancel>
              <AlertDialogAction onClick={confirmDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                {translate(ADMIN.users.delete_button)}
              </AlertDialogAction>
            </AlertDialogFooter>
          </AlertDialogContent>
        </AlertDialog>

        {/* Hard Delete Confirmation Dialog (Soft-deleted user) */}
        <AlertDialog open={hardDeleteDialogOpen} onOpenChange={setHardDeleteDialogOpen}>
          <AlertDialogContent>
            <AlertDialogHeader>
              <AlertDialogTitle>{translate(ADMIN.users.hard_delete_title)}</AlertDialogTitle>
              <AlertDialogDescription>
                {translate(ADMIN.users.hard_delete_confirmation).replace("{name}", userToHardDelete?.name || userToHardDelete?.email || "this user")}
              </AlertDialogDescription>
            </AlertDialogHeader>
            <AlertDialogFooter>
              <AlertDialogCancel>{translate(COMMON.cancel)}</AlertDialogCancel>
              <AlertDialogAction onClick={confirmHardDelete} className="bg-destructive text-destructive-foreground hover:bg-destructive/90">
                {translate(ADMIN.users.hard_delete_button)}
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

export default function AdminPage() {
  return (
    <ProtectedRoute>
      <AdminContent />
    </ProtectedRoute>
  );
}