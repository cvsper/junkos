"use client";

import { Suspense, useState } from "react";
import { useSearchParams, useRouter } from "next/navigation";
import { useAuthStore } from "@/stores/auth-store";
import { Check } from "lucide-react";

// ---------------------------------------------------------------------------
// Plan data
// ---------------------------------------------------------------------------

const plans = [
  {
    id: "starter",
    name: "Starter",
    monthlyPrice: 149,
    annualPrice: 1341,
    popular: false,
    description: "Perfect for occasional cleanouts",
    features: [
      "1 pickup per month",
      "Up to 1/4 truck load",
      "Priority scheduling",
      "Text-based booking",
      "Donation receipts included",
    ],
    cta: "Get Started",
  },
  {
    id: "professional",
    name: "Professional",
    monthlyPrice: 349,
    annualPrice: 3141,
    popular: true,
    description: "Ideal for property managers & landlords",
    features: [
      "2 pickups per month",
      "Up to 1/2 truck each pickup",
      "Dedicated account manager",
      "Priority scheduling",
      "Text-based booking",
      "Donation receipts included",
    ],
    cta: "Get Started",
  },
  {
    id: "enterprise",
    name: "Enterprise",
    monthlyPrice: 799,
    annualPrice: 7191,
    popular: false,
    description: "Built for high-volume operations",
    features: [
      "4 pickups per month",
      "Full truck each pickup",
      "White-glove service",
      "Dedicated team assigned",
      "Custom SLA",
      "Priority scheduling & booking",
      "Donation receipts included",
    ],
    cta: "Get Started",
  },
] as const;

type PlanId = (typeof plans)[number]["id"];

// ---------------------------------------------------------------------------
// Inner component (needs useSearchParams inside Suspense)
// ---------------------------------------------------------------------------

