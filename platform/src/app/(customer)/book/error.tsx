"use client";

import * as Sentry from "@sentry/nextjs";
import { useEffect } from "react";

export default function BookError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    Sentry.captureException(error);
  }, [error]);

  return (
    <div className="max-w-3xl mx-auto px-4 py-12">
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 space-y-4">
        <h2 className="text-lg font-bold text-destructive">
          Booking Page Error
        </h2>
        <p className="text-sm text-destructive/80">
          Something went wrong loading the booking page. Please try again.
        </p>
        <button
          onClick={reset}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium"
        >
          Try Again
        </button>
      </div>
    </div>
  );
}
