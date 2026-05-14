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

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: UmuveSpacing.xlarge) {
                headerSection

                pickupSection
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
    }

    // MARK: - Header Section

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.small) {
            Text("Where's the pickup?")
                .font(UmuveTypography.h1Font)
                .foregroundColor(.umuveText)

            Text("Enter the pickup location")
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
                    placeholder: "Search pickup address...",
                    accent: .categoryBlue,
                    onSelect: { completion in
                        viewModel.selectPickupAddress(completion, bookingData: bookingData)
                    }
                )

                currentLocationButton
            }
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
