"use client";

import { useCallback, useRef, useState } from "react";
import { Upload, X, AlertCircle, Sparkles, Loader2, Zap } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useBookingStore } from "@/stores/booking-store";
import { cn } from "@/lib/utils";
import { aiApi, apiBaseUrl } from "@/lib/api";
import { funnelSignal } from "@/hooks/use-funnel-beacon";
import { InstantQuote } from "@/components/booking/instant-quote";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_FILES = 10;
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export function Step2Photos() {
  const { photos, photoPreviewUrls, addPhotos, removePhoto, aiAnalysis, aiAnalyzing, setAiAnalysis, setAiAnalyzing, address, scheduledDate, setQuoteId, setQuoteBinding, setQuoteToken, setEstimatedPrice } =
    useBookingStore();
  const nextStep = useBookingStore((s) => s.nextStep);
  const leadSource = useBookingStore((s) => s.leadSource);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState("");
  const [showInstantQuote, setShowInstantQuote] = useState(false);

  // "Text me a price": the person who won't upload photos or pick items on a
  // phone still leaves a number, and a person texts them. 86% of visitors
  // left on this step and none of them were reachable.
  const [textPhone, setTextPhone] = useState("");
  const [textBusy, setTextBusy] = useState(false);
  const [textSent, setTextSent] = useState(false);
  const [textError, setTextError] = useState("");
  const submitTextMe = useCallback(
    async (e: React.FormEvent) => {
      e.preventDefault();
      const digits = textPhone.replace(/\D/g, "");
      if (digits.length < 10) {
        setTextError("Enter a 10-digit mobile number.");
        return;
      }
      setTextBusy(true);
      setTextError("");
      try {
        const res = await fetch(`${apiBaseUrl}/api/leads/web`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            phone: digits.slice(-10),
            address: address?.street,
            zip: address?.zip,
            source: leadSource || "web",
          }),
        });
        if (!res.ok) throw new Error("failed");
        funnelSignal("text_me", {}, true);
        setTextSent(true);
      } catch {
        setTextError("That didn't go through. Call or text (844) 435-6005 instead.");
      } finally {
        setTextBusy(false);
      }
    },
    [textPhone, address, leadSource]
  );

  const validateAndAddFiles = useCallback(
    (files: FileList | File[]) => {
      setError("");
      const fileArray = Array.from(files);

      // Check total count
      if (photos.length + fileArray.length > MAX_FILES) {
        setError(`Maximum ${MAX_FILES} photos allowed. You already have ${photos.length}.`);
        return;
      }

      // Validate each file
      const validFiles: File[] = [];
      for (const file of fileArray) {
        if (!ACCEPTED_TYPES.includes(file.type)) {
          setError("Only JPG, PNG, and WebP images are accepted.");
          return;
        }
        if (file.size > MAX_FILE_SIZE) {
          setError(`"${file.name}" exceeds the 10MB size limit.`);
          return;
        }
        validFiles.push(file);
      }

      if (validFiles.length > 0) {
        addPhotos(validFiles);
        // Trigger AI analysis in background
        const allPhotos = [...photos, ...validFiles];
        if (allPhotos.length > 0) {
          setAiAnalyzing(true);
          aiApi.analyzePhotos(allPhotos.slice(0, 5)).then((result) => {
            setAiAnalysis(result);
            setAiAnalyzing(false);
          }).catch(() => {
            setAiAnalyzing(false);
          });
        }
      }
    },
    [photos.length, addPhotos]
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(true);
  }, []);

  const handleDragLeave = useCallback((e: React.DragEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setIsDragging(false);
  }, []);

  const handleDrop = useCallback(
    (e: React.DragEvent) => {
      e.preventDefault();
      e.stopPropagation();
      setIsDragging(false);
      if (e.dataTransfer.files.length > 0) {
        validateAndAddFiles(e.dataTransfer.files);
      }
    },
    [validateAndAddFiles]
  );

  const handleFileSelect = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      if (e.target.files && e.target.files.length > 0) {
        validateAndAddFiles(e.target.files);
      }
      // Reset input so the same file can be selected again
      e.target.value = "";
    },
    [validateAndAddFiles]
  );

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="font-display text-2xl font-bold tracking-tight text-foreground">
          Photos, if you have them
        </h2>
        <p className="mt-1 text-muted-foreground">
          A couple of pictures and we fill in your items and your price for you.
          No photos? Skip ahead and add the items yourself — it takes a minute longer.
        </p>
      </div>

      {/* Two ways forward, both obvious. */}
      <div className="grid gap-3 sm:grid-cols-2">
        <button
          type="button"
          onClick={() => fileInputRef.current?.click()}
          className="rounded-lg border-2 border-primary bg-primary/5 p-4 text-left transition-colors hover:bg-primary/10"
        >
          <span className="block text-sm font-semibold text-foreground">Add photos</span>
          <span className="mt-1 block text-xs text-muted-foreground">We fill in the items and the price for you</span>
        </button>
        <button
          type="button"
          onClick={() => {
            funnelSignal("skip_photos", {}, true);
            nextStep();
          }}
          className="rounded-lg border-2 border-border p-4 text-left transition-colors hover:border-primary/50 hover:bg-muted/50"
        >
          <span className="block text-sm font-semibold text-foreground">No photos, I&apos;ll pick the items</span>
          <span className="mt-1 block text-xs text-muted-foreground">About a minute, price at the end</span>
        </button>
      </div>

      {/* Drop Zone */}
      <div
        role="button"
        tabIndex={0}
        aria-label="Upload photos, optional. Click or drag photos here. JPG, PNG, or WebP. Max 10 files, 10MB each."
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            fileInputRef.current?.click();
          }
        }}
        className={cn(
          "relative cursor-pointer rounded-lg border-2 border-dashed p-8 text-center transition-colors",
          isDragging
            ? "border-primary bg-primary/5"
            : "border-border hover:border-primary/50 hover:bg-muted/50",
          photos.length >= MAX_FILES && "pointer-events-none opacity-50"
        )}
      >
        <input
          ref={fileInputRef}
          type="file"
          accept=".jpg,.jpeg,.png,.webp"
          multiple
          onChange={handleFileSelect}
          className="hidden"
        />
        <div className="flex flex-col items-center gap-3">
          <div className="flex h-14 w-14 items-center justify-center rounded-full bg-primary/10">
            <Upload className="h-6 w-6 text-primary" />
          </div>
          <div>
            <p className="text-sm font-semibold text-foreground">
              {isDragging ? "Drop photos here" : "Click or drag photos here"}
            </p>
            <p className="text-xs text-muted-foreground mt-1">
              Optional. JPG, PNG, or WebP. Max 10 files, 10MB each.
            </p>
          </div>
        </div>
      </div>

      {/* Error */}
      <div aria-live="polite" aria-atomic="true">
        {error && (
          <div role="alert" className="flex items-center gap-2 text-sm text-destructive font-medium">
            <AlertCircle className="h-4 w-4 shrink-0" aria-hidden="true" />
            {error}
          </div>
        )}
      </div>

      {/* Preview Grid */}
      {photoPreviewUrls.length > 0 && (
        <div>
          <p className="text-sm font-medium text-foreground mb-3">
            {photos.length} photo{photos.length !== 1 ? "s" : ""} selected
          </p>
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
            {photoPreviewUrls.map((url, index) => (
              <div
                key={`${url}-${index}`}
                className="group relative aspect-square rounded-lg overflow-hidden border border-border bg-muted"
              >
                {/* eslint-disable-next-line @next/next/no-img-element */}
                <img
                  src={url}
                  alt={`Upload ${index + 1}`}
                  className="h-full w-full object-cover"
                />
                <button
                  type="button"
                  onClick={(e) => {
                    e.stopPropagation();
                    removePhoto(index);
                  }}
                  className="absolute top-1.5 right-1.5 flex h-7 w-7 items-center justify-center rounded-full bg-black/60 text-white opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/80"
                  aria-label={`Remove photo ${index + 1}`}
                >
                  <X className="h-4 w-4" />
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* AI Analysis Status */}
      {aiAnalyzing && (
        <div className="flex items-center gap-2 rounded-lg border border-primary/20 bg-primary/5 p-3">
          <Loader2 className="h-4 w-4 text-primary animate-spin shrink-0" />
          <p className="text-sm text-primary font-medium">
            Analyzing your photos...
          </p>
        </div>
      )}
      {aiAnalysis && !aiAnalyzing && (
        <div className="flex items-center gap-2 rounded-lg border border-green-200 bg-green-50 p-3 dark:border-green-800 dark:bg-green-950/20">
          <Sparkles className="h-4 w-4 text-green-600 shrink-0" />
          <p className="text-sm text-green-700 dark:text-green-400 font-medium">
            AI detected {aiAnalysis.items.length} item{aiAnalysis.items.length !== 1 ? "s" : ""} from your photos
          </p>
        </div>
      )}

      {/* Instant photo -> price quote (Vision Quote Engine) */}
      <div className="rounded-lg border border-border">
        <button
          type="button"
          onClick={() => setShowInstantQuote((v) => !v)}
          className="flex w-full items-center gap-2 p-4 text-left"
          aria-expanded={showInstantQuote}
        >
          <Zap className="h-4 w-4 shrink-0 text-primary" />
          <span className="text-sm font-semibold text-foreground">
            Get an instant price from photos
          </span>
          <span className="ml-auto text-xs text-muted-foreground">
            {showInstantQuote ? "Hide" : "Try it"}
          </span>
        </button>
        {showInstantQuote && (
          <div className="border-t border-border p-4">
            <InstantQuote
              zipCode={address?.zip}
              scheduledDate={scheduledDate || undefined}
              onQuote={(q) => {
                // Carry the quote into the booking so the backend honors its
                // locked price. Only mirror the price into the UI when it's a
                // binding quote (the backend recomputes non-binding ones).
                setQuoteId(q.id);
                // Anonymous quotes come with a one-time claim token — it is
                // what proves ownership at conversion (audit F11: a body
                // user_id is never trusted).
                setQuoteToken(q.quote_token || null);
                const binding = q.binding && typeof q.price === "number";
                setQuoteBinding(binding);
                if (binding) {
                  setEstimatedPrice(q.price);
                }
              }}
            />
          </div>
        )}
      </div>

      {/* Rather not do this on a phone? A person texts a price. */}
      <div className="rounded-lg border border-border bg-muted/30 p-4">
        <p className="text-sm font-semibold text-foreground">Rather have us text you a price?</p>
        <p className="mt-1 text-xs text-muted-foreground">
          Enter your mobile number. A real person texts back within a few minutes, 8am to 8pm.
        </p>
        {textSent ? (
          <p className="mt-3 text-sm font-medium text-green-700 dark:text-green-400">
            Got it. Watch for a text from (561) 782-4350.
          </p>
        ) : (
          <form className="mt-3 flex flex-col gap-2 sm:flex-row" onSubmit={submitTextMe}>
            <input
              type="tel"
              inputMode="tel"
              autoComplete="tel"
              value={textPhone}
              onChange={(e) => setTextPhone(e.target.value)}
              placeholder="(305) 555-0123"
              aria-label="Mobile number"
              className="h-10 flex-1 rounded-md border border-input bg-background px-3 text-sm"
            />
            <Button type="submit" variant="outline" disabled={textBusy}>
              {textBusy ? "Sending…" : "Text me a price"}
            </Button>
          </form>
        )}
        {textError && <p className="mt-2 text-xs text-destructive">{textError}</p>}
      </div>
    </div>
  );
}
