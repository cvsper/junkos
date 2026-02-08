//
//  HomeView.swift
//  JunkOS
//
//  Home screen with service category cards.
//

import SwiftUI

struct HomeView: View {
    @EnvironmentObject var bookingData: BookingData
    @State private var searchText = ""

    var body: some View {
        ScrollView {
            VStack(spacing: JunkSpacing.xlarge) {
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
            .padding(.horizontal, JunkSpacing.large)
            .padding(.bottom, JunkSpacing.xxlarge)
        }
        .background(Color.junkBackground.ignoresSafeArea())
        .navigationBarHidden(true)
    }

    // MARK: - Header Section
    private var headerSection: some View {
        HStack {
            VStack(alignment: .leading, spacing: 4) {
                Text("JunkOS")
                    .font(JunkTypography.h1Font)
                    .foregroundColor(.junkText)

                Text("Professional junk removal")
                    .font(JunkTypography.bodyFont)
                    .foregroundColor(.junkTextMuted)
            }

            Spacer()

            ZStack {
                Circle()
                    .fill(
                        LinearGradient(
                            colors: [Color.junkPrimary, Color.junkPrimaryDark],
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
        .padding(.top, JunkSpacing.normal)
    }

    // MARK: - Search Bar
    private var searchBar: some View {
        HStack(spacing: JunkSpacing.small) {
            Image(systemName: "magnifyingglass")
                .foregroundColor(.junkTextMuted)

            TextField("What do you need removed?", text: $searchText)
                .font(JunkTypography.bodyFont)
                .foregroundColor(.junkText)
        }
        .padding(JunkSpacing.normal)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: JunkRadius.md))
        .shadow(color: .black.opacity(0.06), radius: 4, x: 0, y: 2)
    }

    // MARK: - Service Categories
    private var serviceCategoriesSection: some View {
        VStack(spacing: JunkSpacing.medium) {
            ForEach(ServiceCategory.all, id: \.id) { category in
                NavigationLink {
                    MapAddressPickerView()
                        .environmentObject(bookingData)
                } label: {
                    ServiceCategoryCard(category: category)
                }
                .buttonStyle(.plain)
            }
        }
    }

    // MARK: - Trust Badges
    private var trustBadgesSection: some View {
        HStack(spacing: JunkSpacing.large) {
            TrustBadge(icon: "star.fill", text: "4.9/5", color: .categoryYellow)
            TrustBadge(icon: "checkmark.circle.fill", text: "2,500+ Jobs", color: .junkPrimary)
            TrustBadge(icon: "shield.fill", text: "Insured", color: .categoryBlue)
        }
        .padding(.vertical, JunkSpacing.normal)
    }

    // MARK: - How It Works
    private var howItWorksSection: some View {
        VStack(alignment: .leading, spacing: JunkSpacing.normal) {
            Text("How it works")
                .font(JunkTypography.h2Font)
                .foregroundColor(.junkText)

            VStack(spacing: JunkSpacing.medium) {
                HowItWorksStep(number: 1, title: "Choose Service", description: "Select what you need removed")
                HowItWorksStep(number: 2, title: "Set Location", description: "Tell us where to pick up")
                HowItWorksStep(number: 3, title: "Get Quote", description: "Instant pricing based on photos")
                HowItWorksStep(number: 4, title: "We Haul It", description: "Sit back, we handle the rest")
            }
        }
        .padding(JunkSpacing.normal)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 4, x: 0, y: 2)
    }
}

// MARK: - Service Category Model
struct ServiceCategory: Identifiable {
    let id: String
    let title: String
    let description: String
    let icon: String
    let color: Color

    static let all: [ServiceCategory] = [
        ServiceCategory(id: "junk", title: "Junk Removal", description: "Furniture, appliances, general junk", icon: "trash.fill", color: .categoryBlue),
        ServiceCategory(id: "donation", title: "Donation Pickups", description: "Gently used items for charity", icon: "heart.fill", color: .categoryPink),
        ServiceCategory(id: "moving", title: "Moving Labor", description: "Heavy lifting & loading help", icon: "figure.strengthtraining.traditional", color: .categoryYellow),
        ServiceCategory(id: "cleanout", title: "Property Cleanout", description: "Full property or estate cleanout", icon: "house.fill", color: .categoryGreen),
    ]
}

// MARK: - Service Category Card
struct ServiceCategoryCard: View {
    let category: ServiceCategory

    var body: some View {
        HStack(spacing: JunkSpacing.normal) {
            // Icon
            ZStack {
                RoundedRectangle(cornerRadius: JunkRadius.md)
                    .fill(category.color.opacity(0.15))
                    .frame(width: 64, height: 64)

                Image(systemName: category.icon)
                    .font(.system(size: 26))
                    .foregroundColor(category.color)
            }

            // Content
            VStack(alignment: .leading, spacing: 4) {
                Text(category.title)
                    .font(JunkTypography.h3Font)
                    .foregroundColor(.junkText)

                Text(category.description)
                    .font(JunkTypography.bodySmallFont)
                    .foregroundColor(.junkTextMuted)
                    .lineLimit(2)
            }

            Spacer()

            Image(systemName: "chevron.right")
                .font(.system(size: 14, weight: .semibold))
                .foregroundColor(.junkTextTertiary)
        }
        .padding(JunkSpacing.normal)
        .background(Color.white)
        .clipShape(RoundedRectangle(cornerRadius: JunkRadius.lg))
        .shadow(color: .black.opacity(0.06), radius: 6, x: 0, y: 3)
    }
}

// MARK: - How It Works Step
struct HowItWorksStep: View {
    let number: Int
    let title: String
    let description: String

    var body: some View {
        HStack(spacing: JunkSpacing.normal) {
            ZStack {
                Circle()
                    .fill(Color.junkPrimary.opacity(0.15))
                    .frame(width: 36, height: 36)

                Text("\(number)")
                    .font(JunkTypography.h3Font)
                    .foregroundColor(.junkPrimary)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(JunkTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.junkText)

                Text(description)
                    .font(JunkTypography.bodySmallFont)
                    .foregroundColor(.junkTextMuted)
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
