/**
 * The browser routes for the ad engine are for admins. The app has no
 * sessions of its own; the backend does. So a request proves itself with
 * the same bearer token the admin pages already carry, and the backend says
 * who it is.
 */
import { resolveApiBaseUrl } from "@/lib/api-base-url";

export async function requireAdmin(req: Request): Promise<{ ok: true; email: string } | { ok: false; status: number; error: string }> {
  const auth = req.headers.get("authorization") || "";
  if (!auth.startsWith("Bearer ")) return { ok: false, status: 401, error: "Sign in as an admin first." };
  try {
    const r = await fetch(`${resolveApiBaseUrl()}/api/auth/me`, { headers: { Authorization: auth }, cache: "no-store" });
    if (!r.ok) return { ok: false, status: 401, error: "Sign in as an admin first." };
    const j = (await r.json()) as { user?: { role?: string; email?: string }; role?: string; email?: string };
    const role = j.user?.role || j.role;
    if (role !== "admin") return { ok: false, status: 403, error: "That needs an admin." };
    return { ok: true, email: j.user?.email || j.email || "" };
  } catch {
    return { ok: false, status: 502, error: "Couldn't verify your session." };
  }
}
