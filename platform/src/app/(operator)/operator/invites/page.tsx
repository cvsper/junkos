"use client";

import { useEffect, useState } from "react";
import {
  Mail,
  Copy,
  Check,
  Trash2,
  Plus,
  X,
  Send,
  Loader2,
} from "lucide-react";
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

  if (loading) {
    return (
      <div className="space-y-6">
        <div className="flex items-center justify-between">
          <div className="h-8 bg-muted rounded w-32 animate-pulse" />
          <div className="h-10 bg-muted rounded w-28 animate-pulse" />
        </div>

        {/* Table skeleton - Desktop */}
        <div className="rounded-xl border border-border bg-card overflow-hidden hidden md:block">
          <div className="border-b border-border bg-muted/50 px-4 py-3">
            <div className="flex gap-8">
              {["w-24", "w-32", "w-16", "w-20", "w-20", "w-16"].map((w, i) => (
                <div key={i} className={`h-4 bg-muted rounded ${w} animate-pulse`} />
              ))}
            </div>
          </div>
          {[...Array(3)].map((_, i) => (
            <div key={i} className="px-4 py-3 border-b border-border animate-pulse">
              <div className="flex gap-8 items-center">
                <div className="h-6 bg-muted rounded w-28" />
                <div className="h-4 bg-muted rounded w-32" />
                <div className="h-4 bg-muted rounded w-12" />
                <div className="h-4 bg-muted rounded w-20" />
                <div className="h-4 bg-muted rounded w-20" />
                <div className="h-4 bg-muted rounded w-14" />
              </div>
            </div>
          ))}
        </div>

        {/* Card skeleton - Mobile */}
        <div className="md:hidden space-y-3">
          {[...Array(3)].map((_, i) => (
            <div key={i} className="rounded-xl border border-border bg-card p-4 animate-pulse space-y-3">
              <div className="flex items-center justify-between">
                <div className="h-7 bg-muted rounded w-28" />
                <div className="h-4 bg-muted rounded w-12" />
              </div>
              <div className="flex gap-4">
                <div className="h-3 bg-muted rounded w-20" />
                <div className="h-3 bg-muted rounded w-24" />
              </div>
              <div className="flex gap-2">
                <div className="h-8 bg-muted rounded w-16" />
                <div className="h-8 bg-muted rounded w-16" />
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-display font-bold">Invite Codes</h1>
        <button
          onClick={() => setShowCreate(true)}
          className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
        >
          <Plus className="w-4 h-4" />
          <span className="hidden sm:inline">Create Invite</span>
          <span className="sm:hidden">Invite</span>
        </button>
      </div>

      {invites.length === 0 ? (
        /* Empty State */
        <div className="rounded-xl border border-border bg-card px-4 py-16 flex flex-col items-center text-center">
          <div className="w-14 h-14 rounded-full bg-purple-50 flex items-center justify-center mb-4">
            <Send className="w-7 h-7 text-purple-500" />
          </div>
          <h3 className="font-semibold text-foreground mb-1">No active invite codes</h3>
          <p className="text-sm text-muted-foreground max-w-sm mb-4">
            Create an invite code to start building your fleet. You can set limits on uses and expiration.
          </p>
          <button
            onClick={() => setShowCreate(true)}
            className="inline-flex items-center gap-2 px-4 py-2 rounded-lg bg-primary text-primary-foreground text-sm font-medium hover:bg-primary/90 transition-colors"
          >
            <Plus className="w-4 h-4" />
            Create Your First Invite
          </button>
        </div>
      ) : (
        <>
          {/* Invites Table - Desktop */}
          <div className="rounded-xl border border-border bg-card overflow-hidden hidden md:block">
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
                  {invites.map((inv) => (
                    <tr key={inv.id} className="hover:bg-muted/30 transition-colors">
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-2">
                          <code className="bg-muted px-2 py-1 rounded text-xs font-mono font-bold">
                            {inv.invite_code}
                          </code>
                          <button
                            onClick={() => copyCode(inv.invite_code, inv.id)}
                            className="text-muted-foreground hover:text-foreground transition-colors p-1 rounded hover:bg-muted"
                          >
                            {copiedId === inv.id ? (
                              <Check className="w-3.5 h-3.5 text-green-600" />
                            ) : (
                              <Copy className="w-3.5 h-3.5" />
                            )}
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
                          className="inline-flex items-center gap-1 text-xs text-red-600 hover:text-red-700 font-medium px-2 py-1 rounded hover:bg-red-50 transition-colors"
                        >
                          <Trash2 className="w-3 h-3" />
                          Revoke
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          {/* Invites Cards - Mobile */}
          <div className="md:hidden space-y-3">
            {invites.map((inv) => (
              <div key={inv.id} className="rounded-xl border border-border bg-card p-4 space-y-3">
                <div className="flex items-center justify-between">
                  <code className="bg-muted px-2.5 py-1 rounded text-xs font-mono font-bold">
                    {inv.invite_code}
                  </code>
                  <span className="text-xs text-muted-foreground">
                    {inv.use_count} / {inv.max_uses} uses
                  </span>
                </div>
                {inv.email && (
                  <p className="text-xs text-muted-foreground truncate">
                    For: {inv.email}
                  </p>
                )}
                <div className="flex items-center gap-4 text-xs text-muted-foreground">
                  <span>
                    Expires: {inv.expires_at ? new Date(inv.expires_at).toLocaleDateString() : "Never"}
                  </span>
                  <span>
                    Created: {new Date(inv.created_at).toLocaleDateString()}
                  </span>
                </div>
                <div className="flex items-center gap-2 pt-1">
                  <button
                    onClick={() => copyCode(inv.invite_code, inv.id)}
                    className="inline-flex items-center gap-1.5 text-xs font-medium px-3 py-1.5 rounded-lg border border-border hover:bg-muted transition-colors"
                  >
                    {copiedId === inv.id ? (
                      <>
                        <Check className="w-3 h-3 text-green-600" />
                        Copied
                      </>
                    ) : (
                      <>
                        <Copy className="w-3 h-3" />
                        Copy
                      </>
                    )}
                  </button>
                  <button
                    onClick={() => handleRevoke(inv.id)}
                    className="inline-flex items-center gap-1.5 text-xs font-medium text-red-600 px-3 py-1.5 rounded-lg border border-red-200 hover:bg-red-50 transition-colors"
                  >
                    <Trash2 className="w-3 h-3" />
                    Revoke
                  </button>
                </div>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Create Invite Modal */}
      {showCreate && (
        <div className="fixed inset-0 z-50 flex items-end sm:items-center justify-center bg-black/50" onClick={() => setShowCreate(false)}>
          <div
            className="bg-card rounded-t-xl sm:rounded-xl border border-border shadow-xl w-full sm:max-w-sm sm:mx-4"
            onClick={(e) => e.stopPropagation()}
          >
            <form onSubmit={handleCreate}>
              <div className="px-4 sm:px-6 py-4 border-b border-border flex items-center justify-between">
                <h3 className="font-semibold">Create Invite Code</h3>
                <button
                  type="button"
                  onClick={() => setShowCreate(false)}
                  className="p-1 rounded-lg hover:bg-muted transition-colors"
                >
                  <X className="w-5 h-5" />
                </button>
              </div>
              <div className="px-4 sm:px-6 py-4 space-y-4">
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
              <div className="px-4 sm:px-6 py-3 border-t border-border flex justify-end gap-2">
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
                  className="inline-flex items-center gap-2 text-sm px-4 py-2 rounded-lg bg-primary text-primary-foreground font-medium hover:bg-primary/90 transition-colors disabled:opacity-50"
                >
                  {creating ? (
                    <>
                      <Loader2 className="w-4 h-4 animate-spin" />
                      Creating...
                    </>
                  ) : (
                    "Create"
                  )}
                </button>
              </div>
            </form>
          </div>
        </div>
      )}
    </div>
  );
}
