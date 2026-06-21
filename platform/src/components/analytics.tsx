import Script from "next/script";

const META_PIXEL_ID = process.env.NEXT_PUBLIC_META_PIXEL_ID || "1785795592383973";

/**
 * Analytics component that conditionally renders tracking scripts.
 *
 * Supports:
 * - Google Analytics: set NEXT_PUBLIC_GA_ID (e.g., "G-XXXXXXXXXX")
 * - Google Ads: set NEXT_PUBLIC_GOOGLE_ADS_ID (e.g., "AW-XXXXXXXXXX")
 * - Meta Pixel: set NEXT_PUBLIC_META_PIXEL_ID (defaults to Umuve pixel)
 * - Plausible Analytics: set NEXT_PUBLIC_PLAUSIBLE_DOMAIN (e.g., "goumuve.com")
 * - Umami Analytics: set NEXT_PUBLIC_UMAMI_WEBSITE_ID + NEXT_PUBLIC_UMAMI_URL
 *
 * If no env vars are set, this component renders nothing (safe for dev).
 */
export function Analytics() {
  const gaId = process.env.NEXT_PUBLIC_GA_ID;
  const gadsId = process.env.NEXT_PUBLIC_GOOGLE_ADS_ID;
  const plausibleDomain = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;
  const umamiWebsiteId = process.env.NEXT_PUBLIC_UMAMI_WEBSITE_ID;
  const umamiUrl = process.env.NEXT_PUBLIC_UMAMI_URL;

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

      {/* Umami Analytics */}
      {umamiWebsiteId && umamiUrl && (
        <Script
          defer
          data-website-id={umamiWebsiteId}
          src={`${umamiUrl}/script.js`}
          strategy="afterInteractive"
        />
      )}

      {/* ELU Analytics */}
      <Script
        async
        src="https://elu.dev/v1/elu_pk_live_Qkuq7zxzjj0bVbaxzcZObMoiA4.js"
        strategy="afterInteractive"
      />
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

  // Meta Pixel purchase conversion.
  // eventID matches the server-side Conversions API event ("purchase_<id>") so
  // Meta deduplicates the browser + server events into one conversion.
  const fbq = (window as unknown as Record<string, unknown>).fbq as
    | ((...args: unknown[]) => void)
    | undefined;
  if (fbq) {
    fbq(
      "track",
      "Purchase",
      {
        value: params.value,
        currency: params.currency || "USD",
        content_ids: [params.bookingId],
        content_type: "product",
      },
      { eventID: `purchase_${params.bookingId}` }
    );
  }
}

/**
 * Fire Meta InitiateCheckout — the early optimization event the ad campaign
 * uses before Purchase volume is high enough (see palm-beach-meta-launch.md).
 * Call when the customer reaches the payment step of the booking funnel.
 */
export function trackInitiateCheckout(params?: {
  value?: number;
  currency?: string;
  bookingId?: string;
}) {
  if (typeof window === "undefined") return;
  const fbq = (window as unknown as Record<string, unknown>).fbq as
    | ((...args: unknown[]) => void)
    | undefined;
  if (fbq) {
    // Pass eventID checkout_<bookingId> so this dedupes with the server-side
    // CAPI InitiateCheckout (fired from create-intent-simple). Without a
    // bookingId there's nothing to dedupe against, so omit it.
    const opts = params?.bookingId
      ? { eventID: `checkout_${params.bookingId}` }
      : undefined;
    fbq(
      "track",
      "InitiateCheckout",
      {
        value: params?.value ?? 0,
        currency: params?.currency || "USD",
        ...(params?.bookingId
          ? { content_ids: [params.bookingId], content_type: "product" }
          : {}),
      },
      opts
    );
  }
}

export function trackLead() {
  if (typeof window === "undefined") return;
  const fbq = (window as unknown as Record<string, unknown>).fbq as
    | ((...args: unknown[]) => void)
    | undefined;
  if (fbq) {
    fbq("track", "Lead");
  }
}
