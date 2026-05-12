// Server-side rewrite target. Distinct from NEXT_PUBLIC_API_URL (which
// the browser uses to build URLs hitting localhost so this proxy engages).
const PROXY_TARGET = process.env.PORTAL_PROXY_TARGET || "https://junkos-backend.onrender.com";

/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  async rewrites() {
    return [
      { source: "/portal/v1/:path*", destination: `${PROXY_TARGET}/portal/v1/:path*` },
    ];
  },
  async headers() {
    return [
      {
        source: "/(.*)",
        headers: [
          { key: "X-Frame-Options", value: "DENY" },
          { key: "X-Content-Type-Options", value: "nosniff" },
          { key: "Referrer-Policy", value: "strict-origin-when-cross-origin" },
        ],
      },
    ];
  },
};

export default nextConfig;
