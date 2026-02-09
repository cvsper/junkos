"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  DollarSign,
  TrendingUp,
  Calendar,
  Users,
  ArrowRight,
} from "lucide-react";
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
        <div className="h-8 bg-muted rounded w-28 animate-pulse" />
        {/* Summary card skeletons */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-5 sm:p-6 animate-pulse">
              <div className="flex items-center gap-3 mb-3">
                <div className="w-10 h-10 rounded-lg bg-muted" />
                <div className="h-4 bg-muted rounded w-24" />
              </div>
              <div className="h-8 bg-muted rounded w-24" />
            </div>
          ))}
        </div>
        {/* Table skeleton */}
        <div className="rounded-xl border border-border bg-card">
          <div className="px-4 sm:px-6 py-4 border-b border-border">
            <div className="h-5 bg-muted rounded w-48 animate-pulse" />
          </div>
          {/* Desktop skeleton */}
          <div className="hidden md:block">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="px-4 py-3 border-b border-border animate-pulse">
                <div className="flex gap-8 items-center">
                  <div className="h-4 bg-muted rounded w-28" />
                  <div className="h-4 bg-muted rounded w-12" />
                  <div className="h-4 bg-muted rounded w-20" />
                </div>
              </div>
            ))}
          </div>
          {/* Mobile skeleton */}
          <div className="md:hidden divide-y divide-border">
            {[...Array(3)].map((_, i) => (
              <div key={i} className="px-4 py-4 animate-pulse space-y-2">
                <div className="h-4 bg-muted rounded w-32" />
                <div className="flex gap-4">
                  <div className="h-3 bg-muted rounded w-16" />
                  <div className="h-3 bg-muted rounded w-20" />
                </div>
              </div>
            ))}
          </div>
        </div>
      </div>
    );
  }

  const summaryCards = [
    {
      label: "Total Commission",
      value: `$${(earnings?.total ?? 0).toFixed(2)}`,
      color: "text-primary",
      bg: "bg-primary/10",
      icon: DollarSign,
    },
    {
      label: "Last 30 Days",
      value: `$${(earnings?.earnings_30d ?? 0).toFixed(2)}`,
      color: "text-green-600",
      bg: "bg-green-50",
      icon: TrendingUp,
    },
    {
      label: "Last 7 Days",
      value: `$${(earnings?.earnings_7d ?? 0).toFixed(2)}`,
      color: "text-blue-600",
      bg: "bg-blue-50",
      icon: Calendar,
    },
  ];

  return (
    <div className="space-y-6">
      <h1 className="text-2xl font-display font-bold">Earnings</h1>

      {/* Summary Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
        {summaryCards.map((card) => {
          const Icon = card.icon;
          return (
            <div key={card.label} className="rounded-xl border border-border bg-card p-5 sm:p-6">
              <div className="flex items-center gap-3 mb-3">
                <div className={`w-10 h-10 rounded-lg ${card.bg} flex items-center justify-center`}>
                  <Icon className={`w-5 h-5 ${card.color}`} />
                </div>
                <p className="text-sm text-muted-foreground">{card.label}</p>
              </div>
              <p className={`text-2xl font-bold ${card.color}`}>{card.value}</p>
            </div>
          );
        })}
      </div>

      {/* Per-Contractor Breakdown */}
      <div className="rounded-xl border border-border bg-card">
        <div className="px-4 sm:px-6 py-4 border-b border-border">
          <h2 className="font-semibold">Per-Contractor Breakdown</h2>
        </div>

        {!earnings?.per_contractor || earnings.per_contractor.length === 0 ? (
          /* Empty State */
          <div className="px-4 sm:px-6 py-12 flex flex-col items-center text-center">
            <div className="w-12 h-12 rounded-full bg-muted flex items-center justify-center mb-3">
              <Users className="w-6 h-6 text-muted-foreground/60" />
            </div>
            <h3 className="text-sm font-medium text-foreground mb-1">No earnings data yet</h3>
            <p className="text-sm text-muted-foreground max-w-xs mb-4">
              Once your fleet contractors complete jobs, your commission breakdown will appear here.
            </p>
            <Link
              href="/operator/fleet"
              className="inline-flex items-center gap-1 text-sm text-primary hover:underline"
            >
              View Fleet
              <ArrowRight className="w-3.5 h-3.5" />
            </Link>
          </div>
        ) : (
          <>
            {/* Table - Desktop */}
            <div className="overflow-x-auto hidden md:block">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Contractor</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Jobs</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Your Commission</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {earnings.per_contractor.map((c) => (
                    <tr key={c.contractor_id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3 font-medium">{c.name || "Unnamed"}</td>
                      <td className="px-4 py-3">{c.jobs}</td>
                      <td className="px-4 py-3 text-primary font-medium">
                        ${c.commission.toFixed(2)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Cards - Mobile */}
            <div className="md:hidden divide-y divide-border">
              {earnings.per_contractor.map((c) => (
                <div key={c.contractor_id} className="px-4 py-4 flex items-center justify-between">
                  <div>
                    <p className="text-sm font-medium">{c.name || "Unnamed"}</p>
                    <p className="text-xs text-muted-foreground mt-0.5">
                      {c.jobs} job{c.jobs !== 1 ? "s" : ""} completed
                    </p>
                  </div>
                  <p className="text-sm font-semibold text-primary">${c.commission.toFixed(2)}</p>
                </div>
              ))}
            </div>
          </>
        )}
      </div>
    </div>
  );
}
