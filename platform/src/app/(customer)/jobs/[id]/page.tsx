"use client";

import { useEffect, useState, useCallback } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { jobsApi, ratingsApi } from "@/lib/api";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";

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

const CANCELLABLE_STATUSES = ["pending", "confirmed"];

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
// Star icon component
// ---------------------------------------------------------------------------

function StarIcon({
  filled,
  onClick,
  onMouseEnter,
  onMouseLeave,
  interactive = false,
}: {
  filled: boolean;
  onClick?: () => void;
  onMouseEnter?: () => void;
  onMouseLeave?: () => void;
  interactive?: boolean;
}) {
  return (
    <svg
      className={`w-6 h-6 transition-colors ${interactive ? "cursor-pointer" : ""} ${
        filled ? "text-yellow-400 fill-yellow-400" : "text-gray-300"
      }`}
      viewBox="0 0 24 24"
      fill={filled ? "currentColor" : "none"}
      stroke="currentColor"
      strokeWidth={1.5}
      onClick={onClick}
      onMouseEnter={onMouseEnter}
      onMouseLeave={onMouseLeave}
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M11.48 3.499a.562.562 0 011.04 0l2.125 5.111a.563.563 0 00.475.345l5.518.442c.499.04.701.663.321.988l-4.204 3.602a.563.563 0 00-.182.557l1.285 5.385a.562.562 0 01-.84.61l-4.725-2.885a.563.563 0 00-.586 0L6.982 20.54a.562.562 0 01-.84-.61l1.285-5.386a.562.562 0 00-.182-.557l-4.204-3.602a.563.563 0 01.321-.988l5.518-.442a.563.563 0 00.475-.345L11.48 3.5z"
      />
    </svg>
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
      setCancelConfirm(false);
    } catch (err: unknown) {
      const message =
        err instanceof Error ? err.message : "Failed to cancel job.";
      setError(message);
    } finally {
      setCancelling(false);
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
  const hasRating = !!job.rating;
  const hasContractor = !!job.contractor;
  const hasPhotos = job.photos && job.photos.length > 0;
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
                    <div className="flex items-center gap-1 mt-0.5">
                      <div className="flex">
                        {[1, 2, 3, 4, 5].map((star) => (
                          <StarIcon
                            key={star}
                            filled={star <= Math.round(job.contractor!.avg_rating)}
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

        {/* Photos */}
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

        {/* Rating section (only for completed jobs) */}
        {isCompleted && (
          <Card>
            <CardHeader>
              <CardTitle className="font-display text-lg">Rating</CardTitle>
            </CardHeader>
            <CardContent>
              {hasRating && job.rating ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-1">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <StarIcon
                        key={star}
                        filled={star <= job.rating!.stars}
                      />
                    ))}
                    <span className="text-sm font-medium ml-2">
                      {job.rating.stars} / 5
                    </span>
                  </div>
                  {job.rating.comment && (
                    <p className="text-sm text-muted-foreground">
                      &ldquo;{job.rating.comment}&rdquo;
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground">
                    Rated on {formatDate(job.rating.created_at)}
                  </p>
                </div>
              ) : ratingSuccess ? (
                <div className="text-center py-4">
                  <div className="w-12 h-12 rounded-full bg-green-100 flex items-center justify-center mx-auto mb-3">
                    <svg
                      className="w-6 h-6 text-green-600"
                      fill="none"
                      viewBox="0 0 24 24"
                      strokeWidth={2}
                      stroke="currentColor"
                    >
                      <path
                        strokeLinecap="round"
                        strokeLinejoin="round"
                        d="M4.5 12.75l6 6 9-13.5"
                      />
                    </svg>
                  </div>
                  <p className="font-medium text-sm">
                    Thank you for your feedback!
                  </p>
                  <p className="text-muted-foreground text-xs mt-1">
                    Your rating has been submitted.
                  </p>
                </div>
              ) : (
                <div className="space-y-4">
                  <p className="text-sm text-muted-foreground">
                    How was your experience? Rate your pickup.
                  </p>

                  {/* Star selector */}
                  <div className="flex items-center gap-1">
                    {[1, 2, 3, 4, 5].map((star) => (
                      <StarIcon
                        key={star}
                        filled={
                          star <= (ratingHover > 0 ? ratingHover : ratingStars)
                        }
                        interactive
                        onClick={() => setRatingStars(star)}
                        onMouseEnter={() => setRatingHover(star)}
                        onMouseLeave={() => setRatingHover(0)}
                      />
                    ))}
                    {ratingStars > 0 && (
                      <span className="text-sm text-muted-foreground ml-2">
                        {ratingStars} / 5
                      </span>
                    )}
                  </div>

                  {/* Comment */}
                  <div>
                    <label
                      htmlFor="rating-comment"
                      className="text-sm text-muted-foreground block mb-1.5"
                    >
                      Comment (optional)
                    </label>
                    <textarea
                      id="rating-comment"
                      rows={3}
                      value={ratingComment}
                      onChange={(e) => setRatingComment(e.target.value)}
                      placeholder="Share your experience..."
                      className="w-full rounded-lg border border-input bg-background px-3 py-2 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 resize-none"
                    />
                  </div>

                  {ratingError && (
                    <p className="text-destructive text-sm">{ratingError}</p>
                  )}

                  <Button
                    onClick={handleRatingSubmit}
                    disabled={ratingStars === 0 || ratingSubmitting}
                    size="sm"
                  >
                    {ratingSubmitting ? "Submitting..." : "Submit Rating"}
                  </Button>
                </div>
              )}
            </CardContent>
          </Card>
        )}

        {/* Cancel button (only for pending/confirmed) */}
        {canCancel && (
          <div className="pt-2">
            {cancelConfirm ? (
              <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-4">
                <p className="text-sm font-medium text-destructive mb-3">
                  Are you sure you want to cancel this job?
                </p>
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
              <Button
                variant="outline"
                className="text-destructive border-destructive/30 hover:bg-destructive/5"
                onClick={handleCancel}
              >
                Cancel Job
              </Button>
            )}
          </div>
        )}
      </div>
    </div>
  );
}
