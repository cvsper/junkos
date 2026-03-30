/**
 * Resolve the API base URL from environment or default to production.
 */
export function resolveApiBaseUrl(): string {
  return (
    process.env.NEXT_PUBLIC_API_URL || "https://junkos-backend.onrender.com"
  );
}
