"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";

const steps = [
  { number: 1, label: "Address" },
  { number: 2, label: "Photos" },
  { number: 3, label: "Items" },
  { number: 4, label: "Schedule" },
  { number: 5, label: "Estimate" },
  { number: 6, label: "Payment" },
];

interface ProgressBarProps {
  currentStep: number;
}

export function ProgressBar({ currentStep }: ProgressBarProps) {
  const progressPercent = ((currentStep - 1) / (steps.length - 1)) * 100;

  return (
    <div className="w-full">
      {/* Desktop: circles connected by lines */}
      <div className="hidden sm:block">
        <div className="relative flex items-center justify-between">
          {/* Connecting line (background) */}
          <div className="absolute left-0 right-0 top-1/2 -translate-y-1/2 h-0.5 bg-border z-0" />
          {/* Connecting line (progress) */}
          <div
            className="absolute left-0 top-1/2 -translate-y-1/2 h-0.5 bg-primary z-0 transition-all duration-500 ease-in-out"
            style={{ width: `${progressPercent}%` }}
          />

          {steps.map((step) => {
            const isCompleted = step.number < currentStep;
            const isCurrent = step.number === currentStep;
            const isFuture = step.number > currentStep;

            return (
              <div
                key={step.number}
                className="relative z-10 flex flex-col items-center"
              >
                <div
                  className={cn(
                    "w-10 h-10 rounded-full flex items-center justify-center text-sm font-semibold border-2 transition-all duration-300",
                    isCompleted &&
                      "bg-emerald-500 border-emerald-500 text-white",
                    isCurrent &&
                      "bg-primary border-primary text-primary-foreground shadow-md shadow-primary/25",
                    isFuture &&
                      "bg-background border-border text-muted-foreground"
                  )}
                >
                  {isCompleted ? (
                    <Check className="w-5 h-5" />
                  ) : (
                    step.number
                  )}
                </div>
                <span
                  className={cn(
                    "mt-2 text-xs font-medium transition-colors",
                    isCompleted && "text-emerald-600",
                    isCurrent && "text-primary font-semibold",
                    isFuture && "text-muted-foreground"
                  )}
                >
                  {step.label}
                </span>
              </div>
            );
          })}
        </div>
      </div>

      {/* Mobile: simple progress bar */}
      <div className="sm:hidden">
        <div className="flex items-center justify-between mb-2">
          <span className="text-sm font-semibold text-foreground">
            Step {currentStep} of {steps.length}
          </span>
          <span className="text-sm font-medium text-primary">
            {steps[currentStep - 1]?.label}
          </span>
        </div>
        <div className="h-2 bg-muted rounded-full overflow-hidden">
          <div
            className="h-full bg-primary rounded-full transition-all duration-500 ease-in-out"
            style={{ width: `${(currentStep / steps.length) * 100}%` }}
          />
        </div>
      </div>
    </div>
  );
}
