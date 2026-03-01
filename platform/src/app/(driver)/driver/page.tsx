"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  DollarSign,
  Briefcase,
  Star,
  TrendingUp,
  ArrowRight,
  AlertCircle,
  RefreshCw,
  MapPin,
  Clock,
  Loader2,
} from "lucide-react";
import { driverApi } from "@/lib/api";
import type { DriverStats, DriverJob, DriverProfile } from "@/types";

export default function DriverDashboardPage() {
  const [stats, setStats] = useState<DriverStats | null>(null);
  const [profile, setProfile] = useState<DriverProfile | null>(null);
  const [activeJobs, setActiveJobs] = useState<DriverJob[]>([]);
  const [recentJobs, setRecentJobs] = useState<DriverJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [isOnline, setIsOnline] = useState(false);
  const [togglingAvailability, setTogglingAvailability] = useState(false);

  const loadData = useCallback(async () => {
    try {
      setError(null);
      setLoading(true);
      const [statsRes, profileRes, activeRes, completedRes] = await Promise.all([
        driverApi.stats(),
        driverApi.profile(),
        driverApi.activeJobs(),
        driverApi.completedJobs(1),
      ]);
      setStats(statsRes.stats);
      setProfile(profileRes.profile);
      setIsOnline(profileRes.profile.is_online);
      setActiveJobs(activeRes.jobs);
      setRecentJobs(completedRes.jobs.slice(0, 3));
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const handleToggleAvailability = async () => {
    setTogglingAvailability(true);
    try {
      const res = await driverApi.setAvailability(!isOnline);
      setIsOnline(res.is_online);
    } catch {
      // Revert on failure — no-op, state unchanged
    } finally {
      setTogglingAvailability(false);
    }
  };

  // ---------------------------------------------------------------------------
  // Loading skeleton
  // ---------------------------------------------------------------------------
  if (loading) {
    return (
      <div className="space-y-6">
        {/* Toggle skeleton */}
        <div className="h-14 bg-muted rounded-xl animate-pulse" />
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
        {/* Active job skeleton */}
        <div className="rounded-xl border border-border bg-card p-6 animate-pulse">
          <div className="h-5 bg-muted rounded w-32 mb-4" />
          <div className="h-4 bg-muted rounded w-3/4 mb-2" />
          <div className="h-4 bg-muted rounded w-1/2" />
        </div>
        {/* Recent activity skeleton */}
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

  // ---------------------------------------------------------------------------
  // Error state
  // ---------------------------------------------------------------------------
  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-display font-bold">Dashboard</h1>
        <div className="rounded-xl border border-red-200 bg-red-50 p-8 flex flex-col items-center text-center">
          <AlertCircle className="h-10 w-10 text-red-400 mb-3" />
          <p className="text-red-700 font-medium mb-1">Something went wrong</p>
          <p className="text-sm text-red-600 mb-4">{error}</p>
          <button
            onClick={loadData}
            className="inline-flex items-center gap-2 text-sm bg-red-100 text-red-700 px-4 py-2 rounded-lg hover:bg-red-200 transition-colors font-medium"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Stat cards config
  // ---------------------------------------------------------------------------
  const statCards = [
    {
      label: "Today's Earnings",
      value: `$${(stats?.today_earnings ?? 0).toFixed(2)}`,
      color: "text-emerald-600",
      bg: "bg-emerald-50",
      icon: DollarSign,
    },
    {
      label: "Today's Jobs",
      value: stats?.today_jobs ?? 0,
      color: "text-blue-600",
      bg: "bg-blue-50",
      icon: Briefcase,
    },
    {
      label: "Rating",
      value: `${(stats?.rating ?? 0).toFixed(1)}/5.0`,
      color: "text-amber-600",
      bg: "bg-amber-50",
      icon: Star,
    },
    {
      label: "Acceptance Rate",
      value: `${Math.round(stats?.acceptance_rate ?? 0)}%`,
      color: "text-purple-600",
      bg: "bg-purple-50",
      icon: TrendingUp,
    },
  ];

  const activeJob = activeJobs[0] ?? null;

  const statusLabel = (s: string) =>
    s
      .replace(/_/g, " ")
      .replace(/\b\w/g, (c) => c.toUpperCase());

  const formatDate = (iso: string) => {
    const d = new Date(iso);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  };

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-display font-bold">Driver Dashboard</h1>

      {/* ---- Online / Offline Toggle ---- */}
      <button
        onClick={handleToggleAvailability}
        disabled={togglingAvailability}
        className={`w-full rounded-xl px-6 py-4 flex items-center justify-between transition-colors ${
          isOnline
            ? "bg-emerald-600 text-white hover:bg-emerald-700"
            : "bg-muted text-muted-foreground hover:bg-muted/80"
        }`}
      >
        <div className="flex items-center gap-3">
          {togglingAvailability ? (
            <Loader2 className="w-5 h-5 animate-spin" />
          ) : (
            <span
              className={`inline-block w-3 h-3 rounded-full ${
                isOnline ? "bg-white animate-pulse" : "bg-muted-foreground/50"
              }`}
            />
          )}
          <span className="text-lg font-semibold">
            {togglingAvailability
              ? "Updating..."
              : isOnline
                ? "You're Online"
                : "You're Offline"}
          </span>
        </div>
        <span className="text-sm opacity-80">
          {isOnline ? "Tap to go offline" : "Tap to go online"}
        </span>
      </button>

      {/* ---- Pending Approval Banner ---- */}
      {profile && profile.approval_status !== "approved" && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 px-5 py-4 flex flex-col sm:flex-row sm:items-center gap-3">
          <div className="flex items-start gap-3 flex-1">
            <AlertCircle className="w-5 h-5 text-amber-600 mt-0.5 shrink-0" />
            <div>
              <p className="text-sm font-medium text-amber-800">
                Your account is under review
              </p>
              <p className="text-sm text-amber-700 mt-0.5">
                You&apos;ll be notified when approved. Check your onboarding status for details.
              </p>
            </div>
          </div>
          <Link
            href="/driver/onboarding"
            className="inline-flex items-center gap-1.5 text-sm font-medium text-amber-800 bg-amber-100 px-4 py-2 rounded-lg hover:bg-amber-200 transition-colors whitespace-nowrap self-start sm:self-center"
          >
            Check Status
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      )}

      {/* ---- Stat Cards ---- */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        {statCards.map((stat) => {
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

      {/* ---- Active Job Card ---- */}
      {activeJob && (
        <div className="rounded-xl border-2 border-emerald-200 bg-emerald-50/50 p-5 sm:p-6">
          <div className="flex items-center justify-between mb-4">
            <h2 className="font-semibold text-emerald-800">Active Job</h2>
            <span className="inline-flex items-center gap-1.5 text-xs font-medium bg-emerald-100 text-emerald-700 px-2.5 py-1 rounded-full">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 animate-pulse" />
              {statusLabel(activeJob.status)}
            </span>
          </div>
          <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
            <div className="min-w-0 space-y-1.5">
              <div className="flex items-start gap-2">
                <MapPin className="w-4 h-4 text-emerald-600 mt-0.5 shrink-0" />
                <p className="text-sm font-medium truncate">{activeJob.address}</p>
              </div>
              <div className="flex items-center gap-4 text-xs text-muted-foreground">
                {activeJob.customer_name && (
                  <span>{activeJob.customer_name}</span>
                )}
                <span className="font-semibold text-emerald-700">
                  ${activeJob.total_price.toFixed(2)}
                </span>
              </div>
            </div>
            <Link
              href={`/driver/jobs/${activeJob.id}/active`}
              className="inline-flex items-center gap-2 text-sm bg-emerald-600 text-white px-5 py-2.5 rounded-lg hover:bg-emerald-700 transition-colors font-medium whitespace-nowrap self-start sm:self-center"
            >
              Continue Job
              <ArrowRight className="w-4 h-4" />
            </Link>
          </div>
        </div>
      )}

      {/* ---- Recent Activity ---- */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-4 sm:px-6 py-4 border-b border-border flex items-center justify-between">
          <h2 className="font-semibold">Recent Activity</h2>
          <Link
            href="/driver/jobs"
            className="text-sm text-emerald-600 hover:underline inline-flex items-center gap-1"
          >
            View All
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
        {recentJobs.length === 0 ? (
          <div className="px-4 sm:px-6 py-12 flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-full bg-emerald-50 flex items-center justify-center mb-3">
              <Briefcase className="w-6 h-6 text-emerald-500" />
            </div>
            <p className="text-sm font-medium text-foreground mb-1">No completed jobs yet</p>
            <p className="text-sm text-muted-foreground">
              Your recent completed jobs will appear here.
            </p>
          </div>
        ) : (
          <div className="divide-y divide-border">
            {recentJobs.map((job) => (
              <div
                key={job.id}
                className="px-4 sm:px-6 py-4 flex flex-col sm:flex-row sm:items-center justify-between gap-3"
              >
                <div className="min-w-0">
                  <div className="flex items-start gap-2">
                    <MapPin className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
                    <p className="text-sm font-medium truncate">{job.address}</p>
                  </div>
                  <div className="flex items-center gap-3 mt-1 ml-6 text-xs text-muted-foreground">
                    <span className="inline-flex items-center gap-1">
                      <Clock className="w-3 h-3" />
                      {formatDate(job.completed_at || job.updated_at)}
                    </span>
                    <span className="font-semibold text-foreground">
                      ${job.total_price.toFixed(2)}
                    </span>
                  </div>
                </div>
                <Link
                  href={`/driver/jobs/${job.id}`}
                  className="text-xs bg-muted text-muted-foreground px-3 py-1.5 rounded-lg font-medium hover:bg-muted/80 transition-colors self-start sm:self-center whitespace-nowrap"
                >
                  Details
                </Link>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
