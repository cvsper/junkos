//
//  BookingWizardView.swift
//  Umuve
//
//  Main booking wizard container with step-based navigation and progress indicator
//

import SwiftUI

struct BookingWizardView: View {
    @StateObject private var bookingData = BookingData()
    @StateObject private var wizardVM = BookingWizardViewModel()
    @Environment(\.dismiss) private var dismiss

    var body: some View {
        VStack(spacing: 0) {
            // Progress indicator
            progressIndicator
                .padding(.horizontal, UmuveSpacing.large)
                .padding(.vertical, UmuveSpacing.normal)
                .background(Color.umuveWhite)
                .shadow(color: .black.opacity(0.05), radius: 2, x: 0, y: 2)

            // Step content
            stepContent
                .frame(maxWidth: .infinity, maxHeight: .infinity)

            // Running price estimate bar
            if bookingData.estimatedPrice != nil {
                priceEstimateBar
                    .transition(.move(edge: .bottom).combined(with: .opacity))
            }
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .navigationBarTitleDisplayMode(.inline)
        .toolbar {
            ToolbarItem(placement: .navigationBarLeading) {
                if wizardVM.canGoBack {
                    Button {
                        wizardVM.goBack()
                    } label: {
                        Image(systemName: "chevron.left")
                            .foregroundColor(.umuvePrimary)
                            .font(.system(size: 16, weight: .semibold))
                    }
                }
            }

            ToolbarItem(placement: .principal) {
                Text("New Booking")
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.umuveText)
            }

            ToolbarItem(placement: .navigationBarTrailing) {
                Button {
                    dismiss()
                } label: {
                    Image(systemName: "xmark")
                        .foregroundColor(.umuveTextMuted)
                        .font(.system(size: 14, weight: .semibold))
                }
            }
        }
        .environmentObject(bookingData)
        .environmentObject(wizardVM)
    }

    // MARK: - Progress Indicator

    private var progressIndicator: some View {
        VStack(spacing: UmuveSpacing.small) {
            // Progress dots with connecting lines
            HStack(spacing: 0) {
                ForEach(0..<wizardVM.stepCount, id: \.self) { step in
                    VStack(spacing: 4) {
                        // Dot
                        ZStack {
                            Circle()
                                .strokeBorder(lineWidth: 2)
                                .foregroundColor(dotColor(for: step))
                                .frame(width: 12, height: 12)
                                .background(
                                    Circle()
                                        .fill(dotFillColor(for: step))
                                )

                            // Ring for current step
                            if step == wizardVM.currentStep {
                                Circle()
                                    .strokeBorder(lineWidth: 2)
                                    .foregroundColor(.umuvePrimary.opacity(0.3))
                                    .frame(width: 20, height: 20)
                            }
                        }
                        .onTapGesture {
                            if wizardVM.isStepAccessible(step) {
                                wizardVM.goToStep(step)
                            }
                        }

                        // Step label
                        Text(wizardVM.stepTitle(for: step))
                            .font(UmuveTypography.smallFont)
                            .foregroundColor(
                                step == wizardVM.currentStep ? .umuvePrimary :
                                wizardVM.completedSteps.contains(step) ? .umuveText :
                                .umuveTextMuted
                            )
                    }
                    .frame(maxWidth: .infinity)

                    // Connecting line (except after last step)
                    if step < wizardVM.stepCount - 1 {
                        Rectangle()
                            .fill(lineColor(from: step, to: step + 1))
                            .frame(height: 2)
                            .frame(maxWidth: .infinity)
                            .offset(y: -8)
                    }
                }
            }
        }
    }

    // MARK: - Step Content

    @ViewBuilder
    private var stepContent: some View {
        ScrollView {
            Group {
                switch wizardVM.currentStep {
                case 0:
                    // Service Selection - will be implemented in Plan 02
                    placeholderStep(
                        icon: "truck.box.fill",
                        title: "Service Selection",
                        description: "Choose between Junk Removal or Auto Transport"
                    )

                case 1:
                    // Address Input - will be refactored in Plan 03
                    placeholderStep(
                        icon: "mappin.circle.fill",
                        title: "Address Entry",
                        description: "Enter pickup location (and dropoff for auto transport)"
                    )

                case 2:
                    // Photo Upload - will be cleaned up in Plan 04
                    placeholderStep(
                        icon: "camera.fill",
                        title: "Photos",
                        description: "Upload photos of items to be hauled"
                    )

                case 3:
                    // Schedule - will be cleaned up in Plan 04
                    placeholderStep(
                        icon: "calendar",
                        title: "Schedule",
                        description: "Pick your preferred date and time"
                    )

                case 4:
                    // Review - will be created in Plan 05
                    placeholderStep(
                        icon: "checkmark.circle.fill",
                        title: "Review & Confirm",
                        description: "Review your booking details before confirming"
                    )

                default:
                    EmptyView()
                }
            }
            .padding(.horizontal, UmuveSpacing.large)
            .padding(.vertical, UmuveSpacing.normal)
        }
    }

