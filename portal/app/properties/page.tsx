"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { Nav } from "@/components/nav";
import { portalFetch } from "@/lib/api";
import { useAuthStore } from "@/lib/stores/authStore";

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
  const router = useRouter();
  const { token, isLoading, hydrate, role } = useAuthStore();
  const [rows, setRows] = useState<Property[]>([]);
  const [form, setForm] = useState({
    name: "",
    address_line1: "",
    city: "",
    state: "FL",
    zip: "",
    unit_count: 1,
  });
  const canCreate =
    role === "owner" || role === "admin" || role === "operator";

  useEffect(() => {
    hydrate();
  }, [hydrate]);

  async function refresh() {
    const r = await portalFetch<{ properties: Property[] }>("/properties");
    setRows(r.properties);
  }

  useEffect(() => {
    if (isLoading) return;
    if (!token) return router.replace("/login");
    refresh();
  }, [isLoading, token, router]);

  async function create(e: React.FormEvent) {
    e.preventDefault();
    await portalFetch("/properties", {
      method: "POST",
      body: JSON.stringify(form),
    });
    setForm({ ...form, name: "", address_line1: "", zip: "" });
    await refresh();
  }

  if (isLoading || !token) return <div className="p-8 text-gray-500">Loading…</div>;

  return (
    <div className="flex min-h-screen">
      <Nav />
      <main className="flex-1 p-8 max-w-5xl">
        <h1 className="text-2xl font-semibold mb-6">Properties</h1>

        {canCreate && (
          <form
            onSubmit={create}
            className="mb-6 grid grid-cols-1 md:grid-cols-6 gap-2 rounded-lg border border-gray-200 bg-white p-4"
          >
            <input
              placeholder="Property name"
              value={form.name}
              required
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              className="md:col-span-2 rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <input
              placeholder="Address"
              value={form.address_line1}
              onChange={(e) =>
                setForm({ ...form, address_line1: e.target.value })
              }
              className="md:col-span-2 rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <input
              placeholder="ZIP"
              value={form.zip}
              onChange={(e) => setForm({ ...form, zip: e.target.value })}
              className="rounded border border-gray-300 px-3 py-2 text-sm"
            />
            <button
              type="submit"
              className="rounded bg-brand-600 text-white text-sm px-4 py-2 hover:bg-brand-700"
            >
              Add
            </button>
          </form>
        )}

        <div className="rounded-lg border border-gray-200 bg-white overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 text-left">
              <tr>
                <th className="px-4 py-3 text-xs uppercase text-gray-500">
                  Name
                </th>
                <th className="px-4 py-3 text-xs uppercase text-gray-500">
                  Address
                </th>
                <th className="px-4 py-3 text-xs uppercase text-gray-500 text-right">
                  Units
                </th>
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 && (
                <tr>
                  <td colSpan={3} className="p-6 text-center text-gray-500">
                    No properties yet.
                  </td>
                </tr>
              )}
              {rows.map((p) => (
                <tr key={p.id} className="border-t border-gray-100">
                  <td className="px-4 py-3 font-medium">{p.name}</td>
                  <td className="px-4 py-3 text-gray-600">
                    {[p.address_line1, p.city, p.state, p.zip]
                      .filter(Boolean)
                      .join(", ")}
                  </td>
                  <td className="px-4 py-3 text-right">{p.unit_count}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
