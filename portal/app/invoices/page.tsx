"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Nav } from "@/components/nav";
import { portalFetch } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";

interface Invoice {
  id: string;
  number: string;
  period_start: string;
  period_end: string;
  total_cents: number;
  status: string;
  due_at: string | null;
}

const STATUS_BADGE: Record<string, string> = {
  draft: "bg-gray-100 text-gray-700",
  open: "bg-yellow-50 text-yellow-800",
  paid: "bg-green-50 text-green-700",
  past_due: "bg-red-50 text-red-700",
  void: "bg-gray-100 text-gray-400 line-through",
};

export default function InvoicesPage() {
  const router = useRouter();
  const { token, isLoading, hydrate } = useAuthStore();
  const [rows, setRows] = useState<Invoice[]>([]);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (isLoading) return;
    if (!token) return router.replace("/login");
    portalFetch<{ invoices: Invoice[] }>("/billing/invoices").then((r) =>
      setRows(r.invoices)
    );
  }, [isLoading, token, router]);

  if (isLoading || !token) return <div className="p-8 text-gray-500">Loading…</div>;

  return (
    <div className="flex min-h-screen">
      <Nav />
      <main className="flex-1 p-8">
        <h1 className="text-2xl font-semibold mb-6">Invoices</h1>
        <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="px-4 py-3 text-xs uppercase text-gray-500">
                  Number
                </th>
                <th className="px-4 py-3 text-xs uppercase text-gray-500">
                  Period
                </th>
                <th className="px-4 py-3 text-xs uppercase text-gray-500">
                  Status
                </th>
                <th className="px-4 py-3 text-xs uppercase text-gray-500 text-right">
                  Amount
                </th>
                <th className="px-4 py-3 text-xs uppercase text-gray-500">
                  Due
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={5} className="p-6 text-center text-gray-500">
                    No invoices yet.
                  </td>
                </tr>
              )}
              {rows.map((i) => (
                <tr key={i.id} className="border-t border-gray-100">
                  <td className="px-4 py-3 font-medium">{i.number}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {new Date(i.period_start).toLocaleDateString()} –{" "}
                    {new Date(i.period_end).toLocaleDateString()}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-block text-xs px-2 py-0.5 rounded-full ${
                        STATUS_BADGE[i.status] || STATUS_BADGE.draft
                      }`}
                    >
                      {i.status}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-right">
                    ${(i.total_cents / 100).toFixed(2)}
                  </td>
                  <td className="px-4 py-3 text-gray-600">
                    {i.due_at
                      ? new Date(i.due_at).toLocaleDateString()
                      : "—"}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
