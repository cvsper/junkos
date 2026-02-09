"use client";

import { useEffect, useState } from "react";
import { operatorApi, type OperatorEarnings } from "@/lib/api";

export default function OperatorEarningsPage() {
  const [earnings, setEarnings] = useState<OperatorEarnings | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    operatorApi.earnings()
      .then((res) => setEarnings(res.earnings))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <h1 className="text-2xl font-display font-bold">Earnings</h1>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-6 animate-pulse">
              <div className="h-4 bg-muted rounded w-24 mb-2" />
              <div className="h-8 bg-muted rounded w-20" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-display font-bold">Earnings</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        <div className="rounded-xl border border-border bg-card p-6">
          <p className="text-sm text-muted-foreground">Total Commission</p>
          <p className="text-2xl font-bold text-primary mt-1">
            ${(earnings?.total ?? 0).toFixed(2)}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-6">
          <p className="text-sm text-muted-foreground">Last 30 Days</p>
          <p className="text-2xl font-bold mt-1">
            ${(earnings?.earnings_30d ?? 0).toFixed(2)}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-6">
          <p className="text-sm text-muted-foreground">Last 7 Days</p>
          <p className="text-2xl font-bold mt-1">
            ${(earnings?.earnings_7d ?? 0).toFixed(2)}
          </p>
        </div>
      </div>

      {/* Per-Contractor Breakdown */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Per-Contractor Breakdown</h2>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Contractor</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Jobs</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Your Commission</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {!earnings?.per_contractor || earnings.per_contractor.length === 0 ? (
                <tr>
                  <td colSpan={3} className="px-4 py-8 text-center text-muted-foreground">
                    No earnings data yet
                  </td>
                </tr>
              ) : (
                earnings.per_contractor.map((c) => (
                  <tr key={c.contractor_id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3 font-medium">{c.name || "Unnamed"}</td>
                    <td className="px-4 py-3">{c.jobs}</td>
                    <td className="px-4 py-3 text-primary font-medium">
                      ${c.commission.toFixed(2)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
