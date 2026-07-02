"use client";

import { useState, useEffect, useCallback } from "react";
import {
  Sofa,
  Refrigerator,
  Monitor,
  HardHat,
  TreePine,
  Trash2,
  Package,
  Minus,
  Plus,
  Sparkles,
  X as XIcon,
  Truck,
  Weight,
  ChevronDown,
  ChevronUp,
  Info,
  DollarSign,
  Shield,
  Heart,
  Recycle,
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useBookingStore } from "@/stores/booking-store";
import { cn } from "@/lib/utils";
import type { JobItem, DispositionPreference } from "@/types";

// ---------------------------------------------------------------------------
// Category definitions with truck space & weight data (1-800-GOT-JUNK model)
// ---------------------------------------------------------------------------

const CATEGORIES = [
  { value: "furniture", label: "Furniture", icon: Sofa },
  { value: "appliances", label: "Appliances", icon: Refrigerator },
  { value: "electronics", label: "Electronics", icon: Monitor },
  { value: "construction", label: "Construction Debris", icon: HardHat },
  { value: "yard_waste", label: "Yard Waste", icon: TreePine },
  { value: "general", label: "General Junk", icon: Trash2 },
  { value: "other", label: "Other", icon: Package },
] as const;

// Common items per category with estimated cubic feet and weight per unit
interface ItemPreset {
  label: string;
  cuFtPerUnit: number;
  lbsPerUnit: number;
}

