"use client";

import { ReactNode, useEffect } from "react";
import { useRouter } from "next/navigation";
import { useAuthStore } from "@/lib/stores/authStore";
import { Nav } from "./nav";

/**
 * Portal design-system kit. Shared by every inner page so the app reads as
 * one coherent product: porcelain canvas, white cards, Outfit display type,
 * a single red accent, and consistent tables / badges / forms.
 */

// ---- Auth guard (dedupes the hydrate + redirect every page needs) ----------
export function usePortalGuard() {
  const router = useRouter();
  const { token, isLoading, hydrate } = useAuthStore();
  useEffect(() => {
    hydrate();
  }, [hydrate]);
  useEffect(() => {
    if (!isLoading && !token) router.replace("/login");
  }, [isLoading, token, router]);
  return { ready: !isLoading && !!token };
}

export function PortalLoading() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-[#FAF8F5]">
      <div className="flex items-center gap-3 text-gray-400">
        <span className="h-4 w-4 animate-spin rounded-full border-2 border-gray-300 border-t-brand-600" />
        <span className="text-sm">Loading…</span>
      </div>
    </div>
  );
}

// ---- App shell: sidebar + sticky header + content ---------------------------
export function AppShell({
  title,
  subtitle,
  action,
  children,
  maxWidth = "max-w-6xl",
}: {
  title: string;
  subtitle?: string;
  action?: ReactNode;
  children: ReactNode;
  maxWidth?: string;
}) {
  return (
    <div className="flex min-h-screen bg-[#FAF8F5]">
      <Nav />
      <div className="min-w-0 flex-1">
        <header className="sticky top-0 z-10 border-b border-gray-200/70 bg-[#FAF8F5]/80 px-6 py-5 backdrop-blur sm:px-8">
          <div className={`mx-auto flex items-end justify-between gap-4 ${maxWidth}`}>
            <div>
              <h1 className="text-2xl font-extrabold tracking-tight text-gray-900">
                {title}
              </h1>
              {subtitle && <p className="mt-0.5 text-sm text-gray-500">{subtitle}</p>}
            </div>
            {action}
          </div>
        </header>
        <main className="px-6 py-8 sm:px-8">
          <div className={`mx-auto ${maxWidth}`}>{children}</div>
        </main>
      </div>
    </div>
  );
}

export function Card({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <div
      className={`rounded-xl border border-gray-200/80 bg-white shadow-[0_1px_3px_rgba(17,17,17,0.04)] ${className}`}
    >
      {children}
    </div>
  );
}

export function StatCard({
  label,
  value,
  hint,
}: {
  label: string;
  value: ReactNode;
  hint?: string;
}) {
  return (
    <Card className="p-5">
      <div className="text-xs font-semibold uppercase tracking-wider text-gray-400">
        {label}
      </div>
      <div className="mt-2 text-3xl font-extrabold tracking-tight text-gray-900">
        {value}
      </div>
      {hint && <div className="mt-1 text-xs text-gray-500">{hint}</div>}
    </Card>
  );
}

type ButtonProps = React.ButtonHTMLAttributes<HTMLButtonElement> & {
  variant?: "primary" | "secondary" | "dark";
};
export function Button({
  children,
  variant = "primary",
  className = "",
  ...rest
}: ButtonProps) {
  const styles =
    variant === "secondary"
      ? "border border-gray-300 bg-white text-gray-900 hover:border-gray-900"
      : variant === "dark"
      ? "bg-gray-900 text-white hover:bg-gray-800"
      : "bg-brand-600 text-white hover:bg-brand-700";
  return (
    <button
      className={`rounded-lg px-4 py-2 text-sm font-semibold transition-colors disabled:opacity-50 ${styles} ${className}`}
      {...rest}
    >
      {children}
    </button>
  );
}

export type Tone = "gray" | "green" | "yellow" | "red" | "blue";
const TONES: Record<Tone, string> = {
  gray: "bg-gray-100 text-gray-600",
  green: "bg-green-50 text-green-700",
  yellow: "bg-amber-50 text-amber-700",
  red: "bg-red-50 text-red-700",
  blue: "bg-blue-50 text-blue-700",
};
export function Badge({ children, tone = "gray" }: { children: ReactNode; tone?: Tone }) {
  return (
    <span
      className={`inline-block rounded-full px-2.5 py-0.5 text-xs font-medium capitalize ${TONES[tone]}`}
    >
      {children}
    </span>
  );
}

/** Map common status strings to a badge tone. */
export function statusTone(status: string): Tone {
  const s = (status || "").toLowerCase();
  if (["paid", "active", "completed", "complete"].includes(s)) return "green";
  if (["open", "pending", "scheduled", "trial", "paused"].includes(s)) return "yellow";
  if (["past_due", "overdue", "failed", "cancelled", "canceled"].includes(s))
    return "red";
  if (["assigned", "in_progress", "dispatched", "en_route"].includes(s))
    return "blue";
  return "gray";
}

// ---- Table primitives -------------------------------------------------------
export function Table({ head, children }: { head: ReactNode; children: ReactNode }) {
  return (
    <Card className="overflow-hidden">
      <div className="overflow-x-auto">
        <table className="w-full text-sm">
          <thead className="border-b border-gray-200/70 bg-gray-50/60 text-left">
            {head}
          </thead>
          <tbody>{children}</tbody>
        </table>
      </div>
    </Card>
  );
}
export function Th({
  children,
  className = "",
}: {
  children?: ReactNode;
  className?: string;
}) {
  return (
    <th
      className={`px-5 py-3 text-xs font-semibold uppercase tracking-wider text-gray-400 ${className}`}
    >
      {children}
    </th>
  );
}
export function Td({
  children,
  className = "",
}: {
  children?: ReactNode;
  className?: string;
}) {
  return <td className={`px-5 py-3.5 align-middle text-gray-900 ${className}`}>{children}</td>;
}
export function Tr({ children }: { children: ReactNode }) {
  return (
    <tr className="border-t border-gray-100 transition-colors hover:bg-gray-50/50">
      {children}
    </tr>
  );
}
export function EmptyRow({
  colSpan,
  children,
}: {
  colSpan: number;
  children: ReactNode;
}) {
  return (
    <tr>
      <td colSpan={colSpan} className="px-5 py-14 text-center text-sm text-gray-400">
        {children}
      </td>
    </tr>
  );
}

// ---- Form fields ------------------------------------------------------------
export function Input(props: React.InputHTMLAttributes<HTMLInputElement>) {
  const { className = "", ...rest } = props;
  return (
    <input
      {...rest}
      className={`w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm text-gray-900 outline-none transition-colors placeholder:text-gray-400 focus:border-brand-600 focus:ring-2 focus:ring-brand-100 ${className}`}
    />
  );
}
export function Select(props: React.SelectHTMLAttributes<HTMLSelectElement>) {
  const { className = "", ...rest } = props;
  return (
    <select
      {...rest}
      className={`rounded-lg border border-gray-300 bg-white px-3 py-2.5 text-sm text-gray-900 outline-none transition-colors focus:border-brand-600 focus:ring-2 focus:ring-brand-100 ${className}`}
    />
  );
}
export function FieldLabel({
  children,
  className = "",
}: {
  children: ReactNode;
  className?: string;
}) {
  return (
    <span className={`mb-1.5 block text-xs font-medium text-gray-600 ${className}`}>
      {children}
    </span>
  );
}
