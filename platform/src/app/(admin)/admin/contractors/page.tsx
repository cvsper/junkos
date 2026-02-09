"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  HardHat,
  CheckCircle,
  XCircle,
  Star,
  Shield,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { adminApi, type AdminContractorRecord } from "@/lib/api";

const FILTER_TABS = [
  { label: "All", value: "" },
  { label: "Pending", value: "pending" },
  { label: "Approved", value: "approved" },
  { label: "Suspended", value: "suspended" },
] as const;

const TYPE_TABS = [
  { label: "All Types", value: "" },
  { label: "Operators", value: "operator" },
  { label: "Fleet", value: "fleet" },
  { label: "Independent", value: "independent" },
] as const;

function getTypeBadge(c: AdminContractorRecord) {
  if (c.is_operator) {
    return (
      <Badge className="bg-amber-500/15 text-amber-700 border-amber-300 hover:bg-amber-500/25">
        Operator{c.fleet_size ? ` (${c.fleet_size})` : ""}
      </Badge>
    );
  }
  if (c.operator_id) {
    return (
      <Badge className="bg-blue-500/15 text-blue-700 border-blue-300 hover:bg-blue-500/25">
        Fleet{c.operator_name ? ` - ${c.operator_name}` : ""}
      </Badge>
    );
  }
  return (
    <Badge variant="secondary">Independent</Badge>
  );
}

function getApprovalBadge(status: string) {
  const s = status.toLowerCase();
  if (s === "approved") {
    return (
      <Badge className="bg-green-500/15 text-green-700 border-green-300 hover:bg-green-500/25">
        Approved
      </Badge>
    );
  }
  if (s === "pending") {
    return (
      <Badge className="bg-yellow-500/15 text-yellow-700 border-yellow-300 hover:bg-yellow-500/25">
        Pending
      </Badge>
    );
  }
  if (s === "suspended") {
    return (
      <Badge variant="destructive">Suspended</Badge>
    );
  }
  return <Badge variant="secondary">{status}</Badge>;
}

function formatRating(rating: number | null | undefined): string {
  if (rating == null || rating === 0) return "--";
  return rating.toFixed(1);
}

