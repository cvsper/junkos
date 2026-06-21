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

interface Invoice {
  id: string;
  number: string;
  period_start: string;
  period_end: string;
  total_cents: number;
  status: string;
  due_at: string | null;
}

export default function InvoicesPage() {
  const { ready } = usePortalGuard();
  const [rows, setRows] = useState<Invoice[]>([]);

  useEffect(() => {
    if (!ready) return;
    portalFetch<{ invoices: Invoice[] }>("/billing/invoices").then((r) =>
      setRows(r.invoices)
    );
  }, [ready]);

  if (!ready) return <PortalLoading />;

  return (
    <AppShell title="Invoices" subtitle="Your monthly statements, one per cycle.">
      <Table
        head={
          <tr>
            <Th>Number</Th>
            <Th>Period</Th>
            <Th>Status</Th>
            <Th className="text-right">Amount</Th>
            <Th>Due</Th>
          </tr>
        }
      >
        {rows.length === 0 ? (
          <EmptyRow colSpan={5}>
            No invoices yet. They appear here once your first billing cycle closes.
          </EmptyRow>
        ) : (
          rows.map((i) => (
            <Tr key={i.id}>
              <Td className="font-medium">{i.number}</Td>
              <Td className="text-gray-600">
                {new Date(i.period_start).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                })}{" "}
                –{" "}
                {new Date(i.period_end).toLocaleDateString(undefined, {
                  month: "short",
                  day: "numeric",
                })}
              </Td>
              <Td>
                <Badge tone={statusTone(i.status)}>
                  {i.status.replace(/_/g, " ")}
                </Badge>
              </Td>
              <Td className="text-right font-medium tabular-nums">
                ${(i.total_cents / 100).toFixed(2)}
              </Td>
              <Td className="text-gray-600">
                {i.due_at ? new Date(i.due_at).toLocaleDateString() : "—"}
              </Td>
            </Tr>
          ))
        )}
      </Table>
    </AppShell>
  );
}
