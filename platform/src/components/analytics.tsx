import Script from "next/script";

/**
 * Analytics component that conditionally renders tracking scripts.
 *
 * Supports:
 * - Google Analytics: set NEXT_PUBLIC_GA_ID (e.g., "G-XXXXXXXXXX")
 * - Google Ads: set NEXT_PUBLIC_GOOGLE_ADS_ID (e.g., "AW-XXXXXXXXXX")
 * - Plausible Analytics: set NEXT_PUBLIC_PLAUSIBLE_DOMAIN (e.g., "goumuve.com")
 *
 * If no env vars are set, this component renders nothing (safe for dev).
 */
export function Analytics() {
  const gaId = process.env.NEXT_PUBLIC_GA_ID;
  const gadsId = process.env.NEXT_PUBLIC_GOOGLE_ADS_ID;
  const plausibleDomain = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;

  // Use GA ID as the primary gtag config, but also load Ads tag if set
  const primaryTag = gaId || gadsId;

  return (
    <>
      {/* Google Analytics + Google Ads (shared gtag.js) */}
      {primaryTag && (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${primaryTag}`}
            strategy="afterInteractive"
          />
          <Script id="google-analytics" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              ${gaId ? `gtag('config', '${gaId}');` : ""}
              ${gadsId ? `gtag('config', '${gadsId}');` : ""}
            `}
          </Script>
        </>
      )}

      {/* Plausible Analytics */}
      {plausibleDomain && (
        <Script
          defer
          data-domain={plausibleDomain}
          src="https://plausible.io/js/script.js"
          strategy="afterInteractive"
        />
      )}
    </>
  );
}

/**
 * Fire a Google Ads conversion event + GA4 purchase event.
 * Call this after a successful booking payment.
 */
export function trackBookingConversion(params: {
  bookingId: string;
  value: number;
  currency?: string;
}) {
  if (typeof window === "undefined") return;

  const gtag = (window as unknown as Record<string, unknown>).gtag as
    | ((...args: unknown[]) => void)
    | undefined;
  if (!gtag) return;

  // GA4 purchase event (for Analytics reporting)
  gtag("event", "purchase", {
    transaction_id: params.bookingId,
    value: params.value,
    currency: params.currency || "USD",
    items: [
      {
        item_id: params.bookingId,
        item_name: "Junk Removal Service",
        price: params.value,
        quantity: 1,
      },
    ],
  });

  // Google Ads conversion (set NEXT_PUBLIC_GOOGLE_ADS_CONVERSION_LABEL)
  const conversionLabel = process.env.NEXT_PUBLIC_GOOGLE_ADS_CONVERSION_LABEL;
  const gadsId = process.env.NEXT_PUBLIC_GOOGLE_ADS_ID;
  if (gadsId && conversionLabel) {
    gtag("event", "conversion", {
      send_to: `${gadsId}/${conversionLabel}`,
      value: params.value,
      currency: params.currency || "USD",
      transaction_id: params.bookingId,
    });
  }
}
