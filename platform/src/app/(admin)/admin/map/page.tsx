"use client";

import { useEffect, useRef, useState, useCallback } from "react";
import mapboxgl from "mapbox-gl";
import "mapbox-gl/dist/mapbox-gl.css";
import { RefreshCw, AlertCircle, MapPin } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import {
  adminApi,
  type MapContractorPoint,
  type MapJobPoint,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

const SOUTH_FLORIDA_CENTER: [number, number] = [-80.15, 26.1];
const DEFAULT_ZOOM = 10;
const REFRESH_INTERVAL_MS = 30_000;

/** Colour for a job marker based on its status string. */
function jobStatusColor(status: string): string {
  switch (status.toLowerCase()) {
    case "pending":
      return "#eab308"; // yellow-500
    case "accepted":
    case "assigned":
      return "#3b82f6"; // blue-500
    case "en_route":
      return "#f97316"; // orange-500
    case "arrived":
      return "#8b5cf6"; // violet-500
    case "started":
      return "#ec4899"; // pink-500
    case "completed":
      return "#22c55e"; // green-500
    default:
      return "#6b7280"; // gray-500
  }
}

/** Friendly label for a job status. */
function jobStatusLabel(status: string): string {
  switch (status.toLowerCase()) {
    case "pending":
      return "Pending";
    case "accepted":
    case "assigned":
      return "Assigned";
    case "en_route":
      return "En Route";
    case "arrived":
      return "Arrived";
    case "started":
      return "In Progress";
    case "completed":
      return "Completed";
    default:
      return status;
  }
}

/** Build an SVG circle data-URL for use as a map marker image. */
function circleIcon(color: string, size = 28): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">
    <circle cx="${size / 2}" cy="${size / 2}" r="${size / 2 - 2}" fill="${color}" stroke="white" stroke-width="2"/>
  </svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

/** Build a pin SVG data-URL for job markers. */
function pinIcon(color: string): string {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" width="28" height="36" viewBox="0 0 28 36">
    <path d="M14 0C6.27 0 0 6.27 0 14c0 10.5 14 22 14 22s14-11.5 14-22C28 6.27 21.73 0 14 0z" fill="${color}" stroke="white" stroke-width="1.5"/>
    <circle cx="14" cy="14" r="5" fill="white"/>
  </svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdminMapPage() {
  const mapContainer = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<mapboxgl.Marker[]>([]);

  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null);
  const [contractorCount, setContractorCount] = useState(0);
  const [jobCount, setJobCount] = useState(0);
  const [refreshing, setRefreshing] = useState(false);

  // -----------------------------------------------------------------------
  // Clear existing markers
  // -----------------------------------------------------------------------
  const clearMarkers = useCallback(() => {
    markersRef.current.forEach((m) => m.remove());
    markersRef.current = [];
  }, []);

  // -----------------------------------------------------------------------
  // Render markers from API data
  // -----------------------------------------------------------------------
  const renderMarkers = useCallback(
    (contractors: MapContractorPoint[], jobs: MapJobPoint[]) => {
      const map = mapRef.current;
      if (!map) return;

      clearMarkers();

      // --- Contractor markers (green dots -- all returned are online) ---
      contractors.forEach((c) => {
        const el = document.createElement("div");
        el.style.width = "24px";
        el.style.height = "24px";
        el.style.backgroundImage = `url("${circleIcon("#22c55e", 24)}")`;
        el.style.backgroundSize = "contain";
        el.style.cursor = "pointer";

        const popup = new mapboxgl.Popup({ offset: 16, maxWidth: "260px" }).setHTML(`
          <div style="font-family:system-ui,sans-serif;padding:4px 0;">
            <p style="font-weight:600;margin:0 0 4px;">${c.name || "Unknown Contractor"}</p>
            <p style="margin:0;font-size:13px;color:#6b7280;">Truck: ${c.truck_type || "N/A"}</p>
            <p style="margin:0;font-size:13px;color:#6b7280;">Rating: ${c.avg_rating ? c.avg_rating.toFixed(1) : "--"} | Jobs: ${c.total_jobs ?? 0}</p>
            <span style="display:inline-block;margin-top:6px;padding:2px 8px;border-radius:9999px;font-size:11px;font-weight:600;background:#dcfce7;color:#16a34a;">Online</span>
          </div>
        `);

        const marker = new mapboxgl.Marker({ element: el })
          .setLngLat([c.lng, c.lat])
          .setPopup(popup)
          .addTo(map);

        // Tooltip on hover
        const tooltip = new mapboxgl.Popup({
          offset: 16,
          closeButton: false,
          closeOnClick: false,
          className: "map-tooltip",
        }).setHTML(
          `<span style="font-family:system-ui,sans-serif;font-size:12px;font-weight:500;">${c.name || "Contractor"}</span>`
        );

        el.addEventListener("mouseenter", () => {
          if (!marker.getPopup()?.isOpen()) {
            tooltip.setLngLat([c.lng, c.lat]).addTo(map);
          }
        });
        el.addEventListener("mouseleave", () => tooltip.remove());
        el.addEventListener("click", () => tooltip.remove());

        markersRef.current.push(marker);
      });

      // --- Job markers (colored pins) ---
      jobs.forEach((j) => {
        const color = jobStatusColor(j.status);
        const el = document.createElement("div");
        el.style.width = "28px";
        el.style.height = "36px";
        el.style.backgroundImage = `url("${pinIcon(color)}")`;
        el.style.backgroundSize = "contain";
        el.style.cursor = "pointer";

        const popup = new mapboxgl.Popup({ offset: 24, maxWidth: "280px" }).setHTML(`
          <div style="font-family:system-ui,sans-serif;padding:4px 0;">
            <p style="font-weight:600;margin:0 0 4px;">${j.address || "Job"}</p>
            <p style="margin:0;font-size:13px;color:#6b7280;">Customer: ${j.customer_name || "N/A"}</p>
            <p style="margin:0;font-size:13px;color:#6b7280;">Price: $${j.total_price != null ? j.total_price.toFixed(2) : "--"}</p>
            <span style="display:inline-block;margin-top:6px;padding:2px 8px;border-radius:9999px;font-size:11px;font-weight:600;background:${color}20;color:${color};">${jobStatusLabel(j.status)}</span>
            ${j.driver_id ? `<p style="margin:4px 0 0;font-size:12px;color:#6b7280;">Assigned to driver</p>` : ""}
          </div>
        `);

        const marker = new mapboxgl.Marker({ element: el })
          .setLngLat([j.lng, j.lat])
          .setPopup(popup)
          .addTo(map);

        markersRef.current.push(marker);
      });
    },
    [clearMarkers]
  );

  // -----------------------------------------------------------------------
  // Fetch map data
  // -----------------------------------------------------------------------
  const fetchData = useCallback(
    async (showRefreshing = false) => {
      if (showRefreshing) setRefreshing(true);
      try {
        const data = await adminApi.mapData();
        setContractorCount(data.contractors?.length ?? 0);
        setJobCount(data.jobs?.length ?? 0);
        renderMarkers(data.contractors ?? [], data.jobs ?? []);
        setLastUpdated(new Date());
        setError(null);
      } catch (err) {
        setError(
          err instanceof Error ? err.message : "Failed to load map data"
        );
      } finally {
        setLoading(false);
        setRefreshing(false);
      }
    },
    [renderMarkers]
  );

  // -----------------------------------------------------------------------
  // Initialize Mapbox on mount
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!mapContainer.current || mapRef.current) return;

    const token = process.env.NEXT_PUBLIC_MAPBOX_TOKEN;
    if (!token) {
      setError("NEXT_PUBLIC_MAPBOX_TOKEN is not set");
      setLoading(false);
      return;
    }

    mapboxgl.accessToken = token;

    const map = new mapboxgl.Map({
      container: mapContainer.current,
      style: "mapbox://styles/mapbox/light-v11",
      center: SOUTH_FLORIDA_CENTER,
      zoom: DEFAULT_ZOOM,
    });

    map.addControl(new mapboxgl.NavigationControl(), "bottom-right");

    mapRef.current = map;

    map.on("load", () => {
      fetchData();
    });

    return () => {
      clearMarkers();
      map.remove();
      mapRef.current = null;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // -----------------------------------------------------------------------
  // Polling interval
  // -----------------------------------------------------------------------
  useEffect(() => {
    const interval = setInterval(() => {
      fetchData();
    }, REFRESH_INTERVAL_MS);

    return () => clearInterval(interval);
  }, [fetchData]);

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <div className="flex flex-col h-[calc(100vh-7rem)]">
      {/* Header */}
      <div className="flex items-center justify-between mb-4 flex-shrink-0">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Live Map
          </h1>
          <p className="text-muted-foreground mt-1">
            Real-time view of contractors and active jobs.
          </p>
        </div>
        <div className="flex items-center gap-3">
          {lastUpdated && (
            <span className="text-xs text-muted-foreground hidden sm:inline">
              Updated{" "}
              {lastUpdated.toLocaleTimeString([], {
                hour: "2-digit",
                minute: "2-digit",
                second: "2-digit",
              })}
            </span>
          )}
          <Button
            variant="outline"
            size="sm"
            onClick={() => fetchData(true)}
            disabled={refreshing}
          >
            <RefreshCw
              className={`mr-2 h-4 w-4 ${refreshing ? "animate-spin" : ""}`}
            />
            Refresh
          </Button>
        </div>
      </div>

      {/* Stats bar */}
      <div className="flex items-center gap-3 mb-4 flex-shrink-0 flex-wrap">
        <Badge
          variant="secondary"
          className="bg-green-500/15 text-green-700 border-green-300 text-xs gap-1.5 px-3 py-1"
        >
          <span className="flex h-2 w-2 rounded-full bg-green-500" />
          {contractorCount} contractor{contractorCount !== 1 ? "s" : ""} online
        </Badge>
        <Badge
          variant="secondary"
          className="bg-blue-500/15 text-blue-700 border-blue-300 text-xs gap-1.5 px-3 py-1"
        >
          <MapPin className="h-3 w-3" />
          {jobCount} active job{jobCount !== 1 ? "s" : ""}
        </Badge>
      </div>

      {/* Error banner */}
      {error && (
        <Card className="mb-4 flex-shrink-0">
          <CardContent className="flex items-center gap-3 py-3 px-4">
            <AlertCircle className="h-5 w-5 text-destructive flex-shrink-0" />
            <p className="text-sm text-muted-foreground flex-1">{error}</p>
            <Button variant="outline" size="sm" onClick={() => fetchData(true)}>
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Map container */}
      <div className="relative flex-1 rounded-lg border border-border overflow-hidden bg-muted">
        <div ref={mapContainer} className="absolute inset-0" />

        {/* Loading overlay */}
        {loading && (
          <div className="absolute inset-0 flex items-center justify-center bg-background/60 z-10">
            <div className="flex flex-col items-center gap-2">
              <RefreshCw className="h-6 w-6 animate-spin text-primary" />
              <p className="text-sm text-muted-foreground">Loading map...</p>
            </div>
          </div>
        )}

        {/* Legend */}
        <div className="absolute top-3 right-3 z-10">
          <Card className="shadow-lg">
            <CardContent className="p-3 space-y-2 min-w-[160px]">
              <p className="text-xs font-semibold text-foreground uppercase tracking-wider mb-2">
                Legend
              </p>

              {/* Contractors */}
              <div className="space-y-1">
                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                  Contractors
                </p>
                <div className="flex items-center gap-2">
                  <span className="flex h-3 w-3 rounded-full bg-green-500 border border-white shadow-sm" />
                  <span className="text-xs text-muted-foreground">Online</span>
                </div>
                <div className="flex items-center gap-2">
                  <span className="flex h-3 w-3 rounded-full bg-gray-400 border border-white shadow-sm" />
                  <span className="text-xs text-muted-foreground">Offline</span>
                </div>
              </div>

              {/* Divider */}
              <div className="border-t border-border" />

              {/* Jobs */}
              <div className="space-y-1">
                <p className="text-[10px] font-medium text-muted-foreground uppercase tracking-wider">
                  Jobs
                </p>
                {[
                  { label: "Pending", color: "#eab308" },
                  { label: "Assigned", color: "#3b82f6" },
                  { label: "En Route", color: "#f97316" },
                  { label: "Arrived", color: "#8b5cf6" },
                  { label: "In Progress", color: "#ec4899" },
                  { label: "Completed", color: "#22c55e" },
                ].map((item) => (
                  <div key={item.label} className="flex items-center gap-2">
                    <svg width="12" height="16" viewBox="0 0 12 16">
                      <path
                        d="M6 0C2.69 0 0 2.69 0 6c0 4.5 6 10 6 10s6-5.5 6-10C12 2.69 9.31 0 6 0z"
                        fill={item.color}
                      />
                      <circle cx="6" cy="6" r="2" fill="white" />
                    </svg>
                    <span className="text-xs text-muted-foreground">
                      {item.label}
                    </span>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  );
}
