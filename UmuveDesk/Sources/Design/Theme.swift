//  Theme.swift — Umuve Desk
//  The satin-grey system the web desk uses, in SwiftUI. Red means one thing
//  here: the line is not ringing to you. Green is on-clock, money, and book.
//
//  Type: the desk's Outfit/DM Sans ship as woff2 for the web; iOS wants
//  TTF/OTF. Until those are bundled, SF Pro at heavy weight with tight
//  tracking carries the same voice. (Follow-up: drop the TTFs in Resources
//  and swap `display()` to Font.custom("Outfit", ...).)

import SwiftUI

extension Color {
    init(hex: UInt32, alpha: Double = 1) {
        self.init(.sRGB, red: Double((hex >> 16) & 0xFF) / 255,
                  green: Double((hex >> 8) & 0xFF) / 255,
                  blue: Double(hex & 0xFF) / 255, opacity: alpha)
    }
    static let canvas = Color(hex: 0xE4E5E9)
    static let ink = Color(hex: 0x17181C)
    static let muted = Color(hex: 0x17181C, alpha: 0.64)
    static let faint = Color(hex: 0x17181C, alpha: 0.42)
    static let line = Color(hex: 0x17181C, alpha: 0.09)
    static let glass = Color.white.opacity(0.58)
    static let glassBorder = Color.white.opacity(0.78)
    static let raise = Color.white.opacity(0.80)
    static let go = Color(hex: 0x1F9D55)
    static let goPress = Color(hex: 0x18773F)
    static let stop = Color(hex: 0xC52222)
    static let dark = Color(hex: 0x26272C)
}

enum Type {
    /// The one big thing on a screen.
    static func display(_ size: CGFloat) -> Font { .system(size: size, weight: .heavy, design: .default) }
    static let title = Font.system(size: 26, weight: .bold)
    static let body = Font.system(size: 16, weight: .regular)
    static let bodyStrong = Font.system(size: 16, weight: .semibold)
    static let small = Font.system(size: 13.5, weight: .regular)
    static let smallStrong = Font.system(size: 13.5, weight: .semibold)
    static let button = Font.system(size: 17.5, weight: .bold)
}

/// One frosted panel rule, reused everywhere — same as the web desk.
struct Glass: ViewModifier {
    var padding: CGFloat = 18
    func body(content: Content) -> some View {
        content
            .padding(padding)
            .background(.ultraThinMaterial.opacity(0.9))
            .background(Color.glass)
            .overlay(RoundedRectangle(cornerRadius: 20, style: .continuous).stroke(Color.glassBorder, lineWidth: 1))
            .clipShape(RoundedRectangle(cornerRadius: 20, style: .continuous))
            .shadow(color: Color(hex: 0x181A22).opacity(0.14), radius: 24, y: 14)
    }
}
extension View { func glass(_ padding: CGFloat = 18) -> some View { modifier(Glass(padding: padding)) } }

/// Full-width pill. `tone` picks the colour; the label says what happens.
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
                Text(title).font(Type.button)
            }
            .frame(maxWidth: .infinity).frame(minHeight: 58)
            .foregroundStyle(fg)
            .background(bg, in: Capsule())
            .overlay(Capsule().stroke(border, lineWidth: tone == .quiet ? 1 : 0))
        }
        .disabled(busy)
        .shadow(color: shadow, radius: 16, y: 10)
    }
    private var bg: Color { switch tone { case .go: .go; case .dark: .dark; case .quiet: .clear; case .stop: .stop } }
    private var fg: Color { tone == .quiet ? .ink : .white }
    private var border: Color { Color.ink.opacity(0.22) }
    private var shadow: Color {
        switch tone { case .go: Color.go.opacity(0.45); case .stop: Color.stop.opacity(0.4)
                      case .dark: Color(hex: 0x181A22).opacity(0.3); case .quiet: .clear }
    }
}
