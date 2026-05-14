//
//  WelcomeView.swift
//  Umuve
//
//  Welcome screen with hero section and social proof
//  SF Symbols Reference: https://developer.apple.com/sf-symbols/
//

import SwiftUI

struct WelcomeView: View {
    @EnvironmentObject var bookingData: BookingData
    @StateObject private var viewModel = WelcomeViewModel()
    @AppStorage("hasCompletedOnboarding") private var hasCompletedOnboarding = false
    @State private var showOnboarding = false
    
    var body: some View {
        ScrollView {
            VStack(spacing: UmuveSpacing.xxlarge) {
                // Logo placeholder
                logoSection
                
                // Hero section
                heroSection
                
                // LoadUp Feature #3: Eco-Friendly Badge
                ecoFriendlyBadge
                
                // LoadUp Feature #4: Commercial Booking Toggle
                commercialToggle
                
                // Live bookings counter
                HStack {
                    Spacer()
                    LiveBookingsCounter()
                    Spacer()
                }
                .padding(.vertical, UmuveSpacing.small)
                .accessibilityElement(children: .contain)
                
                // Social proof
                socialProofBar
                
                // Trust badges
                TrustBadgesBar()
                    .padding(.vertical, UmuveSpacing.small)
                
                // LoadUp Feature #7: Enhanced Trust & Coverage
                trustAndCoverageBadges
                
                // Feature cards
                featureCardsSection
                
                // Customer reviews
                ReviewsSection()
                    .padding(.top, UmuveSpacing.normal)
                
                // CTA button
                ctaButton
            }
            .padding(UmuveSpacing.large)
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .navigationBarHidden(true)
        .onAppear {
            viewModel.startAnimations()
            if !hasCompletedOnboarding {
                showOnboarding = true
            }
        }
        .sheet(isPresented: $showOnboarding) {
            OnboardingView()
        }
    }
    
    // MARK: - Logo Section
    private var logoSection: some View {
        // Brand wordmark — the horizontal red-U + black "muve" lockup. The
        // image is the entire brand mark, so no accompanying "Umuve" Text
        // (would duplicate the word).
        Image("UmuveLogo")
            .resizable()
            .scaledToFit()
            .frame(height: 64)
            .accessibilityLabel("Umuve")
            .padding(.top, UmuveSpacing.xlarge)
            .opacity(viewModel.isAnimating ? 1 : 0)
            .offset(y: viewModel.isAnimating ? 0 : -20)
    }
    
    // MARK: - Hero Section
    private var heroSection: some View {
        VStack(spacing: UmuveSpacing.normal) {
            // Badge - SF Symbol: sparkles for special/featured content
            HStack {
                HStack(spacing: 4) {
                    Image(systemName: "sparkles")
                        .font(.system(size: 12))
                    Text("INSTANT BOOKING")
                }
                .font(UmuveTypography.smallFont)
                .foregroundColor(.white)
                .padding(.horizontal, UmuveSpacing.medium)
                .padding(.vertical, UmuveSpacing.small)
                .background(
                    LinearGradient(
                        colors: [Color.umuvePrimary, Color.umuveSecondary],
                        startPoint: .leading,
                        endPoint: .trailing
                    )
                )
                .cornerRadius(20)
            }
            
            // Title
            Text("Book junk removal in 3 taps")
                .font(UmuveTypography.displayFont)
                .foregroundColor(.umuveText)
                .multilineTextAlignment(.center)
            
            // Subtitle
            Text("Same-day service • Eco-friendly disposal • Licensed & insured")
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveTextMuted)
                .multilineTextAlignment(.center)
        }
        .opacity(viewModel.isAnimating ? 1 : 0)
        .offset(y: viewModel.isAnimating ? 0 : -20)
        .animation(.easeInOut(duration: 0.6).delay(0.2), value: viewModel.isAnimating)
    }
    
    // MARK: - Social Proof
    private var socialProofBar: some View {
        HStack(spacing: UmuveSpacing.large) {
            // SF Symbol: star.fill for ratings
            ProofBadge(icon: "star.fill", text: "4.9/5")
            // SF Symbol: checkmark.circle.fill for completion/verification
            ProofBadge(icon: "checkmark.circle.fill", text: "2500+ Jobs")
            // SF Symbol: shield.fill for protection/insurance
            ProofBadge(icon: "shield.fill", text: "Insured")
        }
        .padding(.vertical, UmuveSpacing.normal)
        .opacity(viewModel.isAnimating ? 1 : 0)
        .animation(.easeInOut(duration: 0.6).delay(0.4), value: viewModel.isAnimating)
    }
    
    // MARK: - Feature Cards
    private var featureCardsSection: some View {
        VStack(spacing: UmuveSpacing.normal) {
            FeatureCard(step: 1, title: "Take Photos", description: "Snap pics of items to remove")
            FeatureCard(step: 2, title: "Get Quote", description: "Instant pricing based on volume")
            FeatureCard(step: 3, title: "Book Pickup", description: "Choose your time slot")
            FeatureCard(step: 4, title: "We Haul", description: "Sit back, we handle the rest")
        }
        .opacity(viewModel.isAnimating ? 1 : 0)
        .animation(.easeInOut(duration: 0.6).delay(0.6), value: viewModel.isAnimating)
    }
    
