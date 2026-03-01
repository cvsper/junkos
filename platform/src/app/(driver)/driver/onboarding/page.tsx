"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { driverApi, ApiError } from "@/lib/api";
import { useAuthStore } from "@/stores/auth-store";
import type { DriverOnboardingStatus } from "@/types";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const STEPS = ["Profile", "Documents", "Stripe", "Review"] as const;

const TRUCK_TYPES = [
  "Pickup Truck",
  "Box Truck",
  "Flatbed",
  "Van",
  "Dump Truck",
  "Other",
] as const;

// ---------------------------------------------------------------------------
// Shared UI helpers
// ---------------------------------------------------------------------------

function Spinner({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg
      className={`animate-spin ${className}`}
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
        d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
      />
    </svg>
  );
}

function CheckIcon({ className = "h-4 w-4" }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={2.5}
      stroke="currentColor"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
    </svg>
  );
}

function UploadIcon({ className = "h-8 w-8" }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"
      />
    </svg>
  );
}

function ClockIcon({ className = "h-12 w-12" }: { className?: string }) {
  return (
    <svg
      className={className}
      fill="none"
      viewBox="0 0 24 24"
      strokeWidth={1.5}
      stroke="currentColor"
    >
      <path
        strokeLinecap="round"
        strokeLinejoin="round"
        d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"
      />
    </svg>
  );
}

// ---------------------------------------------------------------------------
// Stepper
// ---------------------------------------------------------------------------

