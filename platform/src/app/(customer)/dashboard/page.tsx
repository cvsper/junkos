"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { jobsApi } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

// ---------------------------------------------------------------------------
// Local types (mirrors backend response, not importing from @/types)
// ---------------------------------------------------------------------------

interface JobContractor {
  id: string;
  user: { name: string | null; phone: string | null } | null;
  truck_type: string | null;
  avg_rating: number;
  total_jobs: number;
}

interface CustomerJob {
  id: string;
  status: string;
  address: string;
  items: { category: string; quantity: number }[];
  total_price: number;
  scheduled_at: string | null;
  created_at: string;
  contractor?: JobContractor | null;
}

interface LookedUpJob {
  id: string;
  confirmation_code: string;
  status: string;
  address: string;
  items: { category: string; quantity: number }[];
  photos: string[];
  before_photos: string[];
  after_photos: string[];
  scheduled_at: string | null;
  started_at: string | null;
  completed_at: string | null;
  total_price: number;
  created_at: string;
  notes: string | null;
  contractor?: {
    name: string | null;
    truck_type: string | null;
    avg_rating: number;
    total_jobs: number;
  } | null;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const ACTIVE_STATUSES = [
  "pending",
  "confirmed",
  "assigned",
  "en_route",
  "arrived",
  "in_progress",
];

type TabKey = "all" | "active" | "completed" | "cancelled";

const TABS: { key: TabKey; label: string }[] = [
  { key: "all", label: "All" },
  { key: "active", label: "Active" },
  { key: "completed", label: "Completed" },
  { key: "cancelled", label: "Cancelled" },
];

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800 border-yellow-200",
  confirmed: "bg-blue-100 text-blue-800 border-blue-200",
  assigned: "bg-indigo-100 text-indigo-800 border-indigo-200",
  en_route: "bg-orange-100 text-orange-800 border-orange-200",
  arrived: "bg-orange-100 text-orange-800 border-orange-200",
  in_progress: "bg-orange-100 text-orange-800 border-orange-200",
  completed: "bg-green-100 text-green-800 border-green-200",
  cancelled: "bg-red-100 text-red-800 border-red-200",
};

