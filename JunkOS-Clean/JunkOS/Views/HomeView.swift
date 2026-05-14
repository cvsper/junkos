//
//  HomeView.swift
//  Umuve
//
//  Home screen with service category cards.
//

import SwiftUI

struct HomeView: View {
    @EnvironmentObject var bookingData: BookingData

    var body: some View {
        ScrollView {
            VStack(spacing: UmuveSpacing.xlarge) {
                headerSection
                serviceCategoriesSection
                trustBadgesSection
                howItWorksSection
            }
            .padding(.horizontal, UmuveSpacing.large)
            .padding(.bottom, UmuveSpacing.xxlarge)
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .navigationBarHidden(true)
    }

    // MARK: - Header Section
    private var headerSection: some View {
        HStack(alignment: .center) {
            Image("UmuveLogo")
                .resizable()
                .scaledToFit()
                .frame(height: 36)
                .accessibilityLabel("Umuve")

            Spacer()

            Text("Professional junk removal")
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(.umuveTextMuted)
                .multilineTextAlignment(.trailing)
        }
        .padding(.top, UmuveSpacing.normal)
    }

    // MARK: - Service Categories
    private var serviceCategoriesSection: some View {
        VStack(spacing: UmuveSpacing.medium) {
            NavigationLink {
                BookingWizardView(prefilledService: .junkRemoval)
            } label: {
                ServiceTypeCard(serviceType: .junkRemoval)
            }
            .buttonStyle(.plain)
            .simultaneousGesture(TapGesture().onEnded {
                HapticManager.shared.lightTap()
            })
        }
    }

    // MARK: - Trust Badges
    private var trustBadgesSection: some View {
        HStack(spacing: UmuveSpacing.large) {
            TrustBadge(icon: "star.fill", text: "4.9/5", color: .categoryYellow)
            TrustBadge(icon: "checkmark.circle.fill", text: "2,500+ Jobs", color: .umuvePrimary)
            TrustBadge(icon: "shield.fill", text: "Insured", color: .categoryBlue)
        }
        .padding(.vertical, UmuveSpacing.normal)
    }

    // MARK: - How It Works
    private var howItWorksSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("How it works")
                .font(UmuveTypography.h2Font)
                .foregroundColor(.umuveText)

            VStack(spacing: UmuveSpacing.medium) {
                HowItWorksStep(number: 1, title: "Choose Service", description: "Select what you need removed")
                HowItWorksStep(number: 2, title: "Set Location", description: "Tell us where to pick up")
                HowItWorksStep(number: 3, title: "Get Quote", description: "Instant pricing based on photos")
                HowItWorksStep(number: 4, title: "We Haul It", description: "Sit back, we handle the rest")
            }
        }
        .padding(UmuveSpacing.normal)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 4, x: 0, y: 2)
    }
}

// MARK: - Service Type Card
struct ServiceTypeCard: View {
    let serviceType: ServiceType

    var body: some View {
        HStack(spacing: UmuveSpacing.normal) {
            // Icon
            ZStack {
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .fill(Color.umuvePrimary.opacity(0.15))
                    .frame(width: 64, height: 64)

                Image(systemName: serviceType.icon)
                    .font(.system(size: 26))
                    .foregroundColor(.umuvePrimary)
            }

            // Content
            VStack(alignment: .leading, spacing: 4) {
                Text(serviceType.rawValue)
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.umuveText)

                Text(serviceType.description)
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
                    .lineLimit(2)
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.system(size: 14, weight: .semibold))
                .foregroundColor(.umuveTextTertiary)
        }
        .padding(UmuveSpacing.normal)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 6, x: 0, y: 3)
    }
}

// MARK: - How It Works Step
struct HowItWorksStep: View {
    let number: Int
    let title: String
    let description: String

    var body: some View {
        HStack(spacing: UmuveSpacing.normal) {
            ZStack {
                Circle()
                    .fill(Color.umuvePrimary.opacity(0.15))
                    .frame(width: 36, height: 36)

                Text("\(number)")
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.umuvePrimary)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)

                Text(description)
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
            }

            Spacer()
        }
    }
}

#Preview {
    NavigationStack {
        HomeView()
            .environmentObject(BookingData())
    }
}
