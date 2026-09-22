"use client";

import Link from "next/link";
import { useState } from "react";
import { useSearchParams } from "next/navigation";
import { Suspense } from "react";
import { authApi, ApiError } from "@/lib/api";

function ForgotPasswordForm() {
  const params = useSearchParams();
  const to = params.get("to") === "operator" ? "operator" : "customer";
  const loginHref = to === "operator" ? "/operator/login" : "/login";
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      await authApi.forgotPassword(email.trim());
      setSent(true);
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
            {sent ? "Check your email" : "Reset your password"}
          </p>
        </div>

        {sent ? (
          <div className="space-y-4 text-center">
            <p className="text-sm text-foreground">
              If there&apos;s an account for <span className="font-medium">{email.trim()}</span>, a link to choose a new
              password is on its way. It works for one hour.
            </p>
            <p className="text-sm text-muted-foreground">Nothing there in a few minutes? Check spam, or try again.</p>
            <Link href={loginHref} className="inline-block text-sm text-primary hover:underline">
              Back to sign in
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
                <label htmlFor="email" className="block text-sm font-medium mb-1.5">
                  Email
                </label>
                <input
                  id="email"
                  type="email"
                  value={email}
                  onChange={(e) => setEmail(e.target.value)}
                  placeholder="you@example.com"
                  required
                  autoFocus
                  className="w-full rounded-lg border border-border bg-card px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-colors"
                />
              </div>
              <button type="submit" disabled={loading} className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed">
                {loading ? "Sending..." : "Email me a reset link"}
              </button>
            </form>
            <p className="mt-6 text-center text-sm text-muted-foreground">
              <Link href={loginHref} className="text-primary hover:underline">
                Back to sign in
              </Link>
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export default function ForgotPasswordPage() {
  return (
    <Suspense fallback={null}>
      <ForgotPasswordForm />
    </Suspense>
  );
}
