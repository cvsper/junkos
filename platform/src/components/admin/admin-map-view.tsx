"use client";

import { useRef, useEffect, useState, useCallback } from "react";
import { MapPin, RefreshCw, Wifi, WifiOff } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import {
  adminApi,
  type MapContractorPoint,
  type MapJobPoint,
} from "@/lib/api";
import { useAdminMapSocket } from "@/hooks/use-admin-map-socket";
import type { Map as MapboxMap, Marker as MapboxMarker, Popup as MapboxPopup } from "mapbox-gl";

import "mapbox-gl/dist/mapbox-gl.css";

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";
const DEFAULT_CENTER = { lat: 26.1224, lng: -80.1373 }; // South Florida
const DEFAULT_ZOOM = 10;
const POLL_INTERVAL_MS = 30_000;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdminMapView() {
  const containerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<MapboxMap | null>(null);
  const contractorMarkersRef = useRef<Map<string, MapboxMarker>>(new Map());
  const jobMarkersRef = useRef<Map<string, MapboxMarker>>(new Map());

  const [mapLoaded, setMapLoaded] = useState(false);
  const [contractors, setContractors] = useState<MapContractorPoint[]>([]);
  const [jobs, setJobs] = useState<MapJobPoint[]>([]);
  const [refreshing, setRefreshing] = useState(false);

  // -----------------------------------------------------------------------
  // Data fetching
  // -----------------------------------------------------------------------

  const fetchMapData = useCallback(async () => {
    try {
      setRefreshing(true);
      const res = await adminApi.mapData();
      setContractors(res.contractors);
      setJobs(res.jobs);
    } catch (err) {
      console.error("[admin-map] failed to fetch map data:", err);
    } finally {
      setRefreshing(false);
    }
  }, []);

  // Initial fetch + polling fallback
  useEffect(() => {
    fetchMapData();
    const interval = setInterval(fetchMapData, POLL_INTERVAL_MS);
    return () => clearInterval(interval);
  }, [fetchMapData]);

  // -----------------------------------------------------------------------
  // Socket.IO for live updates
  // -----------------------------------------------------------------------

  const { isConnected } = useAdminMapSocket({
    onContractorLocation: useCallback(
      (data: { contractor_id: string; lat: number; lng: number }) => {
        setContractors((prev) => {
          const idx = prev.findIndex((c) => c.id === data.contractor_id);
          if (idx === -1) {
            // Unknown contractor — refetch to get full info
            fetchMapData();
            return prev;
          }
          const next = [...prev];
          next[idx] = { ...next[idx], lat: data.lat, lng: data.lng };
          return next;
        });
      },
      [fetchMapData]
    ),
    onJobStatus: useCallback((_data: { job_id: string; status: string }) => {
      // Re-fetch to get updated job statuses
      fetchMapData();
    }, [fetchMapData]),
  });

  // -----------------------------------------------------------------------
  // Initialize Mapbox map
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (!MAPBOX_TOKEN || !containerRef.current) return;

    let cancelled = false;

    import("mapbox-gl").then((mod) => {
      if (cancelled || !containerRef.current) return;

      const mapboxgl = mod.default ?? mod;
      mapboxgl.accessToken = MAPBOX_TOKEN;

      const map = new mapboxgl.Map({
        container: containerRef.current,
        style: "mapbox://styles/mapbox/streets-v12",
        center: [DEFAULT_CENTER.lng, DEFAULT_CENTER.lat],
        zoom: DEFAULT_ZOOM,
      });

      map.addControl(new mapboxgl.NavigationControl(), "top-right");

      map.on("load", () => {
        if (!cancelled) setMapLoaded(true);
      });

      mapRef.current = map;
    });

    const cMarkers = contractorMarkersRef.current;
    const jMarkers = jobMarkersRef.current;

    return () => {
      cancelled = true;
      // Clean up markers
      cMarkers.forEach((m) => m.remove());
      cMarkers.clear();
      jMarkers.forEach((m) => m.remove());
      jMarkers.clear();
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      setMapLoaded(false);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // -----------------------------------------------------------------------
  // Reconcile contractor markers
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;

    import("mapbox-gl").then((mod) => {
      const mapboxgl = mod.default ?? mod;
      if (!mapRef.current) return;

      const map = mapRef.current;
      const existing = contractorMarkersRef.current;
      const currentIds = new Set(contractors.map((c) => c.id));

      // Remove stale markers
      existing.forEach((marker, id) => {
        if (!currentIds.has(id)) {
          marker.remove();
          existing.delete(id);
        }
      });

      // Add or update
      contractors.forEach((c) => {
        const marker = existing.get(c.id);
        if (marker) {
          marker.setLngLat([c.lng, c.lat]);
          // Update popup content
          const popup = marker.getPopup();
          if (popup) {
            popup.setHTML(contractorPopupHTML(c));
          }
        } else {
          const el = createContractorMarkerEl();
          const popup = new mapboxgl.Popup({ offset: 16, closeButton: false })
            .setHTML(contractorPopupHTML(c));
          const newMarker = new mapboxgl.Marker({ element: el })
            .setLngLat([c.lng, c.lat])
            .setPopup(popup)
            .addTo(map);
          existing.set(c.id, newMarker);
        }
      });
    });
  }, [contractors, mapLoaded]);

  // -----------------------------------------------------------------------
  // Reconcile job markers
  // -----------------------------------------------------------------------

  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;

    import("mapbox-gl").then((mod) => {
      const mapboxgl = mod.default ?? mod;
      if (!mapRef.current) return;

      const map = mapRef.current;
      const existing = jobMarkersRef.current;
      const currentIds = new Set(jobs.map((j) => j.id));

      // Remove stale markers
      existing.forEach((marker, id) => {
        if (!currentIds.has(id)) {
          marker.remove();
          existing.delete(id);
        }
      });

      // Add or update
      jobs.forEach((j) => {
        const marker = existing.get(j.id);
        if (marker) {
          marker.setLngLat([j.lng, j.lat]);
          const popup = marker.getPopup();
          if (popup) {
            popup.setHTML(jobPopupHTML(j));
          }
        } else {
          const el = createJobMarkerEl();
          const popup = new mapboxgl.Popup({ offset: 20, closeButton: false })
            .setHTML(jobPopupHTML(j));
          const newMarker = new mapboxgl.Marker({ element: el })
            .setLngLat([j.lng, j.lat])
            .setPopup(popup)
            .addTo(map);
          existing.set(j.id, newMarker);
        }
      });
    });
  }, [jobs, mapLoaded]);

  // -----------------------------------------------------------------------
  // Fallback: no Mapbox token
  // -----------------------------------------------------------------------

  if (!MAPBOX_TOKEN) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="font-display text-lg font-semibold">
            Live Map
          </CardTitle>
        </CardHeader>
        <CardContent>
          <div className="w-full h-[calc(100vh-220px)] min-h-[400px] rounded-lg bg-muted border border-border flex flex-col items-center justify-center gap-3 p-6">
            <MapPin className="w-10 h-10 text-muted-foreground" />
            <p className="text-sm font-medium text-muted-foreground text-center">
              Map unavailable &mdash; configure NEXT_PUBLIC_MAPBOX_TOKEN
            </p>
            <p className="text-xs text-muted-foreground">
              {contractors.length} contractors online, {jobs.length} active jobs
            </p>
          </div>
        </CardContent>
      </Card>
    );
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------

  return (
    <Card>
      <CardHeader className="pb-3">
        <div className="flex items-center justify-between">
          <CardTitle className="font-display text-lg font-semibold">
            Live Map
          </CardTitle>
          <div className="flex items-center gap-2">
            {/* Connection indicator */}
            <span className="flex items-center gap-1.5 text-xs text-muted-foreground">
              {isConnected ? (
                <>
                  <Wifi className="h-3.5 w-3.5 text-emerald-500" />
                  <span className="text-emerald-600">Live</span>
                </>
              ) : (
                <>
                  <WifiOff className="h-3.5 w-3.5 text-amber-500" />
                  <span className="text-amber-600">Polling</span>
                </>
              )}
            </span>
            {/* Refresh button */}
            <Button
              variant="ghost"
              size="icon"
              className="h-7 w-7"
              onClick={fetchMapData}
              disabled={refreshing}
            >
              <RefreshCw
                className={`h-3.5 w-3.5 ${refreshing ? "animate-spin" : ""}`}
              />
            </Button>
          </div>
        </div>
      </CardHeader>
      <CardContent className="p-0">
        <div className="relative w-full h-[calc(100vh-220px)] min-h-[400px] rounded-b-lg overflow-hidden">
          <div ref={containerRef} className="w-full h-full" />

          {/* Loading overlay */}
          {!mapLoaded && (
            <div className="absolute inset-0 flex items-center justify-center bg-muted">
              <div className="flex flex-col items-center gap-2">
                <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
                <p className="text-xs text-muted-foreground">Loading map...</p>
              </div>
            </div>
          )}

          {/* Legend */}
          {mapLoaded && (
            <div className="absolute bottom-3 left-3 bg-white/90 backdrop-blur-sm rounded-lg px-3 py-2 shadow-md border border-border text-xs space-y-1">
              <div className="flex items-center gap-2">
                <span className="inline-block w-3 h-3 rounded-full bg-emerald-500" />
                <span>Contractors ({contractors.length})</span>
              </div>
              <div className="flex items-center gap-2">
                <span className="inline-block w-3 h-3 rounded-sm bg-orange-500" style={{ borderRadius: "50% 50% 50% 0", transform: "rotate(-45deg)" }} />
                <span>Active Jobs ({jobs.length})</span>
              </div>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Marker element factories
// ---------------------------------------------------------------------------

function createContractorMarkerEl(): HTMLDivElement {
  const el = document.createElement("div");
  el.style.cssText = `
    width: 20px;
    height: 20px;
    border-radius: 50%;
    background: hsl(142 71% 45%);
    border: 2.5px solid white;
    box-shadow: 0 0 0 2px hsla(142 71% 45% / 0.3), 0 2px 6px rgba(0,0,0,0.25);
    cursor: pointer;
  `;
  return el;
}

function createJobMarkerEl(): HTMLDivElement {
  const el = document.createElement("div");
  el.style.cssText = `
    width: 26px;
    height: 26px;
    border-radius: 50% 50% 50% 0;
    background: hsl(25 95% 53%);
    transform: rotate(-45deg);
    border: 2.5px solid white;
    box-shadow: 0 2px 6px rgba(0,0,0,0.3);
    cursor: pointer;
  `;
  const dot = document.createElement("div");
  dot.style.cssText = `
    width: 8px;
    height: 8px;
    background: white;
    border-radius: 50%;
    position: absolute;
    top: 50%;
    left: 50%;
    transform: translate(-50%, -50%);
  `;
  el.appendChild(dot);
  return el;
}

// ---------------------------------------------------------------------------
// Popup HTML factories
// ---------------------------------------------------------------------------

function contractorPopupHTML(c: MapContractorPoint): string {
  const rating = c.avg_rating ? `${c.avg_rating.toFixed(1)} stars` : "No rating";
  return `
    <div style="font-family: Inter, system-ui, sans-serif; font-size: 13px; line-height: 1.4; min-width: 140px;">
      <div style="font-weight: 600; margin-bottom: 2px;">${escapeHtml(c.name ?? "Unknown")}</div>
      <div style="color: #666;">${escapeHtml(c.truck_type ?? "N/A")}</div>
      <div style="color: #666;">${rating} &middot; ${c.total_jobs} jobs</div>
    </div>
  `;
}

function jobPopupHTML(j: MapJobPoint): string {
  const statusLabel = j.status.replace(/_/g, " ").replace(/\b\w/g, (l) => l.toUpperCase());
  const price = j.total_price
    ? `$${j.total_price.toFixed(2)}`
    : "TBD";
  return `
    <div style="font-family: Inter, system-ui, sans-serif; font-size: 13px; line-height: 1.4; min-width: 160px;">
      <div style="font-weight: 600; margin-bottom: 2px;">${escapeHtml(j.address)}</div>
      <div style="color: #666;">${statusLabel} &middot; ${price}</div>
      ${j.customer_name ? `<div style="color: #999; font-size: 11px;">${escapeHtml(j.customer_name)}</div>` : ""}
    </div>
  `;
}

function escapeHtml(str: string): string {
  const div = document.createElement("div");
  div.textContent = str;
  return div.innerHTML;
}
