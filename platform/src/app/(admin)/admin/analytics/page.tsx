"use client";

import { useEffect, useState, useCallback } from "react";
import { adminApi } from "@/lib/api";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import {
  BarChart3,
  DollarSign,
  CheckCircle2,
  CalendarDays,
  Loader2,
  AlertCircle,
  RefreshCw,
  Star,
  Clock,
  TrendingUp,
  Users,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface DayData {
  date: string;
  count: number;
}

interface WeekData {
  week_start: string;
  revenue: number;
}

interface ContractorData {
  id: string;
  name: string | null;
  total_jobs: number;
  avg_rating: number;
}

interface HourData {
  hour: number;
  count: number;
}

interface AnalyticsData {
  jobs_by_day: DayData[];
  revenue_by_week: WeekData[];
  jobs_by_status: Record<string, number>;
  top_contractors: ContractorData[];
  busiest_hours: HourData[];
  avg_job_value: number;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
  completed: "bg-green-500",
  in_progress: "bg-blue-500",
  pending: "bg-yellow-500",
  assigned: "bg-purple-500",
  cancelled: "bg-red-500",
};

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 0,
    maximumFractionDigits: 0,
  }).format(value);
}

function formatDate(dateStr: string): string {
  const d = new Date(dateStr);
  return d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
}

