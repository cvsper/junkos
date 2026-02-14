//
//  OnboardingView.swift
//  Umuve
//
//  3-screen customer onboarding (first launch only)
//

import SwiftUI

// MARK: - Onboarding Page
struct OnboardingPage {
    let id: Int
    let icon: String
    let title: String
    let subtitle: String
}

// MARK: - Onboarding View
struct OnboardingView: View {
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    @State private var currentPage = 0
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    let pages: [OnboardingPage] = [
        OnboardingPage(
            id: 0,
            icon: "shippingbox",
            title: "Book a pickup",
            subtitle: "Tell us what you need hauled and we'll handle the rest."
        ),
        OnboardingPage(
            id: 1,
            icon: "location.fill",
            title: "Track your driver",
            subtitle: "Watch your driver arrive in real time on the map."
        ),
        OnboardingPage(
            id: 2,
            icon: "checkmark.circle",
            title: "Done — hauling made simple",
            subtitle: "Sit back while we haul it all away. That's it."
        )
    ]

    var body: some View {
        ZStack {
            Color.umuveBackground.ignoresSafeArea()

            VStack(spacing: 0) {
                // Skip button
                HStack {
                    Spacer()
                    Button("Skip") {
                        hasCompletedOnboarding = true
                    }
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)
                    .padding()
                    .accessibilityLabel("Skip onboarding")
                    .accessibilityHint("Double tap to skip and go to sign in")
                }

                // Page content
                TabView(selection: $currentPage) {
                    ForEach(pages, id: \.id) { page in
                        OnboardingPageView(page: page)
                            .tag(page.id)
                    }
                }
                .tabViewStyle(PageTabViewStyle(indexDisplayMode: .always))
                .animation(.easeInOut, value: currentPage)

                // Action button
                Button(action: {
                    if currentPage < pages.count - 1 {
                        withAnimation {
                            currentPage += 1
                        }
                    } else {
                        hasCompletedOnboarding = true
                    }
                }) {
                    Text(currentPage == pages.count - 1 ? "Get Started" : "Next")
                }
                .buttonStyle(UmuvePrimaryButtonStyle())
                .padding(.horizontal, UmuveSpacing.large)
                .padding(.bottom, UmuveSpacing.xxlarge)
                .accessibilityLabel(currentPage == pages.count - 1 ? "Get started with Umuve" : "Next page")
            }
        }
    }
}

// MARK: - Onboarding Page View
struct OnboardingPageView: View {
    let page: OnboardingPage
    @State private var isAnimating = false
    @Environment(\.accessibilityReduceMotion) var reduceMotion

    var body: some View {
        VStack(spacing: UmuveSpacing.xxlarge) {
            Spacer()

            // Icon with gradient background
            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [
                                Color.umuvePrimary.opacity(0.2),
                                Color.umuvePrimary.opacity(0.05)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 200, height: 200)
                    .scaleEffect(isAnimating ? 1 : 0.8)

                Image(systemName: page.icon)
                    .font(.system(size: 80))
                    .foregroundColor(.umuvePrimary)
                    .scaleEffect(isAnimating ? 1 : 0.5)
            }

            VStack(spacing: UmuveSpacing.normal) {
                Text(page.title)
                    .font(UmuveTypography.h1Font)
                    .foregroundColor(.umuveText)
                    .multilineTextAlignment(.center)
                    .opacity(isAnimating ? 1 : 0)

                Text(page.subtitle)
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, UmuveSpacing.xlarge)
                    .opacity(isAnimating ? 1 : 0)
            }

            Spacer()
        }
        .onAppear {
            if reduceMotion {
                isAnimating = true
            } else {
                withAnimation(.spring(response: 0.8, dampingFraction: 0.7)) {
                    isAnimating = true
                }
            }
        }
        .accessibilityElement(children: .combine)
    }
}

// MARK: - Preview
struct OnboardingView_Previews: PreviewProvider {
    static var previews: some View {
        OnboardingView()
    }
}
