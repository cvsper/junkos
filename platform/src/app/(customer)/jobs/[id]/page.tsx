"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { jobsApi, ratingsApi } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { ChatPanel } from "@/components/chat/chat-panel";
import BeforeAfterSlider from "@/components/photos/before-after-slider";

// ---------------------------------------------------------------------------
// Local types (mirrors backend response shape)
// ---------------------------------------------------------------------------

interface JobPayment {
  amount: number;
  payment_status: string;
  tip_amount: number;
}

interface JobRating {
  stars: number;
  comment: string | null;
  created_at: string;
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
  before_photos: string[];
  after_photos: string[];
  proof_submitted_at: string | null;
  total_price: number;
  base_price: number;
  item_total: number;
  service_fee: number;
  surge_multiplier: number;
  notes: string | null;
  scheduled_at: string | null;
  created_at: string;
  completed_at: string | null;
  cancelled_at?: string | null;
  cancellation_fee?: number;
  rescheduled_count?: number;
  payment?: JobPayment | null;
  rating?: JobRating | null;
  contractor?: JobContractor | null;
}

// ---------------------------------------------------------------------------
// Constants
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

const ACTIVE_STATUSES = [
  "pending",
  "confirmed",
  "assigned",
  "en_route",
  "arrived",
  "in_progress",
];

const CANCELLABLE_STATUSES = ["pending", "confirmed", "assigned"];

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

/** Estimate the cancellation fee based on time until scheduled pickup. */
function estimateCancellationFee(scheduledAt: string | null | undefined): number {
  if (!scheduledAt) return 0;
  const now = new Date();
  const scheduled = new Date(scheduledAt);
  const hoursUntil = (scheduled.getTime() - now.getTime()) / (1000 * 60 * 60);
  if (hoursUntil < 2) return 50;
  if (hoursUntil < 24) return 25;
  return 0;
}

// ---------------------------------------------------------------------------
// Star rating labels
// ---------------------------------------------------------------------------

const RATING_LABELS: Record<number, string> = {
  1: "Poor",
  2: "Fair",
  3: "Good",
  4: "Great",
  5: "Excellent",
};

// ---------------------------------------------------------------------------
// Star icon component (with animations)
// ---------------------------------------------------------------------------

