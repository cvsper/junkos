"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Nav } from "@/components/nav";
import { portalFetch } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";

interface Subscription {
  tier: string;
  status: string;
  auto_pay: boolean;
  net_terms_days: number;
  stripe_customer_id: string | null;
  stripe_subscription_id: string | null;
}

export default function SettingsPage() {
  const router = useRouter();
  const { token, isLoading, hydrate, org } = useAuthStore();
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
    hydrate();
  }, [hydrate]);

  useEffect(() => {
    if (isLoading) return;
    if (!token) return router.replace("/login");
    portalFetch<Subscription>("/billing/subscription").then(setSub);
  }, [isLoading, token, router]);

  if (isLoading || !token) return <div className="p-8 text-gray-500">Loading…</div>;

  return (
    <div className="flex min-h-screen">
      <Nav />
      <main className="flex-1 p-8 max-w-3xl">
        <h1 className="text-2xl font-semibold mb-6">Settings</h1>

        <section className="mb-8 rounded-lg border border-gray-200 bg-white p-5">
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">
            Organization
          </h2>
          <Row label="Name" value={org?.name || "—"} />
          <Row label="Slug" value={org?.slug || "—"} />
          <Row label="Billing email" value={org?.billing_email || "—"} />
          <Row label="Status" value={org?.status || "—"} />
        </section>

        <section className="rounded-lg border border-gray-200 bg-white p-5">
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">
            Subscription
          </h2>
          <Row label="Tier" value={sub?.tier || "—"} />
          <Row label="Status" value={sub?.status || "—"} />
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
        </section>

        <section className="mt-6 rounded-lg border border-gray-200 bg-white p-5">
          <h2 className="text-sm font-medium text-gray-500 uppercase tracking-wide mb-3">
            Billing
          </h2>
          {sub?.stripe_customer_id ? (
            <button
              onClick={manageBilling}
              disabled={busy}
              className="rounded-md bg-gray-900 px-4 py-2 text-sm font-medium text-white hover:bg-gray-800 disabled:opacity-50"
            >
              {busy ? "Opening…" : "Manage billing"}
            </button>
          ) : (
            <div>
              <p className="text-sm text-gray-500 mb-3">
                Choose a plan to start recurring service.
              </p>
              <div className="flex flex-wrap gap-2">
                {["starter", "pro", "enterprise"].map((t) => (
                  <button
                    key={t}
                    onClick={() => startCheckout(t)}
                    disabled={busy}
                    className="rounded-md border border-gray-300 px-4 py-2 text-sm font-medium capitalize text-gray-900 hover:border-gray-900 disabled:opacity-50"
                  >
                    Subscribe — {t}
                  </button>
                ))}
              </div>
            </div>
          )}
        </section>
      </main>
    </div>
  );
}

function Row({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="flex justify-between items-center py-2 border-b border-gray-100 last:border-0 text-sm">
      <span className="text-gray-500">{label}</span>
      <span className="font-medium text-gray-900">{value}</span>
    </div>
  );
}
