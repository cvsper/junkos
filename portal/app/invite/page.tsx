"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { portalFetchPublic } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";
import { AuthShell, Field } from "@/components/auth-shell";

function InviteForm() {
  const router = useRouter();
  const search = useSearchParams();
  const token = search.get("token") || "";
  const { onAuthenticated } = useAuthStore();
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) setErr("This invite link is missing its token.");
  }, [token]);

  async function submit(e: React.FormEvent) {
    e.preventDefault();
    setBusy(true);
    setErr(null);
    try {
      const res = await portalFetchPublic<{
        token: string;
        org_id: string;
        role: string;
      }>("/orgs/invite/accept", {
        method: "POST",
        body: JSON.stringify({
          invite_token: token,
          password: password || undefined,
        }),
      });
      onAuthenticated(
        res.token,
        res.org_id,
        res.role as "owner" | "admin" | "operator" | "viewer"
      );
      router.replace("/");
    } catch (e: any) {
      setErr(e?.payload?.error || String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <AuthShell
      heading="Accept your invite"
      sub="Set a password to join your team on Umuve."
    >
      <form onSubmit={submit} className="space-y-4">
        <Field
          label="Choose a password"
          type="password"
          value={password}
          onChange={setPassword}
          placeholder="At least 6 characters"
          autoComplete="new-password"
          autoFocus
        />
        {err && <p className="text-sm text-brand-600">{err}</p>}
        <button
          type="submit"
          disabled={busy || !token}
          className="w-full rounded-lg bg-brand-600 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-brand-700 disabled:opacity-50"
        >
          {busy ? "Joining…" : "Accept & continue"}
        </button>
      </form>
    </AuthShell>
  );
}

export default function InvitePage() {
  return (
    <Suspense
      fallback={<div className="p-8 text-sm text-gray-400">Loading…</div>}
    >
      <InviteForm />
    </Suspense>
  );
}
