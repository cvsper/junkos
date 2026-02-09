"use client";

import { Check } from "lucide-react";
import { cn } from "@/lib/utils";
import type { JobStatus } from "@/types";

// -----------------------------------------------------------------------
// Status steps in order
// -----------------------------------------------------------------------

interface StatusStep {
  key: JobStatus;
  label: string;
  description?: string;
}

const STEPS: StatusStep[] = [
  { key: "pending", label: "Booked", description: "Your pickup is confirmed" },
  { key: "assigned", label: "Assigned", description: "A crew has been assigned" },
  { key: "en_route", label: "En Route", description: "Crew is on the way" },
  { key: "arrived", label: "Arrived", description: "Crew is at your location" },
  { key: "in_progress", label: "In Progress", description: "Loading your items" },
  { key: "completed", label: "Completed", description: "Pickup complete" },
];

// Map each status to its index so we can determine completed/active/future
const STATUS_INDEX: Record<string, number> = {};
STEPS.forEach((s, i) => {
  STATUS_INDEX[s.key] = i;
});

// "confirmed" maps to the same visual position as "pending" (booked)
STATUS_INDEX["confirmed"] = 0;

// -----------------------------------------------------------------------
// Component
// -----------------------------------------------------------------------

interface StatusTimelineProps {
  currentStatus: JobStatus | null;
  timestamps?: Partial<Record<JobStatus, string>>;
}

export default function StatusTimeline({
  currentStatus,
  timestamps,
}: StatusTimelineProps) {
  const currentIndex =
    currentStatus && currentStatus in STATUS_INDEX
      ? STATUS_INDEX[currentStatus]
      : -1;

  return (
    <div className="relative flex flex-col gap-0">
      {STEPS.map((step, index) => {
        const isCompleted = index < currentIndex;
        const isCurrent = index === currentIndex;
        const isLast = index === STEPS.length - 1;

        return (
          <div key={step.key} className="relative flex gap-3">
            {/* Vertical connector line */}
            {!isLast && (
              <div
                className={cn(
                  "absolute left-[11px] top-6 w-0.5 h-full",
                  isCompleted ? "bg-primary" : "bg-border"
                )}
                aria-hidden
              />
            )}

            {/* Circle indicator */}
            <div className="relative z-10 flex-shrink-0 mt-0.5">
              {isCompleted ? (
                <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center">
                  <Check className="w-3.5 h-3.5 text-primary-foreground" />
                </div>
              ) : isCurrent ? (
                <div className="w-6 h-6 rounded-full bg-primary flex items-center justify-center animate-pulse shadow-md shadow-primary/30">
                  <div className="w-2 h-2 rounded-full bg-primary-foreground" />
                </div>
              ) : (
                <div className="w-6 h-6 rounded-full bg-muted border-2 border-border" />
              )}
            </div>

            {/* Label + optional timestamp + description */}
            <div className="pb-6 min-w-0">
              <p
                className={cn(
                  "text-sm leading-6",
                  isCompleted || isCurrent
                    ? "text-foreground font-medium"
                    : "text-muted-foreground"
                )}
              >
                {step.label}
              </p>
              {timestamps?.[step.key] && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {formatTimestamp(timestamps[step.key]!)}
                </p>
              )}
              {isCurrent && !timestamps?.[step.key] && (
                <p className="text-xs text-primary mt-0.5 font-medium">
                  Current
                </p>
              )}
              {isCurrent && step.description && (
                <p className="text-xs text-muted-foreground mt-0.5">
                  {step.description}
                </p>
              )}
            </div>
          </div>
        );
      })}
    </div>
  );
}

// -----------------------------------------------------------------------
// Helpers
// -----------------------------------------------------------------------

function formatTimestamp(iso: string): string {
  try {
    const date = new Date(iso);
    return date.toLocaleTimeString([], {
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return iso;
  }
}
