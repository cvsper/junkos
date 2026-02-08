//
//  AnimationConstants.swift
//  JunkOS Driver
//
//  Centralized animation timing and spring parameters.
//

import SwiftUI

enum AnimationConstants {
    // MARK: - Spring Animations
    static let bouncySpring = Animation.spring(response: 0.5, dampingFraction: 0.6)
    static let smoothSpring = Animation.spring(response: 0.4, dampingFraction: 0.8)
    static let snappySpring = Animation.spring(response: 0.3, dampingFraction: 0.7)
    static let gentleSpring = Animation.spring(response: 0.6, dampingFraction: 0.9)

    // MARK: - Easing Animations
    static let fastEase = Animation.easeInOut(duration: 0.2)
    static let standardEase = Animation.easeInOut(duration: 0.3)
    static let slowEase = Animation.easeInOut(duration: 0.5)

    // MARK: - Stagger Delays
    static let staggerDelay: Double = 0.1
    static let sequenceDelay: Double = 0.15

    // MARK: - Scale Effects
    static let pressScale: CGFloat = 0.95
    static let tapScale: CGFloat = 0.98
    static let hoverScale: CGFloat = 1.02
}
