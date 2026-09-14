"use client";

import { createContext, useCallback, useContext, useEffect, useRef, useState } from "react";
import { driverApi } from "@/lib/api";

const Presence = createContext({ isOnline: false, updating: false, toggle: async () => {} });
export const useDriverPresence = () => useContext(Presence);

/** Lives in the driver layout so navigation cannot stop an online driver's GPS. */
export function DriverPresenceProvider({ initialOnline, children }: { initialOnline: boolean; children: React.ReactNode }) {
  const [isOnline, setOnline] = useState(initialOnline);
  const [updating, setUpdating] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [connected, setConnected] = useState(true);
  const mounted = useRef(false);
  const toggling = useRef(false);
  const locating = useRef(false);
  const onlineNow = useRef(isOnline);
  onlineNow.current = isOnline;
  const revision = useRef(0);

  const refresh = useCallback(async () => {
    if (toggling.current || !navigator.onLine || document.hidden) return;
    const requestRevision = ++revision.current;
    try {
      const result = await driverApi.profile();
      if (mounted.current && requestRevision === revision.current && !toggling.current) { setOnline(result.profile.is_online); setError(null); }
    } catch {
      if (mounted.current && requestRevision === revision.current) setError("Your online status could not be checked. Retry when connected.");
    }
  }, []);

  const locate = useCallback(() => {
    if (!mounted.current || !isOnline || document.hidden || !navigator.onLine || locating.current) return;
    if (!navigator.geolocation) { setLocationError("This browser cannot share your location. Use a browser with location access to receive nearby jobs."); return; }
    locating.current = true;
    navigator.geolocation.getCurrentPosition(async ({ coords }) => {
      try {
        // Permission prompts/GPS fixes can resolve after the tab is hidden
        // or the connection drops. Recheck immediately before sending.
        if (!mounted.current || !onlineNow.current || document.hidden || !navigator.onLine) return;
        await driverApi.updateLocation(coords.latitude, coords.longitude);
        if (mounted.current) setLocationError(null);
      } catch {
        if (mounted.current) setLocationError("Location update failed. Keep this page open and retry when connected.");
      } finally { locating.current = false; }
    }, () => {
      locating.current = false;
      if (mounted.current) setLocationError("Location is unavailable. Allow location access in your browser, then retry to receive nearby jobs.");
    }, { enableHighAccuracy: true, timeout: 15000, maximumAge: 15000 });
  }, [isOnline]);

  useEffect(() => {
    mounted.current = true;
    return () => { mounted.current = false; };
  }, []);

  useEffect(() => {
    const resume = () => { setConnected(navigator.onLine); void refresh(); locate(); };
    resume();
    const timer = setInterval(resume, 30000);
    window.addEventListener("online", resume);
    window.addEventListener("offline", resume);
    document.addEventListener("visibilitychange", resume);
    return () => {
      clearInterval(timer);
      window.removeEventListener("online", resume);
      window.removeEventListener("offline", resume);
      document.removeEventListener("visibilitychange", resume);
    };
  }, [refresh, locate]);

  async function toggle() {
    if (toggling.current) return;
    toggling.current = true; setUpdating(true); setError(null);
    revision.current += 1;
    const target = !isOnline;
    try {
      const response = await driverApi.setAvailability(target);
      if (mounted.current) setOnline(response.is_online);
    } catch {
      // A lost response can still mean the server changed the status.
      try {
        const response = await driverApi.profile();
        if (mounted.current) {
          setOnline(response.profile.is_online);
          if (response.profile.is_online !== target) setError("Your status was not changed. Retry the online switch.");
        }
      } catch {
        if (mounted.current) setError("Your status could not be confirmed. Retry the status check when connected.");
      }
    } finally { toggling.current = false; if (mounted.current) setUpdating(false); }
  }

  const message = !connected ? "You are offline. Saved pickup work stays in this browser; reconnect before retrying updates." : error || (isOnline ? locationError : null);
  return (
    <Presence.Provider value={{ isOnline, updating, toggle }}>
      {message ? (
        <div role="status" className="mb-4 rounded-xl border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900">
          {message}
          <button className="ml-2 underline font-semibold" onClick={() => { void refresh(); locate(); }}>Retry status and location</button>
        </div>
      ) : isOnline ? <p className="mb-3 text-xs text-muted-foreground">Keep this browser open while online so your location stays current.</p> : null}
      {children}
    </Presence.Provider>
  );
}
