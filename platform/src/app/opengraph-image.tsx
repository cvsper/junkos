import { ImageResponse } from "next/og";

export const runtime = "edge";
export const alt = "Umuve - Premium Junk Removal in South Florida";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          background: "linear-gradient(135deg, #dc2626 0%, #991b1b 100%)",
          width: "100%",
          height: "100%",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          fontFamily: "system-ui, sans-serif",
          color: "white",
          padding: "60px",
        }}
      >
        <div
          style={{
            fontSize: 72,
            fontWeight: 800,
            letterSpacing: "-2px",
            marginBottom: 16,
          }}
        >
          Umuve
        </div>
        <div
          style={{
            fontSize: 32,
            fontWeight: 400,
            opacity: 0.9,
            marginBottom: 40,
          }}
        >
          Hauling Made Simple
        </div>
        <div
          style={{
            display: "flex",
            gap: 32,
            fontSize: 20,
            opacity: 0.85,
          }}
        >
          <span>Same-Day Service</span>
          <span>•</span>
          <span>Upfront Pricing</span>
          <span>•</span>
          <span>South Florida</span>
        </div>
        <div
          style={{
            position: "absolute",
            bottom: 40,
            fontSize: 18,
            opacity: 0.7,
          }}
        >
          goumuve.com
        </div>
      </div>
    ),
    { ...size }
  );
}
