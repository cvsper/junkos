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
        <Script async src="https://elu.dev/v1/elu_pk_live_Qkuq7zxzjj0bVbaxzcZObMoiA4.js" />
      </head>
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
