//
//  AddressInputView.swift
//  Umuve
//
//  Address input screen with MapKit autocomplete and mini-map preview.
//

import SwiftUI
import MapKit
import CoreLocation

struct AddressInputView: View {
    @EnvironmentObject var bookingData: BookingData
    @EnvironmentObject var wizardVM: BookingWizardViewModel
    @StateObject private var viewModel = AddressInputViewModel()

    // Rotating placeholder mirroring the web's 5-address cycle on Step 1.
    private static let placeholderExamples: [String] = [
        "123 Main St, Boca Raton, FL",
        "456 Ocean Blvd, Fort Lauderdale, FL",
        "789 Glades Rd, Delray Beach, FL",
        "321 Atlantic Ave, West Palm Beach, FL",
        "654 University Dr, Coral Springs, FL",
    ]
    @State private var placeholderIndex: Int = 0
    private let placeholderTimer = Timer.publish(every: 3, on: .main, in: .common).autoconnect()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: UmuveSpacing.xlarge) {
                headerSection
                pickupSection

                if !viewModel.pickupSelected {
                    trustCallout
                    trustIndicators
                }
            }
            .padding(.horizontal, UmuveSpacing.large)
            .padding(.top, UmuveSpacing.normal)
            .padding(.bottom, UmuveSpacing.xxlarge)
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .safeAreaInset(edge: .bottom) {
            continueButton
                .padding(.horizontal, UmuveSpacing.large)
                .padding(.vertical, UmuveSpacing.normal)
                .background(Color.umuveBackground)
                .ignoresSafeArea(.keyboard, edges: .bottom)
        }
        .onReceive(placeholderTimer) { _ in
            withAnimation(.easeInOut(duration: 0.3)) {
                placeholderIndex = (placeholderIndex + 1) % Self.placeholderExamples.count
            }
        }
    }

    // MARK: - Header Section (web parity copy)

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.small) {
            Text("Where should we pick up?")
                .font(UmuveTypography.h1Font)
                .foregroundColor(.umuveText)

            Text("Enter the address where your junk needs to be removed.")
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveTextMuted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Pickup Section

    private var pickupSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            sectionLabel(icon: "mappin.and.ellipse", title: "Pickup Address", accent: .categoryBlue)

            if viewModel.pickupSelected {
                pickupMiniMap
            } else {
                searchField(
                    query: $viewModel.pickupSearchQuery,
                    completions: viewModel.pickupCompletions,
                    placeholder: Self.placeholderExamples[placeholderIndex],
                    accent: .categoryBlue,
                    onSelect: { completion in
                        viewModel.selectPickupAddress(completion, bookingData: bookingData)
                    }
                )

                currentLocationButton
            }
        }
    }

    // MARK: - Trust Callout (web Step 1 social proof box)

    private var trustCallout: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
            HStack(spacing: UmuveSpacing.small) {
                Image(systemName: "checkmark.seal.fill")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(.umuvePrimary)
                Text("2,450+ pickups completed in South Florida")
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)
            }

            Text("Serving Palm Beach & Broward County")
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(.umuveTextMuted)
                .padding(.leading, 26)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(UmuveSpacing.normal)
        .background(Color.umuvePrimary.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.md)
                .strokeBorder(Color.umuvePrimary.opacity(0.18), lineWidth: 1)
        )
    }

    // MARK: - Trust Indicators (web Step 1 three-cell row)

    private var trustIndicators: some View {
        VStack(spacing: UmuveSpacing.medium) {
            trustIndicator(
                icon: "bolt.fill",
                title: "Same-Day Available",
                subtitle: "Book today, we pick up today",
                tint: .umuveSuccess
            )
            trustIndicator(
                icon: "dollarsign.circle.fill",
                title: "Starting at $89",
                subtitle: "Transparent pricing, no hidden fees",
                tint: .umuvePrimary
            )
            trustIndicator(
                icon: "leaf.fill",
                title: "Eco-Friendly Disposal",
                subtitle: "We recycle & donate first",
                tint: .categoryGreen
            )
        }
    }

    private func trustIndicator(icon: String, title: String, subtitle: String, tint: Color) -> some View {
        HStack(spacing: UmuveSpacing.normal) {
            ZStack {
                Circle()
                    .fill(tint.opacity(0.15))
                    .frame(width: 44, height: 44)
                Image(systemName: icon)
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(tint)
            }

            VStack(alignment: .leading, spacing: 2) {
                Text(title)
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)
                Text(subtitle)
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
            }

            Spacer()
        }
    }

    // MARK: - Section Label

    private func sectionLabel(icon: String, title: String, accent: Color) -> some View {
        HStack(spacing: UmuveSpacing.small) {
            ZStack {
                RoundedRectangle(cornerRadius: UmuveRadius.sm)
                    .fill(accent.opacity(0.18))
                    .frame(width: 32, height: 32)

                Image(systemName: icon)
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(accent)
            }

            Text(title)
                .font(UmuveTypography.h3Font)
                .foregroundColor(.umuveText)

            Spacer()
        }
    }

    // MARK: - Search Field Component

    private func searchField(
        query: Binding<String>,
        completions: [MKLocalSearchCompletion],
        placeholder: String,
        accent: Color,
        onSelect: @escaping (MKLocalSearchCompletion) -> Void
    ) -> some View {
        VStack(spacing: UmuveSpacing.small) {
            HStack(spacing: UmuveSpacing.small) {
                Image(systemName: "magnifyingglass")
                    .font(.system(size: 16, weight: .medium))
                    .foregroundColor(.umuveTextMuted)

                TextField(placeholder, text: query)
                    .font(UmuveTypography.bodyFont)
                    .autocapitalization(.words)
                    .autocorrectionDisabled()

                if !query.wrappedValue.isEmpty {
                    Button {
                        query.wrappedValue = ""
                    } label: {
                        Image(systemName: "xmark.circle.fill")
                            .foregroundColor(.umuveTextMuted)
                    }
                }
            }
            .padding(.horizontal, UmuveSpacing.normal)
            .padding(.vertical, UmuveSpacing.normal)
            .background(Color.umuveWhite)
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
            .overlay(
                RoundedRectangle(cornerRadius: UmuveRadius.lg)
                    .strokeBorder(Color.umuveBorder, lineWidth: 1)
            )
            .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 4)

            if !completions.isEmpty {
                VStack(spacing: 0) {
                    ForEach(completions.prefix(5), id: \.self) { completion in
                        Button {
                            onSelect(completion)
                        } label: {
                            HStack(spacing: UmuveSpacing.normal) {
                                ZStack {
                                    RoundedRectangle(cornerRadius: UmuveRadius.sm)
                                        .fill(accent.opacity(0.18))
                                        .frame(width: 36, height: 36)

                                    Image(systemName: "mappin.circle.fill")
                                        .font(.system(size: 18))
                                        .foregroundColor(accent)
                                }

                                VStack(alignment: .leading, spacing: 2) {
                                    Text(completion.title)
                                        .font(UmuveTypography.bodyFont.weight(.medium))
                                        .foregroundColor(.umuveText)
                                        .lineLimit(1)

                                    if !completion.subtitle.isEmpty {
                                        Text(completion.subtitle)
                                            .font(UmuveTypography.bodySmallFont)
                                            .foregroundColor(.umuveTextMuted)
                                            .lineLimit(1)
                                    }
                                }

                                Spacer()

                                Image(systemName: "arrow.up.left")
                                    .font(.system(size: 14, weight: .semibold))
                                    .foregroundColor(.umuveTextTertiary)
                            }
                            .padding(.horizontal, UmuveSpacing.normal)
                            .padding(.vertical, UmuveSpacing.medium)
                            .contentShape(Rectangle())
                            .background(Color.umuveWhite)
                        }
                        .buttonStyle(.plain)

                        if completion != completions.prefix(5).last {
                            Divider()
                                .padding(.leading, 60)
                        }
                    }
                }
                .background(Color.umuveWhite)
                .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
                .overlay(
                    RoundedRectangle(cornerRadius: UmuveRadius.lg)
                        .strokeBorder(Color.umuveBorder, lineWidth: 1)
                )
                .shadow(color: .black.opacity(0.08), radius: 10, x: 0, y: 4)
            }
        }
    }

    // MARK: - Pickup Mini-Map

    private var pickupMiniMap: some View {
        UmuveCard {
            VStack(spacing: UmuveSpacing.small) {
                // Map
                Map(coordinateRegion: $viewModel.pickupRegion, annotationItems: pickupAnnotations) { annotation in
                    MapPin(coordinate: annotation.coordinate, tint: .red)
                }
                .frame(height: 150)
                .cornerRadius(UmuveRadius.sm)

                // Address text
                VStack(alignment: .leading, spacing: 4) {
                    Text(bookingData.address.fullAddress)
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveText)
                        .lineLimit(2)

                    // Change button
                    Button {
                        viewModel.pickupSelected = false
                        viewModel.pickupSearchQuery = ""
                    } label: {
                        Text("Change")
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundColor(.umuvePrimary)
                    }
                }
                .frame(maxWidth: .infinity, alignment: .leading)
                .padding(.horizontal, UmuveSpacing.small)
                .padding(.bottom, UmuveSpacing.tiny)
            }
        }
    }

    // MARK: - Current Location Button

    private var currentLocationButton: some View {
        Button {
            viewModel.detectCurrentLocation(bookingData: bookingData)
        } label: {
            HStack(spacing: UmuveSpacing.small) {
                Image(systemName: "location.fill")
                    .font(.system(size: 16, weight: .semibold))
                Text("Use Current Location")
                    .font(UmuveTypography.bodyFont.weight(.semibold))
            }
            .foregroundColor(.umuvePrimary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, UmuveSpacing.normal)
            .background(Color.umuvePrimary.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
            .overlay(
                RoundedRectangle(cornerRadius: UmuveRadius.lg)
                    .strokeBorder(Color.umuvePrimary.opacity(0.25), lineWidth: 1)
            )
        }
    }

    // MARK: - Continue Button

    private var continueButton: some View {
        Button {
            wizardVM.completeCurrentStep()
        } label: {
            Text("Continue")
        }
        .buttonStyle(UmuvePrimaryButtonStyle(isEnabled: viewModel.pickupSelected))
        .disabled(!viewModel.pickupSelected)
    }

    // MARK: - Computed Properties

    private var pickupAnnotations: [MapAnnotation] {
        guard let coordinate = bookingData.pickupCoordinate else { return [] }
        return [MapAnnotation(id: "pickup", coordinate: coordinate)]
    }
}

// MARK: - Map Annotation

struct MapAnnotation: Identifiable {
    let id: String
    let coordinate: CLLocationCoordinate2D
}

// MARK: - Preview

#Preview {
    NavigationStack {
        BookingWizardView()
    }
}
