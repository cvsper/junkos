//
//  BookingReviewView.swift
//  Umuve
//
//  Review and confirmation screen - final step of booking wizard
//

import SwiftUI
import MapKit

struct BookingReviewView: View {
    @EnvironmentObject var bookingData: BookingData
    @EnvironmentObject var wizardVM: BookingWizardViewModel
    @StateObject private var viewModel = BookingReviewViewModel()
    @State private var isPriceExpanded = false
    @State private var showSuccessOverlay = false

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
    }

    // MARK: - Service Summary Card

    private var serviceSummaryCard: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            HStack(spacing: UmuveSpacing.small) {
                if let serviceType = bookingData.serviceType {
                    Image(systemName: serviceType.icon)
                        .font(.system(size: 24))
                        .foregroundColor(.umuvePrimary)

                    VStack(alignment: .leading, spacing: 2) {
                        Text(serviceType.rawValue)
                            .font(UmuveTypography.h3Font)
                            .foregroundColor(.umuveText)

                        // Volume tier for Junk Removal
                        if serviceType == .junkRemoval {
                            Text("\(bookingData.volumeTier.rawValue) — \(bookingData.volumeTier.description)")
                                .font(UmuveTypography.bodySmallFont)
                                .foregroundColor(.umuveTextMuted)
                        }

                        // Vehicle info for Auto Transport
                        if serviceType == .autoTransport {
                            Text("\(bookingData.vehicleYear) \(bookingData.vehicleMake) \(bookingData.vehicleModel)")
                                .font(UmuveTypography.bodySmallFont)
                                .foregroundColor(.umuveTextMuted)

                            // Surcharge badges
                            HStack(spacing: UmuveSpacing.tiny) {
                                if !bookingData.isVehicleRunning {
                                    badge(text: "Non-running", color: .orange)
                                }
                                if bookingData.needsEnclosedTrailer {
                                    badge(text: "Enclosed", color: .blue)
                                }
                            }
                        }
                    }
                }

                Spacer()
            }
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 2)
        .padding(.horizontal, UmuveSpacing.large)
    }

    // MARK: - Location Card

    private var locationCard: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            // Pickup
            HStack(spacing: UmuveSpacing.small) {
                Image(systemName: "mappin.circle.fill")
                    .font(.system(size: 20))
                    .foregroundColor(.umuvePrimary)

                VStack(alignment: .leading, spacing: 2) {
                    Text("Pickup")
                        .font(UmuveTypography.bodySmallFont.weight(.semibold))
                        .foregroundColor(.umuveTextMuted)

                    Text(bookingData.address.fullAddress)
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveText)
                }

                Spacer()
            }

            // Pickup mini-map
            if let coordinate = bookingData.pickupCoordinate {
                miniMap(for: coordinate)
            }

            // Dropoff (Auto Transport only)
            if bookingData.needsDropoff {
                Divider()
                    .padding(.vertical, UmuveSpacing.tiny)

                HStack(spacing: UmuveSpacing.small) {
                    Image(systemName: "mappin.circle.fill")
                        .font(.system(size: 20))
                        .foregroundColor(.umuvePrimary)

                    VStack(alignment: .leading, spacing: 2) {
                        Text("Dropoff")
                            .font(UmuveTypography.bodySmallFont.weight(.semibold))
                            .foregroundColor(.umuveTextMuted)

                        Text(bookingData.dropoffAddress.fullAddress)
                            .font(UmuveTypography.bodyFont)
                            .foregroundColor(.umuveText)
                    }

                    Spacer()
                }

                // Dropoff mini-map
                if let coordinate = bookingData.dropoffCoordinate {
                    miniMap(for: coordinate)
                }

                // Distance
                if let distance = bookingData.estimatedDistance {
                    HStack(spacing: UmuveSpacing.tiny) {
                        Image(systemName: "arrow.left.and.right")
                            .font(.system(size: 12))
                            .foregroundColor(.umuveTextMuted)

                        Text("Distance: \(String(format: "%.1f", distance)) miles")
                            .font(UmuveTypography.bodySmallFont)
                            .foregroundColor(.umuveTextMuted)
                    }
                }
            }
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 2)
        .padding(.horizontal, UmuveSpacing.large)
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
            HStack(spacing: UmuveSpacing.small) {
                Image(systemName: "camera.fill")
                    .font(.system(size: 20))
                    .foregroundColor(.umuvePrimary)

                Text("Photos")
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.umuveText)

                Spacer()
            }

            if bookingData.photos.isEmpty {
                Text("No photos added")
                    .font(UmuveTypography.bodyFont)
                    .foregroundColor(.umuveTextMuted)
            } else {
                // Photo thumbnails
                ScrollView(.horizontal, showsIndicators: false) {
                    HStack(spacing: UmuveSpacing.small) {
                        ForEach(0..<bookingData.photos.count, id: \.self) { index in
                            if let uiImage = UIImage(data: bookingData.photos[index]) {
                                Image(uiImage: uiImage)
                                    .resizable()
                                    .scaledToFill()
                                    .frame(width: 80, height: 80)
                                    .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
                            }
                        }
                    }
                }

                Text("\(bookingData.photos.count) photo(s) uploaded")
                    .font(UmuveTypography.bodySmallFont)
                    .foregroundColor(.umuveTextMuted)
            }
        }
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 2)
        .padding(.horizontal, UmuveSpacing.large)
    }

    // MARK: - Schedule Card

    private var scheduleCard: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            HStack(spacing: UmuveSpacing.small) {
                Image(systemName: "calendar")
                    .font(.system(size: 20))
                    .foregroundColor(.umuvePrimary)

                Text("Schedule")
                    .font(UmuveTypography.h3Font)
                    .foregroundColor(.umuveText)

                Spacer()
            }

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
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 2)
        .padding(.horizontal, UmuveSpacing.large)
    }

    // MARK: - Price Section

    private var priceSection: some View {
        VStack(alignment: .leading, spacing: UmuveSpacing.normal) {
            // Total prominently displayed
            if let price = bookingData.estimatedPrice {
                VStack(alignment: .leading, spacing: UmuveSpacing.tiny) {
                    Text("Estimated Total")
                        .font(UmuveTypography.bodyFont)
                        .foregroundColor(.umuveTextMuted)

                    Text("$\(String(format: "%.2f", price))")
                        .font(UmuveTypography.h1Font)
                        .foregroundColor(.umuvePrimary)
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
        .padding(UmuveSpacing.normal)
        .background(Color.umuveWhite)
        .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        .shadow(color: .black.opacity(0.05), radius: 4, x: 0, y: 2)
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
                await viewModel.confirmBooking(bookingData: bookingData)
            }
        } label: {
            HStack {
                if viewModel.isSubmitting {
                    ProgressView()
                        .progressViewStyle(CircularProgressViewStyle(tint: .white))
                } else {
                    Text("Confirm Booking")
                        .font(UmuveTypography.bodyFont.weight(.semibold))
                        .foregroundColor(.white)
                }
            }
            .frame(maxWidth: .infinity)
            .padding(.vertical, UmuveSpacing.normal)
            .background(viewModel.isSubmitting ? Color.umuveTextMuted : Color.umuvePrimary)
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.md))
        }
        .disabled(viewModel.isSubmitting)
    }

    // MARK: - Success Overlay

    private var successOverlay: some View {
        ZStack {
            Color.black.opacity(0.4)
                .ignoresSafeArea()

            VStack(spacing: UmuveSpacing.large) {
                Image(systemName: "checkmark.circle.fill")
                    .font(.system(size: 72))
                    .foregroundColor(.green)

                VStack(spacing: UmuveSpacing.small) {
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

    // MARK: - Helper Views

    private func badge(text: String, color: Color) -> some View {
        Text(text)
            .font(UmuveTypography.smallFont)
            .foregroundColor(color)
            .padding(.horizontal, UmuveSpacing.small)
            .padding(.vertical, 4)
            .background(color.opacity(0.1))
            .clipShape(RoundedRectangle(cornerRadius: UmuveRadius.sm))
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
