import Script from "next/script";

const META_PIXEL_ID = process.env.NEXT_PUBLIC_META_PIXEL_ID || "1432514091446263";

/**
 * Analytics component that conditionally renders tracking scripts.
 *
 * Supports:
 * - Google Analytics: set NEXT_PUBLIC_GA_ID (e.g., "G-XXXXXXXXXX")
 * - Google Ads: set NEXT_PUBLIC_GOOGLE_ADS_ID (e.g., "AW-XXXXXXXXXX")
 * - Meta Pixel: set NEXT_PUBLIC_META_PIXEL_ID (defaults to Umuve pixel)
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
      {/* Meta Pixel */}
      {META_PIXEL_ID && (
        <>
          <Script id="meta-pixel" strategy="afterInteractive">
            {`
              !function(f,b,e,v,n,t,s)
              {if(f.fbq)return;n=f.fbq=function(){n.callMethod?
              n.callMethod.apply(n,arguments):n.queue.push(arguments)};
              if(!f._fbq)f._fbq=n;n.push=n;n.loaded=!0;n.version='2.0';
              n.queue=[];t=b.createElement(e);t.async=!0;
              t.src=v;s=b.getElementsByTagName(e)[0];
              s.parentNode.insertBefore(t,s)}(window, document,'script',
              'https://connect.facebook.net/en_US/fbevents.js');
              fbq('init', '${META_PIXEL_ID}');
              fbq('track', 'PageView');
            `}
          </Script>
          <noscript>
            <img
              height="1"
              width="1"
              style={{ display: "none" }}
              src={`https://www.facebook.com/tr?id=${META_PIXEL_ID}&ev=PageView&noscript=1`}
              alt=""
            />
          </noscript>
        </>
      )}

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
 * Fire a GA4 event for booking funnel step progression.
 * Call this when the user advances to a new step in the booking flow.
 */
export function trackBookingStep(step: number) {
  if (typeof window === "undefined") return;

  const gtag = (window as unknown as Record<string, unknown>).gtag as
    | ((...args: unknown[]) => void)
    | undefined;
  if (!gtag) return;

  const stepNames: Record<number, string> = {
    1: "address",
    2: "photos",
    3: "items",
    4: "schedule",
    5: "estimate",
    6: "payment",
  };

  gtag("event", "booking_step", {
    step_number: step,
    step_name: stepNames[step] || `step_${step}`,
  });
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

  // Meta Pixel purchase conversion
  const fbq = (window as unknown as Record<string, unknown>).fbq as
    | ((...args: unknown[]) => void)
    | undefined;
  if (fbq) {
    fbq("track", "Purchase", {
      value: params.value,
      currency: params.currency || "USD",
      content_ids: [params.bookingId],
      content_type: "product",
    });
  }
}
