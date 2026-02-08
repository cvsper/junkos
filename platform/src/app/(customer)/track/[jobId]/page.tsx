import dynamic from "next/dynamic";

const TrackingPage = dynamic(
  () => import("@/components/tracking/tracking-page"),
  { ssr: false }
);

export default async function TrackJobPage({
  params,
}: {
  params: Promise<{ jobId: string }>;
}) {
  const { jobId } = await params;

  return <TrackingPage jobId={jobId} />;
}
