"use client";

import { useEffect, useState, useCallback } from "react";
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
  Camera,
  MessageSquare,
} from "lucide-react";

import {
  Card,
  CardContent,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import StatusTimeline from "@/components/tracking/status-timeline";

import { useTrackingStore } from "@/stores/tracking-store";
import { trackingApi, jobsApi } from "@/lib/api";
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
// Types
// ---------------------------------------------------------------------------

interface TrackingPageProps {
  jobId: string;
}

interface JobContractor {
  id: string;
  user: { name: string | null; phone: string | null } | null;
  truck_type: string | null;
  avg_rating: number;
  total_jobs: number;
}

interface JobData {
  id: string;
  status: string;
  address: string;
  items: { category: string; quantity: number }[];
  photos: string[];
  total_price: number;
  scheduled_at: string | null;
  created_at: string;
  completed_at: string | null;
  notes: string | null;
  contractor?: JobContractor | null;
  rating?: {
    stars: number;
    comment: string | null;
    created_at: string;
  } | null;
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatEta(minutes: number): string {
  if (minutes < 1) return "< 1 min";
  if (minutes < 60) return `${Math.round(minutes)} min`;
  const hrs = Math.floor(minutes / 60);
  const mins = Math.round(minutes % 60);
  return mins > 0 ? `${hrs}h ${mins}m` : `${hrs}h`;
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
  const [job, setJob] = useState<JobData | null>(null);

  // Pickup location from initial fetch (address.lat/lng from the job)
  const [pickupLocation, setPickupLocation] = useState<{
    lat: number;
    lng: number;
  } | null>(null);

  // -----------------------------------------------------------------------
  // Fetch job details
  // -----------------------------------------------------------------------
  const fetchJobDetails = useCallback(async () => {
    try {
      const res = await jobsApi.get(jobId);
      if (res.job) {
        setJob(res.job as unknown as JobData);
      }
    } catch (err) {
      console.error("[tracking] failed to load job details:", err);
    }
  }, [jobId]);

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

        // 3. Also fetch full job details for contractor info, photos, etc.
        await fetchJobDetails();

        // Set a fallback pickup location
        setPickupLocation({ lat: 26.1224, lng: -80.1373 });
      } catch (err) {
        if (!mounted) return;
        console.error("[tracking] failed to load initial status:", err);
        setError("Unable to load tracking data. Please try again.");
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
  }, [jobId, fetchJobDetails]);

  // Periodically refresh job details to pick up contractor assignment, photos, etc.
  useEffect(() => {
    const interval = setInterval(fetchJobDetails, 30000);
    return () => clearInterval(interval);
  }, [fetchJobDetails]);

  // Derive states
  const isCompleted = status === "completed" || job?.status === "completed";
  const isCancelled = status === "cancelled" || job?.status === "cancelled";
  const hasContractor = !!job?.contractor;
  const hasPhotos = job?.photos && job.photos.length > 0;
  const hasRating = !!job?.rating;

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

        <div className="flex items-center gap-3">
          {/* Connection indicator */}
          <ConnectionBadge isConnected={isConnected} />

          {/* Quick links */}
          <Link href={`/jobs/${jobId}`}>
            <Button variant="outline" size="sm">
              Job Details
            </Button>
          </Link>
          {isCompleted && (
            <Link href={`/jobs/${jobId}/receipt`}>
              <Button variant="outline" size="sm">
                View Receipt
              </Button>
            </Link>
          )}
        </div>
      </div>

      {/* Error banner */}
      {error && (
        <div className="mb-6 rounded-lg border border-destructive/50 bg-destructive/10 px-4 py-3 text-sm text-destructive flex items-center gap-2">
          <WifiOff className="w-4 h-4 flex-shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {/* Cancelled banner */}
      {isCancelled && (
        <div className="mb-6 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-700 flex items-center gap-2">
          <span className="font-medium">This job has been cancelled.</span>
        </div>
      )}

      {/* Two-column layout: map + sidebar */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Map - takes 2/3 width on desktop */}
        <div className="lg:col-span-2 space-y-6">
          <div className="h-[350px] sm:h-[450px] lg:h-[480px]">
            <MapView
              pickupLocation={pickupLocation}
              contractorLocation={contractorLocation}
            />
          </div>

          {/* Proof Photos -- shown when completed and has photos */}
          {isCompleted && hasPhotos && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg flex items-center gap-2">
                  <Camera className="w-5 h-5 text-muted-foreground" />
                  Proof Photos
                </CardTitle>
              </CardHeader>
              <CardContent>
                <div className="grid grid-cols-2 sm:grid-cols-3 gap-3">
                  {job!.photos.map((url, idx) => (
                    <div
                      key={idx}
                      className="aspect-square rounded-lg overflow-hidden border border-border bg-muted"
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img
                        src={url}
                        alt={`Job photo ${idx + 1}`}
                        className="w-full h-full object-cover hover:scale-105 transition-transform cursor-pointer"
                      />
                    </div>
                  ))}
                </div>
              </CardContent>
            </Card>
          )}
        </div>

        {/* Status sidebar - takes 1/3 width on desktop */}
        <div className="space-y-5">
          {/* Step-by-step progress indicator */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Job Progress</CardTitle>
            </CardHeader>
            <CardContent>
              <StatusTimeline currentStatus={status} />
            </CardContent>
          </Card>

          {/* ETA card -- only shown during active statuses */}
          {!isCompleted && !isCancelled && (
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
                        <>{formatEta(eta)}</>
                      ) : (
                        <span className="text-base text-muted-foreground font-normal">
                          Calculating...
                        </span>
                      )}
                    </p>
                  </div>
                </div>
              </CardContent>
            </Card>
          )}

          {/* Driver / Contractor info card */}
          <Card>
            <CardHeader className="pb-3">
              <CardTitle className="text-lg">Your Crew</CardTitle>
            </CardHeader>
            <CardContent>
              {hasContractor && job?.contractor ? (
                <div className="space-y-4">
                  <div className="flex items-center gap-3">
                    {/* Avatar */}
                    <div className="w-12 h-12 rounded-full bg-primary/10 flex items-center justify-center text-primary font-semibold text-lg">
                      {job.contractor.user?.name
                        ? job.contractor.user.name.charAt(0).toUpperCase()
                        : "C"}
                    </div>
                    <div className="min-w-0 flex-1">
                      <p className="text-sm font-semibold text-foreground truncate">
                        {job.contractor.user?.name ?? "Contractor"}
                      </p>
                      <div className="flex items-center gap-1 mt-0.5">
                        <Star className="w-3.5 h-3.5 text-amber-500 fill-amber-500" />
                        <span className="text-xs text-muted-foreground">
                          {job.contractor.avg_rating.toFixed(1)} rating
                        </span>
                        <span className="text-xs text-muted-foreground mx-1">
                          &middot;
                        </span>
                        <span className="text-xs text-muted-foreground">
                          {job.contractor.total_jobs} jobs
                        </span>
                      </div>
                    </div>
                  </div>

                  {job.contractor.truck_type && (
                    <div className="text-xs text-muted-foreground flex items-center gap-1.5">
                      <Truck className="w-3.5 h-3.5" />
                      <span>{job.contractor.truck_type}</span>
                    </div>
                  )}

                  <Separator />

                  {job.contractor.user?.phone && (
                    <Button
                      variant="outline"
                      className="w-full gap-2"
                      size="sm"
                      asChild
                    >
                      <a href={`tel:${job.contractor.user.phone}`}>
                        <Phone className="w-4 h-4" />
                        Contact Crew
                      </a>
                    </Button>
                  )}
                  {!job.contractor.user?.phone && (
                    <Button variant="outline" className="w-full gap-2" size="sm" disabled>
                      <Phone className="w-4 h-4" />
                      Contact Crew
                    </Button>
                  )}
                </div>
              ) : (
                <div className="flex flex-col items-center py-4 text-center">
                  <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
                    <Truck className="w-5 h-5 text-muted-foreground" />
                  </div>
                  <p className="text-sm font-medium text-muted-foreground">
                    Pending assignment
                  </p>
                  <p className="text-xs text-muted-foreground mt-1">
                    A crew member will be assigned shortly.
                  </p>
                </div>
              )}
            </CardContent>
          </Card>

          {/* Rate This Job card -- only when completed and no rating yet */}
          {isCompleted && !hasRating && (
            <Card className="border-primary/20 bg-primary/5">
              <CardContent className="pt-5">
                <div className="flex items-center gap-3">
                  <div className="flex-shrink-0 w-10 h-10 rounded-full bg-primary/10 flex items-center justify-center">
                    <MessageSquare className="w-5 h-5 text-primary" />
                  </div>
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-foreground">
                      How was your pickup?
                    </p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      Your feedback helps us improve.
                    </p>
                  </div>
                </div>
                <Link href={`/jobs/${jobId}`} className="block mt-3">
                  <Button className="w-full gap-2" size="sm">
                    <Star className="w-4 h-4" />
                    Rate This Job
                  </Button>
                </Link>
              </CardContent>
            </Card>
          )}

          {/* Existing rating display */}
          {isCompleted && hasRating && job?.rating && (
            <Card>
              <CardHeader className="pb-3">
                <CardTitle className="text-lg">Your Rating</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="flex items-center gap-1 mb-2">
                  {[1, 2, 3, 4, 5].map((s) => (
                    <Star
                      key={s}
                      className={`w-5 h-5 ${
                        s <= job.rating!.stars
                          ? "text-amber-500 fill-amber-500"
                          : "text-gray-300"
                      }`}
                    />
                  ))}
                  <span className="text-sm font-medium ml-2">
                    {job.rating.stars} / 5
                  </span>
                </div>
                {job.rating.comment && (
                  <p className="text-sm text-muted-foreground">
                    &ldquo;{job.rating.comment}&rdquo;
                  </p>
                )}
              </CardContent>
            </Card>
          )}
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
