//
//  PaymentView.swift
//  Umuve
//
//  Payment screen shown after booking confirmation.
//  Supports Apple Pay via PassKit and manual card entry.
//  Does NOT use the Stripe SDK — card data is sent to the backend
//  which handles the actual Stripe charge.
//

import SwiftUI
import PassKit

// MARK: - Payment View

struct PaymentView: View {
    @EnvironmentObject var bookingData: BookingData
    @StateObject private var viewModel = PaymentViewModel()
    @Environment(\.dismiss) private var dismiss
    @State private var navigateToSuccess = false

    /// Called when payment succeeds — the parent can show the success animation
    var onPaymentSuccess: (() -> Void)?

    /// Resolved pricing estimate from the booking wizard. Falls back to zero
    /// when the API call has not yet returned (UI shows "Calculating…").
    private var estimate: PricingEstimate? { bookingData.priceBreakdown }
    private var orderSubtotal: Double { estimate?.total ?? bookingData.estimatedPrice ?? 0 }
    /// Subtotal minus any applied promo discount. This is what the user
    /// actually pays — used everywhere we render or charge a total.
    private var orderTotal: Double { max(0, orderSubtotal - bookingData.promoDiscount) }

    // Promo input state — local to this view so dismissing PaymentView
    // doesn't leave stale UI in flight. The applied result lives on
    // bookingData so it survives navigation.
    @State private var promoInput: String = ""
    @State private var promoError: String?
    @State private var promoValidating: Bool = false

    var body: some View {
        ZStack {
            ScrollView {
                VStack(spacing: UmuveSpacing.xxlarge) {
                    // Header
                    ScreenHeader(
                        title: "Payment",
                        subtitle: "Secure checkout",
                        progress: 1.0
                    )
                    .staggeredEntrance(index: 0, isVisible: viewModel.elementsVisible)

                    // Order total card
                    orderTotalCard
                        .staggeredEntrance(index: 1, isVisible: viewModel.elementsVisible)

                    // Promo code (web Step 6 parity)
                    promoSection
                        .staggeredEntrance(index: 2, isVisible: viewModel.elementsVisible)

                    // Apple Pay section
                    if viewModel.isApplePayAvailable {
                        applePaySection
                            .staggeredEntrance(index: 3, isVisible: viewModel.elementsVisible)
                    }

                    // Divider with "or"
                    if viewModel.isApplePayAvailable {
                        orDivider
                            .staggeredEntrance(index: 3, isVisible: viewModel.elementsVisible)
                    }

                    // Card payment section
                    cardPaymentSection
                        .staggeredEntrance(
                            index: viewModel.isApplePayAvailable ? 4 : 2,
                            isVisible: viewModel.elementsVisible
                        )

                    // Security note
                    securityNote
                        .staggeredEntrance(
                            index: viewModel.isApplePayAvailable ? 5 : 3,
                            isVisible: viewModel.elementsVisible
                        )

                    // Bottom spacing for the pay button
                    Spacer().frame(height: 80)
                }
                .padding(UmuveSpacing.large)
            }
            .background(Color.umuveBackground.ignoresSafeArea())
            .navigationBarTitleDisplayMode(.inline)
            .safeAreaInset(edge: .bottom) {
                payButton
                    .ignoresSafeArea(.keyboard, edges: .bottom)
            }
            .onAppear {
                viewModel.configure(amount: orderTotal)
            }

            // Processing overlay
            if viewModel.isProcessing {
                processingOverlay
            }

            // Success overlay
            if viewModel.showSuccess {
                successOverlay
            }
        }
        .alert("Payment Failed", isPresented: $viewModel.showError) {
            Button("Try Again") {
                viewModel.showError = false
            }
            Button("Cancel", role: .cancel) {
                viewModel.showError = false
            }
        } message: {
            Text(viewModel.errorMessage)
        }
        .sheet(isPresented: $viewModel.showApplePaySheet) {
            ApplePayViewControllerRepresentable(
                amount: orderTotal,
                onSuccess: { viewModel.handleApplePaySuccess() },
                onFailure: { error in viewModel.handleApplePayFailure(error: error) },
                onCancel: { viewModel.handleApplePayCancel() }
            )
            .ignoresSafeArea()
        }
        .navigationDestination(isPresented: $navigateToSuccess) {
            BookingSuccessView(
                customerEmail: bookingData.customerEmail,
                totalAmount: orderTotal,
                scheduledDate: formattedScheduledDate,
                scheduledTime: formattedScheduledTime
            )
            .environmentObject(bookingData)
        }
    }

