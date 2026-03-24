import { Metadata } from "next";

export const metadata: Metadata = {
  title: "Umuve Blog — Junk Removal Tips & Guides",
  description:
    "Expert tips on decluttering, junk removal costs, recycling, moving preparation, and home organization from South Florida's premium junk removal service.",
};

export default function BlogLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return <>{children}</>;
}