const ITEM_PRESETS: Record<string, ItemPreset[]> = {
  furniture: [
    { label: "Couch / Sofa", cuFtPerUnit: 40, lbsPerUnit: 150 },
    { label: "Loveseat", cuFtPerUnit: 28, lbsPerUnit: 100 },
    { label: "Recliner / Armchair", cuFtPerUnit: 20, lbsPerUnit: 80 },
    { label: "Mattress (any size)", cuFtPerUnit: 35, lbsPerUnit: 80 },
    { label: "Box Spring", cuFtPerUnit: 30, lbsPerUnit: 60 },
    { label: "Bed Frame", cuFtPerUnit: 15, lbsPerUnit: 50 },
    { label: "Dresser / Chest", cuFtPerUnit: 25, lbsPerUnit: 120 },
    { label: "Desk", cuFtPerUnit: 20, lbsPerUnit: 70 },
    { label: "Dining Table", cuFtPerUnit: 25, lbsPerUnit: 80 },
    { label: "Dining Chairs (set of 4)", cuFtPerUnit: 16, lbsPerUnit: 40 },
    { label: "Bookshelf", cuFtPerUnit: 18, lbsPerUnit: 60 },
    { label: "Other Furniture", cuFtPerUnit: 20, lbsPerUnit: 70 },
  ],
  appliances: [
    { label: "Refrigerator", cuFtPerUnit: 35, lbsPerUnit: 200 },
    { label: "Washer", cuFtPerUnit: 20, lbsPerUnit: 175 },
    { label: "Dryer", cuFtPerUnit: 20, lbsPerUnit: 125 },
    { label: "Dishwasher", cuFtPerUnit: 15, lbsPerUnit: 100 },
    { label: "Oven / Stove", cuFtPerUnit: 20, lbsPerUnit: 150 },
    { label: "Microwave", cuFtPerUnit: 4, lbsPerUnit: 35 },
    { label: "Water Heater", cuFtPerUnit: 15, lbsPerUnit: 120 },
    { label: "AC Unit (window)", cuFtPerUnit: 6, lbsPerUnit: 60 },
    { label: "Other Appliance", cuFtPerUnit: 15, lbsPerUnit: 100 },
  ],
  electronics: [
    { label: "TV (flat screen)", cuFtPerUnit: 8, lbsPerUnit: 30 },
    { label: "TV (CRT / tube)", cuFtPerUnit: 12, lbsPerUnit: 80 },
    { label: "Computer / Desktop", cuFtPerUnit: 4, lbsPerUnit: 25 },
    { label: "Monitor", cuFtPerUnit: 4, lbsPerUnit: 15 },
    { label: "Printer / Scanner", cuFtPerUnit: 4, lbsPerUnit: 30 },
    { label: "Other Electronics", cuFtPerUnit: 4, lbsPerUnit: 20 },
  ],
  construction: [
    { label: "Drywall / Sheetrock", cuFtPerUnit: 10, lbsPerUnit: 80 },
    { label: "Lumber / Wood", cuFtPerUnit: 10, lbsPerUnit: 60 },
    { label: "Carpet / Flooring", cuFtPerUnit: 15, lbsPerUnit: 100 },
    { label: "Cabinets", cuFtPerUnit: 20, lbsPerUnit: 80 },
    { label: "Concrete / Brick", cuFtPerUnit: 5, lbsPerUnit: 200 },
    { label: "Roofing Materials", cuFtPerUnit: 10, lbsPerUnit: 90 },
    { label: "Mixed Debris (bags/pile)", cuFtPerUnit: 8, lbsPerUnit: 50 },
    { label: "Other Construction", cuFtPerUnit: 10, lbsPerUnit: 70 },
  ],
  yard_waste: [
    { label: "Tree Branches / Limbs", cuFtPerUnit: 15, lbsPerUnit: 40 },
    { label: "Bagged Leaves / Clippings", cuFtPerUnit: 5, lbsPerUnit: 30 },
    { label: "Soil / Dirt (bags)", cuFtPerUnit: 3, lbsPerUnit: 50 },
    { label: "Sod / Turf", cuFtPerUnit: 5, lbsPerUnit: 60 },
    { label: "Fence Sections", cuFtPerUnit: 10, lbsPerUnit: 40 },
    { label: "Hot Tub / Spa", cuFtPerUnit: 60, lbsPerUnit: 500 },
    { label: "Other Yard Waste", cuFtPerUnit: 8, lbsPerUnit: 35 },
  ],
  general: [
    { label: "Bags of Junk", cuFtPerUnit: 4, lbsPerUnit: 25 },
    { label: "Boxes (moving boxes)", cuFtPerUnit: 4, lbsPerUnit: 30 },
    { label: "Exercise Equipment", cuFtPerUnit: 15, lbsPerUnit: 100 },
    { label: "Toys / Kids Items", cuFtPerUnit: 6, lbsPerUnit: 20 },
    { label: "Clothing / Textiles", cuFtPerUnit: 4, lbsPerUnit: 15 },
    { label: "Misc Household Items", cuFtPerUnit: 5, lbsPerUnit: 25 },
  ],
  other: [
    { label: "Tires", cuFtPerUnit: 6, lbsPerUnit: 25 },
    { label: "Piano", cuFtPerUnit: 40, lbsPerUnit: 500 },
    { label: "Pool Table", cuFtPerUnit: 50, lbsPerUnit: 400 },
    { label: "Custom / Unlisted Item", cuFtPerUnit: 10, lbsPerUnit: 50 },
  ],
};

// Truck load thresholds based on 1-800-GOT-JUNK sizing (full truck = ~450 cu ft)
// Preview-only: the binding quote comes from the backend estimate. Floor must
// not undercut MINIMUM_JOB_PRICE ($119, 2026-07-02 re-tier) or step 5 reads
// as a bait-and-switch.
const TRUCK_LOADS = [
  { label: "1/8 Truck", fraction: 0.125, maxCuFt: 56, price: 119 },
  { label: "1/4 Truck", fraction: 0.25, maxCuFt: 112, price: 179 },
  { label: "1/2 Truck", fraction: 0.5, maxCuFt: 225, price: 279 },
  { label: "3/4 Truck", fraction: 0.75, maxCuFt: 337, price: 429 },
  { label: "Full Truck", fraction: 1.0, maxCuFt: 450, price: 599 },
];

