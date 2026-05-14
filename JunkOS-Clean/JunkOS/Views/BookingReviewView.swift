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

    var body: some View {
        ZStack {
            ScrollView {
                VStack(spacing: UmuveSpacing.normal) {
                    // Header
                    VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                        Text("Review Your Booking")
                            .font(UmuveTypography.h1Font)
                            .foregroundColor(.umuveText)

                        Text("Everything look good?")
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveTextMuted)
                    }
                    .frame(maxWidth: .infinity, alignment: .leading)
                    .padding(.horizontal, UmuveSpacing.large)
                    .padding(.top, UmuveSpacing.large)

                    // Service Summary Card
                    serviceSummaryCard

                    // Location Card
                    locationCard

                    // Photos Card
                    photosCard

                    // Schedule Card
                    scheduleCard

                    // Price Section
                    priceSection

                    // Spacing for button
                    Spacer()
                        .frame(height: 80)
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

                Text("\(bookingData.volumeTier.rawValue) — \(bookingData.volumeTier.description)")
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

    // MARK: - Confirm Button

    private var confirmButton: some View {
        Button {
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
                    Text("Confirm & Pay")
                        .font(UmuveTypography.bodyFont.weight(.semibold))
                }
            }
            .foregroundColor(.white)
            .frame(maxWidth: .infinity)
            .padding(.vertical, UmuveSpacing.normal)
            .background(
                Group {
                    if viewModel.isPreparingPayment || viewModel.isSubmitting {
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
            .shadow(color: Color.umuvePrimary.opacity(0.3), radius: 10, x: 0, y: 6)
        }
        .disabled(viewModel.isPreparingPayment || viewModel.isSubmitting)
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
    bookingData.volumeTier = .half
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
