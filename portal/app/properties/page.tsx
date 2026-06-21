"use client";

import { useEffect, useState } from "react";
import { Plus } from "lucide-react";
import { portalFetch } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";
import {
  AppShell,
  Card,
  Button,
  Input,
  FieldLabel,
  Table,
  Th,
  Td,
  Tr,
  EmptyRow,
  PortalLoading,
  usePortalGuard,
} from "@/components/ui";

interface Property {
  id: string;
  name: string;
  address_line1: string | null;
  city: string | null;
  state: string | null;
  zip: string | null;
  unit_count: number;
  active: boolean;
}

export default function PropertiesPage() {
  const { ready } = usePortalGuard();
  const { role } = useAuthStore();
  const [rows, setRows] = useState<Property[]>([]);
  const [showForm, setShowForm] = useState(false);
  const [form, setForm] = useState({
    name: "",
    address_line1: "",
    city: "",
    state: "FL",
    zip: "",
    unit_count: 1,
  });
  const canCreate = role === "owner" || role === "admin" || role === "operator";

  async function refresh() {
    const r = await portalFetch<{ properties: Property[] }>("/properties");
    setRows(r.properties);
  }

  useEffect(() => {
    if (ready) refresh();
  }, [ready]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    await portalFetch("/properties", {
      method: "POST",
      body: JSON.stringify(form),
    });
    setForm({ ...form, name: "", address_line1: "", zip: "" });
    setShowForm(false);
    await refresh();
  }

  if (!ready) return <PortalLoading />;

  return (
    <AppShell
      title="Properties"
      subtitle="The sites Umuve services for your business."
      maxWidth="max-w-5xl"
      action={
        canCreate ? (
          <Button onClick={() => setShowForm((v) => !v)}>
            <span className="inline-flex items-center gap-1.5">
              <Plus className="h-4 w-4" /> Add property
            </span>
          </Button>
        ) : undefined
      }
    >
      {canCreate && showForm && (
        <Card className="mb-6 p-5">
          <form onSubmit={create} className="grid grid-cols-1 gap-3 md:grid-cols-6">
            <label className="md:col-span-2">
              <FieldLabel>Property name</FieldLabel>
              <Input
                placeholder="Riverside Apartments"
                value={form.name}
                required
                onChange={(e) => setForm({ ...form, name: e.target.value })}
              />
            </label>
            <label className="md:col-span-2">
              <FieldLabel>Address</FieldLabel>
              <Input
                placeholder="123 Main St"
                value={form.address_line1}
                onChange={(e) =>
                  setForm({ ...form, address_line1: e.target.value })
                }
              />
            </label>
            <label>
              <FieldLabel>ZIP</FieldLabel>
              <Input
                placeholder="33401"
                value={form.zip}
                onChange={(e) => setForm({ ...form, zip: e.target.value })}
              />
            </label>
            <div className="flex items-end">
              <Button type="submit" className="w-full">
                Save
              </Button>
            </div>
          </form>
        </Card>
      )}

      <Table
        head={
          <tr>
            <Th>Name</Th>
            <Th>Address</Th>
            <Th className="text-right">Units</Th>
          </tr>
        }
      >
        {rows.length === 0 ? (
          <EmptyRow colSpan={3}>
            No properties yet. Add one to start scheduling pickups.
          </EmptyRow>
        ) : (
          rows.map((p) => (
            <Tr key={p.id}>
              <Td className="font-medium">{p.name}</Td>
              <Td className="text-gray-600">
                {[p.address_line1, p.city, p.state, p.zip]
                  .filter(Boolean)
                  .join(", ") || "—"}
              </Td>
              <Td className="text-right tabular-nums">{p.unit_count}</Td>
            </Tr>
          ))
        )}
      </Table>
    </AppShell>
  );
}
