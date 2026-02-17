"use client";

export default function BookError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  return (
    <div className="max-w-3xl mx-auto px-4 py-12">
      <div className="rounded-lg border border-destructive/30 bg-destructive/5 p-6 space-y-4">
        <h2 className="text-lg font-bold text-destructive">
          Booking Page Error
        </h2>
        <pre className="text-sm text-destructive/80 whitespace-pre-wrap break-words bg-destructive/5 rounded p-3 border border-destructive/20">
          {error.message}
        </pre>
        {error.stack && (
          <details className="text-xs text-muted-foreground">
            <summary className="cursor-pointer">Stack trace</summary>
            <pre className="mt-2 whitespace-pre-wrap break-words">
              {error.stack}
            </pre>
          </details>
        )}
        <button
          onClick={reset}
          className="px-4 py-2 bg-primary text-primary-foreground rounded-md text-sm font-medium"
        >
          Try Again
        </button>
      </div>
    </div>
  );
}
