"use client";

import { useRef, useState, useCallback, useEffect } from "react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface BeforeAfterSliderProps {
  /** URL(s) of the "before" photos */
  beforePhotos: string[];
  /** URL(s) of the "after" photos */
  afterPhotos: string[];
  /** Optional label override for the section header */
  label?: string;
  /** If true, render a compact version (used in receipts) */
  compact?: boolean;
}

// ---------------------------------------------------------------------------
// Thumbnail strip for selecting a specific photo pair
// ---------------------------------------------------------------------------

function PhotoThumbnail({
  src,
  active,
  onClick,
  alt,
}: {
  src: string;
  active: boolean;
  onClick: () => void;
  alt: string;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`
        relative w-14 h-14 sm:w-16 sm:h-16 rounded-lg overflow-hidden border-2 transition-all duration-200
        flex-shrink-0 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary
        ${active ? "border-primary shadow-md" : "border-border hover:border-primary/40"}
      `}
    >
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={src}
        alt={alt}
        className="w-full h-full object-cover"
        loading="lazy"
      />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Slider component (draggable divider)
// ---------------------------------------------------------------------------

function SliderComparison({
  beforeSrc,
  afterSrc,
  compact,
}: {
  beforeSrc: string;
  afterSrc: string;
  compact?: boolean;
}) {
  const containerRef = useRef<HTMLDivElement>(null);
  const [sliderPos, setSliderPos] = useState(50); // percentage 0-100
  const [isDragging, setIsDragging] = useState(false);

  const updatePosition = useCallback(
    (clientX: number) => {
      const container = containerRef.current;
      if (!container) return;
      const rect = container.getBoundingClientRect();
      const x = clientX - rect.left;
      const percent = Math.max(0, Math.min(100, (x / rect.width) * 100));
      setSliderPos(percent);
    },
    []
  );

  // Mouse handlers
  const handleMouseDown = useCallback(
    (e: React.MouseEvent) => {
      e.preventDefault();
      setIsDragging(true);
      updatePosition(e.clientX);
    },
    [updatePosition]
  );

  useEffect(() => {
    if (!isDragging) return;

    const handleMouseMove = (e: MouseEvent) => {
      e.preventDefault();
      updatePosition(e.clientX);
    };
    const handleMouseUp = () => {
      setIsDragging(false);
    };

    window.addEventListener("mousemove", handleMouseMove);
    window.addEventListener("mouseup", handleMouseUp);
    return () => {
      window.removeEventListener("mousemove", handleMouseMove);
      window.removeEventListener("mouseup", handleMouseUp);
    };
  }, [isDragging, updatePosition]);

  // Touch handlers
  const handleTouchStart = useCallback(
    (e: React.TouchEvent) => {
      setIsDragging(true);
      updatePosition(e.touches[0].clientX);
    },
    [updatePosition]
  );

  useEffect(() => {
    if (!isDragging) return;

    const handleTouchMove = (e: TouchEvent) => {
      updatePosition(e.touches[0].clientX);
    };
    const handleTouchEnd = () => {
      setIsDragging(false);
    };

    window.addEventListener("touchmove", handleTouchMove, { passive: true });
    window.addEventListener("touchend", handleTouchEnd);
    return () => {
      window.removeEventListener("touchmove", handleTouchMove);
      window.removeEventListener("touchend", handleTouchEnd);
    };
  }, [isDragging, updatePosition]);

  const height = compact ? "aspect-[4/3]" : "aspect-[4/3] sm:aspect-[16/10]";

  return (
    <div
      ref={containerRef}
      className={`relative ${height} w-full rounded-xl overflow-hidden select-none cursor-col-resize bg-muted border border-border`}
      onMouseDown={handleMouseDown}
      onTouchStart={handleTouchStart}
      role="slider"
      aria-label="Before and after comparison slider"
      aria-valuenow={Math.round(sliderPos)}
      aria-valuemin={0}
      aria-valuemax={100}
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "ArrowLeft") setSliderPos((p) => Math.max(0, p - 2));
        if (e.key === "ArrowRight") setSliderPos((p) => Math.min(100, p + 2));
      }}
    >
      {/* After image (full background) */}
      {/* eslint-disable-next-line @next/next/no-img-element */}
      <img
        src={afterSrc}
        alt="After"
        className="absolute inset-0 w-full h-full object-cover"
        draggable={false}
        loading="lazy"
      />

      {/* Before image (clipped) */}
      <div
        className="absolute inset-0 overflow-hidden"
        style={{ width: `${sliderPos}%` }}
      >
        {/* eslint-disable-next-line @next/next/no-img-element */}
        <img
          src={beforeSrc}
          alt="Before"
          className="absolute inset-0 w-full h-full object-cover"
          style={{
            width: containerRef.current
              ? `${containerRef.current.offsetWidth}px`
              : "100vw",
            maxWidth: "none",
          }}
          draggable={false}
          loading="lazy"
        />
      </div>

      {/* Slider line */}
      <div
        className="absolute top-0 bottom-0 w-[3px] bg-white shadow-[0_0_8px_rgba(0,0,0,0.4)] z-10"
        style={{ left: `${sliderPos}%`, transform: "translateX(-50%)" }}
      >
        {/* Handle circle */}
        <div className="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-10 h-10 rounded-full bg-white shadow-lg flex items-center justify-center">
          <svg
            className="w-5 h-5 text-gray-600"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={2}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M8 9l4-4 4 4M16 15l-4 4-4-4"
            />
          </svg>
        </div>
      </div>

      {/* Labels */}
      <div className="absolute top-3 left-3 z-20">
        <span className="inline-block bg-black/60 backdrop-blur-sm text-white text-xs font-medium px-2.5 py-1 rounded-full">
          Before
        </span>
      </div>
      <div className="absolute top-3 right-3 z-20">
        <span className="inline-block bg-black/60 backdrop-blur-sm text-white text-xs font-medium px-2.5 py-1 rounded-full">
          After
        </span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Stacked fallback (when only one set of photos exists)
