import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Analytics",
  description: "Insights and metrics for your junk removal operations.",
};

export default function AnalyticsLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
