"use client";

import { useEffect, useState } from "react";
import { operatorApi, type OperatorAnalytics } from "@/lib/api";

export default function OperatorAnalyticsPage() {
  const [data, setData] = useState<OperatorAnalytics | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    operatorApi
      .analytics()
      .then((res) => setData(res.analytics))
      .catch((err) => setError(err.message || "Failed to load analytics"))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-display font-bold">Analytics</h1>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-border bg-card p-6 animate-pulse"
            >
              <div className="h-4 bg-muted rounded w-24 mb-2" />
              <div className="h-8 bg-muted rounded w-20" />
            </div>
          ))}
        </div>
        <div className="rounded-xl border border-border bg-card p-6 h-64 animate-pulse" />
        <div className="rounded-xl border border-border bg-card p-6 h-64 animate-pulse" />
      </div>
    );
  }

  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-display font-bold">Analytics</h1>
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-6 text-center">
          <p className="text-destructive">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) return null;

  // Derived stats
  const totalCommission = data.per_contractor_jobs.reduce(
    (sum, c) => sum + c.commission,
    0
  );
  const totalJobs = data.per_contractor_jobs.reduce(
    (sum, c) => sum + c.jobs,
    0
  );
  const totalJobsLast30 = data.jobs_by_day.reduce(
    (sum, d) => sum + d.count,
    0
  );

  // Chart helpers
  const maxWeeklyEarning = Math.max(...data.earnings_by_week.map((w) => w.amount), 1);
  const maxDailyJobs = Math.max(...data.jobs_by_day.map((d) => d.count), 1);
  const maxContractorJobs = Math.max(
    ...data.per_contractor_jobs.map((c) => c.jobs),
    1
  );
  const maxContractorCommission = Math.max(
    ...data.per_contractor_jobs.map((c) => c.commission),
    1
  );

  function formatWeekLabel(dateStr: string) {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  function formatDayLabel(dateStr: string) {
    const d = new Date(dateStr + "T00:00:00");
    return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-display font-bold">Analytics</h1>

      {/* ---------- Key Metric Cards ---------- */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
        <MetricCard
          label="Total Commission"
          value={`$${totalCommission.toFixed(2)}`}
          accent
        />
        <MetricCard
          label="Jobs Delegated (all time)"
          value={String(totalJobs)}
        />
        <MetricCard
          label="Jobs (last 30d)"
          value={String(totalJobsLast30)}
        />
        <MetricCard
          label="Avg Delegation Time"
          value={
            data.delegation_time_avg !== null
              ? `${data.delegation_time_avg} min`
              : "--"
          }
        />
      </div>

      {/* ---------- Weekly Earnings Trend ---------- */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Weekly Commission (last 12 weeks)</h2>
        </div>
        <div className="p-6">
          {/* Area / bar style chart via CSS */}
          <div className="flex items-end gap-1.5 h-48">
            {data.earnings_by_week.map((w, i) => {
              const pct = (w.amount / maxWeeklyEarning) * 100;
              return (
                <div
                  key={i}
                  className="flex-1 flex flex-col items-center gap-1 group relative"
                >
                  {/* Tooltip */}
                  <div className="absolute bottom-full mb-1 hidden group-hover:flex flex-col items-center z-10">
                    <span className="bg-foreground text-background text-xs px-2 py-1 rounded whitespace-nowrap">
                      ${w.amount.toFixed(2)}
                    </span>
                    <span className="w-0 h-0 border-l-4 border-r-4 border-t-4 border-l-transparent border-r-transparent border-t-foreground" />
                  </div>
                  <div
                    className="w-full rounded-t bg-primary/80 hover:bg-primary transition-colors min-h-[2px]"
                    style={{ height: `${Math.max(pct, 1)}%` }}
                  />
                  <span className="text-[10px] text-muted-foreground leading-tight text-center hidden sm:block">
                    {formatWeekLabel(w.week_start)}
                  </span>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ---------- Daily Jobs (last 30 days) ---------- */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Daily Jobs (last 30 days)</h2>
        </div>
        <div className="p-6">
          <div className="flex items-end gap-[3px] h-40">
            {data.jobs_by_day.map((d, i) => {
              const pct = (d.count / maxDailyJobs) * 100;
              const showLabel = i % 5 === 0;
              return (
                <div
                  key={i}
                  className="flex-1 flex flex-col items-center gap-1 group relative"
                >
                  <div className="absolute bottom-full mb-1 hidden group-hover:flex flex-col items-center z-10">
                    <span className="bg-foreground text-background text-xs px-2 py-1 rounded whitespace-nowrap">
                      {d.count} job{d.count !== 1 ? "s" : ""} &middot;{" "}
                      {formatDayLabel(d.date)}
                    </span>
                    <span className="w-0 h-0 border-l-4 border-r-4 border-t-4 border-l-transparent border-r-transparent border-t-foreground" />
                  </div>
                  <div
                    className="w-full rounded-t bg-amber-500/80 hover:bg-amber-500 transition-colors min-h-[2px]"
                    style={{ height: `${Math.max(pct, 1)}%` }}
                  />
                  {showLabel && (
                    <span className="text-[9px] text-muted-foreground leading-tight text-center hidden sm:block">
                      {formatDayLabel(d.date)}
                    </span>
                  )}
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* ---------- Contractor Breakdown ---------- */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Contractor Breakdown</h2>
        </div>
        <div className="p-6 space-y-4">
          {data.per_contractor_jobs.length === 0 ? (
            <p className="text-sm text-muted-foreground text-center py-8">
              No contractor data yet
            </p>
          ) : (
            data.per_contractor_jobs.map((c) => {
              const jobsPct = (c.jobs / maxContractorJobs) * 100;
              const commPct = (c.commission / maxContractorCommission) * 100;
              return (
                <div key={c.contractor_id} className="space-y-2">
                  <div className="flex items-center justify-between text-sm">
                    <span className="font-medium truncate max-w-[180px]">
                      {c.name || "Unnamed"}
                    </span>
                    <span className="text-muted-foreground">
                      {c.jobs} job{c.jobs !== 1 ? "s" : ""} &middot;{" "}
                      <span className="text-primary font-medium">
                        ${c.commission.toFixed(2)}
                      </span>
                    </span>
                  </div>
                  {/* Jobs bar */}
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-primary/70 rounded-full transition-all duration-500"
                      style={{ width: `${jobsPct}%` }}
                    />
                  </div>
                  {/* Commission bar */}
                  <div className="h-2 bg-muted rounded-full overflow-hidden">
                    <div
                      className="h-full bg-amber-500/70 rounded-full transition-all duration-500"
                      style={{ width: `${commPct}%` }}
                    />
                  </div>
                  <div className="flex gap-4 text-[10px] text-muted-foreground">
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-primary/70 inline-block" />
                      Jobs
                    </span>
                    <span className="flex items-center gap-1">
                      <span className="w-2 h-2 rounded-full bg-amber-500/70 inline-block" />
                      Commission
                    </span>
                  </div>
                </div>
              );
            })
          )}
        </div>
      </div>
    </div>
  );
}

/* ---------- Metric Card Component ---------- */

function MetricCard({
  label,
  value,
  accent,
}: {
  label: string;
  value: string;
  accent?: boolean;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-6">
      <p className="text-sm text-muted-foreground">{label}</p>
      <p
        className={`text-2xl font-bold mt-1 ${
          accent ? "text-primary" : ""
        }`}
      >
        {value}
      </p>
    </div>
  );
}
