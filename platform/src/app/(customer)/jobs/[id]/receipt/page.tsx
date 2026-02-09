"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { jobsApi } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface JobPayment {
  amount: number;
  payment_status: string;
  tip_amount: number;
}

interface JobContractor {
  id: string;
  user: { name: string | null; phone: string | null } | null;
  truck_type: string | null;
  avg_rating: number;
  total_jobs: number;
}

interface JobDetail {
  id: string;
  status: string;
  address: string;
  items: { category: string; quantity: number }[];
  photos: string[];
  total_price: number;
  base_price: number;
  item_total: number;
  service_fee: number;
  surge_multiplier: number;
  notes: string | null;
  scheduled_at: string | null;
  created_at: string;
  completed_at: string | null;
  payment?: JobPayment | null;
  contractor?: JobContractor | null;
}

// ---------------------------------------------------------------------------
// Status colors
// ---------------------------------------------------------------------------

const STATUS_COLORS: Record<string, string> = {
  pending: "bg-yellow-100 text-yellow-800 border-yellow-200",
  confirmed: "bg-blue-100 text-blue-800 border-blue-200",
  assigned: "bg-indigo-100 text-indigo-800 border-indigo-200",
  en_route: "bg-orange-100 text-orange-800 border-orange-200",
  arrived: "bg-orange-100 text-orange-800 border-orange-200",
  in_progress: "bg-orange-100 text-orange-800 border-orange-200",
  completed: "bg-green-100 text-green-800 border-green-200",
  cancelled: "bg-red-100 text-red-800 border-red-200",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusLabel(status: string): string {
  return status
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDate(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

function formatDateTime(iso: string): string {
  const d = new Date(iso);
  return d.toLocaleString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

function formatPrice(amount: number): string {
  return `$${amount.toFixed(2)}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function ReceiptPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchJob = useCallback(async () => {
    if (!id) return;
    setLoading(true);
    setError(null);
    try {
      const res = await jobsApi.get(id);
      setJob(res.job ?? null);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to load job details.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  useEffect(() => {
    fetchJob();
  }, [fetchJob]);

  function handlePrint() {
    window.print();
  }

  const shortId = id ? id.slice(0, 8) : "";

  // Loading state
  if (loading) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 sm:py-12">
        <div className="flex items-center justify-center py-24">
          <svg
            className="h-8 w-8 animate-spin text-primary"
            xmlns="http://www.w3.org/2000/svg"
            fill="none"
            viewBox="0 0 24 24"
          >
            <circle
              className="opacity-25"
              cx="12"
              cy="12"
              r="10"
              stroke="currentColor"
              strokeWidth="4"
            />
            <path
              className="opacity-75"
              fill="currentColor"
              d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z"
            />
          </svg>
          <span className="ml-3 text-muted-foreground text-sm">
            Loading receipt...
          </span>
        </div>
      </div>
    );
  }

  // Error state
  if (error && !job) {
    return (
      <div className="max-w-2xl mx-auto px-4 py-8 sm:py-12">
        <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-6 print:hidden">
          <Link
            href="/dashboard"
            className="hover:text-foreground transition-colors"
          >
            My Jobs
          </Link>
          <span>/</span>
          <span className="text-foreground">Receipt</span>
        </nav>
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-8 text-center">
          <p className="text-destructive font-medium mb-1">
            Something went wrong
          </p>
          <p className="text-muted-foreground text-sm mb-4">{error}</p>
          <div className="flex items-center justify-center gap-3">
            <Button variant="outline" size="sm" onClick={fetchJob}>
              Try Again
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push("/dashboard")}
            >
              Back to Dashboard
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!job) return null;

  const hasSurge = job.surge_multiplier > 1.0;
  const subtotal = job.base_price + job.item_total;
  const hasContractor = !!job.contractor;
  const tipAmount = job.payment?.tip_amount ?? 0;
  const grandTotal = job.total_price + tipAmount;

  return (
    <>
      {/* Print-friendly styles */}
      <style jsx global>{`
        @media print {
          /* Hide navigation, header, footer */
          header, footer, nav, .print\\:hidden {
            display: none !important;
          }
          /* Make the receipt full width */
          body {
            background: white !important;
            -webkit-print-color-adjust: exact;
            print-color-adjust: exact;
          }
          /* Remove shadows and borders for cleaner print */
          .print-receipt {
            box-shadow: none !important;
            border: none !important;
            max-width: 100% !important;
            padding: 0 !important;
          }
          /* Ensure text is dark for readability */
          * {
            color: #1a1a1a !important;
          }
          .print-subtle {
            color: #666 !important;
          }
        }
      `}</style>

      <div className="max-w-2xl mx-auto px-4 py-8 sm:py-12">
        {/* Breadcrumb -- hidden on print */}
        <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-6 print:hidden">
          <Link
            href="/dashboard"
            className="hover:text-foreground transition-colors"
          >
            My Jobs
          </Link>
          <span>/</span>
          <Link
            href={`/jobs/${id}`}
            className="hover:text-foreground transition-colors"
          >
            Job #{shortId}
          </Link>
          <span>/</span>
          <span className="text-foreground">Receipt</span>
        </nav>

        {/* Actions bar -- hidden on print */}
        <div className="flex items-center justify-between mb-6 print:hidden">
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">
            Receipt
          </h1>
          <div className="flex items-center gap-3">
            <Link href={`/jobs/${id}`}>
              <Button variant="outline" size="sm">
                Job Details
              </Button>
            </Link>
            <Button onClick={handlePrint} size="sm" className="gap-2">
              <svg
                className="w-4 h-4"
                fill="none"
                viewBox="0 0 24 24"
                strokeWidth={2}
                stroke="currentColor"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="M6.72 13.829c-.24.03-.48.062-.72.096m.72-.096a42.415 42.415 0 0110.56 0m-10.56 0L6.34 18m10.94-4.171c.24.03.48.062.72.096m-.72-.096L17.66 18m0 0l.229 2.523a1.125 1.125 0 01-1.12 1.227H7.231c-.662 0-1.18-.568-1.12-1.227L6.34 18m11.318 0h1.091A2.25 2.25 0 0021 15.75V9.456c0-1.081-.768-2.015-1.837-2.175a48.055 48.055 0 00-1.913-.247M6.34 18H5.25A2.25 2.25 0 013 15.75V9.456c0-1.081.768-2.015 1.837-2.175a48.041 48.041 0 011.913-.247m10.5 0a48.536 48.536 0 00-10.5 0m10.5 0V3.375c0-.621-.504-1.125-1.125-1.125h-8.25c-.621 0-1.125.504-1.125 1.125v3.659M18 10.5h.008v.008H18V10.5zm-3 0h.008v.008H15V10.5z"
                />
              </svg>
              Download Receipt
            </Button>
          </div>
        </div>

        {/* Receipt card */}
        <Card className="print-receipt">
          <CardContent className="p-6 sm:p-8">
            {/* Receipt header */}
            <div className="flex items-start justify-between mb-8">
              <div>
                <div className="flex items-center gap-2 mb-2">
                  <div className="w-8 h-8 rounded-lg bg-primary flex items-center justify-center">
                    <span className="text-primary-foreground font-display font-bold text-sm">
                      J
                    </span>
                  </div>
                  <span className="font-display font-bold text-xl tracking-tight">
                    JunkOS
                  </span>
                </div>
                <p className="text-sm text-muted-foreground print-subtle">
                  Junk Removal Services
                </p>
              </div>
              <div className="text-right">
                <Badge
                  className={
                    STATUS_COLORS[job.status] ??
                    "bg-muted text-muted-foreground"
                  }
                >
                  {statusLabel(job.status)}
                </Badge>
                <p className="text-xs text-muted-foreground print-subtle mt-2">
                  Order #{shortId}
                </p>
              </div>
            </div>

            <Separator className="mb-6" />

            {/* Booking details grid */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6 mb-6">
              <div>
                <p className="text-xs text-muted-foreground print-subtle uppercase tracking-wider font-medium mb-1">
                  Pickup Address
                </p>
                <p className="text-sm font-medium">{job.address}</p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground print-subtle uppercase tracking-wider font-medium mb-1">
                  Scheduled Date
                </p>
                <p className="text-sm font-medium">
                  {job.scheduled_at
                    ? formatDate(job.scheduled_at)
                    : "Not scheduled"}
                </p>
              </div>
              <div>
                <p className="text-xs text-muted-foreground print-subtle uppercase tracking-wider font-medium mb-1">
                  Order Placed
                </p>
                <p className="text-sm font-medium">
                  {formatDateTime(job.created_at)}
                </p>
              </div>
              {job.completed_at && (
                <div>
                  <p className="text-xs text-muted-foreground print-subtle uppercase tracking-wider font-medium mb-1">
                    Completed
                  </p>
                  <p className="text-sm font-medium">
                    {formatDateTime(job.completed_at)}
                  </p>
                </div>
              )}
            </div>

            <Separator className="mb-6" />

            {/* Items */}
            <div className="mb-6">
              <p className="text-xs text-muted-foreground print-subtle uppercase tracking-wider font-medium mb-3">
                Items
              </p>
              <div className="space-y-2">
                {job.items.map((item, idx) => (
                  <div
                    key={idx}
                    className="flex items-center justify-between text-sm"
                  >
                    <span>{item.category}</span>
                    <span className="text-muted-foreground print-subtle">
                      x{item.quantity}
                    </span>
                  </div>
                ))}
              </div>
            </div>

            {/* Notes */}
            {job.notes && (
              <>
                <div className="mb-6">
                  <p className="text-xs text-muted-foreground print-subtle uppercase tracking-wider font-medium mb-1">
                    Notes
                  </p>
                  <p className="text-sm">{job.notes}</p>
                </div>
              </>
            )}

            <Separator className="mb-6" />

            {/* Price breakdown */}
            <div className="mb-6">
              <p className="text-xs text-muted-foreground print-subtle uppercase tracking-wider font-medium mb-3">
                Price Breakdown
              </p>
              <div className="space-y-2 text-sm">
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground print-subtle">
                    Base Price
                  </span>
                  <span>{formatPrice(job.base_price)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground print-subtle">
                    Item Total
                  </span>
                  <span>{formatPrice(job.item_total)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground print-subtle">
                    Subtotal
                  </span>
                  <span>{formatPrice(subtotal)}</span>
                </div>
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground print-subtle">
                    Service Fee
                  </span>
                  <span>{formatPrice(job.service_fee)}</span>
                </div>
                {hasSurge && (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground print-subtle">
                      Surge Pricing ({job.surge_multiplier}x)
                    </span>
                    <span className="text-orange-600 font-medium">
                      Applied
                    </span>
                  </div>
                )}
                {tipAmount > 0 && (
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground print-subtle">
                      Tip
                    </span>
                    <span>{formatPrice(tipAmount)}</span>
                  </div>
                )}
                <Separator />
                <div className="flex items-center justify-between font-semibold text-base pt-1">
                  <span>Total</span>
                  <span className="text-lg">{formatPrice(grandTotal)}</span>
                </div>
              </div>

              {/* Payment status */}
              {job.payment && (
                <div className="mt-4 flex items-center justify-between text-sm">
                  <span className="text-muted-foreground print-subtle">
                    Payment Status
                  </span>
                  <Badge variant="outline" className="capitalize">
                    {job.payment.payment_status.replace(/_/g, " ")}
                  </Badge>
                </div>
              )}
            </div>

            <Separator className="mb-6" />

            {/* Contractor info */}
            <div className="mb-2">
              <p className="text-xs text-muted-foreground print-subtle uppercase tracking-wider font-medium mb-3">
                Contractor
              </p>
              {hasContractor && job.contractor ? (
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center text-primary font-semibold">
                    {job.contractor.user?.name
                      ? job.contractor.user.name.charAt(0).toUpperCase()
                      : "C"}
                  </div>
                  <div>
                    <p className="text-sm font-semibold">
                      {job.contractor.user?.name ?? "Contractor"}
                    </p>
                    <div className="flex items-center gap-2 text-xs text-muted-foreground print-subtle">
                      {job.contractor.truck_type && (
                        <span>{job.contractor.truck_type}</span>
                      )}
                      <span>&middot;</span>
                      <span>
                        {job.contractor.avg_rating.toFixed(1)} rating
                      </span>
                      <span>&middot;</span>
                      <span>{job.contractor.total_jobs} jobs completed</span>
                    </div>
                  </div>
                </div>
              ) : (
                <p className="text-sm text-muted-foreground print-subtle">
                  No contractor assigned.
                </p>
              )}
            </div>

            {/* Footer */}
            <div className="mt-8 pt-6 border-t border-border text-center">
              <p className="text-xs text-muted-foreground print-subtle">
                Thank you for choosing JunkOS for your junk removal needs.
              </p>
              <p className="text-xs text-muted-foreground print-subtle mt-1">
                Questions? Contact us at support@junkos.com
              </p>
            </div>
          </CardContent>
        </Card>
      </div>
    </>
  );
}