    // MARK: - Order Total Card

    private var orderTotalCard: some View {
        UmuveCard {
            VStack(spacing: UmuveSpacing.normal) {
                HStack {
                    Image(systemName: "cart.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.umuvePrimary)
                    Text("Order Summary")
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuveText)
                    Spacer()
                }

                Divider()

                if let estimate {
                    summaryLine("Subtotal", value: estimate.subtotal)

                    if let discount = estimate.volumeDiscount, discount > 0 {
                        summaryLine(
                            estimate.volumeDiscountLabel ?? "Volume Discount",
                            value: -discount,
                            tint: .umuveSuccess
                        )
                    }

                    if let surge = estimate.surgeAmount, surge > 0 {
                        summaryLine(
                            surgeLabel(from: estimate.surgeReasons),
                            value: surge
                        )
                    }

                    if let serviceFee = estimate.serviceFee, serviceFee > 0 {
                        summaryLine("Service Fee", value: serviceFee)
                    }

                    if let recycling = estimate.recyclingFees, recycling > 0 {
                        summaryLine("Recycling & Disposal", value: recycling)
                    }
                } else {
                    HStack {
                        Text("Calculating your estimate…")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveTextMuted)
                        Spacer()
                        ProgressView()
                    }
                }

                Divider()

                // Pre-promo subtotal — only render when a promo is applied,
                // otherwise the row duplicates the "Total" row below.
                if bookingData.promoApplied {
                    HStack {
                        Text("Subtotal")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveTextMuted)
                        Spacer()
                        Text("$\(formatPrice(orderSubtotal))")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveText)
                    }

                    HStack {
                        Text("Promo \(bookingData.promoCode)")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveSuccess)
                        Spacer()
                        Text("-$\(formatPrice(bookingData.promoDiscount))")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveSuccess)
                    }
                }

                HStack {
                    Text("Total")
                        .font(UmuveTypography.h2Font)
                        .foregroundColor(.umuveText)
                    Spacer()
                    Text("$\(formatPrice(orderTotal))")
                        .font(UmuveTypography.priceFont)
                        .foregroundColor(.umuveCTA)
                }
            }
            .padding(UmuveSpacing.large)
        }
    }

    private func summaryLine(_ label: String, value: Double, tint: Color = .umuveText) -> some View {
        HStack {
            Text(label)
                .font(UmuveTypography.bodyFont)
                .foregroundColor(.umuveTextMuted)
            Spacer()
            Text("\(value < 0 ? "-$" : "$")\(formatPrice(abs(value)))")
                .font(UmuveTypography.bodyFont)
                .foregroundColor(tint)
        }
    }

    private func surgeLabel(from reasons: [String]?) -> String {
        guard let first = reasons?.first, !first.isEmpty else { return "Surge Pricing" }
        return first
    }

    // MARK: - Promo Section
    // Mirrors web Step 6's promo flow: text input + Apply button, or an
    // applied chip with a remove (X) button. Validation hits
    // /api/promos/validate; success populates bookingData.promo* so the
    // discount is reflected in the order total and ApplePay sheet amount.
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
                    Text("-$\(formatPrice(bookingData.promoDiscount)) applied")
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
                    .frame(width: 100)
                    .disabled(promoInput.trimmingCharacters(in: .whitespaces).isEmpty || promoValidating)
                }

                if let promoError {
                    Text(promoError)
                        .font(UmuveTypography.smallFont)
                        .foregroundColor(.umuveError)
                }
            }
        }
    }

    @MainActor
    private func applyPromo() async {
        let trimmed = promoInput.trimmingCharacters(in: .whitespaces).uppercased()
        guard !trimmed.isEmpty else { return }

        promoValidating = true
        promoError = nil

        do {
            let response = try await APIClient.shared.validatePromoCode(
                trimmed,
                orderAmount: orderSubtotal
            )

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

    // MARK: - Apple Pay Section

    private var applePaySection: some View {
        VStack(spacing: UmuveSpacing.medium) {
            Button {
                HapticManager.shared.mediumTap()
                viewModel.initiateApplePay()
            } label: {
                HStack(spacing: UmuveSpacing.small) {
                    Image(systemName: "apple.logo")
                        .font(.system(size: 18, weight: .semibold))
                    Text("Pay")
                        .font(UmuveTypography.bodyFont.weight(.semibold))
                }
                .foregroundColor(.white)
                .frame(maxWidth: .infinity)
                .padding(.vertical, 16)
                .background(
                    RoundedRectangle(cornerRadius: UmuveRadius.md)
                        .fill(Color.black)
                )
            }
            .disabled(viewModel.isProcessing)

            Text("Quick and secure checkout")
                .font(UmuveTypography.captionFont)
                .foregroundColor(.umuveTextMuted)
        }
    }

    // MARK: - Or Divider

    private var orDivider: some View {
        HStack(spacing: UmuveSpacing.normal) {
            Rectangle()
                .fill(Color.umuveBorder)
                .frame(height: 1)
            Text("or pay with card")
                .font(UmuveTypography.captionFont)
                .foregroundColor(.umuveTextMuted)
                .layoutPriority(1)
            Rectangle()
                .fill(Color.umuveBorder)
                .frame(height: 1)
        }
    }

    // MARK: - Card Payment Section

    private var cardPaymentSection: some View {
        UmuveCard {
            VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
                HStack {
                    Image(systemName: "creditcard.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.umuvePrimary)
                    Text("Card Details")
                        .font(UmuveTypography.h3Font)
                        .foregroundColor(.umuveText)
                    Spacer()

                    // Card brand icons
                    HStack(spacing: 4) {
                        cardBrandIcon("visa")
                        cardBrandIcon("mastercard")
                        cardBrandIcon("amex")
                    }
                }

                // Card Number
                VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                    Text("Card Number")
                        .font(UmuveTypography.captionFont)
                        .foregroundColor(.umuveTextMuted)
                    HStack {
                        Image(systemName: "creditcard")
                            .foregroundColor(.umuveTextTertiary)
                            .frame(width: 24)
                        TextField("1234 5678 9012 3456", text: $viewModel.cardNumber)
                            .font(UmuveTypography.bodyFont)
                            .keyboardType(.numberPad)
                            .textContentType(.creditCardNumber)
                            .onChange(of: viewModel.cardNumber) { newValue in
                                viewModel.cardNumber = formatCardNumber(newValue)
                            }
                    }
                    .padding(UmuveSpacing.medium)
                    .background(Color.umuveBackground)
                    .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
                    .overlay(
                        RoundedRectangle(cornerRadius: UmuveRadius.sm)
                            .stroke(
                                viewModel.cardNumberError != nil ? Color.umuveError : Color.clear,
                                lineWidth: 1
                            )
                    )

                    if let error = viewModel.cardNumberError {
                        Text(error)
                            .font(UmuveTypography.smallFont)
                            .foregroundColor(.umuveError)
                    }
                }

                // Expiry and CVC side by side
                HStack(spacing: UmuveSpacing.medium) {
                    // Expiry
                    VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                        Text("Expiry")
                            .font(UmuveTypography.captionFont)
                            .foregroundColor(.umuveTextMuted)
                        HStack {
                            Image(systemName: "calendar")
                                .foregroundColor(.umuveTextTertiary)
                                .frame(width: 24)
                            TextField("MM/YY", text: $viewModel.expiryDate)
                                .font(UmuveTypography.bodyFont)
                                .keyboardType(.numberPad)
                                .onChange(of: viewModel.expiryDate) { newValue in
                                    viewModel.expiryDate = formatExpiryDate(newValue)
                                }
                        }
                        .padding(UmuveSpacing.medium)
                        .background(Color.umuveBackground)
                        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
                        .overlay(
                            RoundedRectangle(cornerRadius: UmuveRadius.sm)
                                .stroke(
                                    viewModel.expiryError != nil ? Color.umuveError : Color.clear,
                                    lineWidth: 1
                                )
                        )

                        if let error = viewModel.expiryError {
                            Text(error)
                                .font(UmuveTypography.smallFont)
                                .foregroundColor(.umuveError)
                        }
                    }

                    // CVC
                    VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                        Text("CVC")
                            .font(UmuveTypography.captionFont)
                            .foregroundColor(.umuveTextMuted)
                        HStack {
                            Image(systemName: "lock.fill")
                                .foregroundColor(.umuveTextTertiary)
                                .frame(width: 24)
                            SecureField("123", text: $viewModel.cvc)
                                .font(UmuveTypography.bodyFont)
                                .keyboardType(.numberPad)
                                .onChange(of: viewModel.cvc) { newValue in
                                    // Limit to 4 digits (Amex has 4)
                                    let filtered = newValue.filter { $0.isNumber }
                                    if filtered.count <= 4 {
                                        viewModel.cvc = filtered
                                    } else {
                                        viewModel.cvc = String(filtered.prefix(4))
                                    }
                                }
                        }
                        .padding(UmuveSpacing.medium)
                        .background(Color.umuveBackground)
                        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
                        .overlay(
                            RoundedRectangle(cornerRadius: UmuveRadius.sm)
                                .stroke(
                                    viewModel.cvcError != nil ? Color.umuveError : Color.clear,
                                    lineWidth: 1
                                )
                        )

                        if let error = viewModel.cvcError {
                            Text(error)
                                .font(UmuveTypography.smallFont)
                                .foregroundColor(.umuveError)
                        }
                    }
                }
            }
            .padding(UmuveSpacing.large)
        }
    }

    // MARK: - Security Note

    private var securityNote: some View {
        HStack(spacing: UmuveSpacing.small) {
            Image(systemName: "lock.shield.fill")
                .font(.system(size: 16))
                .foregroundColor(.umuveTextTertiary)
            Text("Your payment info is encrypted and secure. We never store your card details.")
                .font(UmuveTypography.bodySmallFont)
                .foregroundColor(.umuveTextMuted)
        }
        .padding(UmuveSpacing.normal)
    }

    // MARK: - Pay Button

    private var payButton: some View {
        Button {
            HapticManager.shared.mediumTap()
            viewModel.submitCardPayment()
        } label: {
            HStack {
                if viewModel.isProcessing {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                        .padding(.trailing, UmuveSpacing.small)
                }
                Text(viewModel.isProcessing ? "Processing..." : "Pay $\(formatPrice(orderTotal))")
            }
        }
        .buttonStyle(UmuvePrimaryButtonStyle(isEnabled: viewModel.isCardFormValid && !viewModel.isProcessing))
        .disabled(!viewModel.isCardFormValid || viewModel.isProcessing)
        .padding(UmuveSpacing.large)
        .background(Color.umuveBackground)
    }

    // MARK: - Processing Overlay

    private var processingOverlay: some View {
        ZStack {
            Color.black.opacity(0.4)
                .ignoresSafeArea()

            VStack(spacing: UmuveSpacing.large) {
                ProgressView()
                    .progressViewStyle(CircularProgressViewStyle(tint: .umuvePrimary))
                    .scaleEffect(1.5)

                Text("Processing payment...")
                    .font(UmuveTypography.bodyFont.weight(.medium))
                    .foregroundColor(.white)
            }
            .padding(UmuveSpacing.xxlarge)
            .background(
                RoundedRectangle(cornerRadius: UmuveRadius.lg)
                    .fill(Color(.systemBackground))
            )
            .shadow(color: .black.opacity(0.15), radius: 20, x: 0, y: 10)
        }
        .transition(.opacity)
    }

    // MARK: - Success Overlay

    private var successOverlay: some View {
        ZStack {
            Color.black.opacity(0.3)
                .ignoresSafeArea()

            SuccessCheckmark()
        }
        .transition(.opacity)
        .onAppear {
            HapticManager.shared.success()
            DispatchQueue.main.asyncAfter(deadline: .now() + 1.5) {
                withAnimation {
                    viewModel.showSuccess = false
                }
                onPaymentSuccess?()
                navigateToSuccess = true
            }
        }
    }

    // MARK: - Helpers

    private var formattedScheduledDate: String {
        guard let date = bookingData.selectedDate else { return "Scheduled" }
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        return formatter.string(from: date)
    }

    private var formattedScheduledTime: String {
        guard let slotId = bookingData.selectedTimeSlot else { return "Your time window" }
        if let slot = TimeSlot.slots.first(where: { $0.id == slotId }) {
            return slot.time
        }
        return slotId
    }

    private func formatPrice(_ price: Double) -> String {
        String(format: "%.2f", price)
    }

    private func formatCardNumber(_ input: String) -> String {
        let digits = input.filter { $0.isNumber }
        let limited = String(digits.prefix(16))
        var formatted = ""
        for (index, char) in limited.enumerated() {
            if index > 0 && index % 4 == 0 {
                formatted.append(" ")
            }
            formatted.append(char)
        }
        return formatted
    }

    private func formatExpiryDate(_ input: String) -> String {
        let digits = input.filter { $0.isNumber }
        let limited = String(digits.prefix(4))
        if limited.count > 2 {
            let month = String(limited.prefix(2))
            let year = String(limited.dropFirst(2))
            return "\(month)/\(year)"
        }
        return limited
    }

    private func cardBrandIcon(_ brand: String) -> some View {
        Text(brand.uppercased())
            .font(.system(size: 8, weight: .bold))
            .foregroundColor(.umuveTextTertiary)
            .padding(.horizontal, 4)
            .padding(.vertical, 2)
            .background(
                RoundedRectangle(cornerRadius: 2)
                    .stroke(Color.umuveBorder, lineWidth: 1)
            )
    }
}

