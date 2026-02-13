"use client";

import { useState, useRef, useEffect, useCallback } from "react";
import { AnimatePresence, motion } from "motion/react";
import { MapPin, Clock, DollarSign, Leaf } from "lucide-react";
import { Label } from "@/components/ui/label";
import { useBookingStore } from "@/stores/booking-store";

const ADDRESS_PLACEHOLDERS = [
  "123 Main St, Boca Raton, FL",
  "456 Ocean Blvd, Fort Lauderdale, FL",
  "789 Palm Ave, West Palm Beach, FL",
  "321 Sunrise Rd, Delray Beach, FL",
  "555 Federal Hwy, Pompano Beach, FL",
];

interface MapboxFeature {
  id: string;
  place_name: string;
  text: string;
  center: [number, number]; // [lng, lat]
  context?: Array<{
    id: string;
    text: string;
    short_code?: string;
  }>;
  address?: string;
}

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;

export function Step1Address() {
  const { address, setAddress } = useBookingStore();
  const [streetValue, setStreetValue] = useState(address.street || "");
  const [error, setError] = useState("");
  const [suggestions, setSuggestions] = useState<MapboxFeature[]>([]);
  const [showSuggestions, setShowSuggestions] = useState(false);
  const [activeSuggestion, setActiveSuggestion] = useState(-1);
  const [currentPlaceholder, setCurrentPlaceholder] = useState(0);
  const debounceRef = useRef<NodeJS.Timeout | null>(null);
  const placeholderIntervalRef = useRef<NodeJS.Timeout | null>(null);
  const wrapperRef = useRef<HTMLDivElement>(null);

  // Cycle through placeholder text
  useEffect(() => {
    const startAnimation = () => {
      placeholderIntervalRef.current = setInterval(() => {
        setCurrentPlaceholder((prev) => (prev + 1) % ADDRESS_PLACEHOLDERS.length);
      }, 3000);
    };

    const handleVisibilityChange = () => {
      if (document.visibilityState !== "visible" && placeholderIntervalRef.current) {
        clearInterval(placeholderIntervalRef.current);
        placeholderIntervalRef.current = null;
      } else if (document.visibilityState === "visible") {
        startAnimation();
      }
    };

    startAnimation();
    document.addEventListener("visibilitychange", handleVisibilityChange);

    return () => {
      if (placeholderIntervalRef.current) clearInterval(placeholderIntervalRef.current);
      document.removeEventListener("visibilitychange", handleVisibilityChange);
    };
  }, []);

  // Close dropdown when clicking outside
  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (wrapperRef.current && !wrapperRef.current.contains(e.target as Node)) {
        setShowSuggestions(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  const fetchSuggestions = useCallback(async (query: string) => {
    if (!MAPBOX_TOKEN || query.trim().length < 3) {
      setSuggestions([]);
      return;
    }

    try {
      const encoded = encodeURIComponent(query.trim());
      const res = await fetch(
        `https://api.mapbox.com/geocoding/v5/mapbox.places/${encoded}.json?access_token=${MAPBOX_TOKEN}&country=us&types=address&limit=5&proximity=-80.1373,26.1224&bbox=-80.6,25.8,-79.8,27.0`
      );
      if (!res.ok) return;
      const data = await res.json();
      setSuggestions(data.features || []);
      setShowSuggestions(true);
      setActiveSuggestion(-1);
    } catch {
      // Silently fail — user can still type manually
    }
  }, []);

  const handleChange = (value: string) => {
    setStreetValue(value);
    if (error) setError("");
    setAddress({ street: value });

    // Debounce API calls
    if (debounceRef.current) clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => fetchSuggestions(value), 300);
  };

  const selectSuggestion = (feature: MapboxFeature) => {
    const fullAddress = feature.place_name;
    setStreetValue(fullAddress);
    setShowSuggestions(false);
    setSuggestions([]);

    // Parse address components from Mapbox context
    let city = "";
    let state = "";
    let zip = "";

    if (feature.context) {
      for (const ctx of feature.context) {
        if (ctx.id.startsWith("place")) city = ctx.text;
        if (ctx.id.startsWith("region")) state = ctx.short_code?.replace("US-", "") || ctx.text;
        if (ctx.id.startsWith("postcode")) zip = ctx.text;
      }
    }

    setAddress({
      street: fullAddress,
      city,
      state,
      zip,
      lng: feature.center[0],
      lat: feature.center[1],
    });

    if (error) setError("");
  };

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (!showSuggestions || suggestions.length === 0) {
      if (e.key === "Enter") {
        if (Step1Address.validate()) {
          useBookingStore.getState().nextStep();
        }
      }
      return;
    }

    if (e.key === "ArrowDown") {
      e.preventDefault();
      setActiveSuggestion((prev) => Math.min(prev + 1, suggestions.length - 1));
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      setActiveSuggestion((prev) => Math.max(prev - 1, 0));
    } else if (e.key === "Enter") {
      e.preventDefault();
      if (activeSuggestion >= 0 && activeSuggestion < suggestions.length) {
        selectSuggestion(suggestions[activeSuggestion]);
      } else if (suggestions.length > 0) {
        selectSuggestion(suggestions[0]);
      }
    } else if (e.key === "Escape") {
      setShowSuggestions(false);
    }
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
        <div className="relative" ref={wrapperRef}>
          <MapPin className="absolute left-3 top-1/2 -translate-y-1/2 h-5 w-5 text-muted-foreground z-10" />
          <input
            id="address"
            type="text"
            value={streetValue}
            onChange={(e) => handleChange(e.target.value)}
            onKeyDown={handleKeyDown}
            onFocus={() => {
              if (suggestions.length > 0) setShowSuggestions(true);
            }}
            autoComplete="off"
            className="flex w-full rounded-md border border-border bg-card pl-10 pr-4 h-12 text-base text-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-colors"
          />
          {/* Animated cycling placeholder */}
          {!streetValue && (
            <div className="absolute inset-0 flex items-center pointer-events-none pl-10">
              <AnimatePresence mode="wait">
                <motion.p
                  key={`placeholder-${currentPlaceholder}`}
                  initial={{ y: 5, opacity: 0 }}
                  animate={{ y: 0, opacity: 1 }}
                  exit={{ y: -15, opacity: 0 }}
                  transition={{ duration: 0.3, ease: "linear" }}
                  className="text-base text-muted-foreground truncate"
                >
                  {ADDRESS_PLACEHOLDERS[currentPlaceholder]}
                </motion.p>
              </AnimatePresence>
            </div>
          )}

          {/* Autocomplete Dropdown */}
          {showSuggestions && suggestions.length > 0 && (
            <ul className="absolute z-50 top-full left-0 right-0 mt-1 bg-card border border-border rounded-lg shadow-lg overflow-hidden">
              {suggestions.map((feature, i) => (
                <li
                  key={feature.id}
                  className={`flex items-start gap-3 px-3 py-3 cursor-pointer transition-colors ${
                    i === activeSuggestion
                      ? "bg-primary/10 text-foreground"
                      : "hover:bg-muted text-foreground"
                  }`}
                  onMouseDown={() => selectSuggestion(feature)}
                  onMouseEnter={() => setActiveSuggestion(i)}
                >
                  <MapPin className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
                  <span className="text-sm">{feature.place_name}</span>
                </li>
              ))}
            </ul>
          )}
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
