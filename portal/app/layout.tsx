import "./globals.css";
import type { Metadata } from "next";

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
      <body className="font-sans antialiased">{children}</body>
    </html>
  );
}
