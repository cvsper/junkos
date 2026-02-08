import { create } from "zustand";
import type { Address, JobItem } from "@/types";

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
  estimatedPrice: number;
  isSubmitting: boolean;

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
  setEstimatedPrice: (price: number) => void;
  setIsSubmitting: (isSubmitting: boolean) => void;

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
  estimatedPrice: 0,
  isSubmitting: false,
};

export const useBookingStore = create<BookingState>((set, get) => ({
  ...initialState,

  // Navigation
  setStep: (step) => set({ step: Math.min(Math.max(step, 1), 6) }),
  nextStep: () => set((state) => ({ step: Math.min(state.step + 1, 6) })),
  prevStep: () => set((state) => ({ step: Math.max(state.step - 1, 1) })),

  // Address
  setAddress: (address) =>
    set((state) => ({ address: { ...state.address, ...address } })),

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

  // Items
  setItems: (items) => set({ items }),
  addItem: (item) => set((state) => ({ items: [...state.items, item] })),
  removeItem: (id) =>
    set((state) => ({
      items: state.items.filter((item) => item.id !== id),
    })),

  // Schedule
  setSchedule: (scheduledDate, scheduledTimeSlot) =>
    set({ scheduledDate, scheduledTimeSlot }),

  // Misc
  setNotes: (notes) => set({ notes }),
  setEstimatedPrice: (estimatedPrice) => set({ estimatedPrice }),
  setIsSubmitting: (isSubmitting) => set({ isSubmitting }),

  // Reset - revoke all object URLs before clearing
  reset: () => {
    const { photoPreviewUrls } = get();
    photoPreviewUrls.forEach((url) => URL.revokeObjectURL(url));
    set(initialState);
  },
}));
