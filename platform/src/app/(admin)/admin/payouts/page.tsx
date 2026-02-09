"use client";

import { useEffect, useState, useCallback } from "react";
import { adminApi } from "@/lib/api";
import type { AdminPaymentRecord, AdminPaymentTotals } from "@/lib/api";
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
  Users,
} from "lucide-react";

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

function payoutStatusBadge(status: string) {
  switch (status) {
    case "paid":
      return <Badge className="text-xs">Paid</Badge>;
    case "pending":
      return (
        <Badge variant="secondary" className="text-xs">
          Pending
        </Badge>
      );
    default:
      return (
        <Badge variant="outline" className="text-xs">
          {status}
        </Badge>
      );
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdminPayoutsPage() {
  const [payments, setPayments] = useState<AdminPaymentRecord[]>([]);
  const [totals, setTotals] = useState<AdminPaymentTotals | null>(null);
  const [totalCount, setTotalCount] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchData = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.payments({ status: "succeeded" });
      setPayments(res.payments || []);
      setTotals(res.totals || null);
      setTotalCount(res.total || 0);
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

  // ---- Derived values from server-computed totals ----
  const totalRevenue = totals?.total_revenue ?? 0;
  const totalCommission = totals?.total_commission ?? 0;
  const totalDriverPayouts = totals?.total_driver_payouts ?? 0;
  const totalOperatorPayouts = totals?.total_operator_payouts ?? 0;

  // Pending payouts = payments where payout_status is still "pending"
  const pendingPayoutTotal = payments
    .filter((p) => p.payout_status === "pending")
    .reduce((sum, p) => sum + p.driver_payout_amount + p.operator_payout_amount, 0);
  const pendingPayoutCount = payments.filter(
    (p) => p.payout_status === "pending"
  ).length;

  // Check if any payment has a non-zero operator payout (to show/hide operator column)
  const hasOperatorPayouts = payments.some(
    (p) => p.operator_payout_amount > 0 || p.operator_name
  );

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
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-muted-foreground">
                Total Revenue
              </span>
              <DollarSign className="h-5 w-5 text-muted-foreground" />
            </div>
            <p className="text-2xl font-display font-bold">
              {formatCurrency(totalRevenue)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {totalCount} payment{totalCount !== 1 ? "s" : ""} total
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-muted-foreground">
                Platform Commission
              </span>
              <Banknote className="h-5 w-5 text-muted-foreground" />
            </div>
            <p className="text-2xl font-display font-bold">
              {formatCurrency(totalCommission)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Platform&apos;s share of revenue
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-muted-foreground">
                Driver Payouts
              </span>
              <Users className="h-5 w-5 text-muted-foreground" />
            </div>
            <p className="text-2xl font-display font-bold text-green-600">
              {formatCurrency(totalDriverPayouts)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Total paid to drivers
            </p>
          </CardContent>
        </Card>
        <Card>
          <CardContent className="pt-6">
            <div className="flex items-center justify-between mb-2">
              <span className="text-sm font-medium text-muted-foreground">
                {totalOperatorPayouts > 0 ? "Operator Payouts" : "Pending Payouts"}
              </span>
              <Clock className="h-5 w-5 text-muted-foreground" />
            </div>
            <p className="text-2xl font-display font-bold">
              {totalOperatorPayouts > 0
                ? formatCurrency(totalOperatorPayouts)
                : formatCurrency(pendingPayoutTotal)}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              {totalOperatorPayouts > 0
                ? "Total paid to operators"
                : `${pendingPayoutCount} payment${pendingPayoutCount !== 1 ? "s" : ""} awaiting payout`}
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
      {/* Payment Breakdown Table                                              */}
      {/* ------------------------------------------------------------------ */}
      <Card>
        <CardHeader>
          <CardTitle className="font-display text-lg">
            Payment Breakdown
          </CardTitle>
          <CardDescription>
            Actual commission, operator, and driver payout amounts per payment
          </CardDescription>
        </CardHeader>
        <CardContent>
          {payments.length === 0 ? (
            <div className="text-center py-12">
              <p className="text-sm text-muted-foreground">
                No payments to display. Payouts will appear here after
                jobs are completed and paid.
              </p>
            </div>
          ) : (
            <div className="rounded-lg border border-border overflow-hidden">
              <div className="overflow-x-auto">
                <table className="w-full">
                  <thead>
                    <tr className="border-b border-border bg-muted/50">
                      <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                        Job
                      </th>
                      <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                        Driver
                      </th>
                      {hasOperatorPayouts && (
                        <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                          Operator
                        </th>
                      )}
                      <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                        Total
                      </th>
                      <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                        Platform Commission
                      </th>
                      {hasOperatorPayouts && (
                        <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                          Operator Payout
                        </th>
                      )}
                      <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                        Driver Payout
                      </th>
                      <th className="text-center text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                        Payout Status
                      </th>
                    </tr>
                  </thead>
                  <tbody>
                    {payments.map((payment) => (
                      <tr
                        key={payment.id}
                        className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors"
                      >
                        <td className="px-4 py-3">
                          <div className="text-sm font-mono">
                            {payment.job_id.length > 8
                              ? `${payment.job_id.slice(0, 8)}...`
                              : payment.job_id}
                          </div>
                          {payment.customer_name && (
                            <div className="text-xs text-muted-foreground mt-0.5">
                              {payment.customer_name}
                            </div>
                          )}
                        </td>
                        <td className="px-4 py-3 text-sm font-medium">
                          {payment.driver_name || "Unassigned"}
                        </td>
                        {hasOperatorPayouts && (
                          <td className="px-4 py-3 text-sm">
                            {payment.operator_name ? (
                              <span className="font-medium">
                                {payment.operator_name}
                              </span>
                            ) : (
                              <span className="text-muted-foreground">--</span>
                            )}
                          </td>
                        )}
                        <td className="px-4 py-3 text-sm text-right font-medium">
                          {formatCurrency(payment.amount)}
                        </td>
                        <td className="px-4 py-3 text-sm text-right text-muted-foreground">
                          {formatCurrency(payment.commission)}
                        </td>
                        {hasOperatorPayouts && (
                          <td className="px-4 py-3 text-sm text-right text-blue-600">
                            {payment.operator_payout_amount > 0
                              ? formatCurrency(payment.operator_payout_amount)
                              : "--"}
                          </td>
                        )}
                        <td className="px-4 py-3 text-sm text-right font-medium text-green-600">
                          {formatCurrency(payment.driver_payout_amount)}
                        </td>
                        <td className="px-4 py-3 text-center">
                          {payoutStatusBadge(payment.payout_status)}
                        </td>
                      </tr>
                    ))}
                  </tbody>
                  {/* Table footer with totals */}
                  <tfoot>
                    <tr className="border-t-2 border-border bg-muted/30">
                      <td
                        colSpan={hasOperatorPayouts ? 3 : 2}
                        className="px-4 py-3 text-sm font-semibold"
                      >
                        Totals ({payments.length} payment
                        {payments.length !== 1 ? "s" : ""})
                      </td>
                      <td className="px-4 py-3 text-sm text-right font-semibold">
                        {formatCurrency(
                          payments.reduce((sum, p) => sum + p.amount, 0)
                        )}
                      </td>
                      <td className="px-4 py-3 text-sm text-right text-muted-foreground font-semibold">
                        {formatCurrency(
                          payments.reduce((sum, p) => sum + p.commission, 0)
                        )}
                      </td>
                      {hasOperatorPayouts && (
                        <td className="px-4 py-3 text-sm text-right font-semibold text-blue-600">
                          {formatCurrency(
                            payments.reduce(
                              (sum, p) => sum + p.operator_payout_amount,
                              0
                            )
                          )}
                        </td>
                      )}
                      <td className="px-4 py-3 text-sm text-right font-semibold text-green-600">
                        {formatCurrency(
                          payments.reduce(
                            (sum, p) => sum + p.driver_payout_amount,
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
