//
//  DesignSystem.swift
//  JunkOS
//
//  Unified emerald green design system.
//

import SwiftUI

// MARK: - Colors
extension Color {
    // Primary — emerald green
    static let junkPrimary = Color(hex: "10B981")
    static let junkPrimaryLight = Color(hex: "34D399")
    static let junkPrimaryDark = Color(hex: "059669")
    static let junkSecondary = Color(hex: "34D399")
    static let junkCTA = Color(hex: "10B981")

    // Backgrounds
    static let junkBackground = Color(hex: "F0FDF4")
    static let junkSurface = Color.white
    static let junkSurfaceElevated = Color(hex: "ECFDF5")

    // Aliases for legacy references
    static let loadUpGreen = Color(hex: "10B981")
    static let loadUpGreenLight = Color(hex: "34D399")
    static let loadUpGreenDark = Color(hex: "059669")

    // Category card colors
    static let categoryBlue = Color(hex: "3B82F6")
    static let categoryYellow = Color(hex: "FBBF24")
    static let categoryPink = Color(hex: "EC4899")
    static let categoryGreen = Color(hex: "10B981")
    static let categoryPurple = Color(hex: "8B5CF6")
    static let categoryOrange = Color(hex: "F97316")

    // Text colors
    static let junkText = Color(hex: "0F172A")
    static let junkTextMuted = Color(hex: "64748B")
    static let junkTextTertiary = Color(hex: "94A3B8")

    // Semantic
    static let junkSuccess = Color(hex: "22C55E")
    static let junkWarning = Color(hex: "F59E0B")
    static let junkError = Color(hex: "EF4444")
    static let junkInfo = Color(hex: "3B82F6")

    // UI colors
    static let junkBorder = Color(hex: "E2E8F0")
    static let junkDivider = Color(hex: "F1F5F9")
    static let junkWhite = Color.white

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
struct JunkTypography {
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
struct JunkSpacing {
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
struct JunkRadius {
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 16
    static let xl: CGFloat = 20
    static let full: CGFloat = 999
}

// MARK: - Reusable Components

// Primary button style
struct JunkPrimaryButtonStyle: ButtonStyle {
    var isEnabled: Bool = true

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(JunkTypography.bodyFont.weight(.semibold))
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(
                RoundedRectangle(cornerRadius: JunkRadius.md)
                    .fill(isEnabled ? Color.junkPrimary : Color.junkPrimary.opacity(0.4))
            )
            .scaleEffect(configuration.isPressed ? 0.97 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}

// Secondary button style
struct JunkSecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(JunkTypography.bodyFont.weight(.medium))
            .foregroundColor(.junkPrimary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(Color.junkWhite)
            .cornerRadius(JunkRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: JunkRadius.md)
                    .stroke(Color.junkPrimary, lineWidth: 1.5)
            )
            .scaleEffect(configuration.isPressed ? 0.97 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}

// Card container
struct JunkCard<Content: View>: View {
    let content: Content

    init(@ViewBuilder content: () -> Content) {
        self.content = content()
    }

    var body: some View {
        content
            .padding(JunkSpacing.normal)
            .background(Color.junkWhite)
            .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
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
        VStack(alignment: .leading, spacing: JunkSpacing.medium) {
            if let progress = progress {
                ProgressDots(current: Int(progress * 5), total: 5)
                    .padding(.bottom, JunkSpacing.small)
            }

            Text(title)
                .font(JunkTypography.h1Font)
                .foregroundColor(.junkText)

            if let subtitle = subtitle {
                Text(subtitle)
                    .font(JunkTypography.bodyFont)
                    .foregroundColor(.junkTextMuted)
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
                    .fill(index < current ? Color.junkPrimary : Color.junkBorder)
                    .frame(width: 8, height: 8)
                    .animation(.easeInOut, value: current)
            }
        }
    }
}

