import TrackingPageClient from "@/components/tracking/tracking-page-client";

export default async function TrackJobPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;

  return <TrackingPageClient jobId={jobId} />;
}
