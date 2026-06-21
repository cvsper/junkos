"use client";

import { ReactNode, useEffect, useState } from "react";
import { portalFetch } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";
import {
  AppShell,
  Card,
  Button,
  Badge,
  statusTone,
  PortalLoading,
  usePortalGuard,
} from "@/components/ui";

interface Subscription {
  tier: string;
  status: string;
  auto_pay: boolean;
  net_terms_days: number;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
}

export default function SettingsPage() {
  const { ready } = usePortalGuard();
  const { org } = useAuthStore();
  const [sub, setSub] = useState<Subscription | null>(null);
  const [busy, setBusy] = useState(false);

  async function startCheckout(tier: string) {
    setBusy(true);
    try {
      const r = await portalFetch<{ url: string }>("/billing/checkout", {
        method: "POST",
        body: JSON.stringify({ tier }),
      });
      if (r.url) window.location.href = r.url;
      else setBusy(false);
    } catch {
      setBusy(false);
    }
  }

  async function manageBilling() {
    setBusy(true);
    try {
      const r = await portalFetch<{ url: string }>("/billing/portal-session", {
        method: "POST",
      });
      if (r.url) window.location.href = r.url;
      else setBusy(false);
    } catch {
      setBusy(false);
    }
  }

  useEffect(() => {
    if (!ready) return;
    portalFetch<Subscription>("/billing/subscription").then(setSub);
  }, [ready]);

  if (!ready) return <PortalLoading />;

  return (
    <AppShell
      title="Settings"
      subtitle="Your organization and billing."
      maxWidth="max-w-3xl"
    >
      <div className="space-y-6">
        <Section title="Organization">
          <Row label="Name" value={org?.name || "—"} />
          <Row label="Slug" value={org?.slug || "—"} />
          <Row label="Billing email" value={org?.billing_email || "—"} />
          <Row
            label="Status"
            value={org?.status ? <Badge tone={statusTone(org.status)}>{org.status}</Badge> : "—"}
          />
        </Section>

        <Section title="Subscription">
          <Row label="Plan" value={<span className="capitalize">{sub?.tier || "—"}</span>} />
          <Row
            label="Status"
            value={sub?.status ? <Badge tone={statusTone(sub.status)}>{sub.status}</Badge> : "—"}
          />
          <Row
            label="Payment"
            value={
              sub?.auto_pay
                ? "Auto-debit"
                : sub?.net_terms_days
                ? `Net-${sub.net_terms_days}`
                : "—"
            }
          />
          <Row
            label="Stripe customer"
            value={
              sub?.stripe_customer_id || (
                <span className="text-gray-400">Not provisioned</span>
              )
            }
          />
        </Section>

        <Section title="Billing">
          {sub?.stripe_customer_id ? (
            <Button variant="dark" onClick={manageBilling} disabled={busy}>
              {busy ? "Opening…" : "Manage billing"}
            </Button>
          ) : (
            <div>
              <p className="mb-3 text-sm text-gray-500">
                Choose a plan to start recurring service and consolidated monthly
                billing.
              </p>
              <div className="flex flex-wrap gap-2">
                {["starter", "pro", "enterprise"].map((t) => (
                  <Button
                    key={t}
                    variant="secondary"
                    className="capitalize"
                    onClick={() => startCheckout(t)}
                    disabled={busy}
                  >
                    Subscribe — {t}
                  </Button>
                ))}
              </div>
            </div>
          )}
        </Section>
      </div>
    </AppShell>
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card className="p-6">
      <h2 className="mb-4 text-xs font-semibold uppercase tracking-wider text-gray-400">
        {title}
      </h2>
      {children}
    </Card>
  );
}

function Row({ label, value }: { label: string; value: ReactNode }) {
  return (
    <div className="flex items-center justify-between border-b border-gray-100 py-2.5 text-sm last:border-0">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-900">{value}</span>
    </div>
  );
}
