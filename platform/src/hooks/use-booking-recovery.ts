"use client";

import { useEffect, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { useBookingStore } from "@/stores/booking-store";
import { bookingDraftKey, readBrowserWork, removeBrowserWork, saveBrowserWork } from "@/lib/browser-work";

function snapshot() {
  const s = useBookingStore.getState();
  return {
    step: s.step, address: s.address, photos: s.photos, items: s.items,
    scheduledDate: s.scheduledDate, scheduledTimeSlot: s.scheduledTimeSlot,
    notes: s.notes, dispositionPreference: s.dispositionPreference,
    estimatedPrice: s.estimatedPrice, priceVersion: s.priceVersion,
    quoteId: s.quoteId, quoteBinding: s.quoteBinding, quoteToken: s.quoteToken,
    promoCode: s.promoCode, promoDiscount: s.promoDiscount, promoApplied: s.promoApplied,
    leadSource: s.leadSource, contact: s.contact,
    checkout: s.checkout,
  };
}
type Draft = { version: 1; updatedAt: number; data: ReturnType<typeof snapshot> };

export async function saveBookingDraft() {
  const key = useBookingStore.getState().draftOwner;
  if (!key) throw new Error("Wait for your saved booking to finish loading.");
  await saveBrowserWork(key, { version: 1, updatedAt: Date.now(), data: snapshot() } satisfies Draft);
}

export function useBookingRecovery() {
  const userId = useAuthStore((s) => s.user?.id);
  const authLoading = useAuthStore((s) => s.isLoading);
  const key = bookingDraftKey(userId);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (authLoading) return;
    let active = true;
    let unsubscribe: (() => void) | undefined;
    let revision = 0;
    setLoadedKey(null); setError(null); setMessage(null);
    const save = () => {
      const current = ++revision;
      const state = useBookingStore.getState();
      if (state.draftOwner !== key) return;
      const meaningful = Boolean(state.address.street || state.items.length || state.photos.length);
      const work = state.draftComplete || !meaningful
        ? removeBrowserWork(key)
        : saveBrowserWork(key, { version: 1, updatedAt: Date.now(), data: snapshot() } satisfies Draft);
      if (meaningful && !state.draftComplete) setMessage("Saving your draft…");
      void work.then(() => {
        if (!active || revision !== current) return;
        setError(null);
        setMessage(state.draftComplete || !meaningful ? null : "Draft saved in this browser, including your photos.");
      }).catch(() => {
        if (active) { setMessage(null); setError("Your draft could not be saved. Keep this page open and retry saving before leaving."); }
      });
    };
    void (async () => {
      try {
        const state = useBookingStore.getState();
        if (state.draftOwner !== key) {
          const draft = await readBrowserWork<Draft>(key);
          if (!active) return;
          if (state.draftOwner) state.reset();
          if (draft?.version === 1 && Date.now() - draft.updatedAt < 7 * 86400_000) {
            const photos = draft.data.photos.filter((file) => file instanceof Blob);
            useBookingStore.getState().photoPreviewUrls.forEach((url) => URL.revokeObjectURL(url));
            useBookingStore.setState({ ...draft.data, photos, photoPreviewUrls: photos.map((file) => URL.createObjectURL(file)), isSubmitting: false });
            setMessage("Your saved booking is ready to continue.");
          } else if (draft) await removeBrowserWork(key);
          useBookingStore.setState({ draftOwner: key, draftComplete: false });
        }
      } catch {
        if (!active) return;
        const state = useBookingStore.getState();
        if (state.draftOwner && state.draftOwner !== key) state.reset();
        useBookingStore.setState({ draftOwner: key });
        setError("This browser could not restore your saved draft. Keep this page open while booking.");
      }
      if (active) {
        setLoadedKey(key);
        unsubscribe = useBookingStore.subscribe(save);
      }
    })();
    return () => { active = false; unsubscribe?.(); };
  }, [key, authLoading]);

  return { ready: !authLoading && loadedKey === key, message, error, retry: () => {
    // A same-owner retry saves the in-memory draft before trying restoration.
    const key = bookingDraftKey(userId);
    void saveBrowserWork(key, { version: 1, updatedAt: Date.now(), data: snapshot() } satisfies Draft)
      .then(() => { setError(null); setMessage("Draft saved in this browser."); })
      .catch(() => setError("Your draft still could not be saved. Keep this page open and allow browser storage, then retry."));
  } };
}
