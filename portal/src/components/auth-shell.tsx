"use client";

import Link from "next/link";

/**
 * Split-screen auth layout shared by /login and /signup.
 * Left: the form. Right (lg+): the brand thesis — "one invoice a month" —
 * made tangible with the same monthly-invoice card motif as the homepage,
 * so the B2B value prop is on screen at the exact moment someone signs up.
 */
export function AuthShell({
  children,
  heading,
  sub,
}: {
  children: React.ReactNode;
  heading: string;
  sub?: string;
}) {
  return (
    <div className="min-h-screen grid lg:grid-cols-2 bg-white">
      {/* Form side */}
      <div className="flex flex-col px-6 py-8 sm:px-12 lg:px-16">
        <Link href="/" className="block" aria-label="Umuve Commercial — Home">
          {/* eslint-disable-next-line @next/next/no-img-element */}
          <img src="/logo-nav.png" alt="Umuve" className="h-8 w-auto" />
          <span className="mt-1 block text-[0.6rem] font-semibold uppercase tracking-[0.2em] text-gray-400">
            Commercial
          </span>
        </Link>

        <div className="flex flex-1 items-center">
          <div className="mx-auto w-full max-w-sm py-10">
            <h1 className="text-3xl font-extrabold tracking-tight text-gray-900">
              {heading}
            </h1>
            {sub && <p className="mt-2 text-sm leading-relaxed text-gray-500">{sub}</p>}
            <div className="mt-8">{children}</div>
          </div>
        </div>

        <p className="text-xs text-gray-400">
          © 2026 Umuve · Palm Beach &amp; Broward County, FL
        </p>
      </div>

      {/* Brand side */}
      <div className="relative hidden items-center overflow-hidden bg-[#141414] p-16 text-white lg:flex">
        <div className="absolute -right-24 -top-24 h-96 w-96 rounded-full bg-brand-600/20 blur-3xl" />
        <div className="relative max-w-md">
          <h2 className="text-4xl font-extrabold leading-[1.1] tracking-tight">
            One default hauler.
            <br />
            One invoice a month.
          </h2>
          <p className="mt-5 leading-relaxed text-white/60">
            Set your pickup schedule once. Umuve dispatches a vetted local hauler
            for every property, then rolls it all into a single monthly invoice —
            recycle-first, licensed and insured.
          </p>

          {/* Signature: the monthly-invoice card */}
          <div className="mt-10 max-w-xs rounded-2xl bg-white p-6 text-gray-900 shadow-2xl">
            <div className="flex items-center justify-between">
              <span className="text-xs font-semibold uppercase tracking-wider text-gray-400">
                Monthly invoice
              </span>
              <span className="text-xs font-medium text-gray-400">June</span>
            </div>
            <div className="mt-4 space-y-2 text-sm">
              <div className="flex justify-between">
                <span className="text-gray-500">Riverside Apts · 8 turnovers</span>
                <span className="font-medium">$1,240</span>
              </div>
              <div className="flex justify-between">
                <span className="text-gray-500">4 listing cleanouts</span>
                <span className="font-medium">$600</span>
              </div>
            </div>
            <div className="my-4 border-t border-gray-100" />
            <div className="flex items-end justify-between">
              <div>
                <div className="text-xs text-gray-400">Total · net-30</div>
                <div className="text-2xl font-extrabold">$1,840</div>
              </div>
              <span className="rounded-full bg-green-50 px-2.5 py-1 text-xs font-semibold text-green-700">
                ✓ Auto-billed
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export function Field({
  label,
  type = "text",
  value,
  onChange,
  placeholder,
  autoFocus,
  autoComplete,
  required = true,
}: {
  label: string;
  type?: string;
  value: string;
  onChange: (v: string) => void;
  placeholder?: string;
  autoFocus?: boolean;
  autoComplete?: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="text-xs font-medium text-gray-600">{label}</span>
      <input
        type={type}
        value={value}
        required={required}
        autoFocus={autoFocus}
        autoComplete={autoComplete}
        onChange={(e) => onChange(e.target.value)}
        placeholder={placeholder}
        className="mt-1.5 w-full rounded-lg border border-gray-300 px-3.5 py-2.5 text-sm text-gray-900 outline-none transition-colors placeholder:text-gray-400 focus:border-brand-600 focus:ring-2 focus:ring-brand-100"
      />
    </label>
  );
}
