//
//  AddressInputView.swift
//  Umuve
//
//  Address input screen with MapKit autocomplete, mini-map preview, and conditional dropoff
//

import SwiftUI
import MapKit
import CoreLocation

struct AddressInputView: View {
    @EnvironmentObject var bookingData: BookingData
    @EnvironmentObject var wizardVM: BookingWizardViewModel
    @StateObject private var viewModel = AddressInputViewModel()

    var body: some View {
        VStack(spacing: 0) {
            ScrollView {
                VStack(spacing: UmuveSpacing.large) {
                    // Header
                    headerSection

                    // Pickup Address Section
                    pickupSection

                    // Dropoff Address Section (Auto Transport only)
                    if bookingData.needsDropoff {
                        dropoffSection
                    }

                    // Distance Display (Auto Transport only, after both addresses selected)
                    if bookingData.needsDropoff && viewModel.pickupSelected && viewModel.dropoffSelected {
                        distanceDisplay
                    }
                }
                .padding(UmuveSpacing.large)
            }

            // Continue Button
            continueButton
        }
        .background(Color.umuveBackground.ignoresSafeArea())
    }

    // MARK: - Header Section

    private var headerSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.small) {
            Text(bookingData.needsDropoff ? "Pickup & Dropoff" : "Where's the pickup?")
                .font(UmuveTypography.h2Font)
                .foregroundColor(.umuveText)

            Text(bookingData.needsDropoff ? "Enter both pickup and delivery addresses" : "Enter the pickup location")
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveTextMuted)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
    }

    // MARK: - Pickup Section

    private var pickupSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("Pickup Address")
                .font(UmuveTypography.bodyFont.weight(.semibold))
                .foregroundColor(.umuveText)

            if viewModel.pickupSelected {
                // Mini-map preview
                pickupMiniMap
            } else {
                // Search field
                searchField(
                    query: $viewModel.pickupSearchQuery,
                    completions: viewModel.pickupCompletions,
                    placeholder: "Search pickup address...",
                    onSelect: { completion in
                        viewModel.selectPickupAddress(completion, bookingData: bookingData)
                    }
                )

                // "Use Current Location" button
                currentLocationButton
            }
        }
    }

    // MARK: - Dropoff Section

    private var dropoffSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("Dropoff Address")
                .font(UmuveTypography.bodyFont.weight(.semibold))
                .foregroundColor(.umuveText)

            if viewModel.dropoffSelected {
                // Mini-map preview
                dropoffMiniMap
            } else {
                // Search field
                searchField(
                    query: $viewModel.dropoffSearchQuery,
                    completions: viewModel.dropoffCompletions,
                    placeholder: "Search dropoff address...",
                    onSelect: { completion in
                        viewModel.selectDropoffAddress(completion, bookingData: bookingData)
                    }
                )
            }
        }
    }

    // MARK: - Search Field Component

    private func searchField(
        query: Binding<String>,
        completions: [MKLocalSearchCompletion],
        placeholder: String,
        onSelect: @escaping (MKLocalSearchCompletion) -> Void
    ) -> some View {
        VStack(spacing: 0) {
            // Text field
            HStack {
                Image(systemName: "magnifyingglass")
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
            .padding(UmuveSpacing.normal)
            .background(Color.umuveWhite)
            .cornerRadius(UmuveRadius.md)
            .overlay(
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .stroke(Color.umuveBorder, lineWidth: 2)
            )

            // Autocomplete suggestions
            if !completions.isEmpty {
                VStack(spacing: 0) {
                    ForEach(completions.prefix(5), id: \.self) { completion in
                        Button {
                            onSelect(completion)
                        } label: {
                            HStack(alignment: .top, spacing: UmuveSpacing.small) {
                                Image(systemName: "mappin.circle.fill")
                                    .foregroundColor(.umuvePrimary)
                                    .font(.system(size: 16))

                                VStack(alignment: .leading, spacing: 2) {
                                    Text(completion.title)
                                        .font(UmuveTypography.bodyFont)
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
                            }
                            .padding(UmuveSpacing.normal)
                            .background(Color.umuveWhite)
                        }
                        .buttonStyle(.plain)

                        if completion != completions.prefix(5).last {
                            Divider()
                                .padding(.leading, UmuveSpacing.normal)
                        }
                    }
                }
                .background(Color.umuveWhite)
                .cornerRadius(UmuveRadius.md)
                .overlay(
                    RoundedRectangle(cornerRadius: UmuveRadius.md)
                        .stroke(Color.umuveBorder, lineWidth: 1)
                )
                .shadow(color: .black.opacity(0.1), radius: 4, x: 0, y: 2)
                .padding(.top, UmuveSpacing.tiny)
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

    // MARK: - Dropoff Mini-Map

    private var dropoffMiniMap: some View {
        UmuveCard {
            VStack(spacing: UmuveSpacing.small) {
                // Map
                Map(coordinateRegion: $viewModel.dropoffRegion, annotationItems: dropoffAnnotations) { annotation in
                    MapPin(coordinate: annotation.coordinate, tint: .red)
                }
                .frame(height: 150)
                .cornerRadius(UmuveRadius.sm)

                // Address text
                VStack(alignment: .leading, spacing: 4) {
                    Text(bookingData.dropoffAddress.fullAddress)
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveText)
                        .lineLimit(2)

                    // Change button
                    Button {
                        viewModel.dropoffSelected = false
                        viewModel.dropoffSearchQuery = ""
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
            HStack {
                Image(systemName: "location.fill")
                Text("Use Current Location")
            }
            .font(UmuveTypography.bodyFont)
            .foregroundColor(.umuvePrimary)
            .frame(maxWidth: .infinity)
            .padding(.vertical, UmuveSpacing.normal)
            .background(Color.umuvePrimary.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        }
    }

    // MARK: - Distance Display

    private var distanceDisplay: some View {
        HStack(spacing: UmuveSpacing.small) {
            Image(systemName: "car.fill")
                .foregroundColor(.umuvePrimary)
                .font(.system(size: 18))

            if let distance = viewModel.calculatedDistance {
                Text("Distance: \(String(format: "%.1f", distance)) miles")
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)
            } else {
                Text("Calculating distance...")
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)
            }

            Spacer()
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .cornerRadius(UmuveRadius.md)
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.md)
                .stroke(Color.umuvePrimary.opacity(0.3), lineWidth: 2)
        )
        .onAppear {
            // Calculate distance when both addresses are selected
            viewModel.calculateDistance(bookingData: bookingData)
        }
    }

    // MARK: - Continue Button

    private var continueButton: some View {
        Button {
            // Calculate distance for Auto Transport before continuing
            if bookingData.needsDropoff {
                viewModel.calculateDistance(bookingData: bookingData)
            }
            wizardVM.completeCurrentStep()
        } label: {
            Text("Continue")
                .font(UmuveTypography.bodyFont.weight(.semibold))
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, UmuveSpacing.normal)
                .background(continueButtonEnabled ? Color.umuvePrimary : Color.umuveTextMuted)
                .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        }
        .disabled(!continueButtonEnabled)
        .padding(UmuveSpacing.large)
        .background(Color.umuveBackground)
    }

    // MARK: - Computed Properties

    private var continueButtonEnabled: Bool {
        // Pickup must be selected
        guard viewModel.pickupSelected else { return false }

        // If Auto Transport, dropoff must also be selected
        if bookingData.needsDropoff {
            return viewModel.dropoffSelected
        }

        return true
    }

    private var pickupAnnotations: [MapAnnotation] {
        guard let coordinate = bookingData.pickupCoordinate else { return [] }
        return [MapAnnotation(id: "pickup", coordinate: coordinate)]
    }

    private var dropoffAnnotations: [MapAnnotation] {
        guard let coordinate = bookingData.dropoffCoordinate else { return [] }
        return [MapAnnotation(id: "dropoff", coordinate: coordinate)]
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
