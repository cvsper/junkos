import { create } from "zustand";
import type { JobStatus, TrackingUpdate } from "@/types";

interface TrackingState {
  jobId: string | null;
  status: JobStatus | null;
  contractorLocation: { lat: number; lng: number } | null;
  eta: number | null;
  updates: TrackingUpdate[];
  isConnected: boolean;

  setJobId: (jobId: string | null) => void;
  setStatus: (status: JobStatus) => void;
  setContractorLocation: (location: { lat: number; lng: number } | null) => void;
  setEta: (eta: number | null) => void;
  addUpdate: (update: TrackingUpdate) => void;
  setConnected: (isConnected: boolean) => void;
  reset: () => void;
}

const initialState = {
  jobId: null,
  status: null,
  contractorLocation: null,
  eta: null,
  updates: [],
  isConnected: false,
};

export const useTrackingStore = create<TrackingState>((set) => ({
  ...initialState,

  setJobId: (jobId) => set({ jobId }),
  setStatus: (status) => set({ status }),
  setContractorLocation: (contractorLocation) => set({ contractorLocation }),
  setEta: (eta) => set({ eta }),
  addUpdate: (update) =>
    set((state) => ({
      updates: [...state.updates, update],
      // Also sync top-level fields from the update
      status: update.status,
      contractorLocation: update.contractorLocation ?? state.contractorLocation,
      eta: update.eta ?? state.eta,
    })),
  setConnected: (isConnected) => set({ isConnected }),
  reset: () => set(initialState),
}));
