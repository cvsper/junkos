//
//  BookingReviewView.swift
//  Umuve
//
//  Review and confirmation screen - final step of booking wizard
//

import SwiftUI
import MapKit
import Combine
import StripePaymentSheet

struct BookingReviewView: View {
    @EnvironmentObject var bookingData: BookingData
    @EnvironmentObject var wizardVM: BookingWizardViewModel
    @StateObject private var viewModel = BookingReviewViewModel()
    @State private var isPriceExpanded = false
    @State private var showSuccessOverlay = false
    @State private var showPaymentSheet = false

    // Promo code UI state — kept local so dismissing the screen doesn't
    // leave a half-typed input in flight. The applied result lives on
    // bookingData so it persists across navigation.
    @State private var promoInput: String = ""
    @State private var promoError: String?
    @State private var promoValidating: Bool = false

    var body: some View {
        ZStack {
            ScrollView {
                VStack(spacing: UmuveSpacing.normal) {
                    // Header (web parity copy)
                    VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                        Text("Review Your Estimate")
                            .font(UmuveTypography.h1Font)
                            .foregroundColor(.umuveText)

                        Text("Check the details below and accept the estimate to continue.")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveTextMuted)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, UmuveSpacing.large)
                    .padding(.top, UmuveSpacing.large)

                    serviceSummaryCard
                    locationCard
                    photosCard
                    scheduleCard
                    priceSection
                    ecoFootnote
                    promoSection
                    acceptCheckbox

                    // Spacing for button
                    Spacer()
                        .frame(height: 100)
                }
            }

            // Confirm Button (safeAreaInset bottom)
            VStack {
                Spacer()
                confirmButton
                    .padding(.horizontal, UmuveSpacing.large)
                    .padding(.bottom, UmuveSpacing.normal)
                    .background(
                        LinearGradient(
                            colors: [.clear, Color.umuveBackground.opacity(0.95)],
                            startPoint: .top,
                            endPoint: .bottom
                        )
                        .frame(height: 120)
                    )
            }
            .ignoresSafeArea(edges: .bottom)

