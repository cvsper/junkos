"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  LayoutDashboard,
  Building2,
  Truck,
  FileText,
  Users,
  Settings,
  LogOut,
} from "lucide-react";
import { useAuthStore } from "@/lib/stores/authStore";

const items = [
  { href: "/", label: "Dashboard", Icon: LayoutDashboard },
  { href: "/properties", label: "Properties", Icon: Building2 },
  { href: "/jobs", label: "Jobs", Icon: Truck },
  { href: "/invoices", label: "Invoices", Icon: FileText },
  { href: "/team", label: "Team", Icon: Users },
  { href: "/settings", label: "Settings", Icon: Settings },
];

export function Nav() {
  const pathname = usePathname();
  const { org, role, signOut } = useAuthStore();

  const initial = (org?.name || "U").trim().charAt(0).toUpperCase();

  return (
    <aside className="flex min-h-screen w-60 flex-col border-r border-gray-200/80 bg-white">
      <div className="px-5 py-5">
        <Link href="/" className="inline-flex items-baseline gap-2">
          <span className="text-xl font-extrabold tracking-tight text-brand-600">
            Umuve
          </span>
          <span className="text-[0.6rem] font-semibold uppercase tracking-[0.18em] text-gray-400">
            Commercial
          </span>
        </Link>
      </div>

      <nav className="flex-1 space-y-0.5 px-3">
        {items.map(({ href, label, Icon }) => {
          const active =
            pathname === href || (href !== "/" && pathname?.startsWith(href));
          return (
            <Link
              key={href}
              href={href}
              className={`flex items-center gap-3 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                active
                  ? "bg-brand-50 text-brand-700"
                  : "text-gray-600 hover:bg-gray-50 hover:text-gray-900"
              }`}
            >
              <Icon
                className={`h-[18px] w-[18px] ${
                  active ? "text-brand-600" : "text-gray-400"
                }`}
                strokeWidth={2}
              />
              {label}
            </Link>
          );
        })}
      </nav>

      <div className="m-3 rounded-xl border border-gray-200/80 bg-gray-50/60 p-3">
        <div className="flex items-center gap-2.5">
          <div className="flex h-9 w-9 flex-none items-center justify-center rounded-lg bg-brand-600 text-sm font-bold text-white">
            {initial}
          </div>
          <div className="min-w-0">
            <div className="truncate text-sm font-semibold text-gray-900">
              {org?.name || "—"}
            </div>
            <div className="truncate text-xs capitalize text-gray-500">
              {role}
              {org?.tier ? ` · ${org.tier}` : ""}
            </div>
          </div>
        </div>
        <button
          onClick={signOut}
          className="mt-3 flex w-full items-center justify-center gap-1.5 rounded-lg border border-gray-200 bg-white py-1.5 text-xs font-medium text-gray-600 transition-colors hover:border-gray-300 hover:text-brand-600"
        >
          <LogOut className="h-3.5 w-3.5" />
          Sign out
        </button>
      </div>
    </aside>
  );
}
