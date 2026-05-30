"use client";

import { useCallback, useEffect, useState } from "react";
import {
  Loader2,
  RefreshCw,
  Truck,
  Star,
  Clock,
  MapPin,
  Package,
  CheckCircle2,
  CircleDashed,
  PhoneCall,
  AlertTriangle,
  XCircle,
} from "lucide-react";

import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { resolveApiBaseUrl } from "@/lib/api-base-url";

const API_BASE_URL = resolveApiBaseUrl();

// ---------------------------------------------------------------------------
// Types — mirrors GET /api/tracking/code/<code>
// ---------------------------------------------------------------------------
type Stage =
  | "waiting"
  | "assigned"
  | "en_route"
  | "on_site"
  | "complete"
  | "cancelled"
  | "issue"
  | "unknown";

interface Tracking {
  code: string;
  stage: Stage;
  message: string;
  scheduled_at: string | null;
  address_short: string | null;
  hauler: {
    first_name: string;
    truck_type: string | null;
    avg_rating: number;
  } | null;
  items_summary: string;
}

// The happy-path order of stages, used to render the progress rail.
const FLOW: { key: Stage; label: string; blurb: string }[] = [
  { key: "waiting", label: "Confirming hauler", blurb: "Locking in your crew" },
  { key: "assigned", label: "Hauler assigned", blurb: "You're on the schedule" },
  { key: "en_route", label: "On the way", blurb: "Your hauler is rolling out" },
  { key: "on_site", label: "On site", blurb: "Loading everything up" },
  { key: "complete", label: "Complete", blurb: "All hauled away" },
];

const SUPPORT_PHONE = "+15618883427";

function flowIndex(stage: Stage): number {
  const i = FLOW.findIndex((s) => s.key === stage);
  return i; // -1 for terminal/unknown stages
}

