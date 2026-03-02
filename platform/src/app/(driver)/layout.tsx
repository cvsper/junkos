"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useCallback, useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { SocketProvider } from "@/lib/socket-provider";
import { NotificationBell } from "@/components/notification-bell";
import { driverApi } from "@/lib/api";
import {
  LayoutDashboard,
  Briefcase,
  DollarSign,
  UserCircle,
  LogOut,
  Menu,
  X,
  Clock,
  CheckCircle2,
  AlertCircle,
  RefreshCw,
  Loader2,
} from "lucide-react";

const sidebarLinks = [
  { href: "/driver", label: "Dashboard", icon: LayoutDashboard },
  { href: "/driver/jobs", label: "Jobs", icon: Briefcase },
  { href: "/driver/earnings", label: "Earnings", icon: DollarSign },
  { href: "/driver/profile", label: "Profile", icon: UserCircle },
];

export default function DriverLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, token, isAuthenticated } = useAuthStore();
  const [hydrated, setHydrated] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  // Approval gate state
  const [approvalStatus, setApprovalStatus] = useState<string | null>(null);
  const [approvalLoading, setApprovalLoading] = useState(true);
  const [approvalError, setApprovalError] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;

    // Allow public access to login, signup, and onboarding pages
    const isPublicPage =
      pathname === "/driver/login" ||
      pathname === "/driver/signup" ||
      pathname === "/driver/onboarding";

    if (!isAuthenticated && !isPublicPage) {
      router.replace("/driver/login");
    }
  }, [hydrated, isAuthenticated, router, pathname]);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  // Check approval status for authenticated drivers on non-public pages
  const isPublicPage =
    pathname === "/driver/login" ||
    pathname === "/driver/signup" ||
    pathname === "/driver/onboarding";

  const checkApproval = useCallback(async () => {
    if (!isAuthenticated || isPublicPage) {
      setApprovalLoading(false);
      return;
    }
    try {
      setApprovalError(false);
      const res = await driverApi.profile();
      setApprovalStatus(res.profile.approval_status);
    } catch {
      setApprovalError(true);
    } finally {
      setApprovalLoading(false);
    }
  }, [isAuthenticated, isPublicPage]);

  useEffect(() => {
    if (hydrated) checkApproval();
  }, [hydrated, checkApproval]);

  // Show loading only during hydration
  if (!hydrated) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <img
            src="/logo.png"
            alt="Umuve"
            className="h-20 w-20 object-contain mx-auto mb-3 animate-pulse"
          />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // Allow login/signup/onboarding pages to render without auth
  if (!isAuthenticated && !isPublicPage) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <img
            src="/logo.png"
            alt="Umuve"
            className="h-20 w-20 object-contain mx-auto mb-3 animate-pulse"
          />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  // If on login/signup/onboarding page, render without layout chrome
  if (isPublicPage) {
    return <>{children}</>;
  }

  // ---------- Approval gate for authenticated drivers ----------

  if (approvalLoading) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <Loader2 className="h-8 w-8 text-emerald-600 animate-spin mx-auto mb-3" />
          <p className="text-sm text-muted-foreground">Checking your account status...</p>
        </div>
      </div>
    );
  }

  if (approvalError) {
    return (
      <div className="h-screen flex items-center justify-center px-4">
        <div className="text-center max-w-sm">
          <AlertCircle className="h-10 w-10 text-red-400 mx-auto mb-3" />
          <p className="text-sm font-medium text-foreground mb-1">Could not verify account</p>
          <p className="text-sm text-muted-foreground mb-4">
            We couldn&apos;t check your approval status. Please try again.
          </p>
          <button
            onClick={() => { setApprovalLoading(true); checkApproval(); }}
            className="inline-flex items-center gap-2 text-sm bg-emerald-600 text-white px-4 py-2 rounded-lg hover:bg-emerald-700 transition-colors font-medium"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  if (approvalStatus && approvalStatus !== "approved") {
    const isRejected = approvalStatus === "rejected";

    return (
      <div className="h-screen flex items-center justify-center px-4">
        <div className="text-center max-w-md">
          <div className={`w-16 h-16 rounded-full ${isRejected ? "bg-red-100" : "bg-amber-100"} flex items-center justify-center mx-auto mb-5`}>
            {isRejected ? (
              <AlertCircle className="w-8 h-8 text-red-500" />
            ) : (
              <Clock className="w-8 h-8 text-amber-500" />
            )}
          </div>

          <h1 className="text-xl font-bold mb-2">
            {isRejected ? "Application Not Approved" : "Waiting on Approval"}
          </h1>

          <p className="text-muted-foreground text-sm mb-6 max-w-xs mx-auto">
            {isRejected
              ? "Your application was not approved. Please check your onboarding page for details and re-submit."
              : "Your application is being reviewed by our team. We'll notify you as soon as you're approved to start accepting jobs."}
          </p>

          <div className="space-y-3">
            <Link
              href="/driver/onboarding"
              className="inline-flex items-center gap-2 text-sm bg-emerald-600 text-white px-5 py-2.5 rounded-lg hover:bg-emerald-700 transition-colors font-medium"
            >
              {isRejected ? "Re-submit Application" : "Check Onboarding Status"}
            </Link>

            <div>
              <button
                onClick={() => { setApprovalLoading(true); checkApproval(); }}
                className="inline-flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors font-medium mt-2"
              >
                <RefreshCw className="w-3.5 h-3.5" />
                Refresh Status
              </button>
            </div>

            <div className="pt-2">
              <button
                onClick={() => {
                  useAuthStore.getState().logout();
                  router.push("/driver/login");
                }}
                className="text-sm text-muted-foreground hover:text-foreground transition-colors"
              >
                Sign Out
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  }

  const userName = user?.name || user?.email || "Driver";
  const userInitial = userName[0]?.toUpperCase() || "D";

  return (
    <SocketProvider token={token ?? undefined}>
      <div className="h-screen flex overflow-hidden">
        {/* Mobile overlay */}
        {mobileMenuOpen && (
          <div
            className="fixed inset-0 bg-black/50 z-30 md:hidden"
            onClick={() => setMobileMenuOpen(false)}
          />
        )}

        {/* Sidebar */}
        <aside
          className={`
            w-64 border-r border-border bg-card flex-shrink-0 flex flex-col h-screen
            fixed md:sticky top-0 z-40 transition-transform duration-200
            ${mobileMenuOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}
          `}
        >
          <div className="h-16 flex items-center justify-between px-6 border-b border-border">
            <Link href="/driver" className="flex items-center gap-2">
              <img
                src="/logo-nav.png"
                alt="Umuve"
                className="h-9 w-auto object-contain"
              />
              <span className="text-xs font-medium text-emerald-700 bg-emerald-100 px-1.5 py-0.5 rounded">
                Driver
              </span>
            </Link>
            <button
              className="md:hidden p-1 rounded-lg hover:bg-muted transition-colors"
              onClick={() => setMobileMenuOpen(false)}
            >
              <X className="w-5 h-5" />
            </button>
          </div>

          <nav className="flex-1 px-3 py-4 space-y-1 overflow-y-auto">
            {sidebarLinks.map((link) => {
              const isActive =
                link.href === "/driver"
                  ? pathname === "/driver"
                  : pathname.startsWith(link.href);
              const Icon = link.icon;

              return (
                <Link
                  key={link.href}
                  href={link.href}
                  onClick={() => setMobileMenuOpen(false)}
                  className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors ${
                    isActive
                      ? "bg-primary/10 text-primary"
                      : "text-muted-foreground hover:text-foreground hover:bg-muted"
                  }`}
                >
                  <Icon className="w-5 h-5 flex-shrink-0" />
                  {link.label}
                </Link>
              );
            })}
          </nav>

          <div className="p-4 border-t border-border">
            <div className="flex items-center gap-3 px-3 py-2 mb-3">
              <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                <span className="text-sm font-medium text-emerald-700">
                  {userInitial}
                </span>
              </div>
              <div className="min-w-0">
                <p className="text-sm font-medium truncate">{userName}</p>
                <p className="text-xs text-muted-foreground">Driver</p>
              </div>
            </div>
            <button
              onClick={() => {
                useAuthStore.getState().logout();
                router.push("/driver/login");
              }}
              className="flex items-center gap-2 text-sm text-muted-foreground hover:text-foreground transition-colors w-full px-3 py-2 rounded-lg hover:bg-muted"
            >
              <LogOut className="w-4 h-4" />
              Sign Out
            </button>
          </div>
        </aside>

        {/* Main content */}
        <div className="flex-1 flex flex-col min-w-0 h-screen overflow-hidden">
          <header className="h-16 border-b border-border bg-card flex items-center px-4 sm:px-6 flex-shrink-0 z-10">
            <div className="flex items-center justify-between w-full">
              <button
                className="md:hidden p-2 -ml-2 rounded-lg hover:bg-muted transition-colors"
                onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
              >
                <Menu className="w-5 h-5" />
              </button>

              <div className="ml-auto flex items-center gap-3">
                <NotificationBell
                  fetchNotifications={driverApi.notifications}
                  markAsRead={driverApi.markNotificationRead}
                  markAllAsRead={driverApi.markAllNotificationsRead}
                />
                <span className="text-sm text-muted-foreground hidden sm:inline">
                  {userName}
                </span>
                <div className="w-8 h-8 rounded-full bg-emerald-100 flex items-center justify-center">
                  <span className="text-sm font-medium text-emerald-700">
                    {userInitial}
                  </span>
                </div>
              </div>
            </div>
          </header>

          <main className="flex-1 p-4 sm:p-6 overflow-y-auto">{children}</main>
        </div>
      </div>
    </SocketProvider>
  );
}
