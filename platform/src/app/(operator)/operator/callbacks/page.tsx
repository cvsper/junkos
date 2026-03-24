"use client";

import { useEffect, useState } from "react";
import {
  PhoneCall,
  AlertCircle,
  RefreshCw,
  Clock,
  CheckCircle2,
  XCircle,
} from "lucide-react";
import { vapiApi, type VapiCallbackRecord } from "@/lib/api";

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

export default function OperatorCallbacksPage() {
  const [callbacks, setCallbacks] = useState<VapiCallbackRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [statusFilter, setStatusFilter] = useState("pending");

  const loadCallbacks = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await vapiApi.callbacks(
        statusFilter !== "all" ? statusFilter : undefined
      );
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
  }, [statusFilter]);

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-display font-bold">Callbacks</h1>
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
      <h1 className="text-2xl font-display font-bold">Callbacks</h1>

      {/* Status Filter */}
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
                  </tr>
                ))
              ) : callbacks.length === 0 ? (
                <tr>
                  <td colSpan={5} className="px-4 py-12 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-1">
                        <PhoneCall className="w-6 h-6 text-muted-foreground/60" />
                      </div>
                      <p className="text-sm text-muted-foreground">
                        {statusFilter === "pending"
                          ? "No pending callbacks. You're all caught up!"
                          : "No callbacks match the current filter."}
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
                        <a
                          href={`tel:${cb.phone}`}
                          className="text-primary hover:underline font-mono"
                        >
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
                ? "No pending callbacks. You're all caught up!"
                : "No callbacks match the current filter."}
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
                  <a
                    href={`tel:${cb.phone}`}
                    className="text-sm text-primary hover:underline font-mono"
                  >
                    {cb.phone}
                  </a>
                </div>
                <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Clock className="w-3.5 h-3.5" />
                  <span>Requested: {formatRequestedTime(cb.requested_time)}</span>
                </div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
}
