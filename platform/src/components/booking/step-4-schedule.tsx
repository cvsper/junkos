"use client";

import { useState, useMemo } from "react";
import { CalendarDays, Clock } from "lucide-react";
import { Label } from "@/components/ui/label";
import { useBookingStore } from "@/stores/booking-store";
import { cn } from "@/lib/utils";

const TIME_SLOTS = [
  { id: "8-10", label: "8-10 AM" },
  { id: "10-12", label: "10 AM-12 PM" },
  { id: "12-14", label: "12-2 PM" },
  { id: "14-16", label: "2-4 PM" },
  { id: "16-18", label: "4-6 PM" },
];

function formatDisplayDate(dateStr: string): string {
  if (!dateStr) return "";
  const [year, month, day] = dateStr.split("-").map(Number);
  const date = new Date(year, month - 1, day);
  return date.toLocaleDateString("en-US", {
    weekday: "long",
    month: "long",
    day: "numeric",
    year: "numeric",
  });
}

export function Step4Schedule() {
  const { scheduledDate, scheduledTimeSlot, setSchedule } = useBookingStore();
  const [date, setDate] = useState(scheduledDate);
  const [timeSlot, setTimeSlot] = useState(scheduledTimeSlot);
  const [errors, setErrors] = useState<{ date?: string; time?: string }>({});

  // Calculate min date (tomorrow) and max date (90 days out)
  const { minDate, maxDate } = useMemo(() => {
    const tomorrow = new Date();
    tomorrow.setDate(tomorrow.getDate() + 1);

    const max = new Date();
    max.setDate(max.getDate() + 90);

    const toISO = (d: Date) => d.toISOString().split("T")[0];
    return { minDate: toISO(tomorrow), maxDate: toISO(max) };
  }, []);

  const handleDateChange = (value: string) => {
    setDate(value);
    if (errors.date) setErrors((prev) => ({ ...prev, date: undefined }));
    // Sync to store immediately
    setSchedule(value, timeSlot);
  };

  const handleTimeSelect = (slotId: string) => {
    setTimeSlot(slotId);
    if (errors.time) setErrors((prev) => ({ ...prev, time: undefined }));
    setSchedule(date, slotId);
  };

  const validate = (): boolean => {
    const newErrors: { date?: string; time?: string } = {};

    if (!date) {
      newErrors.date = "Please select a date.";
    } else {
      // Check date is at least 24 hours ahead
      const selected = new Date(date + "T00:00:00");
      const tomorrow = new Date();
      tomorrow.setDate(tomorrow.getDate() + 1);
      tomorrow.setHours(0, 0, 0, 0);

      if (selected < tomorrow) {
        newErrors.date = "Please select a date at least 24 hours from now.";
      }
    }

    if (!timeSlot) {
      newErrors.time = "Please select a time slot.";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  Step4Schedule.validate = validate;

  const selectedSlotLabel = TIME_SLOTS.find((s) => s.id === timeSlot)?.label;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="font-display text-2xl font-bold tracking-tight text-foreground">
          Pick a Date &amp; Time
        </h2>
        <p className="mt-1 text-muted-foreground">
          Choose when you would like us to come pick up your items.
        </p>
      </div>

      {/* Date Input */}
      <div className="space-y-3">
        <Label htmlFor="booking-date" className="text-sm font-medium flex items-center gap-2">
          <CalendarDays className="h-4 w-4 text-muted-foreground" />
          Select Date
        </Label>
        <input
          id="booking-date"
          type="date"
          min={minDate}
          max={maxDate}
          value={date}
          onChange={(e) => handleDateChange(e.target.value)}
          className="flex h-12 w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
        />
        {errors.date && (
          <p className="text-sm text-destructive font-medium">{errors.date}</p>
        )}
      </div>

      {/* Time Slot Selection */}
      <div className="space-y-3">
        <Label className="text-sm font-medium flex items-center gap-2">
          <Clock className="h-4 w-4 text-muted-foreground" />
          Select Time Slot
        </Label>
        <div className="grid grid-cols-2 sm:grid-cols-5 gap-3">
          {TIME_SLOTS.map((slot) => {
            const isSelected = timeSlot === slot.id;
            return (
              <button
                key={slot.id}
                type="button"
                onClick={() => handleTimeSelect(slot.id)}
                className={cn(
                  "rounded-lg border-2 py-3 px-4 text-sm font-medium transition-all text-center",
                  isSelected
                    ? "border-primary bg-primary/5 text-primary"
                    : "border-border bg-card text-muted-foreground hover:border-primary/30 hover:bg-muted/50"
                )}
              >
                {slot.label}
              </button>
            );
          })}
        </div>
        {errors.time && (
          <p className="text-sm text-destructive font-medium">{errors.time}</p>
        )}
      </div>

      {/* Summary */}
      {date && timeSlot && (
        <div className="rounded-lg border border-primary/20 bg-primary/5 p-4">
          <p className="text-sm font-semibold text-foreground">
            Selected Schedule
          </p>
          <p className="text-sm text-muted-foreground mt-1">
            {formatDisplayDate(date)} &middot; {selectedSlotLabel}
          </p>
        </div>
      )}
    </div>
  );
}

Step4Schedule.validate = (): boolean => {
  const { scheduledDate, scheduledTimeSlot } = useBookingStore.getState();
  if (!scheduledDate || !scheduledTimeSlot) return false;
  const selected = new Date(scheduledDate + "T00:00:00");
  const tomorrow = new Date();
  tomorrow.setDate(tomorrow.getDate() + 1);
  tomorrow.setHours(0, 0, 0, 0);
  return selected >= tomorrow;
};
