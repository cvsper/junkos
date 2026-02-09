"use client";

import { useEffect, useState, useCallback } from "react";
import { adminApi } from "@/lib/api";
import type { PricingConfigData } from "@/lib/api";
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
  Layers,
  Clock,
  ShieldCheck,
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

/** Volume discount tier for editing */
interface VolumeTier {
  min_qty: number;
  max_qty: number | null;
  discount_rate: number;
}

const DAYS = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];

// Default category prices (matches backend defaults)
const DEFAULT_CATEGORIES: Record<string, Record<string, number>> = {
  furniture: { small: 45, medium: 65, large: 85, default: 65 },
  appliances: { small: 60, medium: 90, large: 120, default: 90 },
  electronics: { small: 25, medium: 35, large: 50, default: 35 },
  yard_waste: { default: 35 },
  construction: { default: 55 },
  general: { default: 30 },
  mattress: { default: 50 },
  hot_tub: { small: 250, medium: 325, large: 400, default: 325 },
  other: { default: 30 },
};

const CATEGORY_LABELS: Record<string, string> = {
  furniture: "Furniture",
  appliances: "Appliances",
  electronics: "Electronics",
  yard_waste: "Yard Waste",
  construction: "Construction Debris",
  general: "General Junk",
  mattress: "Mattress",
  hot_tub: "Hot Tub / Spa",
  other: "Other",
};

const SIZE_LABELS: Record<string, string> = {
  small: "Small",
  medium: "Medium",
  large: "Large",
  default: "Flat Rate",
};

// ---------------------------------------------------------------------------
// Component
// ---------------------------------------------------------------------------

