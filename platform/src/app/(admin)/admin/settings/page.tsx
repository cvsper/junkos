"use client";

import { useState, useEffect, useCallback } from "react";
import { adminApi } from "@/lib/api";
import type { OnboardingChecks } from "@/lib/api";
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
  CheckCircle2,
  Circle,
  Rocket,
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
  businessName: "Umuve",
  supportEmail: "support@goumuve.com",
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
// localStorage keys
// ---------------------------------------------------------------------------

const LS_KEY_GENERAL = "umuve_settings_general";
const LS_KEY_SCHEDULE = "umuve_settings_schedule";

function loadFromStorage<T>(key: string, fallback: T): T {
  if (typeof window === "undefined") return fallback;
  try {
    const raw = localStorage.getItem(key);
    if (!raw) return fallback;
    return JSON.parse(raw) as T;
  } catch {
    return fallback;
  }
}

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdminSettingsPage() {
  const [general, setGeneral] = useState<GeneralSettings>(DEFAULT_GENERAL);
  const [schedule, setSchedule] = useState<DaySchedule[]>(DEFAULT_SCHEDULE);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);

  // ---- Onboarding Checklist State ----
  const [onboarding, setOnboarding] = useState<OnboardingChecks | null>(null);
  const [onboardingLoading, setOnboardingLoading] = useState(true);

  // Load persisted settings on mount (client-only)
  useEffect(() => {
    setGeneral(loadFromStorage<GeneralSettings>(LS_KEY_GENERAL, DEFAULT_GENERAL));
    setSchedule(loadFromStorage<DaySchedule[]>(LS_KEY_SCHEDULE, DEFAULT_SCHEDULE));
  }, []);

  // Fetch onboarding status
  const fetchOnboarding = useCallback(async () => {
    setOnboardingLoading(true);
    try {
      const res = await adminApi.getOnboardingStatus();
      setOnboarding(
        (res as { success: boolean; checks: OnboardingChecks }).checks
      );
    } catch {
      // If the endpoint isn't available, show a sensible default.
      // Admin is viewing the page so admin_created is true.
      // Service area is always hardcoded to true.
      setOnboarding({
        stripe_configured: false,
        admin_created: true,
        pricing_configured: false,
        service_area_defined: true,
        contractor_registered: false,
      });
    } finally {
      setOnboardingLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchOnboarding();
  }, [fetchOnboarding]);

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

  const handleSave = useCallback(async () => {
    setSaving(true);
    try {
      localStorage.setItem(LS_KEY_GENERAL, JSON.stringify(general));
      localStorage.setItem(LS_KEY_SCHEDULE, JSON.stringify(schedule));
      // Small delay so the UI transition feels natural
      await new Promise((resolve) => setTimeout(resolve, 300));
      setSaved(true);
      setTimeout(() => setSaved(false), 4000);
    } catch {
      // localStorage might be full or blocked -- fail silently for now
    } finally {
      setSaving(false);
    }
  }, [general, schedule]);

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
              Settings saved successfully.
            </p>
          </div>
        </div>
      )}

      <div className="space-y-8 max-w-4xl">
        {/* ---------------------------------------------------------------- */}
        {/* Section 0: Onboarding Checklist                                   */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-lg">
              <Rocket className="h-5 w-5 text-primary" />
              Launch Readiness Checklist
            </CardTitle>
            <CardDescription>
              Complete these steps to go live with your junk removal service.
            </CardDescription>
          </CardHeader>
          <CardContent>
            {onboardingLoading ? (
              <div className="flex items-center justify-center py-8">
                <Loader2 className="h-5 w-5 animate-spin text-muted-foreground" />
                <span className="ml-2 text-sm text-muted-foreground">
                  Checking readiness...
                </span>
              </div>
            ) : onboarding ? (
              <>
                {/* Progress summary */}
                {(() => {
                  const checks = [
                    onboarding.stripe_configured,
                    onboarding.admin_created,
                    onboarding.pricing_configured,
                    onboarding.service_area_defined,
                    onboarding.contractor_registered,
                  ];
                  const completed = checks.filter(Boolean).length;
                  const total = checks.length;
                  const allDone = completed === total;

                  return (
                    <div className="mb-4">
                      <div className="flex items-center justify-between mb-2">
                        <p className="text-sm font-medium">
                          {allDone
                            ? "All checks passed -- you are ready to launch!"
                            : `${completed} of ${total} steps completed`}
                        </p>
                        <Badge
                          variant={allDone ? "default" : "secondary"}
                          className="text-xs"
                        >
                          {allDone ? "Ready" : "In Progress"}
                        </Badge>
                      </div>
                      <div className="w-full bg-muted rounded-full h-2">
                        <div
                          className="bg-primary h-2 rounded-full transition-all"
                          style={{
                            width: `${(completed / total) * 100}%`,
                          }}
                        />
                      </div>
                    </div>
                  );
                })()}

                {/* Checklist items */}
                <div className="space-y-3">
                  {[
                    {
                      label: "Stripe payment keys configured",
                      description:
                        "STRIPE_SECRET_KEY and STRIPE_PUBLISHABLE_KEY environment variables are set.",
                      done: onboarding.stripe_configured,
                    },
                    {
                      label: "Admin account created",
                      description:
                        "At least one admin user exists and can access the dashboard.",
                      done: onboarding.admin_created,
                    },
                    {
                      label: "Pricing configured",
                      description:
                        "Item category prices and fee settings have been saved.",
                      done: onboarding.pricing_configured,
                    },
                    {
                      label: "Service area defined",
                      description:
                        "Geographic service zones are configured for dispatch.",
                      done: onboarding.service_area_defined,
                    },
                    {
                      label: "At least 1 contractor registered",
                      description:
                        "An approved contractor is available to accept jobs.",
                      done: onboarding.contractor_registered,
                    },
                  ].map((item) => (
                    <div
                      key={item.label}
                      className="flex items-start gap-3 rounded-md border border-border p-3"
                    >
                      {item.done ? (
                        <CheckCircle2 className="h-5 w-5 text-green-600 dark:text-green-400 shrink-0 mt-0.5" />
                      ) : (
                        <Circle className="h-5 w-5 text-muted-foreground/40 shrink-0 mt-0.5" />
                      )}
                      <div>
                        <p
                          className={`text-sm font-medium ${
                            item.done ? "" : "text-muted-foreground"
                          }`}
                        >
                          {item.label}
                        </p>
                        <p className="text-xs text-muted-foreground mt-0.5">
                          {item.description}
                        </p>
                      </div>
                    </div>
                  ))}
                </div>
              </>
            ) : null}
          </CardContent>
        </Card>

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
            Settings are saved to your browser&apos;s local storage. They will
            persist across page refreshes but are specific to this browser.
          </p>
        </div>
      </div>
    </div>
  );
}
