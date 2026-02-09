"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import {
  Truck,
  Star,
  Mail,
  ArrowRight,
} from "lucide-react";
import { operatorApi, type OperatorFleetContractor } from "@/lib/api";

export default function OperatorFleetPage() {
  const [contractors, setContractors] = useState<OperatorFleetContractor[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    operatorApi.fleet()
      .then((res) => setContractors(res.contractors))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="h-8 bg-muted rounded w-20 animate-pulse" />
          <div className="h-4 bg-muted rounded w-28 animate-pulse" />
        </div>

        {/* Table skeleton - Desktop */}
        <div className="rounded-xl border border-border bg-card overflow-hidden hidden md:block">
          <div className="border-b border-border bg-muted/50 px-4 py-3">
            <div className="flex gap-8">
              {["w-20", "w-32", "w-20", "w-16", "w-12", "w-10", "w-8"].map((w, i) => (
                <div key={i} className={`h-4 bg-muted rounded ${w} animate-pulse`} />
              ))}
            </div>
          </div>
          {[...Array(3)].map((_, i) => (
            <div key={i} className="px-4 py-3 border-b border-border animate-pulse">
              <div className="flex gap-8 items-center">
                <div className="h-4 bg-muted rounded w-24" />
                <div className="h-4 bg-muted rounded w-36" />
                <div className="h-4 bg-muted rounded w-20" />
                <div className="h-6 bg-muted rounded-full w-18" />
                <div className="h-4 bg-muted rounded w-10" />
                <div className="h-4 bg-muted rounded w-8" />
                <div className="h-3 w-3 bg-muted rounded-full" />
              </div>
            </div>
          ))}
        </div>

        {/* Card skeleton - Mobile */}
        <div className="md:hidden space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse space-y-3">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-3">
                  <div className="w-10 h-10 rounded-full bg-muted" />
                  <div className="space-y-1.5">
                    <div className="h-4 bg-muted rounded w-28" />
                    <div className="h-3 bg-muted rounded w-36" />
                  </div>
                </div>
                <div className="h-3 w-3 bg-muted rounded-full" />
              </div>
              <div className="flex gap-4">
                <div className="h-3 bg-muted rounded w-16" />
                <div className="h-3 bg-muted rounded w-16" />
                <div className="h-3 bg-muted rounded w-16" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-display font-bold">Fleet</h1>
        <span className="text-sm text-muted-foreground">
          {contractors.length} contractor{contractors.length !== 1 ? "s" : ""}
        </span>
      </div>

      {contractors.length === 0 ? (
        /* Empty State */
        <div className="rounded-xl border border-border bg-card px-4 py-16 flex flex-col items-center text-center">
          <div className="w-14 h-14 rounded-full bg-blue-50 flex items-center justify-center mb-4">
            <Truck className="w-7 h-7 text-blue-500" />
          </div>
          <h3 className="font-semibold text-foreground mb-1">No contractors in your fleet yet</h3>
          <p className="text-sm text-muted-foreground max-w-sm mb-4">
            Share an invite code to get started. Once contractors sign up with your code, they will appear here.
          </p>
          <Link
            href="/operator/invites"
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Mail className="w-4 h-4" />
            Create Invite Code
            <ArrowRight className="w-3.5 h-3.5" />
          </Link>
        </div>
      ) : (
        <>
          {/* Table - Desktop */}
          <div className="rounded-xl border border-border bg-card overflow-hidden hidden md:block">
            <div className="overflow-x-auto">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/50">
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Name</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Email</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Truck Type</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Status</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Rating</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Jobs</th>
                    <th className="text-left px-4 py-3 font-medium text-muted-foreground">Online</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-border">
                  {contractors.map((c) => (
                    <tr key={c.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3 font-medium">{c.name || "Unnamed"}</td>
                      <td className="px-4 py-3 text-muted-foreground">{c.email || "-"}</td>
                      <td className="px-4 py-3">{c.truck_type || "-"}</td>
                      <td className="px-4 py-3">
                        <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${
                          c.approval_status === "approved"
                            ? "bg-green-100 text-green-700"
                            : c.approval_status === "pending"
                            ? "bg-amber-100 text-amber-700"
                            : "bg-red-100 text-red-700"
                        }`}>
                          {c.approval_status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <Star className="h-3.5 w-3.5 text-yellow-500 fill-yellow-500" />
                          <span>{c.avg_rating.toFixed(1)}</span>
                        </div>
                      </td>
                      <td className="px-4 py-3">{c.total_jobs}</td>
                      <td className="px-4 py-3">
                        <span className={`w-2.5 h-2.5 rounded-full inline-block ${c.is_online ? "bg-green-500" : "bg-gray-300"}`} />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Cards - Mobile */}
          <div className="md:hidden space-y-3">
            {contractors.map((c) => (
              <div key={c.id} className="rounded-xl border border-border bg-card p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <div className="flex items-center gap-3 min-w-0">
                    <div className="w-10 h-10 rounded-full bg-blue-50 flex items-center justify-center flex-shrink-0">
                      <span className="text-sm font-semibold text-blue-600">
                        {(c.name || "U")[0].toUpperCase()}
                      </span>
                    </div>
                    <div className="min-w-0">
                      <p className="text-sm font-medium truncate">{c.name || "Unnamed"}</p>
                      <p className="text-xs text-muted-foreground truncate">{c.email || "-"}</p>
                    </div>
                  </div>
                  <div className="flex items-center gap-2 flex-shrink-0">
                    <span className={`inline-block px-2 py-1 rounded-full text-xs font-medium ${
                      c.approval_status === "approved"
                        ? "bg-green-100 text-green-700"
                        : c.approval_status === "pending"
                        ? "bg-amber-100 text-amber-700"
                        : "bg-red-100 text-red-700"
                    }`}>
                      {c.approval_status}
                    </span>
                    <span className={`w-2.5 h-2.5 rounded-full ${c.is_online ? "bg-green-500" : "bg-gray-300"}`} />
                  </div>
                </div>
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>{c.truck_type || "No truck type"}</span>
                  <span className="flex items-center gap-1">
                    <Star className="h-3 w-3 text-yellow-500 fill-yellow-500" />
                    {c.avg_rating.toFixed(1)}
                  </span>
                  <span>{c.total_jobs} job{c.total_jobs !== 1 ? "s" : ""}</span>
                </div>
              </div>
            ))}
          </div>
        </>
      )}
    </div>
  );
}
