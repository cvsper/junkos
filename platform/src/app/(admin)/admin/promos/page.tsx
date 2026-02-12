"use client";

import { useEffect, useState, useCallback } from "react";
import {
  AlertCircle,
  RefreshCw,
  Plus,
  Tag,
  Pencil,
  Trash2,
  X,
  Loader2,
  CheckCircle2,
} from "lucide-react";
import { Card, CardContent } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  adminApi,
  type AdminPromoCodeRecord,
  type PromoCodeCreatePayload,
} from "@/lib/api";

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function formatDate(dateStr: string | null): string {
  if (!dateStr) return "--";
  try {
    return new Date(dateStr).toLocaleDateString("en-US", {
      month: "short",
      day: "numeric",
      year: "numeric",
    });
  } catch {
    return dateStr;
  }
}

function formatDiscountValue(promo: AdminPromoCodeRecord): string {
  if (promo.discount_type === "percentage") {
    return `${promo.discount_value}%`;
  }
  return `$${promo.discount_value.toFixed(2)}`;
}

function formatUsage(promo: AdminPromoCodeRecord): string {
  if (promo.max_uses === null || promo.max_uses === undefined) {
    return `${promo.use_count} / Unlimited`;
  }
  return `${promo.use_count} / ${promo.max_uses}`;
}

function isExpired(promo: AdminPromoCodeRecord): boolean {
  if (!promo.expires_at) return false;
  return new Date(promo.expires_at) < new Date();
}

// ---------------------------------------------------------------------------
// Modal for Create / Edit
// ---------------------------------------------------------------------------

interface PromoFormData {
  code: string;
  discount_type: "percentage" | "fixed";
  discount_value: string;
  min_order_amount: string;
  max_discount: string;
  max_uses: string;
  expires_at: string;
  is_active: boolean;
}

const emptyForm: PromoFormData = {
  code: "",
  discount_type: "percentage",
  discount_value: "",
  min_order_amount: "0",
  max_discount: "",
  max_uses: "",
  expires_at: "",
  is_active: true,
};

