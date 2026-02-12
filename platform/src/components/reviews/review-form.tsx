"use client";

import { useState } from "react";
import { Star } from "lucide-react";
import { reviewsApi, type ReviewRecord } from "@/lib/api";
import { trackEvent } from "@/lib/posthog";

interface ReviewFormProps {
  jobId: string;
  onReviewSubmitted?: (review: ReviewRecord) => void;
}

export function ReviewForm({ jobId, onReviewSubmitted }: ReviewFormProps) {
  const [rating, setRating] = useState(0);
  const [hoveredRating, setHoveredRating] = useState(0);
  const [comment, setComment] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = async () => {
    if (rating === 0) {
      setError("Please select a rating");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const res = await reviewsApi.create(
        jobId,
        rating,
        comment.trim() || undefined
      );
      trackEvent("review_submitted", { job_id: jobId, rating });
      onReviewSubmitted?.(res.review);
    } catch (err: unknown) {
      const msg =
        err instanceof Error ? err.message : "Failed to submit review";
      setError(msg);
    } finally {
      setIsSubmitting(false);
    }
  };

  const displayRating = hoveredRating || rating;

  return (
    <div className="rounded-lg border bg-white p-5">
      <h3 className="text-base font-semibold text-gray-900 mb-3">
        Rate Your Experience
      </h3>

      {/* Star rating */}
      <div className="flex gap-1 mb-3">
        {[1, 2, 3, 4, 5].map((star) => (
          <button
            key={star}
            type="button"
            onClick={() => setRating(star)}
            onMouseEnter={() => setHoveredRating(star)}
            onMouseLeave={() => setHoveredRating(0)}
            className="p-0.5 transition-transform hover:scale-110"
            aria-label={`${star} star${star > 1 ? "s" : ""}`}
          >
            <Star
              className={`h-7 w-7 ${
                star <= displayRating
                  ? "fill-yellow-400 text-yellow-400"
                  : "text-gray-300"
              }`}
            />
          </button>
        ))}
        {rating > 0 && (
          <span className="ml-2 text-sm text-gray-500 self-center">
            {rating}/5
          </span>
        )}
      </div>

      {/* Comment */}
      <textarea
        value={comment}
        onChange={(e) => setComment(e.target.value)}
        placeholder="Tell us about your experience (optional)"
        rows={3}
        className="w-full rounded-md border border-gray-200 px-3 py-2 text-sm placeholder:text-gray-400 focus:border-emerald-500 focus:ring-1 focus:ring-emerald-500 resize-none"
      />

      {error && <p className="text-sm text-red-600 mt-1">{error}</p>}

      <button
        onClick={handleSubmit}
        disabled={isSubmitting || rating === 0}
        className="mt-3 w-full rounded-md bg-emerald-600 px-4 py-2 text-sm font-medium text-white hover:bg-emerald-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
      >
        {isSubmitting ? "Submitting..." : "Submit Review"}
      </button>
    </div>
  );
}
