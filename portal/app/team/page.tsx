"use client";

import { useEffect, useState } from "react";
import { UserPlus } from "lucide-react";
import { portalFetch } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";
import {
  AppShell,
  Card,
  Button,
  Input,
  Select,
  FieldLabel,
  Badge,
  Table,
  Th,
  Td,
  Tr,
  EmptyRow,
  PortalLoading,
  usePortalGuard,
} from "@/components/ui";

interface Member {
  id: string;
  role: string;
  email: string;
  name: string | null;
  pending: boolean;
  joined_at: string | null;
}

export default function TeamPage() {
  const { ready } = usePortalGuard();
  const { role } = useAuthStore();
  const [members, setMembers] = useState<Member[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [email, setEmail] = useState("");
  const [newRole, setNewRole] = useState<"admin" | "operator" | "viewer">("viewer");
  const [inviteUrl, setInviteUrl] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const canInvite = role === "owner" || role === "admin";

  async function refresh() {
    const r = await portalFetch<{ members: Member[] }>("/orgs/me/members");
    setMembers(r.members);
  }

  useEffect(() => {
    if (ready) refresh();
  }, [ready]);

  async function invite(e: React.FormEvent) {
    e.preventDefault();
    setError(null);
    setInviteUrl(null);
    try {
      const r = await portalFetch<{ invite_url: string }>("/orgs/me/members", {
        method: "POST",
        body: JSON.stringify({ email, role: newRole }),
      });
      setInviteUrl(r.invite_url);
      setEmail("");
      await refresh();
    } catch (e: any) {
      setError(e?.payload?.error || String(e));
    }
  }

  if (!ready) return <PortalLoading />;

  return (
    <AppShell
      title="Team"
      subtitle="Who can see and manage this account."
      maxWidth="max-w-4xl"
      action={
        canInvite ? (
          <Button onClick={() => setShowForm((v) => !v)}>
            <span className="inline-flex items-center gap-1.5">
              <UserPlus className="h-4 w-4" /> Invite teammate
            </span>
          </Button>
        ) : undefined
      }
    >
      {canInvite && showForm && (
        <Card className="mb-6 p-5">
          <form onSubmit={invite} className="flex flex-wrap items-end gap-3">
            <label className="min-w-[16rem] flex-1">
              <FieldLabel>Email</FieldLabel>
              <Input
                type="email"
                required
                value={email}
                placeholder="teammate@yourstore.com"
                onChange={(e) => setEmail(e.target.value)}
              />
            </label>
            <label>
              <FieldLabel>Role</FieldLabel>
              <Select
                value={newRole}
                onChange={(e) => setNewRole(e.target.value as any)}
              >
                <option value="viewer">Viewer</option>
                <option value="operator">Operator</option>
                <option value="admin">Admin</option>
              </Select>
            </label>
            <Button type="submit">Send invite</Button>
          </form>

          {inviteUrl && (
            <div className="mt-4 rounded-lg border border-green-100 bg-green-50 p-3 text-sm">
              <div className="font-medium text-green-800">Invite created</div>
              <div className="mt-1 break-all text-green-700">{inviteUrl}</div>
            </div>
          )}
          {error && (
            <div className="mt-4 rounded-lg border border-red-100 bg-red-50 px-3 py-2 text-sm text-red-700">
              {error}
            </div>
          )}
        </Card>
      )}

      <Table
        head={
          <tr>
            <Th>Member</Th>
            <Th>Role</Th>
            <Th>Status</Th>
          </tr>
        }
      >
        {members.length === 0 ? (
          <EmptyRow colSpan={3}>No teammates yet.</EmptyRow>
        ) : (
          members.map((m) => (
            <Tr key={m.id}>
              <Td>
                <div className="font-medium">{m.name || m.email}</div>
                {m.name && <div className="text-xs text-gray-500">{m.email}</div>}
              </Td>
              <Td className="capitalize text-gray-700">{m.role}</Td>
              <Td>
                {m.pending ? (
                  <Badge tone="yellow">Pending</Badge>
                ) : (
                  <Badge tone="green">Active</Badge>
                )}
              </Td>
            </Tr>
          ))
        )}
      </Table>
    </AppShell>
  );
}
