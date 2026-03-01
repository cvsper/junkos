"use client";

import { useEffect, useState, useCallback } from "react";
import { driverApi } from "@/lib/api";
import type { DriverEarningsSummary, DriverEarningsRecord } from "@/types";
import {
  DollarSign,
  Briefcase,
  TrendingUp,
  AlertCircle,
  RefreshCw,
} from "lucide-react";

type Period = "today" | "week" | "month" | "all";

const PERIOD_TABS: { key: Period; label: string }[] = [
  { key: "today", label: "Today" },
  { key: "week", label: "This Week" },
  { key: "month", label: "This Month" },
  { key: "all", label: "All Time" },
];

interface WeeklyChartDay {
  day: string;
  amount: number;
}

export default function DriverEarningsPage() {
  const [period, setPeriod] = useState<Period>("week");
  const [summary, setSummary] = useState<DriverEarningsSummary | null>(null);
  const [records, setRecords] = useState<DriverEarningsRecord[]>([]);
  const [weeklyChart, setWeeklyChart] = useState<WeeklyChartDay[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchEarnings = useCallback(async (p: Period) => {
    setLoading(true);
    setError(null);
    try {
      const res = await driverApi.earnings(p);
      setSummary(res.summary);
      setRecords(res.records);
      setWeeklyChart(res.weekly_chart ?? []);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to load earnings";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchEarnings(period);
  }, [period, fetchEarnings]);

  function formatCurrency(amount: number): string {
    return `$${amount.toFixed(2)}`;
  }

  function formatDate(dateStr: string): string {
    const d = new Date(dateStr);
    return d.toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  }

  // ---------------------------------------------------------------------------
  // Skeleton loading state
  // ---------------------------------------------------------------------------
  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-display font-bold">Earnings</h1>

        {/* Period tabs skeleton */}
        <div className="flex gap-2">
          {PERIOD_TABS.map((t) => (
            <div
              key={t.key}
              className="h-9 w-24 rounded-lg bg-muted animate-pulse"
            />
          ))}
        </div>

        {/* Summary cards skeleton */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div
              key={i}
              className="rounded-xl border border-border bg-card p-6 animate-pulse"
            >
              <div className="h-4 bg-muted rounded w-24 mb-3" />
              <div className="h-8 bg-muted rounded w-20" />
            </div>
          ))}
        </div>

        {/* Chart skeleton */}
        <div className="rounded-xl border border-border bg-card p-6 h-56 animate-pulse" />

        {/* Table skeleton */}
        <div className="rounded-xl border border-border bg-card p-6 h-64 animate-pulse" />
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Error state
  // ---------------------------------------------------------------------------
  if (error) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-display font-bold">Earnings</h1>
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-8 text-center space-y-3">
          <AlertCircle className="w-8 h-8 text-destructive mx-auto" />
          <p className="text-destructive font-medium">{error}</p>
          <button
            onClick={() => fetchEarnings(period)}
            className="inline-flex items-center gap-2 text-sm font-medium text-primary hover:underline"
          >
            <RefreshCw className="w-4 h-4" />
            Try Again
          </button>
        </div>
      </div>
    );
  }

  const maxAmount = Math.max(...weeklyChart.map((d) => d.amount), 1);

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-display font-bold">Earnings</h1>

      {/* ------------------------------------------------------------------ */}
      {/* Period Filter Tabs                                                  */}
      {/* ------------------------------------------------------------------ */}
      <div className="flex flex-wrap gap-2">
        {PERIOD_TABS.map((tab) => (
          <button
            key={tab.key}
            onClick={() => setPeriod(tab.key)}
            className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
              period === tab.key
                ? "bg-primary text-primary-foreground"
                : "bg-muted text-muted-foreground hover:text-foreground"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Summary Cards                                                       */}
      {/* ------------------------------------------------------------------ */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <SummaryCard
          label="Total Earnings"
          value={formatCurrency(summary?.total ?? 0)}
          icon={DollarSign}
          bgColor="bg-emerald-50"
          textColor="text-emerald-600"
        />
        <SummaryCard
          label="Jobs Completed"
          value={String(summary?.jobs_completed ?? 0)}
          icon={Briefcase}
          bgColor="bg-blue-50"
          textColor="text-blue-600"
        />
        <SummaryCard
          label="Avg per Job"
          value={formatCurrency(summary?.avg_per_job ?? 0)}
          icon={TrendingUp}
          bgColor="bg-purple-50"
          textColor="text-purple-600"
        />
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Weekly Bar Chart (CSS-only)                                          */}
      {/* ------------------------------------------------------------------ */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Weekly Earnings</h2>
        </div>
        <div className="p-6">
          {weeklyChart.length === 0 ? (
            <div className="flex items-center justify-center h-40 text-sm text-muted-foreground">
              No earnings data for this period
            </div>
          ) : (
            <div className="flex items-end gap-2 sm:gap-3">
              {weeklyChart.map((day) => (
                <div
                  key={day.day}
                  className="flex flex-col items-center gap-1 flex-1"
                >
                  <span className="text-xs text-muted-foreground">
                    ${day.amount.toFixed(0)}
                  </span>
                  <div
                    className="w-full bg-muted rounded-t-sm"
                    style={{ height: "120px" }}
                  >
                    <div
                      className="w-full bg-emerald-500 rounded-t-sm"
                      style={{
                        height: `${(day.amount / maxAmount) * 100}%`,
                        marginTop: `${100 - (day.amount / maxAmount) * 100}%`,
                      }}
                    />
                  </div>
                  <span className="text-xs font-medium">{day.day}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Earnings History — Desktop Table                                     */}
      {/* ------------------------------------------------------------------ */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Earnings History</h2>
        </div>

        {records.length === 0 ? (
          <div className="p-8 text-center text-sm text-muted-foreground">
            No earnings records for this period
          </div>
        ) : (
          <>
            {/* Desktop table */}
            <div className="hidden md:block overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-muted-foreground">
                    <th className="px-6 py-3 font-medium">Job Address</th>
                    <th className="px-6 py-3 font-medium">Amount</th>
                    <th className="px-6 py-3 font-medium">Tip</th>
                    <th className="px-6 py-3 font-medium">Payout Status</th>
                    <th className="px-6 py-3 font-medium">Date</th>
                  </tr>
                </thead>
                <tbody>
                  {records.map((record) => (
                    <tr
                      key={record.id}
                      className="border-b border-border last:border-0 hover:bg-muted/50 transition-colors"
                    >
                      <td className="px-6 py-4 max-w-[240px] truncate">
                        {record.address}
                      </td>
                      <td className="px-6 py-4 font-medium">
                        {formatCurrency(record.amount)}
                      </td>
                      <td className="px-6 py-4">
                        {record.tip > 0
                          ? formatCurrency(record.tip)
                          : "--"}
                      </td>
                      <td className="px-6 py-4">
                        <PayoutBadge status={record.payout_status} />
                      </td>
                      <td className="px-6 py-4 text-muted-foreground">
                        {formatDate(record.completed_at)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Mobile cards */}
            <div className="md:hidden divide-y divide-border">
              {records.map((record) => (
                <div key={record.id} className="p-4 space-y-2">
                  <div className="flex items-start justify-between gap-2">
                    <p className="text-sm font-medium truncate flex-1">
                      {record.address}
                    </p>
                    <PayoutBadge status={record.payout_status} />
                  </div>
                  <div className="flex items-center justify-between text-sm">
                    <div className="flex items-center gap-3">
                      <span className="font-medium">
                        {formatCurrency(record.amount)}
                      </span>
                      {record.tip > 0 && (
                        <span className="text-muted-foreground">
                          + {formatCurrency(record.tip)} tip
                        </span>
                      )}
                    </div>
                    <span className="text-xs text-muted-foreground">
                      {formatDate(record.completed_at)}
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Summary Card                                                                */
/* -------------------------------------------------------------------------- */

function SummaryCard({
  label,
  value,
  icon: Icon,
  bgColor,
  textColor,
}: {
  label: string;
  value: string;
  icon: React.ComponentType<{ className?: string }>;
  bgColor: string;
  textColor: string;
}) {
  return (
    <div className="rounded-xl border border-border bg-card p-6">
      <div className="flex items-center gap-3">
        <div
          className={`w-10 h-10 rounded-lg ${bgColor} flex items-center justify-center flex-shrink-0`}
        >
          <Icon className={`w-5 h-5 ${textColor}`} />
        </div>
        <div className="min-w-0">
          <p className="text-sm text-muted-foreground">{label}</p>
          <p className={`text-2xl font-bold ${textColor}`}>{value}</p>
        </div>
      </div>
    </div>
  );
}

/* -------------------------------------------------------------------------- */
/* Payout Status Badge                                                         */
/* -------------------------------------------------------------------------- */

function PayoutBadge({
  status,
}: {
  status: "pending" | "processing" | "paid";
}) {
  const styles: Record<string, string> = {
    pending: "bg-amber-100 text-amber-700",
    processing: "bg-blue-100 text-blue-700",
    paid: "bg-emerald-100 text-emerald-700",
  };

  return (
    <span
      className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium capitalize ${
        styles[status] ?? styles.pending
      }`}
    >
      {status}
    </span>
  );
}
