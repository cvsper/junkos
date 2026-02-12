"use client";

import { useEffect, useState, useCallback } from "react";
import { adminApi } from "@/lib/api";
import {
  Card,
  CardHeader,
  CardTitle,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Star, Loader2, AlertCircle, RefreshCw } from "lucide-react";

interface ReviewItem {
  id: string;
  job_id: string;
  customer_id: string;
  contractor_id: string;
  rating: number;
  comment: string | null;
  customer_name: string | null;
  created_at: string | null;
}

function StarRating({ rating }: { rating: number }) {
  return (
    <div className="flex gap-0.5">
      {[1, 2, 3, 4, 5].map((star) => (
        <Star
          key={star}
          className={`h-4 w-4 ${
            star <= rating
              ? "fill-yellow-400 text-yellow-400"
              : "text-gray-200"
          }`}
        />
      ))}
    </div>
  );
}

export default function AdminReviewsPage() {
  const [reviews, setReviews] = useState<ReviewItem[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [filterRating, setFilterRating] = useState<number | null>(null);

  const fetchReviews = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const params = new URLSearchParams();
      if (filterRating) params.append("rating", String(filterRating));
      const res = await adminApi.getReviews?.(filterRating ?? undefined);
      setReviews(res?.reviews || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load reviews");
    } finally {
      setLoading(false);
    }
  }, [filterRating]);

  useEffect(() => {
    fetchReviews();
  }, [fetchReviews]);

  const avgRating =
    reviews.length > 0
      ? (reviews.reduce((sum, r) => sum + r.rating, 0) / reviews.length).toFixed(
          1
        )
      : "0.0";

  const ratingCounts = [5, 4, 3, 2, 1].map((r) => ({
    rating: r,
    count: reviews.filter((rev) => rev.rating === r).length,
  }));

  if (loading) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Reviews
          </h1>
          <p className="text-muted-foreground mt-1">
            Customer feedback and ratings.
          </p>
        </div>
        <div className="flex items-center justify-center py-24">
          <Loader2 className="h-8 w-8 animate-spin text-muted-foreground" />
          <span className="ml-3 text-muted-foreground">Loading reviews...</span>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Reviews
          </h1>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="h-10 w-10 text-destructive mb-3" />
            <p className="text-sm text-muted-foreground mb-4">{error}</p>
            <Button variant="outline" onClick={fetchReviews}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div>
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Reviews
          </h1>
          <p className="text-muted-foreground mt-1">
            {reviews.length} total reviews
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchReviews}>
          <RefreshCw className="mr-2 h-4 w-4" />
          Refresh
        </Button>
      </div>

      {/* Stats cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Average Rating
            </CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex items-center gap-2">
              <span className="text-3xl font-bold">{avgRating}</span>
              <Star className="h-6 w-6 fill-yellow-400 text-yellow-400" />
            </div>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Reviews
            </CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-3xl font-bold">{reviews.length}</span>
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              5-Star Rate
            </CardTitle>
          </CardHeader>
          <CardContent>
            <span className="text-3xl font-bold">
              {reviews.length > 0
                ? Math.round(
                    (reviews.filter((r) => r.rating === 5).length /
                      reviews.length) *
                      100
                  )
                : 0}
              %
            </span>
          </CardContent>
        </Card>
      </div>

      {/* Rating distribution */}
      <Card className="mb-6">
        <CardHeader>
          <CardTitle className="text-base">Rating Distribution</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="space-y-2">
            {ratingCounts.map(({ rating, count }) => {
              const pct =
                reviews.length > 0
                  ? Math.round((count / reviews.length) * 100)
                  : 0;
              return (
                <button
                  key={rating}
                  onClick={() =>
                    setFilterRating(filterRating === rating ? null : rating)
                  }
                  className={`flex items-center gap-3 w-full text-left rounded px-2 py-1 transition-colors ${
                    filterRating === rating
                      ? "bg-primary/10"
                      : "hover:bg-muted"
                  }`}
                >
                  <span className="text-sm w-12">{rating} star</span>
                  <div className="flex-1 h-2 bg-gray-100 rounded-full overflow-hidden">
                    <div
                      className="h-full bg-yellow-400 rounded-full transition-all"
                      style={{ width: `${pct}%` }}
                    />
                  </div>
                  <span className="text-sm text-muted-foreground w-8 text-right">
                    {count}
                  </span>
                </button>
              );
            })}
          </div>
          {filterRating && (
            <Button
              variant="ghost"
              size="sm"
              className="mt-2"
              onClick={() => setFilterRating(null)}
            >
              Clear filter
            </Button>
          )}
        </CardContent>
      </Card>

      {/* Reviews list */}
      <div className="space-y-3">
        {(filterRating
          ? reviews.filter((r) => r.rating === filterRating)
          : reviews
        ).map((review) => (
          <Card key={review.id}>
            <CardContent className="py-4">
              <div className="flex items-start justify-between">
                <div>
                  <div className="flex items-center gap-2 mb-1">
                    <StarRating rating={review.rating} />
                    <Badge variant="outline" className="text-xs">
                      {review.rating}/5
                    </Badge>
                  </div>
                  {review.comment && (
                    <p className="text-sm text-gray-700 mt-2 leading-relaxed">
                      &ldquo;{review.comment}&rdquo;
                    </p>
                  )}
                  <p className="text-xs text-muted-foreground mt-2">
                    By {review.customer_name || "Customer"} &middot; Job #
                    {review.job_id.slice(0, 8)}
                  </p>
                </div>
                <span className="text-xs text-muted-foreground whitespace-nowrap">
                  {review.created_at
                    ? new Date(review.created_at).toLocaleDateString("en-US", {
                        month: "short",
                        day: "numeric",
                      })
                    : ""}
                </span>
              </div>
            </CardContent>
          </Card>
        ))}

        {reviews.length === 0 && (
          <Card>
            <CardContent className="py-12 text-center">
              <Star className="h-10 w-10 text-muted-foreground mx-auto mb-3" />
              <p className="text-muted-foreground">No reviews yet.</p>
            </CardContent>
          </Card>
        )}
      </div>
    </div>
  );
}
