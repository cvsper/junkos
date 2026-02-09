"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { operatorApi, type OperatorDashboardData, type OperatorJobRecord } from "@/lib/api";

export default function OperatorDashboardPage() {
  const [dashboard, setDashboard] = useState<OperatorDashboardData | null>(null);
  const [pendingJobs, setPendingJobs] = useState<OperatorJobRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const router = useRouter();

  useEffect(() => {
    async function load() {
      try {
        const [dashRes, jobsRes] = await Promise.all([
          operatorApi.dashboard(),
          operatorApi.jobs("delegating"),
        ]);
        setDashboard(dashRes.dashboard);
        setPendingJobs(jobsRes.jobs);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Failed to load dashboard");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-display font-bold">Dashboard</h1>
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-6 animate-pulse">
              <div className="h-4 bg-muted rounded w-24 mb-2" />
              <div className="h-8 bg-muted rounded w-16" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-display font-bold">Dashboard</h1>
        <div className="rounded-xl border border-red-200 bg-red-50 p-6">
          <p className="text-red-700">{error}</p>
          <button onClick={() => window.location.reload()} className="mt-2 text-sm text-red-600 underline">
            Retry
          </button>
        </div>
      </div>
    );
  }

  const stats = [
    { label: "Fleet Size", value: dashboard?.fleet_size ?? 0, color: "text-blue-600" },
    { label: "Online Now", value: dashboard?.online_count ?? 0, color: "text-green-600" },
    { label: "Pending Delegation", value: dashboard?.pending_delegation ?? 0, color: "text-amber-600" },
    { label: "Earnings (30d)", value: `$${(dashboard?.earnings_30d ?? 0).toFixed(2)}`, color: "text-primary" },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-display font-bold">Operator Dashboard</h1>

      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => (
          <div key={stat.label} className="rounded-xl border border-border bg-card p-6">
            <p className="text-sm text-muted-foreground">{stat.label}</p>
            <p className={`text-2xl font-bold mt-1 ${stat.color}`}>{stat.value}</p>
          </div>
        ))}
      </div>

      {/* Pending Delegation Quick Action */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-6 py-4 border-b border-border flex items-center justify-between">
          <h2 className="font-semibold">Jobs Needing Delegation</h2>
          <button
            onClick={() => router.push("/operator/jobs")}
            className="text-sm text-primary hover:underline"
          >
            View All
          </button>
        </div>
        {pendingJobs.length === 0 ? (
          <div className="px-6 py-8 text-center text-muted-foreground text-sm">
            No jobs pending delegation
          </div>
        ) : (
          <div className="divide-y divide-border">
            {pendingJobs.slice(0, 5).map((job) => (
              <div key={job.id} className="px-6 py-4 flex items-center justify-between">
                <div>
                  <p className="text-sm font-medium">{job.address}</p>
                  <p className="text-xs text-muted-foreground">
                    {job.customer_name} &middot; ${job.total_price?.toFixed(2)}
                  </p>
                </div>
                <button
                  onClick={() => router.push("/operator/jobs")}
                  className="text-xs bg-amber-100 text-amber-700 px-3 py-1.5 rounded-lg font-medium hover:bg-amber-200 transition-colors"
                >
                  Delegate
                </button>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
