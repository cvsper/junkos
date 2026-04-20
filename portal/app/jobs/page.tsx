"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Nav } from "@/components/nav";
import { portalFetch } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";

interface Job {
  id: string;
  status: string;
  address: string;
  total_price: number;
  scheduled_at: string | null;
  created_at: string;
}

export default function JobsPage() {
  const router = useRouter();
  const { token, isLoading, hydrate } = useAuthStore();
  const [jobs, setJobs] = useState<Job[]>([]);
  const [err, setErr] = useState<string | null>(null);

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (isLoading) return;
    if (!token) {
      router.replace("/login");
      return;
    }
    portalFetch<{ jobs: Job[]; total: number }>("/jobs")
      .then((r) => setJobs(r.jobs))
      .catch((e) => setErr(String(e)));
  }, [isLoading, token, router]);

  if (isLoading || !token) return <div className="p-8 text-gray-500">Loading…</div>;

  return (
    <div className="flex min-h-screen">
      <Nav />
      <main className="flex-1 p-8">
        <h1 className="text-2xl font-semibold mb-6">Jobs</h1>
        {err && <div className="text-brand-600 mb-4">{err}</div>}
        <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <Th>Status</Th>
                <Th>Address</Th>
                <Th>Scheduled</Th>
                <Th className="text-right">Total</Th>
              </tr>
            </thead>
            <tbody>
              {jobs.length === 0 && (
                <tr>
                  <td colSpan={4} className="p-6 text-center text-gray-500">
                    No jobs yet.
                  </td>
                </tr>
              )}
              {jobs.map((j) => (
                <tr key={j.id} className="border-t border-gray-100">
                  <Td>
                    <span className="inline-block text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-700 capitalize">
                      {j.status}
                    </span>
                  </Td>
                  <Td className="truncate max-w-sm">{j.address}</Td>
                  <Td>
                    {j.scheduled_at
                      ? new Date(j.scheduled_at).toLocaleString()
                      : "—"}
                  </Td>
                  <Td className="text-right">
                    ${j.total_price?.toFixed(2) ?? "0.00"}
                  </Td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}

function Th({ children, className = "" }: any) {
  return (
    <th
      className={`px-4 py-3 text-xs font-medium uppercase tracking-wide text-gray-500 ${className}`}
    >
      {children}
    </th>
  );
}
function Td({ children, className = "" }: any) {
  return <td className={`px-4 py-3 text-gray-900 ${className}`}>{children}</td>;
}
