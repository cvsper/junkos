"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Nav } from "@/components/nav";
import { portalFetch } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";

interface Member {
  id: string;
  role: string;
  email: string;
  name: string | null;
  pending: boolean;
  joined_at: string | null;
}

export default function TeamPage() {
  const router = useRouter();
  const { token, isLoading, hydrate, role } = useAuthStore();
  const [members, setMembers] = useState<Member[]>([]);
  const [email, setEmail] = useState("");
  const [newRole, setNewRole] = useState<"admin" | "operator" | "viewer">(
    "viewer"
  );
  const [status, setStatus] = useState<string | null>(null);
  const canInvite = role === "owner" || role === "admin";

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  async function refresh() {
    const r = await portalFetch<{ members: Member[] }>("/orgs/me/members");
    setMembers(r.members);
  }

  useEffect(() => {
    if (isLoading) return;
    if (!token) return router.replace("/login");
    refresh();
  }, [isLoading, token, router]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setStatus(null);
    try {
      const r = await portalFetch<{ invite_url: string }>(
        "/orgs/me/members",
        {
          method: "POST",
          body: JSON.stringify({ email, role: newRole }),
        }
      );
      setStatus(`Invite sent: ${r.invite_url}`);
      setEmail("");
      await refresh();
    } catch (e: any) {
      setStatus(`Error: ${e?.payload?.error || String(e)}`);
    }
  }

  if (isLoading || !token) return <div className="p-8 text-gray-500">Loading…</div>;

  return (
    <div className="flex min-h-screen">
      <Nav />
      <main className="flex-1 p-8 max-w-4xl">
        <h1 className="text-2xl font-semibold mb-6">Team</h1>

        {canInvite && (
          <form
            onSubmit={invite}
            className="mb-6 rounded-lg border border-gray-200 bg-white p-4 flex gap-2 items-end"
          >
            <label className="flex-1">
              <span className="block text-xs text-gray-500">Email</span>
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="mt-1 w-full rounded border border-gray-300 px-3 py-2 text-sm"
              />
            </label>
            <label>
              <span className="block text-xs text-gray-500">Role</span>
              <select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value as any)}
                className="mt-1 rounded border border-gray-300 px-2 py-2 text-sm"
              >
                <option value="viewer">Viewer</option>
                <option value="operator">Operator</option>
                <option value="admin">Admin</option>
              </select>
            </label>
            <button
              type="submit"
              className="rounded bg-brand-600 text-white text-sm px-4 py-2 hover:bg-brand-700"
            >
              Invite
            </button>
          </form>
        )}

        {status && (
          <div className="mb-4 text-sm text-gray-700 break-all">{status}</div>
        )}

        <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="px-4 py-3 text-xs uppercase text-gray-500">
                  Member
                </th>
                <th className="px-4 py-3 text-xs uppercase text-gray-500">
                  Role
                </th>
                <th className="px-4 py-3 text-xs uppercase text-gray-500">
                  Status
                </th>
              </tr>
            </thead>
            <tbody>
              {members.map((m) => (
                <tr key={m.id} className="border-t border-gray-100">
                  <td className="px-4 py-3">
                    <div className="font-medium">{m.name || m.email}</div>
                    {m.name && (
                      <div className="text-xs text-gray-500">{m.email}</div>
                    )}
                  </td>
                  <td className="px-4 py-3 capitalize">{m.role}</td>
                  <td className="px-4 py-3 text-xs">
                    {m.pending ? (
                      <span className="text-yellow-700">Pending</span>
                    ) : (
                      <span className="text-green-700">Active</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
