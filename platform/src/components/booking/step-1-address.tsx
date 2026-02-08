"use client";

import { useState } from "react";
import { MapPin, Clock, DollarSign, Leaf } from "lucide-react";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useBookingStore } from "@/stores/booking-store";

export function Step1Address() {
  const { address, setAddress } = useBookingStore();
  const [streetValue, setStreetValue] = useState(address.street || "");
  const [error, setError] = useState("");

  const handleChange = (value: string) => {
    setStreetValue(value);
    if (error) setError("");
    // Sync to store on every keystroke so external Next button can validate
    setAddress({ street: value });
  };

  // Expose validation that also sets local error state
  Step1Address.validate = (): boolean => {
    const trimmed = streetValue.trim();
    if (trimmed.length < 10) {
      setError("Please enter a valid address (at least 10 characters).");
      return false;
    }
    setError("");
    setAddress({ street: trimmed });
    return true;
  };

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="font-display text-2xl font-bold tracking-tight text-foreground">
          Where should we pick up?
        </h2>
        <p className="mt-1 text-muted-foreground">
          Enter the address where your junk needs to be removed.
        </p>
      </div>

      {/* Address Input */}
      <div className="space-y-3">
        <Label htmlFor="address" className="text-sm font-medium">
          Pickup Address
        </Label>
        <div className="relative">
          <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground" />
          <Input
            id="address"
            type="text"
            placeholder="Enter your pickup address..."
            value={streetValue}
            onChange={(e) => handleChange(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === "Enter") {
                if (Step1Address.validate()) {
                  useBookingStore.getState().nextStep();
                }
              }
            }}
            className="pl-10 h-12 text-base"
          />
        </div>
        {error && (
          <p className="text-sm text-destructive font-medium">{error}</p>
        )}
      </div>

      {/* Service Area Info */}
      <div className="rounded-lg border border-primary/20 bg-primary/5 p-4 flex items-start gap-3">
        <MapPin className="h-5 w-5 text-primary mt-0.5 shrink-0" />
        <div>
          <p className="text-sm font-semibold text-foreground">
            Service Area
          </p>
          <p className="text-sm text-muted-foreground mt-0.5">
            We serve Palm Beach &amp; Broward County, South Florida
          </p>
        </div>
      </div>

      {/* Trust Indicators */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <TrustIndicator
          icon={<Clock className="h-5 w-5" />}
          title="Same-Day Available"
          description="Book today, we pick up today"
        />
        <TrustIndicator
          icon={<DollarSign className="h-5 w-5" />}
          title="Transparent Pricing"
          description="No hidden fees, ever"
        />
        <TrustIndicator
          icon={<Leaf className="h-5 w-5" />}
          title="Eco-Friendly Disposal"
          description="We recycle &amp; donate first"
        />
      </div>
    </div>
  );
}

function TrustIndicator({
  icon,
  title,
  description,
}: {
  icon: React.ReactNode;
  title: string;
  description: string;
}) {
  return (
    <div className="flex items-start gap-3 rounded-lg border border-border bg-card p-4">
      <div className="flex h-9 w-9 shrink-0 items-center justify-center rounded-full bg-primary/10 text-primary">
        {icon}
      </div>
      <div>
        <p className="text-sm font-semibold text-foreground">{title}</p>
        <p className="text-xs text-muted-foreground mt-0.5">{description}</p>
      </div>
    </div>
  );
}

// Default static validation (overwritten when component renders)
Step1Address.validate = (): boolean => {
  const { address } = useBookingStore.getState();
  return (address.street?.trim() || "").length >= 10;
};