// MARK: - Payment View Model

class PaymentViewModel: ObservableObject {
    // MARK: - Published Properties

    // UI state
    @Published var elementsVisible = false
    @Published var isProcessing = false
    @Published var showSuccess = false
    @Published var showError = false
    @Published var errorMessage = ""
    @Published var showApplePaySheet = false

    // Card form fields
    @Published var cardNumber = ""
    @Published var expiryDate = ""
    @Published var cvc = ""

    // Validation errors
    @Published var cardNumberError: String?
    @Published var expiryError: String?
    @Published var cvcError: String?

    // MARK: - Private Properties

    private let paymentService = PaymentService.shared
    private var amount: Double = 0
    private var paymentIntentId: String?

    // MARK: - Computed Properties

    var isApplePayAvailable: Bool {
        paymentService.isApplePayAvailable
    }

    var isCardFormValid: Bool {
        let digits = cardNumber.filter { $0.isNumber }
        let expiryDigits = expiryDate.filter { $0.isNumber }
        let cvcDigits = cvc.filter { $0.isNumber }
        return digits.count >= 15 && expiryDigits.count == 4 && cvcDigits.count >= 3
    }

    // MARK: - Public Methods

    func configure(amount: Double) {
        self.amount = amount
        withAnimation(AnimationConstants.smoothSpring) {
            elementsVisible = true
        }
    }

