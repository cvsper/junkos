"use client";

import { useState } from "react";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Separator } from "@/components/ui/separator";
import {
  MapPin,
  Clock,
  Bell,
  Save,
  Check,
  Loader2,
  Mail,
  Phone,
  Building2,
  Info,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface GeneralSettings {
  businessName: string;
  supportEmail: string;
  supportPhone: string;
}

interface DaySchedule {
  day: string;
  open: string;
  close: string;
  isOpen: boolean;
}

interface NotificationTemplate {
  id: string;
  name: string;
  description: string;
  preview: string;
}

// ---------------------------------------------------------------------------
// Default Data
// ---------------------------------------------------------------------------

const DEFAULT_GENERAL: GeneralSettings = {
  businessName: "JunkOS",
  supportEmail: "support@junkos.app",
  supportPhone: "(561) 555-0100",
};

const DEFAULT_SCHEDULE: DaySchedule[] = [
  { day: "Monday", open: "07:00", close: "19:00", isOpen: true },
  { day: "Tuesday", open: "07:00", close: "19:00", isOpen: true },
  { day: "Wednesday", open: "07:00", close: "19:00", isOpen: true },
  { day: "Thursday", open: "07:00", close: "19:00", isOpen: true },
  { day: "Friday", open: "07:00", close: "19:00", isOpen: true },
  { day: "Saturday", open: "08:00", close: "17:00", isOpen: true },
  { day: "Sunday", open: "09:00", close: "15:00", isOpen: false },
];

const NOTIFICATION_TEMPLATES: NotificationTemplate[] = [
  {
    id: "job_confirmed",
    name: "Job Confirmed",
    description: "Sent when a customer's booking is confirmed",
    preview:
      'Hi {customer_name}, your junk removal job #{job_id} has been confirmed for {scheduled_date}. A driver will arrive between {time_window}. Reply STOP to opt out.',
  },
  {
    id: "driver_en_route",
    name: "Driver En Route",
    description: "Sent when the assigned driver is on their way",
    preview:
      'Your driver {driver_name} is on the way! Estimated arrival: {eta}. Track your pickup in real time at {tracking_url}.',
  },
  {
    id: "job_complete",
    name: "Job Complete",
    description: "Sent after the job is finished",
    preview:
      'Your junk removal is complete! Total: {total_price}. We removed {item_count} items. Rate your experience: {rating_url}.',
  },
  {
    id: "receipt",
    name: "Receipt",
    description: "Payment receipt sent after successful charge",
    preview:
      'Payment of {total_price} received for Job #{job_id}. Charged to card ending in {card_last4}. View full receipt: {receipt_url}.',
  },
];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdminSettingsPage() {
  const [general, setGeneral] = useState<GeneralSettings>(DEFAULT_GENERAL);
  const [schedule, setSchedule] = useState<DaySchedule[]>(DEFAULT_SCHEDULE);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // ---- Handlers ----

  const handleGeneralChange = (field: keyof GeneralSettings, value: string) => {
    setGeneral((prev) => ({ ...prev, [field]: value }));
    setSaved(false);
  };

  const handleScheduleChange = (
    index: number,
    field: keyof DaySchedule,
    value: string | boolean
  ) => {
    setSchedule((prev) =>
      prev.map((s, i) => (i === index ? { ...s, [field]: value } : s))
    );
    setSaved(false);
  };

  const handleSave = async () => {
    setSaving(true);
    // Simulate save delay -- backend persistence coming later
    await new Promise((resolve) => setTimeout(resolve, 800));
    setSaving(false);
    setSaved(true);
    setTimeout(() => setSaved(false), 4000);
  };

  const formatTime = (time24: string): string => {
    const [h, m] = time24.split(":").map(Number);
    const ampm = h >= 12 ? "PM" : "AM";
    const h12 = h % 12 || 12;
    return `${h12}:${m.toString().padStart(2, "0")} ${ampm}`;
  };

  return (
    <div>
      {/* Header */}
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Settings
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage your platform configuration and preferences.
          </p>
        </div>
        <Button onClick={handleSave} disabled={saving}>
          {saving ? (
            <Loader2 className="h-4 w-4 mr-2 animate-spin" />
          ) : saved ? (
            <Check className="h-4 w-4 mr-2" />
          ) : (
            <Save className="h-4 w-4 mr-2" />
          )}
          {saved ? "Settings Saved" : "Save Settings"}
        </Button>
      </div>

      {/* Success toast banner */}
      {saved && (
        <div className="mb-6 rounded-lg border border-green-200 bg-green-50 p-4 dark:border-green-800 dark:bg-green-950">
          <div className="flex items-center gap-2">
            <Check className="h-4 w-4 text-green-600 dark:text-green-400" />
            <p className="text-sm font-medium text-green-800 dark:text-green-200">
              Settings saved successfully. Backend persistence will be available
              in a future update.
            </p>
          </div>
        </div>
      )}

      <div className="space-y-8 max-w-4xl">
        {/* ---------------------------------------------------------------- */}
        {/* Section 1: General Settings                                       */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-lg">
              <Building2 className="h-5 w-5 text-primary" />
              General Settings
            </CardTitle>
            <CardDescription>
              Basic information about your business
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div className="sm:col-span-2">
                  <Label htmlFor="business-name">Business Name</Label>
                  <Input
                    id="business-name"
                    value={general.businessName}
                    onChange={(e) =>
                      handleGeneralChange("businessName", e.target.value)
                    }
                    placeholder="Your business name"
                  />
                </div>
                <div>
                  <Label htmlFor="support-email">
                    <span className="flex items-center gap-1.5">
                      <Mail className="h-3.5 w-3.5" />
                      Support Email
                    </span>
                  </Label>
                  <Input
                    id="support-email"
                    type="email"
                    value={general.supportEmail}
                    onChange={(e) =>
                      handleGeneralChange("supportEmail", e.target.value)
                    }
                    placeholder="support@example.com"
                  />
                </div>
                <div>
                  <Label htmlFor="support-phone">
                    <span className="flex items-center gap-1.5">
                      <Phone className="h-3.5 w-3.5" />
                      Support Phone
                    </span>
                  </Label>
                  <Input
                    id="support-phone"
                    type="tel"
                    value={general.supportPhone}
                    onChange={(e) =>
                      handleGeneralChange("supportPhone", e.target.value)
                    }
                    placeholder="(555) 123-4567"
                  />
                </div>
              </div>
            </div>
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Section 2: Service Area                                           */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-lg">
              <MapPin className="h-5 w-5 text-primary" />
              Service Area
            </CardTitle>
            <CardDescription>
              Geographic zones where your service operates
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="rounded-md border border-border p-4 mb-4">
              <div className="flex items-start gap-3">
                <MapPin className="h-5 w-5 text-primary shrink-0 mt-0.5" />
                <div>
                  <p className="text-sm font-medium">
                    Palm Beach &amp; Broward County, South Florida
                  </p>
                  <p className="text-xs text-muted-foreground mt-0.5">
                    Active service area covering Palm Beach County and Broward
                    County
                  </p>
                </div>
              </div>
            </div>
            <div className="flex items-start gap-2 rounded-md bg-muted/50 border border-border p-3">
              <Info className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
              <p className="text-xs text-muted-foreground">
                A Mapbox-powered interactive zone editor is coming soon. You
                will be able to draw and manage custom service zones on a map.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Section 3: Operating Hours                                        */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-lg">
              <Clock className="h-5 w-5 text-primary" />
              Operating Hours
            </CardTitle>
            <CardDescription>
              Set the hours your business accepts pickups
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-3">
              {schedule.map((daySchedule, index) => (
                <div
                  key={daySchedule.day}
                  className="flex items-center gap-4 rounded-md border border-border p-3"
                >
                  {/* Day name + toggle */}
                  <div className="flex items-center gap-3 w-32 shrink-0">
                    <button
                      onClick={() =>
                        handleScheduleChange(
                          index,
                          "isOpen",
                          !daySchedule.isOpen
                        )
                      }
                      className={`relative inline-flex h-5 w-9 items-center rounded-full transition-colors shrink-0 ${
                        daySchedule.isOpen
                          ? "bg-primary"
                          : "bg-muted-foreground/30"
                      }`}
                    >
                      <span
                        className={`inline-block h-3.5 w-3.5 transform rounded-full bg-white transition-transform ${
                          daySchedule.isOpen
                            ? "translate-x-[18px]"
                            : "translate-x-[3px]"
                        }`}
                      />
                    </button>
                    <span
                      className={`text-sm font-medium ${
                        !daySchedule.isOpen ? "text-muted-foreground" : ""
                      }`}
                    >
                      {daySchedule.day}
                    </span>
                  </div>

                  {/* Time inputs */}
                  {daySchedule.isOpen ? (
                    <div className="flex items-center gap-2 flex-1">
                      <Input
                        type="time"
                        className="w-32 h-8 text-sm"
                        value={daySchedule.open}
                        onChange={(e) =>
                          handleScheduleChange(index, "open", e.target.value)
                        }
                      />
                      <span className="text-sm text-muted-foreground">to</span>
                      <Input
                        type="time"
                        className="w-32 h-8 text-sm"
                        value={daySchedule.close}
                        onChange={(e) =>
                          handleScheduleChange(index, "close", e.target.value)
                        }
                      />
                      <span className="text-xs text-muted-foreground ml-2 hidden sm:inline">
                        {formatTime(daySchedule.open)} &ndash;{" "}
                        {formatTime(daySchedule.close)}
                      </span>
                    </div>
                  ) : (
                    <div className="flex-1">
                      <Badge variant="secondary" className="text-xs">
                        Closed
                      </Badge>
                    </div>
                  )}
                </div>
              ))}
            </div>
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Section 4: Notification Templates                                 */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-lg">
              <Bell className="h-5 w-5 text-primary" />
              Notification Templates
            </CardTitle>
            <CardDescription>
              SMS and email templates for customer communications (read-only
              preview)
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="space-y-4">
              {NOTIFICATION_TEMPLATES.map((template) => (
                <div
                  key={template.id}
                  className="rounded-md border border-border p-4"
                >
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <p className="text-sm font-medium">{template.name}</p>
                      <p className="text-xs text-muted-foreground mt-0.5">
                        {template.description}
                      </p>
                    </div>
                    <Badge variant="outline" className="text-xs shrink-0">
                      Template
                    </Badge>
                  </div>
                  <Separator className="my-2" />
                  <div className="rounded bg-muted/50 p-3">
                    <p className="text-xs text-muted-foreground font-mono leading-relaxed whitespace-pre-wrap">
                      {template.preview}
                    </p>
                  </div>
                </div>
              ))}
            </div>

            <div className="flex items-start gap-2 rounded-md bg-muted/50 border border-border p-3 mt-4">
              <Info className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
              <p className="text-xs text-muted-foreground">
                Template editing will be available in a future update. Variables
                in curly braces are auto-populated at send time.
              </p>
            </div>
          </CardContent>
        </Card>

        {/* Bottom note */}
        <div className="flex items-start gap-2 rounded-md bg-muted/50 border border-border p-4">
          <Info className="h-4 w-4 text-muted-foreground shrink-0 mt-0.5" />
          <p className="text-sm text-muted-foreground">
            Settings are stored locally for now. Backend persistence will be
            connected in a future release. Changes will be lost on page refresh.
          </p>
        </div>
      </div>
    </div>
  );
}
