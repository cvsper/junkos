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
}
