import type { Metadata } from "next";
import { DM_Sans, Outfit, JetBrains_Mono } from "next/font/google";
import "@/styles/globals.css";
import { Analytics } from "@/components/analytics";
import { PostHogProvider } from "@/components/providers/posthog-provider";

const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-dm-sans",
  display: "swap",
});

const outfit = Outfit({
  subsets: ["latin"],
  variable: "--font-outfit",
  display: "swap",
});

const jetbrainsMono = JetBrains_Mono({
  subsets: ["latin"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://goumuve.com";

export const metadata: Metadata = {
  icons: {
    icon: "/logo.png",
    apple: "/logo.png",
  },
  title: {
    default: "Umuve | Premium Junk Removal in South Florida",
    template: "%s | Umuve",
  },
  description:
    "Book professional junk removal in South Florida. Fast, reliable, affordable. Get instant quotes and real-time tracking.",
  metadataBase: new URL(SITE_URL),
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "Umuve | Premium Junk Removal in South Florida",
    description:
      "Book professional junk removal in South Florida. Fast, reliable, affordable. Get instant quotes and real-time tracking.",
    siteName: "Umuve",
    type: "website",
    locale: "en_US",
    url: SITE_URL,
  },
  twitter: {
    card: "summary_large_image",
    title: "Umuve | Premium Junk Removal in South Florida",
    description:
      "Book professional junk removal in South Florida. Fast, reliable, affordable. Get instant quotes and real-time tracking.",
  },
  robots: {
    index: true,
    follow: true,
    googleBot: {
      index: true,
      follow: true,
      "max-video-preview": -1,
      "max-image-preview": "large",
      "max-snippet": -1,
    },
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${dmSans.variable} ${outfit.variable} ${jetbrainsMono.variable}`}>
      <body className="font-sans antialiased bg-background text-foreground min-h-screen">
        <PostHogProvider>
          {children}
        </PostHogProvider>
        <Analytics />
      </body>
    </html>
  );
}
