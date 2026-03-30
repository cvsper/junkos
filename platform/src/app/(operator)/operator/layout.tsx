import type { Metadata } from "next";

export const metadata: Metadata = {
  title: {
    default: "Operator Portal",
    template: "%s | Umuve Operator",
  },
  description: "Umuve operator portal. Manage your fleet, delegate jobs, and track earnings.",
  robots: {
    index: false,
    follow: false,
  },
};

export default function OperatorInnerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