function getTruckLoad(totalCuFt: number) {
  for (const load of TRUCK_LOADS) {
    if (totalCuFt <= load.maxCuFt) return load;
  }
  return TRUCK_LOADS[TRUCK_LOADS.length - 1];
}

/** Returns the price range bracket — current load price as low, next tier as high */
function getPriceRange(totalCuFt: number): { low: number; high: number; label: string } {
  const currentLoad = getTruckLoad(totalCuFt);
  const currentIdx = TRUCK_LOADS.indexOf(currentLoad);
  const nextLoad = TRUCK_LOADS[Math.min(currentIdx + 1, TRUCK_LOADS.length - 1)];

  if (totalCuFt === 0) {
    return { low: 119, high: 179, label: "1/8 – 1/4 Truck" };
  }
  if (currentIdx === TRUCK_LOADS.length - 1) {
    // Already at full truck
    return { low: currentLoad.price, high: currentLoad.price, label: currentLoad.label };
  }
  return {
    low: currentLoad.price,
    high: nextLoad.price,
    label: `${currentLoad.label} – ${nextLoad.label}`,
  };
}

const MAX_DESCRIPTION = 500;

// ---------------------------------------------------------------------------
// Disposition preference (Rescue Engine v1) — how the customer wants items
// handled after pickup. Copy is intentionally aspirational, never a promise:
// every option is a best-effort estimate, and no charity is named.
// ---------------------------------------------------------------------------

const DISPOSITION_OPTIONS: {
  value: DispositionPreference;
  label: string;
  description: string;
  icon: typeof Sparkles;
}[] = [
  {
    value: "best",
    label: "Let Umuve decide",
    description: "We'll aim for the most responsible option for each item.",
    icon: Sparkles,
  },
  {
    value: "donate",
    label: "Donate if usable",
    description:
      "Whenever possible, reusable items may be routed toward donation or reuse partners.",
    icon: Heart,
  },
  {
    value: "recycle",
    label: "Recycle",
    description: "We'll route recyclable materials to recycling where available.",
    icon: Recycle,
  },
  {
    value: "dispose",
    label: "Dispose",
    description: "Standard responsible disposal.",
    icon: Trash2,
  },
];

// ---------------------------------------------------------------------------
// Item row component
// ---------------------------------------------------------------------------

interface ItemRowProps {
  item: JobItem & { preset?: string };
  presets: ItemPreset[];
  onUpdate: (id: string, updates: Partial<JobItem & { preset: string }>) => void;
  onRemove: (id: string) => void;
}

