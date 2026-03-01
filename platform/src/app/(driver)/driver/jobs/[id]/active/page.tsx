"use client";

import { useEffect, useState, useCallback, useRef } from "react";
import Link from "next/link";
import { useParams, useRouter } from "next/navigation";
import { driverApi, ApiError } from "@/lib/api";
import type { DriverJob } from "@/types";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
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

function getCurrentLocation(): Promise<{ lat: number; lng: number } | null> {
  return new Promise((resolve) => {
    if (!navigator.geolocation) {
      resolve(null);
      return;
    }
    navigator.geolocation.getCurrentPosition(
      (pos) => resolve({ lat: pos.coords.latitude, lng: pos.coords.longitude }),
      () => resolve(null),
      { timeout: 5000 }
    );
  });
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
}: {
  label: string;
  photos: File[];
  onUpload: (files: File[]) => void;
  uploading: boolean;
  existingUrls: string[];
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
                src={url}
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
            </div>
          ))}
        </div>
      )}

      {/* Upload button */}
      <input
        ref={fileInputRef}
        type="file"
        accept="image/*"
        capture="environment"
        multiple
        onChange={handleFileChange}
        className="hidden"
      />
      <Button
        variant="outline"
        size="sm"
        className="w-full gap-2 border-dashed"
        onClick={() => fileInputRef.current?.click()}
        disabled={uploading}
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
}: {
  open: boolean;
  title: string;
  message: string;
  confirmLabel: string;
  onConfirm: () => void;
  onCancel: () => void;
  loading: boolean;
}) {
  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4">
      <div className="fixed inset-0 bg-black/50" onClick={onCancel} />
      <div className="relative bg-card border border-border rounded-xl shadow-lg max-w-sm w-full p-6 space-y-4">
        <h3 className="text-lg font-semibold text-foreground">{title}</h3>
        <p className="text-sm text-muted-foreground">{message}</p>
        <div className="flex items-center gap-3 pt-2">
          <Button
            onClick={onConfirm}
            disabled={loading}
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
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------

export default function ActiveJobPage() {
  const params = useParams();
  const router = useRouter();
  const id = params.id as string;

  // Core state
  const [job, setJob] = useState<DriverJob | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Status transition state
  const [transitioning, setTransitioning] = useState(false);
  const [successBanner, setSuccessBanner] = useState<string | null>(null);

  // Photo state - before
  const [beforePhotos, setBeforePhotos] = useState<File[]>([]);
  const [beforeUploading, setBeforeUploading] = useState(false);
  const [beforeUploadedUrls, setBeforeUploadedUrls] = useState<string[]>([]);

  // Photo state - after
  const [afterPhotos, setAfterPhotos] = useState<File[]>([]);
  const [afterUploading, setAfterUploading] = useState(false);
  const [afterUploadedUrls, setAfterUploadedUrls] = useState<string[]>([]);

  // Completion confirm modal
  const [completeModalOpen, setCompleteModalOpen] = useState(false);

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
      setBeforeUploadedUrls(j.before_photos || []);
      setAfterUploadedUrls(j.after_photos || []);
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
          setBeforeUploadedUrls(res.job.before_photos || []);
          setAfterUploadedUrls(res.job.after_photos || []);
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

  async function handleStatusUpdate(newStatus: string, successMessage: string) {
    if (!id) return;
    setTransitioning(true);
    setError(null);
    try {
      const loc = await getCurrentLocation();
      const res = await driverApi.updateJobStatus(
        id,
        newStatus,
        loc?.lat,
        loc?.lng
      );
      setJob(res.job);
      setBeforeUploadedUrls(res.job.before_photos || []);
      setAfterUploadedUrls(res.job.after_photos || []);
      setSuccessBanner(successMessage);
    } catch (err: unknown) {
      const message = err instanceof ApiError ? err.message : "Failed to update status.";
      setError(message);
    } finally {
      setTransitioning(false);
    }
  }

  async function handleBeforeUpload(files: File[]) {
    setBeforePhotos((prev) => [...prev, ...files]);
    setBeforeUploading(true);
    try {
      const res = await driverApi.uploadJobPhotos(id, files, "before");
      setBeforeUploadedUrls((prev) => [...prev, ...res.urls]);
      setBeforePhotos([]);
      setSuccessBanner("Before photos uploaded successfully.");
    } catch (err: unknown) {
      const message = err instanceof ApiError ? err.message : "Failed to upload photos.";
      setError(message);
    } finally {
      setBeforeUploading(false);
    }
  }

  async function handleAfterUpload(files: File[]) {
    setAfterPhotos((prev) => [...prev, ...files]);
    setAfterUploading(true);
    try {
      const res = await driverApi.uploadJobPhotos(id, files, "after");
      setAfterUploadedUrls((prev) => [...prev, ...res.urls]);
      setAfterPhotos([]);
      setSuccessBanner("After photos uploaded successfully.");
    } catch (err: unknown) {
      const message = err instanceof ApiError ? err.message : "Failed to upload photos.";
      setError(message);
    } finally {
      setAfterUploading(false);
    }
  }

  async function handleCompleteJob() {
    await handleStatusUpdate("completed", "Job completed! Great work.");
    setCompleteModalOpen(false);
  }

  // ---------------------------------------------------------------------------
  // Loading Skeleton
  // ---------------------------------------------------------------------------

  if (loading) {
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
                    {formatPrice(job.total_price)}
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
            disabled={transitioning}
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
                    {itemsCount} item{itemsCount !== 1 ? "s" : ""} &middot; {formatPrice(job.total_price)}
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
            disabled={transitioning}
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
                existingUrls={beforeUploadedUrls}
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
                  <p className="font-bold text-emerald-700">{formatPrice(job.total_price)}</p>
                  <p className="text-muted-foreground text-xs">
                    {itemsCount} item{itemsCount !== 1 ? "s" : ""}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Action: Start Job */}
          <Button
            onClick={() => handleStatusUpdate("in_progress", "Job started. Timer running.")}
            disabled={transitioning}
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
                existingUrls={afterUploadedUrls}
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
                  {formatPrice(job.total_price)}
                </p>
              </div>
            </CardContent>
          </Card>

          {/* Action: Complete Job (with confirmation) */}
          <Button
            onClick={() => setCompleteModalOpen(true)}
            disabled={transitioning}
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
            onCancel={() => setCompleteModalOpen(false)}
            loading={transitioning}
          />
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
                  Great work. Your payout is being processed.
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
                    {job.total_price.toFixed(2)}
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