function PromoModal({
  isOpen,
  onClose,
  onSave,
  initialData,
  isEditing,
}: {
  isOpen: boolean;
  onClose: () => void;
  onSave: (data: PromoCodeCreatePayload) => Promise<void>;
  initialData: PromoFormData;
  isEditing: boolean;
}) {
  const [form, setForm] = useState<PromoFormData>(initialData);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    setForm(initialData);
    setError(null);
  }, [initialData, isOpen]);

  if (!isOpen) return null;

  const handleSubmit = async () => {
    if (!form.code.trim()) {
      setError("Code is required.");
      return;
    }
    if (!form.discount_value || parseFloat(form.discount_value) <= 0) {
      setError("Discount value must be greater than 0.");
      return;
    }
    if (
      form.discount_type === "percentage" &&
      parseFloat(form.discount_value) > 100
    ) {
      setError("Percentage discount cannot exceed 100%.");
      return;
    }

    setSaving(true);
    setError(null);

    try {
      const payload: PromoCodeCreatePayload = {
        code: form.code.trim().toUpperCase(),
        discount_type: form.discount_type,
        discount_value: parseFloat(form.discount_value),
        min_order_amount: form.min_order_amount
          ? parseFloat(form.min_order_amount)
          : 0,
        max_discount:
          form.max_discount && parseFloat(form.max_discount) > 0
            ? parseFloat(form.max_discount)
            : null,
        max_uses:
          form.max_uses && parseInt(form.max_uses) > 0
            ? parseInt(form.max_uses)
            : null,
        expires_at: form.expires_at
          ? new Date(form.expires_at).toISOString()
          : null,
        is_active: form.is_active,
      };

      await onSave(payload);
      onClose();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to save promo code.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center">
      {/* Overlay */}
      <div
        className="absolute inset-0 bg-black/50"
        onClick={onClose}
      />

      {/* Modal */}
      <div className="relative bg-card border border-border rounded-xl shadow-xl w-full max-w-lg mx-4 max-h-[90vh] overflow-y-auto">
        <div className="flex items-center justify-between p-6 border-b border-border">
          <h2 className="font-display text-xl font-bold">
            {isEditing ? "Edit Promo Code" : "Create Promo Code"}
          </h2>
          <button
            onClick={onClose}
            className="text-muted-foreground hover:text-foreground transition-colors"
          >
            <X className="h-5 w-5" />
          </button>
        </div>

        <div className="p-6 space-y-5">
          {error && (
            <div className="flex items-start gap-2 rounded-lg border border-destructive/30 bg-destructive/5 p-3">
              <AlertCircle className="h-4 w-4 text-destructive shrink-0 mt-0.5" />
              <p className="text-sm text-destructive">{error}</p>
            </div>
          )}

          {/* Code */}
          <div className="space-y-2">
            <Label className="text-sm font-medium">
              Promo Code *
            </Label>
            <Input
              placeholder="e.g. SUMMER20"
              value={form.code}
              onChange={(e) =>
                setForm({ ...form, code: e.target.value.toUpperCase() })
              }
              disabled={saving}
            />
          </div>

          {/* Discount Type + Value */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-sm font-medium">
                Discount Type *
              </Label>
              <select
                value={form.discount_type}
                onChange={(e) =>
                  setForm({
                    ...form,
                    discount_type: e.target.value as "percentage" | "fixed",
                  })
                }
                disabled={saving}
                className="w-full h-10 rounded-md border border-input bg-background px-3 text-sm ring-offset-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                <option value="percentage">Percentage (%)</option>
                <option value="fixed">Fixed ($)</option>
              </select>
            </div>
            <div className="space-y-2">
              <Label className="text-sm font-medium">
                Discount Value *
              </Label>
              <Input
                type="number"
                placeholder={form.discount_type === "percentage" ? "20" : "15.00"}
                value={form.discount_value}
                onChange={(e) =>
                  setForm({ ...form, discount_value: e.target.value })
                }
                min="0"
                step={form.discount_type === "percentage" ? "1" : "0.01"}
                disabled={saving}
              />
            </div>
          </div>

          {/* Min Order + Max Discount */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-sm font-medium">
                Min Order Amount ($)
              </Label>
              <Input
                type="number"
                placeholder="0"
                value={form.min_order_amount}
                onChange={(e) =>
                  setForm({ ...form, min_order_amount: e.target.value })
                }
                min="0"
                step="0.01"
                disabled={saving}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-sm font-medium">
                Max Discount ($)
                <span className="text-muted-foreground font-normal ml-1">
                  (% only)
                </span>
              </Label>
              <Input
                type="number"
                placeholder="No limit"
                value={form.max_discount}
                onChange={(e) =>
                  setForm({ ...form, max_discount: e.target.value })
                }
                min="0"
                step="0.01"
                disabled={saving || form.discount_type === "fixed"}
              />
            </div>
          </div>

          {/* Max Uses + Expiry */}
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-2">
              <Label className="text-sm font-medium">
                Max Uses
              </Label>
              <Input
                type="number"
                placeholder="Unlimited"
                value={form.max_uses}
                onChange={(e) =>
                  setForm({ ...form, max_uses: e.target.value })
                }
                min="0"
                step="1"
                disabled={saving}
              />
            </div>
            <div className="space-y-2">
              <Label className="text-sm font-medium">
                Expires At
              </Label>
              <Input
                type="datetime-local"
                value={form.expires_at}
                onChange={(e) =>
                  setForm({ ...form, expires_at: e.target.value })
                }
                disabled={saving}
              />
            </div>
          </div>

          {/* Active toggle */}
          <div className="flex items-center gap-3">
            <button
              type="button"
              onClick={() => setForm({ ...form, is_active: !form.is_active })}
              disabled={saving}
              className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                form.is_active ? "bg-primary" : "bg-muted-foreground/30"
              }`}
            >
              <span
                className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                  form.is_active ? "translate-x-6" : "translate-x-1"
                }`}
              />
            </button>
            <span className="text-sm font-medium">
              {form.is_active ? "Active" : "Inactive"}
            </span>
          </div>
        </div>

        {/* Footer */}
        <div className="flex items-center justify-end gap-3 p-6 border-t border-border">
          <Button variant="outline" onClick={onClose} disabled={saving}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={saving}>
            {saving ? (
              <>
                <Loader2 className="mr-2 h-4 w-4 animate-spin" />
                Saving...
              </>
            ) : isEditing ? (
              "Update"
            ) : (
              "Create"
            )}
          </Button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Page
// ---------------------------------------------------------------------------

export default function AdminPromosPage() {
  const [promos, setPromos] = useState<AdminPromoCodeRecord[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [total, setTotal] = useState(0);

  // Modal state
  const [modalOpen, setModalOpen] = useState(false);
  const [editingPromo, setEditingPromo] = useState<AdminPromoCodeRecord | null>(
    null
  );
  const [modalForm, setModalForm] = useState<PromoFormData>(emptyForm);

  const fetchPromos = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const res = await adminApi.promos();
      setPromos(res.promos || []);
      setTotal(res.total || 0);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Failed to load promo codes");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchPromos();
  }, [fetchPromos]);

  const handleCreate = () => {
    setEditingPromo(null);
    setModalForm(emptyForm);
    setModalOpen(true);
  };

  const handleEdit = (promo: AdminPromoCodeRecord) => {
    setEditingPromo(promo);
    setModalForm({
      code: promo.code,
      discount_type: promo.discount_type,
      discount_value: String(promo.discount_value),
      min_order_amount: String(promo.min_order_amount || 0),
      max_discount: promo.max_discount ? String(promo.max_discount) : "",
      max_uses: promo.max_uses !== null ? String(promo.max_uses) : "",
      expires_at: promo.expires_at
        ? new Date(promo.expires_at).toISOString().slice(0, 16)
        : "",
      is_active: promo.is_active,
    });
    setModalOpen(true);
  };

  const handleSave = async (data: PromoCodeCreatePayload) => {
    if (editingPromo) {
      await adminApi.updatePromo(editingPromo.id, data);
    } else {
      await adminApi.createPromo(data);
    }
    await fetchPromos();
  };

  const handleDeactivate = async (promo: AdminPromoCodeRecord) => {
    if (
      !window.confirm(
        `Are you sure you want to deactivate the promo code "${promo.code}"?`
      )
    ) {
      return;
    }

    try {
      await adminApi.deactivatePromo(promo.id);
      await fetchPromos();
    } catch (err) {
      setError(
        err instanceof Error ? err.message : "Failed to deactivate promo code"
      );
    }
  };

  // Table skeleton rows
  const SkeletonRow = () => (
    <tr className="border-b border-border">
      {Array.from({ length: 7 }).map((_, i) => (
        <td key={i} className="px-4 py-3">
          <div className="h-4 w-full max-w-[100px] rounded bg-muted animate-pulse" />
        </td>
      ))}
    </tr>
  );

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display text-3xl font-bold tracking-tight">
          Promo Codes
        </h1>
        <p className="text-muted-foreground mt-1">
          Create and manage coupon codes for customer discounts.
        </p>
      </div>

      {/* Actions Bar */}
      <div className="flex items-center gap-3 mb-6">
        <Button onClick={handleCreate}>
          <Plus className="mr-2 h-4 w-4" />
          Create Promo Code
        </Button>
        <Button
          variant="outline"
          size="sm"
          onClick={fetchPromos}
          disabled={loading}
        >
          <RefreshCw
            className={`mr-2 h-4 w-4 ${loading ? "animate-spin" : ""}`}
          />
          Refresh
        </Button>
        {total > 0 && (
          <span className="ml-auto text-sm text-muted-foreground">
            {total} promo code{total !== 1 ? "s" : ""}
          </span>
        )}
      </div>

      {/* Error State */}
      {error && (
        <Card className="mb-6">
          <CardContent className="flex flex-col items-center justify-center py-12">
            <AlertCircle className="h-10 w-10 text-destructive mb-3" />
            <p className="text-sm text-muted-foreground mb-4">{error}</p>
            <Button variant="outline" onClick={fetchPromos}>
              <RefreshCw className="mr-2 h-4 w-4" />
              Retry
            </Button>
          </CardContent>
        </Card>
      )}

      {/* Promos Table */}
      {!error && (
        <div className="rounded-lg border border-border bg-card overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border bg-muted/50">
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Code
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Discount
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Min Order
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Usage
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Expires
                  </th>
                  <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Status
                  </th>
                  <th className="text-right text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                    Actions
                  </th>
                </tr>
              </thead>
              <tbody>
                {loading ? (
                  Array.from({ length: 5 }).map((_, i) => (
                    <SkeletonRow key={i} />
                  ))
                ) : promos.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-center py-12">
                      <div className="flex flex-col items-center gap-2">
                        <Tag className="h-10 w-10 text-muted-foreground/50" />
                        <p className="text-muted-foreground text-sm">
                          No promo codes yet. Create one to get started.
                        </p>
                      </div>
                    </td>
                  </tr>
                ) : (
                  promos.map((promo) => {
                    const expired = isExpired(promo);
                    const maxedOut =
                      promo.max_uses !== null &&
                      promo.use_count >= promo.max_uses;

                    let statusLabel = "Active";
                    let statusClass =
                      "bg-emerald-100 text-emerald-700 dark:bg-emerald-900/30 dark:text-emerald-400";

                    if (!promo.is_active) {
                      statusLabel = "Inactive";
                      statusClass =
                        "bg-gray-100 text-gray-600 dark:bg-gray-800 dark:text-gray-400";
                    } else if (expired) {
                      statusLabel = "Expired";
                      statusClass =
                        "bg-red-100 text-red-700 dark:bg-red-900/30 dark:text-red-400";
                    } else if (maxedOut) {
                      statusLabel = "Maxed Out";
                      statusClass =
                        "bg-amber-100 text-amber-700 dark:bg-amber-900/30 dark:text-amber-400";
                    }

                    return (
                      <tr
                        key={promo.id}
                        className="border-b border-border hover:bg-muted/30 transition-colors"
                      >
                        <td className="px-4 py-3">
                          <span className="inline-flex items-center gap-1.5 text-sm font-mono font-bold bg-muted px-2 py-1 rounded">
                            <Tag className="h-3 w-3 text-muted-foreground" />
                            {promo.code}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-sm font-medium">
                          {formatDiscountValue(promo)}
                          {promo.discount_type === "percentage" &&
                            promo.max_discount && (
                              <span className="text-muted-foreground text-xs ml-1">
                                (max ${promo.max_discount.toFixed(2)})
                              </span>
                            )}
                        </td>
                        <td className="px-4 py-3 text-sm text-muted-foreground">
                          {promo.min_order_amount > 0
                            ? `$${promo.min_order_amount.toFixed(2)}`
                            : "--"}
                        </td>
                        <td className="px-4 py-3 text-sm">
                          {formatUsage(promo)}
                        </td>
                        <td className="px-4 py-3 text-sm text-muted-foreground">
                          {promo.expires_at
                            ? formatDate(promo.expires_at)
                            : "Never"}
                        </td>
                        <td className="px-4 py-3">
                          <span
                            className={`inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium ${statusClass}`}
                          >
                            {statusLabel}
                          </span>
                        </td>
                        <td className="px-4 py-3 text-right">
                          <div className="flex items-center justify-end gap-1">
                            <Button
                              variant="ghost"
                              size="sm"
                              onClick={() => handleEdit(promo)}
                              className="h-8 w-8 p-0"
                            >
                              <Pencil className="h-4 w-4" />
                            </Button>
                            {promo.is_active && (
                              <Button
                                variant="ghost"
                                size="sm"
                                onClick={() => handleDeactivate(promo)}
                                className="h-8 w-8 p-0 text-destructive hover:text-destructive"
                              >
                                <Trash2 className="h-4 w-4" />
                              </Button>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {/* Create / Edit Modal */}
      <PromoModal
        isOpen={modalOpen}
        onClose={() => setModalOpen(false)}
        onSave={handleSave}
        initialData={modalForm}
        isEditing={!!editingPromo}
      />
    </div>
  );
}
