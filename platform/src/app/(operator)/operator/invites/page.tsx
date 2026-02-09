"use client";

import { useEffect, useState } from "react";
import { operatorApi, type OperatorInvite } from "@/lib/api";

export default function OperatorInvitesPage() {
  const [invites, setInvites] = useState<OperatorInvite[]>([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);
  const [email, setEmail] = useState("");
  const [maxUses, setMaxUses] = useState(1);
  const [expiresDays, setExpiresDays] = useState(7);
  const [creating, setCreating] = useState(false);
  const [copiedId, setCopiedId] = useState<string | null>(null);

  const loadInvites = () => {
    operatorApi.listInvites()
      .then((res) => setInvites(res.invites))
      .catch(() => {})
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadInvites();
  }, []);

  const handleCreate = async (e: React.FormEvent) => {
    e.preventDefault();
    setCreating(true);
    try {
      await operatorApi.createInvite({
        email: email || undefined,
        max_uses: maxUses,
        expires_days: expiresDays,
      });
      setShowCreate(false);
      setEmail("");
      setMaxUses(1);
      loadInvites();
    } catch {
      // silent
    } finally {
      setCreating(false);
    }
  };

  const handleRevoke = async (id: string) => {
    try {
      await operatorApi.revokeInvite(id);
      loadInvites();
    } catch {
      // silent
    }
  };

  const copyCode = (code: string, id: string) => {
    navigator.clipboard.writeText(code);
    setCopiedId(id);
    setTimeout(() => setCopiedId(null), 2000);
  };

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-display font-bold">Invite Codes</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          Create Invite
        </button>
      </div>

      {/* Invites Table */}
      <div className="rounded-xl border border-border bg-card overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-border bg-muted/50">
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Code</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Email</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Uses</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Expires</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Created</th>
                <th className="text-left px-4 py-3 font-medium text-muted-foreground">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-border">
              {loading ? (
                [...Array(3)].map((_, i) => (
                  <tr key={i}>
                    {[...Array(6)].map((_, j) => (
                      <td key={j} className="px-4 py-3">
                        <div className="h-4 bg-muted rounded animate-pulse w-20" />
                      </td>
                    ))}
                  </tr>
                ))
              ) : invites.length === 0 ? (
                <tr>
                  <td colSpan={6} className="px-4 py-8 text-center text-muted-foreground">
                    No active invite codes. Create one to invite contractors to your fleet.
                  </td>
                </tr>
              ) : (
                invites.map((inv) => (
                  <tr key={inv.id} className="hover:bg-muted/30 transition-colors">
                    <td className="px-4 py-3">
                      <div className="flex items-center gap-2">
                        <code className="bg-muted px-2 py-1 rounded text-xs font-mono font-bold">
                          {inv.invite_code}
                        </code>
                        <button
                          onClick={() => copyCode(inv.invite_code, inv.id)}
                          className="text-xs text-muted-foreground hover:text-foreground"
                        >
                          {copiedId === inv.id ? "Copied!" : "Copy"}
                        </button>
                      </div>
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">{inv.email || "-"}</td>
                    <td className="px-4 py-3">{inv.use_count} / {inv.max_uses}</td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {inv.expires_at
                        ? new Date(inv.expires_at).toLocaleDateString()
                        : "Never"}
                    </td>
                    <td className="px-4 py-3 text-muted-foreground">
                      {new Date(inv.created_at).toLocaleDateString()}
                    </td>
                    <td className="px-4 py-3">
                      <button
                        onClick={() => handleRevoke(inv.id)}
                        className="text-xs text-red-600 hover:text-red-700 font-medium"
                      >
                        Revoke
                      </button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </div>

      {/* Create Invite Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50" onClick={() => setShowCreate(false)}>
          <div className="bg-card rounded-xl border border-border shadow-xl w-full max-w-sm mx-4" onClick={(e) => e.stopPropagation()}>
            <form onSubmit={handleCreate}>
              <div className="px-6 py-4 border-b border-border">
                <h3 className="font-semibold">Create Invite Code</h3>
              </div>
              <div className="px-6 py-4 space-y-4">
                <div>
                  <label className="block text-sm font-medium mb-1">Email (optional)</label>
                  <input
                    type="email"
                    value={email}
                    onChange={(e) => setEmail(e.target.value)}
                    placeholder="contractor@example.com"
                    className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                  />
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <div>
                    <label className="block text-sm font-medium mb-1">Max Uses</label>
                    <input
                      type="number"
                      min={1}
                      max={100}
                      value={maxUses}
                      onChange={(e) => setMaxUses(parseInt(e.target.value) || 1)}
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>
                  <div>
                    <label className="block text-sm font-medium mb-1">Expires (days)</label>
                    <input
                      type="number"
                      min={1}
                      max={365}
                      value={expiresDays}
                      onChange={(e) => setExpiresDays(parseInt(e.target.value) || 7)}
                      className="w-full rounded-lg border border-border bg-background px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-ring"
                    />
                  </div>
                </div>
              </div>
              <div className="px-6 py-3 border-t border-border flex justify-end gap-2">
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="text-sm px-4 py-2 rounded-lg border border-border hover:bg-muted transition-colors"
                >
                  Cancel
                </button>
                <button
                  type="submit"
                  disabled={creating}
                  className="text-sm px-4 py-2 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {creating ? "Creating..." : "Create"}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