function ItemRow({ item, presets, onUpdate, onRemove }: ItemRowProps) {
  const preset = presets.find((p) => p.label === item.name);
  const cuFt = (preset?.cuFtPerUnit ?? 10) * item.quantity;
  const lbs = (preset?.lbsPerUnit ?? 50) * item.quantity;

  return (
    <div className="flex items-center gap-3 rounded-lg border border-border bg-background p-3">
      <div className="flex-1 min-w-0 space-y-2">
        <select
          value={item.name}
          onChange={(e) => onUpdate(item.id, { name: e.target.value })}
          className="w-full rounded-md border border-input bg-background px-3 py-1.5 text-sm focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">Select item...</option>
          {presets.map((p) => (
            <option key={p.label} value={p.label}>
              {p.label}
            </option>
          ))}
        </select>
        <div className="flex items-center gap-4 text-xs text-muted-foreground">
          <span className="flex items-center gap-1">
            <Truck className="h-3 w-3" />
            ~{cuFt} cu ft
          </span>
          <span className="flex items-center gap-1">
            <Weight className="h-3 w-3" />
            ~{lbs} lbs
          </span>
        </div>
      </div>

      {/* Quantity */}
      <div className="flex items-center gap-1.5 shrink-0">
        <button
          type="button"
          onClick={() => onUpdate(item.id, { quantity: Math.max(1, item.quantity - 1) })}
          disabled={item.quantity <= 1}
          className="h-7 w-7 rounded border border-input flex items-center justify-center text-muted-foreground hover:bg-muted disabled:opacity-40"
        >
          <Minus className="h-3 w-3" />
        </button>
        <span className="w-6 text-center text-sm font-semibold tabular-nums">
          {item.quantity}
        </span>
        <button
          type="button"
          onClick={() => onUpdate(item.id, { quantity: Math.min(20, item.quantity + 1) })}
          disabled={item.quantity >= 20}
          className="h-7 w-7 rounded border border-input flex items-center justify-center text-muted-foreground hover:bg-muted disabled:opacity-40"
        >
          <Plus className="h-3 w-3" />
        </button>
      </div>

      {/* Remove */}
      <button
        type="button"
        onClick={() => onRemove(item.id)}
        className="h-7 w-7 rounded flex items-center justify-center text-muted-foreground hover:text-destructive hover:bg-destructive/10 transition-colors shrink-0"
        aria-label="Remove item"
      >
        <XIcon className="h-4 w-4" />
      </button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Truck fill visualization
// ---------------------------------------------------------------------------

function TruckFillBar({ totalCuFt }: { totalCuFt: number }) {
  const maxCuFt = 450;
  const pct = Math.min((totalCuFt / maxCuFt) * 100, 100);
  const load = getTruckLoad(totalCuFt);

  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between text-sm">
        <span className="font-medium text-foreground flex items-center gap-2">
          <Truck className="h-4 w-4" />
          Estimated Truck Space
        </span>
        <span className="font-semibold text-primary">
          {load.label} (${load.price})
        </span>
      </div>
      <div className="relative h-6 rounded-full bg-muted overflow-hidden">
        <div
          className={cn(
            "absolute inset-y-0 left-0 rounded-full transition-all duration-500 ease-out",
            pct <= 25
              ? "bg-green-500"
              : pct <= 50
                ? "bg-yellow-500"
                : pct <= 75
                  ? "bg-orange-500"
                  : "bg-red-500"
          )}
          style={{ width: `${pct}%` }}
        />
        {/* Tick marks for truck fractions */}
        {[0.125, 0.25, 0.5, 0.75].map((frac) => (
          <div
            key={frac}
            className="absolute top-0 bottom-0 w-px bg-foreground/20"
            style={{ left: `${frac * 100}%` }}
          />
        ))}
      </div>
      <div className="flex justify-between text-[10px] text-muted-foreground">
        <span>1/8</span>
        <span>1/4</span>
        <span>1/2</span>
        <span>3/4</span>
        <span>Full</span>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Main Step 3 component
// ---------------------------------------------------------------------------

export function Step3Items() {
  const {
    items,
    setItems,
    aiAnalysis,
    notes,
    setNotes,
    dispositionPreference,
    setDispositionPreference,
  } = useBookingStore();

  const [selectedCategories, setSelectedCategories] = useState<string[]>(() => {
    // Initialize from existing items
    const cats = Array.from(new Set(items.map((i) => i.category).filter(Boolean)));
    return cats.length > 0 ? cats : [];
  });

  const [itemsByCategory, setItemsByCategory] = useState<Record<string, (JobItem & { preset?: string })[]>>(() => {
    // Group existing items by category
    const grouped: Record<string, (JobItem & { preset?: string })[]> = {};
    items.forEach((item) => {
      if (!grouped[item.category]) grouped[item.category] = [];
      grouped[item.category].push(item);
    });
    return grouped;
  });

  const [description, setDescription] = useState(() => {
    // Prefer notes already in the store (e.g. a resumed booking)
    if (notes) return notes;
    // Use the first item's name as description if it doesn't match a preset
    return items[0]?.name && !Object.values(ITEM_PRESETS).flat().some((p) => p.label === items[0]?.name)
      ? items[0].name
      : "";
  });

  const [errors, setErrors] = useState<{ categories?: string; items?: string; description?: string }>({});
  const [aiDismissed, setAiDismissed] = useState(false);
  const [expandedCategory, setExpandedCategory] = useState<string | null>(null);

  // Pre-fill from AI analysis
  useEffect(() => {
    if (aiAnalysis && !aiDismissed && selectedCategories.length === 0 && items.length === 0) {
      const cats = Array.from(new Set(aiAnalysis.items.map((i) => i.category)));
      setSelectedCategories(cats);
      if (aiAnalysis.notes) setDescription(aiAnalysis.notes);

      const grouped: Record<string, (JobItem & { preset?: string })[]> = {};
      aiAnalysis.items.forEach((ai, idx) => {
        if (!grouped[ai.category]) grouped[ai.category] = [];
        // Try to match AI description to a preset label for accurate estimates
        const catPresets = ITEM_PRESETS[ai.category] || ITEM_PRESETS.other;
        const desc = (ai.description || "").toLowerCase();
        const matchedPreset = catPresets.find((p) =>
          desc.includes(p.label.toLowerCase().split(" ")[0]) ||
          p.label.toLowerCase().includes(desc.split(" ")[0])
        );
        grouped[ai.category].push({
          id: `ai-${idx}`,
          name: matchedPreset?.label || ai.description || catPresets[catPresets.length - 1].label,
          category: ai.category,
          quantity: ai.quantity,
        });
      });
      setItemsByCategory(grouped);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [aiAnalysis, aiDismissed]);

  // Toggle category selection
  const toggleCategory = useCallback((cat: string) => {
    setSelectedCategories((prev) => {
      if (prev.includes(cat)) {
        // Removing category — also clean up its items
        setItemsByCategory((prevItems) => {
          const next = { ...prevItems };
          delete next[cat];
          return next;
        });
        return prev.filter((c) => c !== cat);
      }
      // Adding category — auto-expand and add a default item
      setExpandedCategory(cat);
      const presets = ITEM_PRESETS[cat] || ITEM_PRESETS.other;
      setItemsByCategory((prevItems) => ({
        ...prevItems,
        [cat]: prevItems[cat]?.length
          ? prevItems[cat]
          : [
              {
                id: `item-${Date.now()}`,
                name: presets[0].label,
                category: cat,
                quantity: 1,
              },
            ],
      }));
      return [...prev, cat];
    });
    if (errors.categories) setErrors((prev) => ({ ...prev, categories: undefined }));
  }, [errors.categories]);

  // Add item to a category
  const addItemToCategory = useCallback((cat: string) => {
    const presets = ITEM_PRESETS[cat] || ITEM_PRESETS.other;
    setItemsByCategory((prev) => ({
      ...prev,
      [cat]: [
        ...(prev[cat] || []),
        {
          id: `item-${Date.now()}-${Math.random().toString(36).slice(2, 6)}`,
          name: presets[0].label,
          category: cat,
          quantity: 1,
        },
      ],
    }));
  }, []);

  // Update an item
  const updateItem = useCallback((cat: string, id: string, updates: Partial<JobItem>) => {
    setItemsByCategory((prev) => ({
      ...prev,
      [cat]: (prev[cat] || []).map((item) =>
        item.id === id ? { ...item, ...updates } : item
      ),
    }));
  }, []);

  // Remove an item
  const removeItem = useCallback((cat: string, id: string) => {
    setItemsByCategory((prev) => ({
      ...prev,
      [cat]: (prev[cat] || []).filter((item) => item.id !== id),
    }));
  }, []);

  // Compute totals
  const allItems = Object.entries(itemsByCategory).flatMap(([cat, catItems]) =>
    catItems.map((item) => {
      const presets = ITEM_PRESETS[cat] || ITEM_PRESETS.other;
      const preset = presets.find((p) => p.label === item.name);
      return {
        ...item,
        category: cat,
        estimatedCuFt: (preset?.cuFtPerUnit ?? 10) * item.quantity,
        estimatedWeight: (preset?.lbsPerUnit ?? 50) * item.quantity,
      };
    })
  );

  const totalCuFt = allItems.reduce((sum, i) => sum + (i.estimatedCuFt || 0), 0);
  const totalWeight = allItems.reduce((sum, i) => sum + (i.estimatedWeight || 0), 0);
  const priceRange = getPriceRange(totalCuFt);

  // Sync to store
  useEffect(() => {
    if (selectedCategories.length > 0 && allItems.length > 0) {
      setItems(
        allItems.map((item) => ({
          id: item.id,
          name: item.name,
          category: item.category,
          quantity: item.quantity,
          estimatedCuFt: item.estimatedCuFt,
          estimatedWeight: item.estimatedWeight,
        }))
      );
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [itemsByCategory, selectedCategories, setItems]);

  // Sync notes to the store so they reach the submit payload
  useEffect(() => {
    setNotes(description);
  }, [description, setNotes]);

  // Validation
  const validate = (): boolean => {
    const newErrors: typeof errors = {};

    if (selectedCategories.length === 0) {
      newErrors.categories = "Please select at least one category.";
    }

    const hasItems = Object.values(itemsByCategory).some((catItems) =>
      catItems.some((item) => item.name)
    );
    if (!hasItems) {
      newErrors.items = "Please add at least one item.";
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  Step3Items.validate = validate;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="font-display text-2xl font-bold tracking-tight text-foreground">
          What are we removing?
        </h2>
        <p className="mt-1 text-muted-foreground">
          Select categories and tell us what items you need hauled away.
        </p>
      </div>

      {/* AI-detected items banner */}
      {aiAnalysis && !aiDismissed && (
        <div className="flex items-center justify-between rounded-lg border border-primary/20 bg-primary/5 p-3">
          <div className="flex items-center gap-2">
            <Sparkles className="h-4 w-4 text-primary shrink-0" />
            <p className="text-sm text-primary font-medium">
              Items detected from your photos
            </p>
          </div>
          <button
            type="button"
            onClick={() => setAiDismissed(true)}
            className="text-primary/60 hover:text-primary"
            aria-label="Dismiss AI suggestions"
          >
            <XIcon className="h-4 w-4" />
          </button>
        </div>
      )}

      {/* Category Selection — Multi-select */}
      <div className="space-y-3">
        <Label className="text-sm font-medium">
          Categories <span className="text-muted-foreground font-normal">(select all that apply)</span>
        </Label>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {CATEGORIES.map((cat) => {
            const Icon = cat.icon;
            const isSelected = selectedCategories.includes(cat.value);
            const itemCount = (itemsByCategory[cat.value] || []).length;
            return (
              <button
                key={cat.value}
                type="button"
                onClick={() => toggleCategory(cat.value)}
                className={cn(
                  "relative flex flex-col items-center gap-2 rounded-lg border-2 p-4 transition-all text-center",
                  isSelected
                    ? "border-primary bg-primary/5 text-primary"
                    : "border-border bg-card text-muted-foreground hover:border-primary/30 hover:bg-muted/50"
                )}
              >
                <Icon className="h-6 w-6" />
                <span className="text-xs font-medium">{cat.label}</span>
                {isSelected && itemCount > 0 && (
                  <span className="absolute -top-2 -right-2 h-5 w-5 rounded-full bg-primary text-[10px] font-bold text-primary-foreground flex items-center justify-center">
                    {itemCount}
                  </span>
                )}
              </button>
            );
          })}
        </div>
        <div aria-live="polite" aria-atomic="true">
          {errors.categories && (
            <p role="alert" className="text-sm text-destructive font-medium">
              {errors.categories}
            </p>
          )}
        </div>
      </div>

      {/* Items per selected category */}
      {selectedCategories.length > 0 && (
        <div className="space-y-4">
          {selectedCategories.map((cat) => {
            const catDef = CATEGORIES.find((c) => c.value === cat);
            const catItems = itemsByCategory[cat] || [];
            const presets = ITEM_PRESETS[cat] || ITEM_PRESETS.other;
            const isExpanded = expandedCategory === cat;
            const CatIcon = catDef?.icon || Package;

            return (
              <div key={cat} className="rounded-lg border border-border overflow-hidden">
                <button
                  type="button"
                  onClick={() => setExpandedCategory(isExpanded ? null : cat)}
                  className="w-full flex items-center justify-between px-4 py-3 bg-muted/30 hover:bg-muted/50 transition-colors"
                >
                  <div className="flex items-center gap-2">
                    <CatIcon className="h-4 w-4 text-primary" />
                    <span className="text-sm font-semibold text-foreground">
                      {catDef?.label || cat}
                    </span>
                    <span className="text-xs text-muted-foreground">
                      ({catItems.length} item{catItems.length !== 1 ? "s" : ""})
                    </span>
                  </div>
                  {isExpanded ? (
                    <ChevronUp className="h-4 w-4 text-muted-foreground" />
                  ) : (
                    <ChevronDown className="h-4 w-4 text-muted-foreground" />
                  )}
                </button>

                {isExpanded && (
                  <div className="p-4 space-y-3">
                    {catItems.map((item) => (
                      <ItemRow
                        key={item.id}
                        item={item}
                        presets={presets}
                        onUpdate={(id, updates) => updateItem(cat, id, updates)}
                        onRemove={(id) => removeItem(cat, id)}
                      />
                    ))}
                    <Button
                      type="button"
                      variant="outline"
                      size="sm"
                      onClick={() => addItemToCategory(cat)}
                      className="w-full gap-1.5"
                    >
                      <Plus className="h-3.5 w-3.5" />
                      Add Another {catDef?.label || "Item"}
                    </Button>
                  </div>
                )}
              </div>
            );
          })}

          <div aria-live="polite" aria-atomic="true">
            {errors.items && (
              <p role="alert" className="text-sm text-destructive font-medium">
                {errors.items}
              </p>
            )}
          </div>
        </div>
      )}

      {/* Live Price Ticker + Truck Fill */}
      {allItems.length > 0 && totalCuFt > 0 && (
        <>
          {/* Sticky Price Ticker */}
          <div className="sticky bottom-0 z-10 -mx-6 sm:-mx-8 px-6 sm:px-8 py-3 bg-gradient-to-t from-card via-card to-card/95 border-t border-border">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <div className="flex h-8 w-8 items-center justify-center rounded-full bg-primary/10">
                  <DollarSign className="h-4 w-4 text-primary" />
                </div>
                <div>
                  <p className="text-xs text-muted-foreground">Estimated Price Range</p>
                  <p className="text-lg font-bold text-foreground tabular-nums">
                    {priceRange.low === priceRange.high ? (
                      <>${priceRange.low}</>
                    ) : (
                      <>${priceRange.low} – ${priceRange.high}</>
                    )}
                  </p>
                </div>
              </div>
              <div className="text-right">
                <p className="text-xs text-muted-foreground">{priceRange.label}</p>
                <div className="flex items-center gap-1 text-xs text-green-600">
                  <Shield className="h-3 w-3" />
                  <span className="font-medium">No hidden fees</span>
                </div>
              </div>
            </div>
          </div>

          {/* Truck Fill Visualization + Weight Summary */}
          <div className="rounded-lg border border-border bg-card p-5 space-y-4">
            <TruckFillBar totalCuFt={totalCuFt} />

            <div className="grid grid-cols-3 gap-3">
              <div className="rounded-lg bg-muted/50 p-3 text-center">
                <p className="text-lg font-bold text-foreground">{totalCuFt}</p>
                <p className="text-xs text-muted-foreground">cu ft</p>
              </div>
              <div className="rounded-lg bg-muted/50 p-3 text-center">
                <p className="text-lg font-bold text-foreground">{totalWeight}</p>
                <p className="text-xs text-muted-foreground">lbs</p>
              </div>
              <div className="rounded-lg bg-primary/5 border border-primary/20 p-3 text-center">
                <p className="text-lg font-bold text-primary">
                  ${priceRange.low}{priceRange.low !== priceRange.high && <>–${priceRange.high}</>}
                </p>
                <p className="text-xs text-muted-foreground">est. price</p>
              </div>
            </div>

            <div className="flex items-start gap-2 text-xs text-muted-foreground">
              <Info className="h-3.5 w-3.5 shrink-0 mt-0.5" />
              <span>
                Price based on truck space used — not by item count. Final price confirmed before we start, never higher than the high estimate.
              </span>
            </div>
          </div>
        </>
      )}

      {/* Additional Notes */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label htmlFor="description" className="text-sm font-medium">
            Additional Notes <span className="text-muted-foreground font-normal">(optional)</span>
          </Label>
          <span
            className={cn(
              "text-xs",
              description.length > MAX_DESCRIPTION
                ? "text-destructive"
                : "text-muted-foreground"
            )}
          >
            {description.length}/{MAX_DESCRIPTION}
          </span>
        </div>
        <textarea
          id="description"
          placeholder="Anything else we should know? (e.g., items are on 2nd floor, narrow hallway, heavy items need 2 people...)"
          value={description}
          onChange={(e) => {
            setDescription(e.target.value);
            if (errors.description) {
              setErrors((prev) => ({ ...prev, description: undefined }));
            }
          }}
          rows={3}
          maxLength={MAX_DESCRIPTION}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-none"
        />
      </div>

      {/* Disposition preference — Rescue Engine v1 */}
      <div className="space-y-3">
        <div>
          <Label className="text-sm font-medium">
            What should happen to your items?
          </Label>
          <p className="mt-1 text-xs text-muted-foreground">
            Tell us your preference — we&apos;ll aim for it wherever it&apos;s practical.
          </p>
        </div>
        <div
          role="radiogroup"
          aria-label="What should happen to your items?"
          className="grid grid-cols-1 sm:grid-cols-2 gap-3"
        >
          {DISPOSITION_OPTIONS.map((opt) => {
            const Icon = opt.icon;
            const isSelected = dispositionPreference === opt.value;
            return (
              <button
                key={opt.value}
                type="button"
                role="radio"
                aria-checked={isSelected}
                onClick={() => setDispositionPreference(opt.value)}
                className={cn(
                  "flex items-start gap-3 rounded-lg border-2 p-3 text-left transition-all",
                  isSelected
                    ? "border-primary bg-primary/5"
                    : "border-border bg-card hover:border-primary/30 hover:bg-muted/50"
                )}
              >
                <span
                  className={cn(
                    "flex h-8 w-8 shrink-0 items-center justify-center rounded-full",
                    isSelected
                      ? "bg-primary/10 text-primary"
                      : "bg-muted text-muted-foreground"
                  )}
                >
                  <Icon className="h-4 w-4" />
                </span>
                <span className="min-w-0">
                  <span
                    className={cn(
                      "block text-sm font-semibold",
                      isSelected ? "text-primary" : "text-foreground"
                    )}
                  >
                    {opt.label}
                  </span>
                  <span className="mt-0.5 block text-xs text-muted-foreground leading-snug">
                    {opt.description}
                  </span>
                </span>
              </button>
            );
          })}
        </div>
      </div>
    </div>
  );
}

// Static validation fallback
Step3Items.validate = (): boolean => {
  const { items } = useBookingStore.getState();
  return items.length > 0 && items.some((item) => !!item.category && !!item.name);
};
