"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  Briefcase,
  MoreHorizontal,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { adminApi, type AdminJobRecord } from "@/lib/api";

const STATUS_TABS = [
  { label: "All", value: "" },
  { label: "Pending", value: "pending" },
  { label: "Active", value: "active" },
  { label: "Completed", value: "completed" },
  { label: "Cancelled", value: "cancelled" },
] as const;

function getStatusBadge(status: string) {
  const s = status.toLowerCase();
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
    return (
      <Badge variant="destructive">{status}</Badge>
    );
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

export default function AdminJobsPage() {
  const [jobs, setJobs] = useState<AdminJobRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);

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

  // Reset page when filter changes
  const handleFilterChange = (value: string) => {
    setStatusFilter(value);
    setPage(1);
  };

  // Table skeleton rows
  const SkeletonRow = () => (
    <tr className="border-b border-border">
      {Array.from({ length: 7 }).map((_, i) => (
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
        <Button variant="outline" size="sm" onClick={fetchJobs} disabled={loading}>
          <RefreshCw className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`} />
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
                    <td
                      colSpan={7}
                      className="text-center py-12"
                    >
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
                        <p className="text-sm font-medium">{job.customer_name || "--"}</p>
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
                        {formatDate(job.scheduled_date)}
                      </td>
                      <td className="px-4 py-3 text-sm font-medium">
                        {formatPrice(job.final_price ?? job.estimated_price)}
                      </td>
                      <td className="px-4 py-3">
                        <Button variant="ghost" size="icon" className="h-8 w-8">
                          <MoreHorizontal className="h-4 w-4" />
                        </Button>
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
                {/* Page number buttons (show up to 5) */}
                {Array.from({ length: Math.min(5, totalPages) }).map((_, i) => {
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
                })}
                <Button
                  variant="outline"
                  size="sm"
                  disabled={page >= totalPages}
                  onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
                >
                  Next
                  <ChevronRight className="h-4 w-4 ml-1" />
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
