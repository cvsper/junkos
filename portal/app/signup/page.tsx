"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { portalFetchPublic } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";
import { AuthShell, Field } from "@/components/auth-shell";

export default function SignupPage() {
  const router = useRouter();
  const { onAuthenticated } = useAuthStore();
  const [business, setBusiness] = useState("");
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const res = await portalFetchPublic<{
        token: string;
        org_id: string;
        role: string;
      }>("/auth/register", {
        method: "POST",
        body: JSON.stringify({
          business_name: business,
          contact_name: name,
          email,
          password,
        }),
      });
      onAuthenticated(res.token, res.org_id, res.role as any);
      router.replace("/");
    } catch (e: any) {
      setErr(e?.payload?.error || "Something went wrong. Please try again.");
      setBusy(false);
    }
  }

  return (
    <AuthShell
      heading="Create your business account"
      sub="Set up recurring pickups and one monthly invoice. Takes about a minute."
    >
      <form onSubmit={submit} className="space-y-4">
        <Field
          label="Business name"
          value={business}
          onChange={setBusiness}
          placeholder="Riverside Market"
          autoFocus
        />
        <Field
          label="Your name"
          value={name}
          onChange={setName}
          placeholder="Jordan Smith"
          autoComplete="name"
          required={false}
        />
        <Field
          label="Work email"
          type="email"
          value={email}
          onChange={setEmail}
          placeholder="you@yourstore.com"
          autoComplete="email"
        />
        <Field
          label="Password"
          type="password"
          value={password}
          onChange={setPassword}
          placeholder="At least 6 characters"
          autoComplete="new-password"
        />
        {err && <p className="text-sm text-brand-600">{err}</p>}
        <button
          type="submit"
          disabled={busy}
          className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
        >
          {busy ? "Creating account…" : "Create account"}
        </button>
        <p className="text-center text-xs leading-relaxed text-gray-400">
          No charge to sign up. You only pay when you book pickups.
        </p>
      </form>

      <p className="mt-6 text-sm text-gray-500">
        Already have an account?{" "}
        <Link
          href="/login"
          className="font-semibold text-brand-600 hover:text-brand-700"
        >
          Sign in
        </Link>
      </p>
    </AuthShell>
  );
}
