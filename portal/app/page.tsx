"use client";

import { useEffect, useState } from "react";
import { Truck } from "lucide-react";
import { portalFetch } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";
import {
  AppShell,
  Card,
  StatCard,
  PortalLoading,
  usePortalGuard,
} from "@/components/ui";

interface Summary {
  jobs_this_month: number;
  open_invoices: number;
  active_properties: number;
  next_pickup: { id: string; scheduled_at: string | null; address: string } | null;
}

export default function DashboardPage() {
  const { ready } = usePortalGuard();
  const { org } = useAuthStore();
  const [summary, setSummary] = useState<Summary | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    portalFetch<Summary>("/dashboard/summary")
      .then(setSummary)
      .catch((e) => setError(String(e)));
  }, [ready]);

  if (!ready) return <PortalLoading />;

  return (
    <AppShell
      title="Dashboard"
      subtitle={org?.name ? `Welcome back, ${org.name}.` : undefined}
    >
      {error && (
        <div className="mb-4 rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
          {error}
        </div>
      )}

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <StatCard label="Jobs this month" value={summary?.jobs_this_month ?? "—"} />
        <StatCard label="Open invoices" value={summary?.open_invoices ?? "—"} />
        <StatCard label="Active properties" value={summary?.active_properties ?? "—"} />
        <StatCard
          label="Next pickup"
          value={
            summary?.next_pickup?.scheduled_at
              ? new Date(summary.next_pickup.scheduled_at).toLocaleDateString(
                  undefined,
                  { month: "short", day: "numeric" }
                )
              : "None"
          }
          hint={summary?.next_pickup?.scheduled_at ? "scheduled" : "nothing scheduled"}
        />
      </div>

      {summary?.next_pickup && (
        <Card className="mt-6 p-6">
          <div className="flex items-start gap-4">
            <div className="flex h-11 w-11 flex-none items-center justify-center rounded-xl bg-brand-50">
              <Truck className="h-5 w-5 text-brand-600" />
            </div>
            <div>
              <div className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                Upcoming pickup
              </div>
              <div className="mt-1 text-lg font-semibold text-gray-900">
                {summary.next_pickup.address}
              </div>
              {summary.next_pickup.scheduled_at && (
                <div className="mt-0.5 text-sm text-gray-500">
                  {new Date(summary.next_pickup.scheduled_at).toLocaleString()}
                </div>
              )}
            </div>
          </div>
        </Card>
      )}
    </AppShell>
  );
}
