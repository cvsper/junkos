"use client";

import { useState, useEffect } from "react";
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
} from "lucide-react";
import { Button } from "@/components/ui/button";
import { Label } from "@/components/ui/label";
import { useBookingStore } from "@/stores/booking-store";
import { cn } from "@/lib/utils";

const CATEGORIES = [
  { value: "furniture", label: "Furniture", icon: Sofa },
  { value: "appliances", label: "Appliances", icon: Refrigerator },
  { value: "electronics", label: "Electronics", icon: Monitor },
  { value: "construction", label: "Construction Debris", icon: HardHat },
  { value: "yard_waste", label: "Yard Waste", icon: TreePine },
  { value: "general", label: "General Junk", icon: Trash2 },
  { value: "other", label: "Other", icon: Package },
] as const;

const MAX_DESCRIPTION = 500;

export function Step3Items() {
  const { items, setItems } = useBookingStore();

  // Initialize from store if there's an existing item
  const existingItem = items[0];
  const [selectedCategory, setSelectedCategory] = useState(
    existingItem?.category || ""
  );
  const [description, setDescription] = useState(
    existingItem?.name || ""
  );
  const [quantity, setQuantity] = useState(existingItem?.quantity || 1);
  const [errors, setErrors] = useState<{ category?: string; description?: string }>({});

  // Sync to store on changes
  useEffect(() => {
    if (selectedCategory && description.trim().length >= 10) {
      setItems([
        {
          id: existingItem?.id || "item-1",
          name: description.trim(),
          category: selectedCategory,
          quantity,
        },
      ]);
    }
  }, [selectedCategory, description, quantity, setItems, existingItem?.id]);

  const validate = (): boolean => {
    const newErrors: { category?: string; description?: string } = {};

    if (!selectedCategory) {
      newErrors.category = "Please select a category.";
    }

    const trimmedDesc = description.trim();
    if (trimmedDesc.length < 10) {
      newErrors.description =
        "Please provide a description (at least 10 characters).";
    } else if (trimmedDesc.length > MAX_DESCRIPTION) {
      newErrors.description = `Description must be under ${MAX_DESCRIPTION} characters.`;
    }

    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  // Expose validation
  Step3Items.validate = validate;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h2 className="font-display text-2xl font-bold tracking-tight text-foreground">
          What are we removing?
        </h2>
        <p className="mt-1 text-muted-foreground">
          Select a category and describe the items for your junk removal.
        </p>
      </div>

      {/* Category Selection */}
      <div className="space-y-3">
        <Label className="text-sm font-medium">Category</Label>
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3">
          {CATEGORIES.map((cat) => {
            const Icon = cat.icon;
            const isSelected = selectedCategory === cat.value;
            return (
              <button
                key={cat.value}
                type="button"
                onClick={() => {
                  setSelectedCategory(cat.value);
                  if (errors.category) {
                    setErrors((prev) => ({ ...prev, category: undefined }));
                  }
                }}
                className={cn(
                  "flex flex-col items-center gap-2 rounded-lg border-2 p-4 transition-all text-center",
                  isSelected
                    ? "border-primary bg-primary/5 text-primary"
                    : "border-border bg-card text-muted-foreground hover:border-primary/30 hover:bg-muted/50"
                )}
              >
                <Icon className="h-6 w-6" />
                <span className="text-xs font-medium">{cat.label}</span>
              </button>
            );
          })}
        </div>
        {errors.category && (
          <p className="text-sm text-destructive font-medium">
            {errors.category}
          </p>
        )}
      </div>

      {/* Description */}
      <div className="space-y-3">
        <div className="flex items-center justify-between">
          <Label htmlFor="description" className="text-sm font-medium">
            Description
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
          placeholder="Describe the items you need removed (e.g., old couch, broken refrigerator, pile of yard debris)..."
          value={description}
          onChange={(e) => {
            setDescription(e.target.value);
            if (errors.description) {
              setErrors((prev) => ({ ...prev, description: undefined }));
            }
          }}
          rows={4}
          maxLength={MAX_DESCRIPTION}
          className="flex w-full rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background placeholder:text-muted-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50 resize-none"
        />
        {errors.description && (
          <p className="text-sm text-destructive font-medium">
            {errors.description}
          </p>
        )}
      </div>

      {/* Quantity Selector */}
      <div className="space-y-3">
        <Label className="text-sm font-medium">
          Estimated Number of Items
        </Label>
        <div className="flex items-center gap-4">
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={() => setQuantity((q) => Math.max(1, q - 1))}
            disabled={quantity <= 1}
            aria-label="Decrease quantity"
          >
            <Minus className="h-4 w-4" />
          </Button>
          <span className="text-2xl font-bold text-foreground tabular-nums w-12 text-center">
            {quantity}
          </span>
          <Button
            type="button"
            variant="outline"
            size="icon"
            onClick={() => setQuantity((q) => Math.min(20, q + 1))}
            disabled={quantity >= 20}
            aria-label="Increase quantity"
          >
            <Plus className="h-4 w-4" />
          </Button>
          <span className="text-sm text-muted-foreground">
            item{quantity !== 1 ? "s" : ""}
          </span>
        </div>
      </div>
    </div>
  );
}

// Static validation reference (overwritten on render)
Step3Items.validate = (): boolean => {
  const { items } = useBookingStore.getState();
  const item = items[0];
  if (!item) return false;
  return (
    !!item.category &&
    item.name.trim().length >= 10 &&
    item.name.trim().length <= 500
  );
};
