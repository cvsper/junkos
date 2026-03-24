"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Phone,
  ChevronDown,
  ChevronUp,
  Loader2,
  AlertCircle,
  RefreshCw,
  UserPlus,
} from "lucide-react";
import { vapiApi, type VapiCallRecord, type Assignee } from "@/lib/api";

const LEAD_BADGES: Record<string, string> = {
  hot: "bg-red-100 text-red-700",
  warm: "bg-amber-100 text-amber-700",
  cold: "bg-blue-100 text-blue-700",
};

const ASSIGNMENT_BADGES: Record<string, { label: string; badge: string }> = {
  unassigned: { label: "Unassigned", badge: "bg-gray-100 text-gray-600" },
  assigned_operator: { label: "Operator Assigned", badge: "bg-blue-100 text-blue-700" },
  assigned_driver: { label: "Driver Assigned", badge: "bg-green-100 text-green-700" },
  completed: { label: "Completed", badge: "bg-emerald-100 text-emerald-700" },
};

const LEAD_FILTER_TABS = [
  { key: "all", label: "All" },
  { key: "hot", label: "Hot" },
  { key: "warm", label: "Warm" },
  { key: "cold", label: "Cold" },
];

const ASSIGNMENT_FILTER_TABS = [
  { key: "all", label: "All" },
  { key: "unassigned", label: "Unassigned" },
  { key: "assigned_operator", label: "With Operator" },
  { key: "assigned_driver", label: "With Driver" },
];

function formatDuration(seconds: number): string {
  const m = Math.floor(seconds / 60);
  const s = seconds % 60;
  return m > 0 ? `${m}m ${s}s` : `${s}s`;
}

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

