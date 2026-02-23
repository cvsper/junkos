//
//  NavigationOverlay.swift
//  Umuve Pro
//
//  In-app turn-by-turn navigation overlay with current instruction.
//

import SwiftUI
import MapKit

struct NavigationOverlay: View {
    let step: MKRoute.Step?
    let eta: String?
    let onNext: () -> Void
    let onStop: () -> Void

    var body: some View {
        VStack(spacing: DriverSpacing.xs) {
            // Navigation instruction card
            VStack(spacing: DriverSpacing.sm) {
                HStack {
                    // Turn icon
                    Image(systemName: turnIcon)
                        .font(.system(size: 32, weight: .bold))
                        .foregroundStyle(Color.driverPrimary)
                        .frame(width: 50)

                    VStack(alignment: .leading, spacing: DriverSpacing.xxs) {
                        // Distance to next turn
                        if let step = step {
                            Text(formatDistance(step.distance))
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverTextSecondary)

                            // Instruction
                            Text(step.instructions)
                                .font(DriverTypography.headline)
                                .foregroundStyle(Color.driverText)

                            // Lane guidance (if turn requires lane change)
                            if shouldShowLaneGuidance {
                                LaneGuidanceView(laneDirections: laneDirections)
                                    .padding(.top, DriverSpacing.xxs)
                            }
                        } else {
                            Text("Calculating route...")
                                .font(DriverTypography.body)
                                .foregroundStyle(Color.driverTextSecondary)
                        }
                    }

                    Spacer()

                    // ETA
                    if let eta = eta {
                        VStack(spacing: DriverSpacing.xxxs) {
                            Image(systemName: "clock.fill")
                                .font(.system(size: 14))
                                .foregroundStyle(Color.driverInfo)
                            Text(eta)
                                .font(DriverTypography.caption)
                                .foregroundStyle(Color.driverText)
                        }
                    }
                }

                // Controls
                HStack(spacing: DriverSpacing.sm) {
                    // Stop navigation
                    Button {
                        onStop()
                    } label: {
                        HStack(spacing: DriverSpacing.xxs) {
                            Image(systemName: "xmark.circle.fill")
                            Text("Stop")
                        }
                        .font(DriverTypography.caption)
                        .foregroundStyle(Color.driverError)
                    }
                    .buttonStyle(DriverSecondaryButtonStyle())

                    Spacer()

                    // Next step (for testing/manual advance)
                    Button {
                        onNext()
                    } label: {
                        HStack(spacing: DriverSpacing.xxs) {
                            Text("Next Step")
                            Image(systemName: "arrow.right")
                        }
                        .font(DriverTypography.caption)
                    }
                    .buttonStyle(DriverSecondaryButtonStyle())
                }
            }
            .padding(DriverSpacing.md)
            .background(.ultraThinMaterial)
            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
            .shadow(color: .black.opacity(0.1), radius: 8, y: 2)
            .padding(.horizontal, DriverSpacing.md)
        }
    }

    private var turnIcon: String {
        guard let step = step else { return "arrow.up" }
        let instruction = step.instructions.lowercased()

        if instruction.contains("left") {
            return "arrow.turn.up.left"
        } else if instruction.contains("right") {
            return "arrow.turn.up.right"
        } else if instruction.contains("straight") || instruction.contains("continue") {
            return "arrow.up"
        } else if instruction.contains("u-turn") {
            return "arrow.uturn.left"
        } else if instruction.contains("arrive") || instruction.contains("destination") {
            return "mappin.circle.fill"
        } else {
            return "arrow.up"
        }
    }

    private func formatDistance(_ meters: Double) -> String {
        if meters < 100 {
            return "Now"
        } else if meters < 1000 {
            return "\(Int(meters)) m"
        } else {
            let miles = meters / 1609.34
            return String(format: "%.1f mi", miles)
        }
    }

    /// Whether to show lane guidance based on turn type
    private var shouldShowLaneGuidance: Bool {
        guard let step = step else { return false }
        let instruction = step.instructions.lowercased()
        // Show lane guidance for turns (not for straight/continue/arrive)
        return instruction.contains("left") || instruction.contains("right") || instruction.contains("exit")
    }

    /// Lane directions based on turn instruction
    private var laneDirections: [LaneDirection] {
        guard let step = step else { return [] }
        let instruction = step.instructions.lowercased()

        // Determine recommended lanes based on turn type
        if instruction.contains("sharp left") || instruction.contains("turn left") {
            return [.left, .straightLeft, .none, .none]
        } else if instruction.contains("slight left") {
            return [.none, .straightLeft, .straight, .none]
        } else if instruction.contains("sharp right") || instruction.contains("turn right") {
            return [.none, .none, .straightRight, .right]
        } else if instruction.contains("slight right") {
            return [.none, .straight, .straightRight, .none]
        } else if instruction.contains("exit") && instruction.contains("right") {
            return [.none, .none, .straightRight, .right]
        } else if instruction.contains("exit") && instruction.contains("left") {
            return [.left, .straightLeft, .none, .none]
        } else {
            return [.none, .straight, .straight, .none]
        }
    }
}

// MARK: - Lane Direction

enum LaneDirection {
    case none
    case left
    case straightLeft
    case straight
    case straightRight
    case right

    var icon: String {
        switch self {
        case .none: return ""
        case .left: return "arrow.turn.up.left"
        case .straightLeft: return "arrow.up.left"
        case .straight: return "arrow.up"
        case .straightRight: return "arrow.up.right"
        case .right: return "arrow.turn.up.right"
        }
    }

    var isActive: Bool {
        self != .none
    }
}

// MARK: - Lane Guidance View

struct LaneGuidanceView: View {
    let laneDirections: [LaneDirection]

    var body: some View {
        HStack(spacing: 4) {
            ForEach(Array(laneDirections.enumerated()), id: \.offset) { index, direction in
                VStack(spacing: 2) {
                    if direction.isActive {
                        Image(systemName: direction.icon)
                            .font(.system(size: 14, weight: .semibold))
                            .foregroundStyle(Color.driverPrimary)
                    } else {
                        Rectangle()
                            .fill(Color.driverTextSecondary.opacity(0.3))
                            .frame(width: 16, height: 2)
                    }

                    // Lane line
                    Rectangle()
                        .fill(direction.isActive ? Color.driverPrimary : Color.driverTextSecondary.opacity(0.5))
                        .frame(width: 20, height: 24)
                        .overlay(
                            RoundedRectangle(cornerRadius: 2)
                                .strokeBorder(direction.isActive ? Color.driverPrimary : Color.driverTextSecondary.opacity(0.3), lineWidth: 1.5)
                        )
                }
            }
        }
    }
}
