import { resolveApiBaseUrl } from "./api-base-url.js";

/** Use the same API/proxy as requests; S3 URLs are already absolute. */
export function resolveMediaUrl(url: string): string {
  return url.startsWith("/uploads/")
    ? `${resolveApiBaseUrl().replace(/\/$/, "")}${url}`
    : url;
}
