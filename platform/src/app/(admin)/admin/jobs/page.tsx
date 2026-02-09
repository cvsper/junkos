"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Briefcase,
  MoreHorizontal,
  UserPlus,
  XCircle,
  Eye,
  Check,
  X,
  Truck,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  adminApi,
  type AdminJobRecord,
  type AdminContractorRecord,
} from "@/lib/api";

const STATUS_TABS = [
  { label: "All", value: "" },
  { label: "Pending", value: "pending" },
  { label: "Active", value: "active" },
  { label: "Completed", value: "completed" },
  { label: "Cancelled", value: "cancelled" },
] as const;

function getStatusBadge(status: string) {
  const s = status.toLowerCase();
  if (s === "delegating") {
    return (
      <Badge className="bg-orange-500/15 text-orange-700 border-orange-300 hover:bg-orange-500/25">
        {status}
      </Badge>
    );
  }
  if (s === "pending" || s === "confirmed") {
    return (
      <Badge className="bg-yellow-500/15 text-yellow-700 border-yellow-300 hover:bg-yellow-500/25">
        {status}
      </Badge>
    );
  }
  if (
    s === "accepted" ||
    s === "assigned" ||
    s === "en_route" ||
    s === "arrived" ||
    s === "started" ||
    s === "in_progress" ||
    s === "active"
  ) {
    return (
      <Badge className="bg-blue-500/15 text-blue-700 border-blue-300 hover:bg-blue-500/25">
        {status}
      </Badge>
    );
  }
  if (s === "completed") {
    return (
      <Badge className="bg-green-500/15 text-green-700 border-green-300 hover:bg-green-500/25">
        {status}
      </Badge>
    );
  }
  if (s === "cancelled") {
    return <Badge variant="destructive">{status}</Badge>;
  }
  return <Badge variant="secondary">{status}</Badge>;
}

