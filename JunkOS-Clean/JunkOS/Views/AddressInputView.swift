//
//  AddressInputView.swift
//  JunkOS
//
//  Address input screen with map preview
//  Enhanced with smooth transitions and button haptics
//  SF Symbols Reference: https://developer.apple.com/sf-symbols/
//

import SwiftUI
import MapKit
import CoreLocation

struct AddressInputView: View {
    @EnvironmentObject var bookingData: BookingData
    @Environment(\.presentationMode) var presentationMode
    @StateObject private var viewModel = AddressInputViewModel()
    
    var body: some View {
        ScrollView {
            VStack(spacing: JunkSpacing.xxlarge) {
                // Header
                ScreenHeader(
                    title: "Your Location",
                    subtitle: "Where should we pick up?",
                    progress: 0.2
                )
                
                // Map preview
                mapPreview
                
                // Form
                addressForm
                
                // Auto-detect button
                autoDetectButton
                
                Spacer()
            }
            .padding(JunkSpacing.large)
        }
        .background(Color.junkBackground.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .safeAreaInset(edge: .bottom) {
            continueButton
        }
        .onAppear {
            viewModel.startAnimations()
        }
    }
    
    // MARK: - Map Preview
    private var mapPreview: some View {
        JunkCard {
            VStack(spacing: 0) {
                Map(coordinateRegion: $viewModel.region)
                    .frame(height: 200)
                    .cornerRadius(12)
                    .disabled(true)
                
                HStack {
                    Image(systemName: "mappin.circle.fill")
                        .foregroundColor(.junkPrimary)
                    Text("Map Preview")
                        .font(JunkTypography.bodySmallFont)
                        .foregroundColor(.junkTextMuted)
                }
                .padding(JunkSpacing.small)
            }
        }
    }
    
    // MARK: - Address Form
    private var addressForm: some View {
        VStack(spacing: JunkSpacing.normal) {
            // SF Symbol: house.fill for street address
            InputField(
                icon: "house.fill",
                placeholder: "Street Address",
                text: $bookingData.address.street
            )
            
            // SF Symbol: building.2.fill for apartment/unit
            InputField(
                icon: "building.2.fill",
                placeholder: "Unit/Apt (Optional)",
                text: $bookingData.address.unit
            )
            
            HStack(spacing: JunkSpacing.normal) {
                // SF Symbol: building.2.crop.circle.fill for city
                InputField(
                    icon: "building.2.crop.circle.fill",
                    placeholder: "City",
                    text: $bookingData.address.city
                )
                
                // SF Symbol: mappin.circle.fill for location/zip code
                InputField(
                    icon: "mappin.circle.fill",
                    placeholder: "ZIP",
                    text: $bookingData.address.zipCode
                )
                .frame(width: 100)
            }
        }
    }
    
    // MARK: - Auto Detect Button (with haptic)
    private var autoDetectButton: some View {
        VStack(spacing: JunkSpacing.small) {
            Button(action: {
                detectLocation()
            }) {
                HStack {
                    if viewModel.isLoadingLocation {
                        ProgressView()
                            .progressViewStyle(CircularProgressViewStyle())
                            .scaleEffect(0.8)
                    } else {
                        Image(systemName: "location.fill")
                    }
                    Text(viewModel.isLoadingLocation ? "Detecting..." : "Use Current Location")
                }
            }
            .buttonStyle(JunkSecondaryButtonStyle())
            .disabled(viewModel.isLoadingLocation)
            
            // Error message
            if let error = viewModel.locationError {
                HStack {
                    Image(systemName: "exclamationmark.triangle.fill")
                        .foregroundColor(.red)
                    Text(error)
                        .font(JunkTypography.bodySmallFont)
                        .foregroundColor(.red)
                }
                .padding(JunkSpacing.small)
                .background(Color.red.opacity(0.1))
                .cornerRadius(8)
                .transition(.scale.combined(with: .opacity))
            }
        }
        .opacity(viewModel.elementsVisible ? 1 : 0)
        .scaleEffect(viewModel.elementsVisible ? 1 : 0.9)
        .animation(AnimationConstants.smoothSpring.delay(0.2), value: viewModel.elementsVisible)
    }
    
    // MARK: - Location Detection
    private func detectLocation() {
        viewModel.detectLocation { result in
            switch result {
            case .success(let address):
                bookingData.address = address
            case .failure(let error):
                print("Geocoding error: \(error.localizedDescription)")
            }
        }
    }
    
    // MARK: - Continue Button
    private var continueButton: some View {
        NavigationLink(
            destination: PhotoUploadView().environmentObject(bookingData),
            label: {
                Text("Continue →")
            }
        )
        .buttonStyle(JunkPrimaryButtonStyle())
        .padding(JunkSpacing.large)
        .background(Color.junkBackground)
        .disabled(!bookingData.isAddressValid)
        .opacity(bookingData.isAddressValid ? 1 : 0.5)
    }
}

// MARK: - Input Field Component
struct InputField: View {
    let icon: String // SF Symbol name
    let placeholder: String
    @Binding var text: String
    
    var body: some View {
        HStack {
            // Using SF Symbol instead of emoji
            // https://developer.apple.com/design/human-interface-guidelines/sf-symbols
            Image(systemName: icon)
                .font(.system(size: 20))
                .foregroundColor(.junkPrimary)
            
            TextField(placeholder, text: $text)
                .font(JunkTypography.bodyFont)
                .autocapitalization(.words)
        }
        .padding(JunkSpacing.normal)
        .background(Color.junkWhite)
        .cornerRadius(12)
        .overlay(
            RoundedRectangle(cornerRadius: 12)
                .stroke(Color.junkBorder, lineWidth: 2)
        )
    }
}

// MARK: - Preview
struct AddressInputView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            AddressInputView()
                .environmentObject(BookingData())
        }
    }
}
