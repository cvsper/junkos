//
//  BookingWizardView.swift
//  Umuve
//
//  Main booking wizard container with step-based navigation and progress indicator
//

import SwiftUI

struct BookingWizardView: View {
    @StateObject private var bookingData: BookingData
    @StateObject private var wizardVM = BookingWizardViewModel()
    @Environment(\.dismiss) private var dismiss
    @State private var isPriceExpanded = false

    /// Initialize the wizard, optionally pre-seeding the service the caller
    /// (e.g. a Home card) already knows the user wants. Without this, the
    /// wizard silently dropped any selection made on the prior screen.
    init(prefilledService: ServiceType? = nil) {
        let data = BookingData()
        if let service = prefilledService {
            data.serviceType = service
        }
        _bookingData = StateObject(wrappedValue: data)
    }

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
        // Hide the MainTabView tab bar while the wizard is on screen.
        // Otherwise the bottom-pinned Confirm & Pay button on the
        // Estimate step gets visually overlapped by the tab bar
        // (multiple users reported this as "the button is being
        // covered by the menu"). A focused multi-step flow shouldn't
        // expose the parent tab bar anyway.
        .toolbar(.hidden, for: .tabBar)
        // Suppress the system back button — we ship a custom leading
        // chevron below that steps backward within the wizard rather than
        // popping the whole flow. Without this, both arrows render.
        .navigationBarBackButtonHidden(true)
        // Lock the navigation-bar background to the page color in both the
        // scrolled and at-top states. Otherwise iOS 15+ switches between
        // its translucent blur (when content scrolls under) and a
        // transparent edge appearance (at top), which made the back-button
        // tint appear to "change colors" as the user scrolled.
        .toolbarBackground(Color.umuveBackground, for: .navigationBar)
        .toolbarBackground(.visible, for: .navigationBar)
        .tint(.umuvePrimary)
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
                    .accessibilityLabel("Back to previous step")
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
                .accessibilityLabel("Close booking")
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
    //
    // Two-row treatment:
    //   • Top row — six SF Symbol icons connected by a track whose red
    //     fill animates between steps. Current step's icon scales up
    //     and pulses subtly with a symbol effect; completed steps fill
    //     solid; future steps are muted grey.
    //   • Bottom row — "Step X of 6 — Title" so the user always knows
    //     where they are without the screen having to render 6 cramped
    //     labels.
    // Word labels under every dot were causing the squished look on
    // small screens; the icons + step counter convey the same info
    // with way more breathing room and a touch of motion.

    private static let stepIcons: [String] = [
        "mappin.and.ellipse",   // Address
        "camera.fill",          // Photos
        "shippingbox.fill",     // Items
        "calendar",             // Schedule
        "doc.text.magnifyingglass", // Estimate
        "creditcard.fill",      // Payment
    ]