export default function AdminPricingPage() {
  // ---- Pricing Config State ----
  const [configLoading, setConfigLoading] = useState(true);
  const [configError, setConfigError] = useState<string | null>(null);
  const [configSaving, setConfigSaving] = useState(false);
  const [configSaved, setConfigSaved] = useState(false);

  // Editable fields
  const [minimumPrice, setMinimumPrice] = useState(89);
  const [serviceFeeRate, setServiceFeeRate] = useState(0.08);
  const [sameDaySurge, setSameDaySurge] = useState(0.25);
  const [nextDaySurge, setNextDaySurge] = useState(0.10);
  const [weekendSurge, setWeekendSurge] = useState(0.15);
  const [volumeTiers, setVolumeTiers] = useState<VolumeTier[]>([
    { min_qty: 1, max_qty: 3, discount_rate: 0.0 },
    { min_qty: 4, max_qty: 7, discount_rate: 0.10 },
    { min_qty: 8, max_qty: 15, discount_rate: 0.15 },
    { min_qty: 16, max_qty: null, discount_rate: 0.20 },
  ]);
  const [categoryPrices, setCategoryPrices] = useState<
    Record<string, Record<string, number>>
  >(() => JSON.parse(JSON.stringify(DEFAULT_CATEGORIES)));

  // ---- Pricing Rules State (legacy table) ----
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

  // ---- Fetch Pricing Config ----
  const fetchConfig = useCallback(async () => {
    setConfigLoading(true);
    setConfigError(null);
    try {
      const res = await adminApi.getPricingConfig();
      const cfg = (res as { success: boolean; config: PricingConfigData })
        .config;
      if (cfg) {
        setMinimumPrice(cfg.minimum_job_price ?? 89);
        if (cfg.time_surge) {
          setSameDaySurge(cfg.time_surge.same_day ?? 0.25);
          setNextDaySurge(cfg.time_surge.next_day ?? 0.10);
          setWeekendSurge(cfg.time_surge.weekend ?? 0.15);
        }
        if (cfg.commission_rate !== undefined) {
          // commission_rate from backend is actually the service fee rate
          // displayed in the config endpoint
        }
        if (cfg.volume_discount_tiers && cfg.volume_discount_tiers.length > 0) {
          setVolumeTiers(cfg.volume_discount_tiers);
        }
      }
    } catch (err: unknown) {
      setConfigError(
        err instanceof Error ? err.message : "Failed to load pricing config"
      );
    } finally {
      setConfigLoading(false);
    }
  }, []);

  // ---- Fetch Pricing Rules ----
  const fetchRules = useCallback(async () => {
    setRulesLoading(true);
    setRulesError(null);
    try {
      const res = await adminApi.pricingRules();
      const fetched =
        (res as { success: boolean; rules: PricingRule[] }).rules || [];
      setRules(fetched);

      // Merge DB rules into category prices
      const merged = JSON.parse(JSON.stringify(DEFAULT_CATEGORIES)) as Record<
        string,
        Record<string, number>
      >;
      for (const rule of fetched) {
        if (!rule.is_active) continue;
        const key = rule.item_type;
        if (key.includes(":")) {
          const [cat, size] = key.split(":", 2);
          if (merged[cat]) {
            merged[cat][size] = rule.base_price;
          }
        } else {
          if (merged[key]) {
            merged[key]["default"] = rule.base_price;
          }
        }
      }
      setCategoryPrices(merged);
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
    fetchConfig();
    fetchRules();
    fetchSurgeZones();
  }, [fetchConfig, fetchRules, fetchSurgeZones]);

  // ---- Handlers: Pricing Config ----

  const handleSaveConfig = async () => {
    setConfigSaving(true);
    setConfigError(null);
    try {
      await adminApi.updatePricingConfig({
        minimum_job_price: minimumPrice,
        service_fee_rate: serviceFeeRate,
        same_day_surge: sameDaySurge,
        next_day_surge: nextDaySurge,
        weekend_surge: weekendSurge,
        volume_discount_tiers: volumeTiers,
      });
      setConfigSaved(true);
      setTimeout(() => setConfigSaved(false), 3000);
    } catch (err: unknown) {
      setConfigError(
        err instanceof Error ? err.message : "Failed to save pricing config"
      );
    } finally {
      setConfigSaving(false);
    }
  };

  const handleCategoryPriceChange = (
    category: string,
    size: string,
    value: number
  ) => {
    setCategoryPrices((prev) => ({
      ...prev,
      [category]: {
        ...prev[category],
        [size]: value,
      },
    }));
    setRulesSaved(false);
  };

  const handleVolumeTierChange = (
    index: number,
    field: keyof VolumeTier,
    value: number | null
  ) => {
    setVolumeTiers((prev) =>
      prev.map((t, i) => (i === index ? { ...t, [field]: value } : t))
    );
    setConfigSaved(false);
  };

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
      // Build rules from category prices
      const rulesToSave: Partial<PricingRule>[] = [];
      for (const [category, sizes] of Object.entries(categoryPrices)) {
        for (const [size, price] of Object.entries(sizes)) {
          const itemType =
            size === "default" ? category : `${category}:${size}`;
          // Check if there is an existing DB rule
          const existing = rules.find((r) => r.item_type === itemType);
          rulesToSave.push({
            ...(existing ? { id: existing.id } : {}),
            item_type: itemType,
            base_price: price,
            description:
              existing?.description ??
              `${CATEGORY_LABELS[category] || category} (${SIZE_LABELS[size] || size})`,
            is_active: existing?.is_active ?? true,
          });
        }
      }
      await adminApi.updatePricingRules(rulesToSave);
      setRulesSaved(true);
      setTimeout(() => setRulesSaved(false), 3000);
      // Refresh
      await fetchRules();
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
          Pricing Configuration
        </h1>
        <p className="text-muted-foreground mt-1">
          Configure item prices, volume discounts, surge rates, and platform
          fees.
        </p>
      </div>

      <div className="space-y-8">
        {/* ---------------------------------------------------------------- */}
        {/* Section 1: Global Settings (Minimum Price + Service Fee)         */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 font-display text-lg">
                  <ShieldCheck className="h-5 w-5 text-primary" />
                  Global Pricing Settings
                </CardTitle>
                <CardDescription className="mt-1">
                  Minimum job price and platform service fee rate.
                </CardDescription>
              </div>
              <Button
                size="sm"
                onClick={handleSaveConfig}
                disabled={configSaving}
              >
                {configSaving ? (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                ) : configSaved ? (
                  <Check className="h-4 w-4 mr-1" />
                ) : (
                  <Save className="h-4 w-4 mr-1" />
                )}
                {configSaved ? "Saved" : "Save Settings"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {configLoading ? (
              renderLoadingState()
            ) : configError ? (
              renderErrorState(configError, fetchConfig)
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-6">
                <div>
                  <Label htmlFor="min-price">Minimum Job Price</Label>
                  <div className="flex items-center gap-1 mt-1">
                    <span className="text-sm text-muted-foreground">$</span>
                    <Input
                      id="min-price"
                      type="number"
                      step="1"
                      min="0"
                      className="w-32"
                      value={minimumPrice}
                      onChange={(e) =>
                        setMinimumPrice(parseFloat(e.target.value) || 0)
                      }
                    />
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    The floor price for any job, regardless of item count.
                  </p>
                </div>
                <div>
                  <Label htmlFor="service-fee">Service Fee Rate</Label>
                  <div className="flex items-center gap-1 mt-1">
                    <Input
                      id="service-fee"
                      type="number"
                      step="0.01"
                      min="0"
                      max="1"
                      className="w-32"
                      value={serviceFeeRate}
                      onChange={(e) =>
                        setServiceFeeRate(parseFloat(e.target.value) || 0)
                      }
                    />
                    <span className="text-sm text-muted-foreground ml-1">
                      ({(serviceFeeRate * 100).toFixed(0)}%)
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    Applied to the customer total at checkout.
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Section 2: Item Category Prices                                  */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 font-display text-lg">
                  <DollarSign className="h-5 w-5 text-primary" />
                  Item Category Prices
                </CardTitle>
                <CardDescription className="mt-1">
                  Set prices per category and size variant. Changes are saved to
                  the database as pricing rules.
                </CardDescription>
              </div>
              <Button
                size="sm"
                onClick={handleSaveRules}
                disabled={rulesSaving}
              >
                {rulesSaving ? (
                  <Loader2 className="h-4 w-4 mr-1 animate-spin" />
                ) : rulesSaved ? (
                  <Check className="h-4 w-4 mr-1" />
                ) : (
                  <Save className="h-4 w-4 mr-1" />
                )}
                {rulesSaved ? "Saved" : "Save Prices"}
              </Button>
            </div>
          </CardHeader>
          <CardContent>
            {rulesLoading ? (
              renderLoadingState()
            ) : rulesError ? (
              renderErrorState(rulesError, fetchRules)
            ) : (
              <div className="space-y-4">
                {Object.entries(categoryPrices).map(([category, sizes]) => {
                  const sizeEntries = Object.entries(sizes).filter(
                    ([s]) => s !== "default"
                  );
                  const hasDefault = "default" in sizes;
                  const hasSizes = sizeEntries.length > 0;

                  return (
                    <div
                      key={category}
                      className="rounded-lg border border-border p-4"
                    >
                      <div className="flex items-center gap-2 mb-3">
                        <h3 className="font-display font-semibold text-sm">
                          {CATEGORY_LABELS[category] || category}
                        </h3>
                        <Badge variant="outline" className="text-xs">
                          {hasSizes
                            ? `${sizeEntries.length} sizes`
                            : "Flat rate"}
                        </Badge>
                      </div>

                      <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
                        {/* Flat / default price */}
                        {hasDefault && (
                          <div>
                            <Label className="text-xs text-muted-foreground">
                              {hasSizes ? "Default" : "Price"}
                            </Label>
                            <div className="flex items-center gap-1 mt-0.5">
                              <span className="text-xs text-muted-foreground">
                                $
                              </span>
                              <Input
                                type="number"
                                step="1"
                                min="0"
                                className="w-20 h-8 text-sm"
                                value={sizes["default"]}
                                onChange={(e) =>
                                  handleCategoryPriceChange(
                                    category,
                                    "default",
                                    parseFloat(e.target.value) || 0
                                  )
                                }
                              />
                            </div>
                          </div>
                        )}

                        {/* Size variants */}
                        {sizeEntries.map(([size, price]) => (
                          <div key={size}>
                            <Label className="text-xs text-muted-foreground">
                              {SIZE_LABELS[size] || size}
                            </Label>
                            <div className="flex items-center gap-1 mt-0.5">
                              <span className="text-xs text-muted-foreground">
                                $
                              </span>
                              <Input
                                type="number"
                                step="1"
                                min="0"
                                className="w-20 h-8 text-sm"
                                value={price}
                                onChange={(e) =>
                                  handleCategoryPriceChange(
                                    category,
                                    size,
                                    parseFloat(e.target.value) || 0
                                  )
                                }
                              />
                            </div>
                          </div>
                        ))}
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Section 3: Volume Discount Tiers                                 */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 font-display text-lg">
                  <Layers className="h-5 w-5 text-primary" />
                  Volume Discount Tiers
                </CardTitle>
                <CardDescription className="mt-1">
                  Discount percentages applied based on the number of items in a
                  job.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {configLoading ? (
              renderLoadingState()
            ) : (
              <div className="rounded-lg border border-border overflow-hidden">
                <div className="overflow-x-auto">
                  <table className="w-full">
                    <thead>
                      <tr className="border-b border-border bg-muted/50">
                        <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                          Items Range
                        </th>
                        <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                          Min Qty
                        </th>
                        <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                          Max Qty
                        </th>
                        <th className="text-left text-xs font-medium text-muted-foreground uppercase tracking-wider px-4 py-3">
                          Discount Rate
                        </th>
                      </tr>
                    </thead>
                    <tbody>
                      {volumeTiers.map((tier, index) => (
                        <tr
                          key={index}
                          className="border-b border-border last:border-0 hover:bg-muted/30 transition-colors"
                        >
                          <td className="px-4 py-3 text-sm font-medium">
                            {tier.min_qty} &ndash;{" "}
                            {tier.max_qty !== null ? tier.max_qty : "unlimited"}{" "}
                            items
                          </td>
                          <td className="px-4 py-3">
                            <Input
                              type="number"
                              min="1"
                              className="w-20 h-8 text-sm"
                              value={tier.min_qty}
                              onChange={(e) =>
                                handleVolumeTierChange(
                                  index,
                                  "min_qty",
                                  parseInt(e.target.value) || 1
                                )
                              }
                            />
                          </td>
                          <td className="px-4 py-3">
                            <Input
                              type="number"
                              min="1"
                              className="w-20 h-8 text-sm"
                              placeholder="No limit"
                              value={tier.max_qty ?? ""}
                              onChange={(e) =>
                                handleVolumeTierChange(
                                  index,
                                  "max_qty",
                                  e.target.value
                                    ? parseInt(e.target.value)
                                    : null
                                )
                              }
                            />
                          </td>
                          <td className="px-4 py-3">
                            <div className="flex items-center gap-1">
                              <Input
                                type="number"
                                step="0.01"
                                min="0"
                                max="1"
                                className="w-20 h-8 text-sm"
                                value={tier.discount_rate}
                                onChange={(e) =>
                                  handleVolumeTierChange(
                                    index,
                                    "discount_rate",
                                    parseFloat(e.target.value) || 0
                                  )
                                }
                              />
                              <span className="text-sm text-muted-foreground">
                                ({(tier.discount_rate * 100).toFixed(0)}% off)
                              </span>
                            </div>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Section 4: Time-Based Surge Pricing                              */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 font-display text-lg">
                  <Clock className="h-5 w-5 text-primary" />
                  Time-Based Surge Rates
                </CardTitle>
                <CardDescription className="mt-1">
                  Surcharges applied based on scheduling urgency.
                </CardDescription>
              </div>
            </div>
          </CardHeader>
          <CardContent>
            {configLoading ? (
              renderLoadingState()
            ) : (
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                <div className="rounded-lg border border-border p-4">
                  <Label htmlFor="same-day" className="text-sm font-medium">
                    Same-Day Pickup
                  </Label>
                  <div className="flex items-center gap-1 mt-2">
                    <span className="text-sm text-muted-foreground">+</span>
                    <Input
                      id="same-day"
                      type="number"
                      step="0.01"
                      min="0"
                      max="2"
                      className="w-20 h-8 text-sm"
                      value={sameDaySurge}
                      onChange={(e) =>
                        setSameDaySurge(parseFloat(e.target.value) || 0)
                      }
                    />
                    <span className="text-sm text-muted-foreground ml-1">
                      ({(sameDaySurge * 100).toFixed(0)}%)
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Applied when the customer requests same-day service.
                  </p>
                </div>

                <div className="rounded-lg border border-border p-4">
                  <Label htmlFor="next-day" className="text-sm font-medium">
                    Next-Day Pickup
                  </Label>
                  <div className="flex items-center gap-1 mt-2">
                    <span className="text-sm text-muted-foreground">+</span>
                    <Input
                      id="next-day"
                      type="number"
                      step="0.01"
                      min="0"
                      max="2"
                      className="w-20 h-8 text-sm"
                      value={nextDaySurge}
                      onChange={(e) =>
                        setNextDaySurge(parseFloat(e.target.value) || 0)
                      }
                    />
                    <span className="text-sm text-muted-foreground ml-1">
                      ({(nextDaySurge * 100).toFixed(0)}%)
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Applied when the customer requests next-day service.
                  </p>
                </div>

                <div className="rounded-lg border border-border p-4">
                  <Label htmlFor="weekend" className="text-sm font-medium">
                    Weekend Pickup
                  </Label>
                  <div className="flex items-center gap-1 mt-2">
                    <span className="text-sm text-muted-foreground">+</span>
                    <Input
                      id="weekend"
                      type="number"
                      step="0.01"
                      min="0"
                      max="2"
                      className="w-20 h-8 text-sm"
                      value={weekendSurge}
                      onChange={(e) =>
                        setWeekendSurge(parseFloat(e.target.value) || 0)
                      }
                    />
                    <span className="text-sm text-muted-foreground ml-1">
                      ({(weekendSurge * 100).toFixed(0)}%)
                    </span>
                  </div>
                  <p className="text-xs text-muted-foreground mt-2">
                    Applied for Saturday and Sunday pickups.
                  </p>
                </div>
              </div>
            )}
          </CardContent>
        </Card>

        {/* ---------------------------------------------------------------- */}
        {/* Section 5: Custom Pricing Rules (legacy table)                   */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <div className="flex items-center justify-between">
              <div>
                <CardTitle className="flex items-center gap-2 font-display text-lg">
                  <DollarSign className="h-5 w-5 text-primary" />
                  Custom Pricing Rules
                </CardTitle>
                <CardDescription className="mt-1">
                  Additional per-item-type pricing rules stored in the database.
                </CardDescription>
              </div>
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
                    <p className="text-sm font-medium mb-3">
                      New Pricing Rule
                    </p>
                    <div className="grid grid-cols-1 sm:grid-cols-4 gap-3">
                      <div>
                        <Label htmlFor="new-item-type">Item Type</Label>
                        <Input
                          id="new-item-type"
                          placeholder="e.g. piano"
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
                          placeholder="Standard piano removal"
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
                      No custom pricing rules. The category prices above are
                      used by default.
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
        {/* Section 6: Surge Zones                                           */}
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
                        surgeSaving ||
                        !newSurge.name ||
                        !newSurge.surge_multiplier
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
        {/* Section 7: Platform Fees (read-only summary)                     */}
        {/* ---------------------------------------------------------------- */}
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 font-display text-lg">
              <Percent className="h-5 w-5 text-primary" />
              Platform Fees
            </CardTitle>
            <CardDescription>
              Current platform fee structure summary.
            </CardDescription>
          </CardHeader>
          <CardContent>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
              <div className="rounded-md border border-border p-4">
                <p className="text-sm text-muted-foreground">Service Fee</p>
                <p className="text-2xl font-display font-bold mt-1">
                  {(serviceFeeRate * 100).toFixed(0)}%
                </p>
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
