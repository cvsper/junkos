import type { Metadata } from "next";
import GuestTracking from "@/components/tracking/guest-tracking";

export const metadata: Metadata = {
  title: "Track your pickup — umuve",
  description: "Live status for your junk removal pickup.",
};

export default async function TrackByCodePage({
  params,
}: {
  params: Promise<{ code: string }>;
}) {
  const { code } = await params;
  return <GuestTracking code={code} />;
}
