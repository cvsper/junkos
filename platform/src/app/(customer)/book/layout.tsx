import type { Metadata } from "next";

export const metadata: Metadata = {
  title: "Book Your Pickup",
  description:
    "Schedule your junk removal pickup in South Florida. Choose your items, pick a time, and get an instant quote.",
  alternates: {
    canonical: "/book",
  },
};

export default function BookLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return children;
}