function truncateId(id: string): string {
  if (!id) return "--";
  return id.length > 8 ? `${id.slice(0, 8)}...` : id;
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "--";
  try {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function formatPrice(amount: number | undefined | null): string {
  if (amount == null) return "--";
  return `$${amount.toLocaleString(undefined, {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  })}`;
}

// ---------------------------------------------------------------------------
// Action Dropdown
// ---------------------------------------------------------------------------

function ActionDropdown({
  job,
  onAssign,
  onViewDetails,
  onCancel,
}: {
  job: AdminJobRecord;
  onAssign: () => void;
  onViewDetails: () => void;
  onCancel: () => void;
}) {
  const [open, setOpen] = useState(false);
  const ref = useRef<HTMLDivElement>(null);

  useEffect(() => {
    const handler = (e: MouseEvent) => {
      if (ref.current && !ref.current.contains(e.target as Node)) {
        setOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  const canAssign =
    job.status === "pending" || job.status === "confirmed" || job.status === "delegating";
  const canCancel =
    job.status !== "completed" && job.status !== "cancelled";

  return (
    <div className="relative" ref={ref}>
      <Button
        variant="ghost"
        size="icon"
        className="h-8 w-8"
        onClick={() => setOpen(!open)}
      >
        <MoreHorizontal className="h-4 w-4" />
      </Button>
      {open && (
        <div className="absolute right-0 top-full mt-1 w-48 rounded-md border border-border bg-card shadow-lg z-50">
          <div className="py-1">
            <button
              className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors"
              onClick={() => {
                setOpen(false);
                onViewDetails();
              }}
            >
              <Eye className="h-4 w-4 text-muted-foreground" />
              View Details
            </button>
            {canAssign && (
              <button
                className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors text-primary font-medium"
                onClick={() => {
                  setOpen(false);
                  onAssign();
                }}
              >
                <UserPlus className="h-4 w-4" />
                Assign Driver
              </button>
            )}
            {canCancel && (
              <button
                className="flex w-full items-center gap-2 px-3 py-2 text-sm hover:bg-muted transition-colors text-destructive"
                onClick={() => {
                  setOpen(false);
                  onCancel();
                }}
              >
                <XCircle className="h-4 w-4" />
                Cancel Job
              </button>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Assign Driver Modal
// ---------------------------------------------------------------------------

function AssignDriverModal({
  job,
  onClose,
  onAssigned,
}: {
  job: AdminJobRecord;
  onClose: () => void;
  onAssigned: () => void;
}) {
  const [contractors, setContractors] = useState<AdminContractorRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [assigning, setAssigning] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    async function load() {
      try {
        const res = await adminApi.contractors({ status: "approved" });
        setContractors(res.contractors || []);
      } catch {
        setError("Failed to load drivers");
      } finally {
        setLoading(false);
      }
    }
    load();
  }, []);

  const handleAssign = async (contractorId: string) => {
    setAssigning(contractorId);
    setError(null);
    try {
      await adminApi.assignJob(job.id, contractorId);
      onAssigned();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to assign driver"
      );
      setAssigning(null);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />
      <div className="relative bg-card border border-border rounded-lg shadow-xl w-full max-w-lg mx-4 max-h-[80vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <div>
            <h2 className="font-display text-lg font-bold">Assign Driver</h2>
            <p className="text-sm text-muted-foreground mt-0.5">
              Job {truncateId(job.id)} — {job.address || "No address"}
            </p>
          </div>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-6 py-4">
          {error && (
            <div className="mb-4 rounded-md bg-destructive/10 border border-destructive/20 px-4 py-3">
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {loading ? (
            <div className="flex items-center justify-center py-12">
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
              <span className="ml-2 text-sm text-muted-foreground">
                Loading available drivers...
              </span>
            </div>
          ) : contractors.length === 0 ? (
            <div className="text-center py-12">
              <Truck className="h-10 w-10 text-muted-foreground/50 mx-auto mb-3" />
              <p className="text-sm text-muted-foreground">
                No approved drivers available.
              </p>
              <p className="text-xs text-muted-foreground mt-1">
                Register and approve drivers in the Contractors tab first.
              </p>
            </div>
          ) : (
            <div className="space-y-4">
              {/* Operators Section */}
              {contractors.filter((c) => c.is_operator).length > 0 && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Fleet Operators</p>
                  <div className="space-y-2">
                    {contractors.filter((c) => c.is_operator).map((c) => (
                      <div
                        key={c.id}
                        className="flex items-center justify-between rounded-lg border border-amber-200 bg-amber-50/50 p-3 hover:bg-amber-50 transition-colors"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-9 h-9 rounded-full bg-amber-100 flex items-center justify-center flex-shrink-0">
                            <span className="text-sm font-medium text-amber-700">
                              {(c.name || "?")[0]?.toUpperCase()}
                            </span>
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">
                              {c.name || "Unnamed"}
                              <Badge className="ml-2 bg-amber-500/15 text-amber-700 border-amber-300 text-xs">
                                Operator{c.fleet_size ? ` (${c.fleet_size} drivers)` : ""}
                              </Badge>
                            </p>
                          </div>
                        </div>
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={assigning !== null}
                          onClick={() => handleAssign(c.id)}
                          className="border-amber-300 text-amber-700 hover:bg-amber-100"
                        >
                          {assigning === c.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <>
                              <Check className="h-4 w-4 mr-1" />
                              Delegate
                            </>
                          )}
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Regular Contractors Section */}
              {contractors.filter((c) => !c.is_operator).length > 0 && (
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wider mb-2">Contractors</p>
                  <div className="space-y-2">
                    {contractors.filter((c) => !c.is_operator).map((c) => (
                      <div
                        key={c.id}
                        className="flex items-center justify-between rounded-lg border border-border p-3 hover:bg-muted/30 transition-colors"
                      >
                        <div className="flex items-center gap-3 min-w-0">
                          <div className="w-9 h-9 rounded-full bg-primary/10 flex items-center justify-center flex-shrink-0">
                            <span className="text-sm font-medium text-primary">
                              {(c.name || "?")[0]?.toUpperCase()}
                            </span>
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-medium truncate">
                              {c.name || "Unnamed"}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {c.truck_type || "No vehicle info"}
                              {c.is_online && (
                                <span className="ml-2 text-green-600">
                                  ● Online
                                </span>
                              )}
                              {!c.is_online && (
                                <span className="ml-2 text-muted-foreground">
                                  ○ Offline
                                </span>
                              )}
                            </p>
                          </div>
                        </div>
                        <Button
                          size="sm"
                          disabled={assigning !== null}
                          onClick={() => handleAssign(c.id)}
                        >
                          {assigning === c.id ? (
                            <Loader2 className="h-4 w-4 animate-spin" />
                          ) : (
                            <>
                              <Check className="h-4 w-4 mr-1" />
                              Assign
                            </>
                          )}
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Job Detail Modal
// ---------------------------------------------------------------------------

function JobDetailModal({
  job,
  onClose,
}: {
  job: AdminJobRecord;
  onClose: () => void;
}) {
  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      <div className="absolute inset-0 bg-black/50" onClick={onClose} />
      <div className="relative bg-card border border-border rounded-lg shadow-xl w-full max-w-md mx-4 max-h-[80vh] overflow-y-auto">
        <div className="flex items-center justify-between px-6 py-4 border-b border-border">
          <h2 className="font-display text-lg font-bold">Job Details</h2>
          <Button variant="ghost" size="icon" onClick={onClose}>
            <X className="h-4 w-4" />
          </Button>
        </div>
        <div className="px-6 py-4 space-y-4">
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              Job ID
            </p>
            <p className="text-sm font-mono mt-0.5">{job.id}</p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              Customer
            </p>
            <p className="text-sm font-medium mt-0.5">
              {job.customer_name || "--"}
            </p>
            <p className="text-xs text-muted-foreground">
              {job.customer_email || ""}
            </p>
          </div>
          <div>
            <p className="text-xs text-muted-foreground uppercase tracking-wider">
              Address
            </p>
            <p className="text-sm mt-0.5">{job.address || "--"}</p>
          </div>
          <div className="flex gap-8">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">
                Status
              </p>
              <div className="mt-1">{getStatusBadge(job.status)}</div>
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">
                Price
              </p>
              <p className="text-sm font-medium mt-0.5">
                {formatPrice(job.final_price ?? job.estimated_price)}
              </p>
            </div>
          </div>
          <div className="flex gap-8">
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">
                Scheduled
              </p>
              <p className="text-sm mt-0.5">
                {formatDate(job.scheduled_date)}
                {job.scheduled_time_slot
                  ? ` at ${job.scheduled_time_slot}`
                  : ""}
              </p>
            </div>
            <div>
              <p className="text-xs text-muted-foreground uppercase tracking-wider">
                Created
              </p>
              <p className="text-sm mt-0.5">{formatDate(job.created_at)}</p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function AdminJobsPage() {
  const [jobs, setJobs] = useState<AdminJobRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

  // Modals
  const [assignJob, setAssignJob] = useState<AdminJobRecord | null>(null);
  const [detailJob, setDetailJob] = useState<AdminJobRecord | null>(null);

  const fetchJobs = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: Record<string, string | number> = { page, limit: 20 };
      if (statusFilter) filters.status = statusFilter;
      const res = await adminApi.jobs(filters);
      setJobs(res.jobs || []);
      setTotalPages(res.pages || 1);
      setTotal(res.total || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load jobs");
    } finally {
      setLoading(false);
    }
  }, [statusFilter, page]);

  useEffect(() => {
    fetchJobs();
  }, [fetchJobs]);

  const handleFilterChange = (value: string) => {
    setStatusFilter(value);
    setPage(1);
  };

  const handleCancelJob = async (job: AdminJobRecord) => {
    if (!confirm(`Cancel job ${truncateId(job.id)}?`)) return;
    try {
      await adminApi.cancelJob(job.id);
      fetchJobs();
    } catch (err) {
      alert(
        err instanceof Error ? err.message : "Failed to cancel job"
      );
    }
  };

  const SkeletonRow = () => (
    <tr className="border-b border-border">
      {Array.from({ length: 8 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 w-full max-w-[120px] rounded bg-muted animate-pulse" />
        </td>
      ))}
    </tr>
  );

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Jobs
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage and monitor all junk removal jobs.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchJobs}
          disabled={loading}
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      </div>

      {/* Status Filter Tabs */}
      <div className="flex items-center gap-2 mb-6 flex-wrap">
        {STATUS_TABS.map((tab) => (
          <Button
            key={tab.value}
            variant={statusFilter === tab.value ? "default" : "outline"}
            size="sm"
            onClick={() => handleFilterChange(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
        {total > 0 && (
          <span className="ml-auto text-sm text-muted-foreground">
            {total} job{total !== 1 ? "s" : ""} found
          </span>
        )}
      </div>

      {/* Error State */}
      {error && (
        <Card className="mb-6">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="h-10 w-10 text-destructive mb-3" />
            <p className="text-sm text-muted-foreground mb-4">{error}</p>
            <Button variant="outline" onClick={fetchJobs}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Jobs Table */}
      {!error && (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Job ID
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Customer
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Address
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Status
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Operator
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Scheduled
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Price
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <SkeletonRow key={i} />
                  ))
                ) : jobs.length === 0 ? (
                  <tr>
                    <td colSpan={8} className="text-center py-12">
                      <div className="flex flex-col items-center gap-2">
                        <Briefcase className="h-10 w-10 text-muted-foreground/50" />
                        <p className="text-muted-foreground text-sm">
                          {statusFilter
                            ? `No ${statusFilter} jobs found.`
                            : "No jobs found. Jobs will appear here once customers start booking."}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  jobs.map((job) => (
                    <tr
                      key={job.id}
                      className="border-b border-border hover:bg-muted/30 transition-colors"
                    >
                      <td className="px-4 py-3 text-sm font-mono">
                        <span title={job.id}>{truncateId(job.id)}</span>
                      </td>
                      <td className="px-4 py-3">
                        <p className="text-sm font-medium">
                          {job.customer_name || "--"}
                        </p>
                        <p className="text-xs text-muted-foreground">
                          {job.customer_email || ""}
                        </p>
                      </td>
                      <td className="px-4 py-3 text-sm max-w-[200px] truncate">
                        {job.address || "--"}
                      </td>
                      <td className="px-4 py-3">
                        {getStatusBadge(job.status)}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {job.operator_id
                          ? <Badge className="bg-amber-500/15 text-amber-700 border-amber-300 text-xs">Operator</Badge>
                          : "-"}
                      </td>
                      <td className="px-4 py-3 text-sm text-muted-foreground">
                        {formatDate(job.scheduled_date)}
                      </td>
                      <td className="px-4 py-3 text-sm font-medium">
                        {formatPrice(job.final_price ?? job.estimated_price)}
                      </td>
                      <td className="px-4 py-3">
                        <ActionDropdown
                          job={job}
                          onAssign={() => setAssignJob(job)}
                          onViewDetails={() => setDetailJob(job)}
                          onCancel={() => handleCancelJob(job)}
                        />
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>

          {/* Pagination */}
          {!loading && totalPages > 1 && (
            <div className="flex items-center justify-between border-t border-border px-4 py-3">
              <p className="text-sm text-muted-foreground">
                Page {page} of {totalPages}
              </p>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page <= 1}
                  onClick={() => setPage((p) => Math.max(1, p - 1))}
                >
                  <ChevronLeft className="h-4 w-4 mr-1" />
                  Previous
                </Button>
                {Array.from({ length: Math.min(5, totalPages) }).map(
                  (_, i) => {
                    let pageNum: number;
                    if (totalPages <= 5) {
                      pageNum = i + 1;
                    } else if (page <= 3) {
                      pageNum = i + 1;
                    } else if (page >= totalPages - 2) {
                      pageNum = totalPages - 4 + i;
                    } else {
                      pageNum = page - 2 + i;
                    }
                    return (
                      <Button
                        key={pageNum}
                        variant={pageNum === page ? "default" : "outline"}
                        size="sm"
                        className="w-9"
                        onClick={() => setPage(pageNum)}
                      >
                        {pageNum}
                      </Button>
                    );
                  }
                )}
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() =>
                    setPage((p) => Math.min(totalPages, p + 1))
                  }
                >
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </div>
      )}

      {/* Assign Driver Modal */}
      {assignJob && (
        <AssignDriverModal
          job={assignJob}
          onClose={() => setAssignJob(null)}
          onAssigned={() => {
            setAssignJob(null);
            fetchJobs();
          }}
        />
      )}

      {/* Job Detail Modal */}
      {detailJob && (
        <JobDetailModal
          job={detailJob}
          onClose={() => setDetailJob(null)}
        />
      )}
    </div>
  );
}