function formatHour(hour: number): string {
  if (hour === 0) return "12a";
  if (hour < 12) return `${hour}a`;
  if (hour === 12) return "12p";
  return `${hour - 12}p`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdminAnalyticsPage() {
  const [analytics, setAnalytics] = useState<AnalyticsData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchAnalytics = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.analytics();
      setAnalytics(res.analytics as AnalyticsData);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to load analytics"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchAnalytics();
  }, [fetchAnalytics]);

  // ---- Loading state ----
  if (loading) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Analytics
          </h1>
          <p className="text-muted-foreground mt-1">
            Insights and metrics for your junk removal operations.
          </p>
        </div>
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="ml-3 text-muted-foreground">
            Loading analytics...
          </span>
        </div>
      </div>
    );
  }

  // ---- Error state ----
  if (error) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Analytics
          </h1>
          <p className="text-muted-foreground mt-1">
            Insights and metrics for your junk removal operations.
          </p>
        </div>
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <AlertCircle className="h-10 w-10 text-destructive mb-3" />
          <p className="text-sm text-destructive mb-4">{error}</p>
          <Button variant="outline" size="sm" onClick={fetchAnalytics}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  // ---- Derived values ----
  const jobsByDay = analytics?.jobs_by_day || [];
  const revenueByWeek = analytics?.revenue_by_week || [];
  const jobsByStatusRaw = analytics?.jobs_by_status || {};
  const jobsByStatus = Object.entries(jobsByStatusRaw).map(([status, count]) => ({
    status,
    count,
  }));
  const topContractors = analytics?.top_contractors || [];
  const busiestHours = analytics?.busiest_hours || [];
  const avgJobValue = analytics?.avg_job_value || 0;

  const totalCompleted = jobsByStatusRaw["completed"] || 0;
  const jobsThisMonth = jobsByDay.reduce((sum, d) => sum + d.count, 0);

  const maxDayCount = Math.max(...jobsByDay.map((d) => d.count), 1);
  const maxWeekRevenue = Math.max(...revenueByWeek.map((w) => w.revenue), 1);
  const maxStatusCount = Math.max(...jobsByStatus.map((s) => s.count), 1);
  const maxHourCount = Math.max(...busiestHours.map((h) => h.count), 1);

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display text-3xl font-bold tracking-tight">
          Analytics
        </h1>
        <p className="text-muted-foreground mt-1">
          Insights and metrics for your junk removal operations.
        </p>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Summary Stat Cards                                                  */}
      {/* ------------------------------------------------------------------ */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-muted-foreground">
                Avg Job Value
              </span>
              <DollarSign className="h-5 w-5 text-muted-foreground" />
            </div>
            <p className="text-2xl font-display font-bold">
              {formatCurrency(avgJobValue)}
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-muted-foreground">
                Total Completed
              </span>
              <CheckCircle2 className="h-5 w-5 text-muted-foreground" />
            </div>
            <p className="text-2xl font-display font-bold">{totalCompleted}</p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-muted-foreground">
                Jobs This Month
              </span>
              <CalendarDays className="h-5 w-5 text-muted-foreground" />
            </div>
            <p className="text-2xl font-display font-bold">{jobsThisMonth}</p>
          </CardContent>
        </Card>
      </div>

      <div className="space-y-8">
        {/* ---------------------------------------------------------------- */}
        {/* Chart 1: Jobs Per Day                                             */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-lg">
              <BarChart3 className="h-5 w-5 text-primary" />
              Jobs Per Day
            </CardTitle>
            <CardDescription>Last 30 days of job volume</CardDescription>
          </CardHeader>
          <CardContent>
            {jobsByDay.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-sm text-muted-foreground">
                  No daily job data available yet.
                </p>
              </div>
            ) : (
              <div className="flex items-end gap-[3px] h-48">
                {jobsByDay.map((day, i) => {
                  const heightPct = (day.count / maxDayCount) * 100;
                  return (
                    <div
                      key={i}
                      className="group relative flex-1 min-w-0 flex flex-col justify-end h-full"
                    >
                      <div
                        className="bg-primary/80 hover:bg-primary rounded-t transition-colors w-full"
                        style={{ height: `${Math.max(heightPct, 2)}%` }}
                      />
                      {/* Tooltip */}
                      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                        <div className="rounded-md bg-foreground text-background px-2 py-1 text-xs whitespace-nowrap shadow-lg">
                          <p className="font-medium">{formatDate(day.date)}</p>
                          <p>
                            {day.count} job{day.count !== 1 ? "s" : ""}
                          </p>
                        </div>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Chart 2: Revenue Per Week                                         */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-lg">
              <TrendingUp className="h-5 w-5 text-primary" />
              Revenue Per Week
            </CardTitle>
            <CardDescription>Last 12 weeks of revenue</CardDescription>
          </CardHeader>
          <CardContent>
            {revenueByWeek.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-sm text-muted-foreground">
                  No weekly revenue data available yet.
                </p>
              </div>
            ) : (
              <div className="flex items-end gap-2 h-48">
                {revenueByWeek.map((week, i) => {
                  const heightPct = (week.revenue / maxWeekRevenue) * 100;
                  return (
                    <div
                      key={i}
                      className="group relative flex-1 min-w-0 flex flex-col justify-end h-full"
                    >
                      <div
                        className="bg-green-500/80 hover:bg-green-500 rounded-t transition-colors w-full"
                        style={{ height: `${Math.max(heightPct, 2)}%` }}
                      />
                      {/* Tooltip */}
                      <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                        <div className="rounded-md bg-foreground text-background px-2 py-1 text-xs whitespace-nowrap shadow-lg">
                          <p className="font-medium">{week.week_start}</p>
                          <p>{formatCurrency(week.revenue)}</p>
                        </div>
                      </div>
                      {/* Label */}
                      <p className="text-[9px] text-muted-foreground text-center mt-1 truncate">
                        {week.week_start}
                      </p>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Chart 3: Jobs by Status (horizontal bars)                         */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-lg">
              <BarChart3 className="h-5 w-5 text-primary" />
              Jobs by Status
            </CardTitle>
            <CardDescription>
              Breakdown of jobs across all statuses
            </CardDescription>
          </CardHeader>
          <CardContent>
            {jobsByStatus.length === 0 ? (
              <div className="text-center py-8">
                <p className="text-sm text-muted-foreground">
                  No status data available yet.
                </p>
              </div>
            ) : (
              <div className="space-y-3">
                {jobsByStatus.map((item) => {
                  const widthPct = (item.count / maxStatusCount) * 100;
                  const color =
                    STATUS_COLORS[item.status] || "bg-muted-foreground";
                  return (
                    <div key={item.status}>
                      <div className="flex items-center justify-between mb-1">
                        <span className="text-sm font-medium capitalize">
                          {item.status.replace(/_/g, " ")}
                        </span>
                        <span className="text-sm text-muted-foreground">
                          {item.count}
                        </span>
                      </div>
                      <div className="h-6 w-full rounded-full bg-muted overflow-hidden">
                        <div
                          className={`h-full rounded-full transition-all ${color}`}
                          style={{ width: `${Math.max(widthPct, 1)}%` }}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* Two-column layout for bottom sections */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8">
          {/* ---------------------------------------------------------------- */}
          {/* Top Contractors                                                   */}
          {/* ---------------------------------------------------------------- */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 font-display text-lg">
                <Users className="h-5 w-5 text-primary" />
                Top Contractors
              </CardTitle>
              <CardDescription>
                Highest performing contractors by job count
              </CardDescription>
            </CardHeader>
            <CardContent>
              {topContractors.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-sm text-muted-foreground">
                    No contractor data available yet.
                  </p>
                </div>
              ) : (
                <div className="space-y-3">
                  {topContractors.map((contractor, i) => (
                    <div
                      key={i}
                      className="flex items-center gap-3 rounded-md border border-border p-3"
                    >
                      {/* Rank */}
                      <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10 text-sm font-display font-bold text-primary shrink-0">
                        {i + 1}
                      </div>

                      {/* Info */}
                      <div className="flex-1 min-w-0">
                        <p className="text-sm font-medium truncate">
                          {contractor.name || "Unknown"}
                        </p>
                        <div className="flex items-center gap-1 mt-0.5">
                          {Array.from({ length: 5 }).map((_, starIdx) => (
                            <Star
                              key={starIdx}
                              className={`h-3 w-3 ${
                                starIdx < Math.round(contractor.avg_rating)
                                  ? "text-yellow-500 fill-yellow-500"
                                  : "text-muted-foreground/30"
                              }`}
                            />
                          ))}
                          <span className="text-xs text-muted-foreground ml-1">
                            {contractor.avg_rating.toFixed(1)}
                          </span>
                        </div>
                      </div>

                      {/* Jobs count */}
                      <Badge variant="secondary">
                        {contractor.total_jobs} jobs
                      </Badge>
                    </div>
                  ))}
                </div>
              )}
            </CardContent>
          </Card>

          {/* ---------------------------------------------------------------- */}
          {/* Busiest Hours                                                     */}
          {/* ---------------------------------------------------------------- */}
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2 font-display text-lg">
                <Clock className="h-5 w-5 text-primary" />
                Busiest Hours
              </CardTitle>
              <CardDescription>
                Job distribution by hour of day
              </CardDescription>
            </CardHeader>
            <CardContent>
              {busiestHours.length === 0 ? (
                <div className="text-center py-8">
                  <p className="text-sm text-muted-foreground">
                    No hourly data available yet.
                  </p>
                </div>
              ) : (
                <div className="flex items-end gap-[2px] h-40">
                  {busiestHours.map((hourData, i) => {
                    const heightPct =
                      (hourData.count / maxHourCount) * 100;
                    return (
                      <div
                        key={i}
                        className="group relative flex-1 min-w-0 flex flex-col justify-end h-full"
                      >
                        <div
                          className="bg-blue-500/70 hover:bg-blue-500 rounded-t transition-colors w-full"
                          style={{
                            height: `${Math.max(heightPct, 2)}%`,
                          }}
                        />
                        {/* Tooltip */}
                        <div className="absolute bottom-full left-1/2 -translate-x-1/2 mb-2 hidden group-hover:block z-10">
                          <div className="rounded-md bg-foreground text-background px-2 py-1 text-xs whitespace-nowrap shadow-lg">
                            <p className="font-medium">
                              {formatHour(hourData.hour)}
                            </p>
                            <p>
                              {hourData.count} job
                              {hourData.count !== 1 ? "s" : ""}
                            </p>
                          </div>
                        </div>
                        {/* Hour label - show every 3 hours */}
                        {hourData.hour % 3 === 0 && (
                          <p className="text-[8px] text-muted-foreground text-center mt-1">
                            {formatHour(hourData.hour)}
                          </p>
                        )}
                      </div>
                    );
                  })}
                </div>
              )}
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
