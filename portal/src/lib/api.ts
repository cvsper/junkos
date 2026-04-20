// Authenticated fetch helper for portal.goumuve.com.
// Reads the portal JWT from localStorage (set after /orgs/invite/accept or
// /auth/token exchange) and attaches it to every request.

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL || "https://junkos-backend.onrender.com";

const TOKEN_KEY = "umuve_portal_token";
const ORG_KEY = "umuve_portal_org";

export function setPortalAuth(token: string, orgId: string, role: string) {
  if (typeof window === "undefined") return;
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(ORG_KEY, orgId);
  localStorage.setItem("umuve_portal_role", role);
}

export function clearPortalAuth() {
  if (typeof window === "undefined") return;
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(ORG_KEY);
  localStorage.removeItem("umuve_portal_role");
}

export function getPortalToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getPortalRole(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem("umuve_portal_role");
}

export class ApiError extends Error {
  constructor(public status: number, public payload: unknown) {
    super(`API error ${status}`);
  }
}

export async function portalFetch<T = unknown>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const token = getPortalToken();
  const headers = new Headers(init.headers || {});
  headers.set("Content-Type", "application/json");
  if (token) headers.set("Authorization", `Bearer ${token}`);

  const resp = await fetch(`${API_BASE}/portal/v1${path}`, {
    ...init,
    headers,
  });

  if (resp.status === 401) {
    clearPortalAuth();
    if (typeof window !== "undefined" && window.location.pathname !== "/login") {
      window.location.href = "/login";
    }
  }

  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) {
    throw new ApiError(resp.status, body);
  }
  return body as T;
}

// Public (unauthenticated) fetch — used for /orgs/invite/accept before we
// have a token.
export async function portalFetchPublic<T = unknown>(
  path: string,
  init: RequestInit = {}
): Promise<T> {
  const headers = new Headers(init.headers || {});
  headers.set("Content-Type", "application/json");
  const resp = await fetch(`${API_BASE}/portal/v1${path}`, {
    ...init,
    headers,
  });
  const body = await resp.json().catch(() => ({}));
  if (!resp.ok) throw new ApiError(resp.status, body);
  return body as T;
}
