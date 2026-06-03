"use client";

import { useCallback, useRef, useState } from "react";
import { Camera, Loader2, AlertCircle, Sparkles, X } from "lucide-react";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";
import { quotesApi, type VisionQuote } from "@/lib/api";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_FILES = 6;
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

interface InstantQuoteProps {
  /** Optional context forwarded to the pricing engine (surge, zone). */
  zipCode?: string;
  zone?: string;
  scheduledDate?: string;
  /** Called when a quote comes back, so a parent flow can prefill / advance. */
  onQuote?: (quote: VisionQuote) => void;
  className?: string;
}

/**
 * Instant Photo -> Price quote widget (Vision Quote Engine, spec 01).
 *
 * Upload 1-6 photos, hit "Get my price", and the backend runs a cloud vision
 * model (or a rules fallback) to return an itemized, priced quote.
 */
export function InstantQuote({
  zipCode,
  zone,
  scheduledDate,
  onQuote,
  className,
}: InstantQuoteProps) {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [files, setFiles] = useState<File[]>([]);
  const [previews, setPreviews] = useState<string[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [quote, setQuote] = useState<VisionQuote | null>(null);

  const addFiles = useCallback(
    (incoming: FileList | File[]) => {
      setError("");
      const arr = Array.from(incoming);
      if (files.length + arr.length > MAX_FILES) {
        setError(`Maximum ${MAX_FILES} photos. You have ${files.length}.`);
        return;
      }
      const valid: File[] = [];
      for (const f of arr) {
        if (!ACCEPTED_TYPES.includes(f.type)) {
          setError("Only JPG, PNG, and WebP images are accepted.");
          return;
        }
        if (f.size > MAX_FILE_SIZE) {
          setError(`"${f.name}" exceeds the 10MB limit.`);
          return;
        }
        valid.push(f);
      }
      setFiles((prev) => [...prev, ...valid]);
      setPreviews((prev) => [...prev, ...valid.map((f) => URL.createObjectURL(f))]);
      setQuote(null);
    },
    [files.length]
  );

  const removeFile = useCallback((index: number) => {
    setFiles((prev) => prev.filter((_, i) => i !== index));
    setPreviews((prev) => {
      const url = prev[index];
      if (url) URL.revokeObjectURL(url);
      return prev.filter((_, i) => i !== index);
    });
    setQuote(null);
  }, []);

  const getQuote = useCallback(async () => {
    if (files.length === 0) {
      setError("Add at least one photo first.");
      return;
    }
    setLoading(true);
    setError("");
    const result = await quotesApi.estimateFromPhotos(files, {
      zipCode,
      zone,
      scheduledDate,
    });
    setLoading(false);
    if (!result) {
      setError("We couldn't generate a quote. Please try again.");
      return;
    }
    setQuote(result);
    onQuote?.(result);
  }, [files, zipCode, zone, scheduledDate, onQuote]);

  return (
    <div className={cn("space-y-6", className)}>
      <div>
        <h3 className="font-display text-xl font-bold tracking-tight text-foreground">
          Get an instant quote from photos
        </h3>
        <p className="mt-1 text-sm text-muted-foreground">
          Snap a few photos of what needs to go and get a price in seconds.
        </p>
      </div>

      {/* Upload control */}
      <div
        role="button"
        tabIndex={0}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        className={cn(
          "flex cursor-pointer flex-col items-center gap-3 rounded-lg border-2 border-dashed border-border p-8 text-center transition-colors hover:border-primary/50 hover:bg-muted/50",
          files.length >= MAX_FILES && "pointer-events-none opacity-50"
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.webp"
          multiple
          onChange={(e) => {
            if (e.target.files?.length) addFiles(e.target.files);
            e.target.value = "";
          }}
          className="hidden"
        />
        <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
          <Camera className="h-6 w-6 text-primary" />
        </div>
        <div>
          <p className="text-sm font-semibold text-foreground">Click to add photos</p>
          <p className="mt-1 text-xs text-muted-foreground">
            JPG, PNG, or WebP. Up to {MAX_FILES} photos.
          </p>
        </div>
      </div>

      {/* Error */}
      <div aria-live="polite" aria-atomic="true">
        {error && (
          <div role="alert" className="flex items-center gap-2 text-sm font-medium text-destructive">
            <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
            {error}
          </div>
        )}
      </div>

      {/* Previews */}
      {previews.length > 0 && (
        <div className="grid grid-cols-3 gap-3 sm:grid-cols-4">
          {previews.map((url, index) => (
            <div
              key={`${url}-${index}`}
              className="group relative aspect-square overflow-hidden rounded-lg border border-border bg-muted"
            >
              {/* eslint-disable-next-line @next/next/no-img-element */}
              <img src={url} alt={`Photo ${index + 1}`} className="h-full w-full object-cover" />
              <button
                type="button"
                onClick={() => removeFile(index)}
                className="absolute right-1.5 top-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-black/60 text-white opacity-0 transition-opacity hover:bg-black/80 group-hover:opacity-100"
                aria-label={`Remove photo ${index + 1}`}
              >
                <X className="h-4 w-4" />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Action */}
      <Button
        type="button"
        onClick={getQuote}
        disabled={loading || files.length === 0}
        className="w-full"
      >
        {loading ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Analyzing your photos...
          </>
        ) : (
          <>
            <Sparkles className="mr-2 h-4 w-4" />
            Get my price
          </>
        )}
      </Button>

      {/* Result */}
      {quote && (
        <div className="space-y-4 rounded-xl border border-border bg-card p-5">
          <div className="flex items-baseline justify-between">
            <div>
              <p className="text-sm text-muted-foreground">
                {quote.binding ? "Your binding price" : "Estimated price"}
              </p>
              <p className="font-display text-3xl font-bold text-foreground">
                ${quote.price.toFixed(2)}
              </p>
              {!quote.binding && quote.price_floor != null && quote.price_ceiling != null && (
                <p className="mt-0.5 text-xs text-muted-foreground">
                  Likely ${quote.price_floor.toFixed(0)}–${quote.price_ceiling.toFixed(0)} pending review
                </p>
              )}
            </div>
            <span
              className={cn(
                "rounded-full px-3 py-1 text-xs font-medium",
                quote.binding
                  ? "bg-green-100 text-green-700 dark:bg-green-950/30 dark:text-green-400"
                  : "bg-amber-100 text-amber-700 dark:bg-amber-950/30 dark:text-amber-400"
              )}
            >
              {quote.binding ? "Guaranteed" : "Estimate"}
            </span>
          </div>

          <ul className="divide-y divide-border">
            {quote.items.map((item, i) => (
              <li key={i} className="flex items-center justify-between py-2 text-sm">
                <span className="text-foreground">
                  {item.count > 1 ? `${item.count}× ` : ""}
                  {item.display_name}
                  {item.hazmat && (
                    <span className="ml-2 text-xs font-medium text-amber-600">hazmat</span>
                  )}
                </span>
                <span className="text-muted-foreground">
                  {item.volume_cubic_feet} cu ft
                </span>
              </li>
            ))}
          </ul>

          <p className="text-xs text-muted-foreground">
            ~{quote.estimated_volume_cubic_yards} cu yd total
            {quote.origin === "rules" && " · estimate only (vision unavailable)"}
          </p>
        </div>
      )}
    </div>
  );
}
