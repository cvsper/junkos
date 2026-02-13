//
//  OnboardingView.swift
//  Umuve
//
//  Onboarding flow with 3 screens
//

import SwiftUI

// MARK: - Onboarding Manager
class OnboardingManager: ObservableObject {
    @AppStorage("hasCompletedOnboarding") var hasCompletedOnboarding = false
    
    func completeOnboarding() {
        hasCompletedOnboarding = true
    }
}

// MARK: - Onboarding Page
struct OnboardingPage {
    let id: Int
    let icon: String
    let title: String
    let subtitle: String
    let color: Color
}

// MARK: - Onboarding View
struct OnboardingView: View {
    @StateObject private var onboardingManager = OnboardingManager()
    @State private var currentPage = 0
    @State private var showMainApp = false
    @Environment(\.dismiss) var dismiss
    
    let pages: [OnboardingPage] = [
        OnboardingPage(
            id: 0,
            icon: "sparkles",
            title: "Welcome to Umuve",
            subtitle: "The fastest way to remove junk from your home. Book in just 3 taps!",
            color: .umuvePrimary
        ),
        OnboardingPage(
            id: 1,
            icon: "camera.viewfinder",
            title: "Snap & Quote",
            subtitle: "Take photos of your items and get instant pricing. No hidden fees, ever.",
            color: .umuveSecondary
        ),
        OnboardingPage(
            id: 2,
            icon: "calendar.badge.checkmark",
            title: "Book Your Time",
            subtitle: "Choose a time slot that works for you. Same-day service available!",
            color: .umuveCTA
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
                        completeOnboarding()
                    }
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)
                    .padding()
                    .accessibilityLabel("Skip onboarding")
                    .accessibilityHint("Double tap to skip and go to main app")
                }
                
                // Page content
                TabView(selection: $currentPage) {
                    ForEach(pages, id: \.id) { page in
                        OnboardingPageView(page: page)
                            .tag(page.id)
                    }
                }
                .tabViewStyle(PageTabViewStyle(indexDisplayMode: .never))
                .animation(.easeInOut, value: currentPage)
                
                // Page indicators
                HStack(spacing: 8) {
                    ForEach(pages, id: \.id) { page in
                        Circle()
                            .fill(currentPage == page.id ? Color.umuvePrimary : Color.umuveBorder)
                            .frame(width: 10, height: 10)
                            .animation(.easeInOut, value: currentPage)
                    }
                }
                .padding(.vertical, UmuveSpacing.normal)
                .accessibilityElement(children: .ignore)
                .accessibilityLabel("Page \(currentPage + 1) of \(pages.count)")
                
                // Action button
                Button(action: {
                    if currentPage < pages.count - 1 {
                        withAnimation {
                            currentPage += 1
                        }
                    } else {
                        completeOnboarding()
                    }
                }) {
                    Text(currentPage == pages.count - 1 ? "Get Started" : "Next")
                }
                .buttonStyle(UmuvePrimaryButtonStyle())
                .padding(.horizontal, UmuveSpacing.large)
                .padding(.bottom, UmuveSpacing.xlarge)
                .accessibilityLabel(currentPage == pages.count - 1 ? "Get started with Umuve" : "Next page")
            }
        }
    }
    
    private func completeOnboarding() {
        onboardingManager.completeOnboarding()
        dismiss()
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
                                page.color.opacity(0.2),
                                page.color.opacity(0.05)
                            ],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 200, height: 200)
                    .scaleEffect(isAnimating ? 1 : 0.8)
                
                Image(systemName: page.icon)
                    .font(.system(size: 80))
                    .foregroundColor(page.color)
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

// MARK: - Permission Pre-prompt View
struct PermissionPrePromptView: View {
    let icon: String
    let title: String
    let subtitle: String
    let reason: String
    let allowAction: () -> Void
    let denyAction: () -> Void
    
    var body: some View {
        VStack(spacing: UmuveSpacing.xlarge) {
            Spacer()
            
            // Icon
            ZStack {
                Circle()
                    .fill(Color.umuvePrimary.opacity(0.1))
                    .frame(width: 120, height: 120)
                
                Image(systemName: icon)
                    .font(.system(size: 60))
                    .foregroundColor(.umuvePrimary)
            }
            
            VStack(spacing: UmuveSpacing.normal) {
                Text(title)
                    .font(UmuveTypography.h2Font)
                    .foregroundColor(.umuveText)
                    .multilineTextAlignment(.center)
                
                Text(subtitle)
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, UmuveSpacing.xlarge)
            }
            
            // Reason card
            UmuveCard {
                HStack(spacing: UmuveSpacing.medium) {
                    Image(systemName: "info.circle.fill")
                        .foregroundColor(.umuvePrimary)
                        .font(.system(size: 24))
                    
                    Text(reason)
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveText)
                        .multilineTextAlignment(.leading)
                }
                .padding(UmuveSpacing.normal)
            }
            .padding(.horizontal, UmuveSpacing.large)
            
            Spacer()
            
            // Actions
            VStack(spacing: UmuveSpacing.medium) {
                Button(action: allowAction) {
                    Text("Allow")
                }
                .buttonStyle(UmuvePrimaryButtonStyle())
                .accessibilityLabel("Allow \(title.lowercased())")
                
                Button(action: denyAction) {
                    Text("Not Now")
                }
                .buttonStyle(UmuveSecondaryButtonStyle())
                .accessibilityLabel("Deny \(title.lowercased())")
            }
            .padding(.horizontal, UmuveSpacing.large)
            .padding(.bottom, UmuveSpacing.xlarge)
        }
        .background(Color.umuveBackground.ignoresSafeArea())
    }
}

// MARK: - Preview
struct OnboardingView_Previews: PreviewProvider {
    static var previews: some View {
        OnboardingView()
        
        PermissionPrePromptView(
            icon: "location.fill",
            title: "Location Access",
            subtitle: "We need your location to provide accurate service",
            reason: "Your location helps us match you with the nearest team and provide accurate arrival times.",
            allowAction: {},
            denyAction: {}
        )
    }
}
