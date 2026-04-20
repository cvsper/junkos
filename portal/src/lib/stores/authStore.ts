"use client";

import { create } from "zustand";
import {
  clearPortalAuth,
  getPortalRole,
  getPortalToken,
  portalFetch,
  setPortalAuth,
} from "../api";

export type OrgRole = "owner" | "admin" | "operator" | "viewer";

interface Org {
  id: string;
  name: string;
  slug: string;
  tier: string;
  status: string;
  billing_email: string;
}

interface AuthState {
  token: string | null;
  orgId: string | null;
  role: OrgRole | null;
  org: Org | null;
  isLoading: boolean;
  hydrate: () => Promise<void>;
  onAuthenticated: (token: string, orgId: string, role: OrgRole) => void;
  signOut: () => void;
}

export const useAuthStore = create<AuthState>((set) => ({
  token: null,
  orgId: null,
  role: null,
  org: null,
  isLoading: true,

  async hydrate() {
    const token = getPortalToken();
    if (!token) {
      set({ isLoading: false });
      return;
    }
    const role = (getPortalRole() as OrgRole) || null;
    try {
      const org = await portalFetch<Org>("/orgs/me");
      set({ token, orgId: org.id, role, org, isLoading: false });
    } catch {
      clearPortalAuth();
      set({ token: null, orgId: null, role: null, org: null, isLoading: false });
    }
  },

  onAuthenticated(token, orgId, role) {
    setPortalAuth(token, orgId, role);
    set({ token, orgId, role });
    // Refresh the org in the background.
    portalFetch<Org>("/orgs/me")
      .then((org) => set({ org }))
      .catch(() => {});
  },

  signOut() {
    clearPortalAuth();
    set({ token: null, orgId: null, role: null, org: null });
    if (typeof window !== "undefined") window.location.href = "/login";
  },
}));