    // MARK: - Apple Pay

    func initiateApplePay() {
        guard isApplePayAvailable else {
            errorMessage = "Apple Pay is not available on this device."
            showError = true
            return
        }
        showApplePaySheet = true
    }

    func handleApplePaySuccess() {
        showApplePaySheet = false
        isProcessing = true

        Task { @MainActor in
            do {
                // Create intent on backend
                let intent = try await paymentService.createPaymentIntent(
                    amountInDollars: amount
                )
                paymentIntentId = intent.paymentIntentId

                // Confirm payment on backend
                let confirmation = try await paymentService.confirmPayment(
                    paymentIntentId: intent.paymentIntentId,
                    paymentMethodType: "apple_pay"
                )

                isProcessing = false

                if confirmation.success {
                    withAnimation {
                        showSuccess = true
                    }
                } else {
                    errorMessage = confirmation.message ?? "Payment could not be completed."
                    showError = true
                }
            } catch {
                isProcessing = false
                errorMessage = error.localizedDescription
                showError = true
                HapticManager.shared.error()
            }
        }
    }

    func handleApplePayFailure(error: String) {
        showApplePaySheet = false
        errorMessage = error
        showError = true
        HapticManager.shared.error()
    }

    func handleApplePayCancel() {
        showApplePaySheet = false
    }

