"use client";

import { useEffect, useRef, useState } from "react";
import { useAuthStore } from "@/stores/auth-store";
import { driverApi } from "@/lib/api";
import { readBrowserWork, removeBrowserWork, saveBrowserWork } from "@/lib/browser-work";
import type { DriverJob } from "@/types";

type Kind = "before" | "after";
interface Work {
  before: File[]; after: File[]; beforeURLs: string[]; afterURLs: string[];
  pendingStatus: string | null;
}
const empty = (): Work => ({ before: [], after: [], beforeURLs: [], afterURLs: [], pendingStatus: null });
const merge = (a: string[], b: string[]) => Array.from(new Set([...a, ...b]));

export function useDriverWork(jobId: string) {
  const userId = useAuthStore((s) => s.user?.id);
  const key = userId ? `proof:${userId}:${jobId}` : null;
  const activeKey = useRef(key);
  activeKey.current = key;
  const current = useRef<Work>(empty());
  const lock = useRef(false);
  const [work, setWork] = useState<Work>(empty);
  const [loadedKey, setLoadedKey] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let active = true;
    activeKey.current = key;
    current.current = empty(); setWork(empty()); setLoadedKey(null); setError(null);
    if (!key) return;
    void readBrowserWork<Work>(key).then((saved) => {
      if (!active) return;
      current.current = saved ?? empty(); setWork(current.current); setLoadedKey(key);
    }).catch(() => {
      if (active) setError("This browser could not restore your saved work. Reload or allow browser storage before continuing.");
    });
    return () => { active = false; activeKey.current = null; };
  }, [key]);

  async function persist(next: Work) {
    if (!key || activeKey.current !== key || useAuthStore.getState().user?.id !== userId) throw new Error("Sign in again before saving this pickup.");
    current.current = next; setWork(next);
    try { await saveBrowserWork(key, next); }
    catch { throw new Error("Your work could not be saved in this browser. Keep this page open, free some space, and retry."); }
    if (activeKey.current !== key || useAuthStore.getState().user?.id !== userId) throw new Error("The signed-in account changed. Open this pickup from its account to continue.");
  }

  async function upload(kind: Kind, added: File[] = []) {
    if (lock.current || loadedKey !== key || !key) return false;
    lock.current = true; setBusy(true); setError(null);
    try {
      const files = [...current.current[kind], ...added];
      if (!files.length) return true;
      if (files.length > 10 || files.some((file) => file.size > 10 * 1024 * 1024 || !/\.(jpe?g|png|webp)$/i.test(file.name))) {
        throw new Error("Choose up to 10 JPG, PNG, or WebP photos, each smaller than 10 MB.");
      }
      await persist({ ...current.current, [kind]: files });
      const result = await driverApi.uploadPhotos(files);
      const urlsKey = kind === "before" ? "beforeURLs" : "afterURLs";
      await persist({ ...current.current, [kind]: [], [urlsKey]: merge(current.current[urlsKey], result.urls) });
      return true;
    } catch (reason) {
      if (activeKey.current === key) setError(reason instanceof Error ? reason.message : "Photo upload failed. Your selected photos are saved for retry.");
      return false;
    } finally { lock.current = false; setBusy(false); }
  }

  async function transition(status: string, handoffPin?: string): Promise<DriverJob | null> {
    if (lock.current || loadedKey !== key || !key) return null;
    lock.current = true; setBusy(true); setError(null);
    try {
      await persist({ ...current.current, pendingStatus: status });
      // A previous request may have succeeded even if its response was lost.
      const { job } = await driverApi.getJob(jobId);
      if (activeKey.current !== key || useAuthStore.getState().user?.id !== userId) return null;
      if (job.requires_acceptance) throw new Error("Accept this pickup before updating its progress.");
      let updated = job;
      const order = ["assigned", "en_route", "arrived", "in_progress", "completed"];
      const alreadyApplied = order.includes(status) && order.indexOf(job.status) >= order.indexOf(status);
      if (!alreadyApplied) {
        if (current.current.before.length || current.current.after.length) throw new Error("Retry your saved photos before updating pickup progress.");
        if ((status === "in_progress" || status === "completed") && (job.volume_adjustment_proposed || job.has_open_change_order)) throw new Error("Wait for the customer to resolve the revised price before continuing.");
        if (status === "completed" && handoffPin && !/^\d{4}$/.test(handoffPin)) throw new Error("Enter the customer's 4-digit handoff PIN.");
        updated = (await driverApi.updateJobStatus(jobId, status, undefined, undefined, {
          before_photos: merge(job.before_photos, current.current.beforeURLs),
          after_photos: merge(job.after_photos, current.current.afterURLs),
          version: job.version,
          // Keep the PIN out of browser storage. An interrupted completion
          // checks server progress first; enter it again only if still needed.
          ...(status === "completed" && handoffPin ? { handoff_pin: handoffPin } : {}),
        })).job;
      }
      if (activeKey.current !== key || useAuthStore.getState().user?.id !== userId) return null;
      if (updated.status === "completed") {
        await removeBrowserWork(key);
        current.current = empty(); setWork(empty());
      } else await persist({ ...current.current, pendingStatus: null });
      return updated;
    } catch (reason) {
      if (activeKey.current === key) setError(reason instanceof Error ? reason.message : "Could not update this pickup. Retry the saved update when connected.");
      return null;
    } finally { lock.current = false; setBusy(false); }
  }

  async function removePendingPhoto(kind: Kind, index: number) {
    if (lock.current || loadedKey !== key || !key) return;
    lock.current = true; setBusy(true);
    try {
      await persist({ ...current.current, [kind]: current.current[kind].filter((_, i) => i !== index) });
      setError(null);
    } catch (reason) {
      if (activeKey.current === key) setError(reason instanceof Error ? reason.message : "Could not save the changed photo selection.");
    } finally { lock.current = false; setBusy(false); }
  }

  return { ...work, ready: Boolean(key && loadedKey === key), busy, error, upload, transition, removePendingPhoto };
}
