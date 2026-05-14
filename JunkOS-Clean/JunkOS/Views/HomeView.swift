//
//  HomeView.swift
//  Umuve
//
//  Home screen — hero, primary booking CTA, trust pills, category
//  showcase, eco callout, "how it works", and a tappable phone fallback.
//

import SwiftUI
import UIKit

struct HomeView: View {
    @EnvironmentObject var bookingData: BookingData

    var body: some View {
        ScrollView {
            VStack(spacing: UmuveSpacing.xlarge) {
                logoHeader
                heroSection
                primaryCTA
                trustPills
                categoryShowcase
                ecoCallout
                howItWorksSection
                phoneFallback
            }
            .padding(.horizontal, UmuveSpacing.large)
            .padding(.bottom, UmuveSpacing.xxlarge)
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .navigationBarHidden(true)
    }

    // MARK: - Logo Header

    private var logoHeader: some View {
        HStack(alignment: .center) {
            Image("UmuveLogo")
                .resizable()
                .scaledToFit()
                .frame(height: 72)
                .accessibilityLabel("Umuve")
            Spacer()
        }
        .padding(.top, UmuveSpacing.normal)
    }

    // MARK: - Hero

    private var heroSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.small) {
            Text("Hauling made simple.")
                .font(UmuveTypography.heroFont)
                .foregroundColor(.umuveText)
                .multilineTextAlignment(.leading)
                .fixedSize(horizontal: false, vertical: true)

            Text("Professional junk removal in Palm Beach & Broward County. Upfront pricing, same-day pickup.")
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveTextMuted)
                .multilineTextAlignment(.leading)
                .fixedSize(horizontal: false, vertical: true)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Primary CTA Card