            // Success overlay
            if showSuccessOverlay {
                successOverlay
            }
        }
        .background(Color.umuveBackground.ignoresSafeArea())
        .alert("Booking Error", isPresented: .constant(viewModel.errorMessage != nil)) {
            Button("OK") {
                viewModel.errorMessage = nil
            }
        } message: {
            if let error = viewModel.errorMessage {
                Text(error)
            }
        }
        .onChange(of: viewModel.showSuccess) { success in
            if success {
                withAnimation(.easeInOut(duration: 0.3)) {
                    showSuccessOverlay = true
                }
            }
        }
        .onReceive(viewModel.$paymentSheet) { sheet in
            showPaymentSheet = (sheet != nil)
        }
        .paymentSheet(
            isPresented: $showPaymentSheet,
            paymentSheet: viewModel.paymentSheet ?? PaymentSheet(
                paymentIntentClientSecret: "",
                configuration: PaymentSheet.Configuration()
            ),
            onCompletion: { result in
                Task {
                    await viewModel.handlePaymentResult(result, bookingData: bookingData)
                }
            }
        )
    }

    // MARK: - Card Header Helper

    private func cardHeader(icon: String, title: String, accent: Color) -> some View {
        HStack(spacing: UmuveSpacing.small) {
            ZStack {
                RoundedRectangle(cornerRadius: UmuveRadius.sm)
                    .fill(accent.opacity(0.18))
                    .frame(width: 36, height: 36)

                Image(systemName: icon)
                    .font(.system(size: 18, weight: .semibold))
                    .foregroundColor(accent)
            }

            Text(title)
                .font(UmuveTypography.h3Font)
                .foregroundColor(.umuveText)

            Spacer()
        }
    }

    // MARK: - Service Summary Card

    private var serviceSummaryCard: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            if let serviceType = bookingData.serviceType {
                cardHeader(
                    icon: serviceType.icon,
                    title: serviceType.rawValue,
                    accent: .categoryBlue
                )

                VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                    Text("\(bookingData.totalQuantity) item\(bookingData.totalQuantity == 1 ? "" : "s") · \(bookingData.currentTruckTier.label)")
                        .font(UmuveTypography.bodyFont.weight(.medium))
                        .foregroundColor(.umuveText)

                    Text("~\(Int(bookingData.totalCuFt)) cu ft · ~\(Int(bookingData.totalLbs)) lbs")
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveTextMuted)
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.lg)
                .strokeBorder(Color.umuveBorder, lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 4)
        .padding(.horizontal, UmuveSpacing.large)
    }

    // MARK: - Location Card

    private var locationCard: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            cardHeader(
                icon: "mappin.and.ellipse",
                title: "Pickup",
                accent: .categoryBlue
            )

            addressRow(
                label: "Address",
                value: bookingData.address.fullAddress,
                icon: "mappin.circle.fill",
                accent: .categoryBlue
            )

            if let coordinate = bookingData.pickupCoordinate {
                miniMap(for: coordinate)
            }
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.lg)
                .strokeBorder(Color.umuveBorder, lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 4)
        .padding(.horizontal, UmuveSpacing.large)
    }

    private func addressRow(label: String, value: String, icon: String, accent: Color) -> some View {
        HStack(spacing: UmuveSpacing.small) {
            Image(systemName: icon)
                .font(.system(size: 18))
                .foregroundColor(accent)

            VStack(alignment: .leading, spacing: 2) {
                Text(label.uppercased())
                    .font(UmuveTypography.smallFont)
                    .tracking(0.5)
                    .foregroundColor(.umuveTextMuted)

                Text(value)
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveText)
            }

            Spacer()
        }
    }

    private func miniMap(for coordinate: CLLocationCoordinate2D) -> some View {
        Map(coordinateRegion: .constant(
            MKCoordinateRegion(
                center: coordinate,
                span: MKCoordinateSpan(latitudeDelta: 0.01, longitudeDelta: 0.01)
            )
        ), annotationItems: [ReviewMapPin(coordinate: coordinate)]) { location in
            MapMarker(coordinate: location.coordinate, tint: .umuvePrimary)
        }
        .frame(height: 100)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
        .allowsHitTesting(false)
    }

    // MARK: - Photos Card

    private var photosCard: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            cardHeader(icon: "camera.fill", title: "Photos", accent: .categoryYellow)

            if bookingData.photos.isEmpty {
                Text("No photos added")
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)
            } else {
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: UmuveSpacing.small) {
                        ForEach(0..<bookingData.photos.count, id: \.self) { index in
                            if let uiImage = UIImage(data: bookingData.photos[index]) {
                                Image(uiImage: uiImage)
                                    .resizable()
                                    .scaledToFill()
                                    .frame(width: 80, height: 80)
                                    .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
                                    .overlay(
                                        RoundedRectangle(cornerRadius: UmuveRadius.md)
                                            .strokeBorder(Color.umuveBorder, lineWidth: 1)
                                    )
                            }
                        }
                    }
                }

                Text("\(bookingData.photos.count) photo(s) uploaded")
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.lg)
                .strokeBorder(Color.umuveBorder, lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 4)
        .padding(.horizontal, UmuveSpacing.large)
    }

    // MARK: - Schedule Card

    private var scheduleCard: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            cardHeader(icon: "calendar", title: "Schedule", accent: .categoryOrange)

            if let date = bookingData.selectedDate {
                VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                    Text(date, style: .date)
                        .font(UmuveTypography.bodyFont.weight(.medium))
                        .foregroundColor(.umuveText)

                    if let timeSlot = bookingData.selectedTimeSlot {
                        Text(timeSlot)
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveTextMuted)
                    }
                }
            }
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.lg)
                .strokeBorder(Color.umuveBorder, lineWidth: 1)
        )
        .shadow(color: .black.opacity(0.06), radius: 8, x: 0, y: 4)
        .padding(.horizontal, UmuveSpacing.large)
    }

    // MARK: - Price Section

    private var priceSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            // Total prominently displayed
            if let price = bookingData.estimatedPrice {
                HStack(alignment: .firstTextBaseline, spacing: UmuveSpacing.small) {
                    VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                        Text("Estimated Total")
                            .font(UmuveTypography.captionFont)
                            .tracking(0.5)
                            .foregroundColor(.umuveTextMuted)

                        Text("$\(String(format: "%.2f", price))")
                            .font(UmuveTypography.displayFont)
                            .foregroundColor(.umuvePrimary)
                    }

                    Spacer()

                    Image(systemName: "creditcard.fill")
                        .font(.system(size: 28))
                        .foregroundColor(.umuvePrimary.opacity(0.5))
                }
            }

            // Expandable breakdown
            if let breakdown = bookingData.priceBreakdown {
                Button {
                    withAnimation(.easeInOut(duration: 0.3)) {
                        isPriceExpanded.toggle()
                    }
                } label: {
                    HStack {
                        Text(isPriceExpanded ? "Hide breakdown" : "View breakdown")
                            .font(UmuveTypography.bodyFont.weight(.medium))
                            .foregroundColor(.umuvePrimary)

                        Spacer()

                        Image(systemName: isPriceExpanded ? "chevron.up" : "chevron.down")
                            .font(.system(size: 12, weight: .semibold))
                            .foregroundColor(.umuvePrimary)
                    }
                }

                if isPriceExpanded {
                    VStack(spacing: UmuveSpacing.small) {
                        Divider()
                            .padding(.vertical, UmuveSpacing.tiny)

                        priceLineItem("Base Fee", amount: breakdown.subtotal)

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
                            .padding(.vertical, UmuveSpacing.tiny)

                        HStack {
                            Text("Total")
                                .font(UmuveTypography.bodyFont.weight(.bold))
                                .foregroundColor(.umuveText)

                            Spacer()

                            Text("$\(String(format: "%.2f", breakdown.total))")
                                .font(UmuveTypography.bodyFont.weight(.bold))
                                .foregroundColor(.umuvePrimary)
                        }
                    }
                    .transition(.opacity.combined(with: .move(edge: .top)))
                }
            }

            // Disclaimer
            Text("*Final price may be adjusted on-site based on actual volume")
                .font(UmuveTypography.smallFont)
                .foregroundColor(.umuveTextMuted)
                .padding(.top, UmuveSpacing.tiny)
        }
        .padding(UmuveSpacing.large)
        .background(
            LinearGradient(
                colors: [Color.umuveWhite, Color.umuvePrimary.opacity(0.04)],
                startPoint: .top,
                endPoint: .bottom
            )
        )
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.lg)
                .strokeBorder(Color.umuvePrimary.opacity(0.2), lineWidth: 1)
        )
        .shadow(color: Color.umuvePrimary.opacity(0.1), radius: 12, x: 0, y: 6)
        .padding(.horizontal, UmuveSpacing.large)
    }

    private func priceLineItem(_ label: String, amount: Double, isDiscount: Bool = false) -> some View {
        HStack {
            Text(label)
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(.umuveTextMuted)

            Spacer()

            Text("\(isDiscount ? "-" : "")$\(String(format: "%.2f", abs(amount)))")
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(isDiscount ? .green : .umuveText)
        }
    }

    // MARK: - Promo Section (web Step 6 parity)

    @ViewBuilder
    private var promoSection: some View {
        if bookingData.promoApplied {
            HStack(spacing: UmuveSpacing.small) {
                Image(systemName: "checkmark.seal.fill")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundColor(.umuveSuccess)

                VStack(alignment: .leading, spacing: 2) {
                    Text(bookingData.promoCode)
                        .font(UmuveTypography.bodyFont.weight(.bold))
                        .foregroundColor(.umuveText)
                    Text("-$\(String(format: "%.2f", bookingData.promoDiscount)) applied")
                        .font(UmuveTypography.bodySmallFont)
                        .foregroundColor(.umuveSuccess)
                }

                Spacer()

                Button {
                    removePromo()
                } label: {
                    Image(systemName: "xmark.circle.fill")
                        .font(.system(size: 22))
                        .foregroundColor(.umuveTextTertiary)
                }
                .accessibilityLabel("Remove promo code")
            }
            .padding(UmuveSpacing.normal)
            .background(Color.umuveSuccess.opacity(0.08))
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
            .overlay(
                RoundedRectangle(cornerRadius: UmuveRadius.md)
                    .strokeBorder(Color.umuveSuccess.opacity(0.3), lineWidth: 1)
            )
            .padding(.horizontal, UmuveSpacing.large)
        } else {
            VStack(alignment: .leading, spacing: UmuveSpacing.small) {
                Text("Have a discount code?")
                    .font(UmuveTypography.captionFont)
                    .foregroundColor(.umuveTextMuted)
                    .textCase(.uppercase)
                    .tracking(0.8)

                HStack(spacing: UmuveSpacing.small) {
                    TextField("Promo code", text: $promoInput)
                        .font(UmuveTypography.bodyFont)
                        .textInputAutocapitalization(.characters)
                        .autocorrectionDisabled()
                        .padding(UmuveSpacing.medium)
                        .background(Color.umuveWhite)
                        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
                        .overlay(
                            RoundedRectangle(cornerRadius: UmuveRadius.sm)
                                .strokeBorder(Color.umuveBorder, lineWidth: 1)
                        )

                    Button {
                        Task { await applyPromo() }
                    } label: {
                        if promoValidating {
                            ProgressView().tint(.white)
                        } else {
                            Text("Apply")
                        }
                    }
                    .buttonStyle(UmuvePrimaryButtonStyle(isEnabled: !promoInput.trimmingCharacters(in: .whitespaces).isEmpty))
                    .frame(width: 90)
                    .disabled(promoInput.trimmingCharacters(in: .whitespaces).isEmpty || promoValidating)
                }

                if let promoError {
                    Text(promoError)
                        .font(UmuveTypography.smallFont)
                        .foregroundColor(.umuveError)
                }
            }
            .padding(.horizontal, UmuveSpacing.large)
        }
    }

    @MainActor
    private func applyPromo() async {
        let trimmed = promoInput.trimmingCharacters(in: .whitespaces).uppercased()
        guard !trimmed.isEmpty else { return }

        promoValidating = true
        promoError = nil

        let orderAmount = bookingData.estimatedPrice ?? bookingData.priceBreakdown?.total ?? 0

        do {
            let response = try await APIClient.shared.validatePromoCode(trimmed, orderAmount: orderAmount)
            promoValidating = false

            if response.valid, let discount = response.discountAmount {
                bookingData.promoCode = trimmed
                bookingData.promoDiscount = discount
                bookingData.promoApplied = true
                promoInput = ""
                HapticManager.shared.success()
            } else {
                promoError = response.error ?? "This code isn't valid."
                HapticManager.shared.error()
            }
        } catch {
            promoValidating = false
            promoError = "Couldn't reach the server. Try again."
            HapticManager.shared.error()
        }
    }

    private func removePromo() {
        HapticManager.shared.lightTap()
        bookingData.promoCode = ""
        bookingData.promoDiscount = 0
        bookingData.promoApplied = false
        promoError = nil
    }

    // MARK: - Eco Footnote (web brand-pillar reminder)

    private var ecoFootnote: some View {
        HStack(alignment: .top, spacing: UmuveSpacing.small) {
            Image(systemName: "leaf.fill")
                .font(.system(size: 14, weight: .semibold))
                .foregroundColor(.umuveSuccess)
                .padding(.top, 2)
            Text("We donate & recycle first — landfill is always the last resort.")
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(.umuveTextMuted)
                .multilineTextAlignment(.leading)
        }
        .frame(maxWidth: .infinity, alignment: .leading)
        .padding(UmuveSpacing.normal)
        .background(Color.umuveSuccess.opacity(0.06))
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        .padding(.horizontal, UmuveSpacing.large)
    }

    // MARK: - Accept Checkbox (web Step 5 parity)

    private var acceptCheckbox: some View {
        Button {
            HapticManager.shared.lightTap()
            bookingData.estimateAccepted.toggle()
        } label: {
            HStack(alignment: .top, spacing: UmuveSpacing.small) {
                Image(systemName: bookingData.estimateAccepted ? "checkmark.square.fill" : "square")
                    .font(.system(size: 22, weight: .semibold))
                    .foregroundColor(bookingData.estimateAccepted ? .umuvePrimary : .umuveTextMuted)
                    .frame(width: 28)

                Text("I understand this is an estimate and accept the pricing. Final price will be confirmed after on-site assessment.")
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveText)
                    .multilineTextAlignment(.leading)
                    .frame(maxWidth: .infinity, alignment: .leading)
            }
        }
        .buttonStyle(.plain)
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        .overlay(
            RoundedRectangle(cornerRadius: UmuveRadius.md)
                .strokeBorder(
                    bookingData.estimateAccepted ? Color.umuvePrimary : Color.umuveBorder,
                    lineWidth: bookingData.estimateAccepted ? 1.5 : 1
                )
        )
        .padding(.horizontal, UmuveSpacing.large)
    }

    // MARK: - Confirm Button

    private var confirmButton: some View {
        let canSubmit = bookingData.estimateAccepted
            && !viewModel.isPreparingPayment
            && !viewModel.isSubmitting
        let total = max(0, (bookingData.estimatedPrice ?? bookingData.priceBreakdown?.total ?? 0) - bookingData.promoDiscount)

        return Button {
            Task {
                await viewModel.confirmAndPay(bookingData: bookingData)
            }
        } label: {
            HStack(spacing: UmuveSpacing.small) {
                if viewModel.isPreparingPayment || viewModel.isSubmitting {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                } else {
                    Image(systemName: "lock.fill")
                        .font(.system(size: 15, weight: .semibold))
                    Text(total > 0 ? "Pay $\(String(format: "%.2f", total))" : "Confirm & Pay")
                        .font(UmuveTypography.bodyFont.weight(.semibold))
                }
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, UmuveSpacing.normal)
            .background(
                Group {
                    if !canSubmit {
                        Color.umuveTextMuted
                    } else {
                        LinearGradient(
                            colors: [Color.umuvePrimary, Color.umuvePrimaryDark],
                            startPoint: .leading,
                            endPoint: .trailing
                        )
                    }
                }
            )
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
            .shadow(color: Color.umuvePrimary.opacity(canSubmit ? 0.3 : 0), radius: 10, x: 0, y: 6)
        }
        .disabled(!canSubmit)
    }

    // MARK: - Success Overlay

    private var successOverlay: some View {
        ZStack {
            Color.black.opacity(0.4)
                .ignoresSafeArea()

            VStack(spacing: UmuveSpacing.large) {
                // Success checkmark with payment badge
                ZStack(alignment: .topTrailing) {
                    Image(systemName: "checkmark.circle.fill")
                        .font(.system(size: 72))
                        .foregroundColor(.green)

                    // Payment confirmed badge
                    Image(systemName: "creditcard.fill")
                        .font(.system(size: 24))
                        .foregroundColor(.white)
                        .padding(8)
                        .background(Circle().fill(Color.green))
                        .overlay(
                            Circle()
                                .strokeBorder(Color.white, lineWidth: 2)
                        )
                        .offset(x: 8, y: -8)
                }

                VStack(spacing: UmuveSpacing.small) {
                    // Payment confirmation
                    Text("Payment confirmed")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.green)

                    Text("Booking Confirmed!")
                        .font(UmuveTypography.h1Font)
                        .foregroundColor(.umuveText)

                    if let jobId = viewModel.createdJobId {
                        Text("Job ID: \(jobId)")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveTextMuted)
                    }

                    Text("We'll notify you when a driver accepts your booking.")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveTextMuted)
                        .multilineTextAlignment(.center)
                        .padding(.horizontal, UmuveSpacing.large)
                }

                Button {
                    bookingData.bookingCompleted = true
                } label: {
                    Text("Done")
                        .font(UmuveTypography.bodyFont.weight(.semibold))
                        .foregroundColor(.white)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, UmuveSpacing.normal)
                        .background(Color.umuvePrimary)
                        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
                }
                .padding(.horizontal, UmuveSpacing.large)
            }
            .padding(UmuveSpacing.xlarge)
            .background(Color.umuveWhite)
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.lg))
            .shadow(color: .black.opacity(0.2), radius: 20, x: 0, y: 10)
            .padding(.horizontal, UmuveSpacing.xlarge)
        }
    }

}

// MARK: - Map Annotation Helper

struct ReviewMapPin: Identifiable {
    let id = UUID()
    let coordinate: CLLocationCoordinate2D
}

#Preview {
    let bookingData = BookingData()
    bookingData.serviceType = .junkRemoval
    bookingData.items = [
        BookingItem(category: .furniture, preset: ItemCategory.furniture.presets[0], quantity: 1)
    ]
    bookingData.address = Address(street: "123 Main St", city: "Miami", state: "FL", zipCode: "33101")
    bookingData.selectedDate = Date()
    bookingData.selectedTimeSlot = "8:00 AM - 10:00 AM"
    bookingData.estimatedPrice = 125.00

    return NavigationStack {
        BookingReviewView()
            .environmentObject(bookingData)
            .environmentObject(BookingWizardViewModel())
    }
}
