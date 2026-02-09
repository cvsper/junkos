"use client";

import { useAuthStore } from "@/stores/auth-store";

export default function OperatorSettingsPage() {
  const { user } = useAuthStore();

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-display font-bold">Settings</h1>

      <div className="rounded-xl border border-border bg-card">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Profile Information</h2>
        </div>
        <div className="px-6 py-4 space-y-4">
          <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-1">Name</label>
              <p className="text-sm">{user?.name || "N/A"}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-1">Email</label>
              <p className="text-sm">{user?.email || "N/A"}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-1">Phone</label>
              <p className="text-sm">{user?.phone || "N/A"}</p>
            </div>
            <div>
              <label className="block text-sm font-medium text-muted-foreground mb-1">Role</label>
              <span className="inline-block px-2 py-1 rounded-full text-xs font-medium bg-amber-100 text-amber-700">
                Operator
              </span>
            </div>
          </div>
        </div>
      </div>

      <div className="rounded-xl border border-border bg-card">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Commission Rate</h2>
        </div>
        <div className="px-6 py-4">
          <p className="text-sm text-muted-foreground">
            Your commission rate is set by the platform admin. You earn a percentage of the driver payout
            for each job completed by your fleet.
          </p>
          <div className="mt-3 bg-muted/50 rounded-lg p-4">
            <p className="text-sm font-medium">Current Rate: 15%</p>
            <p className="text-xs text-muted-foreground mt-1">
              Example: $100 job &rarr; Platform $20 (20%) &rarr; Your commission $12 (15% of $80) &rarr; Contractor $68
            </p>
          </div>
        </div>
      </div>
    </div>
  );
}
