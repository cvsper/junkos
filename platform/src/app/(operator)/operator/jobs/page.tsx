"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Briefcase,
  ChevronLeft,
  ChevronRight,
  ClipboardList,
  Loader2,
  X,
  Copy,
  Check,
} from "lucide-react";
import { operatorApi, type OperatorJobRecord, type OperatorFleetContractor } from "@/lib/api";

const STATUS_BADGES: Record<string, string> = {
  delegating: "bg-amber-100 text-amber-700",
  assigned: "bg-blue-100 text-blue-700",
  accepted: "bg-indigo-100 text-indigo-700",
  en_route: "bg-purple-100 text-purple-700",
  arrived: "bg-cyan-100 text-cyan-700",
  started: "bg-teal-100 text-teal-700",
  completed: "bg-green-100 text-green-700",
  cancelled: "bg-red-100 text-red-700",
};

const FILTER_TABS = [
  { key: "all", label: "All" },
  { key: "delegating", label: "Needs Delegation" },
  { key: "active", label: "Active" },
  { key: "completed", label: "Completed" },
];

export default function OperatorJobsPage() {
  const [jobs, setJobs] = useState<OperatorJobRecord[]>([]);
  const [fleet, setFleet] = useState<OperatorFleetContractor[]>([]);
  const [filter, setFilter] = useState("all");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [loading, setLoading] = useState(true);
  const [delegateJob, setDelegateJob] = useState<OperatorJobRecord | null>(null);
  const [delegating, setDelegating] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);
  const [volumeJob, setVolumeJob] = useState<OperatorJobRecord | null>(null);
  const [volumeInput, setVolumeInput] = useState("");
  const [volumeBusy, setVolumeBusy] = useState(false);
  const [volumeResult, setVolumeResult] = useState<
    | { autoApproved: boolean; newPrice: number; originalPrice: number }
    | { error: string }
    | null
  >(null);

  const submitVolume = async () => {
    if (!volumeJob) return;
    const v = Number(volumeInput);
    if (!v || v <= 0) {
      setVolumeResult({ error: "Enter a positive cubic-yard number." });
      return;
    }
    setVolumeBusy(true);
    setVolumeResult(null);
    try {
      const res = await operatorApi.proposeVolumeAdjustment(volumeJob.id, v);
      setVolumeResult({
        autoApproved: !!res.auto_approved,
        newPrice: res.new_price,
        originalPrice: res.original_price ?? volumeJob.total_price ?? 0,
      });
      loadJobs();
    } catch (e) {
      const msg = e instanceof Error ? e.message : String(e);
      setVolumeResult({ error: msg });
    } finally {
      setVolumeBusy(false);
    }
  };

  const copyJobId = (jobId: string) => {
    navigator.clipboard.writeText(jobId);
    setCopiedId(jobId);
    setTimeout(() => setCopiedId(null), 2000);
  };

  const loadJobs = useCallback(async () => {
    setLoading(true);
    try {
      const res = await operatorApi.jobs(filter, page);
      setJobs(res.jobs);
      setTotalPages(res.pages);
    } catch {
      // silent
    } finally {
      setLoading(false);
    }
  }, [filter, page]);

  useEffect(() => {
    loadJobs();
  }, [loadJobs]);

  useEffect(() => {
    if (delegateJob) {
      operatorApi.fleet().then((res) => setFleet(res.contractors)).catch(() => {});
    }
  }, [delegateJob]);

  const handleDelegate = async (contractorId: string) => {
    if (!delegateJob) return;
    setDelegating(true);
    try {
      await operatorApi.delegateJob(delegateJob.id, contractorId);
      setDelegateJob(null);
      loadJobs();
    } catch {
      // silent
    } finally {
      setDelegating(false);
    }
  };

  const getEmptyMessage = () => {
    switch (filter) {
      case "delegating":
        return "No jobs waiting for delegation. You're all caught up!";
      case "active":
        return "No active jobs at the moment. Jobs in progress will appear here.";
      case "completed":
        return "No completed jobs yet. Completed jobs will show up here.";
      default:
        return "No jobs found. Jobs from your customers will appear here once they book.";
    }
  };

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-display font-bold">Jobs</h1>

      {/* Filter Tabs */}
      <div className="flex gap-2 flex-wrap">
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => { setFilter(tab.key); setPage(1); }}
            className={`px-3 sm:px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              filter === tab.key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Jobs Table - Desktop */}
      <div className="rounded-xl border border-border bg-card overflow-hidden hidden md:block">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Job ID</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Customer</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Address</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Driver</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Price</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                [...Array(5)].map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-16" /></td>
                    <td className="px-4 py-3">
                      <div className="space-y-1">
                        <div className="h-4 bg-muted rounded w-24" />
                        <div className="h-3 bg-muted rounded w-32" />
                      </div>
                    </td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-40" /></td>
                    <td className="px-4 py-3"><div className="h-6 bg-muted rounded-full w-20" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-20" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-16" /></td>
                    <td className="px-4 py-3"><div className="h-8 bg-muted rounded w-20" /></td>
                  </tr>
                ))
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-1">
                        <ClipboardList className="w-6 h-6 text-muted-foreground/60" />
                      </div>
                      <p className="text-sm text-muted-foreground">{getEmptyMessage()}</p>
                    </div>
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3">
                      <button
                        onClick={() => copyJobId(job.id)}
                        className="flex items-center gap-1.5 font-mono text-xs hover:text-primary transition-colors group"
                        title="Click to copy full job ID"
                      >
                        <span>{job.id.slice(0, 8)}...</span>
                        {copiedId === job.id ? (
                          <Check className="w-3 h-3 text-green-600" />
                        ) : (
                          <Copy className="w-3 h-3 opacity-0 group-hover:opacity-100 transition-opacity" />
                        )}
                      </button>
                    </td>
                    <td className="px-4 py-3">
                      <div>
                        <p className="font-medium">{job.customer_name || "N/A"}</p>
                        <p className="text-xs text-muted-foreground">{job.customer_email}</p>
                      </div>
                    </td>
                    <td className="px-4 py-3 max-w-[200px] truncate">{job.address}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${STATUS_BADGES[job.status] || "bg-gray-100 text-gray-700"}`}>
                        {job.status}
                      </span>
                    </td>
                    <td className="px-4 py-3">{job.driver_name || "-"}</td>
                    <td className="px-4 py-3">${job.total_price?.toFixed(2)}</td>
                    <td className="px-4 py-3">
                      {job.status === "delegating" && (
                        <button
                          onClick={() => setDelegateJob(job)}
                          className="text-xs bg-amber-100 text-amber-700 px-3 py-1.5 rounded-lg font-medium hover:bg-amber-200 transition-colors"
                        >
                          Delegate
                        </button>
                      )}
                      {job.status === "arrived" && (
                        <button
                          onClick={() => {
                            setVolumeJob(job);
                            setVolumeInput("");
                            setVolumeResult(null);
                          }}
                          className="text-xs bg-amber-100 text-amber-700 px-3 py-1.5 rounded-lg font-medium hover:bg-amber-200 transition-colors"
                        >
                          Adjust Volume
                        </button>
                      )}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination - Desktop */}
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

      {/* Jobs Cards - Mobile */}
      <div className="md:hidden space-y-3">
        {loading ? (
          [...Array(4)].map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse space-y-3">
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
            <p className="text-sm text-muted-foreground">{getEmptyMessage()}</p>
          </div>
        ) : (
          jobs.map((job) => (
            <div key={job.id} className="rounded-xl border border-border bg-card p-4 space-y-3">
              <div className="flex items-center justify-between">
                <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${STATUS_BADGES[job.status] || "bg-gray-100 text-gray-700"}`}>
                  {job.status}
                </span>
                <span className="text-sm font-semibold">${job.total_price?.toFixed(2)}</span>
              </div>
              <div>
                <p className="text-sm font-medium">{job.address}</p>
                <p className="text-xs text-muted-foreground mt-0.5">
                  {job.customer_name || "N/A"} &middot; {job.customer_email}
                </p>
              </div>
              <div className="flex items-center justify-between">
                <div className="text-xs text-muted-foreground">
                  {job.driver_name ? (
                    <span>Driver: <span className="font-medium text-foreground">{job.driver_name}</span></span>
                  ) : (
                    <button
                      onClick={() => copyJobId(job.id)}
                      className="flex items-center gap-1 font-mono text-xs hover:text-primary transition-colors"
                    >
                      <span>{job.id.slice(0, 8)}...</span>
                      {copiedId === job.id ? (
                        <Check className="w-3 h-3 text-green-600" />
                      ) : (
                        <Copy className="w-3 h-3" />
                      )}
                    </button>
                  )}
                </div>
                {job.status === "delegating" && (
                  <button
                    onClick={() => setDelegateJob(job)}
                    className="text-xs bg-amber-100 text-amber-700 px-3 py-1.5 rounded-lg font-medium hover:bg-amber-200 transition-colors"
                  >
                    Delegate
                  </button>
                )}
                {job.status === "arrived" && (
                  <button
                    onClick={() => {
                      setVolumeJob(job);
                      setVolumeInput("");
                      setVolumeResult(null);
                    }}
                    className="text-xs bg-amber-100 text-amber-700 px-3 py-1.5 rounded-lg font-medium hover:bg-amber-200 transition-colors"
                  >
                    Adjust Volume
                  </button>
                )}
              </div>
            </div>
          ))
        )}

        {/* Pagination - Mobile */}
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

      {/* Delegate Modal */}
      {delegateJob && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50" onClick={() => setDelegateJob(null)}>
          <div
            className="bg-card rounded-t-xl sm:rounded-xl border border-border shadow-xl w-full sm:max-w-md sm:mx-4 max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-4 sm:px-6 py-4 border-b border-border flex items-center justify-between flex-shrink-0">
              <div className="min-w-0 pr-4">
                <h3 className="font-semibold">Delegate Job</h3>
                <p className="text-sm text-muted-foreground mt-1 truncate">{delegateJob.address}</p>
              </div>
              <button
                onClick={() => setDelegateJob(null)}
                className="p-1 rounded-lg hover:bg-muted transition-colors flex-shrink-0"
              >
                <X className="w-5 h-5" />
              </button>
            </div>
            <div className="px-4 sm:px-6 py-4 overflow-y-auto flex-1">
              {fleet.length === 0 ? (
                <div className="flex flex-col items-center py-8 text-center">
                  <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
                    <Briefcase className="w-6 h-6 text-muted-foreground/60" />
                  </div>
                  <p className="text-sm text-muted-foreground">No fleet contractors available</p>
                </div>
              ) : (
                <div className="space-y-2">
                  {fleet.filter((c) => c.approval_status === "approved").map((c) => (
                    <button
                      key={c.id}
                      onClick={() => handleDelegate(c.id)}
                      disabled={delegating}
                      className="w-full flex items-center justify-between p-3 rounded-lg border border-border hover:bg-muted/50 transition-colors disabled:opacity-50"
                    >
                      <div className="text-left">
                        <p className="text-sm font-medium">{c.name || "Unnamed"}</p>
                        <p className="text-xs text-muted-foreground">
                          {c.truck_type || "N/A"} &middot; {c.total_jobs} jobs &middot; {c.avg_rating.toFixed(1)} stars
                        </p>
                      </div>
                      <div className="flex items-center gap-2">
                        {delegating && (
                          <Loader2 className="w-4 h-4 animate-spin text-muted-foreground" />
                        )}
                        <span className={`w-2.5 h-2.5 rounded-full ${c.is_online ? "bg-green-500" : "bg-gray-300"}`} />
                      </div>
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="px-4 sm:px-6 py-3 border-t border-border flex justify-end flex-shrink-0">
              <button
                onClick={() => setDelegateJob(null)}
                className="text-sm px-4 py-2 rounded-lg border border-border hover:bg-muted transition-colors"
              >
                Cancel
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Volume Adjustment Modal */}
      {volumeJob && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50"
          onClick={() => setVolumeJob(null)}
        >
          <div
            className="bg-white rounded-t-2xl sm:rounded-2xl w-full sm:max-w-md max-h-[90vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            <div className="px-5 py-4 border-b border-border">
              <h3 className="font-semibold">Adjust volume on-site</h3>
              <p className="text-xs text-muted-foreground mt-1">
                Job at {volumeJob.address || "—"} · current ${volumeJob.total_price?.toFixed(2)}
              </p>
            </div>
            <div className="px-5 py-4 space-y-3">
              <p className="text-xs text-muted-foreground">
                Enter the actual volume the driver sees (cubic yards). Auto-approves
                if the new price drops; otherwise the customer is pinged to accept.
              </p>
              <input
                type="number"
                step="0.5"
                min="0.5"
                placeholder="cubic yards"
                value={volumeInput}
                onChange={(e) => setVolumeInput(e.target.value)}
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm"
                disabled={volumeBusy}
              />
              {volumeResult && "error" in volumeResult && (
                <div className="text-sm rounded bg-red-50 border border-red-200 p-2 text-red-700">
                  {volumeResult.error}
                </div>
              )}
              {volumeResult && "autoApproved" in volumeResult && volumeResult.autoApproved && (
                <div className="text-sm rounded bg-emerald-50 border border-emerald-300 p-2 text-emerald-800">
                  ✓ Auto-approved. New: ${volumeResult.newPrice.toFixed(2)} (was ${volumeResult.originalPrice.toFixed(2)}).
                </div>
              )}
              {volumeResult && "autoApproved" in volumeResult && !volumeResult.autoApproved && (
                <div className="text-sm rounded bg-amber-50 border border-amber-300 p-2 text-amber-900">
                  Sent to customer. Proposed ${volumeResult.newPrice.toFixed(2)} (was ${volumeResult.originalPrice.toFixed(2)}).
                </div>
              )}
            </div>
            <div className="px-5 py-3 border-t border-border flex justify-end gap-2">
              <button
                onClick={() => setVolumeJob(null)}
                className="text-sm px-4 py-2 rounded-lg border border-border hover:bg-muted"
              >
                Close
              </button>
              <button
                onClick={submitVolume}
                disabled={volumeBusy || !volumeInput}
                className="text-sm px-4 py-2 rounded-lg bg-amber-600 text-white hover:bg-amber-700 disabled:opacity-50 inline-flex items-center gap-2"
              >
                {volumeBusy && <Loader2 className="w-4 h-4 animate-spin" />}
                {volumeBusy ? "Submitting…" : "Submit"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
