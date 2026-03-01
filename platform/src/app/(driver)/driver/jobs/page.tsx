"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import {
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  MapPin,
  Navigation,
  Loader2,
} from "lucide-react";
import { driverApi, ApiError } from "@/lib/api";
import type { DriverJob } from "@/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FILTER_TABS = [
  { key: "available", label: "Available" },
  { key: "active", label: "My Active" },
  { key: "completed", label: "Completed" },
];

const RADIUS_OPTIONS = [10, 20, 30, 50];

const STATUS_BADGES: Record<string, string> = {
  pending: "bg-gray-100 text-gray-700",
  confirmed: "bg-blue-100 text-blue-700",
  assigned: "bg-indigo-100 text-indigo-700",
  en_route: "bg-amber-100 text-amber-700",
  arrived: "bg-orange-100 text-orange-700",
  in_progress: "bg-purple-100 text-purple-700",
  completed: "bg-emerald-100 text-emerald-700",
  cancelled: "bg-red-100 text-red-700",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusLabel(s: string) {
  return s
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDistance(miles: number | null) {
  if (miles == null) return "--";
  return `${miles.toFixed(1)} mi`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DriverJobsPage() {
  const [filter, setFilter] = useState("available");
  const [radius, setRadius] = useState(20);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [jobs, setJobs] = useState<DriverJob[]>([]);
  const [loading, setLoading] = useState(true);
  const [acceptingId, setAcceptingId] = useState<string | null>(null);

  // ---- Data fetching ----
  const loadJobs = useCallback(async () => {
    setLoading(true);
    try {
      if (filter === "available") {
        const res = await driverApi.availableJobs(radius, page);
        setJobs(res.jobs);
        setTotalPages(res.pages);
      } else if (filter === "active") {
        const res = await driverApi.activeJobs();
        setJobs(res.jobs);
        setTotalPages(1);
      } else {
        const res = await driverApi.completedJobs(page);
        setJobs(res.jobs);
        setTotalPages(res.pages);
      }
    } catch {
      setJobs([]);
      setTotalPages(1);
    } finally {
      setLoading(false);
    }
  }, [filter, radius, page]);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  // Reset page when filter or radius changes
  useEffect(() => {
    setPage(1);
  }, [filter, radius]);

  // ---- Accept job ----
  const handleAccept = async (jobId: string) => {
    setAcceptingId(jobId);
    try {
      await driverApi.acceptJob(jobId);
      // Remove from available list on success
      setJobs((prev) => prev.filter((j) => j.id !== jobId));
    } catch {
      // silent
    } finally {
      setAcceptingId(null);
    }
  };

  // ---- Empty state messages ----
  const emptyMessage = () => {
    switch (filter) {
      case "available":
        return "No jobs available in your area right now";
      case "active":
        return "No active jobs";
      case "completed":
        return "No completed jobs yet";
      default:
        return "No jobs found";
    }
  };

  // ---- Render ----
  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-display font-bold">Jobs</h1>

      {/* ---- Filter Tabs ---- */}
      <div className="flex flex-wrap items-center gap-2">
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setFilter(tab.key)}
            className={`px-3 sm:px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              filter === tab.key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}

        {/* Radius selector — only for available */}
        {filter === "available" && (
          <div className="ml-auto flex items-center gap-2">
            <Navigation className="w-4 h-4 text-muted-foreground" />
            <select
              value={radius}
              onChange={(e) => setRadius(Number(e.target.value))}
              className="text-sm border border-border rounded-lg px-2 py-1.5 bg-card focus:outline-none focus:ring-2 focus:ring-primary/30"
            >
              {RADIUS_OPTIONS.map((r) => (
                <option key={r} value={r}>
                  {r} miles
                </option>
              ))}
            </select>
          </div>
        )}
      </div>

      {/* ================================================================== */}
      {/* Desktop Table                                                       */}
      {/* ================================================================== */}
      <div className="rounded-xl border border-border bg-card overflow-hidden hidden md:block">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Address</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Customer</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Distance</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Price</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                [...Array(5)].map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-44" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-24" /></td>
                    <td className="px-4 py-3"><div className="h-6 bg-muted rounded-full w-20" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-16" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-16" /></td>
                    <td className="px-4 py-3"><div className="h-8 bg-muted rounded w-24" /></td>
                  </tr>
                ))
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-12 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-1">
                        <ClipboardList className="w-6 h-6 text-muted-foreground/60" />
                      </div>
                      <p className="text-sm text-muted-foreground">{emptyMessage()}</p>
                    </div>
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 max-w-[240px]">
                      <div className="flex items-start gap-2">
                        <MapPin className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
                        <span className="truncate">{job.address}</span>
                      </div>
                    </td>
                    <td className="px-4 py-3">{job.customer_name || "N/A"}</td>
                    <td className="px-4 py-3">
                      <span
                        className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${
                          STATUS_BADGES[job.status] || "bg-gray-100 text-gray-700"
                        }`}
                      >
                        {statusLabel(job.status)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {formatDistance(job.distance_miles)}
                    </td>
                    <td className="px-4 py-3 font-semibold">
                      ${job.total_price.toFixed(2)}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <Link
                          href={`/driver/jobs/${job.id}`}
                          className="text-xs bg-muted text-muted-foreground px-3 py-1.5 rounded-lg font-medium hover:bg-muted/80 transition-colors"
                        >
                          View
                        </Link>
                        {filter === "available" && (
                          <button
                            onClick={() => handleAccept(job.id)}
                            disabled={acceptingId === job.id}
                            className="text-xs bg-emerald-100 text-emerald-700 px-3 py-1.5 rounded-lg font-medium hover:bg-emerald-200 transition-colors disabled:opacity-50 inline-flex items-center gap-1.5"
                          >
                            {acceptingId === job.id && (
                              <Loader2 className="w-3 h-3 animate-spin" />
                            )}
                            Accept
                          </button>
                        )}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination — Desktop */}
        {!loading && totalPages > 1 && (
          <div className="px-4 py-3 border-t border-border flex items-center justify-between">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="inline-flex items-center gap-1 text-sm px-3 py-1.5 rounded-lg border border-border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
              Previous
            </button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="inline-flex items-center gap-1 text-sm px-3 py-1.5 rounded-lg border border-border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>

      {/* ================================================================== */}
      {/* Mobile Cards                                                        */}
      {/* ================================================================== */}
      <div className="md:hidden space-y-3">
        {loading ? (
          [...Array(4)].map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-border bg-card p-4 animate-pulse space-y-3"
            >
              <div className="flex items-center justify-between">
                <div className="h-6 bg-muted rounded-full w-20" />
                <div className="h-4 bg-muted rounded w-16" />
              </div>
              <div className="space-y-2">
                <div className="h-4 bg-muted rounded w-3/4" />
                <div className="h-3 bg-muted rounded w-1/2" />
              </div>
              <div className="flex items-center justify-between">
                <div className="h-3 bg-muted rounded w-24" />
                <div className="h-8 bg-muted rounded w-20" />
              </div>
            </div>
          ))
        ) : jobs.length === 0 ? (
          <div className="rounded-xl border border-border bg-card px-4 py-12 flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
              <ClipboardList className="w-6 h-6 text-muted-foreground/60" />
            </div>
            <p className="text-sm text-muted-foreground">{emptyMessage()}</p>
          </div>
        ) : (
          jobs.map((job) => (
            <div
              key={job.id}
              className="rounded-xl border border-border bg-card p-4 space-y-3"
            >
              {/* Row 1: status + price */}
              <div className="flex items-center justify-between">
                <span
                  className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${
                    STATUS_BADGES[job.status] || "bg-gray-100 text-gray-700"
                  }`}
                >
                  {statusLabel(job.status)}
                </span>
                <span className="text-sm font-semibold">
                  ${job.total_price.toFixed(2)}
                </span>
              </div>

              {/* Row 2: address + customer */}
              <div>
                <div className="flex items-start gap-2">
                  <MapPin className="w-4 h-4 text-muted-foreground mt-0.5 shrink-0" />
                  <p className="text-sm font-medium">{job.address}</p>
                </div>
                <p className="text-xs text-muted-foreground mt-1 ml-6">
                  {job.customer_name || "N/A"}
                  {job.distance_miles != null && (
                    <> &middot; {formatDistance(job.distance_miles)}</>
                  )}
                </p>
              </div>

              {/* Row 3: actions */}
              <div className="flex items-center justify-end gap-2">
                <Link
                  href={`/driver/jobs/${job.id}`}
                  className="text-xs bg-muted text-muted-foreground px-3 py-1.5 rounded-lg font-medium hover:bg-muted/80 transition-colors"
                >
                  View
                </Link>
                {filter === "available" && (
                  <button
                    onClick={() => handleAccept(job.id)}
                    disabled={acceptingId === job.id}
                    className="text-xs bg-emerald-100 text-emerald-700 px-3 py-1.5 rounded-lg font-medium hover:bg-emerald-200 transition-colors disabled:opacity-50 inline-flex items-center gap-1.5"
                  >
                    {acceptingId === job.id && (
                      <Loader2 className="w-3 h-3 animate-spin" />
                    )}
                    Accept
                  </button>
                )}
              </div>
            </div>
          ))
        )}

        {/* Pagination — Mobile */}
        {!loading && totalPages > 1 && (
          <div className="flex items-center justify-between pt-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="inline-flex items-center gap-1 text-sm px-3 py-1.5 rounded-lg border border-border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <ChevronLeft className="w-4 h-4" />
              Prev
            </button>
            <span className="text-sm text-muted-foreground">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="inline-flex items-center gap-1 text-sm px-3 py-1.5 rounded-lg border border-border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
              <ChevronRight className="w-4 h-4" />
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