const STATUS_ICONS: Record<string, string> = {
  pending: "M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z",
  confirmed: "M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z",
  assigned: "M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z",
  en_route: "M8.25 18.75a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 01-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h1.125c.621 0 1.129-.504 1.09-1.124a17.902 17.902 0 00-3.213-9.193 2.056 2.056 0 00-1.58-.86H14.25M16.5 18.75h-2.25m0-11.177v-.958c0-.568-.422-1.048-.987-1.106a48.554 48.554 0 00-10.026 0 1.106 1.106 0 00-.987 1.106v7.635m12-6.677v6.677m0 4.5v-4.5m0 0h-12",
  arrived: "M15 10.5a3 3 0 11-6 0 3 3 0 016 0z M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z",
  in_progress: "M11.42 15.17l-4.655-5.653a.75.75 0 010-.964l4.655-5.653M20.25 12l-8.83-8.83M20.25 12l-8.83 8.83",
  completed: "M4.5 12.75l6 6 9-13.5",
  cancelled: "M6 18L18 6M6 6l12 12",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusLabel(status: string): string {
  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

function formatPrice(cents: number): string {
  return `$${cents.toFixed(2)}`;
}

function truncate(str: string, max: number): string {
  if (str.length <= max) return str;
  return str.slice(0, max) + "...";
}

function itemCount(items: { category: string; quantity: number }[]): string {
  const total = items.reduce((sum, i) => sum + i.quantity, 0);
  return `${total} item${total !== 1 ? "s" : ""}`;
}

/** Sort: active jobs first (by creation date desc), then completed, then cancelled */
function sortJobs(jobs: CustomerJob[]): CustomerJob[] {
  const priority: Record<string, number> = {};
  ACTIVE_STATUSES.forEach((s) => (priority[s] = 0));
  priority["completed"] = 1;
  priority["cancelled"] = 2;

  return [...jobs].sort((a, b) => {
    const pa = priority[a.status] ?? 1;
    const pb = priority[b.status] ?? 1;
    if (pa !== pb) return pa - pb;
    return new Date(b.created_at).getTime() - new Date(a.created_at).getTime();
  });
}

function isActive(status: string): boolean {
  return ACTIVE_STATUSES.includes(status);
}

// ---------------------------------------------------------------------------
// Guest Lookup Component
// ---------------------------------------------------------------------------

function GuestLookup() {
  const [code, setCode] = useState("");
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [job, setJob] = useState<LookedUpJob | null>(null);

  const handleLookup = async () => {
    const trimmed = code.trim().toUpperCase();
    if (trimmed.length !== 8) {
      setError("Please enter a valid 8-character confirmation code.");
      return;
    }

    setLoading(true);
    setError(null);
    setJob(null);

    try {
      const res = await jobsApi.lookup(trimmed);
      setJob(res.job);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Job not found. Please check your code.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="max-w-xl mx-auto px-4 py-12 sm:py-20">
      <div className="text-center mb-8">
        <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center mx-auto mb-4">
          <svg
            className="w-8 h-8 text-primary"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M21 21l-5.197-5.197m0 0A7.5 7.5 0 105.196 5.196a7.5 7.5 0 0010.607 10.607z"
            />
          </svg>
        </div>
        <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">
          Track Your Pickup
        </h1>
        <p className="text-muted-foreground mt-2">
          Enter the confirmation code from your booking to view your job status.
        </p>
      </div>

      <Card>
        <CardContent className="p-6 space-y-4">
          <div className="flex gap-3">
            <Input
              placeholder="e.g. ABCD1234"
              value={code}
              onChange={(e) => {
                setCode(e.target.value.toUpperCase().replace(/[^A-Z0-9]/g, "").slice(0, 8));
                if (error) setError(null);
              }}
              onKeyDown={(e) => {
                if (e.key === "Enter") handleLookup();
              }}
              className="flex-1 text-center text-lg font-mono tracking-widest uppercase h-12"
              maxLength={8}
              disabled={loading}
            />
            <Button
              onClick={handleLookup}
              disabled={loading || code.trim().length < 8}
              className="h-12 px-6"
            >
              {loading ? (
                <svg
                  className="h-5 w-5 animate-spin"
                  xmlns="http://www.w3.org/2000/svg"
                  fill="none"
                  viewBox="0 0 24 24"
                >
                  <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                  <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                </svg>
              ) : (
                "Track"
              )}
            </Button>
          </div>

          {error && (
            <p className="text-sm text-destructive font-medium text-center">{error}</p>
          )}
        </CardContent>
      </Card>

      {/* Looked-up job result */}
      {job && (
        <Card className="mt-6 border-primary/20">
          <CardContent className="p-6 space-y-5">
            {/* Status header */}
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-3">
                <div
                  className={`w-10 h-10 rounded-full flex items-center justify-center ${
                    isActive(job.status)
                      ? "bg-primary/10"
                      : job.status === "completed"
                      ? "bg-green-100"
                      : "bg-red-100"
                  }`}
                >
                  <svg
                    className={`w-5 h-5 ${
                      isActive(job.status)
                        ? "text-primary"
                        : job.status === "completed"
                        ? "text-green-600"
                        : "text-red-600"
                    }`}
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d={STATUS_ICONS[job.status] ?? STATUS_ICONS["pending"]}
                    />
                  </svg>
                </div>
                <div>
                  <Badge className={STATUS_COLORS[job.status] ?? "bg-muted text-muted-foreground"}>
                    {statusLabel(job.status)}
                  </Badge>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Code: {job.confirmation_code}
                  </p>
                </div>
              </div>
              <p className="text-xl font-bold text-primary">
                {formatPrice(job.total_price)}
              </p>
            </div>

            {/* Details */}
            <div className="space-y-3 text-sm">
              <div className="flex justify-between">
                <span className="text-muted-foreground">Address</span>
                <span className="font-medium text-right max-w-[250px]">
                  {job.address}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Scheduled</span>
                <span className="font-medium">
                  {job.scheduled_at ? formatDate(job.scheduled_at) : "Not scheduled"}
                </span>
              </div>
              <div className="flex justify-between">
                <span className="text-muted-foreground">Items</span>
                <span className="font-medium">{itemCount(job.items)}</span>
              </div>
              {job.contractor && (
                <>
                  <div className="border-t border-border pt-3 flex justify-between">
                    <span className="text-muted-foreground">Contractor</span>
                    <span className="font-medium">
                      {job.contractor.name ?? "Assigned"}
                    </span>
                  </div>
                  {job.contractor.truck_type && (
                    <div className="flex justify-between">
                      <span className="text-muted-foreground">Truck</span>
                      <span className="font-medium">{job.contractor.truck_type}</span>
                    </div>
                  )}
                  <div className="flex justify-between">
                    <span className="text-muted-foreground">Rating</span>
                    <span className="font-medium">
                      {job.contractor.avg_rating.toFixed(1)} / 5.0
                    </span>
                  </div>
                </>
              )}
              {!job.contractor && (
                <div className="border-t border-border pt-3 flex justify-between">
                  <span className="text-muted-foreground">Contractor</span>
                  <span className="text-muted-foreground italic">Awaiting assignment</span>
                </div>
              )}
            </div>

            {/* Track link for active jobs */}
            {isActive(job.status) && (
              <Link
                href={`/track/${job.id}`}
                className="flex items-center justify-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors w-full"
              >
                <svg
                  className="w-4 h-4"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z" />
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z" />
                </svg>
                Live Tracking
              </Link>
            )}
          </CardContent>
        </Card>
      )}

      {/* Sign in link */}
      <p className="text-center text-sm text-muted-foreground mt-8">
        Have an account?{" "}
        <Link href="/login" className="text-primary font-medium hover:underline">
          Sign in
        </Link>{" "}
        for full dashboard access.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Authenticated Dashboard Component
// ---------------------------------------------------------------------------

function AuthenticatedDashboard() {
  const router = useRouter();
  const [jobs, setJobs] = useState<CustomerJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<TabKey>("all");

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await jobsApi.list();
      setJobs(res.jobs ?? []);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to load jobs.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  // Filter jobs by active tab
  const filteredJobs = sortJobs(
    jobs.filter((job) => {
      if (activeTab === "all") return true;
      if (activeTab === "active") return ACTIVE_STATUSES.includes(job.status);
      if (activeTab === "completed") return job.status === "completed";
      if (activeTab === "cancelled") return job.status === "cancelled";
      return true;
    })
  );

  // Counts for tab badges
  const activeCount = jobs.filter((j) => ACTIVE_STATUSES.includes(j.status)).length;
  const completedCount = jobs.filter((j) => j.status === "completed").length;
  const cancelledCount = jobs.filter((j) => j.status === "cancelled").length;
  const tabCounts: Record<TabKey, number> = {
    all: jobs.length,
    active: activeCount,
    completed: completedCount,
    cancelled: cancelledCount,
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8 sm:py-12">
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight">
            My Jobs
          </h1>
          <p className="text-muted-foreground mt-1">
            Track and manage your junk removal pickups.
          </p>
        </div>
        <Link
          href="/book"
          className="inline-flex items-center gap-2 rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
        >
          <svg
            className="w-4 h-4"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M12 4.5v15m7.5-7.5h-15"
            />
          </svg>
          New Pickup
        </Link>
      </div>

      {/* Loading */}
      {loading && (
        <div className="flex items-center justify-center py-24">
          <svg
            className="h-8 w-8 animate-spin text-primary"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <span className="ml-3 text-muted-foreground text-sm">
            Loading your jobs...
          </span>
        </div>
      )}

      {/* Error */}
      {!loading && error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-8 text-center">
          <p className="text-destructive font-medium mb-1">
            Something went wrong
          </p>
          <p className="text-muted-foreground text-sm mb-4">{error}</p>
          <Button variant="outline" size="sm" onClick={fetchJobs}>
            Try Again
          </Button>
        </div>
      )}

      {/* Empty state */}
      {!loading && !error && jobs.length === 0 && (
        <div className="rounded-lg border border-dashed border-border bg-card p-12 text-center">
          <div className="w-16 h-16 rounded-full bg-muted flex items-center justify-center mx-auto mb-4">
            <svg
              className="w-8 h-8 text-muted-foreground"
              fill="none"
              viewBox="0 0 24 24"
              strokeWidth={1.5}
              stroke="currentColor"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M8.25 18.75a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h6m-9 0H3.375a1.125 1.125 0 01-1.125-1.125V14.25m17.25 4.5a1.5 1.5 0 01-3 0m3 0a1.5 1.5 0 00-3 0m3 0h1.125c.621 0 1.129-.504 1.09-1.124a17.902 17.902 0 00-3.213-9.193 2.056 2.056 0 00-1.58-.86H14.25M16.5 18.75h-2.25m0-11.177v-.958c0-.568-.422-1.048-.987-1.106a48.554 48.554 0 00-10.026 0 1.106 1.106 0 00-.987 1.106v7.635m12-6.677v6.677m0 4.5v-4.5m0 0h-12"
              />
            </svg>
          </div>
          <h3 className="font-display text-lg font-semibold mb-1">
            No jobs yet
          </h3>
          <p className="text-muted-foreground text-sm mb-6 max-w-sm mx-auto">
            You haven&apos;t booked any junk removal pickups yet. Get started by
            scheduling your first pickup.
          </p>
          <Link
            href="/book"
            className="inline-flex items-center rounded-lg bg-primary px-5 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors"
          >
            Book Your First Pickup
          </Link>
        </div>
      )}

      {/* Jobs list */}
      {!loading && !error && jobs.length > 0 && (
        <>
          {/* Tab bar */}
          <div className="flex items-center gap-1 border-b border-border mb-6">
            {TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setActiveTab(tab.key)}
                className={`px-4 py-2.5 text-sm font-medium transition-colors relative flex items-center gap-2 ${
                  activeTab === tab.key
                    ? "text-foreground"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab.label}
                {tabCounts[tab.key] > 0 && (
                  <span
                    className={`text-xs rounded-full px-1.5 py-0.5 min-w-[20px] text-center ${
                      activeTab === tab.key
                        ? "bg-primary/10 text-primary"
                        : "bg-muted text-muted-foreground"
                    }`}
                  >
                    {tabCounts[tab.key]}
                  </span>
                )}
                {activeTab === tab.key && (
                  <span className="absolute bottom-0 left-0 right-0 h-0.5 bg-primary rounded-full" />
                )}
              </button>
            ))}
          </div>

          {/* Filtered results */}
          {filteredJobs.length === 0 ? (
            <div className="py-12 text-center">
              <p className="text-muted-foreground text-sm">
                No {activeTab === "all" ? "" : activeTab} jobs found.
              </p>
            </div>
          ) : (
            <div className="grid gap-4">
              {filteredJobs.map((job) => (
                <Card
                  key={job.id}
                  className={`cursor-pointer hover:shadow-md transition-all ${
                    isActive(job.status)
                      ? "border-primary/20 hover:border-primary/40"
                      : ""
                  }`}
                  onClick={() => router.push(`/jobs/${job.id}`)}
                >
                  <CardContent className="p-5">
                    <div className="flex flex-col sm:flex-row sm:items-center gap-4">
                      {/* Left: status icon + address */}
                      <div className="flex items-start gap-3 flex-1 min-w-0">
                        {/* Status icon circle */}
                        <div
                          className={`flex-shrink-0 w-10 h-10 rounded-full flex items-center justify-center ${
                            isActive(job.status)
                              ? "bg-primary/10"
                              : job.status === "completed"
                              ? "bg-green-100"
                              : "bg-red-100"
                          }`}
                        >
                          <svg
                            className={`w-5 h-5 ${
                              isActive(job.status)
                                ? "text-primary"
                                : job.status === "completed"
                                ? "text-green-600"
                                : "text-red-600"
                            }`}
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={1.5}
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d={
                                STATUS_ICONS[job.status] ??
                                STATUS_ICONS["pending"]
                              }
                            />
                          </svg>
                        </div>

                        <div className="min-w-0 flex-1">
                          <div className="flex items-center gap-2 mb-1">
                            <Badge
                              className={
                                STATUS_COLORS[job.status] ??
                                "bg-muted text-muted-foreground"
                              }
                            >
                              {statusLabel(job.status)}
                            </Badge>
                            <span className="text-xs text-muted-foreground">
                              #{job.id.slice(0, 8)}
                            </span>
                          </div>
                          <p className="font-medium text-sm truncate">
                            {truncate(job.address, 60)}
                          </p>
                          <p className="text-xs text-muted-foreground mt-0.5">
                            {job.scheduled_at
                              ? formatDate(job.scheduled_at)
                              : "Not scheduled"}
                          </p>
                        </div>
                      </div>

                      {/* Right: meta + actions */}
                      <div className="flex items-center gap-4 sm:gap-6 text-sm shrink-0">
                        <div className="text-center">
                          <p className="text-muted-foreground text-xs">Items</p>
                          <p className="font-medium">{itemCount(job.items)}</p>
                        </div>
                        <div className="text-center">
                          <p className="text-muted-foreground text-xs">Price</p>
                          <p className="font-semibold text-foreground">
                            {formatPrice(job.total_price)}
                          </p>
                        </div>
                        <div className="text-center min-w-[90px]">
                          <p className="text-muted-foreground text-xs">
                            Contractor
                          </p>
                          <p className="font-medium text-sm">
                            {job.contractor?.user?.name ??
                              "Awaiting"}
                          </p>
                        </div>

                        {/* Action links */}
                        <div className="flex items-center gap-2">
                          {isActive(job.status) && (
                            <Link
                              href={`/track/${job.id}`}
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:text-primary/80 transition-colors whitespace-nowrap"
                            >
                              <svg
                                className="w-3.5 h-3.5"
                                fill="none"
                                viewBox="0 0 24 24"
                                strokeWidth={2}
                                stroke="currentColor"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z"
                                />
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z"
                                />
                              </svg>
                              Track
                            </Link>
                          )}
                          {job.status === "completed" && (
                            <Link
                              href={`/jobs/${job.id}/receipt`}
                              onClick={(e) => e.stopPropagation()}
                              className="inline-flex items-center gap-1 text-xs font-medium text-primary hover:text-primary/80 transition-colors whitespace-nowrap"
                            >
                              <svg
                                className="w-3.5 h-3.5"
                                fill="none"
                                viewBox="0 0 24 24"
                                strokeWidth={2}
                                stroke="currentColor"
                              >
                                <path
                                  strokeLinecap="round"
                                  strokeLinejoin="round"
                                  d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
                                />
                              </svg>
                              Receipt
                            </Link>
                          )}
                          {/* Chevron */}
                          <svg
                            className="w-5 h-5 text-muted-foreground hidden sm:block"
                            fill="none"
                            viewBox="0 0 24 24"
                            strokeWidth={1.5}
                            stroke="currentColor"
                          >
                            <path
                              strokeLinecap="round"
                              strokeLinejoin="round"
                              d="M8.25 4.5l7.5 7.5-7.5 7.5"
                            />
                          </svg>
                        </div>
                      </div>
                    </div>
                  </CardContent>
                </Card>
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page Component — dual mode
// ---------------------------------------------------------------------------

export default function DashboardPage() {
  const { isAuthenticated, isLoading } = useAuthStore();

  // Show nothing while auth state is loading to avoid flash
  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-24">
        <svg
          className="h-8 w-8 animate-spin text-primary"
          xmlns="http://www.w3.org/2000/svg"
          fill="none"
          viewBox="0 0 24 24"
        >
          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
        </svg>
      </div>
    );
  }

  if (isAuthenticated) {
    return <AuthenticatedDashboard />;
  }

  return <GuestLookup />;
}
