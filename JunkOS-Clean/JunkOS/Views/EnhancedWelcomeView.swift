//
//  EnhancedWelcomeView.swift
//  Umuve
//
//  DEPRECATED: Replaced by OnboardingView.swift in Phase 1
//  This file is preserved to avoid breaking Xcode project references.
//

import SwiftUI

struct EnhancedWelcomeView: View {
    @Binding var showingSplash: Bool
    @State private var isAnimating = false
    @AppStorage("hasSeenWelcome") private var hasSeenWelcome = false
    
    var body: some View {
        welcomeContent
    }
    
    private var welcomeContent: some View {
        ZStack {
            // Gradient background
            LinearGradient(
                colors: [Color.loadUpGreen, Color.loadUpGreenLight],
                startPoint: .topLeading,
                endPoint: .bottomTrailing
            )
            .ignoresSafeArea()
            
            VStack(spacing: UmuveSpacing.xxlarge) {
                Spacer()
                
                // Logo
                logoSection
                
                // Trust badges
                trustBadgesRow
                
                // How it works
                howItWorksSection
                
                Spacer()
                
                // Get Started button
                getStartedButton
            }
            .padding(UmuveSpacing.large)
        }
        .onAppear {
            withAnimation(.easeInOut(duration: 0.8)) {
                isAnimating = true
            }
            
            // Auto-transition after 3 seconds
            DispatchQueue.main.asyncAfter(deadline: .now() + 3) {
                withAnimation {
                    showingSplash = false
                    hasSeenWelcome = true
                }
            }
        }
    }
    
    // MARK: - Logo Section
    private var logoSection: some View {
        VStack(spacing: UmuveSpacing.normal) {
            ZStack {
                Circle()
                    .fill(Color.white)
                    .frame(width: 120, height: 120)
                    .shadow(color: .black.opacity(0.2), radius: 12, x: 0, y: 6)
                
                Image(systemName: "trash.fill")
                    .font(.system(size: 60))
                    .foregroundColor(.loadUpGreen)
            }
            .scaleEffect(isAnimating ? 1.0 : 0.8)
            .opacity(isAnimating ? 1.0 : 0)
            
            Text("Umuve")
                .font(.system(size: 48, weight: .bold))
                .foregroundColor(.white)
                .opacity(isAnimating ? 1.0 : 0)
            
            Text("Professional Junk Removal")
                .font(UmuveTypography.h3Font)
                .foregroundColor(.white.opacity(0.9))
                .opacity(isAnimating ? 1.0 : 0)
        }
    }
    
    // MARK: - Trust Badges Row
    private var trustBadgesRow: some View {
        HStack(spacing: UmuveSpacing.xlarge) {
            VStack(spacing: UmuveSpacing.small) {
                Image(systemName: "star.fill")
                    .font(.system(size: 28))
                    .foregroundColor(.categoryYellow)
                
                Text("4.9/5")
                    .font(UmuveTypography.bodyFont.weight(.bold))
                    .foregroundColor(.white)
                
                Text("Rating")
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.white.opacity(0.8))
            }
            
            VStack(spacing: UmuveSpacing.small) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 28))
                    .foregroundColor(.white)
                
                Text("2,500+")
                    .font(UmuveTypography.bodyFont.weight(.bold))
                    .foregroundColor(.white)
                
                Text("Jobs Done")
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.white.opacity(0.8))
            }
            
            VStack(spacing: UmuveSpacing.small) {
                Image(systemName: "shield.fill")
                    .font(.system(size: 28))
                    .foregroundColor(.categoryBlue)
                
                Text("Insured")
                    .font(UmuveTypography.bodyFont.weight(.bold))
                    .foregroundColor(.white)
                
                Text("& Licensed")
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.white.opacity(0.8))
            }
        }
        .opacity(isAnimating ? 1.0 : 0)
        .offset(y: isAnimating ? 0 : 20)
        .animation(.easeOut(duration: 0.8).delay(0.3), value: isAnimating)
    }
    
    // MARK: - How It Works Section
    private var howItWorksSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("How it works")
                .font(UmuveTypography.h2Font)
                .foregroundColor(.white)
                .frame(maxWidth: .infinity, alignment: .leading)
            
            VStack(spacing: UmuveSpacing.medium) {
                WelcomeStep(number: 1, text: "Choose your service")
                WelcomeStep(number: 2, text: "Set pickup location")
                WelcomeStep(number: 3, text: "Get instant quote")
                WelcomeStep(number: 4, text: "We haul it away")
            }
        }
        .padding(UmuveSpacing.large)
        .background(
            RoundedRectangle(cornerRadius: 20)
                .fill(Color.white.opacity(0.2))
                .background(
                    RoundedRectangle(cornerRadius: 20)
                        .stroke(Color.white.opacity(0.3), lineWidth: 1)
                )
        )
        .opacity(isAnimating ? 1.0 : 0)
        .offset(y: isAnimating ? 0 : 20)
        .animation(.easeOut(duration: 0.8).delay(0.5), value: isAnimating)
    }
    
    // MARK: - Get Started Button
    private var getStartedButton: some View {
        Button(action: {
            withAnimation {
                showingSplash = false
                hasSeenWelcome = true
            }
        }) {
            HStack {
                Text("Get Started")
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.loadUpGreen)
                
                Image(systemName: "arrow.right")
                    .font(.system(size: 20, weight: .semibold))
                    .foregroundColor(.loadUpGreen)
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, 18)
            .background(Color.white)
            .cornerRadius(16)
            .shadow(color: .black.opacity(0.2), radius: 12, x: 0, y: 6)
        }
        .opacity(isAnimating ? 1.0 : 0)
        .scaleEffect(isAnimating ? 1.0 : 0.9)
        .animation(.easeOut(duration: 0.8).delay(0.7), value: isAnimating)
    }
}

// MARK: - Welcome Step
struct WelcomeStep: View {
    let number: Int
    let text: String
    
    var body: some View {
        HStack(spacing: UmuveSpacing.normal) {
            ZStack {
                Circle()
                    .fill(Color.white)
                    .frame(width: 36, height: 36)
                
                Text("\(number)")
                    .font(UmuveTypography.bodyFont.weight(.bold))
                    .foregroundColor(.loadUpGreen)
            }
            
            Text(text)
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.white)
            
            Spacer()
        }
    }
}

// MARK: - Preview
struct EnhancedWelcomeView_Previews: PreviewProvider {
    static var previews: some View {
        EnhancedWelcomeView(showingSplash: .constant(true))
    }
}
