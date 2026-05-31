"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, Gift, RotateCcw, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useBookingStore } from "@/stores/booking-store";
import { referralsApi } from "@/lib/api";
import { trackBookingStep, trackLead, trackInitiateCheckout } from "@/components/analytics";
import { ProgressBar } from "@/components/booking/progress-bar";
import { Step1Address } from "@/components/booking/step-1-address";
import { Step2Photos } from "@/components/booking/step-2-photos";
import { Step3Items } from "@/components/booking/step-3-items";
import { Step4Schedule } from "@/components/booking/step-4-schedule";
import { Step5Estimate } from "@/components/booking/step-5-estimate";
import { Step6Payment } from "@/components/booking/step-6-payment";

// ---------------------------------------------------------------------------
// Lead source detection helpers
// ---------------------------------------------------------------------------

function detectLeadSource(searchParams: URLSearchParams): string {
  // 1. Check UTM params
  const utmSource = searchParams.get("utm_source");
  if (utmSource) return utmSource;

  // 2. Check shorthand src param
  const src = searchParams.get("src");
  if (src) return src;

  // 3. Check document.referrer
  if (typeof document !== "undefined" && document.referrer) {
    const ref = document.referrer.toLowerCase();
    if (ref.includes("google")) return "google";
    if (ref.includes("facebook") || ref.includes("fb.com")) return "facebook";
    if (ref.includes("nextdoor")) return "nextdoor";
    if (ref.includes("craigslist")) return "craigslist";
  }

  // 4. Check localStorage fallback
  if (typeof localStorage !== "undefined") {
    const stored = localStorage.getItem("umuve_lead_source");
    if (stored) return stored;
  }

  return "";
}

// ---------------------------------------------------------------------------
// Abandoned booking helpers
// ---------------------------------------------------------------------------

const ABANDONED_BOOKING_KEY = "umuve_abandoned_booking";
const ONE_HOUR_MS = 60 * 60 * 1000;
const SEVEN_DAYS_MS = 7 * 24 * 60 * 60 * 1000;

interface AbandonedBooking {
  step: number;
  timestamp: number;
  address: Record<string, unknown>;
  items: unknown[];
  scheduledDate: string;
  scheduledTimeSlot: string;
  notes: string;
}

function getAbandonedBooking(): AbandonedBooking | null {
  try {
    const raw = localStorage.getItem(ABANDONED_BOOKING_KEY);
    if (!raw) return null;
    const data = JSON.parse(raw) as AbandonedBooking;
    const age = Date.now() - data.timestamp;
    if (age > ONE_HOUR_MS && age < SEVEN_DAYS_MS) return data;
    // Too old or too recent — clear it
    if (age >= SEVEN_DAYS_MS) localStorage.removeItem(ABANDONED_BOOKING_KEY);
    return null;
  } catch {
    return null;
  }
}

function saveAbandonedBooking(state: {
  step: number;
  address: Record<string, unknown>;
  items: unknown[];
  scheduledDate: string;
  scheduledTimeSlot: string;
  notes: string;
}) {
  try {
    const data: AbandonedBooking = { ...state, timestamp: Date.now() };
    localStorage.setItem(ABANDONED_BOOKING_KEY, JSON.stringify(data));
  } catch {
    // Silently fail if localStorage is full
  }
}

// Exported from booking store for use in step-6-payment
function clearAbandonedBooking() {
  try {
    localStorage.removeItem(ABANDONED_BOOKING_KEY);
  } catch {
    // noop
  }
}

// ---------------------------------------------------------------------------
// Inner component that uses useSearchParams (requires Suspense boundary)
// ---------------------------------------------------------------------------

