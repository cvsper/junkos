"use client";

import { Star } from "lucide-react";
import type { ReviewRecord } from "@/lib/api";

interface ReviewDisplayProps {
  review: ReviewRecord;
}

export function ReviewDisplay({ review }: ReviewDisplayProps) {
  const dateStr = review.created_at
    ? new Date(review.created_at).toLocaleDateString("en-US", {
        month: "short",
        day: "numeric",
        year: "numeric",
      })
    : "";

  return (
    <div className="rounded-lg border bg-white p-4">
      <div className="flex items-center justify-between mb-2">
        <div className="flex gap-0.5">
          {[1, 2, 3, 4, 5].map((star) => (
            <Star
              key={star}
              className={`h-4 w-4 ${
                star <= review.rating
                  ? "fill-yellow-400 text-yellow-400"
                  : "text-gray-200"
              }`}
            />
          ))}
        </div>
        <span className="text-xs text-gray-400">{dateStr}</span>
      </div>

      {review.comment && (
        <p className="text-sm text-gray-700 leading-relaxed">
          {review.comment}
        </p>
      )}

      <p className="text-xs text-gray-400 mt-2">
        {review.customer_name || "Customer"}
      </p>
    </div>
  );
}
