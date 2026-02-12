"use client";

import { useEffect, useState, useCallback, Fragment } from "react";
import {
  Loader2,
  AlertCircle,
  RefreshCw,
  ChevronLeft,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  CheckCircle,
  XCircle,
  FileText,
  Shield,
  Clock,
  ExternalLink,
  X,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { adminApi, type OnboardingApplicationRecord } from "@/lib/api";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const FILTER_TABS = [
  { label: "All", value: "" },
  { label: "Pending Review", value: "documents_submitted" },
  { label: "Approved", value: "approved" },
  { label: "Rejected", value: "rejected" },
  { label: "Not Started", value: "pending" },
] as const;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function getStatusBadge(status: string) {
  switch (status) {
    case "approved":
      return (
        <Badge className="bg-green-500/15 text-green-700 border-green-300 hover:bg-green-500/25">
          Approved
        </Badge>
      );
    case "documents_submitted":
      return (
        <Badge className="bg-blue-500/15 text-blue-700 border-blue-300 hover:bg-blue-500/25">
          Pending Review
        </Badge>
      );
    case "under_review":
      return (
        <Badge className="bg-purple-500/15 text-purple-700 border-purple-300 hover:bg-purple-500/25">
          Under Review
        </Badge>
      );
    case "rejected":
      return <Badge variant="destructive">Rejected</Badge>;
    case "pending":
      return (
        <Badge className="bg-yellow-500/15 text-yellow-700 border-yellow-300 hover:bg-yellow-500/25">
          Not Started
        </Badge>
      );
    default:
      return <Badge variant="secondary">{status}</Badge>;
  }
}

function formatDate(dateStr: string | null | undefined): string {
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

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || "http://localhost:5001";

function getDocUrl(url: string | null | undefined): string | null {
  if (!url) return null;
  if (url.startsWith("http")) return url;
  return `${API_BASE_URL}${url}`;
}

// ---------------------------------------------------------------------------
// Main component
// ---------------------------------------------------------------------------

export default function AdminOnboardingPage() {
  const [applications, setApplications] = useState<
    OnboardingApplicationRecord[]
  >([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filter, setFilter] = useState("documents_submitted");
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [total, setTotal] = useState(0);
  const [expandedId, setExpandedId] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Reject modal state
  const [rejectModalOpen, setRejectModalOpen] = useState(false);
  const [rejectTarget, setRejectTarget] =
    useState<OnboardingApplicationRecord | null>(null);
  const [rejectionReason, setRejectionReason] = useState("");

  const fetchApplications = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: Record<string, string | number> = { page, per_page: 20 };
      if (filter) filters.status = filter;
      const res = await adminApi.onboardingApplications(filters);
      setApplications(res.applications || []);
      setTotalPages(res.pages || 1);
      setTotal(res.total || 0);
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to load applications"
      );
    } finally {
      setLoading(false);
    }
  }, [filter, page]);

  useEffect(() => {
    fetchApplications();
  }, [fetchApplications]);

  const handleFilterChange = (value: string) => {
    setFilter(value);
    setPage(1);
    setExpandedId(null);
  };

  const handleApprove = async (app: OnboardingApplicationRecord) => {
    const confirmed = window.confirm(
      `Approve ${app.name || "this driver"}? They will be able to go online and accept jobs.`
    );
    if (!confirmed) return;

    setActionLoading(app.id);
    try {
      await adminApi.reviewOnboarding(app.id, "approve");
      await fetchApplications();
    } catch (err) {
      alert(
        err instanceof Error
          ? err.message
          : "Failed to approve. Please try again."
      );
    } finally {
      setActionLoading(null);
    }
  };

  const openRejectModal = (app: OnboardingApplicationRecord) => {
    setRejectTarget(app);
    setRejectionReason("");
    setRejectModalOpen(true);
  };

  const handleRejectSubmit = async () => {
    if (!rejectTarget) return;
    if (!rejectionReason.trim()) {
      alert("Please provide a rejection reason.");
      return;
    }

    setActionLoading(rejectTarget.id);
    try {
      await adminApi.reviewOnboarding(
        rejectTarget.id,
        "reject",
        rejectionReason.trim()
      );
      setRejectModalOpen(false);
      setRejectTarget(null);
      setRejectionReason("");
      await fetchApplications();
    } catch (err) {
      alert(
        err instanceof Error
          ? err.message
          : "Failed to reject. Please try again."
      );
    } finally {
      setActionLoading(null);
    }
  };

  const toggleExpand = (id: string) => {
    setExpandedId((prev) => (prev === id ? null : id));
  };

  // Skeleton row
  const SkeletonRow = () => (
    <tr className="border-b border-border">
      {Array.from({ length: 7 }).map((_, i) => (
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
            Driver Onboarding
          </h1>
          <p className="text-muted-foreground mt-1">
            Review and manage driver onboarding applications.
          </p>
        </div>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchApplications}
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
            {total} application{total !== 1 ? "s" : ""} found
          </span>
        )}
      </div>

      {/* Error State */}
      {error && (
        <Card className="mb-6">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="h-10 w-10 text-destructive mb-3" />
            <p className="text-sm text-muted-foreground mb-4">{error}</p>
            <Button variant="outline" onClick={fetchApplications}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Applications Table */}
      {!error && (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3 w-8" />
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Name
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Email
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Status
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Truck Type
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Submitted
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
                ) : applications.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center py-12">
                      <div className="flex flex-col items-center gap-2">
                        <Shield className="h-10 w-10 text-muted-foreground/50" />
                        <p className="text-muted-foreground text-sm">
                          {filter
                            ? `No ${FILTER_TABS.find((t) => t.value === filter)?.label?.toLowerCase() || filter} applications found.`
                            : "No onboarding applications yet."}
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  applications.map((app) => {
                    const isExpanded = expandedId === app.id;
                    const isActioning = actionLoading === app.id;
                    const status = app.onboarding_status || "pending";

                    return (
                      <Fragment key={app.id}>
                        {/* Main row */}
                        <tr
                          className={`border-b border-border hover:bg-muted/30 transition-colors cursor-pointer ${
                            isExpanded ? "bg-muted/20" : ""
                          }`}
                          onClick={() => toggleExpand(app.id)}
                        >
                          <td className="px-4 py-3">
                            {isExpanded ? (
                              <ChevronUp className="h-4 w-4 text-muted-foreground" />
                            ) : (
                              <ChevronDown className="h-4 w-4 text-muted-foreground" />
                            )}
                          </td>
                          <td className="px-4 py-3">
                            <p className="text-sm font-medium">
                              {app.name || "--"}
                            </p>
                          </td>
                          <td className="px-4 py-3 text-sm text-muted-foreground">
                            {app.email || "--"}
                          </td>
                          <td className="px-4 py-3">
                            {getStatusBadge(status)}
                          </td>
                          <td className="px-4 py-3 text-sm">
                            {app.truck_type || "--"}
                          </td>
                          <td className="px-4 py-3 text-sm text-muted-foreground">
                            {formatDate(app.updated_at)}
                          </td>
                          <td className="px-4 py-3">
                            <div
                              className="flex items-center gap-2"
                              onClick={(e) => e.stopPropagation()}
                            >
                              {status === "documents_submitted" && (
                                <>
                                  <Button
                                    size="sm"
                                    variant="default"
                                    disabled={isActioning}
                                    onClick={() => handleApprove(app)}
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
                                  <Button
                                    size="sm"
                                    variant="destructive"
                                    disabled={isActioning}
                                    onClick={() => openRejectModal(app)}
                                    className="h-8"
                                  >
                                    <XCircle className="h-3.5 w-3.5 mr-1" />
                                    Reject
                                  </Button>
                                </>
                              )}
                              {status === "approved" && (
                                <span className="flex items-center gap-1 text-sm text-green-600">
                                  <CheckCircle className="h-3.5 w-3.5" />
                                  Approved
                                </span>
                              )}
                              {status === "rejected" && (
                                <span className="flex items-center gap-1 text-sm text-red-600">
                                  <XCircle className="h-3.5 w-3.5" />
                                  Rejected
                                </span>
                              )}
                              {status === "pending" && (
                                <span className="flex items-center gap-1 text-sm text-muted-foreground">
                                  <Clock className="h-3.5 w-3.5" />
                                  Awaiting docs
                                </span>
                              )}
                            </div>
                          </td>
                        </tr>

                        {/* Expanded details row */}
                        {isExpanded && (
                          <tr className="border-b border-border bg-muted/10">
                            <td colSpan={7} className="px-8 py-6">
                              <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
                                {/* Documents */}
                                <div>
                                  <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                                    <FileText className="h-4 w-4" />
                                    Uploaded Documents
                                  </h4>
                                  <div className="space-y-2">
                                    <DocumentLink
                                      label="Insurance"
                                      url={app.insurance_document_url}
                                      expiry={app.insurance_expiry}
                                    />
                                    <DocumentLink
                                      label="Driver's License"
                                      url={app.drivers_license_url}
                                      expiry={app.license_expiry}
                                    />
                                    <DocumentLink
                                      label="Vehicle Registration"
                                      url={app.vehicle_registration_url}
                                    />
                                  </div>
                                </div>

                                {/* Details */}
                                <div>
                                  <h4 className="text-sm font-semibold mb-3 flex items-center gap-2">
                                    <Shield className="h-4 w-4" />
                                    Details
                                  </h4>
                                  <div className="space-y-2 text-sm">
                                    <div className="flex justify-between">
                                      <span className="text-muted-foreground">
                                        Background Check:
                                      </span>
                                      <span className="font-medium">
                                        {app.background_check_status === "passed"
                                          ? "Passed"
                                          : app.background_check_status === "failed"
                                            ? "Failed"
                                            : app.background_check_status === "pending"
                                              ? "Pending"
                                              : "Not Started"}
                                      </span>
                                    </div>
                                    <div className="flex justify-between">
                                      <span className="text-muted-foreground">
                                        Phone:
                                      </span>
                                      <span>{app.phone || "--"}</span>
                                    </div>
                                    <div className="flex justify-between">
                                      <span className="text-muted-foreground">
                                        Registered:
                                      </span>
                                      <span>{formatDate(app.created_at)}</span>
                                    </div>
                                    {app.onboarding_completed_at && (
                                      <div className="flex justify-between">
                                        <span className="text-muted-foreground">
                                          Approved On:
                                        </span>
                                        <span>
                                          {formatDate(app.onboarding_completed_at)}
                                        </span>
                                      </div>
                                    )}
                                    {app.rejection_reason && (
                                      <div className="mt-3 p-3 rounded-md bg-red-50 border border-red-200">
                                        <p className="text-xs font-semibold text-red-700 mb-1">
                                          Rejection Reason:
                                        </p>
                                        <p className="text-sm text-red-600">
                                          {app.rejection_reason}
                                        </p>
                                      </div>
                                    )}
                                  </div>

                                  {/* Action buttons in expanded view */}
                                  {status === "documents_submitted" && (
                                    <div
                                      className="flex items-center gap-2 mt-4 pt-4 border-t border-border"
                                      onClick={(e) => e.stopPropagation()}
                                    >
                                      <Button
                                        size="sm"
                                        variant="default"
                                        disabled={isActioning}
                                        onClick={() => handleApprove(app)}
                                      >
                                        {isActioning ? (
                                          <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                                        ) : (
                                          <CheckCircle className="h-3.5 w-3.5 mr-1" />
                                        )}
                                        Approve
                                      </Button>
                                      <Button
                                        size="sm"
                                        variant="destructive"
                                        disabled={isActioning}
                                        onClick={() => openRejectModal(app)}
                                      >
                                        <XCircle className="h-3.5 w-3.5 mr-1" />
                                        Reject
                                      </Button>
                                    </div>
                                  )}
                                </div>
                              </div>
                            </td>
                          </tr>
                        )}
                      </Fragment>
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

      {/* Reject Modal */}
      {rejectModalOpen && rejectTarget && (
        <div className="fixed inset-0 z-50 flex items-center justify-center">
          {/* Backdrop */}
          <div
            className="absolute inset-0 bg-black/50"
            onClick={() => setRejectModalOpen(false)}
          />
          {/* Modal */}
          <div className="relative bg-card border border-border rounded-lg shadow-lg p-6 w-full max-w-md mx-4 z-10">
            <div className="flex items-center justify-between mb-4">
              <h3 className="text-lg font-semibold">Reject Application</h3>
              <button
                onClick={() => setRejectModalOpen(false)}
                className="text-muted-foreground hover:text-foreground transition-colors"
              >
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="text-sm text-muted-foreground mb-4">
              Rejecting application for{" "}
              <span className="font-medium text-foreground">
                {rejectTarget.name || rejectTarget.email || "this driver"}
              </span>
              . Please provide a reason.
            </p>
            <textarea
              className="w-full border border-border rounded-md px-3 py-2 text-sm bg-background text-foreground placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
              rows={4}
              placeholder="Reason for rejection (e.g., expired insurance document, blurry license photo)..."
              value={rejectionReason}
              onChange={(e) => setRejectionReason(e.target.value)}
              autoFocus
            />
            <div className="flex justify-end gap-2 mt-4">
              <Button
                variant="outline"
                size="sm"
                onClick={() => setRejectModalOpen(false)}
              >
                Cancel
              </Button>
              <Button
                variant="destructive"
                size="sm"
                disabled={
                  !rejectionReason.trim() || actionLoading === rejectTarget.id
                }
                onClick={handleRejectSubmit}
              >
                {actionLoading === rejectTarget.id ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin mr-1" />
                ) : (
                  <XCircle className="h-3.5 w-3.5 mr-1" />
                )}
                Reject
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function DocumentLink({
  label,
  url,
  expiry,
}: {
  label: string;
  url: string | null | undefined;
  expiry?: string | null;
}) {
  const docUrl = getDocUrl(url);

  return (
    <div className="flex items-center justify-between py-1.5 px-3 rounded-md bg-background border border-border">
      <div className="flex items-center gap-2 min-w-0">
        <FileText className="h-4 w-4 text-muted-foreground shrink-0" />
        <span className="text-sm truncate">{label}</span>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        {expiry && (
          <span className="text-xs text-muted-foreground">
            Exp: {formatDate(expiry)}
          </span>
        )}
        {docUrl ? (
          <a
            href={docUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="text-blue-600 hover:text-blue-800 flex items-center gap-1 text-xs font-medium"
            onClick={(e) => e.stopPropagation()}
          >
            View
            <ExternalLink className="h-3 w-3" />
          </a>
        ) : (
          <span className="text-xs text-muted-foreground italic">
            Not uploaded
          </span>
        )}
      </div>
    </div>
  );
}
