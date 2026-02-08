//
//  SplashView.swift
//  JunkOS Driver
//
//  "Drive with JunkOS" brand intro with animated emerald logo.
//

import SwiftUI

struct SplashView: View {
    @State private var logoScale: CGFloat = 0.5
    @State private var logoOpacity: Double = 0
    @State private var taglineOpacity: Double = 0

    var body: some View {
        ZStack {
            Color.driverPrimary
                .ignoresSafeArea()

            VStack(spacing: DriverSpacing.lg) {
                Image(systemName: "truck.box.fill")
                    .font(.system(size: 72))
                    .foregroundStyle(.white)
                    .scaleEffect(logoScale)
                    .opacity(logoOpacity)

                VStack(spacing: DriverSpacing.xs) {
                    Text("JunkOS")
                        .font(.system(size: 40, weight: .bold, design: .rounded))
                        .foregroundStyle(.white)

                    Text("DRIVER")
                        .font(.system(size: 16, weight: .semibold, design: .rounded))
                        .foregroundStyle(.white.opacity(0.8))
                        .tracking(6)
                }
                .opacity(logoOpacity)

                Text("Drive with JunkOS")
                    .font(DriverTypography.headline)
                    .foregroundStyle(.white.opacity(0.7))
                    .opacity(taglineOpacity)
            }
        }
        .onAppear {
            withAnimation(AnimationConstants.bouncySpring) {
                logoScale = 1.0
                logoOpacity = 1.0
            }
            withAnimation(AnimationConstants.smoothSpring.delay(0.3)) {
                taglineOpacity = 1.0
            }
        }
    }
}
