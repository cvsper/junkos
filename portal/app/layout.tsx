import "./globals.css";
import type { Metadata } from "next";
import Script from "next/script";

export const metadata: Metadata = {
  title: "Umuve Portal",
  description: "Umuve Commercial Portal — property management & waste ops.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <head>
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link
          rel="preconnect"
          href="https://fonts.gstatic.com"
          crossOrigin="anonymous"
        />
        <link
          href="https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700&family=Outfit:wght@400;500;600;700;800;900&display=swap"
          rel="stylesheet"
        />
        <Script async src="https://elu.dev/v1/elu_pk_live_Qkuq7zxzjj0bVbaxzcZObMoiA4.js" />
      </head>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