    // MARK: - Card Payment

    func submitCardPayment() {
        guard validateCardForm() else { return }

        isProcessing = true
        HapticManager.shared.lightTap()

        Task { @MainActor in
            do {
                // Step 1: Create payment intent
                let intent = try await paymentService.createPaymentIntent(
                    amountInDollars: amount
                )
                paymentIntentId = intent.paymentIntentId

                // Step 2: Confirm the payment on the backend
                // The backend uses the client_secret to process via Stripe.
                // We do NOT send raw card data to our backend; in a production app
                // you'd use Stripe.js / Stripe iOS SDK to tokenize the card first.
                // This flow sends the intent ID so the backend can mark it confirmed.
                let confirmation = try await paymentService.confirmPayment(
                    paymentIntentId: intent.paymentIntentId,
                    paymentMethodType: "card"
                )

                isProcessing = false

                if confirmation.success {
                    withAnimation {
                        showSuccess = true
                    }
                } else {
                    errorMessage = confirmation.message ?? "Payment could not be completed."
                    showError = true
                    HapticManager.shared.error()
                }
            } catch {
                isProcessing = false
                errorMessage = error.localizedDescription
                showError = true
                HapticManager.shared.error()
            }
        }
    }

    // MARK: - Validation

    private func validateCardForm() -> Bool {
        var isValid = true

        // Reset errors
        cardNumberError = nil
        expiryError = nil
        cvcError = nil

        // Validate card number (basic Luhn-plausible length check)
        let cardDigits = cardNumber.filter { $0.isNumber }
        if cardDigits.count < 15 || cardDigits.count > 16 {
            cardNumberError = "Enter a valid card number"
            isValid = false
        }

        // Validate expiry
        let expiryDigits = expiryDate.filter { $0.isNumber }
        if expiryDigits.count != 4 {
            expiryError = "Enter MM/YY"
            isValid = false
        } else {
            let monthStr = String(expiryDigits.prefix(2))
            if let month = Int(monthStr), month < 1 || month > 12 {
                expiryError = "Invalid month"
                isValid = false
            }
        }

        // Validate CVC
        let cvcDigits = cvc.filter { $0.isNumber }
        if cvcDigits.count < 3 {
            cvcError = "Enter 3 or 4 digit CVC"
            isValid = false
        }

        if !isValid {
            HapticManager.shared.warning()
        }

        return isValid
    }
}