function formatWhen(iso: string | null): string | null {
  if (!iso) return null;
  try {
    const d = new Date(iso);
    return d.toLocaleString(undefined, {
      weekday: "short",
      month: "short",
      day: "numeric",
      hour: "numeric",
      minute: "2-digit",
    });
  } catch {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------
export default function GuestTracking({ code }: { code: string }) {
  const [tracking, setTracking] = useState<Tracking | null>(null);
  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshing, setRefreshing] = useState(false);

  const load = useCallback(
    async (initial = false) => {
      if (!initial) setRefreshing(true);
      try {
        const res = await fetch(
          `${API_BASE_URL}/api/tracking/code/${encodeURIComponent(code)}`,
          { headers: { "Content-Type": "application/json" } }
        );
        if (res.status === 404) {
          setError("We couldn't find a booking for that code. Double-check the link in your confirmation text.");
          setTracking(null);
        } else if (!res.ok) {
          setError("We're having trouble loading your tracking right now. Try again in a moment.");
        } else {
          const data = await res.json();
          setTracking(data.tracking as Tracking);
          setError(null);
        }
      } catch {
        setError("Network hiccup — check your connection and try again.");
      } finally {
        setIsLoading(false);
        setRefreshing(false);
      }
    },
    [code]
  );

  useEffect(() => {
    load(true);
    // Gentle polling — keeps the page fresh without sockets/auth.
    const id = setInterval(() => load(false), 45000);
    return () => clearInterval(id);
  }, [load]);

  // -------------------------------------------------------------------------
  // Loading
  // -------------------------------------------------------------------------
  if (isLoading) {
    return (
      <Shell>
        <div className="flex flex-col items-center justify-center py-28 gap-3">
          <Loader2 className="w-9 h-9 text-primary animate-spin" />
          <p className="text-sm text-muted-foreground font-medium">
            Pulling up your pickup…
          </p>
        </div>
      </Shell>
    );
  }

  // -------------------------------------------------------------------------
  // Error / not found
  // -------------------------------------------------------------------------
  if (error && !tracking) {
    return (
      <Shell>
        <Card className="border-border/60">
          <CardContent className="flex flex-col items-center text-center py-12 px-6 gap-4">
            <div className="w-14 h-14 rounded-2xl bg-muted flex items-center justify-center">
              <Package className="w-7 h-7 text-muted-foreground" />
            </div>
            <div>
              <h2 className="font-display text-xl font-bold">Booking not found</h2>
              <p className="text-sm text-muted-foreground mt-2 max-w-sm">{error}</p>
            </div>
            <Button variant="outline" size="sm" className="gap-2" onClick={() => load(false)}>
              <RefreshCw className="w-4 h-4" /> Try again
            </Button>
          </CardContent>
        </Card>
      </Shell>
    );
  }

  if (!tracking) return null;

  const idx = flowIndex(tracking.stage);
  const isTerminalGood = tracking.stage === "complete";
  const isCancelled = tracking.stage === "cancelled";
  const isIssue = tracking.stage === "issue" || tracking.stage === "unknown";
  const when = formatWhen(tracking.scheduled_at);

  // Accent the hero by state.
  const heroTone = isCancelled
    ? "from-muted to-muted"
    : isIssue
    ? "from-amber-500/15 to-amber-500/5"
    : "from-primary/15 to-primary/[0.03]";

  return (
    <Shell>
      {/* Hero status */}
      <div
        className={`relative overflow-hidden rounded-3xl border border-border/60 bg-gradient-to-br ${heroTone} px-6 py-8 sm:px-8 sm:py-10`}
      >
        {/* soft grain / glow accent */}
        <div className="pointer-events-none absolute -top-24 -right-16 h-56 w-56 rounded-full bg-primary/10 blur-3xl" />

        <div className="relative flex items-start justify-between gap-4">
          <div>
            <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-semibold">
              Booking #{tracking.code}
            </p>
            <h1 className="font-display text-[26px] leading-tight sm:text-3xl font-extrabold mt-2 max-w-md">
              {FLOW.find((f) => f.key === tracking.stage)?.label ??
                (isCancelled ? "Booking cancelled" : isIssue ? "We're on it" : "Tracking")}
            </h1>
            <p className="text-sm sm:text-[15px] text-muted-foreground mt-2 max-w-md leading-relaxed">
              {tracking.message}
            </p>
          </div>

          <StatusGlyph stage={tracking.stage} />
        </div>

        {/* meta chips */}
        <div className="relative flex flex-wrap gap-2 mt-6">
          {when && (
            <Chip icon={<Clock className="w-3.5 h-3.5" />}>{when}</Chip>
          )}
          {tracking.address_short && (
            <Chip icon={<MapPin className="w-3.5 h-3.5" />}>{tracking.address_short}</Chip>
          )}
          {tracking.items_summary && (
            <Chip icon={<Package className="w-3.5 h-3.5" />}>{tracking.items_summary}</Chip>
          )}
        </div>
      </div>

      {/* Progress rail — hidden for cancelled */}
      {!isCancelled && (
        <Card className="mt-5 border-border/60">
          <CardContent className="py-6">
            <ol className="relative">
              {FLOW.map((step, i) => {
                const done = idx >= 0 && i < idx;
                const active = idx >= 0 && i === idx;
                const future = idx < 0 || i > idx;
                const last = i === FLOW.length - 1;
                return (
                  <li key={step.key} className="relative flex gap-4 pb-7 last:pb-0">
                    {/* connector */}
                    {!last && (
                      <span
                        className={`absolute left-[13px] top-7 bottom-0 w-px ${
                          done ? "bg-primary" : "bg-border"
                        }`}
                      />
                    )}
                    {/* node */}
                    <span className="relative z-10 flex-shrink-0 mt-0.5">
                      {done ? (
                        <CheckCircle2 className="w-[27px] h-[27px] text-primary" />
                      ) : active ? (
                        <span className="relative flex h-[27px] w-[27px] items-center justify-center">
                          <span className="absolute inline-flex h-full w-full rounded-full bg-primary/30 animate-ping" />
                          <span className="relative inline-flex h-[15px] w-[15px] rounded-full bg-primary ring-4 ring-primary/20" />
                        </span>
                      ) : (
                        <CircleDashed className="w-[27px] h-[27px] text-muted-foreground/40" />
                      )}
                    </span>
                    {/* label */}
                    <div className={future ? "opacity-50" : ""}>
                      <p
                        className={`text-sm font-semibold leading-tight ${
                          active ? "text-primary" : "text-foreground"
                        }`}
                      >
                        {step.label}
                      </p>
                      <p className="text-xs text-muted-foreground mt-0.5">{step.blurb}</p>
                    </div>
                  </li>
                );
              })}
            </ol>
          </CardContent>
        </Card>
      )}

      {/* Crew card */}
      {tracking.hauler && !isCancelled && (
        <Card className="mt-5 border-border/60">
          <CardContent className="py-5">
            <p className="text-[11px] uppercase tracking-[0.18em] text-muted-foreground font-semibold mb-3">
              Your crew
            </p>
            <div className="flex items-center gap-3">
              <div className="w-12 h-12 rounded-2xl bg-primary/10 flex items-center justify-center text-primary font-display font-bold text-lg">
                {tracking.hauler.first_name.charAt(0).toUpperCase()}
              </div>
              <div className="min-w-0 flex-1">
                <p className="text-sm font-semibold truncate">{tracking.hauler.first_name}</p>
                <div className="flex items-center gap-1.5 mt-0.5 text-xs text-muted-foreground">
                  {tracking.hauler.avg_rating > 0 && (
                    <>
                      <Star className="w-3.5 h-3.5 text-amber-500 fill-amber-500" />
                      <span>{tracking.hauler.avg_rating.toFixed(1)}</span>
                      {tracking.hauler.truck_type && <span className="mx-1">·</span>}
                    </>
                  )}
                  {tracking.hauler.truck_type && (
                    <span className="inline-flex items-center gap-1">
                      <Truck className="w-3.5 h-3.5" />
                      {tracking.hauler.truck_type}
                    </span>
                  )}
                </div>
              </div>
            </div>
          </CardContent>
        </Card>
      )}

      {/* Need help — always available; the Sy lesson */}
      <Card className="mt-5 border-border/60 bg-muted/30">
        <CardContent className="py-5 flex items-center justify-between gap-4">
          <div className="min-w-0">
            <p className="text-sm font-semibold">Something not right?</p>
            <p className="text-xs text-muted-foreground mt-0.5">
              Talk to a real person about this pickup.
            </p>
          </div>
          <Button asChild size="sm" className="gap-2 flex-shrink-0">
            <a href={`tel:${SUPPORT_PHONE}`}>
              <PhoneCall className="w-4 h-4" /> Call us
            </a>
          </Button>
        </CardContent>
      </Card>

      {/* footer: refresh + live badge */}
      <div className="flex items-center justify-between mt-5 px-1">
        <Badge variant="outline" className="gap-1.5 text-xs font-medium border-primary/30 text-primary">
          <span className="relative flex h-2 w-2">
            <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
            <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
          </span>
          Auto-updating
        </Badge>
        <button
          onClick={() => load(false)}
          className="inline-flex items-center gap-1.5 text-xs text-muted-foreground hover:text-foreground transition-colors"
        >
          <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? "animate-spin" : ""}`} />
          Refresh
        </button>
      </div>
    </Shell>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------
function Shell({ children }: { children: React.ReactNode }) {
  return (
    <div className="min-h-[80vh] bg-background">
      <div className="max-w-lg mx-auto px-4 py-6 sm:py-10">{children}</div>
    </div>
  );
}

function Chip({ icon, children }: { icon: React.ReactNode; children: React.ReactNode }) {
  return (
    <span className="inline-flex items-center gap-1.5 rounded-full bg-background/70 border border-border/60 px-3 py-1 text-xs font-medium text-foreground backdrop-blur">
      <span className="text-muted-foreground">{icon}</span>
      {children}
    </span>
  );
}

function StatusGlyph({ stage }: { stage: Stage }) {
  const base = "w-12 h-12 rounded-2xl flex items-center justify-center flex-shrink-0";
  if (stage === "complete")
    return (
      <span className={`${base} bg-primary/15 text-primary`}>
        <CheckCircle2 className="w-6 h-6" />
      </span>
    );
  if (stage === "cancelled")
    return (
      <span className={`${base} bg-muted text-muted-foreground`}>
        <XCircle className="w-6 h-6" />
      </span>
    );
  if (stage === "issue" || stage === "unknown")
    return (
      <span className={`${base} bg-amber-500/15 text-amber-600`}>
        <AlertTriangle className="w-6 h-6" />
      </span>
    );
  return (
    <span className={`${base} bg-primary/15 text-primary`}>
      <Truck className="w-6 h-6" />
    </span>
  );
}
