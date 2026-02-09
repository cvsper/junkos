"use client";

import { useEffect, useState, useCallback } from "react";
import { adminApi } from "@/lib/api";
import type { DashboardData, AdminJobRecord } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  DollarSign,
  Clock,
  Banknote,
  Loader2,
  AlertCircle,
  RefreshCw,
  ExternalLink,
  Info,
} from "lucide-react";

const COMMISSION_RATE = 0.2;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatCurrency(value: number): string {
  return new Intl.NumberFormat("en-US", {
    style: "currency",
    currency: "USD",
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  }).format(value);
}

function getJobTotal(job: AdminJobRecord): number {
  return job.final_price || job.estimated_price || 0;
}

function getContractorName(job: AdminJobRecord): string {
  return job.customer_name || "Unassigned";
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdminPayoutsPage() {
  const [dashboardStats, setDashboardStats] = useState<DashboardData | null>(
    null
  );
  const [completedJobs, setCompletedJobs] = useState<AdminJobRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const [dashRes, jobsRes] = await Promise.all([
        adminApi.dashboard(),
        adminApi.jobs({ status: "completed" }),
      ]);

      // Unwrap the dashboard payload
      setDashboardStats(dashRes.dashboard);

      // Unwrap the paginated jobs payload
      setCompletedJobs(jobsRes.jobs || []);
    } catch (err: unknown) {
      setError(
        err instanceof Error ? err.message : "Failed to load payout data"
      );
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchData();
  }, [fetchData]);

  // ---- Derived values ----
  const totalRevenue = dashboardStats?.revenue_30d || 0;
  const totalCommission = dashboardStats?.commission_30d || totalRevenue * COMMISSION_RATE;
  const totalPaidOut = totalRevenue - totalCommission;
  const pendingPayouts = completedJobs
    .filter((j) => j.status === "completed")
    .reduce((sum, j) => sum + getJobTotal(j) * (1 - COMMISSION_RATE), 0);

  // ---- Loading state ----
  if (loading) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Payouts
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage contractor payouts and payment history.
          </p>
        </div>
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="ml-3 text-muted-foreground">
            Loading payout data...
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
            Payouts
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage contractor payouts and payment history.
          </p>
        </div>
        <div className="flex flex-col items-center justify-center py-24 text-center">
          <AlertCircle className="h-10 w-10 text-destructive mb-3" />
          <p className="text-sm text-destructive mb-4">{error}</p>
          <Button variant="outline" size="sm" onClick={fetchData}>
            <RefreshCw className="h-4 w-4 mr-2" />
            Retry
          </Button>
        </div>
      </div>
    );
  }

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display text-3xl font-bold tracking-tight">
          Payouts
        </h1>
        <p className="text-muted-foreground mt-1">
          Manage contractor payouts and payment history.
        </p>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Summary Cards                                                       */}
      {/* ------------------------------------------------------------------ */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4 mb-8">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-muted-foreground">
                Total Paid Out
              </span>
              <Banknote className="h-5 w-5 text-muted-foreground" />
            </div>
            <p className="text-2xl font-display font-bold">
              {formatCurrency(totalPaidOut)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              80% of total revenue to contractors
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-muted-foreground">
                Pending Payouts
              </span>
              <Clock className="h-5 w-5 text-muted-foreground" />
            </div>
            <p className="text-2xl font-display font-bold">
              {formatCurrency(pendingPayouts)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {completedJobs.length} completed job
              {completedJobs.length !== 1 ? "s" : ""} awaiting payout
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-muted-foreground">
                Platform Commission
              </span>
              <DollarSign className="h-5 w-5 text-muted-foreground" />
            </div>
            <p className="text-2xl font-display font-bold">
              {formatCurrency(totalCommission)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              20% commission earned
            </p>
          </CardContent>
        </Card>
      </div>

      {/* ------------------------------------------------------------------ */}
      {/* Stripe Connect Notice                                               */}
      {/* ------------------------------------------------------------------ */}
      <Card className="mb-8">
        <CardContent className="pt-6">
          <div className="flex items-start gap-3">
            <Info className="h-5 w-5 text-primary shrink-0 mt-0.5" />
            <div>
              <p className="text-sm font-medium">
                Payout Management via Stripe Connect
              </p>
              <p className="text-sm text-muted-foreground mt-1">
                Contractor payouts are processed automatically through Stripe
                Connect. Manage payout schedules, view transfer details, and
                handle disputes directly from the Stripe Dashboard.
              </p>
              <Button variant="outline" size="sm" className="mt-3" asChild>
                <a
                  href="https://dashboard.stripe.com/connect/accounts"
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Open Stripe Dashboard
                  <ExternalLink className="h-3.5 w-3.5 ml-1.5" />
                </a>
              </Button>
            </div>
          </div>
        </CardContent>
      </Card>

      {/* ------------------------------------------------------------------ */}
      {/* Completed Jobs / Payout Breakdown Table                             */}
      {/* ------------------------------------------------------------------ */}
      <Card>
        <CardHeader>
          <CardTitle className="font-display text-lg">
            Recent Completed Jobs
          </CardTitle>
          <CardDescription>
            Breakdown of job revenue, commission, and driver payouts
          </CardDescription>
        </CardHeader>
        <CardContent>
          {completedJobs.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm text-muted-foreground">
                No completed jobs to display. Payouts will appear here after
                jobs are completed.
              </p>
            </div>
          ) : (
            <div className="rounded-lg border border-border overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border bg-muted/50">
                      <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                        Job ID
                      </th>
                      <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                        Contractor
                      </th>
                      <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                        Job Total
                      </th>
                      <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                        Commission (20%)
                      </th>
                      <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                        Driver Payout (80%)
                      </th>
                      <th className="text-center text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                        Status
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {completedJobs.map((job) => {
                      const total = getJobTotal(job);
                      const commission = total * COMMISSION_RATE;
                      const driverPayout = total * (1 - COMMISSION_RATE);
                      return (
                        <tr
                          key={job.id}
                          className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors"
                        >
                          <td className="px-4 py-3 text-sm font-mono">
                            {job.id.length > 8
                              ? `${job.id.slice(0, 8)}...`
                              : job.id}
                          </td>
                          <td className="px-4 py-3 text-sm font-medium">
                            {getContractorName(job)}
                          </td>
                          <td className="px-4 py-3 text-sm text-right font-medium">
                            {formatCurrency(total)}
                          </td>
                          <td className="px-4 py-3 text-sm text-right text-muted-foreground">
                            {formatCurrency(commission)}
                          </td>
                          <td className="px-4 py-3 text-sm text-right font-medium text-green-600">
                            {formatCurrency(driverPayout)}
                          </td>
                          <td className="px-4 py-3 text-center">
                            <Badge
                              variant={
                                job.status === "completed"
                                  ? "default"
                                  : "secondary"
                              }
                              className="text-xs"
                            >
                              {job.status === "completed"
                                ? "Paid"
                                : job.status}
                            </Badge>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                  {/* Table footer with totals */}
                  <tfoot>
                    <tr className="border-t-2 border-border bg-muted/30">
                      <td
                        colSpan={2}
                        className="px-4 py-3 text-sm font-semibold"
                      >
                        Totals ({completedJobs.length} jobs)
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-semibold">
                        {formatCurrency(
                          completedJobs.reduce(
                            (sum, j) => sum + getJobTotal(j),
                            0
                          )
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-muted-foreground font-semibold">
                        {formatCurrency(
                          completedJobs.reduce(
                            (sum, j) =>
                              sum + getJobTotal(j) * COMMISSION_RATE,
                            0
                          )
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-semibold text-green-600">
                        {formatCurrency(
                          completedJobs.reduce(
                            (sum, j) =>
                              sum + getJobTotal(j) * (1 - COMMISSION_RATE),
                            0
                          )
                        )}
                      </td>
                      <td />
                    </tr>
                  </tfoot>
                </table>
              </div>
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
