import { create } from "zustand";
import { persist } from "zustand/middleware";
import type { User } from "@/types";

interface AuthState {
  user: User | null;
  token: string | null;
  isAuthenticated: boolean;
  isLoading: boolean;
  setUser: (user: User | null) => void;
  setToken: (token: string | null) => void;
  setLoading: (loading: boolean) => void;
  login: (user: User, token: string) => void;
  logout: () => void;
}

export const useAuthStore = create<AuthState>()(
  persist(
    (set) => ({
      user: null,
      token: null,
      isAuthenticated: false,
      isLoading: true,
      setUser: (user) => set({ user, isAuthenticated: !!user }),
      setToken: (token) => set({ token }),
      setLoading: (isLoading) => set({ isLoading }),
      login: (user, token) =>
        set({ user, token, isAuthenticated: true, isLoading: false }),
      logout: () =>
        set({ user: null, token: null, isAuthenticated: false, isLoading: false }),
    }),
    {
      name: "umuve-auth",
      partialize: (state) => ({ token: state.token, user: state.user }),
      onRehydrateStorage: () => (state) => {
        if (state) {
          // Migrate from legacy "junkos-auth" if "umuve-auth" is empty
          if (!state.token && !state.user && typeof window !== "undefined") {
            try {
              const legacy = localStorage.getItem("junkos-auth");
              if (legacy) {
                const parsed = JSON.parse(legacy);
                const legacyState = parsed?.state;
                if (legacyState?.token && legacyState?.user) {
                  state.token = legacyState.token;
                  state.user = legacyState.user;
                  // Persist under new key and clean up old key
                  localStorage.setItem(
                    "umuve-auth",
                    JSON.stringify({ state: { token: legacyState.token, user: legacyState.user }, version: 0 })
                  );
                  localStorage.removeItem("junkos-auth");
                }
              }
            } catch {
              // Ignore migration errors
            }
          }
          state.isAuthenticated = !!(state.token && state.user);
          state.isLoading = false;
        }
      },
    }
  )
);
