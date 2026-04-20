"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useAuthStore } from "@/lib/stores/authStore";

const items = [
  { href: "/", label: "Dashboard" },
  { href: "/properties", label: "Properties" },
  { href: "/jobs", label: "Jobs" },
  { href: "/invoices", label: "Invoices" },
  { href: "/team", label: "Team" },
  { href: "/settings", label: "Settings" },
];

export function Nav() {
  const pathname = usePathname();
  const { org, role, signOut } = useAuthStore();

  return (
    <aside className="w-60 bg-white border-r border-gray-200 flex flex-col min-h-screen">
      <div className="px-5 py-5 border-b border-gray-200">
        <Link href="/" className="text-xl font-bold text-brand-600">
          Umuve
        </Link>
        <div className="mt-1 text-xs text-gray-500">Commercial Portal</div>
      </div>
      <nav className="flex-1 p-3 space-y-1">
        {items.map((it) => {
          const active =
            pathname === it.href ||
            (it.href !== "/" && pathname?.startsWith(it.href));
          return (
            <Link
              key={it.href}
              href={it.href}
              className={`block px-3 py-2 rounded-md text-sm ${
                active
                  ? "bg-brand-50 text-brand-700 font-medium"
                  : "text-gray-700 hover:bg-gray-50"
              }`}
            >
              {it.label}
            </Link>
          );
        })}
      </nav>
      <div className="border-t border-gray-200 p-4 text-sm">
        <div className="font-medium text-gray-900 truncate">{org?.name || "—"}</div>
        <div className="text-xs text-gray-500 capitalize">
          {role} · {org?.tier}
        </div>
        <button
          onClick={signOut}
          className="mt-3 text-xs text-gray-500 hover:text-brand-600"
        >
          Sign out
        </button>
      </div>
    </aside>
  );
}
