"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Loader2,
  RefreshCw,
  CheckCircle,
  XCircle,
  Clock,
  Truck,
  MapPin,
  Phone,
  Mail,
  X,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { adminApi, type OperatorApplicationRecord } from "@/lib/api";

const FILTER_TABS = [
  { label: "All", value: "" },
  { label: "Pending", value: "pending" },
  { label: "Approved", value: "approved" },
  { label: "Rejected", value: "rejected" },
] as const;

function getStatusBadge(status: string) {
  switch (status) {
    case "approved":
      return (
        <Badge className="bg-green-500/15 text-green-700 border-green-300 hover:bg-green-500/25">
          Approved
        </Badge>
      );
    case "rejected":
      return (
        <Badge className="bg-red-500/15 text-red-700 border-red-300 hover:bg-red-500/25">
          Rejected
        </Badge>
      );
    default:
      return (
        <Badge className="bg-amber-500/15 text-amber-700 border-amber-300 hover:bg-amber-500/25">
          Pending
        </Badge>
      );
  }
}

export default function OperatorApplicationsPage() {
  const [applications, setApplications] = useState<OperatorApplicationRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("");
  const [total, setTotal] = useState(0);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  // Reject modal state
  const [rejectTarget, setRejectTarget] = useState<OperatorApplicationRecord | null>(null);
  const [rejectReason, setRejectReason] = useState("");
  const [rejectLoading, setRejectLoading] = useState(false);

  const fetchApplications = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const filters: Record<string, string> = {};
      if (statusFilter) filters.status = statusFilter;
      const res = await adminApi.operatorApplications(filters);
      setApplications(res.applications || []);
      setTotal(res.total || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load applications");
    } finally {
      setLoading(false);
    }
  }, [statusFilter]);

  useEffect(() => {
    fetchApplications();
  }, [fetchApplications]);

  const handleApprove = async (app: OperatorApplicationRecord) => {
    setActionLoading(app.id);
    try {
      await adminApi.reviewOperatorApplication(app.id, "approve");
      await fetchApplications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to approve");
    } finally {
      setActionLoading(null);
    }
  };

  const handleRejectSubmit = async () => {
    if (!rejectTarget || !rejectReason.trim()) return;
    setRejectLoading(true);
    try {
      await adminApi.reviewOperatorApplication(rejectTarget.id, "reject", rejectReason.trim());
      setRejectTarget(null);
      setRejectReason("");
      await fetchApplications();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to reject");
    } finally {
      setRejectLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold tracking-tight">Operator Applications</h1>
          <p className="text-sm text-muted-foreground mt-1">
            Review and manage operator applications.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchApplications} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      {/* Filter Tabs */}
      <div className="flex gap-2">
        {FILTER_TABS.map((tab) => (
          <button
            key={tab.value}
            onClick={() => setStatusFilter(tab.value)}
            className={`px-3 py-1.5 text-sm rounded-lg transition-colors ${
              statusFilter === tab.value
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
        <span className="ml-auto text-sm text-muted-foreground self-center">
          {total} application{total !== 1 ? "s" : ""} found
        </span>
      </div>

      {/* Error */}
      {error && (
        <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 dark:bg-red-950/20 dark:border-red-800">
          <p className="text-sm text-red-700 dark:text-red-400">{error}</p>
        </div>
      )}

      {/* Loading */}
      {loading ? (
        <div className="flex items-center justify-center py-16">
          <Loader2 className="h-6 w-6 animate-spin text-primary" />
        </div>
      ) : applications.length === 0 ? (
        <Card>
          <CardContent className="py-16 text-center">
            <p className="text-muted-foreground">No applications found.</p>
          </CardContent>
        </Card>
      ) : (
        <div className="space-y-3">
          {applications.map((app) => (
            <Card key={app.id}>
              <CardContent className="p-5">
                <div className="flex items-start justify-between gap-4">
                  {/* Info */}
                  <div className="space-y-2 min-w-0 flex-1">
                    <div className="flex items-center gap-3">
                      <h3 className="font-semibold text-base">
                        {app.first_name} {app.last_name}
                      </h3>
                      {getStatusBadge(app.status)}
                    </div>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-x-6 gap-y-1 text-sm text-muted-foreground">
                      <span className="flex items-center gap-1.5">
                        <Mail className="h-3.5 w-3.5" /> {app.email}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <Phone className="h-3.5 w-3.5" /> {app.phone}
                      </span>
                      <span className="flex items-center gap-1.5">
                        <MapPin className="h-3.5 w-3.5" /> {app.city}
                      </span>
                      {app.trucks && (
                        <span className="flex items-center gap-1.5">
                          <Truck className="h-3.5 w-3.5" /> {app.trucks} truck{app.trucks !== "1" ? "s" : ""}
                        </span>
                      )}
                    </div>
                    {app.experience && (
                      <p className="text-sm text-muted-foreground">
                        Experience: {app.experience}
                      </p>
                    )}
                    {app.rejection_reason && (
                      <p className="text-sm text-red-600 dark:text-red-400">
                        Rejection reason: {app.rejection_reason}
                      </p>
                    )}
                    <p className="text-xs text-muted-foreground">
                      <Clock className="h-3 w-3 inline mr-1" />
                      Applied {app.created_at ? new Date(app.created_at).toLocaleDateString("en-US", {
                        month: "short", day: "numeric", year: "numeric", hour: "numeric", minute: "2-digit",
                      }) : "N/A"}
                    </p>
                  </div>

                  {/* Actions */}
                  {app.status === "pending" && (
                    <div className="flex gap-2 shrink-0">
                      <Button
                        size="sm"
                        onClick={() => handleApprove(app)}
                        disabled={actionLoading === app.id}
                        className="bg-green-600 hover:bg-green-700 text-white"
                      >
                        {actionLoading === app.id ? (
                          <Loader2 className="h-4 w-4 animate-spin" />
                        ) : (
                          <CheckCircle className="h-4 w-4 mr-1" />
                        )}
                        Approve
                      </Button>
                      <Button
                        size="sm"
                        variant="outline"
                        onClick={() => setRejectTarget(app)}
                        className="text-red-600 border-red-200 hover:bg-red-50"
                      >
                        <XCircle className="h-4 w-4 mr-1" />
                        Reject
                      </Button>
                    </div>
                  )}
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      {/* Reject Modal */}
      {rejectTarget && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-card rounded-lg border border-border shadow-lg max-w-md w-full p-6 space-y-4">
            <div className="flex items-center justify-between">
              <h3 className="font-semibold text-lg">Reject Application</h3>
              <button onClick={() => setRejectTarget(null)} className="text-muted-foreground hover:text-foreground">
                <X className="h-5 w-5" />
              </button>
            </div>
            <p className="text-sm text-muted-foreground">
              Rejecting application from <strong>{rejectTarget.first_name} {rejectTarget.last_name}</strong>.
            </p>
            <div>
              <label className="block text-sm font-medium mb-1.5">Reason</label>
              <textarea
                value={rejectReason}
                onChange={(e) => setRejectReason(e.target.value)}
                placeholder="Provide a reason for rejection..."
                rows={3}
                className="w-full rounded-lg border border-border bg-card px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring resize-none"
              />
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" size="sm" onClick={() => setRejectTarget(null)}>
                Cancel
              </Button>
              <Button
                size="sm"
                onClick={handleRejectSubmit}
                disabled={!rejectReason.trim() || rejectLoading}
                className="bg-red-600 hover:bg-red-700 text-white"
              >
                {rejectLoading ? <Loader2 className="h-4 w-4 animate-spin mr-1" /> : null}
                Reject
              </Button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
