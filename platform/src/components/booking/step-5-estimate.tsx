"use client";

import { useState, useEffect, useCallback } from "react";
import {
  MapPin,
  CalendarDays,
  Package,
  Loader2,
  AlertTriangle,
  Sparkles,
  Truck,
  Weight,
  ShieldCheck,
} from "lucide-react";
import { useBookingStore } from "@/stores/booking-store";
import { bookingApi } from "@/lib/api";

const TIME_SLOT_LABELS: Record<string, string> = {
  "8-10": "8-10 AM",
  "10-12": "10 AM-12 PM",
  "12-14": "12-2 PM",
  "14-16": "2-4 PM",
  "16-18": "4-6 PM",
};

const CATEGORY_LABELS: Record<string, string> = {
  furniture: "Furniture",
  appliances: "Appliances",
  electronics: "Electronics",
  construction: "Construction Debris",
  yard_waste: "Yard Waste",
  hot_tub: "Hot Tub / Spa",
  general: "General Junk",
  other: "Other",
};

const CATEGORY_MULTIPLIERS: Record<string, number> = {
  appliances: 1.3,
  construction: 1.2,
};

interface PriceBreakdown {
  label: string;
  amount: number;
}

function calculateFallbackPrice(
  category: string,
  quantity: number
): { total: number; breakdown: PriceBreakdown[] } {
  const basePrice = 99;
  const perItem = 35;
  const multiplier = CATEGORY_MULTIPLIERS[category] || 1.0;
  const itemsSubtotal = perItem * quantity * multiplier;
  const subtotal = basePrice + itemsSubtotal;
  const serviceFee = Math.round(subtotal * 0.08 * 100) / 100;
  const total = Math.round((subtotal + serviceFee) * 100) / 100;

  return {
    total,
    breakdown: [
      { label: "Base Price", amount: basePrice },
      {
        label: `Items Subtotal (${quantity} x $${perItem}${multiplier > 1 ? ` x ${multiplier}x` : ""})`,
        amount: Math.round(itemsSubtotal * 100) / 100,
      },
      { label: "Service Fee (8%)", amount: serviceFee },
    ],
  };
}

function formatDate(dateStr: string): string {
  if (!dateStr) return "";
  const [year, month, day] = dateStr.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString("en-US", {
    weekday: "short",
    month: "short",
    day: "numeric",
    year: "numeric",
  });
}

