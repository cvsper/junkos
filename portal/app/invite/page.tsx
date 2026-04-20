"use client";

import { Suspense, useEffect, useState } from "react";
import { useRouter, useSearchParams } from "next/navigation";
import { portalFetchPublic } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";

function InviteForm() {
  const router = useRouter();
  const search = useSearchParams();
  const token = search.get("token") || "";
  const { onAuthenticated } = useAuthStore();
  const [password, setPassword] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    if (!token) setErr("Missing invite token.");
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
    <div className="min-h-screen flex items-center justify-center bg-gray-50 px-4">
      <div className="w-full max-w-md bg-white rounded-lg border border-gray-200 p-8">
        <div className="mb-6">
          <div className="text-brand-600 text-2xl font-bold">Umuve</div>
          <div className="text-sm text-gray-500">Accept your invite</div>
        </div>
        <form onSubmit={submit} className="space-y-3">
          <label className="block">
            <span className="text-xs text-gray-600">
              Set a password (optional — SSO coming soon)
            </span>
            <input
              type="password"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
              autoComplete="new-password"
            />
          </label>
          {err && <div className="text-sm text-brand-600">{err}</div>}
          <button
            type="submit"
            disabled={busy || !token}
            className="w-full rounded bg-brand-600 hover:bg-brand-700 text-white py-2 text-sm font-medium disabled:opacity-50"
          >
            {busy ? "Working…" : "Accept & Continue"}
          </button>
        </form>
      </div>
    </div>
  );
}

export default function InvitePage() {
  return (
    <Suspense fallback={<div className="p-8 text-gray-500">Loading…</div>}>
      <InviteForm />
    </Suspense>
  );
}
