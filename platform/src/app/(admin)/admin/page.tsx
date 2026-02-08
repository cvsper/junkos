"use client";

import { useEffect, useState } from "react";
import dynamic from "next/dynamic";
import {
  Briefcase,
  Truck,
  Users,
  DollarSign,
  Activity,
  Loader2,
  AlertCircle,
  RefreshCw,
} from "lucide-react";
import { Card, CardHeader, CardTitle, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { adminApi, type DashboardData } from "@/lib/api";

const AdminMapView = dynamic(
  () => import("@/components/admin/admin-map-view"),
  { ssr: false }
);

export default function AdminDashboardPage() {
  const [data, setData] = useState<DashboardData | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const fetchDashboard = async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.dashboard();
      setData(res.dashboard);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load dashboard");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchDashboard();
  }, []);

  // Skeleton card for loading state
  const SkeletonCard = () => (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex items-center justify-between">
          <div className="h-4 w-24 rounded bg-muted animate-pulse" />
          <div className="h-5 w-5 rounded bg-muted animate-pulse" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="h-8 w-20 rounded bg-muted animate-pulse mb-1" />
        <div className="h-3 w-32 rounded bg-muted animate-pulse" />
      </CardContent>
    </Card>
  );

  if (error) {
    return (
      <div>
        <div className="mb-8">
          <h1 className="font-display text-3xl font-bold tracking-tight">
            Dashboard
          </h1>
          <p className="text-muted-foreground mt-1">
            Overview of your junk removal operations.
          </p>
        </div>
        <Card>
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="h-10 w-10 text-destructive mb-3" />
            <p className="text-sm text-muted-foreground mb-4">{error}</p>
            <Button variant="outline" onClick={fetchDashboard}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      </div>
    );
  }

  const statCards = data
    ? [
        {
          title: "Total Jobs",
          value: data.total_jobs.toLocaleString(),
          secondary: `${data.completed_jobs} completed, ${data.pending_jobs} pending`,
          icon: Briefcase,
        },
        {
          title: "Active Jobs",
          value: data.active_jobs.toLocaleString(),
          secondary: `${data.pending_jobs} awaiting assignment`,
          icon: Activity,
        },
        {
          title: "Online Contractors",
          value: `${data.online_contractors}`,
          secondary: `${data.approved_contractors} approved of ${data.total_contractors} total`,
          icon: Truck,
        },
        {
          title: "Revenue (30d)",
          value: `$${data.revenue_30d.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })}`,
          secondary: `$${data.commission_30d.toLocaleString(undefined, {
            minimumFractionDigits: 2,
            maximumFractionDigits: 2,
          })} commission`,
          icon: DollarSign,
        },
      ]
    : [];

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display text-3xl font-bold tracking-tight">
          Dashboard
        </h1>
        <p className="text-muted-foreground mt-1">
          Overview of your junk removal operations.
        </p>
      </div>

      {/* Stat Cards */}
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4 mb-8">
        {loading
          ? Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)
          : statCards.map((card) => {
              const Icon = card.icon;
              return (
                <Card key={card.title}>
                  <CardHeader className="pb-2">
                    <div className="flex items-center justify-between">
                      <span className="text-sm font-medium text-muted-foreground">
                        {card.title}
                      </span>
                      <Icon className="h-5 w-5 text-muted-foreground" />
                    </div>
                  </CardHeader>
                  <CardContent>
                    <p className="text-2xl font-display font-bold">
                      {card.value}
                    </p>
                    <p className="text-xs text-muted-foreground mt-1">
                      {card.secondary}
                    </p>
                  </CardContent>
                </Card>
              );
            })}
      </div>

      {/* Live Map */}
      <div className="mb-8">
        <AdminMapView />
      </div>

      <Separator className="mb-8" />

      {/* Quick Stats Row */}
      {data && (
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-8">
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Total Users
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xl font-display font-bold">
                {data.total_users.toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Completed Jobs
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xl font-display font-bold">
                {data.completed_jobs.toLocaleString()}
              </p>
            </CardContent>
          </Card>
          <Card>
            <CardHeader className="pb-2">
              <CardTitle className="text-sm font-medium text-muted-foreground">
                Approved Contractors
              </CardTitle>
            </CardHeader>
            <CardContent>
              <p className="text-xl font-display font-bold">
                {data.approved_contractors} / {data.total_contractors}
              </p>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Recent Activity */}
      <Card>
        <CardHeader>
          <CardTitle className="font-display text-lg font-semibold">
            Recent Activity
          </CardTitle>
        </CardHeader>
        <CardContent>
          {loading ? (
            <div className="space-y-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <div key={i} className="flex items-center gap-3">
                  <div className="h-8 w-8 rounded-full bg-muted animate-pulse" />
                  <div className="flex-1">
                    <div className="h-4 w-48 rounded bg-muted animate-pulse mb-1" />
                    <div className="h-3 w-24 rounded bg-muted animate-pulse" />
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="space-y-4">
              <div className="flex items-center gap-3 py-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-muted">
                  <Activity className="h-4 w-4 text-muted-foreground" />
                </div>
                <div className="flex-1">
                  <p className="text-sm">
                    <span className="font-medium">System initialized</span>
                    {" -- "}Dashboard is live and tracking operations.
                  </p>
                  <p className="text-xs text-muted-foreground">Just now</p>
                </div>
              </div>
              {data && data.pending_jobs > 0 && (
                <div className="flex items-center gap-3 py-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-yellow-500/10">
                    <Briefcase className="h-4 w-4 text-yellow-600" />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm">
                      <span className="font-medium">
                        {data.pending_jobs} pending job
                        {data.pending_jobs !== 1 ? "s" : ""}
                      </span>
                      {" "}awaiting contractor assignment.
                    </p>
                    <p className="text-xs text-muted-foreground">Action required</p>
                  </div>
                </div>
              )}
              {data && data.total_contractors > data.approved_contractors && (
                <div className="flex items-center gap-3 py-2">
                  <div className="flex h-8 w-8 items-center justify-center rounded-full bg-blue-500/10">
                    <Users className="h-4 w-4 text-blue-600" />
                  </div>
                  <div className="flex-1">
                    <p className="text-sm">
                      <span className="font-medium">
                        {data.total_contractors - data.approved_contractors} contractor
                        {data.total_contractors - data.approved_contractors !== 1
                          ? "s"
                          : ""}
                      </span>
                      {" "}pending approval review.
                    </p>
                    <p className="text-xs text-muted-foreground">Action required</p>
                  </div>
                </div>
              )}
              {data &&
                data.pending_jobs === 0 &&
                data.total_contractors === data.approved_contractors && (
                  <p className="text-sm text-muted-foreground text-center py-4">
                    No items requiring attention right now.
                  </p>
                )}
            </div>
          )}
        </CardContent>
      </Card>
    </div>
  );
}
