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
    @State private var isPriceExpanded = false

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

            // Running price estimate bar (hide on review step)
            if bookingData.estimatedPrice != nil && wizardVM.currentStep < 4 {
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
        .onChange(of: wizardVM.currentStep) { _ in
            // Refresh pricing when step changes
            Task {
                await wizardVM.refreshPricing(bookingData: bookingData)
            }
        }
        .onChange(of: bookingData.bookingCompleted) { completed in
            if completed {
                // Reset booking data and dismiss wizard
                bookingData.reset()
                dismiss()
            }
        }
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
        Group {
            switch wizardVM.currentStep {
            case 0:
                // Service Selection
                ServiceTypeSelectionView()
                    .environmentObject(bookingData)
                    .environmentObject(wizardVM)

            case 1:
                // Address Input - completed in Plan 03
                AddressInputView()

            case 2:
                // Photo Upload
                PhotoUploadView()
                    .environmentObject(bookingData)
                    .environmentObject(wizardVM)

            case 3:
                // Schedule
                DateTimePickerView()
                    .environmentObject(bookingData)
                    .environmentObject(wizardVM)

            case 4:
                // Review & Confirm
                BookingReviewView()
                    .environmentObject(bookingData)
                    .environmentObject(wizardVM)

            default:
                EmptyView()
            }
        }
    }

    // MARK: - Price Estimate Bar

    private var priceEstimateBar: some View {
        VStack(spacing: 0) {
            // Divider
            Rectangle()
                .fill(Color.umuveTextTertiary.opacity(0.2))
                .frame(height: 1)

            // Collapsed summary
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
                        withAnimation(.easeInOut(duration: 0.3)) {
                            isPriceExpanded.toggle()
                        }
                    } label: {
                        HStack(spacing: 4) {
                            Text("Details")
                                .font(UmuveTypography.bodySmallFont)
                                .foregroundColor(.umuvePrimary)

                            Image(systemName: isPriceExpanded ? "chevron.down" : "chevron.up")
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

            // Expanded breakdown
            if isPriceExpanded, let breakdown = bookingData.priceBreakdown {
                VStack(spacing: UmuveSpacing.small) {
                    Divider()

                    priceLineItem("Subtotal", amount: breakdown.subtotal)
                    priceLineItem("Service Fee", amount: breakdown.serviceFee)

                    if breakdown.volumeDiscount < 0 {
                        priceLineItem("Volume Discount", amount: breakdown.volumeDiscount, isDiscount: true)
                    }

                    if breakdown.timeSurge > 0 {
                        priceLineItem("Time Surcharge", amount: breakdown.timeSurge)
                    }

                    if breakdown.zoneSurge > 0 {
                        priceLineItem("Zone Surcharge", amount: breakdown.zoneSurge)
                    }

                    Divider()

                    HStack {
                        Text("Total")
                            .font(UmuveTypography.bodyFont.weight(.bold))
                            .foregroundColor(.umuveText)

                        Spacer()

                        Text("$\(String(format: "%.2f", breakdown.total))")
                            .font(UmuveTypography.bodyFont.weight(.bold))
                            .foregroundColor(.umuvePrimary)
                    }

                    Text("Est. duration: \(breakdown.estimatedDurationMinutes) min")
                        .font(UmuveTypography.smallFont)
                        .foregroundColor(.umuveTextMuted)
                        .frame(maxWidth: .infinity, alignment: .leading)
                }
                .padding(.horizontal, UmuveSpacing.large)
                .padding(.bottom, UmuveSpacing.normal)
                .transition(.opacity.combined(with: .move(edge: .top)))
            }
        }
        .background(Color.umuveWhite)
        .shadow(color: .black.opacity(0.1), radius: 4, x: 0, y: -2)
    }

    private func priceLineItem(_ label: String, amount: Double, isDiscount: Bool = false) -> some View {
        HStack {
            Text(label)
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(.umuveTextMuted)

            Spacer()

            Text("\(isDiscount ? "" : "$")\(String(format: "%.2f", abs(amount)))")
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(isDiscount ? .green : .umuveText)
        }
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
