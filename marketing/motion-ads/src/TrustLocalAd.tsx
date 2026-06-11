import React from "react";
import {
  AbsoluteFill,
  Img,
  staticFile,
  interpolate,
  spring,
  useCurrentFrame,
  useVideoConfig,
  Easing,
  random,
} from "remotion";
import { loadFont as loadSaira } from "@remotion/google-fonts/SairaCondensed";
import { loadFont as loadHanken } from "@remotion/google-fonts/HankenGrotesk";

const saira = loadSaira("normal", { weights: ["600", "700", "800", "900"] });
const hanken = loadHanken("normal", { weights: ["500"] });

// ---- approved design tokens (trust-local.html) ----
const INK = "#10242E";
const INK2 = "#0B1B23";
const SAND = "#F3E7D2";
const SAND_DIM = "#D8C7AB";
const RED = "#E23A2E";
const RED_DEEP = "#B5271D";
const SEA = "#5BC2B0";
const LINE = "rgba(243,231,210,.16)";

const GRAIN =
  "url(\"data:image/svg+xml;utf8,<svg xmlns='http://www.w3.org/2000/svg' width='160' height='160'><filter id='n'><feTurbulence type='fractalNoise' baseFrequency='0.85' numOctaves='2' stitchTiles='stitch'/></filter><rect width='100%25' height='100%25' filter='url(%23n)'/></svg>\")";

// Reveal-from-baseline mask for headline lines.
const ClipLine: React.FC<{
  at: number;
  children: React.ReactNode;
  color?: string;
}> = ({ at, children, color }) => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  const s = spring({
    frame: frame - at,
    fps,
    config: { damping: 16, stiffness: 110, mass: 0.9 },
  });
  const y = interpolate(s, [0, 1], [110, 0]);
  return (
    <div style={{ overflow: "hidden", paddingBottom: 6, marginBottom: -6 }}>
      <div style={{ transform: `translateY(${y}%)`, color }}>{children}</div>
    </div>
  );
};

