"use client";

import { useCallback, useRef, useState } from "react";
import { Upload, X, ImageIcon, AlertCircle, Sparkles, Loader2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { useBookingStore } from "@/stores/booking-store";
import { cn } from "@/lib/utils";
import { aiApi } from "@/lib/api";

const ACCEPTED_TYPES = ["image/jpeg", "image/png", "image/webp"];
const MAX_FILES = 10;
const MAX_FILE_SIZE = 10 * 1024 * 1024; // 10MB

export function Step2Photos() {
  const { photos, photoPreviewUrls, addPhotos, removePhoto, aiAnalysis, aiAnalyzing, setAiAnalysis, setAiAnalyzing } =
    useBookingStore();
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [error, setError] = useState("");

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
          Upload Photos
        </h2>
        <p className="mt-1 text-muted-foreground">
          Show us what needs to go. This helps us give you an accurate estimate.
        </p>
      </div>

      {/* Drop Zone */}
      <div
        onDragOver={handleDragOver}
        onDragLeave={handleDragLeave}
        onDrop={handleDrop}
        onClick={() => fileInputRef.current?.click()}
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
              JPG, PNG, or WebP. Max 10 files, 10MB each.
            </p>
          </div>
        </div>
      </div>

      {/* Error */}
      {error && (
        <div className="flex items-center gap-2 text-sm text-destructive font-medium">
          <AlertCircle className="h-4 w-4 shrink-0" />
          {error}
        </div>
      )}

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

      {/* Optional note */}
      <div className="flex items-start gap-2 rounded-lg border border-border bg-muted/50 p-3">
        <ImageIcon className="h-4 w-4 text-muted-foreground mt-0.5 shrink-0" />
        <p className="text-xs text-muted-foreground">
          Photos are optional but help us provide more accurate estimates. You
          can skip this step if you prefer.
        </p>
      </div>

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
    </div>
  );
}
