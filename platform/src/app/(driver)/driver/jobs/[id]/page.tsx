"use client";

import { useEffect, useState, useCallback } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import {
  ArrowLeft,
  MapPin,
  User,
  Phone,
  CalendarDays,
  Package,
  StickyNote,
  ImageIcon,
  DollarSign,
  RefreshCw,
  AlertCircle,
  Loader2,
  CheckCircle2,
  X,
} from "lucide-react";
import { driverApi, ApiError } from "@/lib/api";
import type { DriverJob } from "@/types";

// ---------------------------------------------------------------------------
// Status badge palette (shared with jobs list)
// ---------------------------------------------------------------------------

const STATUS_BADGES: Record<string, string> = {
  pending: "bg-gray-100 text-gray-700",
  confirmed: "bg-blue-100 text-blue-700",
  assigned: "bg-indigo-100 text-indigo-700",
  en_route: "bg-amber-100 text-amber-700",
  arrived: "bg-orange-100 text-orange-700",
  in_progress: "bg-purple-100 text-purple-700",
  completed: "bg-emerald-100 text-emerald-700",
  cancelled: "bg-red-100 text-red-700",
};

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function statusLabel(s: string) {
  return s
    .replace(/_/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatDate(iso: string | null) {
  if (!iso) return "Not scheduled";
  const d = new Date(iso);
  return d.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/** Statuses where the driver can accept the job */
const ACCEPTABLE_STATUSES = new Set([
  "pending",
  "confirmed",
  "assigned",
  "delegating",
]);

/** Statuses that are actively in-progress for this driver */
const ACTIVE_STATUSES = new Set([
  "en_route",
  "arrived",
  "in_progress",
]);

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function DriverJobDetailPage() {
  const params = useParams();
  const router = useRouter();
  const jobId = params.id as string;

  const [job, setJob] = useState<DriverJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Confirmation modal state
  const [modalAction, setModalAction] = useState<"accept" | "decline" | null>(null);
  const [actionLoading, setActionLoading] = useState(false);

  // ---- Fetch job ----
  const loadJob = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await driverApi.getJob(jobId);
      setJob(res.job);
    } catch (err) {
      setError(
        err instanceof ApiError
          ? err.message
          : "Failed to load job details"
      );
    } finally {
      setLoading(false);
    }
  }, [jobId]);

  useEffect(() => {
    loadJob();
  }, [loadJob]);

  // ---- Actions ----
  const handleConfirmAction = async () => {
    if (!modalAction || !job) return;
    setActionLoading(true);
    try {
      if (modalAction === "accept") {
        await driverApi.acceptJob(job.id);
        router.push(`/driver/jobs/${job.id}/active`);
      } else {
        await driverApi.declineJob(job.id);
        router.push("/driver/jobs");
      }
    } catch {
      // close modal on error so user can retry
      setModalAction(null);
    } finally {
      setActionLoading(false);
    }
  };

  // ---- Determine which actions to show ----
  const canAccept = job ? ACCEPTABLE_STATUSES.has(job.status) : false;
  const isActive = job ? ACTIVE_STATUSES.has(job.status) : false;
  const isCompleted = job?.status === "completed";

  // ===========================================================================
  // Loading skeleton
  // ===========================================================================
  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center gap-3">
          <div className="h-5 w-5 bg-muted rounded animate-pulse" />
          <div className="h-5 bg-muted rounded w-20 animate-pulse" />
        </div>
        <div className="rounded-xl border border-border bg-card p-6 space-y-5 animate-pulse">
          <div className="flex items-center justify-between">
            <div className="h-7 bg-muted rounded-full w-24" />
            <div className="h-8 bg-muted rounded w-20" />
          </div>
          <div className="h-px bg-border" />
          <div className="space-y-4">
            <div className="h-4 bg-muted rounded w-3/4" />
            <div className="h-4 bg-muted rounded w-1/2" />
            <div className="h-4 bg-muted rounded w-2/3" />
          </div>
          <div className="h-px bg-border" />
          <div className="space-y-3">
            <div className="h-4 bg-muted rounded w-32" />
            <div className="h-4 bg-muted rounded w-48" />
          </div>
          <div className="h-px bg-border" />
          <div className="flex gap-3">
            <div className="h-10 bg-muted rounded-lg flex-1" />
            <div className="h-10 bg-muted rounded-lg flex-1" />
          </div>
        </div>
      </div>
    );
  }

  // ===========================================================================
  // Error state
  // ===========================================================================
  if (error || !job) {
    return (
      <div className="space-y-6">
        <Link
          href="/driver/jobs"
          className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
        >
          <ArrowLeft className="w-4 h-4" />
          Back to Jobs
        </Link>
        <div className="rounded-xl border border-red-200 bg-red-50 p-8 flex flex-col items-center text-center">
          <AlertCircle className="h-10 w-10 text-red-400 mb-3" />
          <p className="text-red-700 font-medium mb-1">
            {error || "Job not found"}
          </p>
          <button
            onClick={loadJob}
            className="mt-4 inline-flex items-center gap-2 text-sm bg-red-100 text-red-700 px-4 py-2 rounded-lg hover:bg-red-200 transition-colors font-medium"
          >
            <RefreshCw className="w-4 h-4" />
            Retry
          </button>
        </div>
      </div>
    );
  }

  // ===========================================================================
  // Render
  // ===========================================================================
  return (
    <div className="space-y-6">
      {/* Back link */}
      <Link
        href="/driver/jobs"
        className="inline-flex items-center gap-1.5 text-sm text-muted-foreground hover:text-foreground transition-colors"
      >
        <ArrowLeft className="w-4 h-4" />
        Back to Jobs
      </Link>

      {/* ---- Main card ---- */}
      <div className="rounded-xl border border-border bg-card">
        {/* Header: status + price */}
        <div className="px-4 sm:px-6 py-4 border-b border-border flex flex-col sm:flex-row sm:items-center justify-between gap-3">
          <span
            className={`inline-block px-3 py-1 rounded-full text-xs font-medium w-fit ${
              STATUS_BADGES[job.status] || "bg-gray-100 text-gray-700"
            }`}
          >
            {statusLabel(job.status)}
          </span>
          <div className="flex items-center gap-2">
            <DollarSign className="w-5 h-5 text-emerald-600" />
            <span className="text-2xl font-bold text-emerald-700">
              ${job.total_price.toFixed(2)}
            </span>
          </div>
        </div>

        <div className="px-4 sm:px-6 py-5 space-y-5">
          {/* ---- Address ---- */}
          <div className="flex items-start gap-3">
            <MapPin className="w-5 h-5 text-muted-foreground mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                Pickup Address
              </p>
              <p className="text-sm font-medium">
                {job.address}
                {job.city ? `, ${job.city}` : ""}
              </p>
            </div>
          </div>

          {/* ---- Customer ---- */}
          <div className="flex items-start gap-3">
            <User className="w-5 h-5 text-muted-foreground mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                Customer
              </p>
              <p className="text-sm font-medium">
                {job.customer_name || "N/A"}
              </p>
            </div>
          </div>

          {/* ---- Phone ---- */}
          {job.customer_phone && (
            <div className="flex items-start gap-3">
              <Phone className="w-5 h-5 text-muted-foreground mt-0.5 shrink-0" />
              <div>
                <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                  Phone
                </p>
                <a
                  href={`tel:${job.customer_phone}`}
                  className="text-sm font-medium text-primary hover:underline"
                >
                  {job.customer_phone}
                </a>
              </div>
            </div>
          )}

          {/* ---- Scheduled date ---- */}
          <div className="flex items-start gap-3">
            <CalendarDays className="w-5 h-5 text-muted-foreground mt-0.5 shrink-0" />
            <div>
              <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                Scheduled
              </p>
              <p className="text-sm font-medium">
                {formatDate(job.scheduled_at)}
              </p>
            </div>
          </div>

          {/* ---- Items ---- */}
          {job.items && job.items.length > 0 && (
            <>
              <div className="h-px bg-border" />
              <div className="flex items-start gap-3">
                <Package className="w-5 h-5 text-muted-foreground mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    Items
                  </p>
                  <div className="space-y-1.5">
                    {job.items.map((item, idx) => (
                      <div
                        key={idx}
                        className="flex items-center justify-between text-sm py-1.5 px-3 rounded-lg bg-muted/50"
                      >
                        <span className="font-medium capitalize">
                          {item.category}
                        </span>
                        <span className="text-muted-foreground">
                          x{item.quantity}
                        </span>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}

          {/* ---- Photos ---- */}
          {job.photos && job.photos.length > 0 && (
            <>
              <div className="h-px bg-border" />
              <div className="flex items-start gap-3">
                <ImageIcon className="w-5 h-5 text-muted-foreground mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                    Photos
                  </p>
                  <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                    {job.photos.map((url, idx) => (
                      <a
                        key={idx}
                        href={url}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="aspect-square rounded-lg overflow-hidden border border-border hover:opacity-80 transition-opacity"
                      >
                        <img
                          src={url}
                          alt={`Job photo ${idx + 1}`}
                          className="w-full h-full object-cover"
                        />
                      </a>
                    ))}
                  </div>
                </div>
              </div>
            </>
          )}

          {/* ---- Notes ---- */}
          {job.notes && (
            <>
              <div className="h-px bg-border" />
              <div className="flex items-start gap-3">
                <StickyNote className="w-5 h-5 text-muted-foreground mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                    Notes
                  </p>
                  <p className="text-sm text-foreground whitespace-pre-wrap">
                    {job.notes}
                  </p>
                </div>
              </div>
            </>
          )}

          {/* ---- Completion info ---- */}
          {isCompleted && job.completed_at && (
            <>
              <div className="h-px bg-border" />
              <div className="flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 mt-0.5 shrink-0" />
                <div>
                  <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-1">
                    Completed
                  </p>
                  <p className="text-sm font-medium text-emerald-700">
                    {formatDate(job.completed_at)}
                  </p>
                </div>
              </div>
            </>
          )}
        </div>

        {/* ---- Action buttons ---- */}
        <div className="px-4 sm:px-6 py-4 border-t border-border">
          {canAccept && (
            <div className="flex gap-3">
              <button
                onClick={() => setModalAction("decline")}
                className="flex-1 text-sm font-medium px-4 py-2.5 rounded-lg border border-border hover:bg-muted transition-colors"
              >
                Decline
              </button>
              <button
                onClick={() => setModalAction("accept")}
                className="flex-1 text-sm font-medium px-4 py-2.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
              >
                Accept Job
              </button>
            </div>
          )}

          {isActive && (
            <Link
              href={`/driver/jobs/${job.id}/active`}
              className="block w-full text-center text-sm font-medium px-4 py-2.5 rounded-lg bg-emerald-600 text-white hover:bg-emerald-700 transition-colors"
            >
              Go to Active Job
            </Link>
          )}

          {isCompleted && (
            <Link
              href="/driver/jobs"
              className="block w-full text-center text-sm font-medium px-4 py-2.5 rounded-lg bg-muted text-muted-foreground hover:bg-muted/80 transition-colors"
            >
              Back to Jobs
            </Link>
          )}
        </div>
      </div>

      {/* ================================================================== */}
      {/* Confirmation Modal — bottom sheet on mobile                         */}
      {/* ================================================================== */}
      {modalAction && (
        <div
          className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50"
          onClick={() => {
            if (!actionLoading) setModalAction(null);
          }}
        >
          <div
            className="bg-card rounded-t-xl sm:rounded-xl border border-border shadow-xl w-full sm:max-w-md sm:mx-4 max-h-[85vh] flex flex-col"
            onClick={(e) => e.stopPropagation()}
          >
            {/* Modal header */}
            <div className="px-4 sm:px-6 py-4 border-b border-border flex items-center justify-between flex-shrink-0">
              <h3 className="font-semibold">
                {modalAction === "accept" ? "Accept Job" : "Decline Job"}
              </h3>
              <button
                onClick={() => {
                  if (!actionLoading) setModalAction(null);
                }}
                className="p-1 rounded-lg hover:bg-muted transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {/* Modal body */}
            <div className="px-4 sm:px-6 py-6">
              <p className="text-sm text-muted-foreground">
                {modalAction === "accept"
                  ? "Are you sure you want to accept this job? You will be responsible for completing it."
                  : "Are you sure you want to decline this job? It will be made available to other drivers."}
              </p>
            </div>

            {/* Modal footer */}
            <div className="px-4 sm:px-6 py-3 border-t border-border flex gap-3 flex-shrink-0">
              <button
                onClick={() => {
                  if (!actionLoading) setModalAction(null);
                }}
                disabled={actionLoading}
                className="flex-1 text-sm font-medium px-4 py-2.5 rounded-lg border border-border hover:bg-muted transition-colors disabled:opacity-50"
              >
                Cancel
              </button>
              <button
                onClick={handleConfirmAction}
                disabled={actionLoading}
                className={`flex-1 text-sm font-medium px-4 py-2.5 rounded-lg transition-colors disabled:opacity-50 inline-flex items-center justify-center gap-2 ${
                  modalAction === "accept"
                    ? "bg-emerald-600 text-white hover:bg-emerald-700"
                    : "bg-red-600 text-white hover:bg-red-700"
                }`}
              >
                {actionLoading && (
                  <Loader2 className="w-4 h-4 animate-spin" />
                )}
                {modalAction === "accept" ? "Accept" : "Decline"}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
