"use client";

import Link from "next/link";
import { Suspense, useState } from "react";
import { useSearchParams } from "next/navigation";
import { authApi, ApiError } from "@/lib/api";

function ResetPasswordForm() {
  const params = useSearchParams();
  const token = params.get("token") || "";
  const to = params.get("to") === "operator" ? "operator" : "customer";
  const loginHref = to === "operator" ? "/operator/login" : "/login";
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [done, setDone] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password !== confirm) {
      setError("Those two passwords don't match.");
      return;
    }
    setLoading(true);
    try {
      await authApi.resetPassword(token, password);
      setDone(true);
    } catch (err) {
      setError(err instanceof ApiError || err instanceof Error ? err.message : "Something went wrong. Try again.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-background">
      <div className="w-full max-w-sm">
        <div className="text-center mb-8">
          <img src="/logo-login.png" alt="Umuve — Hauling made simple" className="h-36 w-auto object-contain mx-auto mb-4" />
          <p className="text-muted-foreground text-sm mt-1">
            {done ? "Password set" : "Choose a password"}
          </p>
        </div>

        {!token ? (
          <div className="space-y-4 text-center">
            <p className="text-sm text-foreground">This link is missing its code. Open the link from your email again, or ask for a new one.</p>
            <Link href={`/forgot-password?to=${to}`} className="inline-block text-sm text-primary hover:underline">
              Send me a new link
            </Link>
          </div>
        ) : done ? (
          <div className="space-y-4 text-center">
            <p className="text-sm text-foreground">Your password is set. Sign in with your email and the password you just chose.</p>
            <Link href={loginHref} className="inline-flex items-center justify-center w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed">
              Sign in
            </Link>
          </div>
        ) : (
          <>
            <div aria-live="polite" aria-atomic="true">
              {error && (
                <div role="alert" className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
                  <p className="text-sm text-red-700">{error}</p>
                </div>
              )}
            </div>
            <form onSubmit={handleSubmit} className="space-y-4">
              <div>
                <label htmlFor="password" className="block text-sm font-medium mb-1.5">
                  New password
                </label>
                <input
                  id="password"
                  type="password"
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  placeholder="At least 8 characters"
                  minLength={8}
                  required
                  autoFocus
                  autoComplete="new-password"
                  className="w-full rounded-lg border border-border bg-card px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-colors"
                />
              </div>
              <div>
                <label htmlFor="confirm" className="block text-sm font-medium mb-1.5">
                  Type it again
                </label>
                <input
                  id="confirm"
                  type="password"
                  value={confirm}
                  onChange={(e) => setConfirm(e.target.value)}
                  placeholder="Same password"
                  minLength={8}
                  required
                  autoComplete="new-password"
                  className="w-full rounded-lg border border-border bg-card px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-colors"
                />
              </div>
              <button type="submit" disabled={loading} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed">
                {loading ? "Saving..." : "Set password"}
              </button>
            </form>
            <p className="mt-6 text-center text-sm text-muted-foreground">
              Link expired?{" "}
              <Link href={`/forgot-password?to=${to}`} className="text-primary hover:underline">
                Send me a new one
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export default function ResetPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ResetPasswordForm />
    </Suspense>
  );
}
