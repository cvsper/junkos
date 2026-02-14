//
//  ServiceTypeSelectionView.swift
//  Umuve
//
//  Service type selection screen - first step of booking wizard
//

import SwiftUI

struct ServiceTypeSelectionView: View {
    @EnvironmentObject var bookingData: BookingData
    @EnvironmentObject var wizardVM: BookingWizardViewModel
    @StateObject private var viewModel = ServiceSelectionViewModel()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: UmuveSpacing.xlarge) {
                // Header
                VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                    Text("What do you need?")
                        .font(UmuveTypography.h1Font)
                        .foregroundColor(.umuveText)

                    Text("Choose a service")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveTextMuted)
                }

                // Service Type Cards
                VStack(spacing: UmuveSpacing.normal) {
                    serviceTypeCard(
                        type: .junkRemoval,
                        icon: "truck.box.fill",
                        title: "Junk Removal",
                        description: ServiceType.junkRemoval.description,
                        isSelected: bookingData.serviceType == .junkRemoval
                    )

                    serviceTypeCard(
                        type: .autoTransport,
                        icon: "car.fill",
                        title: "Auto Transport",
                        description: ServiceType.autoTransport.description,
                        isSelected: bookingData.serviceType == .autoTransport
                    )
                }

                // Conditional Detail Section
                if let serviceType = bookingData.serviceType {
                    if serviceType == .junkRemoval {
                        truckFillSelector
                    } else if serviceType == .autoTransport {
                        vehicleInfoSection
                    }
                }
            }
            .padding(.horizontal, UmuveSpacing.large)
            .padding(.top, UmuveSpacing.normal)
            .padding(.bottom, UmuveSpacing.xxlarge)
        }
        .safeAreaInset(edge: .bottom) {
            continueButton
                .padding(.horizontal, UmuveSpacing.large)
                .padding(.vertical, UmuveSpacing.normal)
                .background(Color.umuveBackground)
        }
    }

    // MARK: - Service Type Card

    private func serviceTypeCard(type: ServiceType, icon: String, title: String, description: String, isSelected: Bool) -> some View {
        Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                bookingData.serviceType = type
            }

            // Request initial pricing estimate
            Task {
                await viewModel.requestPricingEstimate(for: bookingData)
            }
        } label: {
            HStack(spacing: UmuveSpacing.normal) {
                // Icon
                ZStack {
                    Circle()
                        .fill(isSelected ? Color.umuvePrimary.opacity(0.1) : Color.umuveBorder.opacity(0.2))
                        .frame(width: 60, height: 60)

                    Image(systemName: icon)
                        .font(.system(size: 28))
                        .foregroundColor(isSelected ? .umuvePrimary : .umuveTextMuted)
                }

                // Text content
                VStack(alignment: .leading, spacing: 4) {
                    Text(title)
                        .font(UmuveTypography.h2Font)
                        .foregroundColor(.umuveText)

                    Text(description)
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveTextMuted)
                        .multilineTextAlignment(.leading)
                        .fixedSize(horizontal: false, vertical: true)
                }

                Spacer()

                // Checkmark
                if isSelected {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.umuvePrimary)
                }
            }
            .padding(UmuveSpacing.normal)
            .frame(maxWidth: .infinity, alignment: .leading)
            .background(
                RoundedRectangle(cornerRadius: UmuveRadius.lg)
                    .fill(isSelected ? Color.umuvePrimary.opacity(0.05) : Color.umuveWhite)
            )
            .overlay(
                RoundedRectangle(cornerRadius: UmuveRadius.lg)
                    .strokeBorder(
                        isSelected ? Color.umuvePrimary : Color.umuveBorder,
                        lineWidth: isSelected ? 3 : 1
                    )
            )
        }
        .buttonStyle(PlainButtonStyle())
    }

    // MARK: - Truck Fill Selector

    private var truckFillSelector: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("How much do you have?")
                .font(UmuveTypography.h2Font)
                .foregroundColor(.umuveText)

            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: UmuveSpacing.small),
                GridItem(.flexible(), spacing: UmuveSpacing.small)
            ], spacing: UmuveSpacing.small) {
                ForEach(VolumeTier.allCases, id: \.self) { tier in
                    volumeTierCard(tier: tier)
                }
            }
        }
        .transition(.opacity.combined(with: .move(edge: .top)))
    }

    private func volumeTierCard(tier: VolumeTier) -> some View {
        let isSelected = bookingData.volumeTier == tier

        return Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                bookingData.volumeTier = tier
            }

            // Update pricing estimate
            Task {
                await viewModel.requestPricingEstimate(for: bookingData)
            }
        } label: {
            VStack(spacing: UmuveSpacing.small) {
                // Visual fill indicator
                truckFillVisualization(for: tier)
                    .frame(height: 40)

                // Tier name
                Text(tier.rawValue)
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)

                // Description
                Text(tier.description)
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.umuveTextMuted)
            }
            .frame(maxWidth: .infinity)
            .padding(UmuveSpacing.normal)
            .background(
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .fill(isSelected ? Color.umuvePrimary.opacity(0.05) : Color.umuveWhite)
            )
            .overlay(
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .strokeBorder(
                        isSelected ? Color.umuvePrimary : Color.umuveBorder,
                        lineWidth: isSelected ? 2 : 1
                    )
            )
        }
        .buttonStyle(PlainButtonStyle())
    }

    private func truckFillVisualization(for tier: VolumeTier) -> some View {
        HStack(spacing: 3) {
            ForEach(0..<4, id: \.self) { index in
                let fillLevel = tier.fillLevel
                let blockCount = Int(fillLevel * 4)
                let isFilled = index < blockCount

                Rectangle()
                    .fill(isFilled ? Color.umuvePrimary : Color.umuveBorder.opacity(0.3))
                    .frame(width: 8)
            }
        }
        .frame(height: 40)
    }

    // MARK: - Vehicle Info Section

    private var vehicleInfoSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            Text("Vehicle Details")
                .font(UmuveTypography.h2Font)
                .foregroundColor(.umuveText)

            VStack(spacing: UmuveSpacing.normal) {
                // Vehicle Make
                vehicleInputField(
                    icon: "car.fill",
                    placeholder: "Vehicle Make (e.g., Toyota)",
                    text: $bookingData.vehicleMake
                )

                // Vehicle Model
                vehicleInputField(
                    icon: "car.side",
                    placeholder: "Vehicle Model (e.g., Camry)",
                    text: $bookingData.vehicleModel
                )

                // Vehicle Year
                vehicleInputField(
                    icon: "calendar",
                    placeholder: "Vehicle Year (e.g., 2020)",
                    text: $bookingData.vehicleYear
                )
                .keyboardType(.numberPad)

                // Surcharge Toggles
                VStack(spacing: UmuveSpacing.small) {
                    Toggle(isOn: Binding(
                        get: { !bookingData.isVehicleRunning },
                        set: { bookingData.isVehicleRunning = !$0 }
                    )) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Vehicle is non-running")
                                .font(UmuveTypography.bodyFont)
                                .foregroundColor(.umuveText)

                            if !bookingData.isVehicleRunning {
                                Text("Non-running vehicle surcharge applies")
                                    .font(UmuveTypography.captionFont)
                                    .foregroundColor(.umuveTextMuted)
                            }
                        }
                    }
                    .tint(.umuvePrimary)
                    .padding(UmuveSpacing.normal)
                    .background(Color.umuveWhite)
                    .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
                    .overlay(
                        RoundedRectangle(cornerRadius: UmuveRadius.md)
                            .strokeBorder(Color.umuveBorder, lineWidth: 1)
                    )

                    Toggle(isOn: $bookingData.needsEnclosedTrailer) {
                        VStack(alignment: .leading, spacing: 2) {
                            Text("Needs enclosed trailer")
                                .font(UmuveTypography.bodyFont)
                                .foregroundColor(.umuveText)

                            if bookingData.needsEnclosedTrailer {
                                Text("Enclosed trailer surcharge applies")
                                    .font(UmuveTypography.captionFont)
                                    .foregroundColor(.umuveTextMuted)
                            }
                        }
                    }
                    .tint(.umuvePrimary)
                    .padding(UmuveSpacing.normal)
                    .background(Color.umuveWhite)
                    .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
                    .overlay(
                        RoundedRectangle(cornerRadius: UmuveRadius.md)
                            .strokeBorder(Color.umuveBorder, lineWidth: 1)
                    )
                }
            }
        }
        .transition(.opacity.combined(with: .move(edge: .top)))
    }

    private func vehicleInputField(icon: String, placeholder: String, text: Binding<String>) -> some View {
        HStack(spacing: UmuveSpacing.normal) {
            Image(systemName: icon)
                .font(.system(size: 18))
                .foregroundColor(.umuveTextMuted)
                .frame(width: 24)

            TextField(placeholder, text: text)
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveText)
                .autocapitalization(.words)
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.md)
                .strokeBorder(Color.umuveBorder, lineWidth: 1)
        )
    }

    // MARK: - Continue Button

    private var continueButton: some View {
        Button {
            wizardVM.completeCurrentStep()
        } label: {
            Text("Continue")
        }
        .buttonStyle(UmuvePrimaryButtonStyle(isEnabled: bookingData.isServiceConfigured))
        .disabled(!bookingData.isServiceConfigured)
    }
}

#Preview {
    NavigationStack {
        ServiceTypeSelectionView()
            .environmentObject(BookingData())
            .environmentObject(BookingWizardViewModel())
    }
}
