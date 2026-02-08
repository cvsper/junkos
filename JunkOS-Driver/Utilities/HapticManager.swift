//
//  HapticManager.swift
//  JunkOS Driver
//
//  Haptic feedback manager for consistent tactile feedback.
//

import UIKit

final class HapticManager {
    static let shared = HapticManager()

    private let lightImpact = UIImpactFeedbackGenerator(style: .light)
    private let mediumImpact = UIImpactFeedbackGenerator(style: .medium)
    private let heavyImpact = UIImpactFeedbackGenerator(style: .heavy)
    private let selectionGenerator = UISelectionFeedbackGenerator()
    private let notification = UINotificationFeedbackGenerator()

    private init() {
        lightImpact.prepare()
        mediumImpact.prepare()
        selectionGenerator.prepare()
    }

    func lightTap() {
        lightImpact.impactOccurred()
        lightImpact.prepare()
    }

    func mediumTap() {
        mediumImpact.impactOccurred()
        mediumImpact.prepare()
    }

    func heavyTap() {
        heavyImpact.impactOccurred()
        heavyImpact.prepare()
    }

    func selection() {
        selectionGenerator.selectionChanged()
        selectionGenerator.prepare()
    }

    func success() {
        notification.notificationOccurred(.success)
        notification.prepare()
    }

    func warning() {
        notification.notificationOccurred(.warning)
        notification.prepare()
    }

    func error() {
        notification.notificationOccurred(.error)
        notification.prepare()
    }
}
