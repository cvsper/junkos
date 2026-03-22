"use client";

import { useState, useEffect } from "react";
import { Star, X } from "lucide-react";
import { Button } from "@/components/ui/button";

const REVIEW_DISMISSED_PREFIX = "umuve_review_dismissed_";
const GOOGLE_REVIEW_URL = "https://g.page/umuve/review";

interface ReviewPromptProps {
  bookingId: string;
}

export function ReviewPrompt({ bookingId }: ReviewPromptProps) {
  const [dismissed, setDismissed] = useState(true);

  useEffect(() => {
    // Check if already dismissed for this booking
    const key = `${REVIEW_DISMISSED_PREFIX}${bookingId}`;
    const wasDismissed = localStorage.getItem(key);
    setDismissed(!!wasDismissed);
  }, [bookingId]);

  const handleDismiss = () => {
    const key = `${REVIEW_DISMISSED_PREFIX}${bookingId}`;
    localStorage.setItem(key, "1");
    setDismissed(true);
  };

  const handleLeaveReview = () => {
    // Mark as dismissed so it won't show again
    const key = `${REVIEW_DISMISSED_PREFIX}${bookingId}`;
    localStorage.setItem(key, "1");
    window.open(GOOGLE_REVIEW_URL, "_blank", "noopener,noreferrer");
    setDismissed(true);
  };

  if (dismissed || !bookingId) return null;

  return (
    <div className="w-full max-w-sm rounded-lg border border-amber-200 bg-amber-50 p-5 space-y-3 relative">
      <button
        onClick={handleDismiss}
        className="absolute top-3 right-3 text-amber-400 hover:text-amber-600 transition-colors"
        aria-label="Dismiss"
      >
        <X className="h-4 w-4" />
      </button>

      <div className="flex items-center gap-2">
        <Star className="h-5 w-5 text-amber-500 fill-amber-500" />
        <Star className="h-5 w-5 text-amber-500 fill-amber-500" />
        <Star className="h-5 w-5 text-amber-500 fill-amber-500" />
        <Star className="h-5 w-5 text-amber-500 fill-amber-500" />
        <Star className="h-5 w-5 text-amber-500 fill-amber-500" />
      </div>

      <p className="text-sm text-amber-900 font-medium">
        How was your Umuve experience?
      </p>
      <p className="text-xs text-amber-700">
        A quick Google review helps us serve more neighbors like you.
      </p>

      <div className="flex items-center gap-3 pt-1">
        <Button
          size="sm"
          onClick={handleLeaveReview}
          className="bg-amber-600 hover:bg-amber-700 text-white"
        >
          Leave a Review
        </Button>
        <button
          onClick={handleDismiss}
          className="text-sm text-amber-600 hover:text-amber-800 transition-colors"
        >
          Maybe Later
        </button>
      </div>
    </div>
  );
}
