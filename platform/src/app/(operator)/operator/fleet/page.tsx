"use client";

import { useEffect, useState } from "react";
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

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-display font-bold">Fleet</h1>
        <span className="text-sm text-muted-foreground">
          {contractors.length} contractor{contractors.length !== 1 ? "s" : ""}
        </span>
      </div>

      <div className="rounded-xl border border-border bg-card overflow-hidden">
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
              {loading ? (
                [...Array(3)].map((_, i) => (
                  <tr key={i}>
                    {[...Array(7)].map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 bg-muted rounded animate-pulse w-20" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : contractors.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-8 text-center text-muted-foreground">
                    No contractors in your fleet yet. Share an invite code to get started.
                  </td>
                </tr>
              ) : (
                contractors.map((c) => (
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
                    <td className="px-4 py-3">{c.avg_rating.toFixed(1)}</td>
                    <td className="px-4 py-3">{c.total_jobs}</td>
                    <td className="px-4 py-3">
                      <span className={`w-2.5 h-2.5 rounded-full inline-block ${c.is_online ? "bg-green-500" : "bg-gray-300"}`} />
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