    private var progressIndicator: some View {
        VStack(spacing: UmuveSpacing.small) {
            GeometryReader { geo in
                let count = wizardVM.displayedStepCount
                // Width consumed by the 6 circles themselves, evenly distributed
                let trackWidth = geo.size.width
                // Fill ratio = progress through steps. Step 0 = 0/5 etc.
                let progress = count > 1
                    ? min(CGFloat(wizardVM.currentStep) / CGFloat(count - 1), 1)
                    : 0

                ZStack(alignment: .leading) {
                    // Background track
                    Capsule()
                        .fill(Color.umuveBorder)
                        .frame(height: 4)

                    // Animated red fill
                    Capsule()
                        .fill(Color.umuvePrimary)
                        .frame(width: trackWidth * progress, height: 4)
                        .animation(.smooth(duration: 0.45), value: progress)

                    // Six icons evenly distributed on top of the track
                    HStack(spacing: 0) {
                        ForEach(0..<count, id: \.self) { step in
                            progressIcon(for: step)
                                .frame(maxWidth: .infinity)
                        }
                    }
                }
            }
            .frame(height: 32)

            // Step counter — "Step X of 6 — Items"
            HStack(spacing: 4) {
                Text("Step \(wizardVM.currentStep + 1) of \(wizardVM.displayedStepCount)")
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextMuted)
                Text("·")
                    .font(UmuveTypography.smallFont)
                    .foregroundColor(.umuveTextTertiary)
                Text(wizardVM.stepTitle(for: wizardVM.currentStep))
                    .font(UmuveTypography.smallFont.weight(.bold))
                    .foregroundColor(.umuvePrimary)
            }
            .animation(.smooth(duration: 0.3), value: wizardVM.currentStep)
        }
    }

    @ViewBuilder
    private func progressIcon(for step: Int) -> some View {
        let isCurrent = step == wizardVM.currentStep
        let isCompleted = wizardVM.completedSteps.contains(step) || step < wizardVM.currentStep
        let isFilled = isCurrent || isCompleted
        let iconName = Self.stepIcons[min(step, Self.stepIcons.count - 1)]

        ZStack {
            Circle()
                .fill(isFilled ? Color.umuvePrimary : Color.umuveBackground)
                .frame(width: isCurrent ? 32 : 26, height: isCurrent ? 32 : 26)
                .overlay(
                    Circle()
                        .strokeBorder(
                            isFilled ? Color.umuvePrimary : Color.umuveBorder,
                            lineWidth: 2
                        )
                )
                .shadow(color: isCurrent ? Color.umuvePrimary.opacity(0.35) : .clear, radius: 6, x: 0, y: 2)
                .animation(.smooth(duration: 0.35), value: isCurrent)

            Image(systemName: iconName)
                .font(.system(size: isCurrent ? 14 : 11, weight: .bold))
                .foregroundColor(isFilled ? .white : .umuveTextTertiary)
                .scaleEffect(isCurrent ? 1.0 : 0.95)
                .animation(.smooth(duration: 0.3), value: isCurrent)
        }
        .onTapGesture {
            if wizardVM.isStepAccessible(step) {
                wizardVM.goToStep(step)
            }
        }
    }

    // MARK: - Step Content

    @ViewBuilder
    private var stepContent: some View {
        // Step order mirrors the web booking flow (platform/src/components/
        // booking/progress-bar.tsx) so iOS and web present the same six
        // questions in the same order: Address → Photos → Items → Schedule
        // → Estimate (review) → Payment.
        //
        // Wrapping the step content in a transition + id-keyed view triggers
        // a horizontal slide whenever wizardVM.currentStep changes. Respects
        // accessibilityReduceMotion via .smooth() default (system handles it).
        Group {
            switch wizardVM.currentStep {
            case 0:
                AddressInputView()

            case 1:
                PhotoUploadView()
                    .environmentObject(bookingData)
                    .environmentObject(wizardVM)

            case 2:
                ItemSelectionView()
                    .environmentObject(bookingData)
                    .environmentObject(wizardVM)

            case 3:
                DateTimePickerView()
                    .environmentObject(bookingData)
                    .environmentObject(wizardVM)

            case 4:
                BookingReviewView()
                    .environmentObject(bookingData)
                    .environmentObject(wizardVM)

            default:
                EmptyView()
            }
        }
        .id(wizardVM.currentStep)
        .transition(.asymmetric(
            insertion: .move(edge: .trailing).combined(with: .opacity),
            removal: .move(edge: .leading).combined(with: .opacity)
        ))
        .animation(.smooth(duration: 0.35), value: wizardVM.currentStep)
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

                    if let serviceFee = breakdown.serviceFee {
                        priceLineItem("Service Fee", amount: serviceFee)
                    }

                    if let volumeDiscount = breakdown.volumeDiscount, volumeDiscount < 0 {
                        priceLineItem("Volume Discount", amount: volumeDiscount, isDiscount: true)
                    }

                    if let surgeAmount = breakdown.surgeAmount, surgeAmount > 0 {
                        priceLineItem("Surcharge", amount: surgeAmount)
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
