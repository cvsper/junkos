//
//  MapAddressPickerView.swift
//  Umuve
//
//  Map-based address picker — full screen, hides tab bar.
//

import SwiftUI
import MapKit

struct MapAddressPickerView: View {
    @EnvironmentObject var bookingData: BookingData
    @StateObject private var locationManager = LocationManager()
    @State private var region = MKCoordinateRegion(
        center: CLLocationCoordinate2D(latitude: 37.7749, longitude: -122.4194),
        span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
    )
    @State private var selectedAddress = ""
    @State private var isLocating = false
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        ZStack {
            // Map
            Map(coordinateRegion: $region, showsUserLocation: true)
                .ignoresSafeArea()
                .onChange(of: region.center.latitude) { _ in
                    reverseGeocode(coordinate: region.center)
                }

            // Center pin
            VStack {
                Spacer()
                Image(systemName: "mappin.circle.fill")
                    .font(.system(size: 50))
                    .foregroundColor(.umuvePrimary)
                    .shadow(color: .black.opacity(0.3), radius: 4, x: 0, y: 2)
                Spacer()
                    .frame(height: 200)
            }

            // Top bar
            VStack {
                topBar
                Spacer()
            }

            // Bottom sheet
            VStack {
                Spacer()
                bottomSheet
            }
        }
        .navigationBarHidden(true)
        .toolbar(.hidden, for: .tabBar)
        .onAppear {
            requestLocation()
        }
        .onReceive(locationManager.$location) { newLocation in
            guard let location = newLocation else { return }
            region.center = location.coordinate
            reverseGeocode(coordinate: location.coordinate)
            isLocating = false
        }
    }

    // MARK: - Top Bar
    private var topBar: some View {
        HStack {
            Button(action: { dismiss() }) {
                Image(systemName: "chevron.left")
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(.umuveText)
                    .padding(UmuveSpacing.medium)
                    .background(.ultraThinMaterial)
                    .clipShape(Circle())
                    .shadow(color: .black.opacity(0.1), radius: 4, x: 0, y: 2)
            }

            Spacer()
        }
        .padding(UmuveSpacing.normal)
    }

    // MARK: - Bottom Sheet
    private var bottomSheet: some View {
        VStack(spacing: UmuveSpacing.normal) {
            // Handle
            Capsule()
                .fill(Color.umuveBorder)
                .frame(width: 36, height: 5)
                .padding(.top, UmuveSpacing.small)

            // Address display
            VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                HStack {
                    Image(systemName: "mappin.and.ellipse")
                        .foregroundColor(.umuvePrimary)
                        .font(.system(size: 20))

                    Text("Service Location")
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuveText)

                    Spacer()
                }

                Text(selectedAddress.isEmpty ? "Move map to select location" : selectedAddress)
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(selectedAddress.isEmpty ? .umuveTextMuted : .umuveText)
                    .lineLimit(2)

                Text("You can always modify address later")
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.umuveTextMuted)
            }
            .padding(UmuveSpacing.normal)
            .background(Color.umuveBackground)
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))

            // Locate Me button
            Button(action: {
                isLocating = true
                requestLocation()
            }) {
                HStack {
                    if isLocating {
                        ProgressView()
                            .tint(.umuvePrimary)
                    } else {
                        Image(systemName: "location.fill")
                    }
                    Text(isLocating ? "Locating..." : "Locate Me")
                }
            }
            .buttonStyle(UmuveSecondaryButtonStyle())
            .disabled(isLocating)

            // Confirm button
            NavigationLink(
                destination: ServiceSelectionRedesignView().environmentObject(bookingData)
            ) {
                Text("Confirm Address")
            }
            .buttonStyle(UmuvePrimaryButtonStyle(isEnabled: !selectedAddress.isEmpty))
            .disabled(selectedAddress.isEmpty)
        }
        .padding(UmuveSpacing.large)
        .background(
            RoundedRectangle(cornerRadius: 24, style: .continuous)
                .fill(Color.white)
                .shadow(color: .black.opacity(0.1), radius: 20, x: 0, y: -5)
        )
    }

    // MARK: - Helpers

    private func requestLocation() {
        locationManager.requestLocation()
    }

    private func reverseGeocode(coordinate: CLLocationCoordinate2D) {
        let geocoder = CLGeocoder()
        let location = CLLocation(latitude: coordinate.latitude, longitude: coordinate.longitude)

        geocoder.reverseGeocodeLocation(location) { placemarks, error in
            guard let placemark = placemarks?.first else { return }

            var parts: [String] = []
            if let subThoroughfare = placemark.subThoroughfare {
                parts.append(subThoroughfare)
            }
            if let thoroughfare = placemark.thoroughfare {
                parts.append(thoroughfare)
            }

            let street = parts.joined(separator: " ")
            var addressParts: [String] = []
            if !street.isEmpty { addressParts.append(street) }
            if let city = placemark.locality { addressParts.append(city) }
            if let state = placemark.administrativeArea { addressParts.append(state) }
            if let zip = placemark.postalCode { addressParts.append(zip) }

            selectedAddress = addressParts.joined(separator: ", ")

            // Update booking data
            bookingData.address.street = street
            bookingData.address.city = placemark.locality ?? ""
            bookingData.address.state = placemark.administrativeArea ?? ""
            bookingData.address.zipCode = placemark.postalCode ?? ""
        }
    }
}

#Preview {
    NavigationStack {
        MapAddressPickerView()
            .environmentObject(BookingData())
    }
}
