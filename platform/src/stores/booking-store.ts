import { create } from "zustand";
import type { Address, JobItem, DispositionPreference } from "@/types";

interface BookingState {
  // Form state
  step: number;
  address: Partial<Address>;
  photos: File[];
  photoPreviewUrls: string[];
  items: JobItem[];
  scheduledDate: string;
  scheduledTimeSlot: string;
  notes: string;
  dispositionPreference: DispositionPreference;
  estimatedPrice: number;
  /**
   * Server-issued price version from /api/booking/estimate (audit F09).
   * Null whenever any price input changed since the last estimate — the
   * booking cannot be submitted until a fresh estimate re-issues it.
   */
  priceVersion: string | null;
  quoteId: string | null;
  quoteBinding: boolean;
  /** Claim token for an anonymous photo quote (issued once at creation). */
  quoteToken: string | null;
  isSubmitting: boolean;
  leadSource: string;

  // Promo code state
  promoCode: string;
  promoDiscount: number;
  promoApplied: boolean;

  // AI analysis state
  aiAnalysis: {
    items: Array<{category: string; size: string; quantity: number; description: string}>;
    estimatedVolume: number;
    truckSize: string;
    confidence: number;
    notes: string;
  } | null;
  aiAnalyzing: boolean;

  // Navigation actions
  setStep: (step: number) => void;
  nextStep: () => void;
  prevStep: () => void;

  // Address actions
  setAddress: (address: Partial<Address>) => void;

  // Photo actions
  addPhotos: (files: File[]) => void;
  removePhoto: (index: number) => void;

  // Item actions
  setItems: (items: JobItem[]) => void;
  addItem: (item: JobItem) => void;
  removeItem: (id: string) => void;

  // Schedule actions
  setSchedule: (date: string, timeSlot: string) => void;

  // Misc actions
  setNotes: (notes: string) => void;
  setDispositionPreference: (preference: DispositionPreference) => void;
  setEstimatedPrice: (price: number) => void;
  setPriceVersion: (priceVersion: string | null) => void;
  setQuoteId: (quoteId: string | null) => void;
  setQuoteBinding: (quoteBinding: boolean) => void;
  setQuoteToken: (quoteToken: string | null) => void;
  clearQuote: () => void;
  setIsSubmitting: (isSubmitting: boolean) => void;
  setLeadSource: (leadSource: string) => void;

  // Promo code actions
  setPromoCode: (code: string) => void;
  applyPromo: (code: string, discount: number, priceVersion?: string | null) => void;
  clearPromo: () => void;

  // AI analysis actions
  setAiAnalysis: (analysis: BookingState["aiAnalysis"]) => void;
  setAiAnalyzing: (analyzing: boolean) => void;

  // Reset
  reset: () => void;
}

const initialState = {
  step: 1,
  address: {},
  photos: [],
  photoPreviewUrls: [],
  items: [],
  scheduledDate: "",
  scheduledTimeSlot: "",
  notes: "",
  dispositionPreference: "best" as DispositionPreference,
  estimatedPrice: 0,
  priceVersion: null,
  quoteId: null,
  quoteBinding: false,
  quoteToken: null,
  isSubmitting: false,
  leadSource: "",
  promoCode: "",
  promoDiscount: 0,
  promoApplied: false,
  aiAnalysis: null,
  aiAnalyzing: false,
};

/** Canonical pricing scope of a cart — order-independent (category, quantity, size). */
export function itemsScopeKey(items: JobItem[]): string {
  return items
    .map((i) => `${(i.category || "").toLowerCase()}:${i.quantity}:${(i.size || "").toLowerCase()}`)
    .sort()
    .join("|");
}

const QUOTE_CLEARED = { quoteId: null, quoteBinding: false, quoteToken: null } as const;

