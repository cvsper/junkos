//
//  OnlineToggleView.swift
//  Umuve Pro
//
//  Hero toggle with glow animation for going online/offline.
//

import SwiftUI

struct OnlineToggleView: View {
    let isOnline: Bool
    let onToggle: () -> Void

    @State private var pulseScale: CGFloat = 1.0

    var body: some View {
        Button(action: {
            HapticManager.shared.heavyTap()
            onToggle()
        }) {
            ZStack {
                // Glow ring
                if isOnline {
                    Circle()
                        .fill(Color.driverPrimary.opacity(0.15))
                        .frame(width: 160, height: 160)
                        .scaleEffect(pulseScale)

                    Circle()
                        .fill(Color.driverPrimary.opacity(0.08))
                        .frame(width: 200, height: 200)
                        .scaleEffect(pulseScale * 0.9)
                }

                // Main circle
                Circle()
                    .fill(
                        isOnline
                            ? LinearGradient(
                                colors: [Color.driverPrimary, Color.driverPrimaryDark],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                              )
                            : LinearGradient(
                                colors: [Color.driverBorder, Color(hex: "CBD5E1")],
                                startPoint: .topLeading,
                                endPoint: .bottomTrailing
                              )
                    )
                    .frame(width: 130, height: 130)
                    .shadow(
                        color: isOnline ? Color.driverPrimary.opacity(0.4) : .clear,
                        radius: 20, y: 4
                    )

                // Label
                VStack(spacing: DriverSpacing.xxs) {
                    Image(systemName: isOnline ? "power" : "power")
                        .font(.system(size: 32, weight: .semibold))
                        .foregroundStyle(.white)

                    Text(isOnline ? "ONLINE" : "OFFLINE")
                        .font(.system(size: 13, weight: .bold, design: .rounded))
                        .foregroundStyle(.white.opacity(0.9))
                        .tracking(2)
                }
            }
            .frame(maxWidth: .infinity)
            .frame(height: 220)
        }
        .buttonStyle(.plain)
        .onChange(of: isOnline) { _, online in
            if online {
                startPulse()
            } else {
                pulseScale = 1.0
            }
        }
        .onAppear {
            if isOnline { startPulse() }
        }
    }

    private func startPulse() {
        withAnimation(
            .easeInOut(duration: 2.0)
            .repeatForever(autoreverses: true)
        ) {
            pulseScale = 1.15
        }
    }
}
