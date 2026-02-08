"use client";

import { useRef, useEffect, useState } from "react";
import { MapPin } from "lucide-react";
import type { Map as MapboxMap, Marker as MapboxMarker } from "mapbox-gl";

// Import mapbox-gl CSS so the map renders correctly
import "mapbox-gl/dist/mapbox-gl.css";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface LatLng {
  lat: number;
  lng: number;
}

interface MapViewProps {
  pickupLocation?: LatLng | null;
  contractorLocation?: LatLng | null;
}

// ---------------------------------------------------------------------------
// Constants
// ---------------------------------------------------------------------------

const MAPBOX_TOKEN = process.env.NEXT_PUBLIC_MAPBOX_TOKEN ?? "";

const DEFAULT_CENTER: LatLng = { lat: 26.1224, lng: -80.1373 }; // South Florida
const DEFAULT_ZOOM = 11;

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function MapView({
  pickupLocation,
  contractorLocation,
}: MapViewProps) {
  const containerRef = useRef<HTMLDivElement>(null);

  // We store the map + markers as refs so we can update them without
  // re-initialising the entire map on every location change.
  const mapRef = useRef<MapboxMap | null>(null);
  const pickupMarkerRef = useRef<MapboxMarker | null>(null);
  const contractorMarkerRef = useRef<MapboxMarker | null>(null);

  const [mapLoaded, setMapLoaded] = useState(false);

  // -----------------------------------------------------------------------
  // Initialise map
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!MAPBOX_TOKEN || !containerRef.current) return;

    let cancelled = false;

    // Dynamic import keeps mapbox-gl out of SSR bundles
    import("mapbox-gl").then((mod) => {
      if (cancelled || !containerRef.current) return;

      const mapboxgl = mod.default ?? mod;
      mapboxgl.accessToken = MAPBOX_TOKEN;

      const center = pickupLocation ?? DEFAULT_CENTER;

      const map = new mapboxgl.Map({
        container: containerRef.current,
        style: "mapbox://styles/mapbox/streets-v12",
        center: [center.lng, center.lat],
        zoom: DEFAULT_ZOOM,
      });

      map.addControl(new mapboxgl.NavigationControl(), "top-right");

      map.on("load", () => {
        if (!cancelled) setMapLoaded(true);
      });

      mapRef.current = map;

      // ---- Pickup marker (green) ----
      if (pickupLocation) {
        const pickupEl = createPickupMarkerElement();
        const marker = new mapboxgl.Marker({ element: pickupEl }).setLngLat([
          pickupLocation.lng,
          pickupLocation.lat,
        ]);
        marker.addTo(map);
        pickupMarkerRef.current = marker;
      }

      // ---- Contractor marker (blue) ----
      if (contractorLocation) {
        const contractorEl = createContractorMarkerElement();
        const marker = new mapboxgl.Marker({ element: contractorEl }).setLngLat([
          contractorLocation.lng,
          contractorLocation.lat,
        ]);
        marker.addTo(map);
        contractorMarkerRef.current = marker;
      }
    });

    return () => {
      cancelled = true;
      if (mapRef.current) {
        mapRef.current.remove();
        mapRef.current = null;
      }
      pickupMarkerRef.current = null;
      contractorMarkerRef.current = null;
      setMapLoaded(false);
    };
    // We only want to initialise once. Location updates are handled below.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // -----------------------------------------------------------------------
  // Sync pickup marker
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;

    import("mapbox-gl").then((mod) => {
      const mapboxgl = mod.default ?? mod;
      if (!mapRef.current) return;

      if (pickupLocation) {
        if (pickupMarkerRef.current) {
          pickupMarkerRef.current.setLngLat([
            pickupLocation.lng,
            pickupLocation.lat,
          ]);
        } else {
          const el = createPickupMarkerElement();
          const marker = new mapboxgl.Marker({ element: el }).setLngLat([
            pickupLocation.lng,
            pickupLocation.lat,
          ]);
          marker.addTo(mapRef.current);
          pickupMarkerRef.current = marker;
        }
      }
    });
  }, [pickupLocation, mapLoaded]);

  // -----------------------------------------------------------------------
  // Sync contractor marker (updates frequently via socket)
  // -----------------------------------------------------------------------
  useEffect(() => {
    if (!mapLoaded || !mapRef.current) return;

    import("mapbox-gl").then((mod) => {
      const mapboxgl = mod.default ?? mod;
      if (!mapRef.current) return;

      if (contractorLocation) {
        if (contractorMarkerRef.current) {
          contractorMarkerRef.current.setLngLat([
            contractorLocation.lng,
            contractorLocation.lat,
          ]);
        } else {
          const el = createContractorMarkerElement();
          const marker = new mapboxgl.Marker({ element: el }).setLngLat([
            contractorLocation.lng,
            contractorLocation.lat,
          ]);
          marker.addTo(mapRef.current);
          contractorMarkerRef.current = marker;
        }
      }
    });
  }, [contractorLocation, mapLoaded]);

  // -----------------------------------------------------------------------
  // Fallback when no Mapbox token
  // -----------------------------------------------------------------------
  if (!MAPBOX_TOKEN) {
    return (
      <div className="w-full h-full min-h-[300px] rounded-lg bg-muted border border-border flex flex-col items-center justify-center gap-3 p-6">
        <MapPin className="w-10 h-10 text-muted-foreground" />
        <p className="text-sm font-medium text-muted-foreground text-center">
          Map unavailable &mdash; configure Mapbox token
        </p>
        {(pickupLocation || contractorLocation) && (
          <div className="text-xs text-muted-foreground text-center space-y-1 mt-2">
            {pickupLocation && (
              <p>
                Pickup: {pickupLocation.lat.toFixed(4)},{" "}
                {pickupLocation.lng.toFixed(4)}
              </p>
            )}
            {contractorLocation && (
              <p>
                Contractor: {contractorLocation.lat.toFixed(4)},{" "}
                {contractorLocation.lng.toFixed(4)}
              </p>
            )}
          </div>
        )}
      </div>
    );
  }

  // -----------------------------------------------------------------------
  // Render
  // -----------------------------------------------------------------------
  return (
    <div className="relative w-full h-full min-h-[300px] rounded-lg overflow-hidden border border-border">
      <div ref={containerRef} className="w-full h-full" />
      {!mapLoaded && (
        <div className="absolute inset-0 flex items-center justify-center bg-muted">
          <div className="flex flex-col items-center gap-2">
            <div className="w-8 h-8 border-2 border-primary border-t-transparent rounded-full animate-spin" />
            <p className="text-xs text-muted-foreground">Loading map...</p>
          </div>
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Marker element factories
// ---------------------------------------------------------------------------

function createPickupMarkerElement(): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "junkos-marker-pickup";
  el.style.cssText = `
    width: 32px;
    height: 32px;
    border-radius: 50% 50% 50% 0;
    background: hsl(142 71% 45%);
    transform: rotate(-45deg);
    border: 3px solid white;
    box-shadow: 0 2px 8px rgba(0,0,0,0.3);
    cursor: pointer;
  `;
  // Inner dot
  const dot = document.createElement("div");
  dot.style.cssText = `
    width: 10px;
    height: 10px;
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

function createContractorMarkerElement(): HTMLDivElement {
  const el = document.createElement("div");
  el.className = "junkos-marker-contractor";
  el.style.cssText = `
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: hsl(217 91% 60%);
    border: 3px solid white;
    box-shadow: 0 0 0 3px hsla(217 91% 60% / 0.3), 0 2px 8px rgba(0,0,0,0.25);
    cursor: pointer;
  `;
  return el;
}