export const useBookingStore = create<BookingState>((set, get) => ({
  ...initialState,

  // Navigation
  setStep: (step) => set({ step: Math.min(Math.max(step, 1), 6) }),
  nextStep: () => set((state) => ({ step: Math.min(state.step + 1, 6) })),
  prevStep: () => set((state) => ({ step: Math.max(state.step - 1, 1) })),

  // Address — any change to the street text or coordinates invalidates the
  // price version and a binding photo quote (audit F10/F11): the quote was
  // issued for a specific place, and the price for specific coordinates.
  setAddress: (address) =>
    set((state) => {
      const next = { ...state.address, ...address };
      const locationChanged =
        next.street !== state.address.street ||
        next.lat !== state.address.lat ||
        next.lng !== state.address.lng ||
        next.zip !== state.address.zip;
      return locationChanged
        ? { address: next, priceVersion: null, ...QUOTE_CLEARED }
        : { address: next };
    }),

  // Photos
  addPhotos: (files) =>
    set((state) => {
      const newPreviewUrls = files.map((file) => URL.createObjectURL(file));
      return {
        photos: [...state.photos, ...files],
        photoPreviewUrls: [...state.photoPreviewUrls, ...newPreviewUrls],
      };
    }),
  removePhoto: (index) =>
    set((state) => {
      // Revoke the object URL to free memory
      const urlToRevoke = state.photoPreviewUrls[index];
      if (urlToRevoke) {
        URL.revokeObjectURL(urlToRevoke);
      }
      return {
        photos: state.photos.filter((_, i) => i !== index),
        photoPreviewUrls: state.photoPreviewUrls.filter((_, i) => i !== index),
      };
    }),

  // Items — a changed pricing scope invalidates the price version and any
  // binding quote. Re-setting an identical cart (step 3 re-syncs on mount)
  // keeps both.
  setItems: (items) =>
    set((state) =>
      itemsScopeKey(items) === itemsScopeKey(state.items)
        ? { items }
        : { items, priceVersion: null, ...QUOTE_CLEARED }
    ),
  addItem: (item) =>
    set((state) => ({ items: [...state.items, item], priceVersion: null, ...QUOTE_CLEARED })),
  removeItem: (id) =>
    set((state) => ({
      items: state.items.filter((item) => item.id !== id),
      priceVersion: null,
      ...QUOTE_CLEARED,
    })),

  // Schedule — surcharges depend on the date, so the version is stale. The
  // quote is kept: the server re-checks whether the date adds a surcharge.
  setSchedule: (scheduledDate, scheduledTimeSlot) =>
    set((state) =>
      scheduledDate === state.scheduledDate && scheduledTimeSlot === state.scheduledTimeSlot
        ? { scheduledDate, scheduledTimeSlot }
        : { scheduledDate, scheduledTimeSlot, priceVersion: null }
    ),

  // Misc
  setNotes: (notes) => set({ notes }),
  setDispositionPreference: (dispositionPreference) => set({ dispositionPreference }),
  setEstimatedPrice: (estimatedPrice) => set({ estimatedPrice }),
  setPriceVersion: (priceVersion) => set({ priceVersion }),
  setQuoteId: (quoteId) => set({ quoteId, priceVersion: null }),
  setQuoteBinding: (quoteBinding) => set({ quoteBinding }),
  setQuoteToken: (quoteToken) => set({ quoteToken }),
  clearQuote: () => set({ ...QUOTE_CLEARED, priceVersion: null }),
  setIsSubmitting: (isSubmitting) => set({ isSubmitting }),
  setLeadSource: (leadSource) => set({ leadSource }),

  // Promo code — the discount is priced server-side; the version that covers
  // the discounted total travels with it.
  setPromoCode: (promoCode) => set({ promoCode }),
  applyPromo: (promoCode, promoDiscount, priceVersion) =>
    set((state) => ({
      promoCode,
      promoDiscount,
      promoApplied: true,
      priceVersion: priceVersion === undefined ? state.priceVersion : priceVersion,
    })),
  clearPromo: () =>
    set({ promoCode: "", promoDiscount: 0, promoApplied: false, priceVersion: null }),

  // AI analysis
  setAiAnalysis: (aiAnalysis) => set({ aiAnalysis }),
  setAiAnalyzing: (aiAnalyzing) => set({ aiAnalyzing }),

  // Reset - revoke all object URLs before clearing
  reset: () => {
    const { photoPreviewUrls } = get();
    photoPreviewUrls.forEach((url) => URL.revokeObjectURL(url));
    set(initialState);
  },
}));

const ABANDONED_BOOKING_KEY = "umuve_abandoned_booking";

export function clearAbandonedBooking() {
  try {
    localStorage.removeItem(ABANDONED_BOOKING_KEY);
  } catch {
    // noop
  }
}
