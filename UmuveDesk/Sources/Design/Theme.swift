//  Theme.swift — Umuve Desk
//  The web desk's frosted-glass-on-satin-grey material, done properly on iOS.
//  Outfit carries every big line; DM Sans everything else. Red means one thing:
//  the line is not ringing to you. Green is on-clock, money, and book.

import SwiftUI

// MARK: colour

extension Color {
    init(hex: UInt32, alpha: Double = 1) {
        self.init(.sRGB, red: Double((hex >> 16) & 0xFF) / 255, green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255, opacity: alpha)
    }
    static let canvas = Color(hex: 0xE4E5E9)
    static let ink = Color(hex: 0x17181C)
    static let muted = Color(hex: 0x17181C, alpha: 0.64)
    static let faint = Color(hex: 0x17181C, alpha: 0.42)
    static let line = Color(hex: 0x17181C, alpha: 0.09)
    static let go = Color(hex: 0x1F9D55)
    static let goPress = Color(hex: 0x18773F)
    static let stop = Color(hex: 0xC52222)
    static let info = Color(hex: 0x3B6FD9)
    static let warn = Color(hex: 0xB8780C)
    static let dark = Color(hex: 0x26272C)
}

// MARK: type

enum Type {
    static func display(_ size: CGFloat) -> Font { .custom("Outfit-ExtraBold", size: size) }
    static func heading(_ size: CGFloat) -> Font { .custom("Outfit-Bold", size: size) }
    static let wordmark = Font.custom("Outfit-Bold", size: 17)
    static let body = Font.custom("DMSans-Regular", size: 16)
    static let bodyMedium = Font.custom("DMSans-Medium", size: 16)
    static let bodyStrong = Font.custom("DMSans-SemiBold", size: 16)
    static let small = Font.custom("DMSans-Regular", size: 13.5)
    static let smallMedium = Font.custom("DMSans-Medium", size: 13.5)
    static let smallStrong = Font.custom("DMSans-SemiBold", size: 13.5)
    static let button = Font.custom("DMSans-Bold", size: 17)
    static let chip = Font.custom("DMSans-SemiBold", size: 12.5)
}

// MARK: the canvas — satin grey with the same five lights the web desk uses

struct Canvas: View {
    var body: some View {
        GeometryReader { g in
            let w = g.size.width, h = g.size.height
            ZStack {
                Color.canvas
                glow(.white.opacity(0.95), w * 0.62, h * 0.46, x: 0.18, y: 0.12, in: g.size)
                glow(.white.opacity(0.75), w * 0.72, h * 0.52, x: 0.82, y: 0.26, in: g.size)
                glow(.white.opacity(0.60), w * 0.58, h * 0.56, x: 0.70, y: 0.88, in: g.size)
                glow(Color.stop.opacity(0.07), w * 0.50, h * 0.40, x: 0.08, y: 0.78, in: g.size)
                glow(Color.info.opacity(0.06), w * 0.42, h * 0.40, x: 0.92, y: 0.92, in: g.size)
            }
        }
        .ignoresSafeArea()
    }
    private func glow(_ c: Color, _ w: CGFloat, _ h: CGFloat, x: CGFloat, y: CGFloat, in s: CGSize) -> some View {
        Ellipse().fill(c).frame(width: w, height: h).blur(radius: 48)
            .position(x: s.width * x, y: s.height * y)
    }
}

// MARK: glass — one panel rule, reused everywhere

struct Glass: ViewModifier {
    var padding: CGFloat = 18
    var radius: CGFloat = 22
    func body(content: Content) -> some View {
        content
            .padding(padding)
            .background {
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .fill(Color.white.opacity(0.58))
                    .background(.ultraThinMaterial, in: RoundedRectangle(cornerRadius: radius, style: .continuous))
            }
            .overlay {
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .strokeBorder(Color.white.opacity(0.78), lineWidth: 1)
            }
            .overlay(alignment: .top) {
                // the inner top highlight that makes glass read as glass
                RoundedRectangle(cornerRadius: radius, style: .continuous)
                    .trim(from: 0.02, to: 0.23)
                    .stroke(Color.white.opacity(0.9), lineWidth: 1.2)
                    .padding(1)
                    .blendMode(.plusLighter)
            }
            .shadow(color: Color(hex: 0x181A22).opacity(0.10), radius: 34, y: 22)
            .shadow(color: Color(hex: 0x181A22).opacity(0.06), radius: 6, y: 2)
    }
}
extension View { func glass(_ padding: CGFloat = 18, radius: CGFloat = 22) -> some View { modifier(Glass(padding: padding, radius: radius)) } }

// MARK: small parts