    // MARK: - LoadUp Feature #3: Eco-Friendly Badge
    private var ecoFriendlyBadge: some View {
        HStack(spacing: UmuveSpacing.normal) {
            ZStack {
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .fill(Color.umuveSuccess.opacity(0.18))
                    .frame(width: 52, height: 52)

                Image(systemName: "leaf.fill")
                    .font(.system(size: 24))
                    .foregroundColor(.umuveSuccess)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("We Recycle & Donate")
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.umuveText)

                Text("Eco-friendly disposal of your items")
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
            }

            Spacer(minLength: 0)
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.lg)
                .strokeBorder(Color.umuveBorder, lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 4)
        .opacity(viewModel.isAnimating ? 1 : 0)
        .animation(.easeInOut(duration: 0.6).delay(0.3), value: viewModel.isAnimating)
    }
    
    // MARK: - LoadUp Feature #4: Commercial Toggle
    private var commercialToggle: some View {
        UmuveCard {
            HStack {
                VStack(alignment: .leading, spacing: 4) {
                    Text("Business Account")
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuveText)
                    
                    Text("Bulk discounts & recurring pickups available")
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveTextMuted)
                }
                
                Spacer()
                
                Toggle("", isOn: $bookingData.isCommercialBooking)
                    .labelsHidden()
            }
            .padding(UmuveSpacing.normal)
        }
        .opacity(viewModel.isAnimating ? 1 : 0)
        .animation(.easeInOut(duration: 0.6).delay(0.35), value: viewModel.isAnimating)
    }
    
    // MARK: - LoadUp Feature #7: Trust & Coverage Badges
    private var trustAndCoverageBadges: some View {
        VStack(spacing: UmuveSpacing.normal) {
            HStack(spacing: UmuveSpacing.normal) {
                EnhancedTrustBadge(
                    icon: "checkmark.shield.fill",
                    title: "Background Checked",
                    subtitle: "All professionals vetted"
                )
                
                EnhancedTrustBadge(
                    icon: "shield.lefthalf.filled",
                    title: "Fully Insured",
                    subtitle: "$2M liability coverage"
                )
            }
            
            HStack(spacing: UmuveSpacing.normal) {
                EnhancedTrustBadge(
                    icon: "doc.text.fill",
                    title: "Licensed",
                    subtitle: "State certified"
                )
                
                EnhancedTrustBadge(
                    icon: "map.fill",
                    title: "Wide Coverage",
                    subtitle: "Enter zip to verify"
                )
            }
        }
        .padding(.vertical, UmuveSpacing.small)
        .opacity(viewModel.isAnimating ? 1 : 0)
        .animation(.easeInOut(duration: 0.6).delay(0.5), value: viewModel.isAnimating)
    }
    
    // MARK: - CTA Button
    private var ctaButton: some View {
        NavigationLink(destination: AddressInputView().environmentObject(bookingData)) {
            Text("Get Started →")
        }
        .buttonStyle(UmuvePrimaryButtonStyle())
        .padding(.top, UmuveSpacing.normal)
        .opacity(viewModel.isAnimating ? 1 : 0)
        .animation(.easeInOut(duration: 0.6).delay(0.8), value: viewModel.isAnimating)
    }
}

// MARK: - Supporting Views

struct ProofBadge: View {
    let icon: String // SF Symbol name
    let text: String
    
    var body: some View {
        HStack(spacing: UmuveSpacing.small) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundColor(.umuvePrimary)
            Text(text)
                .font(UmuveTypography.captionFont)
                .foregroundColor(.umuveText)
        }
    }
}

struct FeatureCard: View {
    let step: Int
    let title: String
    let description: String

    private var accent: Color {
        switch step {
        case 1: return .categoryBlue
        case 2: return .categoryOrange
        case 3: return .categoryYellow
        default: return .umuvePrimary
        }
    }

    var body: some View {
        UmuveCard {
            HStack(spacing: UmuveSpacing.normal) {
                ZStack {
                    RoundedRectangle(cornerRadius: UmuveRadius.md)
                        .fill(accent.opacity(0.18))
                        .frame(width: 52, height: 52)

                    Text("\(step)")
                        .font(UmuveTypography.h2Font)
                        .foregroundColor(accent)
                }

                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuveText)

                    Text(description)
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveTextMuted)
                }

                Spacer()
            }
            .padding(UmuveSpacing.normal)
        }
    }
}

struct EnhancedTrustBadge: View {
    let icon: String
    let title: String
    let subtitle: String

    var body: some View {
        UmuveCard {
            VStack(spacing: UmuveSpacing.small) {
                ZStack {
                    RoundedRectangle(cornerRadius: UmuveRadius.md)
                        .fill(Color.umuvePrimary.opacity(0.12))
                        .frame(width: 48, height: 48)

                    Image(systemName: icon)
                        .font(.system(size: 22))
                        .foregroundColor(.umuvePrimary)
                }

                Text(title)
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)
                    .multilineTextAlignment(.center)

                Text(subtitle)
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.umuveTextMuted)
                    .multilineTextAlignment(.center)
            }
            .frame(maxWidth: .infinity)
            .padding(UmuveSpacing.normal)
        }
    }
}

// MARK: - Preview
struct WelcomeView_Previews: PreviewProvider {
    static var previews: some View {
        WelcomeView()
            .environmentObject(BookingData())
    }
}
