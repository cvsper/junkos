"use client";

import Link from "next/link";
import { useState } from "react";
import { operatorApplicationApi, ApiError } from "@/lib/api";

export default function OperatorSignupPage() {
  return <SignupForm />;
}

function SignupForm() {
  const [firstName, setFirstName] = useState("");
  const [lastName, setLastName] = useState("");
  const [email, setEmail] = useState("");
  const [phone, setPhone] = useState("");
  const [city, setCity] = useState("");
  const [trucks, setTrucks] = useState("");
  const [experience, setExperience] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setError(null);

    try {
      await operatorApplicationApi.submit({
        first_name: firstName,
        last_name: lastName,
        email,
        phone,
        city,
        trucks: trucks || undefined,
        experience: experience || undefined,
      });
      setSuccess(true);
    } catch (err) {
      if (err instanceof ApiError) {
        setError(err.message);
      } else if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("An unexpected error occurred. Please try again.");
      }
    } finally {
      setLoading(false);
    }
  };

  if (success) {
    return (
      <div className="min-h-screen flex items-center justify-center px-4 bg-background">
        <div className="w-full max-w-sm text-center">
          <img
            src="/logo-login.png"
            alt="Umuve — Hauling made simple"
            className="h-36 w-auto object-contain mx-auto mb-4"
          />
          <div className="rounded-lg border border-green-200 bg-green-50 px-6 py-8 dark:bg-green-950/20 dark:border-green-800">
            <svg className="h-12 w-12 text-green-600 mx-auto mb-4" fill="none" viewBox="0 0 24 24" strokeWidth={1.5} stroke="currentColor">
              <path strokeLinecap="round" strokeLinejoin="round" d="M9 12.75L11.25 15 15 9.75M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
            </svg>
            <h2 className="text-xl font-bold mb-2">Application Submitted!</h2>
            <p className="text-sm text-muted-foreground">
              Thanks for applying to become an Umuve operator. Our team will review your application within 24 hours and send you an email with the result.
            </p>
          </div>
          <Link
            href="/"
            className="mt-6 inline-block text-sm text-primary hover:text-primary/80 transition-colors"
          >
            Back to home
          </Link>
        </div>
      </div>
    );
  }

  const inputClass = "w-full rounded-lg border border-border bg-card px-3 py-2.5 text-sm placeholder:text-muted-foreground focus:outline-none focus:ring-2 focus:ring-ring focus:border-transparent transition-colors";

  return (
    <div className="min-h-screen flex items-center justify-center px-4 bg-background">
      <div className="w-full max-w-sm">
        {/* Logo */}
        <div className="text-center mb-8">
          <img
            src="/logo-login.png"
            alt="Umuve — Hauling made simple"
            className="h-36 w-auto object-contain mx-auto mb-4"
          />
          <div className="inline-flex items-center gap-2 mb-2">
            <h1 className="text-2xl font-bold">Join as Operator</h1>
            <span className="text-xs font-medium text-amber-700 bg-amber-100 px-2 py-1 rounded">
              OPERATOR
            </span>
          </div>
          <p className="text-muted-foreground text-sm mt-1">
            Get more hauling jobs in South Florida
          </p>
        </div>

        {/* Error Message */}
        {error && (
          <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3">
            <p className="text-sm text-red-700">{error}</p>
          </div>
        )}

        {/* Application Form */}
        <form onSubmit={handleSubmit} className="space-y-4">
          <div className="grid grid-cols-2 gap-3">
            <div>
              <label htmlFor="firstName" className="block text-sm font-medium mb-1.5">
                First Name
              </label>
              <input
                id="firstName"
                type="text"
                value={firstName}
                onChange={(e) => setFirstName(e.target.value)}
                placeholder="John"
                required
                className={inputClass}
              />
            </div>
            <div>
              <label htmlFor="lastName" className="block text-sm font-medium mb-1.5">
                Last Name
              </label>
              <input
                id="lastName"
                type="text"
                value={lastName}
                onChange={(e) => setLastName(e.target.value)}
                placeholder="Doe"
                required
                className={inputClass}
              />
            </div>
          </div>

          <div>
            <label htmlFor="email" className="block text-sm font-medium mb-1.5">
              Email
            </label>
            <input
              id="email"
              type="email"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              placeholder="operator@example.com"
              required
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="phone" className="block text-sm font-medium mb-1.5">
              Phone Number
            </label>
            <input
              id="phone"
              type="tel"
              value={phone}
              onChange={(e) => setPhone(e.target.value)}
              placeholder="(555) 123-4567"
              required
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="city" className="block text-sm font-medium mb-1.5">
              City
            </label>
            <input
              id="city"
              type="text"
              value={city}
              onChange={(e) => setCity(e.target.value)}
              placeholder="Miami"
              required
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="trucks" className="block text-sm font-medium mb-1.5">
              How many trucks? <span className="text-muted-foreground font-normal">(Optional)</span>
            </label>
            <input
              id="trucks"
              type="text"
              value={trucks}
              onChange={(e) => setTrucks(e.target.value)}
              placeholder="e.g. 2"
              className={inputClass}
            />
          </div>

          <div>
            <label htmlFor="experience" className="block text-sm font-medium mb-1.5">
              Experience <span className="text-muted-foreground font-normal">(Optional)</span>
            </label>
            <input
              id="experience"
              type="text"
              value={experience}
              onChange={(e) => setExperience(e.target.value)}
              placeholder="e.g. 3 years in junk removal"
              className={inputClass}
            />
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-primary px-4 py-2.5 text-sm font-medium text-primary-foreground hover:bg-primary/90 transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2 disabled:opacity-50 disabled:cursor-not-allowed flex items-center justify-center gap-2"
          >
            {loading && (
              <svg
                className="animate-spin h-4 w-4"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            )}
            {loading ? "Submitting..." : "Submit Application"}
          </button>
        </form>

        {/* Login Link */}
        <p className="mt-6 text-center text-sm text-muted-foreground">
          Already approved?{" "}
          <Link
            href="/operator/login"
            className="font-medium text-primary hover:text-primary/80 transition-colors"
          >
            Sign in
          </Link>
        </p>

        {/* Footer Links */}
        <div className="mt-4 text-center space-y-2">
          <Link
            href="/"
            className="block text-sm text-muted-foreground hover:text-foreground transition-colors"
          >
            Back to home
          </Link>
        </div>

        {/* Terms */}
        <p className="mt-6 text-xs text-center text-muted-foreground">
          By applying, you agree to our{" "}
          <Link href="/terms" className="underline hover:text-foreground">
            Terms
          </Link>{" "}
          and{" "}
          <Link href="/privacy" className="underline hover:text-foreground">
            Privacy Policy
          </Link>
        </p>
      </div>
    </div>
  );
}
