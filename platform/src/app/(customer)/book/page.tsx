"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { ArrowLeft, ArrowRight, Gift } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useBookingStore } from "@/stores/booking-store";
import { referralsApi } from "@/lib/api";
import { ProgressBar } from "@/components/booking/progress-bar";
import { Step1Address } from "@/components/booking/step-1-address";
import { Step2Photos } from "@/components/booking/step-2-photos";
import { Step3Items } from "@/components/booking/step-3-items";
import { Step4Schedule } from "@/components/booking/step-4-schedule";
import { Step5Estimate } from "@/components/booking/step-5-estimate";
import { Step6Payment } from "@/components/booking/step-6-payment";

// ---------------------------------------------------------------------------
// Inner component that uses useSearchParams (requires Suspense boundary)
// ---------------------------------------------------------------------------

function BookPageInner() {
  const step = useBookingStore((s) => s.step);
  const nextStep = useBookingStore((s) => s.nextStep);
  const prevStep = useBookingStore((s) => s.prevStep);
  const searchParams = useSearchParams();

  // Referral banner state
  const [referrerName, setReferrerName] = useState<string | null>(null);

  // Check for ?ref= query param and store it
  useEffect(() => {
    const refCode = searchParams.get("ref");
    if (refCode) {
      // Store in localStorage for use during signup
      localStorage.setItem("junkos_referral_code", refCode.toUpperCase());

      // Validate the code and show referrer name
      referralsApi
        .validate(refCode)
        .then((res) => {
          setReferrerName(res.referrer_name);
        })
        .catch(() => {
          // Invalid code -- silently ignore
          localStorage.removeItem("junkos_referral_code");
        });
    } else {
      // Check if we already have a stored referral code
      const stored = localStorage.getItem("junkos_referral_code");
      if (stored) {
        referralsApi
          .validate(stored)
          .then((res) => setReferrerName(res.referrer_name))
          .catch(() => {
            localStorage.removeItem("junkos_referral_code");
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

      {/* Heading */}
      <h1 className="font-display text-3xl sm:text-4xl font-bold tracking-tight mb-2">
        Book a Pickup
      </h1>
      <p className="text-muted-foreground mb-8">
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
