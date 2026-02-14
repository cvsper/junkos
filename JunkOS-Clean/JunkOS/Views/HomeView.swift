//
//  HomeView.swift
//  Umuve
//
//  Home screen with service category cards.
//

import SwiftUI

struct HomeView: View {
    @EnvironmentObject var bookingData: BookingData
    @State private var searchText = ""

    var body: some View {
        ScrollView {
            VStack(spacing: UmuveSpacing.xlarge) {
                // Header
                headerSection

                // Search bar
                searchBar

                // Service category cards
                serviceCategoriesSection

                // Trust badges
                trustBadgesSection

                // How it works
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
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("Umuve")
                    .font(UmuveTypography.h1Font)
                    .foregroundColor(.umuveText)

                Text("Professional junk removal")
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)
            }

            Spacer()

            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color.umuvePrimary, Color.umuvePrimaryDark],
                            startPoint: .topLeading,
                            endPoint: .bottomTrailing
                        )
                    )
                    .frame(width: 50, height: 50)

                Image(systemName: "leaf.fill")
                    .font(.system(size: 22))
                    .foregroundColor(.white)
            }
        }
        .padding(.top, UmuveSpacing.normal)
    }

    // MARK: - Search Bar
    private var searchBar: some View {
        HStack(spacing: UmuveSpacing.small) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.umuveTextMuted)

            TextField("What do you need removed?", text: $searchText)
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveText)
        }
        .padding(UmuveSpacing.normal)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        .shadow(color: .black.opacity(0.06), radius: 4, x: 0, y: 2)
    }

    // MARK: - Service Categories
    private var serviceCategoriesSection: some View {
        VStack(spacing: UmuveSpacing.medium) {
            // Junk Removal Card
            NavigationLink {
                BookingWizardView()
            } label: {
                ServiceTypeCard(
                    serviceType: .junkRemoval
                )
            }
            .buttonStyle(.plain)

            // Auto Transport Card
            NavigationLink {
                BookingWizardView()
            } label: {
                ServiceTypeCard(
                    serviceType: .autoTransport
                )
            }
            .buttonStyle(.plain)
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
