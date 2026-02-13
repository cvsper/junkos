//
//  AccessibilityHelpers.swift
//  Umuve
//
//  Accessibility helpers and view modifiers
//

import SwiftUI

// MARK: - Enhanced Haptic Modifier
struct HapticFeedbackModifier: ViewModifier {
    let style: HapticStyle
    @Environment(\.accessibilityReduceMotion) var reduceMotion
    
    enum HapticStyle {
        case light, medium, heavy, selection, success, warning, error
    }
    
    func body(content: Content) -> some View {
        content
            .simultaneousGesture(
                TapGesture()
                    .onEnded { _ in
                        triggerHaptic()
                    }
            )
    }
    
    private func triggerHaptic() {
        switch style {
        case .light:
            HapticManager.shared.lightTap()
        case .medium:
            HapticManager.shared.mediumTap()
        case .heavy:
            HapticManager.shared.heavyTap()
        case .selection:
            HapticManager.shared.selection()
        case .success:
            HapticManager.shared.success()
        case .warning:
            HapticManager.shared.warning()
        case .error:
            HapticManager.shared.error()
        }
    }
}

extension View {
    func hapticFeedback(_ style: HapticFeedbackModifier.HapticStyle = .light) -> some View {
        modifier(HapticFeedbackModifier(style: style))
    }
}

// MARK: - Accessibility Enhanced Button
struct AccessibleButton<Label: View>: View {
    let action: () -> Void
    let label: Label
    let accessibilityLabel: String
    let accessibilityHint: String?
    
    @Environment(\.dynamicTypeSize) var dynamicTypeSize
    @Environment(\.colorSchemeContrast) var contrast
    
    init(
        action: @escaping () -> Void,
        accessibilityLabel: String,
        accessibilityHint: String? = nil,
        @ViewBuilder label: () -> Label
    ) {
        self.action = action
        self.accessibilityLabel = accessibilityLabel
        self.accessibilityHint = accessibilityHint
        self.label = label()
    }
    
    var body: some View {
        Button(action: action) {
            label
        }
        .accessibilityLabel(accessibilityLabel)
        .accessibilityHint(accessibilityHint ?? "")
        .accessibilityAddTraits(.isButton)
        .hapticFeedback(.light)
    }
}

// MARK: - Dynamic Type Support Helper
extension Font {
    func dynamicSize() -> Font {
        return self // SwiftUI automatically supports Dynamic Type
    }
}

// MARK: - High Contrast Helper
extension Color {
    func adjustForContrast(_ contrast: ColorSchemeContrast) -> Color {
        switch contrast {
        case .increased:
            // Return more contrasted version
            return self
        case .standard:
            return self
        @unknown default:
            return self
        }
    }
}

// MARK: - Preview
struct AccessibilityHelpers_Previews: PreviewProvider {
    static var previews: some View {
        VStack(spacing: 20) {
            AccessibleButton(
                action: {},
                accessibilityLabel: "Tap me",
                accessibilityHint: "This is a test button"
            ) {
                Text("Accessible Button")
                    .padding()
                    .background(Color.umuvePrimary)
                    .foregroundColor(.white)
                    .cornerRadius(8)
            }
            
            Text("Staggered Animation")
                .staggeredEntrance(index: 0, isVisible: true)
            
            Text("With Haptic")
                .padding()
                .background(Color.umuveCTA)
                .foregroundColor(.white)
                .cornerRadius(8)
                .hapticFeedback(.medium)
        }
        .padding()
    }
}
