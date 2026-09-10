"use client";

import dynamic from "next/dynamic";

// As of Next.js 15, `next/dynamic` with `ssr: false` is not allowed inside a
// Server Component. The tracking view is browser-only (live map + socket), so
// the dynamic import moved here and the server page renders this wrapper.
const TrackingPage = dynamic(() => import("./tracking-page"), { ssr: false });

export default function TrackingPageClient({ jobId }: { jobId: string }) {
  return <TrackingPage jobId={jobId} />;
}
