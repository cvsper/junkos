"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import Link from "next/link";
import {
  Clock,
  Phone,
  Star,
  Truck,
  WifiOff,
  RefreshCw,
  Loader2,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import StatusTimeline from "@/components/tracking/status-timeline";

import { useTrackingStore } from "@/stores/tracking-store";
import { trackingApi } from "@/lib/api";
import {
  connectSocket,
  joinJobRoom,
  leaveJobRoom,
  disconnectSocket,
} from "@/lib/socket";

// Dynamic import for MapView -- no SSR (Mapbox GL requires the DOM)
const MapView = dynamic(() => import("@/components/tracking/map-view"), {
  ssr: false,
  loading: () => (
    <div className="w-full h-full min-h-[300px] rounded-lg bg-muted border border-border flex items-center justify-center">
      <div className="flex flex-col items-center gap-2">
        <Loader2 className="w-8 h-8 text-muted-foreground animate-spin" />
        <p className="text-xs text-muted-foreground">Loading map...</p>
      </div>
    </div>
  ),
});

// ---------------------------------------------------------------------------
// Props
// ---------------------------------------------------------------------------

interface TrackingPageProps {
  jobId: string;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function TrackingPage({ jobId }: TrackingPageProps) {
  const {
    status,
    contractorLocation,
    eta,
    isConnected,
  } = useTrackingStore();

  const [isLoading, setIsLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  // Pickup location from initial fetch (address.lat/lng from the job)
  const [pickupLocation, setPickupLocation] = useState<{
    lat: number;
    lng: number;
  } | null>(null);

  // -----------------------------------------------------------------------
  // Connect socket + fetch initial status
  // -----------------------------------------------------------------------
  useEffect(() => {
    let mounted = true;

    async function init() {
      try {
        // 1. Connect to socket + join room
        connectSocket();
        joinJobRoom(jobId);

        // 2. Fetch current status from REST API
        const data = await trackingApi.getStatus(jobId);
        if (!mounted) return;

        // Seed the store with the initial data
        if (data.status) {
          useTrackingStore.getState().setStatus(data.status);
        }
        if (data.contractorLocation) {
          useTrackingStore.getState().setContractorLocation(
            data.contractorLocation
          );
        }
        if (data.eta !== undefined && data.eta !== null) {
          useTrackingStore.getState().setEta(data.eta);
        }

        // Use contractor location as a fallback to derive pickup for now.
        // In production the server response would include the pickup address.
        // For demo purposes we set a static South Florida location.
        setPickupLocation({ lat: 26.1224, lng: -80.1373 });
      } catch (err) {
        if (!mounted) return;
        console.error("[tracking] failed to load initial status:", err);
        setError("Unable to load tracking data. Please try again.");
        // Still set a pickup location so the map renders
        setPickupLocation({ lat: 26.1224, lng: -80.1373 });
      } finally {
        if (mounted) setIsLoading(false);
      }
    }

    init();

    return () => {
      mounted = false;
      leaveJobRoom(jobId);
      disconnectSocket();
      useTrackingStore.getState().reset();
    };
  }, [jobId]);

  // -----------------------------------------------------------------------
  // Loading state
  // -----------------------------------------------------------------------
  if (isLoading) {
    return (
      <div className="max-w-7xl mx-auto px-4 py-8 sm:py-12">
        <div className="flex flex-col items-center justify-center py-24 gap-4">
          <Loader2 className="w-10 h-10 text-primary animate-spin" />
          <p className="text-sm text-muted-foreground font-medium">
            Connecting to live tracking...
          </p>
        </div>
      </div>
    );
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <div className="max-w-7xl mx-auto px-4 py-6 sm:py-10">
      {/* Breadcrumb */}
      <nav className="flex items-center gap-2 text-sm text-muted-foreground mb-5">
        <Link
          href="/dashboard"
          className="hover:text-foreground transition-colors"
        >
          My Jobs
        </Link>
        <span>/</span>
        <Link
          href={`/jobs/${jobId}`}
          className="hover:text-foreground transition-colors"
        >
          Job #{jobId.slice(0, 8)}
        </Link>
        <span>/</span>
        <span className="text-foreground">Track</span>
      </nav>

      {/* Header row */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 mb-6">
        <div>
          <h1 className="font-display text-2xl sm:text-3xl font-bold tracking-tight">
            Live Tracking
          </h1>
          <p className="text-muted-foreground text-sm mt-1">
            Real-time updates for your junk removal pickup.
          </p>
        </div>

        {/* Connection indicator */}
        <ConnectionBadge isConnected={isConnected} />
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-6 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive flex items-center gap-2">
          <WifiOff className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Two-column layout: map + sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Map - takes 2/3 width on desktop */}
        <div className="lg:col-span-2 h-[350px] sm:h-[450px] lg:h-[560px]">
          <MapView
            pickupLocation={pickupLocation}
            contractorLocation={contractorLocation}
          />
        </div>

        {/* Status sidebar - takes 1/3 width on desktop */}
        <div className="space-y-5">
          {/* Status timeline card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Job Status</CardTitle>
            </CardHeader>
            <CardContent>
              <StatusTimeline currentStatus={status} />
            </CardContent>
          </Card>

          {/* ETA card */}
          <Card>
            <CardContent className="pt-5">
              <div className="flex items-center gap-3">
                <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                  <Clock className="w-5 h-5 text-primary" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground font-medium uppercase tracking-wider">
                    Estimated Arrival
                  </p>
                  <p className="text-2xl font-display font-bold text-foreground">
                    {eta !== null && eta !== undefined ? (
                      <>
                        {eta}{" "}
                        <span className="text-sm font-medium text-muted-foreground">
                          min
                        </span>
                      </>
                    ) : (
                      <span className="text-muted-foreground">--</span>
                    )}
                  </p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Contractor info card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Your Crew</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="flex items-center gap-3 mb-4">
                {/* Avatar placeholder */}
                <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center text-muted-foreground">
                  <Truck className="w-5 h-5" />
                </div>
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium text-foreground truncate">
                    {status && status !== "pending"
                      ? "Crew Member"
                      : "Pending assignment"}
                  </p>
                  <div className="flex items-center gap-1 mt-0.5">
                    <Star className="w-3.5 h-3.5 text-amber-500 fill-amber-500" />
                    <span className="text-xs text-muted-foreground">
                      4.9 rating
                    </span>
                  </div>
                </div>
              </div>

              <div className="text-xs text-muted-foreground mb-4 flex items-center gap-1.5">
                <Truck className="w-3.5 h-3.5" />
                <span>Full-size pickup truck</span>
              </div>

              <Button variant="outline" className="w-full gap-2" size="sm">
                <Phone className="w-4 h-4" />
                Contact Crew
              </Button>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Sub-components
// ---------------------------------------------------------------------------

function ConnectionBadge({ isConnected }: { isConnected: boolean }) {
  if (isConnected) {
    return (
      <Badge
        variant="outline"
        className="gap-1.5 text-xs font-medium border-primary/30 text-primary"
      >
        <span className="relative flex h-2 w-2">
          <span className="animate-ping absolute inline-flex h-full w-full rounded-full bg-primary opacity-75" />
          <span className="relative inline-flex rounded-full h-2 w-2 bg-primary" />
        </span>
        Live
      </Badge>
    );
  }

  return (
    <Badge
      variant="outline"
      className="gap-1.5 text-xs font-medium border-destructive/30 text-destructive"
    >
      <RefreshCw className="w-3 h-3 animate-spin" />
      Reconnecting...
    </Badge>
  );
}
