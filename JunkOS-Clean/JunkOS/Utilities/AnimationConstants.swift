//
//  AnimationConstants.swift
//  JunkOS
//
//  Centralized animation timing and spring parameters
//  Reference: https://developer.apple.com/documentation/swiftui/animation
//

import SwiftUI

/// Animation constants for consistent motion design
enum AnimationConstants {
    // MARK: - Spring Animations
    
    /// Bouncy spring for playful interactions (response: 0.5, dampingFraction: 0.6)
    static let bouncySpring = Animation.spring(response: 0.5, dampingFraction: 0.6)
    
    /// Smooth spring for general UI transitions (response: 0.4, dampingFraction: 0.8)
    static let smoothSpring = Animation.spring(response: 0.4, dampingFraction: 0.8)
    
    /// Snappy spring for quick feedback (response: 0.3, dampingFraction: 0.7)
    static let snappySpring = Animation.spring(response: 0.3, dampingFraction: 0.7)
    
    /// Gentle spring for subtle movements (response: 0.6, dampingFraction: 0.9)
    static let gentleSpring = Animation.spring(response: 0.6, dampingFraction: 0.9)
    
    // MARK: - Easing Animations
    
    /// Fast ease in/out for quick transitions
    static let fastEase = Animation.easeInOut(duration: 0.2)
    
    /// Standard ease in/out for general use
    static let standardEase = Animation.easeInOut(duration: 0.3)
    
    /// Slow ease in/out for dramatic transitions
    static let slowEase = Animation.easeInOut(duration: 0.5)
    
    // MARK: - Stagger Delays
    
    /// Base delay between staggered card animations
    static let staggerDelay: Double = 0.1
    
    /// Delay for sequential view appearances
    static let sequenceDelay: Double = 0.15
    
    // MARK: - Scale Effects
    
    /// Button press scale (slightly smaller)
    static let pressScale: CGFloat = 0.95
    
    /// Card tap scale (subtle feedback)
    static let tapScale: CGFloat = 0.98
    
    /// Hover/selection scale (slightly larger)
    static let hoverScale: CGFloat = 1.02
    
    // MARK: - Durations (for timing tests)
    
    static let shortDuration: Double = 0.2
    static let mediumDuration: Double = 0.3
    static let longDuration: Double = 0.5
    static let extraLongDuration: Double = 0.8
}

// MARK: - View Extension for Consistent Button Press Animation

extension View {
    /// Apply standard button press animation with scale and haptic
    func buttonPressAnimation(isPressed: Bool, hapticStyle: HapticStyle = .light) -> some View {
        self
            .scaleEffect(isPressed ? AnimationConstants.pressScale : 1.0)
            .animation(AnimationConstants.snappySpring, value: isPressed)
            .onChange(of: isPressed) { pressed in
                if pressed {
                    switch hapticStyle {
                    case .light:
                        HapticManager.shared.lightTap()
                    case .medium:
                        HapticManager.shared.mediumTap()
                    case .heavy:
                        HapticManager.shared.heavyTap()
                    }
                }
            }
    }
    
    /// Apply staggered entrance animation
    func staggeredEntrance(index: Int, isVisible: Bool) -> some View {
        self
            .opacity(isVisible ? 1 : 0)
            .offset(y: isVisible ? 0 : 20)
            .animation(
                AnimationConstants.smoothSpring.delay(Double(index) * AnimationConstants.staggerDelay),
                value: isVisible
            )
    }
    
    /// Apply bounce animation on value change
    func bounce(trigger: Int) -> some View {
        self
            .scaleEffect(1.0)
            .animation(AnimationConstants.bouncySpring, value: trigger)
    }
}

enum HapticStyle {
    case light, medium, heavy
}