export default function AdminContractorsPage() {
  const [contractors, setContractors] = useState<AdminContractorRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("");
  const [typeFilter, setTypeFilter] = useState("");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchContractors = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: Record<string, string | number> = { page, limit: 20 };
      if (filter) filters.approval_status = filter;
      if (typeFilter) filters.type = typeFilter;
      const res = await adminApi.contractors(filters);
      setContractors(res.contractors || []);
      setTotalPages(res.pages || 1);
      setTotal(res.total || 0);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load contractors"
      );
    } finally {
      setLoading(false);
    }
  }, [filter, typeFilter, page]);

  useEffect(() => {
    fetchContractors();
  }, [fetchContractors]);

  const handleFilterChange = (value: string) => {
    setFilter(value);
    setPage(1);
  };

  const handleApprove = async (contractor: AdminContractorRecord) => {
    const confirmed = window.confirm(
      `Are you sure you want to approve ${contractor.name || "this contractor"}? They will be able to accept jobs immediately.`
    );
    if (!confirmed) return;

    setActionLoading(contractor.id);
    try {
      await adminApi.approveContractor(contractor.id);
      await fetchContractors();
    } catch (err) {
      alert(
        err instanceof Error
          ? err.message
          : "Failed to approve contractor. Please try again."
      );
    } finally {
      setActionLoading(null);
    }
  };

  const handleSuspend = async (contractor: AdminContractorRecord) => {
    const confirmed = window.confirm(
      `Are you sure you want to suspend ${contractor.name || "this contractor"}? They will no longer be able to accept jobs.`
    );
    if (!confirmed) return;

    setActionLoading(contractor.id);
    try {
      await adminApi.suspendContractor(contractor.id);
      await fetchContractors();
    } catch (err) {
      alert(
        err instanceof Error
          ? err.message
          : "Failed to suspend contractor. Please try again."
      );
    } finally {
      setActionLoading(null);
    }
  };

  const handlePromoteToOperator = async (contractor: AdminContractorRecord) => {
    const confirmed = window.confirm(
      `Are you sure you want to promote ${contractor.name || "this contractor"} to Operator? They will be able to manage a fleet of contractors.`
    );
    if (!confirmed) return;

    setActionLoading(contractor.id);
    try {
      await adminApi.promoteToOperator(contractor.id);
      await fetchContractors();
    } catch (err) {
      alert(
        err instanceof Error
          ? err.message
          : "Failed to promote contractor. Please try again."
      );
    } finally {
      setActionLoading(null);
    }
  };

  // Table skeleton rows
  const SkeletonRow = () => (
    <tr className="border-b border-border">
      {Array.from({ length: 9 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 w-full max-w-[100px] rounded bg-muted animate-pulse" />
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
            Contractors
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage your network of junk removal contractors.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchContractors}
          disabled={loading}
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
      </div>

      {/* Filter Tabs */}
      <div className="flex items-center gap-2 mb-6 flex-wrap">
        {FILTER_TABS.map((tab) => (
          <Button
            key={tab.value}
            variant={filter === tab.value ? "default" : "outline"}
            size="sm"
            onClick={() => handleFilterChange(tab.value)}
          >
            {tab.label}
          </Button>
        ))}
        {total > 0 && (
          <span className="ml-auto text-sm text-muted-foreground">
            {total} contractor{total !== 1 ? "s" : ""} found
          </span>
        )}
      </div>

      {/* Type Filter Tabs */}
      <div className="flex items-center gap-2 mb-6 flex-wrap">
        {TYPE_TABS.map((tab) => (
          <Button
            key={tab.value}
            variant={typeFilter === tab.value ? "default" : "outline"}
            size="sm"
            onClick={() => { setTypeFilter(tab.value); setPage(1); }}
          >
            {tab.label}
          </Button>
        ))}
      </div>

      {/* Error State */}
      {error && (
        <Card className="mb-6">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="h-10 w-10 text-destructive mb-3" />
            <p className="text-sm text-muted-foreground mb-4">{error}</p>
            <Button variant="outline" onClick={fetchContractors}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Contractors Table */}
      {!error && (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Name
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Email
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Phone
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Truck Type
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Status
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Type
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Rating
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Total Jobs
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
                ) : contractors.length === 0 ? (
                  <tr>
                    <td colSpan={9} className="text-center py-12">
                      <div className="flex flex-col items-center gap-2">
                        <HardHat className="h-10 w-10 text-muted-foreground/50" />
                        <p className="text-muted-foreground text-sm">
                          {filter
                            ? `No ${filter} contractors found.`
                            : "No contractors registered yet. Contractors will appear here once they sign up."}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  contractors.map((c) => {
                    const isActioning = actionLoading === c.id;
                    const status = c.approval_status?.toLowerCase() || "";
                    return (
                      <tr
                        key={c.id}
                        className="border-b border-border hover:bg-muted/30 transition-colors"
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            <p className="text-sm font-medium">
                              {c.name || "--"}
                            </p>
                            {c.is_online && (
                              <span className="flex h-2 w-2 rounded-full bg-green-500" title="Online" />
                            )}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm text-muted-foreground">
                          {c.email || "--"}
                        </td>
                        <td className="px-4 py-3 text-sm text-muted-foreground">
                          {c.phone || "--"}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {c.truck_type || "--"}
                        </td>
                        <td className="px-4 py-3">
                          {getApprovalBadge(c.approval_status || "pending")}
                        </td>
                        <td className="px-4 py-3">
                          {getTypeBadge(c)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1">
                            <Star className="h-3.5 w-3.5 text-yellow-500 fill-yellow-500" />
                            <span className="text-sm">
                              {formatRating(c.rating)}
                            </span>
                          </div>
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {c.total_jobs ?? 0}
                        </td>
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-2">
                            {status === "pending" && (
                              <Button
                                size="sm"
                                variant="default"
                                disabled={isActioning}
                                onClick={() => handleApprove(c)}
                                className="h-8"
                              >
                                {isActioning ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <>
                                    <CheckCircle className="h-3.5 w-3.5 mr-1" />
                                    Approve
                                  </>
                                )}
                              </Button>
                            )}
                            {status === "approved" && (
                              <Button
                                size="sm"
                                variant="destructive"
                                disabled={isActioning}
                                onClick={() => handleSuspend(c)}
                                className="h-8"
                              >
                                {isActioning ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <>
                                    <XCircle className="h-3.5 w-3.5 mr-1" />
                                    Suspend
                                  </>
                                )}
                              </Button>
                            )}
                            {status === "approved" && !c.is_operator && (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={isActioning}
                                onClick={() => handlePromoteToOperator(c)}
                                className="h-8"
                              >
                                {isActioning ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <>
                                    <Shield className="h-3.5 w-3.5 mr-1" />
                                    Promote to Operator
                                  </>
                                )}
                              </Button>
                            )}
                            {status === "suspended" && (
                              <Button
                                size="sm"
                                variant="outline"
                                disabled={isActioning}
                                onClick={() => handleApprove(c)}
                                className="h-8"
                              >
                                {isActioning ? (
                                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                                ) : (
                                  <>
                                    <CheckCircle className="h-3.5 w-3.5 mr-1" />
                                    Re-approve
                                  </>
                                )}
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
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
