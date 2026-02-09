import type { Metadata } from "next";
import { Inter, Space_Grotesk } from "next/font/google";
import "@/styles/globals.css";
import { Analytics } from "@/components/analytics";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
});

const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-space-grotesk",
  display: "swap",
});

const SITE_URL = process.env.NEXT_PUBLIC_SITE_URL || "https://junkos.app";

export const metadata: Metadata = {
  title: {
    default: "JunkOS | Premium Junk Removal in South Florida",
    template: "%s | JunkOS",
  },
  description:
    "Book professional junk removal in South Florida. Fast, reliable, affordable. Get instant quotes and real-time tracking.",
  metadataBase: new URL(SITE_URL),
  alternates: {
    canonical: "/",
  },
  openGraph: {
    title: "JunkOS | Premium Junk Removal in South Florida",
    description:
      "Book professional junk removal in South Florida. Fast, reliable, affordable. Get instant quotes and real-time tracking.",
    siteName: "JunkOS",
    type: "website",
    locale: "en_US",
    url: SITE_URL,
  },
  twitter: {
    card: "summary_large_image",
    title: "JunkOS | Premium Junk Removal in South Florida",
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
    <html lang="en" className={`${inter.variable} ${spaceGrotesk.variable}`}>
      <body className="font-sans antialiased bg-background text-foreground min-h-screen">
        {children}
        <Analytics />
      </body>
    </html>
  );
}
