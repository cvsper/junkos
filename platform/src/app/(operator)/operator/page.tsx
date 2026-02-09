"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import {
  Users,
  Wifi,
  Clock,
  DollarSign,
  Briefcase,
  ArrowRight,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
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
        <div className="h-8 bg-muted rounded w-48 animate-pulse" />
        {/* Stat card skeletons */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          {[...Array(4)].map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-5 sm:p-6 animate-pulse">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-lg bg-muted" />
                <div className="h-4 bg-muted rounded w-24" />
              </div>
              <div className="h-8 bg-muted rounded w-16" />
            </div>
          ))}
        </div>
        {/* Job list skeleton */}
        <div className="rounded-xl border border-border bg-card">
          <div className="px-4 sm:px-6 py-4 border-b border-border">
            <div className="h-5 bg-muted rounded w-48 animate-pulse" />
          </div>
          <div className="divide-y divide-border">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="px-4 sm:px-6 py-4 animate-pulse">
                <div className="flex items-center justify-between">
                  <div className="space-y-2 flex-1">
                    <div className="h-4 bg-muted rounded w-3/4 max-w-[250px]" />
                    <div className="h-3 bg-muted rounded w-1/2 max-w-[180px]" />
                  </div>
                  <div className="h-8 bg-muted rounded w-20 ml-4" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-display font-bold">Dashboard</h1>
        <div className="rounded-xl border border-red-200 bg-red-50 p-8 flex flex-col items-center text-center">
          <AlertCircle className="h-10 w-10 text-red-400 mb-3" />
          <p className="text-red-700 font-medium mb-1">Something went wrong</p>
          <p className="text-sm text-red-600 mb-4">{error}</p>
          <button
            onClick={() => window.location.reload()}
            className="inline-flex items-center gap-2 text-sm bg-red-100 text-red-700 px-4 py-2 rounded-lg hover:bg-red-200 transition-colors font-medium"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  const stats = [
    { label: "Fleet Size", value: dashboard?.fleet_size ?? 0, color: "text-blue-600", bg: "bg-blue-50", icon: Users },
    { label: "Online Now", value: dashboard?.online_count ?? 0, color: "text-green-600", bg: "bg-green-50", icon: Wifi },
    { label: "Pending Delegation", value: dashboard?.pending_delegation ?? 0, color: "text-amber-600", bg: "bg-amber-50", icon: Clock },
    { label: "Earnings (30d)", value: `$${(dashboard?.earnings_30d ?? 0).toFixed(2)}`, color: "text-primary", bg: "bg-primary/10", icon: DollarSign },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-display font-bold">Operator Dashboard</h1>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {stats.map((stat) => {
          const Icon = stat.icon;
          return (
            <div key={stat.label} className="rounded-xl border border-border bg-card p-5 sm:p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className={`w-10 h-10 rounded-lg ${stat.bg} flex items-center justify-center`}>
                  <Icon className={`w-5 h-5 ${stat.color}`} />
                </div>
                <p className="text-sm text-muted-foreground">{stat.label}</p>
              </div>
              <p className={`text-2xl font-bold ${stat.color}`}>{stat.value}</p>
            </div>
          );
        })}
      </div>

      {/* Pending Delegation Quick Action */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-4 sm:px-6 py-4 border-b border-border flex items-center justify-between">
          <h2 className="font-semibold">Jobs Needing Delegation</h2>
          <Link
            href="/operator/jobs"
            className="text-sm text-primary hover:underline inline-flex items-center gap-1"
          >
            View All
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
        {pendingJobs.length === 0 ? (
          <div className="px-4 sm:px-6 py-12 flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-full bg-green-50 flex items-center justify-center mb-3">
              <Briefcase className="w-6 h-6 text-green-500" />
            </div>
            <p className="text-sm font-medium text-foreground mb-1">All caught up!</p>
            <p className="text-sm text-muted-foreground">
              No jobs are waiting for delegation right now.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {pendingJobs.slice(0, 5).map((job) => (
              <div key={job.id} className="px-4 sm:px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3">
                <div className="min-w-0">
                  <p className="text-sm font-medium truncate">{job.address}</p>
                  <p className="text-xs text-muted-foreground">
                    {job.customer_name} &middot; ${job.total_price?.toFixed(2)}
                  </p>
                </div>
                <button
                  onClick={() => router.push("/operator/jobs")}
                  className="text-xs bg-amber-100 text-amber-700 px-3 py-1.5 rounded-lg font-medium hover:bg-amber-200 transition-colors self-start sm:self-center whitespace-nowrap"
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