    private var primaryCTA: some View {
        NavigationLink {
            BookingWizardView(prefilledService: .junkRemoval)
        } label: {
            ZStack(alignment: .topTrailing) {
                LinearGradient(
                    colors: [Color.umuvePrimary, Color.umuvePrimaryDark],
                    startPoint: .topLeading,
                    endPoint: .bottomTrailing
                )

                // Subtle truck silhouette in the corner — uses the design
                // system's truck icon at large size with low opacity so it
                // reads as texture, not a literal button.
                Image(systemName: "truck.box.fill")
                    .font(.system(size: 110, weight: .semibold))
                    .foregroundColor(.white.opacity(0.12))
                    .offset(x: 24, y: -10)
                    .clipped()

                VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                    HStack(spacing: 4) {
                        Image(systemName: "sparkles")
                            .font(.system(size: 12, weight: .semibold))
                        Text("INSTANT QUOTE")
                            .font(UmuveTypography.smallFont.weight(.bold))
                            .tracking(0.8)
                    }
                    .foregroundColor(.white.opacity(0.9))

                    Text("Book a Pickup")
                        .font(UmuveTypography.h1Font)
                        .foregroundColor(.white)

                    Text("Starts at $89 · 6-step booking · same-day available")
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.white.opacity(0.85))

                    Spacer().frame(height: UmuveSpacing.small)

                    HStack {
                        Text("Get Started")
                            .font(UmuveTypography.bodyFont.weight(.semibold))
                        Image(systemName: "arrow.right")
                            .font(.system(size: 14, weight: .bold))
                    }
                    .foregroundColor(.umuvePrimary)
                    .padding(.horizontal, UmuveSpacing.normal)
                    .padding(.vertical, UmuveSpacing.small)
                    .background(Capsule().fill(Color.white))
                }
                .padding(UmuveSpacing.large)
            }
            .frame(maxWidth: .infinity, minHeight: 200)
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.xl))
            .shadow(color: Color.umuvePrimary.opacity(0.3), radius: 16, x: 0, y: 8)
        }
        .buttonStyle(.plain)
        .simultaneousGesture(TapGesture().onEnded { HapticManager.shared.lightTap() })
    }

    // MARK: - Trust Pills (compact row)

    private var trustPills: some View {
        HStack(spacing: UmuveSpacing.small) {
            trustPill(icon: "bolt.fill", text: "Same-Day")
            trustPill(icon: "star.fill", text: "4.9 / 5")
            trustPill(icon: "shield.fill", text: "Insured")
        }
    }

    private func trustPill(icon: String, text: String) -> some View {
        HStack(spacing: 4) {
            Image(systemName: icon)
                .font(.system(size: 11, weight: .semibold))
            Text(text)
                .font(UmuveTypography.smallFont.weight(.semibold))
        }
        .foregroundColor(.umuveText)
        .padding(.horizontal, UmuveSpacing.medium)
        .padding(.vertical, UmuveSpacing.small)
        .background(Color.umuveSurfaceElevated)
        .clipShape(Capsule())
        .overlay(Capsule().strokeBorder(Color.umuveBorder, lineWidth: 1))
        .frame(maxWidth: .infinity)
    }

    // MARK: - Category Showcase — "What we haul"

    private var categoryShowcase: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            HStack {
                Text("What we haul")
                    .font(UmuveTypography.h2Font)
                    .foregroundColor(.umuveText)
                Spacer()
                NavigationLink {
                    BookingWizardView(prefilledService: .junkRemoval)
                } label: {
                    Text("See all")
                        .font(UmuveTypography.bodySmallFont.weight(.semibold))
                        .foregroundColor(.umuvePrimary)
                }
                .buttonStyle(.plain)
            }

            LazyVGrid(columns: [GridItem(.flexible()), GridItem(.flexible())], spacing: UmuveSpacing.small) {
                ForEach(ItemCategory.allCases) { category in
                    categoryTile(category)
                }
            }
        }
    }

    private func categoryTile(_ category: ItemCategory) -> some View {
        NavigationLink {
            BookingWizardView(prefilledService: .junkRemoval)
        } label: {
            HStack(spacing: UmuveSpacing.small) {
                ZStack {
                    RoundedRectangle(cornerRadius: UmuveRadius.sm)
                        .fill(Color.umuvePrimary.opacity(0.1))
                        .frame(width: 36, height: 36)
                    Image(systemName: category.systemIcon)
                        .font(.system(size: 16, weight: .semibold))
                        .foregroundColor(.umuvePrimary)
                }
                Text(category.displayName)
                    .font(UmuveTypography.bodySmallFont.weight(.medium))
                    .foregroundColor(.umuveText)
                    .lineLimit(1)
                Spacer(minLength: 0)
            }
            .padding(UmuveSpacing.small)
            .frame(maxWidth: .infinity, minHeight: 56)
            .background(Color.umuveWhite)
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .strokeBorder(Color.umuveBorder, lineWidth: 1)
            )
        }
        .buttonStyle(.plain)
    }

    // MARK: - Eco Callout

    private var ecoCallout: some View {
        HStack(alignment: .top, spacing: UmuveSpacing.normal) {
            ZStack {
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .fill(Color.umuveSuccess.opacity(0.15))
                    .frame(width: 48, height: 48)
                Image(systemName: "leaf.fill")
                    .font(.system(size: 22))
                    .foregroundColor(.umuveSuccess)
            }

            VStack(alignment: .leading, spacing: 4) {
                Text("We donate & recycle first")
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.umuveText)
                Text("Landfill is always the last resort. Reusable items go to local charities, scrap metal gets recycled, e-waste is properly disposed of.")
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
                    .fixedSize(horizontal: false, vertical: true)
            }
            Spacer(minLength: 0)
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveSuccess.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.lg)
                .strokeBorder(Color.umuveSuccess.opacity(0.2), lineWidth: 1)
        )
    }

    // MARK: - How It Works

    private var howItWorksSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("How it works")
                .font(UmuveTypography.h2Font)
                .foregroundColor(.umuveText)

            VStack(spacing: UmuveSpacing.medium) {
                HowItWorksStep(number: 1, title: "Tell us what's going", description: "Pick categories and add items in seconds")
                HowItWorksStep(number: 2, title: "Pick a date", description: "Same-day windows when available")
                HowItWorksStep(number: 3, title: "See your price", description: "Upfront — never higher than the high estimate")
                HowItWorksStep(number: 4, title: "We haul it", description: "Donate, recycle, dispose — landfill last")
            }
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.lg)
                .strokeBorder(Color.umuveBorder, lineWidth: 1)
        )
    }

    // MARK: - Phone Fallback

    private var phoneFallback: some View {
        VStack(spacing: UmuveSpacing.small) {
            Text("Prefer to talk?")
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(.umuveTextMuted)
            Button {
                if let url = URL(string: "tel:5619441636") {
                    UIApplication.shared.open(url)
                }
            } label: {
                HStack(spacing: UmuveSpacing.small) {
                    Image(systemName: "phone.fill")
                        .font(.system(size: 14, weight: .semibold))
                    Text("(561) 944-1636")
                        .font(UmuveTypography.bodyFont.weight(.semibold))
                }
                .foregroundColor(.umuvePrimary)
            }
            .accessibilityLabel("Call us at 561-944-1636")
        }
        .frame(maxWidth: .infinity)
        .padding(.vertical, UmuveSpacing.normal)
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