    // MARK: - Price Estimate Bar

    private var priceEstimateBar: some View {
        VStack(spacing: 0) {
            // Divider
            Rectangle()
                .fill(Color.umuveTextTertiary.opacity(0.2))
                .frame(height: 1)

            HStack {
                VStack(alignment: .leading, spacing: 2) {
                    Text("Estimated Total")
                        .font(UmuveTypography.smallFont)
                        .foregroundColor(.umuveTextMuted)

                    if let price = bookingData.estimatedPrice {
                        Text("$\(String(format: "%.2f", price))")
                            .font(UmuveTypography.h2Font)
                            .foregroundColor(.umuvePrimary)
                    }
                }

                Spacer()

                // Expandable breakdown (tap to show details)
                if bookingData.priceBreakdown != nil {
                    Button {
                        // TODO: Show expandable price breakdown
                    } label: {
                        HStack(spacing: 4) {
                            Text("Details")
                                .font(UmuveTypography.bodySmallFont)
                                .foregroundColor(.umuvePrimary)

                            Image(systemName: "chevron.up")
                                .font(.system(size: 10, weight: .semibold))
                                .foregroundColor(.umuvePrimary)
                        }
                        .padding(.horizontal, UmuveSpacing.small)
                        .padding(.vertical, UmuveSpacing.tiny)
                        .background(Color.umuvePrimary.opacity(0.1))
                        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
                    }
                }
            }
            .padding(.horizontal, UmuveSpacing.large)
            .padding(.vertical, UmuveSpacing.normal)
        }
        .background(Color.umuveWhite)
        .shadow(color: .black.opacity(0.1), radius: 4, x: 0, y: -2)
    }

    // MARK: - Placeholder Step

    private func placeholderStep(icon: String, title: String, description: String) -> some View {
        VStack(spacing: UmuveSpacing.large) {
            Spacer()

            VStack(spacing: UmuveSpacing.normal) {
                Image(systemName: icon)
                    .font(.system(size: 48))
                    .foregroundColor(.umuvePrimary.opacity(0.3))

                Text(title)
                    .font(UmuveTypography.h2Font)
                    .foregroundColor(.umuveText)

                Text(description)
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)
                    .multilineTextAlignment(.center)
                    .padding(.horizontal, UmuveSpacing.large)

                Text("Step \(wizardVM.currentStep + 1) of \(wizardVM.stepCount)")
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextTertiary)
                    .padding(.top, UmuveSpacing.small)
            }

            Spacer()

            // Test navigation button
            Button {
                wizardVM.completeCurrentStep()
            } label: {
                Text(wizardVM.isLastStep ? "Complete" : "Continue")
                    .font(UmuveTypography.bodyFont.weight(.semibold))
                    .foregroundColor(.white)
                    .frame(maxWidth: .infinity)
                    .padding(.vertical, UmuveSpacing.normal)
                    .background(Color.umuvePrimary)
                    .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
            }
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }

    // MARK: - Helper Methods

    private func dotColor(for step: Int) -> Color {
        if wizardVM.completedSteps.contains(step) || step == wizardVM.currentStep {
            return .umuvePrimary
        }
        return .umuveTextTertiary.opacity(0.3)
    }

    private func dotFillColor(for step: Int) -> Color {
        if wizardVM.completedSteps.contains(step) || step == wizardVM.currentStep {
            return .umuvePrimary
        }
        return .clear
    }

    private func lineColor(from: Int, to: Int) -> Color {
        if wizardVM.completedSteps.contains(from) && (wizardVM.completedSteps.contains(to) || to == wizardVM.currentStep) {
            return .umuvePrimary
        }
        return .umuveTextTertiary.opacity(0.2)
    }
}

#Preview {
    NavigationStack {
        BookingWizardView()
    }
}
