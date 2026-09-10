/** @type {import("next").NextConfig} */

// Hosts the image optimizer is allowed to fetch from.
//
// This list used to be `**.amazonaws.com`, `**.ufs.sh`, images.unsplash.com and
// images.pexels.com. A `**.` wildcard matches ANY depth of subdomain, so
// `**.amazonaws.com` let anyone point /_next/image at their own S3 bucket (or
// any other AWS-hosted host) and have our optimizer fetch and process it --
// which is the exposure behind the AVIF/libheif RCE in the August 2026
// advisory. Unsplash, Pexels and uploadthing were not referenced by any code.
//
// Narrowed to hosts we own (audit finding F28):
//   * our uploads bucket -- backend/storage.py serves job photos and operator
//     documents from https://<bucket>.s3.<region>.amazonaws.com/<key>
//   * our own web + API origins
//
// Set NEXT_PUBLIC_UPLOADS_HOST to the exact bucket host to tighten this to a
// single hostname; without it we fall back to a single-label wildcard, which
// still pins the S3 service and region rather than all of AWS.
const uploadsHost = process.env.NEXT_PUBLIC_UPLOADS_HOST;
const uploadsRegion = process.env.NEXT_PUBLIC_UPLOADS_REGION || "us-east-1";

const imageHosts = uploadsHost
  ? [uploadsHost]
  : [`*.s3.${uploadsRegion}.amazonaws.com`];

const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    const backendBase =
      process.env.NEXT_PUBLIC_API_URL || "https://junkos-backend.onrender.com";

    return [
      {
        source: "/api-proxy/:path*",
        destination: `${backendBase}/:path*`,
      },
    ];
  },
  images: {
    // AVIF is deliberately absent: the August 2026 advisory
    // (GHSA-2xp9-vwfh-vxw4) is an unauthenticated RCE via libheif when the
    // optimizer processes an attacker-supplied AVIF. 15.5.25 disables it
    // upstream; not requesting it is the belt to that braces.
    formats: ["image/webp"],
    remotePatterns: [
      ...imageHosts.map((hostname) => ({ protocol: "https", hostname })),
      // First-party origins (uploads fall back to being served by the API when
      // no S3 bucket is configured -- see backend/storage.py).
      { protocol: "https", hostname: "goumuve.com" },
      { protocol: "https", hostname: "www.goumuve.com" },
      { protocol: "https", hostname: "app.goumuve.com" },
      { protocol: "https", hostname: "junkos-backend.onrender.com" },
    ],
  },
};

export default nextConfig;
