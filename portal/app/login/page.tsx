"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";
import { portalFetchPublic } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";
import { AuthShell, Field } from "@/components/auth-shell";

type OrgChoice = { org_id: string; name: string; role: string };
type LoginResp =
  | { token: string; org_id: string; role: string }
  | { needs_org: true; orgs: OrgChoice[] };

export default function LoginPage() {
  const router = useRouter();
  const { onAuthenticated } = useAuthStore();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [orgs, setOrgs] = useState<OrgChoice[] | null>(null);
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function submit(orgId?: string) {
    setErr(null);
    setBusy(true);
    try {
      const res = await portalFetchPublic<LoginResp>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ email, password, org_id: orgId }),
      });
      if ("needs_org" in res) {
        setOrgs(res.orgs);
        setBusy(false);
        return;
      }
      onAuthenticated(res.token, res.org_id, res.role as any);
      router.replace("/");
    } catch (e: any) {
      setErr(e?.payload?.error || "Something went wrong. Please try again.");
      setBusy(false);
    }
  }

  return (
    <AuthShell heading="Welcome back" sub="Sign in to your Umuve business account.">
      {orgs ? (
        <div className="space-y-2">
          <p className="mb-1 text-sm text-gray-600">Choose a business to continue:</p>
          {orgs.map((o) => (
            <button
              key={o.org_id}
              onClick={() => submit(o.org_id)}
              disabled={busy}
              className="w-full rounded-lg border border-gray-200 px-4 py-3 text-left transition-colors hover:border-brand-600 hover:bg-brand-50 disabled:opacity-50"
            >
              <div className="font-medium text-gray-900">{o.name}</div>
              <div className="text-xs capitalize text-gray-500">{o.role}</div>
            </button>
          ))}
          {err && <p className="text-sm text-brand-600">{err}</p>}
        </div>
      ) : (
        <form
          onSubmit={(e) => {
            e.preventDefault();
            submit();
          }}
          className="space-y-4"
        >
          <Field
            label="Work email"
            type="email"
            value={email}
            onChange={setEmail}
            placeholder="you@yourstore.com"
            autoComplete="email"
            autoFocus
          />
          <Field
            label="Password"
            type="password"
            value={password}
            onChange={setPassword}
            placeholder="••••••••"
            autoComplete="current-password"
          />
          {err && <p className="text-sm text-brand-600">{err}</p>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
          >
            {busy ? "Signing in…" : "Sign in"}
          </button>
        </form>
      )}

      {!orgs && (
        <p className="mt-6 text-sm text-gray-500">
          New to Umuve?{" "}
          <Link
            href="/signup"
            className="font-semibold text-brand-600 hover:text-brand-700"
          >
            Create a business account
          </Link>
        </p>
      )}
    </AuthShell>
  );
}