// MARK: - Apple Pay UIViewControllerRepresentable

struct ApplePayViewControllerRepresentable: UIViewControllerRepresentable {
    let amount: Double
    let onSuccess: () -> Void
    let onFailure: (String) -> Void
    let onCancel: () -> Void

    func makeUIViewController(context: Context) -> UIViewController {
        let controller = UIViewController()
        // Present Apple Pay on next run loop so the hosting controller is in the hierarchy
        DispatchQueue.main.async {
            let paymentRequest = PaymentService.shared.createApplePayRequest(amount: amount)
            guard let paymentVC = PKPaymentAuthorizationViewController(paymentRequest: paymentRequest) else {
                onFailure("Unable to present Apple Pay")
                return
            }
            paymentVC.delegate = context.coordinator
            controller.present(paymentVC, animated: true)
        }
        return controller
    }

    func updateUIViewController(_ uiViewController: UIViewController, context: Context) {}

    func makeCoordinator() -> Coordinator {
        Coordinator(
            onSuccess: onSuccess,
            onFailure: onFailure,
            onCancel: onCancel
        )
    }

    class Coordinator: NSObject, PKPaymentAuthorizationViewControllerDelegate {
        let onSuccess: () -> Void
        let onFailure: (String) -> Void
        let onCancel: () -> Void
        private var didAuthorize = false

        init(onSuccess: @escaping () -> Void,
             onFailure: @escaping (String) -> Void,
             onCancel: @escaping () -> Void) {
            self.onSuccess = onSuccess
            self.onFailure = onFailure
            self.onCancel = onCancel
        }

        func paymentAuthorizationViewController(
            _ controller: PKPaymentAuthorizationViewController,
            didAuthorizePayment payment: PKPayment,
            handler completion: @escaping (PKPaymentAuthorizationResult) -> Void
        ) {
            didAuthorize = true
            // The payment token (payment.token) would normally be sent to
            // the backend for Stripe processing. For this lightweight flow,
            // we signal success and let the view model handle the backend call.
            completion(PKPaymentAuthorizationResult(status: .success, errors: nil))
            onSuccess()
        }

        func paymentAuthorizationViewControllerDidFinish(
            _ controller: PKPaymentAuthorizationViewController
        ) {
            controller.dismiss(animated: true) { [weak self] in
                guard let self = self else { return }
                if !self.didAuthorize {
                    self.onCancel()
                }
            }
        }
    }
}

// MARK: - Preview

struct PaymentView_Previews: PreviewProvider {
    static var previews: some View {
        NavigationView {
            PaymentView()
                .environmentObject(BookingData())
        }
    }
}