export const TrustLocalAd: React.FC = () => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();

  const pop = (at: number, damping = 13, stiffness = 140) =>
    spring({ frame: frame - at, fps, config: { damping, stiffness } });

  const fadeUp = (at: number, dur = 16, dist = 26) => ({
    opacity: interpolate(frame, [at, at + dur], [0, 1], {
      extrapolateLeft: "clamp",
      extrapolateRight: "clamp",
    }),
    transform: `translateY(${interpolate(
      frame,
      [at, at + dur],
      [dist, 0],
      { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) }
    )}px)`,
  });

  // --- background life ---
  const ghostDrift = interpolate(frame, [0, 210], [40, -60]);
  const topoDraw = interpolate(frame, [0, 80], [1, 0], {
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.quad),
  });
  // brief atmosphere pulse when "GONE TODAY." lands
  const topoPulse = interpolate(frame, [70, 78, 96], [0.5, 0.85, 0.5], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const grainShift = Math.floor(random(`g${frame}`) * 160);

  // --- logo (f0–18) ---
  const markS = pop(2);
  const wordX = interpolate(pop(8, 18, 120), [0, 1], [-36, 0]);
  const wordO = interpolate(frame, [8, 18], [0, 1], { extrapolateRight: "clamp" });
  const locO = interpolate(frame, [14, 26], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  // --- kicker (f20): tracking tightens as it fades in ---
  const kickerO = interpolate(frame, [20, 34], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });
  const kickerTrack = interpolate(frame, [20, 44], [0.8, 0.34], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
    easing: Easing.out(Easing.cubic),
  });

  // --- badges (f104+, stagger 8) ---
  const badges = ["Upfront pricing", "Same-day", "Licensed & insured", "We do the lifting"];

  // --- footer (f138+) ---
  const footS = pop(138, 15, 100);
  const footY = interpolate(footS, [0, 1], [120, 0]);
  const big25 = pop(146, 11, 170); // extra punch on "$25 OFF"
  const codeFlip = pop(154, 14, 120);
  const ctaS = pop(150, 12, 130);
  // CTA breathing once landed
  const breathe =
    frame > 175 ? 1 + 0.025 * Math.sin(((frame - 175) / 45) * Math.PI * 2) : 1;
  const arrowNudge =
    frame > 175 ? 6 * Math.max(0, Math.sin(((frame - 175) / 45) * Math.PI * 2)) : 0;
  const urlO = interpolate(frame, [152, 168], [0, 1], {
    extrapolateLeft: "clamp",
    extrapolateRight: "clamp",
  });

  const sairaStyle = (w: number) => ({
    fontFamily: `'${saira.fontFamily}', sans-serif`,
    fontWeight: w as any,
  });

  return (
    <AbsoluteFill
      style={{
        background: `radial-gradient(120% 90% at 50% -10%, #1A3A47 0%, ${INK} 42%, ${INK2} 100%)`,
        color: SAND,
        overflow: "hidden",
      }}
    >
      {/* topo coastline lines */}
      <svg
        viewBox="0 0 1080 1920"
        preserveAspectRatio="none"
        style={{ position: "absolute", inset: 0, width: "100%", height: "100%", opacity: topoPulse }}
      >
        {[
          "M-50,520 C200,440 400,600 620,520 S1000,400 1140,520",
          "M-50,620 C200,540 400,700 620,620 S1000,500 1140,620",
          "M-50,1480 C220,1400 460,1560 700,1480 S1020,1360 1140,1480",
          "M-50,1580 C220,1500 460,1660 700,1580 S1020,1460 1140,1580",
        ].map((d, i) => (
          <path
            key={i}
            d={d}
            fill="none"
            stroke={LINE}
            strokeWidth={2}
            strokeDasharray={1400}
            strokeDashoffset={1400 * topoDraw}
          />
        ))}
      </svg>

      {/* ghost watermark, drifting */}
      <div
        style={{
          position: "absolute",
          top: 1920 + ghostDrift,
          left: -40,
          fontSize: 340,
          ...sairaStyle(900),
          textTransform: "uppercase",
          color: "rgba(243,231,210,.035)",
          lineHeight: 0.8,
          whiteSpace: "nowrap",
          letterSpacing: "-0.02em",
          transform: "rotate(-90deg)",
          transformOrigin: "left top",
        }}
      >
        Palm Beach
      </div>

      {/* content */}
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "flex",
          flexDirection: "column",
          padding: "96px 88px",
          zIndex: 5,
        }}
      >
        {/* logo lockup */}
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <Img
            src={staticFile("umuve-logo.png")}
            style={{
              height: 84,
              width: "auto",
              transform: `scale(${markS})`,
              filter: "drop-shadow(0 10px 30px rgba(226,58,46,.35))",
            }}
          />
          <div
            style={{
              ...sairaStyle(800),
              fontSize: 34,
              letterSpacing: "0.02em",
              transform: `translateX(${wordX}px)`,
              opacity: wordO,
            }}
          >
            umuve
          </div>
          <div
            style={{
              marginLeft: "auto",
              ...sairaStyle(600),
              letterSpacing: "0.22em",
              fontSize: 17,
              color: SEA,
              textTransform: "uppercase",
              display: "flex",
              alignItems: "center",
              gap: 11,
              opacity: locO,
            }}
          >
            <span
              style={{
                width: 9,
                height: 9,
                borderRadius: "50%",
                background: SEA,
                boxShadow: `0 0 ${14 * locO}px ${SEA}`,
              }}
            />
            Palm Beach
          </div>
        </div>

        {/* headline block */}
        <div style={{ marginTop: "auto" }}>
          <div
            style={{
              ...sairaStyle(600),
              letterSpacing: `${kickerTrack}em`,
              fontSize: 20,
              color: SAND_DIM,
              textTransform: "uppercase",
              marginBottom: 26,
              opacity: kickerO,
            }}
          >
            Same-day junk removal
          </div>

          <h1
            style={{
              ...sairaStyle(900),
              fontSize: 150,
              lineHeight: 0.9,
              letterSpacing: "-0.005em",
              textTransform: "uppercase",
              margin: 0,
            }}
          >
            <ClipLine at={34}>Licensed.</ClipLine>
            <ClipLine at={46}>Insured.</ClipLine>
            <ClipLine at={60} color={RED}>
              Gone today.
            </ClipLine>
          </h1>

          <p
            style={{
              fontFamily: `'${hanken.fontFamily}', sans-serif`,
              fontWeight: 500,
              color: SAND_DIM,
              maxWidth: "24ch",
              marginTop: 30,
              lineHeight: 1.45,
              fontSize: 33,
              ...fadeUp(88),
            }}
          >
            Estate cleanout, garage, reno debris, one heavy item — upfront
            price, you don't lift a thing.
          </p>

          {/* badges */}
          <div style={{ display: "flex", flexWrap: "wrap", gap: 14, marginTop: 44 }}>
            {badges.map((b, i) => {
              const at = 104 + i * 8;
              const s = pop(at, 12, 160);
              const dotOn = interpolate(frame, [at + 6, at + 12], [0, 1], {
                extrapolateLeft: "clamp",
                extrapolateRight: "clamp",
              });
              return (
                <div
                  key={b}
                  style={{
                    ...sairaStyle(700),
                    textTransform: "uppercase",
                    letterSpacing: "0.07em",
                    fontSize: 22,
                    color: SAND,
                    padding: "13px 22px",
                    border: `1.5px solid ${LINE}`,
                    borderRadius: 100,
                    display: "flex",
                    alignItems: "center",
                    gap: 11,
                    background: "rgba(243,231,210,.04)",
                    transform: `scale(${interpolate(s, [0, 1], [0.6, 1])})`,
                    opacity: s,
                  }}
                >
                  <span
                    style={{
                      width: 8,
                      height: 8,
                      borderRadius: "50%",
                      background: SEA,
                      opacity: dotOn,
                      boxShadow: `0 0 ${10 * dotOn}px ${SEA}`,
                    }}
                  />
                  {b}
                </div>
              );
            })}
          </div>
        </div>

        {/* offer + CTA footer */}
        <div
          style={{
            marginTop: "auto",
            display: "flex",
            alignItems: "flex-end",
            justifyContent: "space-between",
            gap: 32,
            paddingTop: 54,
            transform: `translateY(${footY}px)`,
            opacity: footS,
          }}
        >
          <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
            <div
              style={{
                ...sairaStyle(900),
                textTransform: "uppercase",
                lineHeight: 0.92,
                fontSize: 74,
              }}
            >
              <b
                style={{
                  color: RED,
                  display: "inline-block",
                  transform: `scale(${interpolate(big25, [0, 1], [0.7, 1])})`,
                  transformOrigin: "left bottom",
                }}
              >
                $25 off
              </b>{" "}
              your
              <br />
              first pickup
            </div>
            <div
              style={{
                ...sairaStyle(600),
                letterSpacing: "0.16em",
                fontSize: 21,
                color: SAND_DIM,
                textTransform: "uppercase",
              }}
            >
              code{" "}
              <i
                style={{
                  fontStyle: "normal",
                  color: SAND,
                  background: RED_DEEP,
                  padding: "3px 12px",
                  borderRadius: 7,
                  letterSpacing: "0.22em",
                  marginLeft: 6,
                  display: "inline-block",
                  transform: `perspective(500px) rotateX(${interpolate(
                    codeFlip,
                    [0, 1],
                    [90, 0]
                  )}deg)`,
                  transformOrigin: "center bottom",
                }}
              >
                PBC25
              </i>
            </div>
          </div>

          <div
            style={{
              flex: "none",
              ...sairaStyle(800),
              textTransform: "uppercase",
              letterSpacing: "0.04em",
              background: RED,
              color: SAND,
              padding: "24px 40px",
              borderRadius: 100,
              boxShadow: `0 ${16 * ctaS}px ${40 * ctaS}px rgba(226,58,46,.4), inset 0 2px 0 rgba(255,255,255,.22)`,
              display: "flex",
              alignItems: "center",
              gap: 14,
              whiteSpace: "nowrap",
              fontSize: 36,
              transform: `scale(${interpolate(ctaS, [0, 1], [0.5, 1]) * breathe})`,
              opacity: ctaS,
            }}
          >
            Get Offer
            <span style={{ fontWeight: 900, transform: `translateX(${arrowNudge}px)` }}>
              →
            </span>
          </div>
        </div>
      </div>

      {/* url */}
      <div
        style={{
          position: "absolute",
          left: 88,
          bottom: 54,
          zIndex: 5,
          ...sairaStyle(700),
          letterSpacing: "0.14em",
          fontSize: 22,
          color: SAND_DIM,
          textTransform: "uppercase",
          opacity: urlO,
        }}
      >
        goumuve.com
      </div>

      {/* living grain */}
      <AbsoluteFill
        style={{
          zIndex: 6,
          pointerEvents: "none",
          opacity: 0.06,
          mixBlendMode: "overlay",
          backgroundImage: GRAIN,
          backgroundPosition: `${grainShift}px ${grainShift}px`,
        }}
      />
    </AbsoluteFill>
  );
};
