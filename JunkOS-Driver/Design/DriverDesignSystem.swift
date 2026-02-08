//
//  DriverDesignSystem.swift
//  JunkOS Driver
//
//  Emerald-themed design system for the contractor app.
//  Differentiated from customer app (indigo) with a professional green palette.
//

import SwiftUI

// MARK: - Colors

extension Color {
    // Primary brand — emerald green
    static let driverPrimary = Color(hex: "059669")
    static let driverPrimaryLight = Color(hex: "34D399")
    static let driverPrimaryDark = Color(hex: "047857")

    // Secondary accent
    static let driverAccent = Color(hex: "10B981")
    static let driverAccentLight = Color(hex: "6EE7B7")

    // Backgrounds
    static let driverBackground = Color(hex: "F0FDF4")
    static let driverSurface = Color.white
    static let driverSurfaceElevated = Color(hex: "ECFDF5")

    // Text
    static let driverText = Color(hex: "022C22")
    static let driverTextSecondary = Color(hex: "64748B")
    static let driverTextTertiary = Color(hex: "94A3B8")

    // Semantic
    static let driverSuccess = Color(hex: "22C55E")
    static let driverWarning = Color(hex: "F59E0B")
    static let driverError = Color(hex: "EF4444")
    static let driverInfo = Color(hex: "3B82F6")

    // UI
    static let driverBorder = Color(hex: "E2E8F0")
    static let driverDivider = Color(hex: "F1F5F9")

    // Status colors
    static let statusPending = Color(hex: "F59E0B")
    static let statusAccepted = Color(hex: "3B82F6")
    static let statusEnRoute = Color(hex: "8B5CF6")
    static let statusArrived = Color(hex: "06B6D4")
    static let statusStarted = Color(hex: "F97316")
    static let statusCompleted = Color(hex: "22C55E")
    static let statusCancelled = Color(hex: "EF4444")

    // Hex initializer
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
            blue: Double(b) / 255,
            opacity: Double(a) / 255
        )
    }
}

// MARK: - Typography

struct DriverTypography {
    static let largeTitle = Font.system(size: 34, weight: .bold, design: .rounded)
    static let title = Font.system(size: 28, weight: .bold, design: .rounded)
    static let title2 = Font.system(size: 22, weight: .semibold, design: .rounded)
    static let title3 = Font.system(size: 20, weight: .semibold)
    static let headline = Font.system(size: 17, weight: .semibold)
    static let body = Font.system(size: 17, weight: .regular)
    static let callout = Font.system(size: 16, weight: .regular)
    static let subheadline = Font.system(size: 15, weight: .regular)
    static let footnote = Font.system(size: 13, weight: .regular)
    static let caption = Font.system(size: 12, weight: .medium)
    static let caption2 = Font.system(size: 11, weight: .regular)

    // Monospaced for numbers/prices
    static let price = Font.system(size: 24, weight: .bold, design: .rounded)
    static let priceSmall = Font.system(size: 17, weight: .semibold, design: .rounded)
    static let stat = Font.system(size: 32, weight: .bold, design: .rounded)
}

// MARK: - Spacing

struct DriverSpacing {
    static let xxxs: CGFloat = 2
    static let xxs: CGFloat = 4
    static let xs: CGFloat = 8
    static let sm: CGFloat = 12
    static let md: CGFloat = 16
    static let lg: CGFloat = 20
    static let xl: CGFloat = 24
    static let xxl: CGFloat = 32
    static let xxxl: CGFloat = 48
    static let huge: CGFloat = 64
}

// MARK: - Corner Radius

struct DriverRadius {
    static let sm: CGFloat = 8
    static let md: CGFloat = 12
    static let lg: CGFloat = 16
    static let xl: CGFloat = 20
    static let full: CGFloat = 999
}

// MARK: - Button Styles

struct DriverPrimaryButtonStyle: ButtonStyle {
    var isEnabled: Bool = true

    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(DriverTypography.headline)
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(
                RoundedRectangle(cornerRadius: DriverRadius.md)
                    .fill(isEnabled ? Color.driverPrimary : Color.driverPrimary.opacity(0.4))
            )
            .scaleEffect(configuration.isPressed ? 0.97 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}

struct DriverSecondaryButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(DriverTypography.headline)
            .foregroundColor(.driverPrimary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(
                RoundedRectangle(cornerRadius: DriverRadius.md)
                    .stroke(Color.driverPrimary, lineWidth: 1.5)
            )
            .scaleEffect(configuration.isPressed ? 0.97 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}

struct DriverDestructiveButtonStyle: ButtonStyle {
    func makeBody(configuration: Configuration) -> some View {
        configuration.label
            .font(DriverTypography.headline)
            .foregroundColor(.driverError)
            .frame(maxWidth: .infinity)
            .padding(.vertical, 16)
            .background(
                RoundedRectangle(cornerRadius: DriverRadius.md)
                    .fill(Color.driverError.opacity(0.1))
            )
            .scaleEffect(configuration.isPressed ? 0.97 : 1.0)
            .animation(.easeInOut(duration: 0.15), value: configuration.isPressed)
    }
}

// MARK: - Card Modifier

struct DriverCardModifier: ViewModifier {
    var padding: CGFloat = DriverSpacing.md

    func body(content: Content) -> some View {
        content
            .padding(padding)
            .background(Color.driverSurface)
            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
            .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 2)
    }
}

extension View {
    func driverCard(padding: CGFloat = DriverSpacing.md) -> some View {
        modifier(DriverCardModifier(padding: padding))
    }
}

// MARK: - Input Field Style

struct DriverTextFieldStyle: TextFieldStyle {
    func _body(configuration: TextField<Self._Label>) -> some View {
        configuration
            .font(DriverTypography.body)
            .foregroundStyle(Color.driverText)
            .padding(DriverSpacing.md)
            .background(Color.white)
            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: DriverRadius.md)
                    .stroke(Color.driverBorder, lineWidth: 1)
            )
    }
}
