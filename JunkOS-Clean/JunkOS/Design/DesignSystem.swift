//
//  DesignSystem.swift
//  Umuve
//
//  Unified red design system.
//

import SwiftUI

// MARK: - Colors
extension Color {
    // Primary — red
    static let umuvePrimary = Color(hex: "DC2626")
    static let umuvePrimaryLight = Color(hex: "EF4444")
    static let umuvePrimaryDark = Color(hex: "B91C1C")
    static let umuveSecondary = Color(hex: "EF4444")
    static let umuveCTA = Color(hex: "DC2626")

    // Backgrounds
    static let umuveBackground = Color(hex: "FEF2F2")
    static let umuveSurface = Color.white
    static let umuveSurfaceElevated = Color(hex: "FEE2E2")

    // Aliases for legacy references
    static let loadUpGreen = Color(hex: "DC2626")
    static let loadUpGreenLight = Color(hex: "EF4444")
    static let loadUpGreenDark = Color(hex: "B91C1C")

    // Category card colors
    static let categoryBlue = Color(hex: "3B82F6")
    static let categoryYellow = Color(hex: "FBBF24")
    static let categoryPink = Color(hex: "EC4899")
    static let categoryGreen = Color(hex: "DC2626")
    static let categoryPurple = Color(hex: "8B5CF6")
    static let categoryOrange = Color(hex: "F97316")

    // Text colors
    static let umuveText = Color(hex: "0F172A")
    static let umuveTextMuted = Color(hex: "64748B")
    static let umuveTextTertiary = Color(hex: "94A3B8")

    // Semantic
    static let umuveSuccess = Color(hex: "22C55E")
    static let umuveWarning = Color(hex: "F59E0B")
    static let umuveError = Color(hex: "EF4444")
    static let umuveInfo = Color(hex: "3B82F6")

    // UI colors
    static let umuveBorder = Color(hex: "E2E8F0")
    static let umuveDivider = Color(hex: "F1F5F9")
    static let umuveWhite = Color.white

    // Helper for hex colors
    init(hex: String) {
        let hex = hex.trimmingCharacters(in: CharacterSet.alphanumerics.inverted)
        var int: UInt64 = 0
        Scanner(string: hex).scanHexInt64(&int)
        let a, r, g, b: UInt64
        switch hex.count {
        case 3:
            (a, r, g, b) = (255, (int >> 8) * 17, (int >> 4 & 0xF) * 17, (int & 0xF) * 17)
        case 6:
            (a, r, g, b) = (255, int >> 16, int >> 8 & 0xFF, int & 0xFF)
        case 8:
            (a, r, g, b) = (int >> 24, int >> 16 & 0xFF, int >> 8 & 0xFF, int & 0xFF)
        default:
            (a, r, g, b) = (255, 0, 0, 0)
        }
        self.init(
            .sRGB,
            red: Double(r) / 255,
            green: Double(g) / 255,
            blue:  Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - Typography
struct UmuveTypography {
    static let displayFont = Font.system(size: 34, weight: .bold, design: .rounded)
    static let h1Font = Font.system(size: 28, weight: .bold, design: .rounded)
    static let h2Font = Font.system(size: 22, weight: .semibold, design: .rounded)
    static let h3Font = Font.system(size: 18, weight: .semibold)
    static let bodyFont = Font.system(size: 16, weight: .regular)
    static let bodySmallFont = Font.system(size: 14, weight: .regular)
    static let captionFont = Font.system(size: 13, weight: .medium)
    static let smallFont = Font.system(size: 11, weight: .medium)
    static let priceFont = Font.system(size: 24, weight: .bold, design: .rounded)
}

// MARK: - Spacing
struct UmuveSpacing {
    static let tiny: CGFloat = 4
    static let small: CGFloat = 8
    static let medium: CGFloat = 12
    static let normal: CGFloat = 16
    static let large: CGFloat = 20
    static let xlarge: CGFloat = 24
    static let xxlarge: CGFloat = 32
    static let huge: CGFloat = 48
}

// MARK: - Corner Radius
struct UmuveRadius {
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 16
    static let xl: CGFloat = 20
    static let full: CGFloat = 999
}

// MARK: - Reusable Components

// Primary button style
struct UmuvePrimaryButtonStyle: ButtonStyle {
    var isEnabled: Bool = true

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(UmuveTypography.bodyFont.weight(.semibold))
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .fill(isEnabled ? Color.umuvePrimary : Color.umuvePrimary.opacity(0.4))
            )
            .scaleEffect(configuration.isPressed ? 0.97 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}

// Secondary button style
struct UmuveSecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(UmuveTypography.bodyFont.weight(.medium))
            .foregroundColor(.umuvePrimary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.umuveWhite)
            .cornerRadius(UmuveRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .stroke(Color.umuvePrimary, lineWidth: 1.5)
            )
            .scaleEffect(configuration.isPressed ? 0.97 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}

// Card container
struct UmuveCard<Content: View>: View {
    let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        content
            .padding(UmuveSpacing.normal)
            .background(Color.umuveWhite)
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
            .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }
}

// Screen header
struct ScreenHeader: View {
    let title: String
    let subtitle: String?
    let progress: Double?

    init(title: String, subtitle: String? = nil, progress: Double? = nil) {
        self.title = title
        self.subtitle = subtitle
        self.progress = progress
    }

    var body: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.medium) {
            if let progress = progress {
                ProgressDots(current: Int(progress * 5), total: 5)
                    .padding(.bottom, UmuveSpacing.small)
            }

            Text(title)
                .font(UmuveTypography.h1Font)
                .foregroundColor(.umuveText)

            if let subtitle = subtitle {
                Text(subtitle)
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }
}

// Progress dots indicator
struct ProgressDots: View {
    let current: Int
    let total: Int

    var body: some View {
        HStack(spacing: 8) {
            ForEach(0..<total, id: \.self) { index in
                Circle()
                    .fill(index < current ? Color.umuvePrimary : Color.umuveBorder)
                    .frame(width: 8, height: 8)
                    .animation(.easeInOut, value: current)
            }
        }
    }
}

