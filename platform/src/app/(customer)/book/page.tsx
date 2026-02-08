"use client";

import { useCallback } from "react";
import { ArrowLeft, ArrowRight } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useBookingStore } from "@/stores/booking-store";
import { ProgressBar } from "@/components/booking/progress-bar";
import { Step1Address } from "@/components/booking/step-1-address";
import { Step2Photos } from "@/components/booking/step-2-photos";
import { Step3Items } from "@/components/booking/step-3-items";
import { Step4Schedule } from "@/components/booking/step-4-schedule";
import { Step5Estimate } from "@/components/booking/step-5-estimate";
import { Step6Payment } from "@/components/booking/step-6-payment";

export default function BookPage() {
  const step = useBookingStore((s) => s.step);
  const nextStep = useBookingStore((s) => s.nextStep);
  const prevStep = useBookingStore((s) => s.prevStep);

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
