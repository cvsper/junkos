import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "My Bookings",
  description:
    "View and manage your junk removal bookings. Track active pickups and review past jobs.",
  robots: {
    index: false,
    follow: false,
  },
};

export default function DashboardLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