export function Step5Estimate() {
  const {
    address,
    items,
    scheduledDate,
    scheduledTimeSlot,
    setEstimatedPrice,
    aiAnalysis,
  } = useBookingStore();

  const [breakdown, setBreakdown] = useState<PriceBreakdown[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [usedFallback, setUsedFallback] = useState(false);
  const [accepted, setAccepted] = useState(false);
  const [error, setError] = useState("");

  const item = items[0];
  const category = item?.category || "general";
  const quantity = item?.quantity || 1;

  // Aggregate totals from all items
  const totalCuFt = items.reduce((sum, i) => sum + (i.estimatedCuFt || 0), 0);
  const totalWeight = items.reduce((sum, i) => sum + (i.estimatedWeight || 0), 0);
  const uniqueCategories = Array.from(new Set(items.map((i) => i.category)));
  const totalItemCount = items.reduce((sum, i) => sum + i.quantity, 0);

  const fetchEstimate = useCallback(async () => {
    setLoading(true);
    setUsedFallback(false);

    // A binding vision quote (from step 2) is locked — the backend charges
    // that price, so show it instead of letting a re-estimate overwrite it.
    const { quoteId, quoteBinding, estimatedPrice: lockedPrice } =
      useBookingStore.getState();
    if (quoteId && quoteBinding && lockedPrice > 0) {
      setBreakdown([{ label: "Binding photo quote", amount: lockedPrice }]);
      setTotal(lockedPrice);
      setLoading(false);
      return;
    }

    try {
      const response = await bookingApi.estimate(items, address);
      setBreakdown(response.breakdown || []);
      setTotal(response.estimatedPrice || 0);
      setEstimatedPrice(response.estimatedPrice || 0);
    } catch {
      // Fallback pricing
      const fallback = calculateFallbackPrice(category, quantity);
      setBreakdown(fallback.breakdown);
      setTotal(fallback.total);
      setEstimatedPrice(fallback.total);
      setUsedFallback(true);
    } finally {
      setLoading(false);
    }
  }, [items, address, category, quantity, setEstimatedPrice]);

  useEffect(() => {
    fetchEstimate();
  }, [fetchEstimate]);

  // Expose validation that also sets local error state
  Step5Estimate.validate = (): boolean => {
    if (!accepted) {
      setError("Please confirm your items and price to continue.");
      return false;
    }
    setError("");
    return true;
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="font-display text-2xl font-bold tracking-tight text-foreground">
          Your Price
        </h2>
        <p className="mt-1 text-muted-foreground">
          Locked in before we show up — all-in, no surprises on the day.
        </p>
      </div>

      {/* Booking Summary */}
      <div className="rounded-lg border border-border bg-card p-5 space-y-4">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
          Booking Summary
        </h3>

        <div className="space-y-3">
          <SummaryRow
            icon={<MapPin className="h-4 w-4" />}
            label="Address"
            value={address.street || "Not provided"}
          />
          <SummaryRow
            icon={<CalendarDays className="h-4 w-4" />}
            label="Schedule"
            value={
              scheduledDate && scheduledTimeSlot
                ? `${formatDate(scheduledDate)} - ${TIME_SLOT_LABELS[scheduledTimeSlot] || scheduledTimeSlot}`
                : "Not selected"
            }
          />
          <SummaryRow
            icon={<Package className="h-4 w-4" />}
            label="Items"
            value={`${totalItemCount} item${totalItemCount !== 1 ? "s" : ""} across ${uniqueCategories.length} categor${uniqueCategories.length !== 1 ? "ies" : "y"}`}
          />
          {totalCuFt > 0 && (
            <>
              <SummaryRow
                icon={<Truck className="h-4 w-4" />}
                label="Est. Volume"
                value={`${totalCuFt} cu ft`}
              />
              <SummaryRow
                icon={<Weight className="h-4 w-4" />}
                label="Est. Weight"
                value={`${totalWeight} lbs`}
              />
            </>
          )}
        </div>
      </div>

      {/* AI Volume Estimate */}
      {aiAnalysis && (
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 space-y-2">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary" />
            <h3 className="text-sm font-semibold text-primary">AI Photo Analysis</h3>
          </div>
          <div className="grid grid-cols-3 gap-3 text-center">
            <div>
              <p className="text-lg font-bold text-foreground">{aiAnalysis.estimatedVolume} cu ft</p>
              <p className="text-xs text-muted-foreground">Est. Volume</p>
            </div>
            <div>
              <p className="text-lg font-bold text-foreground">{aiAnalysis.truckSize}</p>
              <p className="text-xs text-muted-foreground">Suggested</p>
            </div>
            <div>
              <p className="text-lg font-bold text-foreground">
                {aiAnalysis.confidence >= 0.8 ? "High" : aiAnalysis.confidence >= 0.5 ? "Medium" : "Low"}
              </p>
              <p className="text-xs text-muted-foreground">Confidence</p>
            </div>
          </div>
        </div>
      )}

      {/* Price Breakdown */}
      <div className="rounded-lg border border-border bg-card p-5 space-y-4">
        <h3 className="text-sm font-semibold text-foreground uppercase tracking-wider">
          Price Breakdown
        </h3>

        {loading ? (
          <div className="flex items-center justify-center py-8">
            <Loader2 className="h-6 w-6 animate-spin text-primary" />
            <span className="ml-2 text-sm text-muted-foreground">
              Calculating estimate...
            </span>
          </div>
        ) : (
          <>
            {usedFallback && (
              <div className="flex items-start gap-2 rounded-md bg-amber-50 border border-amber-200 p-3 dark:bg-amber-950/20 dark:border-amber-800">
                <AlertTriangle className="h-4 w-4 text-amber-600 mt-0.5 shrink-0" />
                <div className="flex-1">
                  <p className="text-xs text-amber-700 dark:text-amber-400">
                    Estimate based on standard pricing. Final price may vary based
                    on actual volume.
                  </p>
                  <button
                    type="button"
                    onClick={() => fetchEstimate()}
                    className="text-xs font-medium text-amber-700 dark:text-amber-400 underline hover:no-underline mt-1"
                  >
                    Retry estimate
                  </button>
                </div>
              </div>
            )}

            <div className="space-y-3">
              {breakdown.map((line, i) => (
                <div
                  key={i}
                  className="flex items-center justify-between text-sm"
                >
                  <span className="text-muted-foreground">{line.label}</span>
                  <span className="font-medium text-foreground">
                    ${line.amount.toFixed(2)}
                  </span>
                </div>
              ))}
            </div>

            <div className="border-t border-border pt-3">
              <div className="flex items-center justify-between">
                <div>
                  <span className="text-base font-bold text-foreground">
                    Your Price
                  </span>
                  <p className="text-xs text-muted-foreground">
                    All-in — loading, hauling &amp; disposal included
                  </p>
                </div>
                <span className="text-2xl font-bold text-primary">
                  ${total.toFixed(2)}
                </span>
              </div>
              {!usedFallback && (
                <div className="mt-3 flex items-center gap-2 rounded-md border border-primary/15 bg-primary/5 px-3 py-2">
                  <ShieldCheck className="h-4 w-4 shrink-0 text-primary" />
                  <p className="text-xs text-foreground">
                    <span className="font-semibold">Locked price.</span> This is
                    what you pay for the items shown — no on-site upcharges.
                  </p>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      {/* Accept Checkbox */}
      {!loading && (
        <div className="space-y-2">
          <label className="flex items-start gap-3 cursor-pointer group">
            <input
              type="checkbox"
              checked={accepted}
              onChange={(e) => {
                setAccepted(e.target.checked);
                if (e.target.checked) setError("");
              }}
              className="mt-1 h-5 w-5 rounded border-border text-primary focus:ring-primary accent-primary cursor-pointer"
            />
            <span className="text-sm text-muted-foreground group-hover:text-foreground transition-colors">
              The items above are accurate, and I accept this locked, all-in price.
              Only materially different or extra items would need a quick re-quote.
            </span>
          </label>
          <div aria-live="polite" aria-atomic="true">
            {error && (
              <p role="alert" className="text-sm text-destructive font-medium">
                {error}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function SummaryRow({
  icon,
  label,
  value,
}: {
  icon: React.ReactNode;
  label: string;
  value: string;
}) {
  return (
    <div className="flex items-start gap-3">
      <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-md bg-muted text-muted-foreground">
        {icon}
      </div>
      <div>
        <p className="text-xs text-muted-foreground">{label}</p>
        <p className="text-sm font-medium text-foreground">{value}</p>
      </div>
    </div>
  );
}

Step5Estimate.validate = (): boolean => true;