function SubscribeContent() {
  const searchParams = useSearchParams();
  const router = useRouter();
  const { isAuthenticated } = useAuthStore();

  const paramPlan = searchParams.get("plan") as PlanId | null;
  const [selectedPlan, setSelectedPlan] = useState<PlanId>(
    plans.some((p) => p.id === paramPlan) ? paramPlan! : "professional"
  );
  const [annual, setAnnual] = useState(false);

  const handleGetStarted = (planId: PlanId) => {
    if (isAuthenticated) {
      router.push(`/book?subscription=${planId}&billing=${annual ? "annual" : "monthly"}`);
    } else {
      router.push(`/signup?redirect=/subscribe&plan=${planId}`);
    }
  };

  return (
    <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-12 md:py-20">
      {/* Header */}
      <div className="text-center max-w-2xl mx-auto mb-12">
        <h1 className="text-3xl sm:text-4xl md:text-5xl font-bold tracking-tight text-foreground font-[family-name:var(--font-outfit)]">
          Never Think About Junk Again
        </h1>
        <p className="mt-4 text-lg text-muted-foreground">
          Subscribe to regular pickups and save up to 40%. Cancel anytime.
        </p>
      </div>

      {/* Billing toggle */}
      <div className="flex items-center justify-center gap-3 mb-10">
        <span
          className={`text-sm font-medium ${!annual ? "text-foreground" : "text-muted-foreground"}`}
        >
          Monthly
        </span>
        <button
          type="button"
          role="switch"
          aria-checked={annual}
          onClick={() => setAnnual(!annual)}
          className={`relative inline-flex h-6 w-11 shrink-0 cursor-pointer rounded-full border-2 border-transparent transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-2 ${
            annual ? "bg-red-600" : "bg-muted"
          }`}
        >
          <span
            className={`pointer-events-none inline-block h-5 w-5 rounded-full bg-white shadow-lg ring-0 transition-transform ${
              annual ? "translate-x-5" : "translate-x-0"
            }`}
          />
        </button>
        <span
          className={`text-sm font-medium ${annual ? "text-foreground" : "text-muted-foreground"}`}
        >
          Annual{" "}
          <span className="inline-block ml-1 text-xs font-semibold text-green-600 bg-green-50 px-1.5 py-0.5 rounded-full">
            2 months free
          </span>
        </span>
      </div>

      {/* Plan cards */}
      <div className="grid grid-cols-1 md:grid-cols-3 gap-6 lg:gap-8">
        {plans.map((plan) => {
          const isSelected = plan.id === selectedPlan;
          const price = annual
            ? Math.round(plan.annualPrice / 12)
            : plan.monthlyPrice;

          return (
            <div
              key={plan.id}
              onClick={() => setSelectedPlan(plan.id)}
              className={`relative rounded-2xl border-2 p-6 lg:p-8 cursor-pointer transition-all ${
                isSelected
                  ? "border-red-600 shadow-lg shadow-red-600/10 scale-[1.02]"
                  : "border-border hover:border-muted-foreground/30"
              }`}
            >
              {/* Popular badge */}
              {plan.popular && (
                <div className="absolute -top-3 left-1/2 -translate-x-1/2">
                  <span className="bg-red-600 text-white text-xs font-semibold px-3 py-1 rounded-full whitespace-nowrap">
                    Most Popular
                  </span>
                </div>
              )}

              <div className="mb-4">
                <h3 className="text-lg font-semibold text-foreground">
                  {plan.name}
                </h3>
                <p className="text-sm text-muted-foreground mt-1">
                  {plan.description}
                </p>
              </div>

              {/* Price */}
              <div className="mb-6">
                <span className="text-4xl font-bold text-foreground">${price}</span>
                <span className="text-muted-foreground">/mo</span>
                {annual && (
                  <p className="text-xs text-muted-foreground mt-1">
                    ${plan.annualPrice.toLocaleString()}/yr billed annually
                  </p>
                )}
              </div>

              {/* Features */}
              <ul className="space-y-3 mb-8">
                {plan.features.map((feature) => (
                  <li key={feature} className="flex items-start gap-2 text-sm">
                    <Check className="w-4 h-4 text-green-600 mt-0.5 shrink-0" />
                    <span className="text-foreground">{feature}</span>
                  </li>
                ))}
              </ul>

              {/* CTA */}
              <button
                onClick={(e) => {
                  e.stopPropagation();
                  handleGetStarted(plan.id);
                }}
                className={`w-full py-2.5 px-4 rounded-lg text-sm font-semibold transition-colors ${
                  isSelected
                    ? "bg-red-600 text-white hover:bg-red-700"
                    : "border border-border text-foreground hover:bg-muted"
                }`}
              >
                {plan.cta}
              </button>
            </div>
          );
        })}
      </div>

      {/* FAQ */}
      <div className="mt-20 max-w-2xl mx-auto">
        <h2 className="text-2xl font-bold text-foreground text-center mb-8">
          Frequently Asked Questions
        </h2>
        <div className="space-y-6">
          {[
            {
              q: "Can I cancel anytime?",
              a: "Yes. Cancel your subscription at any time with no penalties or hidden fees. Your remaining pickups for the current billing period will still be honored.",
            },
            {
              q: "What happens if I need an extra pickup?",
              a: "Additional pickups can be booked at our standard rates. Subscribers get priority scheduling on all extra bookings.",
            },
            {
              q: "How does the annual plan work?",
              a: "Pay upfront for the year and get 2 months free. That's the equivalent of saving up to 17% compared to monthly billing.",
            },
            {
              q: "What areas do you serve?",
              a: "We currently serve Miami-Dade, Broward, and Palm Beach counties in South Florida. Enter your address during booking to confirm coverage.",
            },
          ].map(({ q, a }) => (
            <details
              key={q}
              className="group border border-border rounded-lg overflow-hidden"
            >
              <summary className="flex items-center justify-between cursor-pointer px-5 py-4 text-sm font-medium text-foreground hover:bg-muted/50 transition-colors">
                {q}
                <svg
                  className="w-4 h-4 shrink-0 text-muted-foreground transition-transform group-open:rotate-180"
                  fill="none"
                  viewBox="0 0 24 24"
                  strokeWidth={2}
                  stroke="currentColor"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M19 9l-7 7-7-7" />
                </svg>
              </summary>
              <p className="px-5 pb-4 text-sm text-muted-foreground">{a}</p>
            </details>
          ))}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Page export with Suspense boundary for useSearchParams
// ---------------------------------------------------------------------------

export default function SubscribePage() {
  return (
    <Suspense
      fallback={
        <div className="flex items-center justify-center min-h-[60vh]">
          <div className="animate-spin rounded-full h-8 w-8 border-b-2 border-red-600" />
        </div>
      }
    >
      <SubscribeContent />
    </Suspense>
  );
}
