"use client";

import { payoutStatusLabel } from "@/lib/payout-status";
import { resolveMediaUrl } from "@/lib/media-url";
import * as Dialog from "@radix-ui/react-dialog";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { driverApi, ApiError } from "@/lib/api";
import { useDriverWork } from "@/hooks/use-driver-work";
import type { DriverJob } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import {
  Check,
  Navigation,
  MapPin,
  Camera,
  Clock,
  Phone,
  Package,
  ChevronRight,
  AlertCircle,
  Upload,
  X,
  Loader2,
  CheckCircle2,
  ArrowLeft,
  DollarSign,
  Image as ImageIcon,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STEPS = [
  { key: "assigned", label: "Accepted" },
  { key: "en_route", label: "En Route" },
  { key: "arrived", label: "Arrived" },
  { key: "in_progress", label: "In Progress" },
  { key: "completed", label: "Completed" },
] as const;

const STEP_INDEX: Record<string, number> = {
  assigned: 0,
  en_route: 1,
  arrived: 2,
  in_progress: 3,
  completed: 4,
};

const POLL_INTERVAL = 10_000;

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatPrice(amount: number): string {
  return `$${amount.toFixed(2)}`;
}

function formatAddress(address: string): string {
  return address.length > 60 ? address.slice(0, 57) + "..." : address;
}

function isIOS(): boolean {
  if (typeof navigator === "undefined") return false;
  return /iPad|iPhone|iPod/.test(navigator.userAgent);
}

function getMapsUrl(address: string): string {
  const encoded = encodeURIComponent(address);
  if (isIOS()) {
    return `https://maps.apple.com/?daddr=${encoded}`;
  }
  return `https://www.google.com/maps/dir/?api=1&destination=${encoded}`;
}

function formatElapsedTime(startedAt: string): string {
  const start = new Date(startedAt).getTime();
  const now = Date.now();
  const diff = Math.max(0, now - start);
  const hours = Math.floor(diff / 3_600_000);
  const minutes = Math.floor((diff % 3_600_000) / 60_000);
  const seconds = Math.floor((diff % 60_000) / 1_000);
  if (hours > 0) {
    return `${hours}h ${minutes.toString().padStart(2, "0")}m ${seconds.toString().padStart(2, "0")}s`;
  }
  return `${minutes}m ${seconds.toString().padStart(2, "0")}s`;
}

// ---------------------------------------------------------------------------
// Photo Upload Section (inline reusable component)
// ---------------------------------------------------------------------------

function PhotoUploadSection({
  label,
  photos,
  onUpload,
  uploading,
  existingUrls,
  onRetry,
  onRemove,
  disabled = false,
}: {
  label: string;
  photos: File[];
  onUpload: (files: File[]) => void;
  uploading: boolean;
  existingUrls: string[];
  onRetry: () => void;
  onRemove: (index: number) => void;
  disabled?: boolean;
}) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [previews, setPreviews] = useState<string[]>([]);

  useEffect(() => {
    const urls = photos.map((f) => URL.createObjectURL(f));
    setPreviews(urls);
    return () => urls.forEach((u) => URL.revokeObjectURL(u));
  }, [photos]);

  function handleFileChange(e: React.ChangeEvent<HTMLInputElement>) {
    const files = e.target.files;
    if (!files || files.length === 0) return;
    onUpload(Array.from(files));
    // Reset input so the same file can be selected again
    e.target.value = "";
  }

  return (
    <div className="space-y-3">
      <div className="flex items-center justify-between">
        <h3 className="text-sm font-semibold text-foreground">{label}</h3>
        <Badge variant="outline" className="text-xs">
          {existingUrls.length + photos.length} photo{existingUrls.length + photos.length !== 1 ? "s" : ""}
        </Badge>
      </div>

      {/* Existing uploaded photos */}
      {existingUrls.length > 0 && (
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {existingUrls.map((url, idx) => (
            <div
              key={`existing-${idx}`}
              className="aspect-square rounded-lg overflow-hidden border border-emerald-200 bg-muted relative"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={resolveMediaUrl(url)}
                alt={`${label} ${idx + 1}`}
                className="w-full h-full object-cover"
              />
              <div className="absolute top-1 right-1">
                <CheckCircle2 className="w-4 h-4 text-emerald-600 drop-shadow-sm" />
              </div>
            </div>
          ))}
        </div>
      )}

      {/* Pending upload previews */}
      {previews.length > 0 && (
        <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
          {previews.map((src, idx) => (
            <div
              key={`preview-${idx}`}
              className="aspect-square rounded-lg overflow-hidden border border-dashed border-amber-300 bg-muted relative"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img
                src={src}
                alt={`Preview ${idx + 1}`}
                className="w-full h-full object-cover opacity-80"
              />
              {uploading && (
                <div className="absolute inset-0 flex items-center justify-center bg-black/30">
                  <Loader2 className="w-5 h-5 text-white animate-spin" />
                </div>
              )}
              {!uploading && <button type="button" aria-label={`Remove pending ${label.toLowerCase()} ${idx + 1}`} onClick={() => onRemove(idx)} className="absolute right-1 top-1 rounded bg-white px-2 py-1 text-xs text-destructive">Remove</button>}
            </div>
          ))}
        </div>
      )}

      {photos.length > 0 && !uploading && <Button variant="outline" className="w-full" onClick={onRetry}>Retry saved {label.toLowerCase()}</Button>}
      {/* Upload button */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/jpeg,image/png,image/webp"
        capture="environment"
        multiple
        disabled={uploading || disabled}
        onChange={handleFileChange}
        className="hidden"
      />
      <Button
        variant="outline"
        size="sm"
        className="w-full gap-2 border-dashed"
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading || disabled}
      >
        {uploading ? (
          <>
            <Loader2 className="w-4 h-4 animate-spin" />
            Uploading...
          </>
        ) : (
          <>
            <Camera className="w-4 h-4" />
            Take / Select Photos
          </>
        )}
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Status Stepper
// ---------------------------------------------------------------------------

function StatusStepper({ currentStatus }: { currentStatus: string }) {
  const currentIdx = STEP_INDEX[currentStatus] ?? -1;

  return (
    <div className="w-full overflow-x-auto pb-1">
      <div className="flex items-center min-w-[500px] px-1">
        {STEPS.map((step, idx) => {
          const isCompleted = idx < currentIdx;
          const isCurrent = idx === currentIdx;
          const isFuture = idx > currentIdx;

          return (
            <div key={step.key} className="flex items-center flex-1 last:flex-none">
              {/* Step circle + label */}
              <div className="flex flex-col items-center gap-1.5">
                <div
                  className={`
                    w-8 h-8 rounded-full flex items-center justify-center text-xs font-bold
                    transition-all duration-300 flex-shrink-0
                    ${isCompleted ? "bg-emerald-100 text-emerald-700" : ""}
                    ${isCurrent ? "bg-emerald-600 text-white ring-4 ring-emerald-100" : ""}
                    ${isFuture ? "bg-muted text-muted-foreground" : ""}
                  `}
                >
                  {isCompleted ? (
                    <Check className="w-4 h-4" />
                  ) : (
                    idx + 1
                  )}
                </div>
                <span
                  className={`text-[11px] font-medium whitespace-nowrap ${
                    isCurrent
                      ? "text-emerald-700"
                      : isCompleted
                        ? "text-emerald-600"
                        : "text-muted-foreground"
                  }`}
                >
                  {step.label}
                </span>
              </div>

              {/* Connector line */}
              {idx < STEPS.length - 1 && (
                <div className="flex-1 mx-2 mt-[-18px]">
                  <div
                    className={`h-0.5 w-full rounded-full transition-colors duration-300 ${
                      idx < currentIdx ? "bg-emerald-400" : "bg-muted"
                    }`}
                  />
                </div>
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Confirmation Modal
// ---------------------------------------------------------------------------

function ConfirmModal({
  open,
  title,
  message,
  confirmLabel,
  onConfirm,
  onCancel,
  loading,
  disabled,
  children,
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
  disabled?: boolean;
  children?: React.ReactNode;
}) {
  return (
    <Dialog.Root open={open} onOpenChange={(next) => { if (!next && !loading) onCancel(); }}>
      <Dialog.Portal>
        <Dialog.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <Dialog.Content className="fixed left-1/2 top-1/2 z-50 w-[calc(100%-2rem)] max-w-sm -translate-x-1/2 -translate-y-1/2 rounded-xl border border-border bg-card p-6 shadow-lg space-y-4">
        <Dialog.Title className="text-lg font-semibold text-foreground">{title}</Dialog.Title>
        <Dialog.Description className="text-sm text-muted-foreground">{message}</Dialog.Description>
        {children}
        <div className="flex items-center gap-3 pt-2">
          <Button
            onClick={onConfirm}
            disabled={loading || disabled}
            className="flex-1 bg-emerald-600 hover:bg-emerald-700 text-white"
          >
            {loading ? (
              <Loader2 className="w-4 h-4 animate-spin mr-2" />
            ) : null}
            {confirmLabel}
          </Button>
          <Button
            variant="outline"
            onClick={onCancel}
            disabled={loading}
            className="flex-1"
          >
            Cancel
          </Button>
        </div>
        </Dialog.Content>
      </Dialog.Portal>
    </Dialog.Root>
  );
}

// ---------------------------------------------------------------------------
// Volume Adjustment Card — driver enters actual volume on-site, system auto-
// approves a price drop or pings the customer to accept a price increase.
// ---------------------------------------------------------------------------

function VolumeAdjustmentCard({
  job,
  onAdjusted,
  onError,
}: {
  job: DriverJob;
  onAdjusted: (newPrice: number, autoApproved: boolean) => void;
  onError: (msg: string) => void;
}) {
  const [volume, setVolume] = useState<string>("");
  const [busy, setBusy] = useState(false);
  const [result, setResult] = useState<
    | { autoApproved: boolean; newPrice: number; originalPrice: number }
    | null
  >(null);

  // If customer has already been pinged for an unresolved adjust, show that.
  const pending = (job as DriverJob & { volume_adjustment_proposed?: boolean })
    .volume_adjustment_proposed;

  async function submit() {
    const v = Number(volume);
    if (!v || v <= 0) {
      onError("Enter a positive cubic-yard number.");
      return;
    }
    setBusy(true);
    onError(""); // clear any prior error
    try {
      const res = await driverApi.proposeVolumeAdjustment(job.id, v);
      const original = res.original_price ?? job.total_price;
      setResult({
        autoApproved: !!res.auto_approved,
        newPrice: res.new_price,
        originalPrice: original,
      });
      if (res.auto_approved) onAdjusted(res.new_price, true);
      else onAdjusted(job.total_price, false); // price unchanged until customer approves
    } catch (e) {
      const msg = e instanceof ApiError
        ? (e as ApiError & { data?: { error?: string } }).data?.error || e.message
        : String(e);
      onError(msg);
    } finally {
      setBusy(false);
    }
  }

  return (
    <Card className="border-amber-200 bg-amber-50/40">
      <CardHeader>
        <CardTitle className="text-base font-semibold flex items-center gap-2">
          <DollarSign className="w-4 h-4 text-amber-700" />
          Review the pickup price
        </CardTitle>
      </CardHeader>
      <CardContent className="space-y-3">
        {pending && !result && (
          <div className="text-sm rounded bg-white border border-amber-300 p-2 text-amber-800">
            Customer has a pending price adjustment. Wait for them to accept or
            decline.
          </div>
        )}
        {!pending && !result && (
          <>
            <p className="text-xs text-muted-foreground">
              Enter the actual volume you see (cubic yards). 4yd = quarter
              truck, 8yd = half, 12yd = three-quarter, 16yd = full.
            </p>
            <div className="flex gap-2">
              <input
                type="number"
                step="0.5"
                min="0.5"
                placeholder="cubic yards"
                value={volume}
                onChange={(e) => setVolume(e.target.value)}
                className="flex-1 rounded border border-gray-300 px-3 py-2 text-sm"
                disabled={busy}
              />
              <Button
                onClick={submit}
                disabled={busy || !volume}
                className="bg-amber-600 hover:bg-amber-700 text-white"
              >
                {busy ? <Loader2 className="w-4 h-4 animate-spin" /> : "Propose"}
              </Button>
            </div>
          </>
        )}
        {result?.autoApproved && (
          <div className="text-sm rounded bg-emerald-100 border border-emerald-300 p-2 text-emerald-800">
            ✓ Auto-approved (price went down).
            {" "}New: ${result.newPrice.toFixed(2)} (was ${result.originalPrice.toFixed(2)}).
            The revised amount is reflected in this pickup.
          </div>
        )}
        {result && !result.autoApproved && (
          <div className="text-sm rounded bg-amber-100 border border-amber-300 p-2 text-amber-900">
            Sent to customer for approval. Proposed:
            {" "}${result.newPrice.toFixed(2)} (was ${result.originalPrice.toFixed(2)}).
            Wait for their approval and payment confirmation before starting work.
          </div>
        )}
      </CardContent>
    </Card>
  );
}


// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------

export default function ActiveJobPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;
  const work = useDriverWork(id);

  // Core state
  const [job, setJob] = useState<DriverJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Status transition state
  const [transitioning, setTransitioning] = useState(false);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  const beforePhotos = work.before;
  const afterPhotos = work.after;
  const beforeUploading = work.busy;
  const afterUploading = work.busy;
  const beforeUploadedUrls = Array.from(new Set([...(job?.before_photos ?? []), ...work.beforeURLs]));
  const afterUploadedUrls = Array.from(new Set([...(job?.after_photos ?? []), ...work.afterURLs]));

  // Completion confirm modal
  const [completeModalOpen, setCompleteModalOpen] = useState(false);
  const [handoffPin, setHandoffPin] = useState("");

  // Elapsed timer
  const [elapsed, setElapsed] = useState("");

  // ---------------------------------------------------------------------------
  // Data Loading
  // ---------------------------------------------------------------------------

  const fetchJob = useCallback(async () => {
    if (!id) return;
    try {
      const res = await driverApi.getJob(id);
      const j = res.job;
      setJob(j);
      setError(null);
    } catch (err: unknown) {
      const message = err instanceof ApiError ? err.message : "Failed to load job.";
      setError(message);
    } finally {
      setLoading(false);
    }
  }, [id]);

  // Initial fetch
  useEffect(() => {
    fetchJob();
  }, [fetchJob]);

  // Poll every 10 seconds
  useEffect(() => {
    if (!id) return;
    const interval = setInterval(() => {
      // Silent refresh -- do not overwrite loading state
      driverApi
        .getJob(id)
        .then((res) => {
          setJob(res.job);
        })
        .catch(() => {
          // Silently ignore polling errors
        });
    }, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [id]);

  // Elapsed timer tick
  useEffect(() => {
    if (!job || job.status !== "in_progress" || !job.started_at) return;
    const tick = () => setElapsed(formatElapsedTime(job.started_at!));
    tick();
    const interval = setInterval(tick, 1_000);
    return () => clearInterval(interval);
  }, [job]);

  // Auto-dismiss success banners
  useEffect(() => {
    if (!successBanner) return;
    const t = setTimeout(() => setSuccessBanner(null), 4_000);
    return () => clearTimeout(t);
  }, [successBanner]);

  // ---------------------------------------------------------------------------
  // Status Transition Handlers
  // ---------------------------------------------------------------------------

  async function handleStatusUpdate(newStatus: string, successMessage: string, pin?: string) {
    setTransitioning(true); setError(null);
    try {
      const updated = await work.transition(newStatus, pin);
      if (updated) { setJob(updated); setSuccessBanner(successMessage); }
      return Boolean(updated);
    } finally { setTransitioning(false); }
  }

  async function handleBeforeUpload(files: File[]) {
    if (await work.upload("before", files)) setSuccessBanner("Before photos saved. They will be attached when you start the pickup.");
  }

  async function handleAfterUpload(files: File[]) {
    if (await work.upload("after", files)) setSuccessBanner("After photos saved. They will be attached when you complete the pickup.");
  }

  async function handleCompleteJob() {
    if (await handleStatusUpdate("completed", "Job completed! Great work.", handoffPin)) {
      setCompleteModalOpen(false);
      setHandoffPin("");
    }
  }

  // ---------------------------------------------------------------------------
  // Loading Skeleton
  // ---------------------------------------------------------------------------

  if (loading || (!work.ready && !work.error)) {
    return (
      <div className="max-w-2xl mx-auto space-y-6">
        <div className="flex items-center gap-3">
          <div className="h-8 w-8 rounded-full bg-muted animate-pulse" />
          <div className="h-5 w-40 bg-muted rounded animate-pulse" />
        </div>
        <div className="h-16 bg-muted rounded-xl animate-pulse" />
        <div className="h-48 bg-muted rounded-xl animate-pulse" />
        <div className="h-32 bg-muted rounded-xl animate-pulse" />
        <div className="h-12 bg-muted rounded-xl animate-pulse" />
      </div>
    );
  }

  // ---------------------------------------------------------------------------
  // Error State
  // ---------------------------------------------------------------------------

  if (error && !job) {
    return (
      <div className="max-w-2xl mx-auto">
        <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-8 text-center">
          <AlertCircle className="w-10 h-10 text-destructive mx-auto mb-3" />
          <p className="text-destructive font-medium mb-1">Something went wrong</p>
          <p className="text-muted-foreground text-sm mb-4">{error}</p>
          <div className="flex items-center justify-center gap-3">
            <Button variant="outline" size="sm" onClick={fetchJob}>
              Try Again
            </Button>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => router.push("/driver")}
            >
              Back to Dashboard
            </Button>
          </div>
        </div>
      </div>
    );
  }

  if (!job) return null;

  const currentStep = STEP_INDEX[job.status] ?? -1;
  const itemsCount = job.items.reduce((sum, item) => sum + item.quantity, 0);

  // ---------------------------------------------------------------------------
  // Render
  // ---------------------------------------------------------------------------

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      {/* Back link + job ID */}
      <div className="flex items-center gap-3">
        <Button
          variant="ghost"
          size="sm"
          className="gap-1 -ml-2 text-muted-foreground"
          onClick={() => router.push("/driver/jobs")}
        >
          <ArrowLeft className="w-4 h-4" />
          Jobs
        </Button>
        <span className="text-muted-foreground text-sm">/</span>
        <span className="text-sm font-medium">Job #{id.slice(0, 8)}</span>
      </div>

      {work.error && <div role="alert" className="rounded-lg border border-red-200 bg-red-50 p-4 text-sm text-red-800">{work.error}</div>}
      {work.pendingStatus && <div role="status" className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm">
        <p>You have a saved pickup update. Retry to check whether it already reached the server.</p>
        <Button variant="outline" className="mt-2" disabled={work.busy || !work.ready} onClick={() => {
          if (work.pendingStatus === "completed" && job.status !== "completed") setCompleteModalOpen(true);
          else void handleStatusUpdate(work.pendingStatus!, "Saved update confirmed.");
        }}>Retry saved update</Button>
      </div>}
      {job.requires_acceptance && <div className="rounded-lg border border-amber-200 bg-amber-50 p-4 text-sm"><p>This pickup is assigned to you and still needs your acceptance.</p><Link className="mt-2 inline-block font-semibold underline" href={`/driver/jobs/${id}`}>Review and accept pickup</Link></div>}
      {/* Success Banner */}
      {successBanner && (
        <div className="rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-3 flex items-center gap-3 animate-in fade-in slide-in-from-top-2 duration-300">
          <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
          <p className="text-sm text-emerald-800 font-medium flex-1">{successBanner}</p>
          <button onClick={() => setSuccessBanner(null)} className="text-emerald-600 hover:text-emerald-800">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Error Banner (inline) */}
      {error && job && (
        <div className="rounded-lg bg-destructive/5 border border-destructive/20 px-4 py-3 flex items-center gap-3">
          <AlertCircle className="w-5 h-5 text-destructive flex-shrink-0" />
          <p className="text-sm text-destructive flex-1">{error}</p>
          <button onClick={() => setError(null)} className="text-destructive/60 hover:text-destructive">
            <X className="w-4 h-4" />
          </button>
        </div>
      )}

      {/* Status Stepper */}
      <Card>
        <CardContent className="pt-6 pb-4">
          <StatusStepper currentStatus={job.status} />
        </CardContent>
      </Card>

      {/* ================================================================== */}
      {/* STEP: Accepted (assigned) */}
      {/* ================================================================== */}
      {job.status === "assigned" && (
        <>
          {/* Job Summary */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Package className="w-4 h-4 text-emerald-600" />
                Job Summary
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-muted-foreground block text-xs uppercase tracking-wide mb-1">
                    Pickup Address
                  </span>
                  <p className="font-medium">{job.address}</p>
                  {job.city && (
                    <p className="text-muted-foreground text-xs mt-0.5">{job.city}</p>
                  )}
                </div>
                <div>
                  <span className="text-muted-foreground block text-xs uppercase tracking-wide mb-1">
                    Customer
                  </span>
                  <p className="font-medium">{job.customer_name || "Customer"}</p>
                  {job.customer_phone && (
                    <a
                      href={`tel:${job.customer_phone}`}
                      className="inline-flex items-center gap-1.5 text-emerald-600 hover:text-emerald-700 text-xs mt-1 font-medium"
                    >
                      <Phone className="w-3.5 h-3.5" />
                      {job.customer_phone}
                    </a>
                  )}
                </div>
              </div>

              <Separator />

              <div className="flex items-center justify-between text-sm">
                <div>
                  <span className="text-muted-foreground text-xs uppercase tracking-wide">
                    Items
                  </span>
                  <div className="mt-1 space-y-0.5">
                    {job.items.map((item, idx) => (
                      <p key={idx} className="text-sm">
                        {item.category} <span className="text-muted-foreground">x{item.quantity}</span>
                      </p>
                    ))}
                  </div>
                </div>
                <div className="text-right">
                  <span className="text-muted-foreground text-xs uppercase tracking-wide block">
                    Payout
                  </span>
                  <p className="text-lg font-bold text-emerald-700 mt-0.5">
                    {job.driver_payout == null ? "Pay pending" : formatPrice(job.driver_payout)}
                  </p>
                </div>
              </div>

              {job.notes && (
                <>
                  <Separator />
                  <div>
                    <span className="text-muted-foreground text-xs uppercase tracking-wide">
                      Notes
                    </span>
                    <p className="text-sm mt-1">{job.notes}</p>
                  </div>
                </>
              )}
            </CardContent>
          </Card>

          {/* Action: Start driving */}
          <Button
            onClick={() => handleStatusUpdate("en_route", "You are now en route!")}
            disabled={transitioning || work.busy || !work.ready || job.requires_acceptance}
            className="w-full h-14 text-base font-semibold bg-emerald-600 hover:bg-emerald-700 text-white gap-2 rounded-xl"
          >
            {transitioning ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <Navigation className="w-5 h-5" />
            )}
            {transitioning ? "Updating..." : "I'm on my way"}
          </Button>
        </>
      )}

      {/* ================================================================== */}
      {/* STEP: En Route */}
      {/* ================================================================== */}
      {job.status === "en_route" && (
        <>
          {/* Navigation Card */}
          <Card className="border-emerald-200 bg-emerald-50/50">
            <CardContent className="pt-6 space-y-4">
              <div className="flex items-start gap-3">
                <div className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center flex-shrink-0">
                  <MapPin className="w-5 h-5 text-emerald-700" />
                </div>
                <div className="flex-1 min-w-0">
                  <p className="text-sm font-semibold text-foreground">Heading to pickup</p>
                  <p className="text-sm text-muted-foreground mt-0.5 break-words">
                    {job.address}
                  </p>
                </div>
              </div>

              <a
                href={getMapsUrl(job.address)}
                target="_blank"
                rel="noopener noreferrer"
                className="block"
              >
                <Button
                  variant="outline"
                  className="w-full gap-2 border-emerald-300 text-emerald-700 hover:bg-emerald-100"
                >
                  <Navigation className="w-4 h-4" />
                  Open in Maps
                </Button>
              </a>
            </CardContent>
          </Card>

          {/* Customer Info */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between">
                <div>
                  <p className="text-sm font-semibold">{job.customer_name || "Customer"}</p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    {itemsCount} item{itemsCount !== 1 ? "s" : ""} &middot; {job.driver_payout == null ? "Pay pending" : formatPrice(job.driver_payout)}
                  </p>
                </div>
                {job.customer_phone && (
                  <a
                    href={`tel:${job.customer_phone}`}
                    className="w-10 h-10 rounded-full bg-emerald-100 flex items-center justify-center text-emerald-700 hover:bg-emerald-200 transition-colors"
                  >
                    <Phone className="w-4 h-4" />
                  </a>
                )}
              </div>
            </CardContent>
          </Card>

          {/* Action: Arrived */}
          <Button
            onClick={() => handleStatusUpdate("arrived", "Marked as arrived.")}
            disabled={transitioning || work.busy || !work.ready || job.requires_acceptance}
            className="w-full h-14 text-base font-semibold bg-emerald-600 hover:bg-emerald-700 text-white gap-2 rounded-xl"
          >
            {transitioning ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <MapPin className="w-5 h-5" />
            )}
            {transitioning ? "Updating..." : "I've Arrived"}
          </Button>
        </>
      )}

      {/* ================================================================== */}
      {/* STEP: Arrived */}
      {/* ================================================================== */}
      {job.status === "arrived" && (
        <>
          {/* Before Photos */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Camera className="w-4 h-4 text-emerald-600" />
                Before Photos
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground mb-4">
                Take photos of the items before loading. This helps document the job.
              </p>
              <PhotoUploadSection
                label="Before Photos"
                photos={beforePhotos}
                onUpload={handleBeforeUpload}
                uploading={beforeUploading}
                disabled={!work.ready}
                existingUrls={beforeUploadedUrls}
                onRetry={() => { void work.upload("before"); }}
                onRemove={(index) => { void work.removePendingPhoto("before", index); }}
              />
            </CardContent>
          </Card>

          {/* Customer / Job info summary */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between text-sm">
                <div>
                  <p className="font-semibold">{job.customer_name || "Customer"}</p>
                  <p className="text-muted-foreground text-xs mt-0.5">
                    {formatAddress(job.address)}
                  </p>
                </div>
                <div className="text-right">
                  <p className="font-bold text-emerald-700">{job.driver_payout == null ? "Pay pending" : formatPrice(job.driver_payout)}</p>
                  <p className="text-muted-foreground text-xs">
                    {itemsCount} item{itemsCount !== 1 ? "s" : ""}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Volume adjustment — only relevant in "arrived" status */}
          <VolumeAdjustmentCard
            job={job}
            onAdjusted={(newPrice) =>
              setJob((j) => (j ? { ...j, total_price: newPrice } : j))
            }
            onError={(msg) => setError(msg || null)}
          />

          {/* Action: Start Job */}
          <Button
            onClick={() => handleStatusUpdate("in_progress", "Job started. Timer running.")}
            disabled={transitioning || work.busy || !work.ready || job.requires_acceptance}
            className="w-full h-14 text-base font-semibold bg-emerald-600 hover:bg-emerald-700 text-white gap-2 rounded-xl"
          >
            {transitioning ? (
              <Loader2 className="w-5 h-5 animate-spin" />
            ) : (
              <ChevronRight className="w-5 h-5" />
            )}
            {transitioning ? "Starting..." : "Start Job"}
          </Button>
        </>
      )}

      {/* ================================================================== */}
      {/* STEP: In Progress */}
      {/* ================================================================== */}
      {job.status === "in_progress" && (
        <>
          {/* Elapsed Timer */}
          <Card className="border-emerald-200 bg-emerald-50/50">
            <CardContent className="pt-6 pb-5">
              <div className="flex items-center justify-center gap-3">
                <Clock className="w-5 h-5 text-emerald-600" />
                <div className="text-center">
                  <p className="text-xs text-emerald-700 font-medium uppercase tracking-wide">
                    Time Elapsed
                  </p>
                  <p className="text-3xl font-bold text-emerald-800 tabular-nums mt-0.5">
                    {elapsed || "0m 00s"}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* After Photos */}
          <Card>
            <CardHeader>
              <CardTitle className="text-base font-semibold flex items-center gap-2">
                <Camera className="w-4 h-4 text-emerald-600" />
                After Photos
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xs text-muted-foreground mb-4">
                Take photos after loading/completing the work as proof of completion.
              </p>
              <PhotoUploadSection
                label="After Photos"
                photos={afterPhotos}
                onUpload={handleAfterUpload}
                uploading={afterUploading}
                disabled={!work.ready}
                existingUrls={afterUploadedUrls}
                onRetry={() => { void work.upload("after"); }}
                onRemove={(index) => { void work.removePendingPhoto("after", index); }}
              />
            </CardContent>
          </Card>

          {/* Job summary */}
          <Card>
            <CardContent className="pt-6">
              <div className="flex items-center justify-between text-sm">
                <div>
                  <p className="font-semibold">{formatAddress(job.address)}</p>
                  <p className="text-muted-foreground text-xs mt-0.5">
                    {itemsCount} item{itemsCount !== 1 ? "s" : ""}
                  </p>
                </div>
                <p className="font-bold text-emerald-700 text-lg">
                  {job.driver_payout == null ? "Pay pending" : formatPrice(job.driver_payout)}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Action: Complete Job (with confirmation) */}
          <Button
            onClick={() => setCompleteModalOpen(true)}
            disabled={transitioning || work.busy || !work.ready || job.requires_acceptance}
            className="w-full h-14 text-base font-semibold bg-emerald-600 hover:bg-emerald-700 text-white gap-2 rounded-xl"
          >
            <CheckCircle2 className="w-5 h-5" />
            Complete Job
          </Button>

          <ConfirmModal
            open={completeModalOpen}
            title="Complete this job?"
            message="Confirm that all items have been loaded and the job is finished. This action cannot be undone."
            confirmLabel={transitioning ? "Completing..." : "Yes, Complete Job"}
            onConfirm={handleCompleteJob}
            onCancel={() => { setCompleteModalOpen(false); setHandoffPin(""); }}
            loading={transitioning}
            disabled={handoffPin.length > 0 && handoffPin.length !== 4}
          >
            <div className="space-y-2">
              <Label htmlFor="handoff-pin">Customer handoff PIN</Label>
              <Input id="handoff-pin" inputMode="numeric" autoComplete="one-time-code" maxLength={4}
                value={handoffPin} disabled={transitioning}
                onChange={(event) => setHandoffPin(event.target.value.replace(/\D/g, ""))}
                aria-describedby="handoff-pin-help" placeholder="4-digit PIN" />
              <p id="handoff-pin-help" className="text-xs text-muted-foreground">
                Ask the customer for the PIN sent with their pickup confirmation. Leave blank if a PIN is not required and you have an after photo.
              </p>
            </div>
            {work.error && <p role="alert" className="text-sm text-destructive">{work.error}</p>}
          </ConfirmModal>
        </>
      )}

      {/* ================================================================== */}
      {/* STEP: Completed */}
      {/* ================================================================== */}
      {job.status === "completed" && (
        <>
          {/* Success State */}
          <Card className="border-emerald-200 bg-emerald-50/30 text-center">
            <CardContent className="pt-8 pb-8 space-y-4">
              <div className="w-16 h-16 rounded-full bg-emerald-100 flex items-center justify-center mx-auto">
                <CheckCircle2 className="w-8 h-8 text-emerald-600" />
              </div>
              <div>
                <h2 className="text-xl font-bold text-foreground">Job Complete!</h2>
                <p className="text-sm text-muted-foreground mt-1">
                  {payoutStatusLabel(job.payout_status)}. View Earnings for details.
                </p>
              </div>

              {/* Payout */}
              <div className="bg-white rounded-xl border border-emerald-200 px-6 py-4 inline-block mx-auto">
                <span className="text-xs text-muted-foreground uppercase tracking-wide block">
                  Payout Amount
                </span>
                <div className="flex items-center justify-center gap-2 mt-1">
                  <DollarSign className="w-5 h-5 text-emerald-600" />
                  <span className="text-3xl font-bold text-emerald-700">
                    {job.driver_payout == null ? "Pending" : job.driver_payout.toFixed(2)}
                  </span>
                </div>
              </div>

              {job.completed_at && (
                <p className="text-xs text-muted-foreground">
                  Completed {new Date(job.completed_at).toLocaleString("en-US", {
                    weekday: "short",
                    month: "short",
                    day: "numeric",
                    hour: "numeric",
                    minute: "2-digit",
                  })}
                </p>
              )}
            </CardContent>
          </Card>

          {/* Before / After Photo Comparison */}
          {(beforeUploadedUrls.length > 0 || afterUploadedUrls.length > 0) && (
            <Card>
              <CardHeader>
                <CardTitle className="text-base font-semibold flex items-center gap-2">
                  <ImageIcon className="w-4 h-4 text-emerald-600" />
                  Before &amp; After
                </CardTitle>
              </CardHeader>
              <CardContent className="space-y-4">
                {beforeUploadedUrls.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                      Before
                    </p>
                    <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                      {beforeUploadedUrls.map((url, idx) => (
                        <div
                          key={`before-${idx}`}
                          className="aspect-square rounded-lg overflow-hidden border border-border bg-muted"
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={url}
                            alt={`Before ${idx + 1}`}
                            className="w-full h-full object-cover"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {beforeUploadedUrls.length > 0 && afterUploadedUrls.length > 0 && (
                  <Separator />
                )}

                {afterUploadedUrls.length > 0 && (
                  <div>
                    <p className="text-xs font-medium text-muted-foreground uppercase tracking-wide mb-2">
                      After
                    </p>
                    <div className="grid grid-cols-3 sm:grid-cols-4 gap-2">
                      {afterUploadedUrls.map((url, idx) => (
                        <div
                          key={`after-${idx}`}
                          className="aspect-square rounded-lg overflow-hidden border border-border bg-muted"
                        >
                          {/* eslint-disable-next-line @next/next/no-img-element */}
                          <img
                            src={url}
                            alt={`After ${idx + 1}`}
                            className="w-full h-full object-cover"
                          />
                        </div>
                      ))}
                    </div>
                  </div>
                )}
              </CardContent>
            </Card>
          )}

          {/* Back to Dashboard */}
          <Link href="/driver" className="block">
            <Button
              variant="outline"
              className="w-full h-12 text-base font-semibold gap-2 rounded-xl"
            >
              <ArrowLeft className="w-4 h-4" />
              Back to Dashboard
            </Button>
          </Link>
        </>
      )}
    </div>
  );
}
