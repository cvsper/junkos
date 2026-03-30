import type { Metadata } from "next";

export const metadata: Metadata = {
  title: {
    default: "Admin Dashboard",
    template: "%s | Umuve Admin",
  },
  description: "Umuve admin dashboard. Manage jobs, contractors, pricing, and operations.",
  robots: {
    index: false,
    follow: false,
  },
};

export default function AdminInnerLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
