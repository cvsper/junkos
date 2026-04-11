"use client";

import { useEffect, useState, useCallback } from "react";
import {
  Loader2,
  RefreshCw,
  CheckCircle,
  XCircle,
  Phone,
  Mail,
  MapPin,
  Calendar,
  Tag,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";

interface Partner {
  id: string;
  name: string;
  email: string;
  phone: string;
  brokerage: string;
  coverage_areas: string[];
  referral_code: string;
  status: "pending" | "approved" | "rejected";
  created_at: string;
}

export default function PartnersPage() {
  const [partners, setPartners] = useState<Partner[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [actionLoading, setActionLoading] = useState<string | null>(null);

  const fetchPartners = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/partners/list`);
      if (!res.ok) throw new Error("Failed to fetch partners");
      const data = await res.json();
      setPartners(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : "An error occurred");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPartners();
  }, [fetchPartners]);

  const handleUpdateStatus = async (id: string, newStatus: "approved" | "rejected" | "pending") => {
    setActionLoading(id);
    try {
      const res = await fetch(`${process.env.NEXT_PUBLIC_API_URL}/api/partners/${id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: newStatus }),
      });
      
      if (!res.ok) throw new Error(`Failed to update partner`);
      
      await fetchPartners();
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Action failed");
    } finally {
      setActionLoading(null);
    }
  };

  if (loading && partners.length === 0) {
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
            Partner Management
          </h1>
          <p className="text-muted-foreground mt-1">
            Manage realtors and brokerage partners.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={fetchPartners} disabled={loading}>
          <RefreshCw className={`h-4 w-4 mr-2 ${loading ? "animate-spin" : ""}`} />
          Refresh
        </Button>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Total Partners</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-foreground">{partners.length}</div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Pending Approval</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-amber-600">
              {partners.filter(p => p.status === "pending").length}
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader className="pb-2">
            <CardTitle className="text-sm font-medium text-muted-foreground uppercase tracking-wider">Active Referrals</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="text-2xl font-bold text-emerald-600">
              {partners.filter(p => p.status === "approved").length}
            </div>
          </CardContent>
        </Card>
      </div>

      <Card className="overflow-hidden border-border">
        <div className="overflow-x-auto">
          <table className="w-full text-sm text-left">
            <thead className="text-xs uppercase bg-muted/50 text-muted-foreground border-b border-border font-semibold">
              <tr>
                <th className="px-6 py-4">Partner</th>
                <th className="px-6 py-4">Brokerage</th>
                <th className="px-6 py-4">Referral Code</th>
                <th className="px-6 py-4">Status</th>
                <th className="px-6 py-4">Joined</th>
                <th className="px-6 py-4 text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {partners.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-6 py-12 text-center text-muted-foreground">
                    No partners found.
                  </td>
                </tr>
              ) : (
                partners.map((partner) => (
                  <tr key={partner.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="font-bold text-foreground">{partner.name}</span>
                        <span className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                          <Mail className="h-3 w-3" /> {partner.email}
                        </span>
                        <span className="text-xs text-muted-foreground flex items-center gap-1">
                          <Phone className="h-3 w-3" /> {partner.phone}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <div className="flex flex-col">
                        <span className="text-sm font-medium text-foreground">{partner.brokerage}</span>
                        <span className="text-xs text-muted-foreground flex items-center gap-1 mt-1">
                          <MapPin className="h-3 w-3" /> {partner.coverage_areas?.join(", ") || "N/A"}
                        </span>
                      </div>
                    </td>
                    <td className="px-6 py-4">
                      <Badge variant="outline" className="font-mono tracking-wider bg-muted text-[10px]">
                        <Tag className="h-3 w-3 mr-1" /> {partner.referral_code || "---"}
                      </Badge>
                    </td>
                    <td className="px-6 py-4">
                      <Badge 
                        className={
                          partner.status === "approved" ? "bg-emerald-100 text-emerald-800 border-emerald-200" :
                          partner.status === "rejected" ? "bg-red-100 text-red-800 border-red-200" :
                          "bg-amber-100 text-amber-800 border-amber-200"
                        }
                      >
                        {partner.status.toUpperCase()}
                      </Badge>
                    </td>
                    <td className="px-6 py-4">
                      <span className="text-xs flex items-center gap-1 text-muted-foreground">
                        <Calendar className="h-3 w-3" /> {new Date(partner.created_at).toLocaleDateString()}
                      </span>
                    </td>
                    <td className="px-6 py-4 text-right">
                      <div className="flex justify-end gap-2">
                        {partner.status === "pending" && (
                          <>
                            <Button 
                              size="sm" 
                              variant="outline"
                              className="h-8 px-2 text-emerald-600 hover:text-emerald-700 hover:bg-emerald-50 border-emerald-200"
                              onClick={() => handleUpdateStatus(partner.id, "approved")}
                              disabled={actionLoading === partner.id}
                            >
                              <CheckCircle className="h-4 w-4" />
                            </Button>
                            <Button 
                              size="sm" 
                              variant="outline"
                              className="h-8 px-2 text-red-600 hover:text-red-700 hover:bg-red-50 border-red-200"
                              onClick={() => handleUpdateStatus(partner.id, "rejected")}
                              disabled={actionLoading === partner.id}
                            >
                              <XCircle className="h-4 w-4" />
                            </Button>
                          </>
                        )}
                        {partner.status !== "pending" && (
                          <Button 
                            size="sm" 
                            variant="ghost" 
                            className="h-8 text-xs text-muted-foreground hover:text-foreground"
                            onClick={() => handleUpdateStatus(partner.id, "pending")}
                            disabled={actionLoading === partner.id}
                          >
                            Reset
                          </Button>
                        )}
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
