"use client";

import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { NotificationBell } from "@/components/notification-bell";
import { operatorApi } from "@/lib/api";
import {
  LayoutDashboard,
  Briefcase,
  Users,
  Mail,
  DollarSign,
  BarChart3,
  Settings,
  LogOut,
  Menu,
  X,
} from "lucide-react";

const sidebarLinks = [
  { href: "/operator", label: "Dashboard", icon: LayoutDashboard },
  { href: "/operator/jobs", label: "Jobs", icon: Briefcase },
  { href: "/operator/fleet", label: "Fleet", icon: Users },
  { href: "/operator/invites", label: "Invite Codes", icon: Mail },
  { href: "/operator/earnings", label: "Earnings", icon: DollarSign },
  { href: "/operator/analytics", label: "Analytics", icon: BarChart3 },
  { href: "/operator/settings", label: "Settings", icon: Settings },
];

export default function OperatorLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const { user, isAuthenticated } = useAuthStore();
  const [hydrated, setHydrated] = useState(false);
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  useEffect(() => {
    if (!hydrated) return;
    if (!isAuthenticated) {
      router.replace("/admin/login");
    }
  }, [hydrated, isAuthenticated, router]);

  // Close mobile menu on route change
  useEffect(() => {
    setMobileMenuOpen(false);
  }, [pathname]);

  if (!hydrated || !isAuthenticated) {
    return (
      <div className="h-screen flex items-center justify-center">
        <div className="text-center">
          <img src="/logo.png" alt="Umuve" className="h-8 w-8 object-contain mx-auto mb-3 animate-pulse" />
          <p className="text-sm text-muted-foreground">Loading...</p>
        </div>
      </div>
    );
  }

  const userName = user?.name || user?.email || "Operator";
  const userInitial = userName[0]?.toUpperCase() || "O";

  return (
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
          <Link href="/operator" className="flex items-center gap-2">
            <img src="/logo-nav.png" alt="Umuve" className="h-9 w-auto object-contain" />
            <span className="text-xs font-medium text-amber-700 bg-amber-100 px-1.5 py-0.5 rounded">
              Operator
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
              link.href === "/operator"
                ? pathname === "/operator"
                : pathname.startsWith(link.href);
            const Icon = link.icon;

            return (
              <Link
                key={link.href}
                href={link.href}
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
            <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
              <span className="text-sm font-medium text-amber-700">{userInitial}</span>
            </div>
            <div className="min-w-0">
              <p className="text-sm font-medium truncate">{userName}</p>
              <p className="text-xs text-muted-foreground">Operator</p>
            </div>
          </div>
          <button
            onClick={() => {
              useAuthStore.getState().logout();
              router.push("/admin/login");
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
                fetchNotifications={operatorApi.notifications}
                markAsRead={operatorApi.markNotificationRead}
                markAllAsRead={operatorApi.markAllNotificationsRead}
              />
              <span className="text-sm text-muted-foreground hidden sm:inline">{userName}</span>
              <div className="w-8 h-8 rounded-full bg-amber-100 flex items-center justify-center">
                <span className="text-sm font-medium text-amber-700">{userInitial}</span>
              </div>
            </div>
          </div>
        </header>

        <main className="flex-1 p-4 sm:p-6 overflow-y-auto">{children}</main>
      </div>
    </div>
  );
}
