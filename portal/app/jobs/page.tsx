"use client";

import { useEffect, useState } from "react";
import { portalFetch } from "@/lib/api";
import {
  AppShell,
  Badge,
  statusTone,
  Table,
  Th,
  Td,
  Tr,
  EmptyRow,
  PortalLoading,
  usePortalGuard,
} from "@/components/ui";

interface Job {
  id: string;
  status: string;
  address: string;
  total_price: number;
  scheduled_at: string | null;
  created_at: string;
}

export default function JobsPage() {
  const { ready } = usePortalGuard();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    if (!ready) return;
    portalFetch<{ jobs: Job[]; total: number }>("/jobs")
      .then((r) => setJobs(r.jobs))
      .catch((e) => setErr(String(e)));
  }, [ready]);

  if (!ready) return <PortalLoading />;

  return (
    <AppShell title="Jobs" subtitle="Every pickup across your properties.">
      {err && (
        <div className="mb-4 rounded-lg border border-red-100 bg-red-50 px-4 py-3 text-sm text-red-700">
          {err}
        </div>
      )}

      <Table
        head={
          <tr>
            <Th>Status</Th>
            <Th>Address</Th>
            <Th>Scheduled</Th>
            <Th className="text-right">Total</Th>
          </tr>
        }
      >
        {jobs.length === 0 ? (
          <EmptyRow colSpan={4}>No jobs yet.</EmptyRow>
        ) : (
          jobs.map((j) => (
            <Tr key={j.id}>
              <Td>
                <Badge tone={statusTone(j.status)}>
                  {j.status.replace(/_/g, " ")}
                </Badge>
              </Td>
              <Td className="max-w-sm truncate text-gray-700">{j.address}</Td>
              <Td className="text-gray-600">
                {j.scheduled_at
                  ? new Date(j.scheduled_at).toLocaleString(undefined, {
                      month: "short",
                      day: "numeric",
                      hour: "numeric",
                      minute: "2-digit",
                    })
                  : "—"}
              </Td>
              <Td className="text-right font-medium tabular-nums">
                ${j.total_price?.toFixed(2) ?? "0.00"}
              </Td>
            </Tr>
          ))
        )}
      </Table>
    </AppShell>
  );
}
