"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Nav } from "@/components/nav";
import { portalFetch } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";

interface Summary {
  jobs_this_month: number;
  open_invoices: number;
  active_properties: number;
  next_pickup: { id: string; scheduled_at: string | null; address: string } | null;
}

export default function DashboardPage() {
  const router = useRouter();
  const { token, isLoading, hydrate } = useAuthStore();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (isLoading) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    portalFetch<Summary>("/dashboard/summary")
      .then(setSummary)
      .catch((e) => setError(String(e)));
  }, [isLoading, token, router]);

  if (isLoading || !token) {
    return <div className="p-8 text-gray-500">Loading…</div>;
  }

  return (
    <div className="flex min-h-screen">
      <Nav />
      <main className="flex-1 p-8 max-w-6xl">
        <h1 className="text-2xl font-semibold mb-6">Dashboard</h1>
        {error && <div className="text-brand-600 mb-4">{error}</div>}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card label="Jobs This Month" value={summary?.jobs_this_month ?? "—"} />
          <Card label="Open Invoices" value={summary?.open_invoices ?? "—"} />
          <Card
            label="Active Properties"
            value={summary?.active_properties ?? "—"}
          />
          <Card
            label="Next Pickup"
            value={
              summary?.next_pickup?.scheduled_at
                ? new Date(summary.next_pickup.scheduled_at).toLocaleDateString()
                : "None scheduled"
            }
          />
        </div>

        {summary?.next_pickup && (
          <div className="mt-8 rounded-lg border border-gray-200 bg-white p-5">
            <h2 className="text-sm font-medium text-gray-500 mb-2">
              Upcoming Pickup
            </h2>
            <div className="text-gray-900">{summary.next_pickup.address}</div>
          </div>
        )}
      </main>
    </div>
  );
}

function Card({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-gray-200 bg-white p-5">
      <div className="text-xs font-medium uppercase tracking-wide text-gray-500">
        {label}
      </div>
      <div className="mt-2 text-2xl font-semibold text-gray-900">{value}</div>
    </div>
  );
}
