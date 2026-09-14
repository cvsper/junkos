"use client";

import { useEffect, useState } from "react";
import { CalendarDays, Clock, Loader2 } from "lucide-react";
import { Label } from "@/components/ui/label";
import { Button } from "@/components/ui/button";
import { bookingApi } from "@/lib/api";
import { serviceDate } from "@/lib/browser-work";
import { useBookingStore } from "@/stores/booking-store";
import { cn } from "@/lib/utils";

type Availability = Awaited<ReturnType<typeof bookingApi.availability>>;

export function Step4Schedule() {
  const { address, scheduledDate: date, scheduledTimeSlot: timeSlot, setSchedule } = useBookingStore();
  const [result, setResult] = useState<Availability | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attempt, setAttempt] = useState(0);
  const [validation, setValidation] = useState<string | null>(null);
  const key = `${date}:${address.lat}:${address.lng}`;
  const [checkedKey, setCheckedKey] = useState<string | null>(null);
  const ready = checkedKey === key && !loading && !error;

  useEffect(() => {
    const controller = new AbortController();
    setResult(null); setCheckedKey(null); setError(null);
    if (!date || address.lat == null || address.lng == null) {
      setLoading(false);
      if (date) setError("Choose a pickup address before checking available times.");
      return () => controller.abort();
    }
    setLoading(true);
    void bookingApi.availability(date, address, controller.signal).then((response) => {
      if (controller.signal.aborted) return;
      setResult(response); setCheckedKey(key);
      const selected = useBookingStore.getState().scheduledTimeSlot;
      if (!response.slots.some((slot) => slot.slot === selected && slot.available)) setSchedule(date, "");
    }).catch((reason: unknown) => {
      if (!controller.signal.aborted) {
        setSchedule(date, "");
        setError(reason instanceof Error ? reason.message : "Could not check pickup times.");
      }
    }).finally(() => { if (!controller.signal.aborted) setLoading(false); });
    return () => controller.abort();
    // Only changes that affect the request should invalidate the checked slots.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [key, attempt, setSchedule]);

  Step4Schedule.validate = () => {
    const valid = ready && Boolean(result?.slots.some((slot) => slot.slot === timeSlot && slot.available));
    setValidation(valid ? null : "Choose an available pickup time to continue.");
    return valid;
  };

  return (
    <div className="space-y-8">
      <div>
        <h2 className="font-display text-2xl font-bold tracking-tight">Pick a Date &amp; Time</h2>
        <p className="mt-1 text-muted-foreground">Choose an available window. Pickup times are shown in Eastern Time.</p>
      </div>
      <div className="space-y-3">
        <Label htmlFor="booking-date" className="flex items-center gap-2"><CalendarDays className="h-4 w-4" />Select Date</Label>
        <input id="booking-date" type="date" min={serviceDate()} max={serviceDate(14)} value={date}
          onChange={(event) => { setSchedule(event.target.value, ""); setValidation(null); }}
          className="h-12 w-full rounded-md border border-input bg-background px-3 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring" />
      </div>
      <fieldset className="space-y-3">
        <legend className="flex items-center gap-2 text-sm font-medium"><Clock className="h-4 w-4" />Select Time Slot</legend>
        {loading && <p role="status" className="flex items-center gap-2 text-sm text-muted-foreground"><Loader2 className="h-4 w-4 animate-spin" />Checking crew availability…</p>}
        {!date && <p className="text-sm text-muted-foreground">Select a date to see pickup windows.</p>}
        {error && <div role="alert" className="space-y-2 text-sm text-destructive"><p>{error}</p><Button variant="outline" onClick={() => setAttempt((value) => value + 1)}>Retry availability</Button></div>}
        {ready && !result?.any_available && <p role="status" className="text-sm text-muted-foreground">No crew is available for this date. Choose another day or contact support.</p>}
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-5">
          {(ready ? result?.slots ?? [] : []).map((slot) => (
            <button key={slot.slot} type="button" disabled={!slot.available} aria-pressed={slot.slot === timeSlot}
              onClick={() => { setSchedule(date, slot.slot); setValidation(null); }}
              className={cn("rounded-lg border-2 p-3 text-sm font-medium transition-colors disabled:cursor-not-allowed disabled:opacity-40", slot.slot === timeSlot ? "border-primary bg-primary/5 text-primary" : "border-border bg-card hover:border-primary/30")}>
              {slot.label}<span className="mt-1 block text-xs font-normal">{slot.available ? "Available" : "Unavailable"}</span>
            </button>
          ))}
        </div>
        {validation && <p role="alert" className="text-sm text-destructive">{validation}</p>}
      </fieldset>
    </div>
  );
}

Step4Schedule.validate = (): boolean => false;
