"use client";

import { useEffect, useState } from "react";
import {
  PhoneCall,
  AlertCircle,
  RefreshCw,
  Clock,
  CheckCircle2,
  XCircle,
  UserPlus,
  Loader2,
} from "lucide-react";
import { vapiApi, type VapiCallbackRecord, type Assignee } from "@/lib/api";

const STATUS_CONFIG: Record<string, { label: string; badge: string; icon: typeof Clock }> = {
  pending: { label: "Pending", badge: "bg-amber-100 text-amber-700", icon: Clock },
  completed: { label: "Completed", badge: "bg-green-100 text-green-700", icon: CheckCircle2 },
  failed: { label: "Failed", badge: "bg-red-100 text-red-700", icon: XCircle },
};

const STATUS_FILTER_TABS = [
  { key: "all", label: "All" },
  { key: "pending", label: "Pending" },
  { key: "completed", label: "Completed" },
  { key: "failed", label: "Failed" },
];

const ASSIGNMENT_FILTER_TABS = [
  { key: "all", label: "All" },
  { key: "unassigned", label: "Unassigned" },
  { key: "assigned_operator", label: "With Operator" },
  { key: "assigned_driver", label: "With Driver" },
];

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatRequestedTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

export default function AdminCallbacksPage() {
  const [callbacks, setCallbacks] = useState<VapiCallbackRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("pending");
  const [assignmentFilter, setAssignmentFilter] = useState("all");

  const [operators, setOperators] = useState<Assignee[]>([]);
  const [drivers, setDrivers] = useState<Assignee[]>([]);
  const [assigningId, setAssigningId] = useState<string | null>(null);
  const [assignDropdownId, setAssignDropdownId] = useState<string | null>(null);

  const loadCallbacks = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await vapiApi.callbacks({
        status: statusFilter !== "all" ? statusFilter : undefined,
        assignment_status: assignmentFilter !== "all" ? assignmentFilter : undefined,
      });
      setCallbacks(res.callbacks);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load callbacks");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadCallbacks();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [statusFilter, assignmentFilter]);

  useEffect(() => {
    vapiApi.assignees().then((res) => {
      setOperators(res.operators);
      setDrivers(res.drivers);
    }).catch(() => {});
  }, []);

  const handleAssign = async (callbackId: string, userId: string, type: "operator" | "driver") => {
    setAssigningId(callbackId);
    try {
      const body = type === "operator" ? { operator_id: userId } : { driver_id: userId };
      const updated = await vapiApi.assignCallback(callbackId, body);
      setCallbacks((prev) =>
        prev.map((cb) => (cb.id === callbackId ? { ...cb, ...updated } : cb))
      );
      setAssignDropdownId(null);
    } catch (err) {
      alert(err instanceof Error ? err.message : "Failed to assign");
    } finally {
      setAssigningId(null);
    }
  };

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-display font-bold">Callbacks &mdash; Lead Assignment</h1>
        <div className="rounded-xl border border-red-200 bg-red-50 p-8 flex flex-col items-center text-center">
          <AlertCircle className="h-10 w-10 text-red-400 mb-3" />
          <p className="text-red-700 font-medium mb-1">Something went wrong</p>
          <p className="text-sm text-red-600 mb-4">{error}</p>
          <button
            onClick={() => loadCallbacks()}
            className="inline-flex items-center gap-2 text-sm bg-red-100 text-red-700 px-4 py-2 rounded-lg hover:bg-red-200 transition-colors font-medium"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-display font-bold">Callbacks &mdash; Lead Assignment</h1>
        <button
          onClick={() => loadCallbacks()}
          className="inline-flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg border border-border hover:bg-muted transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div>
          <p className="text-xs text-muted-foreground mb-1.5 font-medium">Status</p>
          <div className="flex gap-2 flex-wrap">
            {STATUS_FILTER_TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setStatusFilter(tab.key)}
                className={`px-3 sm:px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  statusFilter === tab.key
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
        <div>
          <p className="text-xs text-muted-foreground mb-1.5 font-medium">Assignment</p>
          <div className="flex gap-2 flex-wrap">
            {ASSIGNMENT_FILTER_TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => setAssignmentFilter(tab.key)}
                className={`px-3 sm:px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                  assignmentFilter === tab.key
                    ? "bg-primary text-primary-foreground"
                    : "bg-muted text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        </div>
      </div>

      {/* Desktop Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden hidden md:block">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Customer</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Phone</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Requested Time</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Created</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Assign Operator</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Assign Driver</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                [...Array(4)].map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-28" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-28" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-36" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-32" /></td>
                    <td className="px-4 py-3"><div className="h-6 bg-muted rounded-full w-20" /></td>
                    <td className="px-4 py-3"><div className="h-6 bg-muted rounded w-24" /></td>
                    <td className="px-4 py-3"><div className="h-6 bg-muted rounded w-24" /></td>
                  </tr>
                ))
              ) : callbacks.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-1">
                        <PhoneCall className="w-6 h-6 text-muted-foreground/60" />
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {statusFilter === "pending"
                          ? "No pending callbacks."
                          : "No callbacks match the current filters."}
                      </p>
                    </div>
                  </td>
                </tr>
              ) : (
                callbacks.map((cb) => {
                  const config = STATUS_CONFIG[cb.status] || STATUS_CONFIG.pending;
                  return (
                    <tr key={cb.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3 font-medium">{cb.customer_name || "Unknown"}</td>
                      <td className="px-4 py-3">
                        <a href={`tel:${cb.phone}`} className="text-primary hover:underline font-mono">
                          {cb.phone}
                        </a>
                      </td>
                      <td className="px-4 py-3">{formatRequestedTime(cb.requested_time)}</td>
                      <td className="px-4 py-3 text-muted-foreground">{formatDate(cb.created_at)}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${config.badge}`}>
                          <config.icon className="w-3 h-3" />
                          {config.label}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="relative">
                          <button
                            onClick={() => setAssignDropdownId(
                              assignDropdownId === `${cb.id}-op` ? null : `${cb.id}-op`
                            )}
                            disabled={assigningId === cb.id}
                            className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg border border-border hover:bg-muted transition-colors font-medium disabled:opacity-50"
                          >
                            {assigningId === cb.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <UserPlus className="w-3 h-3" />}
                            {cb.assigned_operator_name || "Assign"}
                          </button>
                          {assignDropdownId === `${cb.id}-op` && (
                            <div className="absolute left-0 top-full mt-1 w-56 bg-card border border-border rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
                              {operators.length === 0 ? (
                                <p className="px-3 py-2 text-sm text-muted-foreground">No operators</p>
                              ) : (
                                operators.map((op) => (
                                  <button
                                    key={op.id}
                                    onClick={() => handleAssign(cb.id, op.id, "operator")}
                                    className="w-full text-left px-3 py-2 text-sm hover:bg-muted transition-colors"
                                  >
                                    {op.name || op.email || op.id}
                                  </button>
                                ))
                              )}
                            </div>
                          )}
                        </div>
                      </td>
                      <td className="px-4 py-3">
                        <div className="relative">
                          <button
                            onClick={() => setAssignDropdownId(
                              assignDropdownId === `${cb.id}-drv` ? null : `${cb.id}-drv`
                            )}
                            disabled={assigningId === cb.id}
                            className="inline-flex items-center gap-1.5 text-xs px-2 py-1 rounded-lg border border-border hover:bg-muted transition-colors font-medium disabled:opacity-50"
                          >
                            {assigningId === cb.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <UserPlus className="w-3 h-3" />}
                            {cb.assigned_driver_name || "Assign"}
                          </button>
                          {assignDropdownId === `${cb.id}-drv` && (
                            <div className="absolute left-0 top-full mt-1 w-56 bg-card border border-border rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
                              {drivers.length === 0 ? (
                                <p className="px-3 py-2 text-sm text-muted-foreground">No drivers</p>
                              ) : (
                                drivers.map((d) => (
                                  <button
                                    key={d.id}
                                    onClick={() => handleAssign(cb.id, d.id, "driver")}
                                    className="w-full text-left px-3 py-2 text-sm hover:bg-muted transition-colors"
                                  >
                                    {d.name || d.email || d.id}
                                  </button>
                                ))
                              )}
                            </div>
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
      </div>

      {/* Mobile Cards */}
      <div className="md:hidden space-y-3">
        {loading ? (
          [...Array(4)].map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse space-y-3">
              <div className="flex items-center justify-between">
                <div className="h-6 bg-muted rounded-full w-20" />
                <div className="h-4 bg-muted rounded w-24" />
              </div>
              <div className="space-y-2">
                <div className="h-4 bg-muted rounded w-3/4" />
                <div className="h-3 bg-muted rounded w-1/2" />
              </div>
            </div>
          ))
        ) : callbacks.length === 0 ? (
          <div className="rounded-xl border border-border bg-card px-4 py-12 flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
              <PhoneCall className="w-6 h-6 text-muted-foreground/60" />
            </div>
            <p className="text-sm text-muted-foreground">
              {statusFilter === "pending"
                ? "No pending callbacks."
                : "No callbacks match the current filters."}
            </p>
          </div>
        ) : (
          callbacks.map((cb) => {
            const config = STATUS_CONFIG[cb.status] || STATUS_CONFIG.pending;
            return (
              <div key={cb.id} className="rounded-xl border border-border bg-card p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <span className={`inline-flex items-center gap-1.5 px-2 py-1 rounded-full text-xs font-medium ${config.badge}`}>
                    <config.icon className="w-3 h-3" />
                    {config.label}
                  </span>
                  <span className="text-xs text-muted-foreground">{formatDate(cb.created_at)}</span>
                </div>
                <div>
                  <p className="text-sm font-medium">{cb.customer_name || "Unknown"}</p>
                  <a href={`tel:${cb.phone}`} className="text-sm text-primary hover:underline font-mono">
                    {cb.phone}
                  </a>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Requested: {formatRequestedTime(cb.requested_time)}</span>
                </div>
                <div className="flex flex-wrap gap-2">
                  <div className="relative">
                    <button
                      onClick={() => setAssignDropdownId(
                        assignDropdownId === `${cb.id}-op` ? null : `${cb.id}-op`
                      )}
                      disabled={assigningId === cb.id}
                      className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg border border-border hover:bg-muted transition-colors font-medium disabled:opacity-50"
                    >
                      {assigningId === cb.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <UserPlus className="w-3 h-3" />}
                      {cb.assigned_operator_name || "Operator"}
                    </button>
                    {assignDropdownId === `${cb.id}-op` && (
                      <div className="absolute left-0 bottom-full mb-1 w-56 bg-card border border-border rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
                        {operators.map((op) => (
                          <button
                            key={op.id}
                            onClick={() => handleAssign(cb.id, op.id, "operator")}
                            className="w-full text-left px-3 py-2 text-sm hover:bg-muted transition-colors"
                          >
                            {op.name || op.email || op.id}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                  <div className="relative">
                    <button
                      onClick={() => setAssignDropdownId(
                        assignDropdownId === `${cb.id}-drv` ? null : `${cb.id}-drv`
                      )}
                      disabled={assigningId === cb.id}
                      className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg border border-border hover:bg-muted transition-colors font-medium disabled:opacity-50"
                    >
                      {assigningId === cb.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <UserPlus className="w-3 h-3" />}
                      {cb.assigned_driver_name || "Driver"}
                    </button>
                    {assignDropdownId === `${cb.id}-drv` && (
                      <div className="absolute left-0 bottom-full mb-1 w-56 bg-card border border-border rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
                        {drivers.map((d) => (
                          <button
                            key={d.id}
                            onClick={() => handleAssign(cb.id, d.id, "driver")}
                            className="w-full text-left px-3 py-2 text-sm hover:bg-muted transition-colors"
                          >
                            {d.name || d.email || d.id}
                          </button>
                        ))}
                      </div>
                    )}
                  </div>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
