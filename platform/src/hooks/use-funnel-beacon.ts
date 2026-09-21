"use client";

import { useEffect, useRef } from "react";
import { useBookingStore } from "@/stores/booking-store";

/**
 * Records progress through the booking flow so an abandoned attempt is a row
 * somebody can act on.
 *
 * Until now the page reported nothing until step 6, and only if a valid email
 * had been typed. Someone who gave an address, picked their items, chose a day,
 * saw a locked price and then closed the tab left no trace: no lead, no number,
 * nothing to call back. This sends one small beacon per step, carrying whatever
 * is known so far.
 *
 * It is fire-and-forget. A failed beacon must never affect a booking.
 */

const SESSION_KEY = "umuve_funnel_session";

function sessionId(): string {
  if (typeof window === "undefined") return "";
  try {
    const existing = window.sessionStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const fresh =
      typeof crypto !== "undefined" && "randomUUID" in crypto
        ? crypto.randomUUID()
        : `s-${Date.now()}-${Math.random().toString(36).slice(2, 10)}`;
    window.sessionStorage.setItem(SESSION_KEY, fresh);
    return fresh;
  } catch {
    // Private mode, or storage blocked. Without a stable id every beacon would
    // be a new row, which would make the funnel read worse than reality — so
    // send nothing instead.
    return "";
  }
}

/** Clear the id once a booking succeeds so the next one starts fresh. */
export function clearFunnelSession() {
  try {
    window.sessionStorage.removeItem(SESSION_KEY);
  } catch {
    // noop
  }
}

function addressLine(address: unknown): string | undefined {
  if (!address) return undefined;
  if (typeof address === "string") return address;
  if (typeof address === "object") {
    const a = address as Record<string, unknown>;
    const street = typeof a.street === "string" ? a.street : "";
    const city = typeof a.city === "string" ? a.city : "";
    const zip = zipOf(address) ?? "";
    const line = [street, city, zip].filter(Boolean).join(", ");
    return line || undefined;
  }
  return undefined;
}

function zipOf(address: unknown): string | undefined {
  if (address && typeof address === "object") {
    const a = address as Record<string, unknown>;
    // The booking store keeps it as `zip`; older callers said `zipCode`.
    for (const key of ["zip", "zipCode", "postalCode"]) {
      const v = a[key];
      if (typeof v === "string" && v.trim()) return v.trim();
    }
  }
  return undefined;
}

/**
 * One small beacon for something that happened on the address step, so the
 * funnel can say what people did there before they left. Fire-and-forget;
 * never blocks typing.
 */
const sentOnce = new Set<string>();
export function funnelSignal(
  signal: "typed" | "suggestions" | "no_suggestions" | "picked" | "fetch_failed" | "rejected",
  extra: Record<string, unknown> = {},
  once = false
) {
  const base = process.env.NEXT_PUBLIC_API_URL;
  const id = sessionId();
  if (!base || !id) return;
  if (once) {
    if (sentOnce.has(signal)) return;
    sentOnce.add(signal);
  }
  const s = useBookingStore.getState();
  void fetch(`${base}/api/booking/funnel`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: id, step: s.step, signal, leadSource: s.leadSource || undefined, ...extra }),
    keepalive: true,
  }).catch(() => undefined);
}

export function useFunnelBeacon() {
  const step = useBookingStore((s) => s.step);
  const lastSent = useRef<string>("");

  useEffect(() => {
    const base = process.env.NEXT_PUBLIC_API_URL;
    const id = sessionId();
    if (!base || !id) return;

    const timer = setTimeout(() => {
      const s = useBookingStore.getState();
      const body = {
        session_id: id,
        step: s.step,
        zip: zipOf(s.address),
        address: addressLine(s.address),
        items: (s.items || []).map((i) => ({
          category: (i as { category?: string }).category,
          name: (i as { name?: string }).name,
          quantity: (i as { quantity?: number }).quantity,
        })),
        scheduled_for: [s.scheduledDate, s.scheduledTimeSlot].filter(Boolean).join(" "),
        estimatedPrice: s.estimatedPrice || undefined,
        name: s.contact?.name?.trim() || undefined,
        phone: s.contact?.phone?.trim() || undefined,
        email: s.contact?.email?.trim() || undefined,
        leadSource: s.leadSource || undefined,
      };

      // Don't repeat an identical beacon.
      const fingerprint = JSON.stringify(body);
      if (fingerprint === lastSent.current) return;
      lastSent.current = fingerprint;

      void fetch(`${base}/api/booking/funnel`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: fingerprint,
        keepalive: true,
      }).catch(() => undefined);
    }, 1200);

    return () => clearTimeout(timer);
  }, [step]);
}