// ---------------------------------------------------------------------------

function StackedPhotos({
  photos,
  label,
}: {
  photos: string[];
  label: string;
}) {
  return (
    <div>
      <p className="text-xs text-muted-foreground uppercase tracking-wider font-medium mb-2">
        {label}
      </p>
      <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
        {photos.map((url, idx) => (
          <div
            key={idx}
            className="aspect-square rounded-lg overflow-hidden border border-border bg-muted"
          >
            {/* eslint-disable-next-line @next/next/no-img-element */}
            <img
              src={url}
              alt={`${label} photo ${idx + 1}`}
              className="w-full h-full object-cover"
              loading="lazy"
            />
          </div>
        ))}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main export
// ---------------------------------------------------------------------------

export default function BeforeAfterSlider({
  beforePhotos,
  afterPhotos,
  label,
  compact = false,
}: BeforeAfterSliderProps) {
  const hasBefore = beforePhotos.length > 0;
  const hasAfter = afterPhotos.length > 0;

  // Selected index for slider comparison
  const maxPairs = Math.min(beforePhotos.length, afterPhotos.length);
  const [selectedIndex, setSelectedIndex] = useState(0);

  // No photos at all
  if (!hasBefore && !hasAfter) {
    return null;
  }

  // Both sets: show slider comparison
  if (hasBefore && hasAfter) {
    return (
      <div className="space-y-4">
        {/* Header */}
        <div className="flex items-center gap-2">
          <svg
            className="w-5 h-5 text-green-600"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0112 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.745 3.745 0 011.043 3.296A3.745 3.745 0 0121 12z"
            />
          </svg>
          <span className="text-sm font-semibold text-green-700 dark:text-green-400">
            {label || "Proof of Completion"}
          </span>
        </div>

        {/* Slider */}
        <SliderComparison
          beforeSrc={beforePhotos[selectedIndex] || beforePhotos[0]}
          afterSrc={afterPhotos[selectedIndex] || afterPhotos[0]}
          compact={compact}
        />

        {/* Hint text */}
        <p className="text-xs text-muted-foreground text-center">
          Drag the slider to compare before and after
        </p>

        {/* Thumbnail strip (if more than 1 pair) */}
        {maxPairs > 1 && (
          <div className="flex items-center gap-2 overflow-x-auto pb-1">
            {Array.from({ length: maxPairs }).map((_, idx) => (
              <div key={idx} className="flex items-center gap-1 flex-shrink-0">
                <PhotoThumbnail
                  src={beforePhotos[idx]}
                  active={selectedIndex === idx}
                  onClick={() => setSelectedIndex(idx)}
                  alt={`Before photo ${idx + 1}`}
                />
                <span className="text-muted-foreground text-xs">/</span>
                <PhotoThumbnail
                  src={afterPhotos[idx]}
                  active={selectedIndex === idx}
                  onClick={() => setSelectedIndex(idx)}
                  alt={`After photo ${idx + 1}`}
                />
              </div>
            ))}
          </div>
        )}

        {/* Extra photos beyond pairs (stacked) */}
        {beforePhotos.length > maxPairs && (
          <StackedPhotos
            photos={beforePhotos.slice(maxPairs)}
            label="Additional Before Photos"
          />
        )}
        {afterPhotos.length > maxPairs && (
          <StackedPhotos
            photos={afterPhotos.slice(maxPairs)}
            label="Additional After Photos"
          />
        )}
      </div>
    );
  }

  // Only one set: stacked fallback
  if (hasBefore && !hasAfter) {
    return (
      <div className="space-y-3">
        <div className="flex items-center gap-2">
          <svg
            className="w-5 h-5 text-blue-600"
            fill="none"
            viewBox="0 0 24 24"
            strokeWidth={1.5}
            stroke="currentColor"
          >
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M6.827 6.175A2.31 2.31 0 015.186 7.23c-.38.054-.757.112-1.134.175C2.999 7.58 2.25 8.507 2.25 9.574V18a2.25 2.25 0 002.25 2.25h15A2.25 2.25 0 0021.75 18V9.574c0-1.067-.75-1.994-1.802-2.169a47.865 47.865 0 00-1.134-.175 2.31 2.31 0 01-1.64-1.055l-.822-1.316a2.192 2.192 0 00-1.736-1.039 48.774 48.774 0 00-5.232 0 2.192 2.192 0 00-1.736 1.039l-.821 1.316z"
            />
            <path
              strokeLinecap="round"
              strokeLinejoin="round"
              d="M16.5 12.75a4.5 4.5 0 11-9 0 4.5 4.5 0 019 0zM18.75 10.5h.008v.008h-.008V10.5z"
            />
          </svg>
          <span className="text-sm font-semibold">Before Photos</span>
        </div>
        <StackedPhotos photos={beforePhotos} label="Before" />
      </div>
    );
  }

  // Only after photos
  return (
    <div className="space-y-3">
      <div className="flex items-center gap-2">
        <svg
          className="w-5 h-5 text-green-600"
          fill="none"
          viewBox="0 0 24 24"
          strokeWidth={1.5}
          stroke="currentColor"
        >
          <path
            strokeLinecap="round"
            strokeLinejoin="round"
            d="M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0112 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.745 3.745 0 011.043 3.296A3.745 3.745 0 0121 12z"
          />
        </svg>
        <span className="text-sm font-semibold text-green-700 dark:text-green-400">
          {label || "Proof of Completion"}
        </span>
      </div>
      <StackedPhotos photos={afterPhotos} label="After" />
    </div>
  );
}