function Stepper({
  currentStep,
  completedSteps,
}: {
  currentStep: number;
  completedSteps: boolean[];
}) {
  return (
    <div className="flex items-center justify-center gap-0">
      {STEPS.map((label, idx) => {
        const isActive = idx === currentStep;
        const isCompleted = completedSteps[idx];

        return (
          <div key={label} className="flex items-center">
            {/* Step circle */}
            <div className="flex flex-col items-center">
              <div
                className={`flex h-9 w-9 items-center justify-center rounded-full text-sm font-semibold transition-colors ${
                  isCompleted
                    ? "bg-emerald-100 text-emerald-700"
                    : isActive
                    ? "bg-emerald-600 text-white"
                    : "bg-muted text-muted-foreground"
                }`}
              >
                {isCompleted ? <CheckIcon className="h-4 w-4" /> : idx + 1}
              </div>
              <span
                className={`mt-1.5 text-xs font-medium ${
                  isActive
                    ? "text-emerald-700"
                    : isCompleted
                    ? "text-emerald-600"
                    : "text-muted-foreground"
                }`}
              >
                {label}
              </span>
            </div>

            {/* Connector line */}
            {idx < STEPS.length - 1 && (
              <div
                className={`mx-2 mt-[-1rem] h-0.5 w-10 sm:w-16 ${
                  completedSteps[idx] ? "bg-emerald-400" : "bg-muted"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Drop Zone
// ---------------------------------------------------------------------------

function DropZone({
  label,
  file,
  existingUrl,
  onFile,
}: {
  label: string;
  file: File | null;
  existingUrl: string | null;
  onFile: (f: File) => void;
}) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [dragOver, setDragOver] = useState(false);

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setDragOver(false);
    const dropped = e.dataTransfer.files[0];
    if (dropped) onFile(dropped);
  };

  const hasFile = file !== null;
  const hasExisting = existingUrl !== null && !hasFile;

  return (
    <div
      className={`relative rounded-lg border-2 border-dashed p-6 text-center transition-colors cursor-pointer ${
        dragOver
          ? "border-emerald-500 bg-emerald-50"
          : hasFile || hasExisting
          ? "border-emerald-400 bg-emerald-50/50"
          : "border-border hover:border-muted-foreground/40"
      }`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={handleDrop}
      onClick={() => inputRef.current?.click()}
    >
      <input
        ref={inputRef}
        type="file"
        accept="image/*,application/pdf"
        className="hidden"
        onChange={(e) => {
          const f = e.target.files?.[0];
          if (f) onFile(f);
        }}
      />

      {hasFile ? (
        <div className="flex items-center justify-center gap-2">
          <CheckIcon className="h-5 w-5 text-emerald-600" />
          <span className="text-sm font-medium text-emerald-700 truncate max-w-[200px]">
            {file.name}
          </span>
        </div>
      ) : hasExisting ? (
        <div className="flex items-center justify-center gap-2">
          <CheckIcon className="h-5 w-5 text-emerald-600" />
          <span className="text-sm font-medium text-emerald-700">
            Already uploaded
          </span>
          <span className="text-xs text-muted-foreground">(click to replace)</span>
        </div>
      ) : (
        <>
          <UploadIcon className="mx-auto h-8 w-8 text-muted-foreground" />
          <p className="mt-2 text-sm text-muted-foreground">
            Drag &amp; drop or click to upload
          </p>
        </>
      )}

      <p className="mt-1 text-xs font-medium text-muted-foreground">{label}</p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page Component
// ---------------------------------------------------------------------------

export default function DriverOnboardingPage() {
  const router = useRouter();
  const user = useAuthStore((s) => s.user);

  // Wizard state
  const [step, setStep] = useState(0);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Onboarding status from API
  const [onboarding, setOnboarding] = useState<DriverOnboardingStatus | null>(null);

  // Step 1: Profile
  const [name, setName] = useState("");
  const [phone, setPhone] = useState("");
  const [truckType, setTruckType] = useState("");

  // Step 2: Documents
  const [license, setLicense] = useState<File | null>(null);
  const [insurance, setInsurance] = useState<File | null>(null);
  const [registration, setRegistration] = useState<File | null>(null);

  // Step 3: Stripe
  const [stripeConnected, setStripeConnected] = useState(false);
  const [stripePolling, setStripePolling] = useState(false);

  // Step 4: Review
  const [submitted, setSubmitted] = useState(false);

  // Completed-steps derivation
  const completedSteps = [
    onboarding?.profile_complete ?? false,
    onboarding?.documents_uploaded ?? false,
    onboarding?.stripe_connected ?? false,
    onboarding?.submitted_for_review ?? false,
  ];

  // -------------------------------------------------------------------------
  // Load onboarding status on mount
  // -------------------------------------------------------------------------

  const loadStatus = useCallback(async () => {
    try {
      const res = await driverApi.onboardingStatus();
      const ob = res.onboarding;
      setOnboarding(ob);

      // Seed profile fields from auth store
      setName(user?.name ?? "");
      setPhone(user?.phone ?? "");

      // Stripe
      setStripeConnected(ob.stripe_connected);

      // Submitted state
      setSubmitted(ob.submitted_for_review);

      // Redirect if already approved
      if (ob.approval_status === "approved") {
        router.replace("/driver");
        return;
      }

      // Resume from correct step
      if (ob.submitted_for_review) {
        setStep(3);
      } else if (ob.stripe_connected) {
        setStep(3);
      } else if (ob.documents_uploaded) {
        setStep(2);
      } else if (ob.profile_complete) {
        setStep(1);
      } else {
        setStep(0);
      }
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else {
        setError("Failed to load onboarding status.");
      }
    } finally {
      setLoading(false);
    }
  }, [user, router]);

  useEffect(() => {
    loadStatus();
  }, [loadStatus]);

  // -------------------------------------------------------------------------
  // Stripe polling
  // -------------------------------------------------------------------------

  useEffect(() => {
    if (!stripePolling) return;

    const interval = setInterval(async () => {
      try {
        const res = await driverApi.stripeStatus();
        if (res.connected && res.details_submitted) {
          setStripeConnected(true);
          setStripePolling(false);
          setOnboarding((prev) =>
            prev ? { ...prev, stripe_connected: true } : prev
          );
        }
      } catch {
        // Silently retry
      }
    }, 3000);

    return () => clearInterval(interval);
  }, [stripePolling]);

  // -------------------------------------------------------------------------
  // Step handlers
  // -------------------------------------------------------------------------

  const handleProfileSave = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await driverApi.updateProfile({
        name: name.trim(),
        phone: phone.trim(),
        truck_type: truckType,
      });
      setOnboarding((prev) =>
        prev ? { ...prev, profile_complete: true } : prev
      );
      setStep(1);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to save profile.");
    } finally {
      setSubmitting(false);
    }
  };

  const handleDocumentUpload = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const files: {
        drivers_license?: File;
        insurance?: File;
        vehicle_registration?: File;
      } = {};
      if (license) files.drivers_license = license;
      if (insurance) files.insurance = insurance;
      if (registration) files.vehicle_registration = registration;

      // Require at least one new file if none exist
      const hasExisting =
        onboarding?.drivers_license_url ||
        onboarding?.insurance_document_url ||
        onboarding?.vehicle_registration_url;
      if (Object.keys(files).length === 0 && !hasExisting) {
        setError("Please upload at least one document.");
        setSubmitting(false);
        return;
      }

      if (Object.keys(files).length > 0) {
        await driverApi.uploadDocuments(files);
      }

      setOnboarding((prev) =>
        prev ? { ...prev, documents_uploaded: true } : prev
      );
      setStep(2);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to upload documents."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleStripeConnect = async () => {
    setSubmitting(true);
    setError(null);
    try {
      const res = await driverApi.stripeConnect();
      window.open(res.url, "_blank");
      setStripePolling(true);
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to start Stripe Connect."
      );
    } finally {
      setSubmitting(false);
    }
  };

  const handleSubmitApplication = async () => {
    setSubmitting(true);
    setError(null);
    try {
      await driverApi.submitOnboarding();
      setSubmitted(true);
      setOnboarding((prev) =>
        prev ? { ...prev, submitted_for_review: true } : prev
      );
    } catch (err) {
      setError(
        err instanceof ApiError ? err.message : "Failed to submit application."
      );
    } finally {
      setSubmitting(false);
    }
  };

  // -------------------------------------------------------------------------
  // Loading state
  // -------------------------------------------------------------------------

  if (loading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-background">
        <Spinner className="h-8 w-8 text-emerald-600" />
      </div>
    );
  }

  // -------------------------------------------------------------------------
  // Rejected state
  // -------------------------------------------------------------------------

  const isRejected = onboarding?.approval_status === "rejected";

  // -------------------------------------------------------------------------
  // Under Review state (submitted and pending)
  // -------------------------------------------------------------------------

  const isUnderReview =
    submitted &&
    onboarding?.approval_status !== "rejected" &&
    onboarding?.approval_status !== "approved";

  // -------------------------------------------------------------------------
  // Render
  // -------------------------------------------------------------------------

  return (
    <div className="min-h-screen bg-background">
      {/* Top Bar */}
      <header className="border-b bg-card">
        <div className="mx-auto flex h-14 max-w-3xl items-center justify-between px-4">
          <Link href="/" className="flex items-center gap-2">
            <img
              src="/logo-login.png"
              alt="Umuve"
              className="h-8 w-auto object-contain"
            />
          </Link>
          <Link
            href="/login"
            className="text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Back to Login
          </Link>
        </div>
      </header>

      <main className="mx-auto max-w-2xl px-4 py-8">
        {/* Page Title */}
        <div className="text-center mb-8">
          <h1 className="text-2xl font-bold tracking-tight">Driver Onboarding</h1>
          <p className="text-muted-foreground text-sm mt-1">
            Complete each step to start accepting jobs
          </p>
        </div>

        {/* Stepper */}
        <div className="mb-10">
          <Stepper currentStep={step} completedSteps={completedSteps} />
        </div>

        {/* Inline Error */}
        {error && (
          <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* Step 1: Profile Confirmation                                      */}
        {/* ----------------------------------------------------------------- */}
        {step === 0 && (
          <section className="rounded-lg border bg-card p-6 shadow-sm">
            <h2 className="text-lg font-semibold mb-4">Confirm Your Profile</h2>
            <div className="space-y-4">
              <div>
                <label
                  htmlFor="ob-name"
                  className="block text-sm font-medium mb-1.5"
                >
                  Full Name
                </label>
                <input
                  id="ob-name"
                  type="text"
                  value={name}
                  onChange={(e) => setName(e.target.value)}
                  placeholder="Your full name"
                  required
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-colors"
                />
              </div>

              <div>
                <label
                  htmlFor="ob-email"
                  className="block text-sm font-medium mb-1.5"
                >
                  Email
                </label>
                <input
                  id="ob-email"
                  type="email"
                  value={user?.email ?? ""}
                  disabled
                  className="w-full rounded-lg border border-border bg-muted px-3 py-2.5 text-sm text-muted-foreground cursor-not-allowed"
                />
              </div>

              <div>
                <label
                  htmlFor="ob-phone"
                  className="block text-sm font-medium mb-1.5"
                >
                  Phone Number
                </label>
                <input
                  id="ob-phone"
                  type="tel"
                  value={phone}
                  onChange={(e) => setPhone(e.target.value)}
                  placeholder="(555) 123-4567"
                  required
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-colors"
                />
              </div>

              <div>
                <label
                  htmlFor="ob-truck"
                  className="block text-sm font-medium mb-1.5"
                >
                  Truck Type
                </label>
                <select
                  id="ob-truck"
                  value={truckType}
                  onChange={(e) => setTruckType(e.target.value)}
                  required
                  className="w-full rounded-lg border border-border bg-background px-3 py-2.5 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:border-transparent transition-colors"
                >
                  <option value="" disabled>
                    Select truck type
                  </option>
                  {TRUCK_TYPES.map((t) => (
                    <option key={t} value={t}>
                      {t}
                    </option>
                  ))}
                </select>
              </div>
            </div>

            <button
              type="button"
              disabled={submitting || !name.trim() || !phone.trim() || !truckType}
              onClick={handleProfileSave}
              className="mt-6 w-full rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
            >
              {submitting && <Spinner />}
              {submitting ? "Saving..." : "Save & Continue"}
            </button>
          </section>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* Step 2: Document Uploads                                          */}
        {/* ----------------------------------------------------------------- */}
        {step === 1 && (
          <section className="rounded-lg border bg-card p-6 shadow-sm">
            <h2 className="text-lg font-semibold mb-1">Upload Documents</h2>
            <p className="text-sm text-muted-foreground mb-6">
              We need these to verify your identity and vehicle. Accepted formats:
              images or PDF.
            </p>

            <div className="space-y-4">
              <DropZone
                label="Driver's License"
                file={license}
                existingUrl={onboarding?.drivers_license_url ?? null}
                onFile={setLicense}
              />
              <DropZone
                label="Insurance Certificate"
                file={insurance}
                existingUrl={onboarding?.insurance_document_url ?? null}
                onFile={setInsurance}
              />
              <DropZone
                label="Vehicle Registration"
                file={registration}
                existingUrl={onboarding?.vehicle_registration_url ?? null}
                onFile={setRegistration}
              />
            </div>

            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={() => setStep(0)}
                className="rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-medium hover:bg-muted transition-colors"
              >
                Back
              </button>
              <button
                type="button"
                disabled={submitting}
                onClick={handleDocumentUpload}
                className="flex-1 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
              >
                {submitting && <Spinner />}
                {submitting ? "Uploading..." : "Upload & Continue"}
              </button>
            </div>
          </section>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* Step 3: Stripe Connect                                            */}
        {/* ----------------------------------------------------------------- */}
        {step === 2 && (
          <section className="rounded-lg border bg-card p-6 shadow-sm">
            <h2 className="text-lg font-semibold mb-1">Set Up Payments</h2>
            <p className="text-sm text-muted-foreground mb-6">
              We use Stripe to process payments securely. Connect your account to
              receive payouts for completed jobs directly to your bank account.
            </p>

            {stripeConnected ? (
              <div className="flex items-center justify-center gap-2 rounded-lg bg-emerald-50 border border-emerald-200 px-4 py-4">
                <CheckIcon className="h-5 w-5 text-emerald-600" />
                <span className="text-sm font-medium text-emerald-700">
                  Stripe account connected
                </span>
              </div>
            ) : (
              <>
                <button
                  type="button"
                  disabled={submitting}
                  onClick={handleStripeConnect}
                  className="w-full rounded-lg bg-[#635BFF] px-4 py-2.5 text-sm font-medium text-white hover:bg-[#5147e5] transition-colors focus:outline-none focus:ring-2 focus:ring-[#635BFF] focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                >
                  {submitting && <Spinner />}
                  {submitting ? "Connecting..." : "Connect with Stripe"}
                </button>

                {stripePolling && (
                  <div className="mt-4 flex items-center justify-center gap-2 text-sm text-muted-foreground">
                    <Spinner />
                    <span>Waiting for Stripe confirmation...</span>
                  </div>
                )}
              </>
            )}

            <div className="mt-6 flex gap-3">
              <button
                type="button"
                onClick={() => setStep(1)}
                className="rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-medium hover:bg-muted transition-colors"
              >
                Back
              </button>
              <button
                type="button"
                disabled={!stripeConnected}
                onClick={() => setStep(3)}
                className="flex-1 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed"
              >
                Continue
              </button>
            </div>
          </section>
        )}

        {/* ----------------------------------------------------------------- */}
        {/* Step 4: Review & Submit                                           */}
        {/* ----------------------------------------------------------------- */}
        {step === 3 && (
          <section className="rounded-lg border bg-card p-6 shadow-sm">
            {/* -- Under Review state -- */}
            {isUnderReview && (
              <div className="text-center py-6">
                <ClockIcon className="mx-auto h-12 w-12 text-amber-500" />
                <h2 className="mt-4 text-lg font-semibold">
                  Application Under Review
                </h2>
                <p className="mt-2 text-sm text-muted-foreground max-w-sm mx-auto">
                  Your application has been submitted and is being reviewed by our
                  team. We will notify you once a decision is made.
                </p>
              </div>
            )}

            {/* -- Rejected state -- */}
            {isRejected && (
              <div className="text-center py-4">
                <div className="mx-auto flex h-12 w-12 items-center justify-center rounded-full bg-red-100">
                  <svg
                    className="h-6 w-6 text-red-600"
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
                </div>
                <h2 className="mt-4 text-lg font-semibold text-red-700">
                  Application Rejected
                </h2>
                {onboarding?.rejection_reason && (
                  <p className="mt-2 text-sm text-red-600 max-w-sm mx-auto">
                    Reason: {onboarding.rejection_reason}
                  </p>
                )}
                <p className="mt-3 text-sm text-muted-foreground">
                  You can re-upload your documents and try again.
                </p>
                <button
                  type="button"
                  onClick={() => {
                    setSubmitted(false);
                    setOnboarding((prev) =>
                      prev
                        ? { ...prev, submitted_for_review: false, documents_uploaded: false }
                        : prev
                    );
                    setStep(1);
                  }}
                  className="mt-4 inline-flex rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 transition-colors"
                >
                  Re-upload Documents
                </button>
              </div>
            )}

            {/* -- Ready to submit state -- */}
            {!isUnderReview && !isRejected && (
              <>
                <h2 className="text-lg font-semibold mb-4">
                  Review Your Application
                </h2>
                <p className="text-sm text-muted-foreground mb-6">
                  Everything looks good! Review your progress below and submit your
                  application for review.
                </p>

                <div className="space-y-3">
                  {[
                    {
                      label: "Profile information",
                      done: completedSteps[0],
                    },
                    {
                      label: "Documents uploaded",
                      done: completedSteps[1],
                    },
                    {
                      label: "Stripe connected",
                      done: completedSteps[2],
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="flex items-center gap-3 rounded-lg border px-4 py-3"
                    >
                      <div
                        className={`flex h-6 w-6 items-center justify-center rounded-full ${
                          item.done
                            ? "bg-emerald-100 text-emerald-700"
                            : "bg-muted text-muted-foreground"
                        }`}
                      >
                        {item.done ? (
                          <CheckIcon className="h-3.5 w-3.5" />
                        ) : (
                          <span className="text-xs">-</span>
                        )}
                      </div>
                      <span
                        className={`text-sm ${
                          item.done ? "font-medium" : "text-muted-foreground"
                        }`}
                      >
                        {item.label}
                      </span>
                    </div>
                  ))}
                </div>

                <div className="mt-6 flex gap-3">
                  <button
                    type="button"
                    onClick={() => setStep(2)}
                    className="rounded-lg border border-border bg-background px-4 py-2.5 text-sm font-medium hover:bg-muted transition-colors"
                  >
                    Back
                  </button>
                  <button
                    type="button"
                    disabled={
                      submitting ||
                      !completedSteps[0] ||
                      !completedSteps[1] ||
                      !completedSteps[2]
                    }
                    onClick={handleSubmitApplication}
                    className="flex-1 rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white hover:bg-emerald-700 transition-colors focus:outline-none focus:ring-2 focus:ring-emerald-500 focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
                  >
                    {submitting && <Spinner />}
                    {submitting ? "Submitting..." : "Submit Application"}
                  </button>
                </div>
              </>
            )}
          </section>
        )}
      </main>
    </div>
  );
}
