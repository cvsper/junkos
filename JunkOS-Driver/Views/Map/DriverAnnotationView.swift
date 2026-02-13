//
//  DriverAnnotationView.swift
//  Umuve Pro
//
//  Custom vehicle annotation: emerald circle with truck icon.
//

import SwiftUI

struct DriverAnnotationView: View {
    let truckIcon: String
    var isOnline: Bool = true
    var heading: Double = 0

    @State private var pulseScale: CGFloat = 1.0

    var body: some View {
        ZStack {
            // Pulse ring when online
            if isOnline {
                Circle()
                    .fill(Color.driverPrimary.opacity(0.2))
                    .frame(width: 56, height: 56)
                    .scaleEffect(pulseScale)
            }

            // Main circle
            Circle()
                .fill(
                    LinearGradient(
                        colors: [Color.driverPrimary, Color.driverPrimaryDark],
                        startPoint: .topLeading,
                        endPoint: .bottomTrailing
                    )
                )
                .frame(width: 40, height: 40)
                .shadow(color: Color.driverPrimary.opacity(0.4), radius: 6, y: 2)

            // Truck icon
            Image(systemName: truckIcon)
                .font(.system(size: 18, weight: .semibold))
                .foregroundStyle(.white)
        }
        .rotationEffect(.degrees(heading))
        .onAppear {
            if isOnline {
                withAnimation(
                    .easeInOut(duration: 2.0)
                    .repeatForever(autoreverses: true)
                ) {
                    pulseScale = 1.3
                }
            }
        }
    }
}
