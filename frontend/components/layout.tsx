"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import {
  Home,
  Settings,
  LayoutDashboard,
  Info,
  LogOut,
  Shield,
  BookOpen,
  Wrench,
  MessageSquare,
  ChevronDown,
  ChevronRight,
  User,
  Database,
  Bot,
  Upload,
  Table,
  Users,
  FolderOpen,
  FileSpreadsheet,
  Menu,
  X,
  Gauge,
  SlidersHorizontal,
  Sliders,
  Cpu,
  Layers,
} from "lucide-react";
import { useSession, signOut } from "next-auth/react";
import { useMobile } from "@/hooks/useMobile";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { useTranslation } from "@/lib/translation-context";
import { useTranslate } from "@/lib/translation-helpers";
import { useEffect, useState } from "react";
import { ExampleUserBadge } from "@/components/example-user-badge";
import { GroupAdminBadge } from "@/components/group-admin-badge";

// Import translations for this module
import { NAV } from "@/app/common/translations";
import { ADMIN } from "@/app/admin/translations";
import { TOOLS } from "@/app/tools/translations";
import { SETTINGS } from "@/app/settings/translations";
import { RECIPES } from "@/app/recipes/translations";
import { APP, COMMON } from "@/app/common/translations";

export default function Layout({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const router = useRouter();
  const { data: session, status } = useSession();
  const { isLanguageLoaded } = useTranslation();
  const translate = useTranslate();
  const [version, setVersion] = useState("");
  const [adminExpanded, setAdminExpanded] = useState(false);
  const [setupExpanded, setSetupExpanded] = useState(false);
  const [settingsExpanded, setSettingsExpanded] = useState(false);
  const [toolsExpanded, setToolsExpanded] = useState(false);
  const [myDataExpanded, setMyDataExpanded] = useState(false);
  const [manageDataExpanded, setManageDataExpanded] = useState(false);
  const [aiChatExpanded, setAiChatExpanded] = useState(false);
  const [userRole, setUserRole] = useState<{ isAdmin: boolean; isGroupAdmin: boolean; isExampleUser: boolean } | null>(null);
  const isMobile = useMobile();
  const [mobileDrawerOpen, setMobileDrawerOpen] = useState(false);

  useEffect(() => {
    fetch("/api/version")
      .then(res => res.json())
      .then(versionData => setVersion(versionData.version || ""))
      .catch(console.error);
  }, []);

  useEffect(() => {
    const fetchUserRole = async () => {
      if (status === "authenticated" && session?.user?.id) {
        try {
          const res = await fetch("/api/user/role");
          if (res.ok) {
            const data = await res.json();
            setUserRole(data);
          }
        } catch (error) {
          console.error("Failed to fetch user role:", error);
        }
      }
    };
    fetchUserRole();
  }, [session, status]);

  // Auto-expand Admin and Setup when navigating to their child routes
  useEffect(() => {
    if (pathname.startsWith("/admin/") || pathname === "/admin" || pathname === "/licence") {
      setAdminExpanded(true);
    }
    if (pathname.startsWith("/admin/setup/") || pathname === "/licence") {
      setSetupExpanded(true);
    }
  }, [pathname]);

  const isActive = (href: string) => {
    if (href === "/") return pathname === "/";
    return pathname.startsWith(href);
  };

  const isChildActive = (href: string) => pathname.startsWith(href);

  // The manual virtual-dataset editor hangs off the AI virtual-dataset route
  // (/datasets/virtual/manual) but is its own nav entry, so the AI link must not
  // light up while the manual editor is open.
  const isAiVirtualActive = () =>
    isChildActive("/datasets/virtual") && !isChildActive("/datasets/virtual/manual");

  const handleLogout = async () => {
    await signOut({ redirect: false });
    router.push("/login");
  };

  const isAuthPage = pathname === "/login" || pathname === "/register"
    || pathname === "/forgot-password" || pathname === "/reset-password"
    || pathname === "/verify-email" || pathname === "/resend-verification";
  if (isAuthPage) {
    return <main className="min-h-screen">{children}</main>;
  }

  const isAdmin = session?.user?.isAdmin === true;
  const isExampleUserFlag = userRole?.isExampleUser === true;
  const isGroupAdminUser = userRole?.isGroupAdmin === true;

  if (!isLanguageLoaded) {
    return (
      <div className="flex items-center justify-center h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-primary mx-auto"></div>
          <p className="mt-2 text-sm text-muted-foreground">{translate(APP.name)}</p>
        </div>
      </div>
    );
  }

  return (
    <>
      {/* Mobile header */}
      {isMobile && (
        <header className="fixed top-0 start-0 end-0 z-40 flex items-center justify-between h-14 px-4 bg-background border-b shadow-sm">
          <Button variant="ghost" size="icon" onClick={() => setMobileDrawerOpen(true)} aria-label={translate(COMMON.open_navigation)}>
            <Menu className="h-5 w-5" />
          </Button>
          <span className="font-semibold text-sm">{translate(APP.name)}</span>
          <div className="w-9" /> {/* spacer for centering */}
        </header>
      )}

      {/* Mobile drawer overlay */}
      {isMobile && mobileDrawerOpen && (
        <div className="fixed inset-0 z-50 md:hidden">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setMobileDrawerOpen(false)}
          />
          {/* Drawer */}
          <aside className="absolute start-0 top-0 bottom-0 w-64 bg-background border-e shadow-xl flex flex-col p-4 z-50">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <LayoutDashboard className="h-5 w-5" />
                <span className="font-semibold text-sm">{translate(APP.name)}</span>
              </div>
              <Button variant="ghost" size="icon" onClick={() => setMobileDrawerOpen(false)} aria-label={translate(COMMON.close_navigation)}>
                <X className="h-5 w-5" />
              </Button>
            </div>
            <nav className="flex-1 overflow-y-auto space-y-1">
              <Link href="/" className="block" onClick={() => setMobileDrawerOpen(false)}>
                <Button variant={isActive("/") ? "secondary" : "ghost"} className="w-full justify-start">
                  <Home className="me-2 h-4 w-4" />
                  {translate(NAV.home)}
                </Button>
              </Link>

              <Link href="/recipes" className="block" onClick={() => setMobileDrawerOpen(false)}>
                <Button variant={isChildActive("/recipes") ? "secondary" : "ghost"} className="w-full justify-start text-sm">
                  <BookOpen className="me-2 h-4 w-4" />
                  {translate(RECIPES.title)}
                </Button>
              </Link>

              {/* AI Chat expandable section (mobile) */}
              <div className="space-y-1">
                <Button
                  variant="ghost"
                  className="w-full justify-start text-sm"
                  onClick={() => setAiChatExpanded(!aiChatExpanded)}
                >
                  <MessageSquare className="me-2 h-4 w-4" />
                  {translate(NAV.ai_chat)}
                  <span className="ms-auto">
                    {aiChatExpanded ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4 rtl:rotate-180" />
                    )}
                  </span>
                </Button>
                {aiChatExpanded && (
                  <div className="ms-4 ps-2 border-s border-muted-foreground/20 space-y-1">
                    <Link href="/chat" className="block" onClick={() => setMobileDrawerOpen(false)}>
                      <Button
                        variant={isChildActive("/chat") ? "secondary" : "ghost"}
                        className="w-full justify-start text-sm"
                      >
                        <span className="me-2">💬</span>
                        {translate(NAV.ai_general)}
                      </Button>
                    </Link>
                    <Link href="/aitesting" className="block" onClick={() => setMobileDrawerOpen(false)}>
                      <Button
                        variant={isChildActive("/aitesting") ? "secondary" : "ghost"}
                        className="w-full justify-start text-sm"
                      >
                        <span className="me-2">🧪</span>
                        {translate(NAV.ai_testing)}
                      </Button>
                    </Link>
                    <Link href="/ai/database" className="block" onClick={() => setMobileDrawerOpen(false)}>
                      <Button
                        variant={isChildActive("/ai/database") ? "secondary" : "ghost"}
                        className="w-full justify-start text-sm"
                      >
                        <span className="me-2">🗄️</span>
                        {translate(NAV.ai_database_design)}
                      </Button>
                    </Link>
                    <Link href="/datasets/virtual" className="block" onClick={() => setMobileDrawerOpen(false)}>
                      <Button
                        variant={isAiVirtualActive() ? "secondary" : "ghost"}
                        className="w-full justify-start text-sm"
                      >
                        <span className="me-2">🔗</span>
                        {translate(NAV.ai_virtual_datasets)}
                      </Button>
                    </Link>
                    <Link href="/ai/dataclean" className="block" onClick={() => setMobileDrawerOpen(false)}>
                      <Button
                        variant={isChildActive("/ai/dataclean") ? "secondary" : "ghost"}
                        className="w-full justify-start text-sm"
                      >
                        <span className="me-2">🧹</span>
                        {translate(NAV.ai_dataset_cleaning)}
                      </Button>
                    </Link>
                    <Link href="/ai/recipe" className="block" onClick={() => setMobileDrawerOpen(false)}>
                      <Button
                        variant={isChildActive("/ai/recipe") ? "secondary" : "ghost"}
                        className="w-full justify-start text-sm"
                      >
                        <span className="me-2">📊</span>
                        {translate(NAV.ai_analysis_rules)}
                      </Button>
                    </Link>
                  </div>
                )}
              </div>

              {/* Tools expandable section (mobile) */}
              <div className="space-y-1">
                <Button
                  variant="ghost"
                  className="w-full justify-start text-sm"
                  onClick={() => setToolsExpanded(!toolsExpanded)}
                >
                  <Wrench className="me-2 h-4 w-4" />
                  {translate(TOOLS.title)}
                  <span className="ms-auto">
                    {toolsExpanded ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4 rtl:rotate-180" />
                    )}
                  </span>
                </Button>
                {toolsExpanded && (
                  <div className="ms-4 ps-2 border-s border-muted-foreground/20 space-y-1">

                    {/* Visualization Sandbox */}
                    <Link href="/visualize" className="block" onClick={() => setMobileDrawerOpen(false)}>
                      <Button variant={isChildActive("/visualize") ? "secondary" : "ghost"} className="w-full justify-start text-sm">
                        <span className="me-2">📊</span>
                        {translate(TOOLS.visualize)}
                      </Button>
                    </Link>

                    {/* My Data expandable */}
                    <div className="space-y-1">
                      <Button
                        variant="ghost"
                        className="w-full justify-start text-sm"
                        onClick={() => setMyDataExpanded(!myDataExpanded)}
                      >
                        <FolderOpen className="me-2 h-4 w-4" />
                        {translate(TOOLS.my_data)}
                        <span className="ms-auto">
                          {myDataExpanded ? (
                            <ChevronDown className="h-3 w-3" />
                          ) : (
                            <ChevronRight className="h-3 w-3 rtl:rotate-180" />
                          )}
                        </span>
                      </Button>
                      {myDataExpanded && (
                        <div className="ms-3 ps-2 border-s border-muted-foreground/10 space-y-1">
                          <Link href="/datasets/manage" className="block" onClick={() => setMobileDrawerOpen(false)}>
                            <Button variant={isChildActive("/datasets/manage") ? "secondary" : "ghost"} className="w-full justify-start text-xs">
                              <Table className="me-2 h-3 w-3" />
                              {translate(TOOLS.all_datasets)}
                            </Button>
                          </Link>
                          <Link href="/datasets/uploaded" className="block" onClick={() => setMobileDrawerOpen(false)}>
                            <Button variant={isChildActive("/datasets/uploaded") ? "secondary" : "ghost"} className="w-full justify-start text-xs">
                              <FileSpreadsheet className="me-2 h-3 w-3" />
                              {translate(TOOLS.uploads_list)}
                            </Button>
                          </Link>
                          <Link href="/notebooks" className="block" onClick={() => setMobileDrawerOpen(false)}>
                            <Button variant={isChildActive("/notebooks") ? "secondary" : "ghost"} className="w-full justify-start text-xs">
                              <BookOpen className="me-2 h-3 w-3" />
                              {translate(TOOLS.notebooks)}
                            </Button>
                          </Link>
                          <Link href="/datasets/virtual/manual" className="block" onClick={() => setMobileDrawerOpen(false)}>
                            <Button variant={isChildActive("/datasets/virtual/manual") ? "secondary" : "ghost"} className="w-full justify-start text-xs">
                              <Layers className="me-2 h-3 w-3" />
                              {translate(NAV.ai_virtual_datasets)}
                            </Button>
                          </Link>
                        </div>
                      )}
                    </div>

                    {/* Manage Data expandable */}
                    <div className="space-y-1">
                      <Button
                        variant="ghost"
                        className="w-full justify-start text-sm"
                        onClick={() => setManageDataExpanded(!manageDataExpanded)}
                      >
                        <Wrench className="me-2 h-4 w-4" />
                        {translate(TOOLS.manage_data)}
                        <span className="ms-auto">
                          {manageDataExpanded ? (
                            <ChevronDown className="h-3 w-3" />
                          ) : (
                            <ChevronRight className="h-3 w-3 rtl:rotate-180" />
                          )}
                        </span>
                      </Button>
                      {manageDataExpanded && (
                        <div className="ms-3 ps-2 border-s border-muted-foreground/10 space-y-1">
                          <Link href="/datasets/upload" className="block" onClick={() => setMobileDrawerOpen(false)}>
                            <Button variant={isChildActive("/datasets/upload") ? "secondary" : "ghost"} className="w-full justify-start text-xs">
                              <Upload className="me-2 h-3 w-3" />
                              {translate(TOOLS.upload_csv_excel)}
                            </Button>
                          </Link>
                          <Link href="/datasets/define" className="block" onClick={() => setMobileDrawerOpen(false)}>
                            <Button variant={isChildActive("/datasets/define") ? "secondary" : "ghost"} className="w-full justify-start text-xs">
                              <Database className="me-2 h-3 w-3" />
                              {translate(TOOLS.connect_database)}
                            </Button>
                          </Link>
                          <Link href="/notebooks/import" className="block" onClick={() => setMobileDrawerOpen(false)}>
                            <Button variant={isChildActive("/notebooks/import") ? "secondary" : "ghost"} className="w-full justify-start text-xs">
                              <BookOpen className="me-2 h-3 w-3" />
                              {translate(TOOLS.import_notebook)}
                            </Button>
                          </Link>
                        </div>
                      )}
                    </div>

                  </div>
                )}
              </div>

              {/* Settings expandable section (mobile) */}
              <div className="space-y-1">
                <Button
                  variant="ghost"
                  className="w-full justify-start text-sm"
                  onClick={() => setSettingsExpanded(!settingsExpanded)}
                >
                  <Settings className="me-2 h-4 w-4" />
                  {translate(SETTINGS.title)}
                  <span className="ms-auto">
                    {settingsExpanded ? (
                      <ChevronDown className="h-4 w-4" />
                    ) : (
                      <ChevronRight className="h-4 w-4 rtl:rotate-180" />
                    )}
                  </span>
                </Button>
                {settingsExpanded && (
                  <div className="ms-4 ps-2 border-s border-muted-foreground/20 space-y-1">
                    <Link href="/settings/profile" className="block" onClick={() => setMobileDrawerOpen(false)}>
                      <Button
                        variant={isChildActive("/settings/profile") ? "secondary" : "ghost"}
                        className="w-full justify-start text-sm"
                      >
                        <User className="me-2 h-4 w-4" />
                        {translate(SETTINGS.profile.title)}
                      </Button>
                    </Link>
                    <Link href="/settings/database" className="block" onClick={() => setMobileDrawerOpen(false)}>
                      <Button
                        variant={isChildActive("/settings/database") ? "secondary" : "ghost"}
                        className="w-full justify-start text-sm"
                      >
                        <Database className="me-2 h-4 w-4" />
                        {translate(SETTINGS.database.title)}
                      </Button>
                    </Link>
                    <Link href="/settings/ai" className="block" onClick={() => setMobileDrawerOpen(false)}>
                      <Button
                        variant={isChildActive("/settings/ai") ? "secondary" : "ghost"}
                        className="w-full justify-start text-sm"
                      >
                        <Bot className="me-2 h-4 w-4" />
                        {translate(SETTINGS.ai.title)}
                      </Button>
                    </Link>

                  </div>
                )}
              </div>

              {/* Admin expandable section (mobile) - only if user has admin access */}
              {(isAdmin || isGroupAdminUser || isExampleUserFlag) && (
                <div className="space-y-1">
                  <Button
                    variant="ghost"
                    className="w-full justify-start text-sm"
                    onClick={() => setAdminExpanded(!adminExpanded)}
                  >
                    <Shield className="me-2 h-4 w-4" />
                    {translate(NAV.admin)}
                    <span className="ms-auto">
                      {adminExpanded ? (
                        <ChevronDown className="h-4 w-4" />
                      ) : (
                        <ChevronRight className="h-4 w-4 rtl:rotate-180" />
                      )}
                    </span>
                  </Button>
                  {adminExpanded && (
                    <div className="ms-4 ps-2 border-s border-muted-foreground/20 space-y-1">
                      {(isAdmin || isExampleUserFlag) && (
                        <>
                          <Link href="/admin" className="block" onClick={() => setMobileDrawerOpen(false)}>
                            <Button
                              variant={isChildActive("/admin") ? "secondary" : "ghost"}
                              className="w-full justify-start text-sm"
                            >
                              {translate(NAV.admin_panel)}
                            </Button>
                          </Link>
                          <Link href="/admin/providers" className="block" onClick={() => setMobileDrawerOpen(false)}>
                            <Button
                              variant={isChildActive("/admin/providers") ? "secondary" : "ghost"}
                              className="w-full justify-start text-sm"
                            >
                              {translate(NAV.admin_providers)}
                            </Button>
                          </Link>
                          <Link href="/admin/models" className="block" onClick={() => setMobileDrawerOpen(false)}>
                            <Button
                              variant={isChildActive("/admin/models") ? "secondary" : "ghost"}
                              className="w-full justify-start text-sm"
                            >
                              {translate(COMMON.ai_models)}
                            </Button>
                          </Link>
                          <Link href="/admin/visualization-types" className="block" onClick={() => setMobileDrawerOpen(false)}>
                            <Button
                              variant={isChildActive("/admin/visualization-types") ? "secondary" : "ghost"}
                              className="w-full justify-start text-sm"
                            >
                              {translate(NAV.admin_visualization_types)}
                            </Button>
                          </Link>
                           <Link href="/admin/groups" className="block" onClick={() => setMobileDrawerOpen(false)}>
                             <Button
                               variant={isChildActive("/admin/groups") ? "secondary" : "ghost"}
                               className="w-full justify-start text-sm"
                             >
                               {translate(NAV.admin_groups)}
                             </Button>
                           </Link>

                            {/* Setup expandable (mobile) */}
                            <div className="space-y-1">
                              <Button
                                variant="ghost"
                                className="w-full justify-start text-sm"
                                onClick={() => setSetupExpanded(!setupExpanded)}
                              >
                                <Wrench className="me-2 h-4 w-4" />
                                {translate(NAV.admin_setup)}
                                <span className="ms-auto">
                                  {setupExpanded ? (
                                    <ChevronDown className="h-4 w-4" />
                                  ) : (
                                    <ChevronRight className="h-4 w-4 rtl:rotate-180" />
                                  )}
                                </span>
                              </Button>
                              {setupExpanded && (
                                <div className="ms-4 ps-2 border-s border-muted-foreground/20 space-y-1">
                                  <Link href="/admin/setup/limits" className="block" onClick={() => setMobileDrawerOpen(false)}>
                                    <Button
                                      variant={isChildActive("/admin/setup/limits") ? "secondary" : "ghost"}
                                      className="w-full justify-start text-sm"
                                    >
                                      <Gauge className="me-2 h-4 w-4" />
                                      {translate(NAV.admin_setup_limits)}
                                    </Button>
                                  </Link>
                                  <Link href="/admin/setup/tuning" className="block" onClick={() => setMobileDrawerOpen(false)}>
                                    <Button
                                      variant={isChildActive("/admin/setup/tuning") ? "secondary" : "ghost"}
                                      className="w-full justify-start text-sm"
                                    >
                                      <Sliders className="me-2 h-4 w-4" />
                                      {translate(NAV.admin_setup_tuning)}
                                    </Button>
                                  </Link>
                                  <Link href="/admin/setup/options" className="block" onClick={() => setMobileDrawerOpen(false)}>
                                    <Button
                                      variant={isChildActive("/admin/setup/options") ? "secondary" : "ghost"}
                                      className="w-full justify-start text-sm"
                                    >
                                      <SlidersHorizontal className="me-2 h-4 w-4" />
                                      {translate(NAV.admin_setup_options)}
                                    </Button>
                                  </Link>
                                  <Link href="/admin/setup/internal" className="block" onClick={() => setMobileDrawerOpen(false)}>
                                    <Button
                                      variant={isChildActive("/admin/setup/internal") ? "secondary" : "ghost"}
                                      className="w-full justify-start text-sm"
                                    >
                                      <Cpu className="me-2 h-4 w-4" />
                                      {translate(NAV.admin_setup_internal)}
                                    </Button>
                                  </Link>
                                  <Link href="/licence" className="block" onClick={() => setMobileDrawerOpen(false)}>
                                    <Button
                                      variant={isChildActive("/licence") ? "secondary" : "ghost"}
                                      className="w-full justify-start text-sm"
                                    >
                                      {translate(NAV.admin_licence)}
                                    </Button>
                                  </Link>
                                </div>
                              )}
                            </div>
                          </>
                        )}
                        {isGroupAdminUser && !isExampleUserFlag && (
                        <Link href="/admin/groups" className="block" onClick={() => setMobileDrawerOpen(false)}>
                          <Button
                            variant={isChildActive("/admin/groups") ? "secondary" : "ghost"}
                            className="w-full justify-start text-sm"
                          >
                            <Users className="me-2 h-4 w-4" />
                            {translate(NAV.admin_groups)}
                          </Button>
                        </Link>
                      )}
                    </div>
                  )}
                </div>
              )}

              <Link href="/about" className="block" onClick={() => setMobileDrawerOpen(false)}>
                <Button variant={isChildActive("/about") ? "secondary" : "ghost"} className="w-full justify-start text-sm">
                  <Info className="me-2 h-4 w-4" />
                  {translate(NAV.about)}
                </Button>
              </Link>
            </nav>
            <Separator className="my-4" />
            <div className="flex flex-col gap-2 text-sm">
              <div className="flex items-center gap-2">
                <Avatar className="h-8 w-8">
                  <AvatarImage src={session?.user?.image || undefined} />
                  <AvatarFallback>{session?.user?.name?.charAt(0) || "U"}</AvatarFallback>
                </Avatar>
                <div>
                  <p className="font-medium text-sm">{session?.user?.name || translate(NAV.user)}</p>
                  <p className="text-xs text-muted-foreground">{session?.user?.email || ""}</p>
                </div>
              </div>
              {status === "authenticated" && (
                <Button variant="ghost" size="sm" className="justify-start" onClick={handleLogout}>
                  <LogOut className="h-4 w-4 me-2" />
                  {translate(NAV.logout)}
                </Button>
              )}
            </div>
          </aside>
        </div>
      )}

      <div className="flex flex-col md:flex-row min-h-screen">
        <aside className="hidden md:flex md:flex-col w-64 border-e bg-muted/40 p-4 h-screen sticky top-0">
        <div className="flex items-center gap-2 mb-6">
          <LayoutDashboard className="h-6 w-6" />
          <span className="font-semibold">{translate(APP.name)}</span>
        </div>

        <nav className="flex-1 overflow-y-auto space-y-1">
          <Link href="/" className="block">
            <Button variant={isActive("/") ? "secondary" : "ghost"} className="w-full justify-start">
              <Home className="me-2 h-4 w-4" />
              {translate(NAV.home)}
            </Button>
          </Link>

          <Link href="/recipes" className="block">
            <Button variant={isActive("/recipes") ? "secondary" : "ghost"} className="w-full justify-start">
              <BookOpen className="me-2 h-4 w-4" />
              {translate(RECIPES.title)}
            </Button>
          </Link>

          {/* AI Chat expandable section */}
          <div className="space-y-1">
            <Button
              variant="ghost"
              className="w-full justify-start"
              onClick={() => setAiChatExpanded(!aiChatExpanded)}
            >
              <MessageSquare className="me-2 h-4 w-4" />
              {translate(NAV.ai_chat)}
              <span className="ms-auto">
                {aiChatExpanded ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4 rtl:rotate-180" />
                )}
              </span>
            </Button>
            {aiChatExpanded && (
              <div className="ms-4 ps-2 border-s border-muted-foreground/20 space-y-1">
                <Link href="/chat" className="block">
                  <Button
                    variant={isChildActive("/chat") ? "secondary" : "ghost"}
                    className="w-full justify-start text-sm"
                  >
                    <span className="me-2">💬</span>
                    {translate(NAV.ai_general)}
                  </Button>
                </Link>
                <Link href="/aitesting" className="block">
                  <Button
                    variant={isChildActive("/aitesting") ? "secondary" : "ghost"}
                    className="w-full justify-start text-sm"
                  >
                    <span className="me-2">🧪</span>
                    {translate(NAV.ai_testing)}
                  </Button>
                </Link>
                <Link href="/ai/database" className="block">
                  <Button
                    variant={isChildActive("/ai/database") ? "secondary" : "ghost"}
                    className="w-full justify-start text-sm"
                  >
                    <span className="me-2">🗄️</span>
                    {translate(NAV.ai_database_design)}
                  </Button>
                </Link>
                <Link href="/datasets/virtual" className="block">
                  <Button
                    variant={isAiVirtualActive() ? "secondary" : "ghost"}
                    className="w-full justify-start text-sm"
                  >
                    <span className="me-2">🔗</span>
                    {translate(NAV.ai_virtual_datasets)}
                  </Button>
                </Link>
                <Link href="/ai/dataclean" className="block">
                  <Button
                    variant={isChildActive("/ai/dataclean") ? "secondary" : "ghost"}
                    className="w-full justify-start text-sm"
                  >
                    <span className="me-2">🧹</span>
                    {translate(NAV.ai_dataset_cleaning)}
                  </Button>
                </Link>
                <Link href="/ai/recipe" className="block">
                  <Button
                    variant={isChildActive("/ai/recipe") ? "secondary" : "ghost"}
                    className="w-full justify-start text-sm"
                  >
                    <span className="me-2">📊</span>
                    {translate(NAV.ai_analysis_rules)}
                  </Button>
                </Link>
              </div>
            )}
          </div>

          {/* Tools expandable section */}
          <div className="space-y-1">
            <Button
              variant="ghost"
              className="w-full justify-start"
              onClick={() => setToolsExpanded(!toolsExpanded)}
            >
              <Wrench className="me-2 h-4 w-4" />
              {translate(TOOLS.title)}
              <span className="ms-auto">
                {toolsExpanded ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4 rtl:rotate-180" />
                )}
              </span>
            </Button>
            {toolsExpanded && (
              <div className="ms-4 ps-2 border-s border-muted-foreground/20 space-y-1">
                <Link href="/visualize" className="block">
                  <Button
                    variant={isChildActive("/visualize") ? "secondary" : "ghost"}
                    className="w-full justify-start text-sm"
                  >
                    <span className="me-2">📊</span>
                    {translate(TOOLS.visualize)}
                  </Button>
                </Link>

                {/* My Data expandable */}
                <div className="space-y-1">
                  <Button
                    variant="ghost"
                    className="w-full justify-start text-sm"
                    onClick={() => setMyDataExpanded(!myDataExpanded)}
                  >
                    <FolderOpen className="me-2 h-4 w-4" />
                    {translate(TOOLS.my_data)}
                    <span className="ms-auto">
                      {myDataExpanded ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : (
                        <ChevronRight className="h-3 w-3 rtl:rotate-180" />
                      )}
                    </span>
                  </Button>
                  {myDataExpanded && (
                    <div className="ms-3 ps-2 border-s border-muted-foreground/10 space-y-1">
                      <Link href="/datasets/manage" className="block">
                        <Button
                          variant={isChildActive("/datasets/manage") ? "secondary" : "ghost"}
                          className="w-full justify-start text-xs"
                        >
                          <Table className="me-2 h-3 w-3" />
                          {translate(TOOLS.all_datasets)}
                        </Button>
                      </Link>
                      <Link href="/datasets/uploaded" className="block">
                        <Button
                          variant={isChildActive("/datasets/uploaded") ? "secondary" : "ghost"}
                          className="w-full justify-start text-xs"
                        >
                          <FileSpreadsheet className="me-2 h-3 w-3" />
                          {translate(TOOLS.uploads_list)}
                        </Button>
                      </Link>
                      <Link href="/notebooks" className="block">
                        <Button
                          variant={isChildActive("/notebooks") ? "secondary" : "ghost"}
                          className="w-full justify-start text-xs"
                        >
                          <BookOpen className="me-2 h-3 w-3" />
                          {translate(TOOLS.notebooks)}
                        </Button>
                      </Link>
                      <Link href="/datasets/virtual/manual" className="block">
                        <Button
                          variant={isChildActive("/datasets/virtual/manual") ? "secondary" : "ghost"}
                          className="w-full justify-start text-xs"
                        >
                          <Layers className="me-2 h-3 w-3" />
                          {translate(NAV.ai_virtual_datasets)}
                        </Button>
                      </Link>
                    </div>
                  )}
                </div>

                {/* Manage Data expandable */}
                <div className="space-y-1">
                  <Button
                    variant="ghost"
                    className="w-full justify-start text-sm"
                    onClick={() => setManageDataExpanded(!manageDataExpanded)}
                  >
                    <Wrench className="me-2 h-4 w-4" />
                    {translate(TOOLS.manage_data)}
                    <span className="ms-auto">
                      {manageDataExpanded ? (
                        <ChevronDown className="h-3 w-3" />
                      ) : (
                        <ChevronRight className="h-3 w-3 rtl:rotate-180" />
                      )}
                    </span>
                  </Button>
                  {manageDataExpanded && (
                    <div className="ms-3 ps-2 border-s border-muted-foreground/10 space-y-1">
                      <Link href="/datasets/upload" className="block">
                        <Button
                          variant={isChildActive("/datasets/upload") ? "secondary" : "ghost"}
                          className="w-full justify-start text-xs"
                        >
                          <Upload className="me-2 h-3 w-3" />
                          {translate(TOOLS.upload_csv_excel)}
                        </Button>
                      </Link>
                      <Link href="/datasets/define" className="block">
                        <Button
                          variant={isChildActive("/datasets/define") ? "secondary" : "ghost"}
                          className="w-full justify-start text-xs"
                        >
                          <Database className="me-2 h-3 w-3" />
                          {translate(TOOLS.connect_database)}
                        </Button>
                      </Link>
                      <Link href="/notebooks/import" className="block">
                        <Button
                          variant={isChildActive("/notebooks/import") ? "secondary" : "ghost"}
                          className="w-full justify-start text-xs"
                        >
                          <BookOpen className="me-2 h-3 w-3" />
                          {translate(TOOLS.import_notebook)}
                        </Button>
                      </Link>
                    </div>
                  )}
                </div>
              </div>
            )}
            </div>

          {/* Settings expandable section */}
          <div className="space-y-1">
            <Button
              variant="ghost"
              className="w-full justify-start"
              onClick={() => setSettingsExpanded(!settingsExpanded)}
            >
              <Settings className="me-2 h-4 w-4" />
              {translate(SETTINGS.title)}
              <span className="ms-auto">
                {settingsExpanded ? (
                  <ChevronDown className="h-4 w-4" />
                ) : (
                  <ChevronRight className="h-4 w-4 rtl:rotate-180" />
                )}
              </span>
            </Button>
            {settingsExpanded && (
              <div className="ms-4 ps-2 border-s border-muted-foreground/20 space-y-1">
                <Link href="/settings/profile" className="block">
                  <Button
                    variant={isChildActive("/settings/profile") ? "secondary" : "ghost"}
                    className="w-full justify-start text-sm"
                  >
                    <User className="me-2 h-4 w-4" />
                    {translate(SETTINGS.profile.title)}
                  </Button>
                </Link>
                <Link href="/settings/database" className="block">
                  <Button
                    variant={isChildActive("/settings/database") ? "secondary" : "ghost"}
                    className="w-full justify-start text-sm"
                  >
                    <Database className="me-2 h-4 w-4" />
                    {translate(SETTINGS.database.title)}
                  </Button>
                </Link>
                <Link href="/settings/ai" className="block">
                  <Button
                    variant={isChildActive("/settings/ai") ? "secondary" : "ghost"}
                    className="w-full justify-start text-sm"
                  >
                    <Bot className="me-2 h-4 w-4" />
                    {translate(SETTINGS.ai.title)}
                  </Button>
                </Link>

              </div>
            )}
          </div>

          {/* Admin expandable section - only if user has admin access */}
          {(isAdmin || isGroupAdminUser || isExampleUserFlag) && (
            <div className="space-y-1">
              <Button
                variant="ghost"
                className="w-full justify-start"
                onClick={() => setAdminExpanded(!adminExpanded)}
              >
                <Shield className="me-2 h-4 w-4" />
                {translate(NAV.admin)}
                <span className="ms-auto">
                  {adminExpanded ? (
                    <ChevronDown className="h-4 w-4" />
                  ) : (
                    <ChevronRight className="h-4 w-4 rtl:rotate-180" />
                  )}
                </span>
              </Button>
              {adminExpanded && (
                <div className="ms-4 ps-2 border-s border-muted-foreground/20 space-y-1">
                  {(isAdmin || isExampleUserFlag) && (
                    <>
                      <Link href="/admin" className="block">
                        <Button
                          variant={isChildActive("/admin") ? "secondary" : "ghost"}
                          className="w-full justify-start text-sm"
                        >
                          {translate(NAV.admin_panel)}
                        </Button>
                      </Link>
                      <Link href="/admin/providers" className="block">
                        <Button
                          variant={isChildActive("/admin/providers") ? "secondary" : "ghost"}
                          className="w-full justify-start text-sm"
                        >
                          {translate(NAV.admin_providers)}
                        </Button>
                      </Link>
                      <Link href="/admin/models" className="block">
                        <Button
                          variant={isChildActive("/admin/models") ? "secondary" : "ghost"}
                          className="w-full justify-start text-sm"
                        >
                          {translate(COMMON.ai_models)}
                        </Button>
                      </Link>
                      <Link href="/admin/visualization-types" className="block">
                        <Button
                          variant={isChildActive("/admin/visualization-types") ? "secondary" : "ghost"}
                          className="w-full justify-start text-sm"
                        >
                          {translate(NAV.admin_visualization_types)}
                        </Button>
                      </Link>
                       <Link href="/admin/groups" className="block">
                         <Button
                           variant={isChildActive("/admin/groups") ? "secondary" : "ghost"}
                           className="w-full justify-start text-sm"
                         >
                           {translate(NAV.admin_groups)}
                         </Button>
                       </Link>

                        {/* Setup expandable */}
                        <div className="space-y-1">
                          <Button
                            variant="ghost"
                            className="w-full justify-start text-sm"
                            onClick={() => setSetupExpanded(!setupExpanded)}
                          >
                            <Wrench className="me-2 h-4 w-4" />
                            {translate(NAV.admin_setup)}
                            <span className="ms-auto">
                              {setupExpanded ? (
                                <ChevronDown className="h-4 w-4" />
                              ) : (
                                <ChevronRight className="h-4 w-4 rtl:rotate-180" />
                              )}
                            </span>
                          </Button>
                          {setupExpanded && (
                            <div className="ms-4 ps-2 border-s border-muted-foreground/20 space-y-1">
                              <Link href="/admin/setup/limits" className="block">
                                <Button
                                  variant={isActive("/admin/setup/limits") ? "secondary" : "ghost"}
                                  className="w-full justify-start text-sm"
                                >
                                  <Gauge className="me-2 h-4 w-4" />
                                  {translate(NAV.admin_setup_limits)}
                                </Button>
                              </Link>
                              <Link href="/admin/setup/tuning" className="block">
                                <Button
                                  variant={isActive("/admin/setup/tuning") ? "secondary" : "ghost"}
                                  className="w-full justify-start text-sm"
                                >
                                  <Sliders className="me-2 h-4 w-4" />
                                  {translate(NAV.admin_setup_tuning)}
                                </Button>
                              </Link>
                              <Link href="/admin/setup/options" className="block">
                                <Button
                                  variant={isActive("/admin/setup/options") ? "secondary" : "ghost"}
                                  className="w-full justify-start text-sm"
                                >
                                  <SlidersHorizontal className="me-2 h-4 w-4" />
                                  {translate(NAV.admin_setup_options)}
                                </Button>
                              </Link>
                              <Link href="/admin/setup/internal" className="block">
                                <Button
                                  variant={isActive("/admin/setup/internal") ? "secondary" : "ghost"}
                                  className="w-full justify-start text-sm"
                                >
                                  <Cpu className="me-2 h-4 w-4" />
                                  {translate(NAV.admin_setup_internal)}
                                </Button>
                              </Link>
                              <Link href="/licence" className="block">
                                <Button
                                  variant={isActive("/licence") ? "secondary" : "ghost"}
                                  className="w-full justify-start text-sm"
                                >
                                  {translate(NAV.admin_licence)}
                                </Button>
                              </Link>
                            </div>
                          )}
                        </div>
                      </>
                    )}
                   {isGroupAdminUser && !isExampleUserFlag && (
                     <Link href="/admin/groups" className="block">
                      <Button
                        variant={isChildActive("/admin/groups") ? "secondary" : "ghost"}
                        className="w-full justify-start text-sm"
                      >
                        <Users className="me-2 h-4 w-4" />
                        {translate(NAV.admin_groups)}
                        {isExampleUserFlag && (
                          <span className="ms-2 text-xs text-muted-foreground">{translate(ADMIN.groups.readonly_badge)}</span>
                        )}
                      </Button>
                    </Link>
                  )}
                </div>
              )}
            </div>
          )}

          <Link href="/about" className="block">
            <Button variant={isActive("/about") ? "secondary" : "ghost"} className="w-full justify-start">
              <Info className="me-2 h-4 w-4" />
              {translate(NAV.about)}
            </Button>
          </Link>
        </nav>

        <Separator className="my-4" />

        <div className="flex flex-col">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <Avatar className="h-8 w-8">
                <AvatarImage src={session?.user?.image || undefined} />
                <AvatarFallback>{session?.user?.name?.charAt(0) || "U"}</AvatarFallback>
              </Avatar>
              <div className="text-sm">
                <div className="flex items-center gap-1">
                  <p className="font-medium">{session?.user?.name || translate(NAV.user)}</p>
                  <ExampleUserBadge />
                  <GroupAdminBadge />
                </div>
                <p className="text-xs text-muted-foreground">{session?.user?.email || ""}</p>
              </div>
            </div>
            {status === "authenticated" && (
              <Button variant="ghost" size="icon" onClick={handleLogout} title={translate(NAV.logout)}>
                <LogOut className="h-4 w-4" />
              </Button>
            )}
          </div>
          {version && (
            <div className="mt-2 text-center text-xs text-muted-foreground">
              {translate(APP.version)} {version}
            </div>
          )}
        </div>
      </aside>
      {/* Offset by whatever the banner strip is showing, published as
          --banner-stack-h by banner-stack.tsx: the strip measures itself, so this
          covers one banner, two stacked, or none — where the previous scheme
          offset by a fixed amount and only when demo mode was on. */}
      <main
        className="flex-1 p-4 pt-14 pb-24 md:p-6 overflow-auto"
        style={{ marginTop: "var(--banner-stack-h, 0px)" }}
      >
        {children}
      </main>
    </div>
    </>
  );
}