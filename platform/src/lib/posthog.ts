/**
 * PostHog analytics integration for Umuve platform.
 *
 * Initializes PostHog when NEXT_PUBLIC_POSTHOG_KEY is set.
 * Provides helper functions for tracking events and identifying users.
 * All functions are no-ops when PostHog is not configured.
 */

import posthog from "posthog-js";

let initialized = false;

export function initPostHog() {
  if (typeof window === "undefined") return;
  if (initialized) return;

  const key = process.env.NEXT_PUBLIC_POSTHOG_KEY;
  const host = process.env.NEXT_PUBLIC_POSTHOG_HOST || "https://us.i.posthog.com";

  if (!key) return;

  posthog.init(key, {
    api_host: host,
    capture_pageview: true,
    capture_pageleave: true,
    persistence: "localStorage",
  });
  initialized = true;
}

export function trackEvent(name: string, properties?: Record<string, unknown>) {
  if (!initialized) return;
  posthog.capture(name, properties);
}

export function identifyUser(
  userId: string,
  traits?: Record<string, unknown>
) {
  if (!initialized) return;
  posthog.identify(userId, traits);
}

export function resetUser() {
  if (!initialized) return;
  posthog.reset();
}

export { posthog };