export default function AdminCallsPage() {
  const [calls, setCalls] = useState<VapiCallRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const [totalPages, setTotalPages] = useState(1);
  const [leadFilter, setLeadFilter] = useState("all");
  const [assignmentFilter, setAssignmentFilter] = useState("all");
  const [expandedId, setExpandedId] = useState<string | null>(null);

  const [operators, setOperators] = useState<Assignee[]>([]);
  const [drivers, setDrivers] = useState<Assignee[]>([]);
  const [assigningId, setAssigningId] = useState<string | null>(null);
  const [assignDropdownId, setAssignDropdownId] = useState<string | null>(null);

  const loadCalls = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await vapiApi.calls({
        page,
        per_page: 25,
        lead_score: leadFilter !== "all" ? leadFilter : undefined,
        assignment_status: assignmentFilter !== "all" ? assignmentFilter : undefined,
      });
      setCalls(res.calls);
      setTotalPages(res.pages);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load calls");
    } finally {
      setLoading(false);
    }
  }, [page, leadFilter, assignmentFilter]);

  useEffect(() => {
    loadCalls();
  }, [loadCalls]);

  // Load assignees
  useEffect(() => {
    vapiApi.assignees().then((res) => {
      setOperators(res.operators);
      setDrivers(res.drivers);
    }).catch(() => {});
  }, []);

  const handleAssign = async (callId: string, userId: string, type: "operator" | "driver") => {
    setAssigningId(callId);
    try {
      const body = type === "operator" ? { operator_id: userId } : { driver_id: userId };
      const updated = await vapiApi.assignCall(callId, body);
      setCalls((prev) =>
        prev.map((c) => (c.id === callId ? { ...c, ...updated } : c))
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
        <h1 className="text-2xl font-display font-bold">Call Log &mdash; Lead Assignment</h1>
        <div className="rounded-xl border border-red-200 bg-red-50 p-8 flex flex-col items-center text-center">
          <AlertCircle className="h-10 w-10 text-red-400 mb-3" />
          <p className="text-red-700 font-medium mb-1">Something went wrong</p>
          <p className="text-sm text-red-600 mb-4">{error}</p>
          <button
            onClick={() => loadCalls()}
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
        <h1 className="text-2xl font-display font-bold">Call Log &mdash; Lead Assignment</h1>
        <button
          onClick={() => loadCalls()}
          className="inline-flex items-center gap-2 text-sm px-3 py-1.5 rounded-lg border border-border hover:bg-muted transition-colors"
        >
          <RefreshCw className="w-3.5 h-3.5" />
          Refresh
        </button>
      </div>

      {/* Filters */}
      <div className="flex flex-col sm:flex-row gap-3">
        <div>
          <p className="text-xs text-muted-foreground mb-1.5 font-medium">Lead Score</p>
          <div className="flex gap-2">
            {LEAD_FILTER_TABS.map((tab) => (
              <button
                key={tab.key}
                onClick={() => { setLeadFilter(tab.key); setPage(1); }}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
                  leadFilter === tab.key
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
                onClick={() => { setAssignmentFilter(tab.key); setPage(1); }}
                className={`px-3 py-1.5 rounded-lg text-sm font-medium transition-colors ${
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
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Date / Time</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Phone</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Duration</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Lead</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Assignment</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Operator</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Driver</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Summary</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                [...Array(5)].map((_, i) => (
                  <tr key={i} className="animate-pulse">
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-32" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-28" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-14" /></td>
                    <td className="px-4 py-3"><div className="h-6 bg-muted rounded-full w-14" /></td>
                    <td className="px-4 py-3"><div className="h-6 bg-muted rounded-full w-24" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-20" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-20" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-40" /></td>
                    <td className="px-4 py-3"><div className="h-4 bg-muted rounded w-4" /></td>
                  </tr>
                ))
              ) : calls.length === 0 ? (
                <tr>
                  <td colSpan={9} className="px-4 py-12 text-center">
                    <div className="flex flex-col items-center gap-2">
                      <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-1">
                        <Phone className="w-6 h-6 text-muted-foreground/60" />
                      </div>
                      <p className="text-sm text-muted-foreground">No calls match the current filters.</p>
                    </div>
                  </td>
                </tr>
              ) : (
                calls.map((call) => {
                  const isExpanded = expandedId === call.id;
                  const aStatus = ASSIGNMENT_BADGES[call.assignment_status] || ASSIGNMENT_BADGES.unassigned;
                  return (
                    <tr key={call.id} className="group">
                      <td colSpan={9} className="p-0">
                        <div>
                          <button
                            onClick={() => setExpandedId(isExpanded ? null : call.id)}
                            className="w-full text-left hover:bg-muted/30 transition-colors"
                          >
                            <div className="grid grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)_minmax(0,0.5fr)_minmax(0,0.5fr)_minmax(0,0.9fr)_minmax(0,0.8fr)_minmax(0,0.8fr)_minmax(0,1.5fr)_40px] items-center">
                              <span className="px-4 py-3 text-sm">{formatDate(call.created_at)}</span>
                              <span className="px-4 py-3 text-sm font-mono">{call.phone_number}</span>
                              <span className="px-4 py-3 text-sm">{formatDuration(call.duration)}</span>
                              <span className="px-4 py-3">
                                <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium capitalize ${LEAD_BADGES[call.lead_score] || "bg-gray-100 text-gray-700"}`}>
                                  {call.lead_score}
                                </span>
                              </span>
                              <span className="px-4 py-3">
                                <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${aStatus.badge}`}>
                                  {aStatus.label}
                                </span>
                              </span>
                              <span className="px-4 py-3 text-sm">
                                {call.assigned_operator_name || <span className="text-muted-foreground">--</span>}
                              </span>
                              <span className="px-4 py-3 text-sm">
                                {call.assigned_driver_name || <span className="text-muted-foreground">--</span>}
                              </span>
                              <span className="px-4 py-3 text-sm text-muted-foreground truncate">
                                {call.summary && call.summary.length > 60 ? `${call.summary.slice(0, 60)}...` : call.summary}
                              </span>
                              <span className="px-4 py-3 flex items-center justify-center">
                                {isExpanded ? (
                                  <ChevronUp className="w-4 h-4 text-muted-foreground" />
                                ) : (
                                  <ChevronDown className="w-4 h-4 text-muted-foreground" />
                                )}
                              </span>
                            </div>
                          </button>

                          {isExpanded && (
                            <div className="px-4 pb-4">
                              <div className="rounded-lg border border-border bg-muted/30 p-4 space-y-4">
                                {/* Assignment actions */}
                                <div className="flex flex-wrap gap-3">
                                  {/* Assign Operator */}
                                  <div className="relative">
                                    <button
                                      onClick={() => {
                                        setAssignDropdownId(
                                          assignDropdownId === `${call.id}-op` ? null : `${call.id}-op`
                                        );
                                      }}
                                      disabled={assigningId === call.id}
                                      className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border border-border hover:bg-muted transition-colors font-medium disabled:opacity-50"
                                    >
                                      {assigningId === call.id ? (
                                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                      ) : (
                                        <UserPlus className="w-3.5 h-3.5" />
                                      )}
                                      {call.assigned_operator_name || "Assign Operator"}
                                    </button>
                                    {assignDropdownId === `${call.id}-op` && (
                                      <div className="absolute left-0 top-full mt-1 w-56 bg-card border border-border rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
                                        {operators.length === 0 ? (
                                          <p className="px-3 py-2 text-sm text-muted-foreground">No operators available</p>
                                        ) : (
                                          operators.map((op) => (
                                            <button
                                              key={op.id}
                                              onClick={() => handleAssign(call.id, op.id, "operator")}
                                              className="w-full text-left px-3 py-2 text-sm hover:bg-muted transition-colors"
                                            >
                                              {op.name || op.email || op.id}
                                            </button>
                                          ))
                                        )}
                                      </div>
                                    )}
                                  </div>

                                  {/* Assign Driver */}
                                  <div className="relative">
                                    <button
                                      onClick={() => {
                                        setAssignDropdownId(
                                          assignDropdownId === `${call.id}-drv` ? null : `${call.id}-drv`
                                        );
                                      }}
                                      disabled={assigningId === call.id}
                                      className="inline-flex items-center gap-1.5 text-sm px-3 py-1.5 rounded-lg border border-border hover:bg-muted transition-colors font-medium disabled:opacity-50"
                                    >
                                      {assigningId === call.id ? (
                                        <Loader2 className="w-3.5 h-3.5 animate-spin" />
                                      ) : (
                                        <UserPlus className="w-3.5 h-3.5" />
                                      )}
                                      {call.assigned_driver_name || "Assign Driver"}
                                    </button>
                                    {assignDropdownId === `${call.id}-drv` && (
                                      <div className="absolute left-0 top-full mt-1 w-56 bg-card border border-border rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
                                        {drivers.length === 0 ? (
                                          <p className="px-3 py-2 text-sm text-muted-foreground">No drivers available</p>
                                        ) : (
                                          drivers.map((d) => (
                                            <button
                                              key={d.id}
                                              onClick={() => handleAssign(call.id, d.id, "driver")}
                                              className="w-full text-left px-3 py-2 text-sm hover:bg-muted transition-colors"
                                            >
                                              {d.name || d.email || d.id}
                                            </button>
                                          ))
                                        )}
                                      </div>
                                    )}
                                  </div>
                                </div>

                                <div>
                                  <p className="text-xs font-medium text-muted-foreground mb-1">Full Summary</p>
                                  <p className="text-sm">{call.summary}</p>
                                </div>
                                <div>
                                  <p className="text-xs font-medium text-muted-foreground mb-1">Transcript</p>
                                  <p className="text-sm whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto">
                                    {call.transcript || "No transcript available."}
                                  </p>
                                </div>
                              </div>
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
                <div className="h-6 bg-muted rounded-full w-16" />
                <div className="h-4 bg-muted rounded w-20" />
              </div>
              <div className="space-y-2">
                <div className="h-4 bg-muted rounded w-3/4" />
                <div className="h-3 bg-muted rounded w-1/2" />
              </div>
            </div>
          ))
        ) : calls.length === 0 ? (
          <div className="rounded-xl border border-border bg-card px-4 py-12 flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
              <Phone className="w-6 h-6 text-muted-foreground/60" />
            </div>
            <p className="text-sm text-muted-foreground">No calls match the current filters.</p>
          </div>
        ) : (
          calls.map((call) => {
            const isExpanded = expandedId === call.id;
            const aStatus = ASSIGNMENT_BADGES[call.assignment_status] || ASSIGNMENT_BADGES.unassigned;
            return (
              <div key={call.id} className="rounded-xl border border-border bg-card overflow-hidden">
                <button
                  onClick={() => setExpandedId(isExpanded ? null : call.id)}
                  className="w-full text-left p-4 space-y-3"
                >
                  <div className="flex items-center justify-between">
                    <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium capitalize ${LEAD_BADGES[call.lead_score] || "bg-gray-100 text-gray-700"}`}>
                      {call.lead_score}
                    </span>
                    <div className="flex items-center gap-2">
                      <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${aStatus.badge}`}>
                        {aStatus.label}
                      </span>
                      {isExpanded ? (
                        <ChevronUp className="w-4 h-4 text-muted-foreground" />
                      ) : (
                        <ChevronDown className="w-4 h-4 text-muted-foreground" />
                      )}
                    </div>
                  </div>
                  <div>
                    <p className="text-sm font-medium font-mono">{call.phone_number}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {formatDate(call.created_at)} &middot; {formatDuration(call.duration)}
                    </p>
                  </div>
                  {(call.assigned_operator_name || call.assigned_driver_name) && (
                    <div className="flex gap-3 text-xs text-muted-foreground">
                      {call.assigned_operator_name && <span>Op: {call.assigned_operator_name}</span>}
                      {call.assigned_driver_name && <span>Drv: {call.assigned_driver_name}</span>}
                    </div>
                  )}
                  <p className="text-sm text-muted-foreground line-clamp-2">{call.summary}</p>
                </button>

                {isExpanded && (
                  <div className="px-4 pb-4 space-y-3">
                    <div className="flex flex-wrap gap-2">
                      {/* Assign Operator */}
                      <div className="relative">
                        <button
                          onClick={() => setAssignDropdownId(
                            assignDropdownId === `${call.id}-op` ? null : `${call.id}-op`
                          )}
                          disabled={assigningId === call.id}
                          className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg border border-border hover:bg-muted transition-colors font-medium disabled:opacity-50"
                        >
                          {assigningId === call.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <UserPlus className="w-3 h-3" />}
                          {call.assigned_operator_name || "Operator"}
                        </button>
                        {assignDropdownId === `${call.id}-op` && (
                          <div className="absolute left-0 bottom-full mb-1 w-56 bg-card border border-border rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
                            {operators.map((op) => (
                              <button
                                key={op.id}
                                onClick={() => handleAssign(call.id, op.id, "operator")}
                                className="w-full text-left px-3 py-2 text-sm hover:bg-muted transition-colors"
                              >
                                {op.name || op.email || op.id}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                      {/* Assign Driver */}
                      <div className="relative">
                        <button
                          onClick={() => setAssignDropdownId(
                            assignDropdownId === `${call.id}-drv` ? null : `${call.id}-drv`
                          )}
                          disabled={assigningId === call.id}
                          className="inline-flex items-center gap-1 text-xs px-2 py-1 rounded-lg border border-border hover:bg-muted transition-colors font-medium disabled:opacity-50"
                        >
                          {assigningId === call.id ? <Loader2 className="w-3 h-3 animate-spin" /> : <UserPlus className="w-3 h-3" />}
                          {call.assigned_driver_name || "Driver"}
                        </button>
                        {assignDropdownId === `${call.id}-drv` && (
                          <div className="absolute left-0 bottom-full mb-1 w-56 bg-card border border-border rounded-lg shadow-lg z-20 max-h-48 overflow-y-auto">
                            {drivers.map((d) => (
                              <button
                                key={d.id}
                                onClick={() => handleAssign(call.id, d.id, "driver")}
                                className="w-full text-left px-3 py-2 text-sm hover:bg-muted transition-colors"
                              >
                                {d.name || d.email || d.id}
                              </button>
                            ))}
                          </div>
                        )}
                      </div>
                    </div>
                    <div className="rounded-lg border border-border bg-muted/30 p-4 space-y-3">
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1">Full Summary</p>
                        <p className="text-sm">{call.summary}</p>
                      </div>
                      <div>
                        <p className="text-xs font-medium text-muted-foreground mb-1">Transcript</p>
                        <p className="text-sm whitespace-pre-wrap leading-relaxed max-h-64 overflow-y-auto">
                          {call.transcript || "No transcript available."}
                        </p>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>

      {/* Load More */}
      {!loading && page < totalPages && (
        <div className="flex justify-center pt-2">
          <button
            onClick={() => setPage((p) => p + 1)}
            className="inline-flex items-center gap-2 text-sm px-5 py-2.5 rounded-lg border border-border hover:bg-muted transition-colors font-medium"
          >
            Load More
          </button>
        </div>
      )}

      {!loading && calls.length > 0 && (
        <p className="text-xs text-center text-muted-foreground">
          Page {page} of {totalPages}
        </p>
      )}
    </div>
  );
}
