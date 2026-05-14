//
//  JunkVolumeSelectionView.swift
//  Umuve
//
//  Volume tier selection - first step of the junk removal booking wizard.
//

import SwiftUI

struct JunkVolumeSelectionView: View {
    @EnvironmentObject var bookingData: BookingData
    @EnvironmentObject var wizardVM: BookingWizardViewModel
    @StateObject private var viewModel = ServiceSelectionViewModel()

    var body: some View {
        ScrollView {
            VStack(alignment: .leading, spacing: UmuveSpacing.xlarge) {
                // Header
                VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                    Text("Junk Removal")
                        .font(UmuveTypography.h1Font)
                        .foregroundColor(.umuveText)

                    Text("How much do you have?")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveTextMuted)
                }

                truckFillSelector
            }
            .padding(.horizontal, UmuveSpacing.large)
            .padding(.top, UmuveSpacing.normal)
            .padding(.bottom, UmuveSpacing.xxlarge)
        }
        .onAppear {
            // Junk Removal is the only service — set it as soon as the wizard opens.
            if bookingData.serviceType != .junkRemoval {
                bookingData.serviceType = .junkRemoval
                Task {
                    await viewModel.requestPricingEstimate(for: bookingData)
                }
            }
        }
        .safeAreaInset(edge: .bottom) {
            continueButton
                .padding(.horizontal, UmuveSpacing.large)
                .padding(.vertical, UmuveSpacing.normal)
                .background(Color.umuveBackground)
        }
    }

    // MARK: - Truck Fill Selector

    private var truckFillSelector: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            LazyVGrid(columns: [
                GridItem(.flexible(), spacing: UmuveSpacing.small),
                GridItem(.flexible(), spacing: UmuveSpacing.small)
            ], spacing: UmuveSpacing.small) {
                ForEach(VolumeTier.allCases, id: \.self) { tier in
                    volumeTierCard(tier: tier)
                }
            }
        }
    }

    private func volumeTierCard(tier: VolumeTier) -> some View {
        let isSelected = bookingData.volumeTier == tier

        return Button {
            withAnimation(.easeInOut(duration: 0.2)) {
                bookingData.volumeTier = tier
            }

            Task {
                await viewModel.requestPricingEstimate(for: bookingData)
            }
        } label: {
            VStack(spacing: UmuveSpacing.small) {
                truckFillVisualization(for: tier)
                    .frame(height: 40)

                Text(tier.rawValue)
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.umuveText)

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
        JunkVolumeSelectionView()
            .environmentObject(BookingData())
            .environmentObject(BookingWizardViewModel())
    }
}
