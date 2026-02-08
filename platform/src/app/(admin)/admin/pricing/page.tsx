"use client";

import { useEffect, useState, useCallback } from "react";
import { adminApi } from "@/lib/api";
import { Button } from "@/components/ui/button";
import {
  Card,
  CardHeader,
  CardTitle,
  CardDescription,
  CardContent,
} from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  DollarSign,
  Plus,
  Save,
  Loader2,
  AlertCircle,
  RefreshCw,
  Zap,
  Percent,
  X,
  Check,
} from "lucide-react";

// ---------------------------------------------------------------------------
// Types
// ---------------------------------------------------------------------------

interface PricingRule {
  id: string;
  item_type: string;
  base_price: number;
  description: string;
  is_active: boolean;
}

interface SurgeZone {
  id: string;
  name: string;
  surge_multiplier: number;
  is_active: boolean;
  start_time: string;
  end_time: string;
  days_of_week: string[];
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdminPricingPage() {
  // ---- Pricing Rules State ----
  const [rules, setRules] = useState<PricingRule[]>([]);
  const [rulesLoading, setRulesLoading] = useState(true);
  const [rulesError, setRulesError] = useState<string | null>(null);
  const [rulesSaving, setRulesSaving] = useState(false);
  const [rulesSaved, setRulesSaved] = useState(false);
  const [showAddRule, setShowAddRule] = useState(false);
  const [newRule, setNewRule] = useState({
    item_type: "",
    base_price: "",
    description: "",
  });

  // ---- Surge Zones State ----
  const [surgeZones, setSurgeZones] = useState<SurgeZone[]>([]);
  const [surgeLoading, setSurgeLoading] = useState(true);
  const [surgeError, setSurgeError] = useState<string | null>(null);
  const [showAddSurge, setShowAddSurge] = useState(false);
  const [surgeSaving, setSurgeSaving] = useState(false);
  const [newSurge, setNewSurge] = useState({
    name: "",
    surge_multiplier: "1.5",
    start_time: "17:00",
    end_time: "20:00",
    days_of_week: [] as string[],
    is_active: true,
  });

  // ---- Fetch Pricing Rules ----
  const fetchRules = useCallback(async () => {
    setRulesLoading(true);
    setRulesError(null);
    try {
      const res = await adminApi.pricingRules();
      setRules(
        (res as { success: boolean; rules: PricingRule[] }).rules || []
      );
    } catch (err: unknown) {
      setRulesError(
        err instanceof Error ? err.message : "Failed to load pricing rules"
      );
    } finally {
      setRulesLoading(false);
    }
  }, []);

  // ---- Fetch Surge Zones ----
  const fetchSurgeZones = useCallback(async () => {
    setSurgeLoading(true);
    setSurgeError(null);
    try {
      const res = await adminApi.surgeZones();
      setSurgeZones(
        (res as { success: boolean; surge_zones: SurgeZone[] }).surge_zones ||
          []
      );
    } catch (err: unknown) {
      setSurgeError(
        err instanceof Error ? err.message : "Failed to load surge zones"
      );
    } finally {
      setSurgeLoading(false);
    }
  }, []);

  useEffect(() => {
    fetchRules();
    fetchSurgeZones();
  }, [fetchRules, fetchSurgeZones]);

  // ---- Handlers: Pricing Rules ----

  const handleRuleChange = (
    id: string,
    field: keyof PricingRule,
    value: string | number | boolean
  ) => {
    setRules((prev) =>
      prev.map((r) => (r.id === id ? { ...r, [field]: value } : r))
    );
    setRulesSaved(false);
  };

  const handleSaveRules = async () => {
    setRulesSaving(true);
    try {
      await adminApi.updatePricingRules(rules);
      setRulesSaved(true);
      setTimeout(() => setRulesSaved(false), 3000);
    } catch (err: unknown) {
      setRulesError(
        err instanceof Error ? err.message : "Failed to save pricing rules"
      );
    } finally {
      setRulesSaving(false);
    }
  };

  const handleAddRule = async () => {
    if (!newRule.item_type || !newRule.base_price) return;
    const ruleToAdd: PricingRule = {
      id: `temp-${Date.now()}`,
      item_type: newRule.item_type,
      base_price: parseFloat(newRule.base_price),
      description: newRule.description,
      is_active: true,
    };
    setRules((prev) => [...prev, ruleToAdd]);
    setNewRule({ item_type: "", base_price: "", description: "" });
    setShowAddRule(false);
    setRulesSaved(false);
  };

  // ---- Handlers: Surge Zones ----

  const toggleSurgeDay = (day: string) => {
    setNewSurge((prev) => ({
      ...prev,
      days_of_week: prev.days_of_week.includes(day)
        ? prev.days_of_week.filter((d) => d !== day)
        : [...prev.days_of_week, day],
    }));
  };

  const handleAddSurgeZone = async () => {
    if (!newSurge.name || !newSurge.surge_multiplier) return;
    setSurgeSaving(true);
    try {
      await adminApi.upsertSurgeZone({
        name: newSurge.name,
        surge_multiplier: parseFloat(newSurge.surge_multiplier),
        start_time: newSurge.start_time,
        end_time: newSurge.end_time,
        days_of_week: newSurge.days_of_week,
        is_active: newSurge.is_active,
      });
      await fetchSurgeZones();
      setNewSurge({
        name: "",
        surge_multiplier: "1.5",
        start_time: "17:00",
        end_time: "20:00",
        days_of_week: [],
        is_active: true,
      });
      setShowAddSurge(false);
    } catch (err: unknown) {
      setSurgeError(
        err instanceof Error ? err.message : "Failed to save surge zone"
      );
    } finally {
      setSurgeSaving(false);
    }
  };

  // ---- Render Helpers ----

  const renderLoadingState = () => (
    <div className="flex items-center justify-center py-12">
      <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" />
      <span className="ml-2 text-sm text-muted-foreground">Loading...</span>
    </div>
  );

  const renderErrorState = (message: string, onRetry: () => void) => (
    <div className="flex flex-col items-center justify-center py-12 text-center">
      <AlertCircle className="h-8 w-8 text-destructive mb-2" />
      <p className="text-sm text-destructive mb-3">{message}</p>
      <Button variant="outline" size="sm" onClick={onRetry}>
        <RefreshCw className="h-4 w-4 mr-2" />
        Retry
      </Button>
    </div>
  );

  return (
    <div>
      {/* Header */}
      <div className="mb-8">
        <h1 className="font-display text-3xl font-bold tracking-tight">
          Pricing Rules
        </h1>
        <p className="text-muted-foreground mt-1">
          Configure pricing tiers, item categories, and surge pricing.
        </p>
      </div>

      <div className="space-y-8">
        {/* ---------------------------------------------------------------- */}
        {/* Section 1: Item Pricing Rules                                     */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 font-display text-lg">
                  <DollarSign className="h-5 w-5 text-primary" />
                  Item Pricing Rules
                </CardTitle>
                <CardDescription className="mt-1">
                  Set base prices for each item type. Changes are applied after
                  saving.
                </CardDescription>
              </div>
              <div className="flex items-center gap-2">
                <Button
                  variant="outline"
                  size="sm"
                  onClick={() => setShowAddRule(!showAddRule)}
                >
                  {showAddRule ? (
                    <>
                      <X className="h-4 w-4 mr-1" /> Cancel
                    </>
                  ) : (
                    <>
                      <Plus className="h-4 w-4 mr-1" /> Add Rule
                    </>
                  )}
                </Button>
                <Button
                  size="sm"
                  onClick={handleSaveRules}
                  disabled={rulesSaving || rules.length === 0}
                >
                  {rulesSaving ? (
                    <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                  ) : rulesSaved ? (
                    <Check className="h-4 w-4 mr-1" />
                  ) : (
                    <Save className="h-4 w-4 mr-1" />
                  )}
                  {rulesSaved ? "Saved" : "Save Changes"}
                </Button>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {rulesLoading ? (
              renderLoadingState()
            ) : rulesError ? (
              renderErrorState(rulesError, fetchRules)
            ) : (
              <>
                {/* Add Rule Inline Form */}
                {showAddRule && (
                  <div className="mb-4 rounded-md border border-border bg-muted/30 p-4">
                    <p className="text-sm font-medium mb-3">New Pricing Rule</p>
                    <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                      <div>
                        <Label htmlFor="new-item-type">Item Type</Label>
                        <Input
                          id="new-item-type"
                          placeholder="e.g. Couch"
                          value={newRule.item_type}
                          onChange={(e) =>
                            setNewRule((prev) => ({
                              ...prev,
                              item_type: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <div>
                        <Label htmlFor="new-base-price">Base Price ($)</Label>
                        <Input
                          id="new-base-price"
                          type="number"
                          step="0.01"
                          min="0"
                          placeholder="75.00"
                          value={newRule.base_price}
                          onChange={(e) =>
                            setNewRule((prev) => ({
                              ...prev,
                              base_price: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <div>
                        <Label htmlFor="new-description">Description</Label>
                        <Input
                          id="new-description"
                          placeholder="Standard couch removal"
                          value={newRule.description}
                          onChange={(e) =>
                            setNewRule((prev) => ({
                              ...prev,
                              description: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <div className="flex items-end">
                        <Button
                          size="sm"
                          onClick={handleAddRule}
                          disabled={!newRule.item_type || !newRule.base_price}
                          className="w-full"
                        >
                          <Plus className="h-4 w-4 mr-1" />
                          Add
                        </Button>
                      </div>
                    </div>
                  </div>
                )}

                {/* Rules Table */}
                {rules.length === 0 ? (
                  <div className="text-center py-8">
                    <p className="text-sm text-muted-foreground">
                      No pricing rules configured yet. Click &quot;Add
                      Rule&quot; to create your first item pricing rule.
                    </p>
                  </div>
                ) : (
                  <div className="rounded-lg border border-border overflow-hidden">
                    <div className="overflow-x-auto">
                      <table className="w-full">
                        <thead>
                          <tr className="border-b border-border bg-muted/50">
                            <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                              Item Type
                            </th>
                            <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                              Base Price
                            </th>
                            <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                              Description
                            </th>
                            <th className="text-center text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                              Active
                            </th>
                          </tr>
                        </thead>
                        <tbody>
                          {rules.map((rule) => (
                            <tr
                              key={rule.id}
                              className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors"
                            >
                              <td className="px-4 py-3 text-sm font-medium">
                                {rule.item_type}
                              </td>
                              <td className="px-4 py-3">
                                <div className="flex items-center gap-1">
                                  <span className="text-sm text-muted-foreground">
                                    $
                                  </span>
                                  <Input
                                    type="number"
                                    step="0.01"
                                    min="0"
                                    className="w-24 h-8 text-sm"
                                    value={rule.base_price}
                                    onChange={(e) =>
                                      handleRuleChange(
                                        rule.id,
                                        "base_price",
                                        parseFloat(e.target.value) || 0
                                      )
                                    }
                                  />
                                </div>
                              </td>
                              <td className="px-4 py-3 text-sm text-muted-foreground">
                                {rule.description}
                              </td>
                              <td className="px-4 py-3 text-center">
                                <button
                                  onClick={() =>
                                    handleRuleChange(
                                      rule.id,
                                      "is_active",
                                      !rule.is_active
                                    )
                                  }
                                  className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                                    rule.is_active
                                      ? "bg-primary"
                                      : "bg-muted-foreground/30"
                                  }`}
                                >
                                  <span
                                    className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                                      rule.is_active
                                        ? "translate-x-6"
                                        : "translate-x-1"
                                    }`}
                                  />
                                </button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Section 2: Surge Zones                                            */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 font-display text-lg">
                  <Zap className="h-5 w-5 text-primary" />
                  Surge Zones
                </CardTitle>
                <CardDescription className="mt-1">
                  Configure time-based surge pricing multipliers.
                </CardDescription>
              </div>
              <Button
                variant="outline"
                size="sm"
                onClick={() => setShowAddSurge(!showAddSurge)}
              >
                {showAddSurge ? (
                  <>
                    <X className="h-4 w-4 mr-1" /> Cancel
                  </>
                ) : (
                  <>
                    <Plus className="h-4 w-4 mr-1" /> Add Surge Zone
                  </>
                )}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {surgeLoading ? (
              renderLoadingState()
            ) : surgeError ? (
              renderErrorState(surgeError, fetchSurgeZones)
            ) : (
              <>
                {/* Add Surge Zone Form */}
                {showAddSurge && (
                  <div className="mb-6 rounded-md border border-border bg-muted/30 p-4">
                    <p className="text-sm font-medium mb-3">
                      New Surge Zone
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-2 gap-4 mb-4">
                      <div>
                        <Label htmlFor="surge-name">Zone Name</Label>
                        <Input
                          id="surge-name"
                          placeholder="e.g. Evening Rush"
                          value={newSurge.name}
                          onChange={(e) =>
                            setNewSurge((prev) => ({
                              ...prev,
                              name: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <div>
                        <Label htmlFor="surge-mult">
                          Multiplier (e.g. 1.5 = 50% increase)
                        </Label>
                        <Input
                          id="surge-mult"
                          type="number"
                          step="0.1"
                          min="1"
                          max="5"
                          value={newSurge.surge_multiplier}
                          onChange={(e) =>
                            setNewSurge((prev) => ({
                              ...prev,
                              surge_multiplier: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <div>
                        <Label htmlFor="surge-start">Start Time</Label>
                        <Input
                          id="surge-start"
                          type="time"
                          value={newSurge.start_time}
                          onChange={(e) =>
                            setNewSurge((prev) => ({
                              ...prev,
                              start_time: e.target.value,
                            }))
                          }
                        />
                      </div>
                      <div>
                        <Label htmlFor="surge-end">End Time</Label>
                        <Input
                          id="surge-end"
                          type="time"
                          value={newSurge.end_time}
                          onChange={(e) =>
                            setNewSurge((prev) => ({
                              ...prev,
                              end_time: e.target.value,
                            }))
                          }
                        />
                      </div>
                    </div>

                    {/* Days of Week */}
                    <div className="mb-4">
                      <Label className="mb-2 block">Days of Week</Label>
                      <div className="flex flex-wrap gap-2">
                        {DAYS.map((day) => (
                          <button
                            key={day}
                            onClick={() => toggleSurgeDay(day)}
                            className={`rounded-md border px-3 py-1.5 text-xs font-medium transition-colors ${
                              newSurge.days_of_week.includes(day)
                                ? "border-primary bg-primary text-primary-foreground"
                                : "border-border bg-background text-muted-foreground hover:bg-muted"
                            }`}
                          >
                            {day}
                          </button>
                        ))}
                      </div>
                    </div>

                    {/* Active toggle */}
                    <div className="flex items-center gap-3 mb-4">
                      <Label>Active</Label>
                      <button
                        onClick={() =>
                          setNewSurge((prev) => ({
                            ...prev,
                            is_active: !prev.is_active,
                          }))
                        }
                        className={`relative inline-flex h-6 w-11 items-center rounded-full transition-colors ${
                          newSurge.is_active
                            ? "bg-primary"
                            : "bg-muted-foreground/30"
                        }`}
                      >
                        <span
                          className={`inline-block h-4 w-4 transform rounded-full bg-white transition-transform ${
                            newSurge.is_active
                              ? "translate-x-6"
                              : "translate-x-1"
                          }`}
                        />
                      </button>
                    </div>

                    <Button
                      size="sm"
                      onClick={handleAddSurgeZone}
                      disabled={
                        surgeSaving || !newSurge.name || !newSurge.surge_multiplier
                      }
                    >
                      {surgeSaving ? (
                        <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                      ) : (
                        <Save className="h-4 w-4 mr-1" />
                      )}
                      Save Surge Zone
                    </Button>
                  </div>
                )}

                {/* Surge Zone Cards */}
                {surgeZones.length === 0 ? (
                  <div className="text-center py-8">
                    <p className="text-sm text-muted-foreground">
                      No surge zones configured. Click &quot;Add Surge
                      Zone&quot; to set up time-based pricing.
                    </p>
                  </div>
                ) : (
                  <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
                    {surgeZones.map((zone) => (
                      <div
                        key={zone.id}
                        className="rounded-lg border border-border p-4 hover:shadow-sm transition-shadow"
                      >
                        <div className="flex items-start justify-between mb-2">
                          <h3 className="font-display font-semibold text-sm">
                            {zone.name}
                          </h3>
                          <Badge
                            variant={zone.is_active ? "default" : "secondary"}
                          >
                            {zone.is_active ? "Active" : "Inactive"}
                          </Badge>
                        </div>
                        <p className="text-2xl font-display font-bold text-primary mb-2">
                          {zone.surge_multiplier}x
                        </p>
                        <p className="text-xs text-muted-foreground mb-1">
                          {zone.start_time} &ndash; {zone.end_time}
                        </p>
                        <div className="flex flex-wrap gap-1">
                          {(zone.days_of_week || []).map((day) => (
                            <span
                              key={day}
                              className="rounded bg-muted px-1.5 py-0.5 text-xs text-muted-foreground"
                            >
                              {day}
                            </span>
                          ))}
                        </div>
                      </div>
                    ))}
                  </div>
                )}
              </>
            )}
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Section 3: Platform Fees                                          */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-lg">
              <Percent className="h-5 w-5 text-primary" />
              Platform Fees
            </CardTitle>
            <CardDescription>
              Current platform fee structure. Contact support to modify.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="rounded-md border border-border p-4">
                <p className="text-sm text-muted-foreground">Service Fee</p>
                <p className="text-2xl font-display font-bold mt-1">8%</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Applied to customer total at checkout
                </p>
              </div>
              <div className="rounded-md border border-border p-4">
                <p className="text-sm text-muted-foreground">
                  Platform Commission
                </p>
                <p className="text-2xl font-display font-bold mt-1">20%</p>
                <p className="text-xs text-muted-foreground mt-1">
                  Deducted from contractor payouts
                </p>
              </div>
            </div>
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
