"use client";

import { useEffect, useState, useCallback } from "react";
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

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-display font-bold">Jobs</h1>

      {/* Filter Tabs */}
      <div className="flex gap-2 flex-wrap">
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => { setFilter(tab.key); setPage(1); }}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              filter === tab.key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Jobs Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
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
                  <tr key={i}>
                    {[...Array(7)].map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 bg-muted rounded animate-pulse w-20" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : jobs.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    No jobs found
                  </td>
                </tr>
              ) : (
                jobs.map((job) => (
                  <tr key={job.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-mono text-xs">{job.id.slice(0, 8)}</td>
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
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-4 py-3 border-t border-border flex items-center justify-between">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="text-sm px-3 py-1.5 rounded-lg border border-border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Previous
            </button>
            <span className="text-sm text-muted-foreground">
              Page {page} of {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="text-sm px-3 py-1.5 rounded-lg border border-border hover:bg-muted disabled:opacity-50 disabled:cursor-not-allowed"
            >
              Next
            </button>
          </div>
        )}
      </div>

      {/* Delegate Modal */}
      {delegateJob && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setDelegateJob(null)}>
          <div className="bg-card rounded-xl border border-border shadow-xl w-full max-w-md mx-4" onClick={(e) => e.stopPropagation()}>
            <div className="px-6 py-4 border-b border-border">
              <h3 className="font-semibold">Delegate Job</h3>
              <p className="text-sm text-muted-foreground mt-1 truncate">{delegateJob.address}</p>
            </div>
            <div className="px-6 py-4 max-h-80 overflow-y-auto">
              {fleet.length === 0 ? (
                <p className="text-sm text-muted-foreground text-center py-4">No fleet contractors available</p>
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
                      <span className={`w-2.5 h-2.5 rounded-full ${c.is_online ? "bg-green-500" : "bg-gray-300"}`} />
                    </button>
                  ))}
                </div>
              )}
            </div>
            <div className="px-6 py-3 border-t border-border flex justify-end">
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
    </div>
  );
}
