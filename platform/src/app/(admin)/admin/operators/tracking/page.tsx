"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Loader2,
  RefreshCw,
  Truck,
  Star,
  CheckCircle2,
  Clock,
  Phone,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { adminApi, type AdminContractorRecord } from "@/lib/api";

export default function OperatorTrackingPage() {
  const [contractors, setContractors] = useState<AdminContractorRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchContractors = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.contractors({ status: "approved" });
      setContractors(res.contractors || []);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load operators");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchContractors();
  }, [fetchContractors]);

  if (loading && contractors.length === 0) {
    return (
      <div className="flex items-center justify-center py-24">
        <Loader2 className="h-8 w-8 animate-spin text-primary" />
      </div>
    );
  }

  return (
    <div className="space-y-6 p-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="font-display text-3xl font-bold tracking-tight text-foreground">
            Operator Tracking
          </h1>
          <p className="text-muted-foreground mt-1">
            Monitor active fleet and individual contractors.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchContractors} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Online Now</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">
              {contractors.filter(c => c.is_online).length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Total Fleet</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{contractors.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Avg Rating</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground flex items-center gap-1">
              4.8 <Star className="h-5 w-5 fill-amber-400 text-amber-400" />
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Jobs Today</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-primary">12</div>
          </CardContent>
        </Card>
      </div>

      <Card className="overflow-hidden border-border">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs uppercase bg-muted/50 text-muted-foreground border-b border-border font-semibold">
              <tr>
                <th className="px-6 py-4">Operator</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Vehicle</th>
                <th className="px-6 py-4">Jobs</th>
                <th className="px-6 py-4">Rating</th>
                <th className="px-6 py-4">Last Active</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {contractors.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                    No operators found.
                  </td>
                </tr>
              ) : (
                contractors.map((op) => (
                  <tr key={op.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-3">
                        <div className={`w-10 h-10 rounded-full flex items-center justify-center font-bold text-sm ${op.is_online ? 'bg-emerald-100 text-emerald-700' : 'bg-muted text-muted-foreground'}`}>
                          {(op.name || "?")[0]?.toUpperCase()}
                        </div>
                        <div className="flex flex-col">
                          <span className="font-bold text-foreground">{op.name}</span>
                          <span className="text-xs text-muted-foreground flex items-center gap-1">
                            <Phone className="h-3 w-3" /> {op.phone || "N/A"}
                          </span>
                        </div>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      {op.is_online ? (
                        <Badge className="bg-emerald-100 text-emerald-800 border-emerald-200">
                          <span className="h-1.5 w-1.5 rounded-full bg-emerald-500 mr-1.5 animate-pulse" />
                          ONLINE
                        </Badge>
                      ) : (
                        <Badge variant="secondary" className="text-muted-foreground">OFFLINE</Badge>
                      )}
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-foreground flex items-center gap-1">
                          <Truck className="h-3.5 w-3.5 text-muted-foreground" />
                          {op.truck_type || "No Info"}
                        </span>
                        {op.is_operator && (
                          <span className="text-[10px] uppercase font-bold text-amber-600 mt-0.5">
                            Fleet Operator
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1.5">
                        <CheckCircle2 className="h-4 w-4 text-muted-foreground" />
                        <span className="font-semibold text-foreground">{op.total_jobs || 0}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1">
                        <Star className="h-4 w-4 fill-amber-400 text-amber-400" />
                        <span className="font-medium text-foreground">{(op.rating || 0).toFixed(1)}</span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <Clock className="h-3.5 w-3.5" />
                        {op.created_at ? new Date(op.created_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "Recently"}
                      </div>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </Card>
    </div>
  );
}