/// The U-truck mark with the wordmark beside it.
struct BrandRow: View {
    var subtitle: String? = nil
    var body: some View {
        HStack(spacing: 9) {
            Image("BrandMark").resizable().scaledToFit().frame(width: 28, height: 28)
                .clipShape(RoundedRectangle(cornerRadius: 8, style: .continuous))
            Text("umuve").font(Type.wordmark).foregroundStyle(Color.ink).tracking(-0.3)
            if let s = subtitle {
                Text(s).font(Type.wordmark).foregroundStyle(Color.faint).tracking(-0.3)
            }
        }
    }
}

/// A coloured dot that says what happened to a call. Colour is the label.
struct Dot: View {
    let color: Color
    var size: CGFloat = 8
    var glow = false
    var body: some View {
        Circle().fill(color).frame(width: size, height: size)
            .overlay { if glow { Circle().stroke(color.opacity(0.22), lineWidth: 5) } }
    }
}

extension Color {
    static func forDisposition(_ d: String?) -> Color {
        switch (d ?? "").lowercased() {
        case "booked", "answered_by_human", "quoted": return .go
        case "missed", "choice", "voicemail": return .stop
        case "callback", "callback_menu": return .warn
        case "maya": return .info
        default: return Color.faint
        }
    }
}

/// A small pill for where a call came from.
struct Chip: View {
    let text: String
    var tint: Color = .ink
    var body: some View {
        HStack(spacing: 6) {
            Dot(color: tint, size: 6)
            Text(text).font(Type.chip).foregroundStyle(Color.ink).lineLimit(1)
        }
        .padding(.horizontal, 10).padding(.vertical, 5)
        .background(Color.white.opacity(0.7), in: Capsule())
        .overlay(Capsule().strokeBorder(Color.white.opacity(0.85), lineWidth: 1))
    }
}

/// Full-width pill. The label says what happens; the tone says how much.
struct PillButton: View {
    enum Tone { case go, dark, quiet, stop }
    let title: String
    var tone: Tone = .go
    var busy = false
    let action: () -> Void

    var body: some View {
        Button(action: action) {
            HStack(spacing: 10) {
                if busy { ProgressView().tint(fg) }
                Text(title).font(Type.button).tracking(-0.1)
            }
            .frame(maxWidth: .infinity).frame(minHeight: 56)
            .foregroundStyle(fg)
            .background(bg, in: Capsule())
            .overlay(Capsule().strokeBorder(border, lineWidth: tone == .quiet ? 1 : 0))
        }
        .buttonStyle(.plain)
        .disabled(busy)
        .shadow(color: shadow, radius: 18, y: 10)
    }
    private var bg: Color { switch tone { case .go: .go; case .dark: .dark; case .quiet: Color.white.opacity(0.72); case .stop: .stop } }
    private var fg: Color { tone == .quiet ? .ink : .white }
    private var border: Color { Color.white.opacity(0.9) }
    private var shadow: Color {
        switch tone { case .go: Color.go.opacity(0.42); case .stop: Color.stop.opacity(0.36)
                      case .dark: Color(hex: 0x181A22).opacity(0.28); case .quiet: Color(hex: 0x181A22).opacity(0.08) }
    }
}

/// Section title in Outfit with an optional count.
struct SectionTitle: View {
    let text: String
    var count: Int? = nil
    var body: some View {
        HStack(alignment: .firstTextBaseline, spacing: 10) {
            Text(text).font(Type.heading(21)).tracking(-0.5).foregroundStyle(Color.ink)
            if let c = count, c > 0 {
                Text("\(c)").font(Type.smallStrong).foregroundStyle(Color.muted)
                    .padding(.horizontal, 8).padding(.vertical, 2)
                    .background(Color.ink.opacity(0.07), in: Capsule())
            }
            Spacer()
        }
        .padding(.top, 30).padding(.bottom, 10)
    }
}

struct DeskField: TextFieldStyle {
    func _body(configuration: TextField<Self._Label>) -> some View {
        configuration
            .font(Type.body)
            .padding(.horizontal, 16).frame(minHeight: 52)
            .background(Color.white.opacity(0.8), in: RoundedRectangle(cornerRadius: 14, style: .continuous))
            .overlay(RoundedRectangle(cornerRadius: 14, style: .continuous).strokeBorder(Color.ink.opacity(0.10)))
    }
}

func shortTime(_ iso: String?) -> String {
    guard let iso else { return "" }
    let f = ISO8601DateFormatter(); f.formatOptions = [.withInternetDateTime, .withFractionalSeconds]
    var d = f.date(from: iso)
    if d == nil { f.formatOptions = [.withInternetDateTime]; d = f.date(from: iso) }
    if d == nil { let g = DateFormatter(); g.dateFormat = "yyyy-MM-dd'T'HH:mm:ss.SSSSSS"; g.timeZone = TimeZone(identifier: "UTC"); d = g.date(from: iso) }
    guard let d else { return "" }
    let out = DateFormatter(); out.dateFormat = Calendar.current.isDateInToday(d) ? "h:mm a" : "EEE h:mm a"
    return out.string(from: d)
}