function StarIcon({
  filled,
  onClick,
  onMouseEnter,
  onMouseLeave,
  interactive = false,
  size = "md",
  animated = false,
  index = 0,
}: {
  filled: boolean;
  onClick?: () => void;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
  interactive?: boolean;
  size?: "sm" | "md" | "lg";
  animated?: boolean;
  index?: number;
}) {
  const sizeClasses = {
    sm: "w-5 h-5",
    md: "w-7 h-7",
    lg: "w-9 h-9",
  };

  return (
    <button
      type="button"
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
      disabled={!interactive}
      className={`
        relative inline-flex items-center justify-center p-0.5 border-0 bg-transparent
        transition-transform duration-200 ease-out
        ${interactive ? "cursor-pointer hover:scale-125 active:scale-95" : "cursor-default"}
        ${animated ? "animate-[star-pop_0.3s_ease-out]" : ""}
        focus:outline-none focus-visible:outline-none
        disabled:opacity-100
      `}
      style={animated ? { animationDelay: `${index * 60}ms` } : undefined}
      tabIndex={interactive ? 0 : -1}
    >
      {/* Glow effect behind filled stars */}
      {filled && (
        <span
          className={`absolute inset-0 rounded-full bg-amber-400/20 blur-sm transition-opacity duration-300 ${
            filled ? "opacity-100" : "opacity-0"
          }`}
        />
      )}
      <svg
        className={`
          ${sizeClasses[size]}
          transition-all duration-200 ease-out relative
          ${filled
            ? "text-amber-400 drop-shadow-[0_1px_2px_rgba(251,191,36,0.4)]"
            : interactive
              ? "text-gray-300 hover:text-amber-200"
              : "text-gray-300"
          }
        `}
        viewBox="0 0 24 24"
        fill={filled ? "currentColor" : "none"}
        stroke="currentColor"
        strokeWidth={filled ? 0 : 1.5}
      >
        <path
          strokeLinecap="round"
          strokeLinejoin="round"
          d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"
        />
      </svg>
    </button>
  );
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function JobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  const [job, setJob] = useState<JobDetail | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Cancel state
  const [cancelConfirm, setCancelConfirm] = useState(false);
  const [cancelling, setCancelling] = useState(false);
  const [cancelFeeReturned, setCancelFeeReturned] = useState<number | null>(null);

  // Reschedule state
  const [rescheduleOpen, setRescheduleOpen] = useState(false);
  const [rescheduleDate, setRescheduleDate] = useState("");
  const [rescheduleTime, setRescheduleTime] = useState("");
  const [rescheduling, setRescheduling] = useState(false);
  const [rescheduleError, setRescheduleError] = useState<string | null>(null);

  // Chat state
  const [chatOpen, setChatOpen] = useState(false);

  // Rating state
  const [ratingStars, setRatingStars] = useState(0);
  const [ratingHover, setRatingHover] = useState(0);
  const [ratingComment, setRatingComment] = useState("");
  const [ratingSubmitting, setRatingSubmitting] = useState(false);
  const [ratingSuccess, setRatingSuccess] = useState(false);
  const [ratingError, setRatingError] = useState<string | null>(null);

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

  // Cancel handler
  async function handleCancel() {
    if (!cancelConfirm) {
      setCancelConfirm(true);
      return;
    }
    setCancelling(true);
    try {
      const res = await jobsApi.cancel(id);
      if (res.job) {
        setJob(res.job);
      }
      if (res.cancellation_fee !== undefined) {
        setCancelFeeReturned(res.cancellation_fee);
      }
      setCancelConfirm(false);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to cancel job.";
      setError(message);
    } finally {
      setCancelling(false);
    }
  }

  // Reschedule handler
  async function handleReschedule() {
    if (!rescheduleDate || !rescheduleTime) {
      setRescheduleError("Please select both a date and time.");
      return;
    }
    setRescheduling(true);
    setRescheduleError(null);
    try {
      const res = await jobsApi.reschedule(id, {
        scheduled_date: rescheduleDate,
        scheduled_time: rescheduleTime,
      });
      if (res.job) {
        setJob(res.job);
      }
      setRescheduleOpen(false);
      setRescheduleDate("");
      setRescheduleTime("");
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to reschedule job.";
      setRescheduleError(message);
    } finally {
      setRescheduling(false);
    }
  }

  // Rating submit handler
  async function handleRatingSubmit() {
    if (ratingStars === 0) return;
    setRatingSubmitting(true);
    setRatingError(null);
    try {
      await ratingsApi.submit(
        id,
        ratingStars,
        ratingComment.trim() || undefined
      );
      setRatingSuccess(true);
      // Update job state to reflect the new rating
      if (job) {
        setJob({
          ...job,
          rating: {
            stars: ratingStars,
            comment: ratingComment.trim() || null,
            created_at: new Date().toISOString(),
          },
        });
      }
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to submit rating.";
      setRatingError(message);
    } finally {
      setRatingSubmitting(false);
    }
  }

  const shortId = id ? id.slice(0, 8) : "";

  // Loading state
  if (loading) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8 sm:py-12">
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
            Loading job details...
          </span>
        </div>
      </div>
    );
  }

  // Error state
  if (error && !job) {
    return (
      <div className="max-w-3xl mx-auto px-4 py-8 sm:py-12">
        <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-6">
          <Link
            href="/dashboard"
            className="hover:text-foreground transition-colors"
          >
            My Jobs
          </Link>
          <span>/</span>
          <span className="text-foreground">Job #{shortId}</span>
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

  const canCancel = CANCELLABLE_STATUSES.includes(job.status);
  const isCompleted = job.status === "completed";
  const isActive = ACTIVE_STATUSES.includes(job.status);
  const hasRating = !!job.rating;
  const hasContractor = !!job.contractor;
  const canChat = hasContractor && ["assigned", "en_route", "arrived", "in_progress"].includes(job.status);
  const hasPhotos = job.photos && job.photos.length > 0;
  const hasBeforeAfterPhotos =
    (job.before_photos && job.before_photos.length > 0) ||
    (job.after_photos && job.after_photos.length > 0);
  const hasSurge = job.surge_multiplier > 1.0;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 sm:py-12">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-6">
        <Link
          href="/dashboard"
          className="hover:text-foreground transition-colors"
        >
          My Jobs
        </Link>
        <span>/</span>
        <span className="text-foreground">Job #{shortId}</span>
      </nav>

      {/* Header */}
      <div className="flex items-start justify-between mb-8">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Job #{shortId}
          </h1>
          <p className="text-muted-foreground mt-1">
            Created {formatDateTime(job.created_at)}
          </p>
          {/* Action links */}
          <div className="flex items-center gap-3 mt-3">
            {isActive && (
              <Link href={`/track/${id}`}>
                <Button variant="outline" size="sm" className="gap-2">
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
                      d="M15 10.5a3 3 0 11-6 0 3 3 0 016 0z"
                    />
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M19.5 10.5c0 7.142-7.5 11.25-7.5 11.25S4.5 17.642 4.5 10.5a7.5 7.5 0 1115 0z"
                    />
                  </svg>
                  Live Tracking
                </Button>
              </Link>
            )}
            {isCompleted && (
              <Link href={`/jobs/${id}/receipt`}>
                <Button variant="outline" size="sm" className="gap-2">
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
                      d="M19.5 14.25v-2.625a3.375 3.375 0 00-3.375-3.375h-1.5A1.125 1.125 0 0113.5 7.125v-1.5a3.375 3.375 0 00-3.375-3.375H8.25m2.25 0H5.625c-.621 0-1.125.504-1.125 1.125v17.25c0 .621.504 1.125 1.125 1.125h12.75c.621 0 1.125-.504 1.125-1.125V11.25a9 9 0 00-9-9z"
                    />
                  </svg>
                  View Receipt
                </Button>
              </Link>
            )}
            {canChat && (
              <Button
                variant="outline"
                size="sm"
                className="gap-2"
                onClick={() => setChatOpen(true)}
              >
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
                    d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"
                  />
                </svg>
                Chat with Driver
              </Button>
            )}
          </div>
        </div>
        <Badge
          className={
            STATUS_COLORS[job.status] ?? "bg-muted text-muted-foreground"
          }
        >
          {statusLabel(job.status)}
        </Badge>
      </div>

      {/* Error banner (for inline errors like cancel failure) */}
      {error && (
        <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4 mb-6 text-center">
          <p className="text-destructive text-sm">{error}</p>
        </div>
      )}

      <div className="space-y-6">
        {/* Pickup Details */}
        <Card>
          <CardHeader>
            <CardTitle className="font-display text-lg">
              Pickup Details
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
              <div>
                <span className="text-muted-foreground">Address</span>
                <p className="font-medium mt-0.5">{job.address}</p>
              </div>
              <div>
                <span className="text-muted-foreground">Scheduled Date</span>
                <p className="font-medium mt-0.5">
                  {job.scheduled_at
                    ? formatDateTime(job.scheduled_at)
                    : "Not scheduled"}
                </p>
              </div>
            </div>

            <Separator />

            {/* Items list */}
            <div>
              <span className="text-sm text-muted-foreground">Items</span>
              <ul className="mt-2 space-y-1.5">
                {job.items.map((item, idx) => (
                  <li
                    key={idx}
                    className="flex items-center justify-between text-sm"
                  >
                    <span className="font-medium">{item.category}</span>
                    <span className="text-muted-foreground">
                      x{item.quantity}
                    </span>
                  </li>
                ))}
              </ul>
            </div>

            {/* Notes */}
            {job.notes && (
              <>
                <Separator />
                <div>
                  <span className="text-sm text-muted-foreground">Notes</span>
                  <p className="text-sm mt-1">{job.notes}</p>
                </div>
              </>
            )}
          </CardContent>
        </Card>

        {/* Pricing */}
        <Card>
          <CardHeader>
            <CardTitle className="font-display text-lg">Pricing</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="space-y-2 text-sm">
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Base Price</span>
                <span>{formatPrice(job.base_price)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Item Total</span>
                <span>{formatPrice(job.item_total)}</span>
              </div>
              <div className="flex items-center justify-between">
                <span className="text-muted-foreground">Service Fee</span>
                <span>{formatPrice(job.service_fee)}</span>
              </div>
              {hasSurge && (
                <div className="flex items-center justify-between">
                  <span className="text-muted-foreground">
                    Surge ({job.surge_multiplier}x)
                  </span>
                  <span className="text-orange-600 font-medium">Applied</span>
                </div>
              )}
              <Separator />
              <div className="flex items-center justify-between font-semibold text-base">
                <span>Total</span>
                <span>{formatPrice(job.total_price)}</span>
              </div>

              {/* Payment status */}
              {job.payment && (
                <>
                  <Separator />
                  <div className="flex items-center justify-between">
                    <span className="text-muted-foreground">
                      Payment Status
                    </span>
                    <Badge variant="outline" className="capitalize">
                      {job.payment.payment_status.replace(/_/g, " ")}
                    </Badge>
                  </div>
                  {job.payment.tip_amount > 0 && (
                    <div className="flex items-center justify-between">
                      <span className="text-muted-foreground">Tip</span>
                      <span>{formatPrice(job.payment.tip_amount)}</span>
                    </div>
                  )}
                </>
              )}
            </div>
          </CardContent>
        </Card>

        {/* Contractor */}
        <Card>
          <CardHeader>
            <CardTitle className="font-display text-lg">Contractor</CardTitle>
          </CardHeader>
          <CardContent>
            {hasContractor && job.contractor ? (
              <div className="space-y-3">
                <div className="flex items-center gap-4">
                  {/* Avatar placeholder */}
                  <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary font-semibold text-lg">
                    {job.contractor.user?.name
                      ? job.contractor.user.name.charAt(0).toUpperCase()
                      : "C"}
                  </div>
                  <div>
                    <p className="font-semibold">
                      {job.contractor.user?.name ?? "Contractor"}
                    </p>
                    {job.contractor.truck_type && (
                      <p className="text-sm text-muted-foreground">
                        {job.contractor.truck_type}
                      </p>
                    )}
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div>
                    <span className="text-muted-foreground">Rating</span>
                    <div className="flex items-center gap-0.5 mt-0.5">
                      <div className="flex">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <StarIcon
                            key={star}
                            filled={star <= Math.round(job.contractor!.avg_rating)}
                            size="sm"
                          />
                        ))}
                      </div>
                      <span className="text-sm font-medium ml-1">
                        {job.contractor.avg_rating.toFixed(1)}
                      </span>
                    </div>
                  </div>
                  <div>
                    <span className="text-muted-foreground">Total Jobs</span>
                    <p className="font-medium mt-0.5">
                      {job.contractor.total_jobs}
                    </p>
                  </div>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-3 py-2">
                <div className="w-10 h-10 rounded-full bg-muted flex items-center justify-center">
                  <svg
                    className="w-5 h-5 text-muted-foreground"
                    fill="none"
                    viewBox="0 0 24 24"
                    strokeWidth={1.5}
                    stroke="currentColor"
                  >
                    <path
                      strokeLinecap="round"
                      strokeLinejoin="round"
                      d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"
                    />
                  </svg>
                </div>
                <p className="text-muted-foreground text-sm">
                  Awaiting contractor assignment
                </p>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Original booking photos (hidden when before/after photos exist to avoid duplication) */}
        {!hasBeforeAfterPhotos && (
          <Card>
            <CardHeader>
              <CardTitle className="font-display text-lg">Photos</CardTitle>
            </CardHeader>
            <CardContent>
              {hasPhotos ? (
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {job.photos.map((url, idx) => (
                    <div
                      key={idx}
                      className="aspect-square rounded-lg overflow-hidden border border-border bg-muted"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={url}
                        alt={`Job photo ${idx + 1}`}
                        className="w-full h-full object-cover"
                      />
                    </div>
                  ))}
                </div>
              ) : (
                <p className="text-muted-foreground text-sm">
                  No photos uploaded.
                </p>
              )}
            </CardContent>
          </Card>
        )}

        {/* Before/After Photos - Proof of Completion */}
        {hasBeforeAfterPhotos && (
          <Card>
            <CardHeader>
              <CardTitle className="font-display text-lg">Photos</CardTitle>
            </CardHeader>
            <CardContent>
              <BeforeAfterSlider
                beforePhotos={job.before_photos || []}
                afterPhotos={job.after_photos || []}
              />
            </CardContent>
          </Card>
        )}

        {/* Rating section (only for completed jobs) */}
        {isCompleted && (
          <Card className="overflow-hidden">
            <CardHeader className="bg-gradient-to-r from-amber-50 to-orange-50 dark:from-amber-950/20 dark:to-orange-950/20 border-b">
              <CardTitle className="font-display text-lg flex items-center gap-2">
                <svg className="w-5 h-5 text-amber-500" viewBox="0 0 24 24" fill="currentColor">
                  <path d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z" />
                </svg>
                Your Rating
              </CardTitle>
            </CardHeader>
            <CardContent className="pt-6">
              {hasRating && job.rating ? (
                /* ---- Read-only: already rated ---- */
                <div className="space-y-4">
                  <div className="flex flex-col items-center text-center">
                    <div className="flex items-center gap-0.5 mb-2">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <StarIcon
                          key={star}
                          filled={star <= job.rating!.stars}
                          size="lg"
                          animated
                          index={star}
                        />
                      ))}
                    </div>
                    <p className="text-lg font-semibold text-foreground">
                      {RATING_LABELS[job.rating.stars] ?? ""}{" "}
                      <span className="text-muted-foreground font-normal text-sm">
                        ({job.rating.stars}/5)
                      </span>
                    </p>
                  </div>
                  {job.rating.comment && (
                    <div className="bg-muted/50 rounded-lg px-4 py-3 mx-auto max-w-md">
                      <p className="text-sm text-muted-foreground italic leading-relaxed">
                        &ldquo;{job.rating.comment}&rdquo;
                      </p>
                    </div>
                  )}
                  <p className="text-xs text-muted-foreground text-center">
                    Rated on {formatDate(job.rating.created_at)}
                  </p>
                </div>
              ) : ratingSuccess ? (
                /* ---- Success state after submission ---- */
                <div className="text-center py-6 animate-in fade-in-0 zoom-in-95 duration-500">
                  <div className="w-16 h-16 rounded-full bg-green-100 dark:bg-green-900/30 flex items-center justify-center mx-auto mb-4 animate-in zoom-in-50 duration-300">
                    <svg
                      className="w-8 h-8 text-green-600 dark:text-green-400"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={2.5}
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M4.5 12.75l6 6 9-13.5"
                      />
                    </svg>
                  </div>
                  <div className="flex items-center justify-center gap-0.5 mb-3">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <StarIcon
                        key={star}
                        filled={star <= ratingStars}
                        size="md"
                        animated
                        index={star}
                      />
                    ))}
                  </div>
                  <p className="font-semibold text-base">
                    Thank you for your feedback!
                  </p>
                  <p className="text-muted-foreground text-sm mt-1">
                    Your {ratingStars}-star rating has been submitted.
                  </p>
                </div>
              ) : (
                /* ---- Rating form ---- */
                <div className="space-y-5">
                  <div className="text-center">
                    <p className="text-sm text-muted-foreground mb-1">
                      How was your experience?
                    </p>
                    <p className="text-xs text-muted-foreground/70">
                      Tap a star to rate your pickup
                    </p>
                  </div>

                  {/* Star selector */}
                  <div className="flex flex-col items-center gap-2">
                    <div className="flex items-center gap-0.5">
                      {[1, 2, 3, 4, 5].map((star) => (
                        <StarIcon
                          key={star}
                          filled={
                            star <= (ratingHover > 0 ? ratingHover : ratingStars)
                          }
                          interactive
                          size="lg"
                          onClick={() => setRatingStars(star)}
                          onMouseEnter={() => setRatingHover(star)}
                          onMouseLeave={() => setRatingHover(0)}
                        />
                      ))}
                    </div>
                    <div className="h-6 flex items-center">
                      {(ratingHover > 0 || ratingStars > 0) && (
                        <span
                          className="text-sm font-medium text-amber-600 dark:text-amber-400 animate-in fade-in-0 duration-200"
                        >
                          {RATING_LABELS[ratingHover > 0 ? ratingHover : ratingStars]}
                        </span>
                      )}
                    </div>
                  </div>

                  {/* Comment */}
                  <div>
                    <label
                      htmlFor="rating-comment"
                      className="text-sm text-muted-foreground block mb-1.5"
                    >
                      Comment <span className="text-muted-foreground/60">(optional)</span>
                    </label>
                    <textarea
                      id="rating-comment"
                      rows={3}
                      value={ratingComment}
                      onChange={(e) => setRatingComment(e.target.value)}
                      placeholder="Tell us about your experience..."
                      className="w-full rounded-lg border border-input bg-background px-3 py-2.5 text-sm placeholder:text-muted-foreground/50 focus:outline-none focus:ring-2 focus:ring-amber-400/40 focus:border-amber-400 resize-none transition-all duration-200"
                      maxLength={500}
                    />
                    {ratingComment.length > 0 && (
                      <p className="text-xs text-muted-foreground/50 mt-1 text-right">
                        {ratingComment.length}/500
                      </p>
                    )}
                  </div>

                  {ratingError && (
                    <div className="rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2">
                      <p className="text-destructive text-sm">{ratingError}</p>
                    </div>
                  )}

                  <Button
                    onClick={handleRatingSubmit}
                    disabled={ratingStars === 0 || ratingSubmitting}
                    className="w-full bg-amber-500 hover:bg-amber-600 text-white transition-all duration-200 disabled:opacity-40"
                    size="default"
                  >
                    {ratingSubmitting ? (
                      <span className="flex items-center gap-2">
                        <svg className="w-4 h-4 animate-spin" viewBox="0 0 24 24" fill="none">
                          <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                          <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4z" />
                        </svg>
                        Submitting...
                      </span>
                    ) : ratingStars === 0 ? (
                      "Select a rating"
                    ) : (
                      `Submit ${ratingStars}-Star Rating`
                    )}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Cancel & Reschedule actions (only for cancellable statuses) */}
        {canCancel && (
          <div className="pt-2 space-y-4">
            {/* Reschedule modal */}
            {rescheduleOpen && (
              <Card className="border-primary/30">
                <CardHeader className="pb-3">
                  <CardTitle className="font-display text-lg flex items-center gap-2">
                    <svg
                      className="w-5 h-5 text-primary"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={2}
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
                      />
                    </svg>
                    Reschedule Job
                  </CardTitle>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label
                        htmlFor="reschedule-date"
                        className="text-sm text-muted-foreground block mb-1.5"
                      >
                        New Date
                      </label>
                      <input
                        id="reschedule-date"
                        type="date"
                        value={rescheduleDate}
                        onChange={(e) => setRescheduleDate(e.target.value)}
                        min={new Date().toISOString().split("T")[0]}
                        className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-all duration-200"
                      />
                    </div>
                    <div>
                      <label
                        htmlFor="reschedule-time"
                        className="text-sm text-muted-foreground block mb-1.5"
                      >
                        New Time
                      </label>
                      <input
                        id="reschedule-time"
                        type="time"
                        value={rescheduleTime}
                        onChange={(e) => setRescheduleTime(e.target.value)}
                        className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-all duration-200"
                      />
                    </div>
                  </div>

                  {rescheduleError && (
                    <div className="rounded-md bg-destructive/10 border border-destructive/20 px-3 py-2">
                      <p className="text-destructive text-sm">{rescheduleError}</p>
                    </div>
                  )}

                  <div className="flex items-center gap-3">
                    <Button
                      size="sm"
                      onClick={handleReschedule}
                      disabled={rescheduling || !rescheduleDate || !rescheduleTime}
                    >
                      {rescheduling ? "Rescheduling..." : "Confirm New Time"}
                    </Button>
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => {
                        setRescheduleOpen(false);
                        setRescheduleError(null);
                      }}
                      disabled={rescheduling}
                    >
                      Cancel
                    </Button>
                  </div>
                </CardContent>
              </Card>
            )}

            {/* Cancel confirmation dialog */}
            {cancelConfirm ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4">
                <p className="text-sm font-medium text-destructive mb-2">
                  Are you sure you want to cancel this job?
                </p>
                {(() => {
                  const fee = estimateCancellationFee(job.scheduled_at);
                  return fee > 0 ? (
                    <p className="text-sm text-destructive/80 mb-3">
                      A cancellation fee of <span className="font-semibold">{formatPrice(fee)}</span> will
                      apply because this job is scheduled within{" "}
                      {fee === 50 ? "2 hours" : "24 hours"}.
                    </p>
                  ) : (
                    <p className="text-sm text-muted-foreground mb-3">
                      No cancellation fee will be charged.
                    </p>
                  );
                })()}
                <div className="flex items-center gap-3">
                  <Button
                    variant="destructive"
                    size="sm"
                    onClick={handleCancel}
                    disabled={cancelling}
                  >
                    {cancelling ? "Cancelling..." : "Yes, Cancel Job"}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => setCancelConfirm(false)}
                    disabled={cancelling}
                  >
                    Keep Job
                  </Button>
                </div>
              </div>
            ) : (
              <div className="flex items-center gap-3">
                <Button
                  variant="outline"
                  className="gap-2"
                  onClick={() => setRescheduleOpen(!rescheduleOpen)}
                >
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
                      d="M6.75 3v2.25M17.25 3v2.25M3 18.75V7.5a2.25 2.25 0 012.25-2.25h13.5A2.25 2.25 0 0121 7.5v11.25m-18 0A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75m-18 0v-7.5A2.25 2.25 0 015.25 9h13.5A2.25 2.25 0 0121 11.25v7.5"
                    />
                  </svg>
                  Reschedule
                </Button>
                <Button
                  variant="outline"
                  className="text-destructive border-destructive/30 hover:bg-destructive/5 gap-2"
                  onClick={handleCancel}
                >
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
                      d="M6 18L18 6M6 6l12 12"
                    />
                  </svg>
                  Cancel Job
                </Button>
              </div>
            )}
          </div>
        )}

        {/* Cancellation info (shown when job is already cancelled) */}
        {job.status === "cancelled" && (job.cancellation_fee ?? 0) > 0 && (
          <div className="rounded-lg border border-red-200 bg-red-50 dark:bg-red-950/20 p-4">
            <p className="text-sm text-red-800 dark:text-red-300">
              This job was cancelled with a{" "}
              <span className="font-semibold">
                {formatPrice(job.cancellation_fee ?? 0)}
              </span>{" "}
              cancellation fee.
            </p>
          </div>
        )}
      </div>

      {/* Chat panel (slides in from right) */}
      {canChat && (
        <ChatPanel
          jobId={id}
          isOpen={chatOpen}
          onClose={() => setChatOpen(false)}
          userRole="customer"
        />
      )}
    </div>
  );
}
