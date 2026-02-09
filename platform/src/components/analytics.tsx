import Script from "next/script";

/**
 * Analytics component that conditionally renders tracking scripts.
 *
 * Supports two providers:
 * - Google Analytics: set NEXT_PUBLIC_GA_ID (e.g., "G-XXXXXXXXXX")
 * - Plausible Analytics: set NEXT_PUBLIC_PLAUSIBLE_DOMAIN (e.g., "junkos.app")
 *
 * If neither env var is set, this component renders nothing (safe for dev).
 */
export function Analytics() {
  const gaId = process.env.NEXT_PUBLIC_GA_ID;
  const plausibleDomain = process.env.NEXT_PUBLIC_PLAUSIBLE_DOMAIN;

  return (
    <>
      {/* Google Analytics */}
      {gaId && (
        <>
          <Script
            src={`https://www.googletagmanager.com/gtag/js?id=${gaId}`}
            strategy="afterInteractive"
          />
          <Script id="google-analytics" strategy="afterInteractive">
            {`
              window.dataLayer = window.dataLayer || [];
              function gtag(){dataLayer.push(arguments);}
              gtag('js', new Date());
              gtag('config', '${gaId}');
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
