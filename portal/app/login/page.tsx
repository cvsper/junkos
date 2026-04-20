"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { portalFetchPublic } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";

/**
 * Login page. Two paths in MVP:
 *   1. Invite redemption  — user arrives via emailed /invite?token=...
 *   2. Token exchange     — advanced path for users who already have a
 *      residential JWT from the main app.
 *
 * Magic-link email + SSO land in 2-week v1 per spec §10.
 */
export default function LoginPage() {
  const router = useRouter();
  const { onAuthenticated } = useAuthStore();
  const [userToken, setUserToken] = useState("");
  const [orgId, setOrgId] = useState("");
  const [err, setErr] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function exchange(e: React.FormEvent) {
    e.preventDefault();
    setErr(null);
    setBusy(true);
    try {
      const res = await portalFetchPublic<{
        token: string;
        org_id: string;
        role: string;
      }>("/auth/token", {
        method: "POST",
        body: JSON.stringify({ user_token: userToken, org_id: orgId }),
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
          <div className="text-sm text-gray-500">Commercial Portal</div>
        </div>

        <p className="text-sm text-gray-600 mb-4">
          New here? Check your email for the invite link your sales rep sent.
        </p>

        <form onSubmit={exchange} className="space-y-3">
          <label className="block">
            <span className="text-xs text-gray-600">User JWT</span>
            <input
              type="text"
              value={userToken}
              onChange={(e) => setUserToken(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
              placeholder="eyJhbGciOi..."
            />
          </label>
          <label className="block">
            <span className="text-xs text-gray-600">Org ID</span>
            <input
              type="text"
              value={orgId}
              onChange={(e) => setOrgId(e.target.value)}
              className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
            />
          </label>
          {err && <div className="text-sm text-brand-600">{err}</div>}
          <button
            type="submit"
            disabled={busy}
            className="w-full rounded bg-brand-600 hover:bg-brand-700 text-white py-2 text-sm font-medium disabled:opacity-50"
          >
            {busy ? "Signing in…" : "Continue"}
          </button>
        </form>
      </div>
    </div>
  );
}
