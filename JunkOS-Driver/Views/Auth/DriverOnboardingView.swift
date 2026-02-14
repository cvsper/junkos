//
//  DriverOnboardingView.swift
//  Umuve Pro
//
//  3-screen swipeable onboarding shown on first launch only.
//  Clean white background with SF Symbol icons and red accents.
//

import SwiftUI

struct DriverOnboardingView: View {
    @AppStorage("hasCompletedDriverOnboarding") private var hasCompletedOnboarding = false
    @State private var currentPage = 0
    @Environment(\.accessibilityReduceMotion) private var reduceMotion

    var body: some View {
        ZStack {
            Color.white.ignoresSafeArea()

            VStack(spacing: 0) {
                // Skip button
                HStack {
                    Spacer()
                    Button("Skip") {
                        completeOnboarding()
                    }
                    .font(DriverTypography.callout)
                    .foregroundStyle(Color.driverTextSecondary)
                    .padding(.trailing, DriverSpacing.xl)
                    .padding(.top, DriverSpacing.md)
                }

                Spacer()

                // Swipeable pages
                TabView(selection: $currentPage) {
                    OnboardingPage(
                        iconName: "mappin.and.ellipse",
                        title: "Get jobs nearby",
                        subtitle: "See available jobs in your area and choose the ones that work for you."
                    )
                    .tag(0)

                    OnboardingPage(
                        iconName: "calendar.badge.clock",
                        title: "Set your schedule",
                        subtitle: "Work when you want. You're in control of your availability."
                    )
                    .tag(1)

                    OnboardingPage(
                        iconName: "dollarsign.circle",
                        title: "Earn on your terms",
                        subtitle: "Get paid quickly for every completed job. Track your earnings in real-time."
                    )
                    .tag(2)
                }
                .tabViewStyle(.page(indexDisplayMode: .always))
                .indexViewStyle(.page(backgroundDisplayMode: .always))

                Spacer()

                // Get Started button (shown on last page)
                if currentPage == 2 {
                    Button("Get Started") {
                        completeOnboarding()
                    }
                    .buttonStyle(DriverPrimaryButtonStyle())
                    .padding(.horizontal, DriverSpacing.xl)
                    .padding(.bottom, DriverSpacing.xxl)
                    .transition(.opacity)
                } else {
                    // Empty spacer to maintain layout
                    Color.clear
                        .frame(height: 52 + DriverSpacing.xxl)
                }
            }
        }
        .preferredColorScheme(.light)
    }

    private func completeOnboarding() {
        if reduceMotion {
            hasCompletedOnboarding = true
        } else {
            withAnimation(.easeInOut(duration: 0.3)) {
                hasCompletedOnboarding = true
            }
        }
    }
}

struct OnboardingPage: View {
    let iconName: String
    let title: String
    let subtitle: String

    var body: some View {
        VStack(spacing: DriverSpacing.xxl) {
            // Icon with gradient background
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color.driverPrimary, Color.driverPrimaryLight],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 120, height: 120)

                Image(systemName: iconName)
                    .font(.system(size: 56, weight: .regular))
                    .foregroundStyle(.white)
            }
            .padding(.top, DriverSpacing.huge)

            // Text content
            VStack(spacing: DriverSpacing.md) {
                Text(title)
                    .font(DriverTypography.title)
                    .foregroundStyle(Color.driverText)
                    .multilineTextAlignment(.center)

                Text(subtitle)
                    .font(DriverTypography.body)
                    .foregroundStyle(Color.driverTextSecondary)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, DriverSpacing.xxl)
            }
        }
    }
}