function BookPageInner() {
  const step = useBookingStore((s) => s.step);
  const nextStep = useBookingStore((s) => s.nextStep);
  const prevStep = useBookingStore((s) => s.prevStep);
  const setStep = useBookingStore((s) => s.setStep);
  const setAddress = useBookingStore((s) => s.setAddress);
  const setItems = useBookingStore((s) => s.setItems);
  const setSchedule = useBookingStore((s) => s.setSchedule);
  const setNotes = useBookingStore((s) => s.setNotes);
  const setLeadSource = useBookingStore((s) => s.setLeadSource);
  const searchParams = useSearchParams();

  // Referral banner state
  const [referrerName, setReferrerName] = useState<string | null>(null);

  // Abandoned booking banner state
  const [abandonedBooking, setAbandonedBooking] = useState<AbandonedBooking | null>(null);

  // --- Track booking funnel step in GA4 ---
  useEffect(() => {
    trackBookingStep(step);
    // Step 6 = payment. Fire Meta InitiateCheckout — the campaign's early
    // optimization event before Purchase volume is high enough.
    if (step === 6) {
      trackInitiateCheckout();
    }
  }, [step]);

  // --- Lead source auto-detection ---
  useEffect(() => {
    const source = detectLeadSource(searchParams);
    if (source) {
      setLeadSource(source);
      localStorage.setItem("umuve_lead_source", source);
    }
    trackLead();
  }, [searchParams, setLeadSource]);

  // --- Check for abandoned booking on mount ---
  useEffect(() => {
    const abandoned = getAbandonedBooking();
    if (abandoned) {
      setAbandonedBooking(abandoned);
    }
  }, []);

  // --- Save abandoned booking when step >= 3 ---
  const address = useBookingStore((s) => s.address);
  const items = useBookingStore((s) => s.items);
  const scheduledDate = useBookingStore((s) => s.scheduledDate);
  const scheduledTimeSlot = useBookingStore((s) => s.scheduledTimeSlot);
  const notes = useBookingStore((s) => s.notes);

  useEffect(() => {
    if (step >= 3) {
      saveAbandonedBooking({
        step,
        address: address as Record<string, unknown>,
        items: items as unknown[],
        scheduledDate,
        scheduledTimeSlot,
        notes,
      });
    }
  }, [step, address, items, scheduledDate, scheduledTimeSlot, notes]);

  // --- Resume abandoned booking ---
  const handleResumeAbandoned = useCallback(() => {
    if (!abandonedBooking) return;
    setAddress(abandonedBooking.address as Record<string, string>);
    setItems(abandonedBooking.items as Parameters<typeof setItems>[0]);
    if (abandonedBooking.scheduledDate && abandonedBooking.scheduledTimeSlot) {
      setSchedule(abandonedBooking.scheduledDate, abandonedBooking.scheduledTimeSlot);
    }
    if (abandonedBooking.notes) setNotes(abandonedBooking.notes);
    setStep(abandonedBooking.step);
    setAbandonedBooking(null);
  }, [abandonedBooking, setAddress, setItems, setSchedule, setNotes, setStep]);

  const handleDismissAbandoned = useCallback(() => {
    localStorage.removeItem(ABANDONED_BOOKING_KEY);
    setAbandonedBooking(null);
  }, []);

  // Check for ?ref= query param and store it
  useEffect(() => {
    const refCode = searchParams.get("ref");
    if (refCode) {
      // Store in localStorage for use during signup
      localStorage.setItem("umuve_referral_code", refCode.toUpperCase());

      // Validate the code and show referrer name
      referralsApi
        .validate(refCode)
        .then((res) => {
          setReferrerName(res.referrer_name);
        })
        .catch(() => {
          // Invalid code -- silently ignore
          localStorage.removeItem("umuve_referral_code");
        });
    } else {
      // Check if we already have a stored referral code
      const stored = localStorage.getItem("umuve_referral_code");
      if (stored) {
        referralsApi
          .validate(stored)
          .then((res) => setReferrerName(res.referrer_name))
          .catch(() => {
            localStorage.removeItem("umuve_referral_code");
          });
      }
    }
  }, [searchParams]);

  const handleNext = useCallback(() => {
    // Run step-specific validation before advancing
    switch (step) {
      case 1: {
        if (!Step1Address.validate()) return;
        break;
      }
      case 2:
        // Photos are optional, always allow progression
        break;
      case 3: {
        if (!Step3Items.validate()) return;
        break;
      }
      case 4: {
        if (!Step4Schedule.validate()) return;
        break;
      }
      case 5: {
        if (!Step5Estimate.validate()) return;
        break;
      }
      case 6:
        // Payment step handles its own submission
        return;
      default:
        break;
    }

    nextStep();
  }, [step, nextStep]);

  const handleBack = useCallback(() => {
    prevStep();
  }, [prevStep]);

  // On step 6 (payment), the step component manages its own submit button
  // so we hide the external navigation "Next" button
  const showNextButton = step < 6;
  const showBackButton = step > 1;

  return (
    <div className="max-w-3xl mx-auto px-4 py-8 sm:py-12">
      {/* Referral Banner */}
      {referrerName && (
        <div className="mb-6 flex items-center gap-3 rounded-lg border border-green-200 bg-green-50 px-4 py-3">
          <Gift className="h-5 w-5 text-green-600 flex-shrink-0" />
          <p className="text-sm text-green-800">
            <span className="font-semibold">{referrerName}</span> referred you!
            Sign up to get <span className="font-semibold">$10 off</span> your
            first pickup.
          </p>
        </div>
      )}

      {/* Abandoned Booking Banner */}
      {abandonedBooking && (
        <div className="mb-6 flex items-center justify-between gap-3 rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
          <div className="flex items-center gap-3">
            <RotateCcw className="h-5 w-5 text-amber-600 flex-shrink-0" />
            <p className="text-sm text-amber-800">
              You have an unfinished booking. Pick up where you left off?
            </p>
          </div>
          <div className="flex items-center gap-2 flex-shrink-0">
            <Button
              size="sm"
              variant="outline"
              onClick={handleResumeAbandoned}
              className="border-amber-300 text-amber-800 hover:bg-amber-100"
            >
              Resume
            </Button>
            <button
              onClick={handleDismissAbandoned}
              className="text-amber-400 hover:text-amber-600 transition-colors"
            >
              <X className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}

      {/* Heading */}
      <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mb-2">
        Book a Pickup
      </h1>
      <p className="text-muted-foreground mb-4">
        Schedule your junk removal in just a few steps.
      </p>

      {/* Progress Bar */}
      <div className="mb-10">
        <ProgressBar currentStep={step} />
      </div>

      {/* Step Content */}
      <div className="rounded-lg border border-border bg-card p-6 sm:p-8">
        {step === 1 && <Step1Address />}
        {step === 2 && <Step2Photos />}
        {step === 3 && <Step3Items />}
        {step === 4 && <Step4Schedule />}
        {step === 5 && <Step5Estimate />}
        {step === 6 && <Step6Payment />}
      </div>

      {/* Navigation Buttons */}
      <div className="flex items-center justify-between mt-8">
        <div>
          {showBackButton && (
            <Button
              variant="outline"
              onClick={handleBack}
              className="gap-2"
            >
              <ArrowLeft className="h-4 w-4" />
              Back
            </Button>
          )}
        </div>

        <div>
          {showNextButton && (
            <Button onClick={handleNext} className="gap-2">
              {step === 5 ? "Continue to Payment" : "Next"}
              <ArrowRight className="h-4 w-4" />
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Default export wraps with Suspense for useSearchParams compatibility
// ---------------------------------------------------------------------------

export default function BookPage() {
  return (
    <Suspense
      fallback={
        <div className="max-w-3xl mx-auto px-4 py-8 sm:py-12">
          <div className="flex items-center justify-center py-24">
            <svg
              className="h-8 w-8 animate-spin text-primary"
              xmlns="http://www.w3.org/2000/svg"
              fill="none"
              viewBox="0 0 24 24"
              aria-hidden="true"
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
              Loading...
            </span>
          </div>
        </div>
      }
    >
      <BookPageInner />
    </Suspense>
  );
}
