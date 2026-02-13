//
//  HapticManager.swift
//  Umuve
//
//  Haptic feedback manager for consistent tactile feedback
//  Reference: https://developer.apple.com/documentation/uikit/uifeedbackgenerator
//

import UIKit

/// Centralized haptic feedback manager
/// Uses UIFeedbackGenerator family for different interaction types
/// Reference: https://developer.apple.com/design/human-interface-guidelines/playing-haptics
class HapticManager {
    static let shared = HapticManager()
    
    // MARK: - Generators
    
    /// Light impact for subtle interactions (button presses, toggles)
    private let lightImpact = UIImpactFeedbackGenerator(style: .light)
    
    /// Medium impact for standard interactions (card taps, selections)
    private let mediumImpact = UIImpactFeedbackGenerator(style: .medium)
    
    /// Heavy impact for significant interactions (confirmations, deletions)
    private let heavyImpact = UIImpactFeedbackGenerator(style: .heavy)
    
    /// Selection feedback for scrolling through values
    private let selectionGenerator = UISelectionFeedbackGenerator()
    
    /// Notification feedback for task completion or errors
    private let notification = UINotificationFeedbackGenerator()
    
    private init() {
        // Prepare generators for optimal performance
        // Reference: https://developer.apple.com/documentation/uikit/uifeedbackgenerator/2374298-prepare
        lightImpact.prepare()
        mediumImpact.prepare()
        selectionGenerator.prepare()
    }
    
    // MARK: - Public Interface
    
    /// Light haptic for button presses and toggles
    func lightTap() {
        lightImpact.impactOccurred()
        lightImpact.prepare()
    }
    
    /// Medium haptic for card selections and navigation
    func mediumTap() {
        mediumImpact.impactOccurred()
        mediumImpact.prepare()
    }
    
    /// Heavy haptic for confirmations and important actions
    func heavyTap() {
        heavyImpact.impactOccurred()
        heavyImpact.prepare()
    }
    
    /// Selection haptic for scrolling through options (dates, times, etc.)
    func selection() {
        selectionGenerator.selectionChanged()
        selectionGenerator.prepare()
    }
    
    /// Success notification haptic
    func success() {
        notification.notificationOccurred(.success)
        notification.prepare()
    }
    
    /// Warning notification haptic
    func warning() {
        notification.notificationOccurred(.warning)
        notification.prepare()
    }
    
    /// Error notification haptic
    func error() {
        notification.notificationOccurred(.error)
        notification.prepare()
    }
}
