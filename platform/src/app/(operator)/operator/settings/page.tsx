"use client";

import { useEffect, useState } from "react";
import {
  User,
  Mail,
  Phone,
  Shield,
  Percent,
  Info,
} from "lucide-react";
import { useAuthStore } from "@/stores/auth-store";

export default function OperatorSettingsPage() {
  const { user } = useAuthStore();
  const [hydrated, setHydrated] = useState(false);

  useEffect(() => {
    setHydrated(true);
  }, []);

  if (!hydrated) {
    return (
      <div className="space-y-6">
        <div className="h-8 bg-muted rounded w-24 animate-pulse" />
        {/* Profile card skeleton */}
        <div className="rounded-xl border border-border bg-card">
          <div className="px-4 sm:px-6 py-4 border-b border-border">
            <div className="h-5 bg-muted rounded w-36 animate-pulse" />
          </div>
          <div className="px-4 sm:px-6 py-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
              {[...Array(4)].map((_, i) => (
                <div key={i} className="animate-pulse space-y-2">
                  <div className="h-3 bg-muted rounded w-16" />
                  <div className="h-5 bg-muted rounded w-40" />
                </div>
              ))}
            </div>
          </div>
        </div>
        {/* Commission card skeleton */}
        <div className="rounded-xl border border-border bg-card">
          <div className="px-4 sm:px-6 py-4 border-b border-border">
            <div className="h-5 bg-muted rounded w-32 animate-pulse" />
          </div>
          <div className="px-4 sm:px-6 py-4 animate-pulse space-y-3">
            <div className="h-4 bg-muted rounded w-3/4" />
            <div className="h-20 bg-muted rounded" />
          </div>
        </div>
      </div>
    );
  }

  const profileFields = [
    {
      label: "Name",
      value: user?.name || "N/A",
      icon: User,
    },
    {
      label: "Email",
      value: user?.email || "N/A",
      icon: Mail,
    },
    {
      label: "Phone",
      value: user?.phone || "N/A",
      icon: Phone,
    },
    {
      label: "Role",
      value: null, // special rendering
      icon: Shield,
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-display font-bold">Settings</h1>

      {/* Profile Information */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-4 sm:px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Profile Information</h2>
        </div>
        <div className="px-4 sm:px-6 py-4 sm:py-6">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-5 sm:gap-6">
            {profileFields.map((field) => {
              const Icon = field.icon;
              return (
                <div key={field.label} className="flex items-start gap-3">
                  <div className="w-9 h-9 rounded-lg bg-muted flex items-center justify-center flex-shrink-0 mt-0.5">
                    <Icon className="w-4 h-4 text-muted-foreground" />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-muted-foreground uppercase tracking-wider">
                      {field.label}
                    </label>
                    {field.value !== null ? (
                      <p className="text-sm mt-0.5">{field.value}</p>
                    ) : (
                      <span className="inline-block mt-0.5 px-2 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
                        Operator
                      </span>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {/* Commission Rate */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-4 sm:px-6 py-4 border-b border-border flex items-center gap-2">
          <Percent className="w-4 h-4 text-muted-foreground" />
          <h2 className="font-semibold">Commission Rate</h2>
        </div>
        <div className="px-4 sm:px-6 py-4 sm:py-6">
          <p className="text-sm text-muted-foreground">
            Your commission rate is set by the platform admin. You earn a percentage of the driver payout
            for each job completed by your fleet.
          </p>
          <div className="mt-4 bg-muted/50 rounded-lg p-4">
            <div className="flex items-center gap-2 mb-2">
              <div className="w-8 h-8 rounded-lg bg-primary/10 flex items-center justify-center">
                <Percent className="w-4 h-4 text-primary" />
              </div>
              <p className="text-lg font-bold text-primary">15%</p>
            </div>
            <p className="text-xs text-muted-foreground">Current Commission Rate</p>
          </div>
          <div className="mt-4 flex items-start gap-2 p-3 rounded-lg bg-blue-50 border border-blue-100">
            <Info className="w-4 h-4 text-blue-500 flex-shrink-0 mt-0.5" />
            <p className="text-xs text-blue-700">
              <span className="font-medium">Example breakdown:</span> On a $100 job, the platform takes $20 (20%),
              your commission is $12 (15% of $80), and the contractor receives $68.
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
