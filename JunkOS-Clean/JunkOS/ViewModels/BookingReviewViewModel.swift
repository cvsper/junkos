//
//  BookingReviewViewModel.swift
//  Umuve
//
//  View model for booking review and job creation
//

import Foundation
import SwiftUI
import StripePaymentSheet

class BookingReviewViewModel: ObservableObject {
    @Published var isSubmitting = false
    @Published var showSuccess = false
    @Published var errorMessage: String?
    @Published var createdJobId: String?
    @Published var paymentSheet: PaymentSheet?
    @Published var isPreparingPayment = false
    @Published var paymentIntentId: String?

    @MainActor
    func confirmAndPay(bookingData: BookingData) async {
        // Validate required fields
        guard let serviceType = bookingData.serviceType else {
            errorMessage = "Service type is required"
            return
        }

        guard bookingData.isAddressValid else {
            errorMessage = "Valid address is required"
            return
        }

        guard let selectedDate = bookingData.selectedDate,
              let selectedTimeSlot = bookingData.selectedTimeSlot else {
            errorMessage = "Please select a date and time"
            return
        }

        isPreparingPayment = true
        errorMessage = nil

        do {
            // Prepare Payment Sheet with estimated price
            let amount = bookingData.estimatedPrice ?? 0
            let sheet = try await PaymentService.shared.preparePaymentSheet(
                amountInDollars: amount,
                bookingDescription: "Umuve \(serviceType.rawValue)"
            )

            // Store the PaymentSheet (this triggers presentation in the view)
            self.paymentSheet = sheet
            self.paymentIntentId = PaymentService.shared.paymentIntentId

        } catch {
            errorMessage = "Failed to prepare payment: \(error.localizedDescription)"

            // Haptic feedback
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.error)
        }

        isPreparingPayment = false
    }

    @MainActor
    func handlePaymentResult(_ result: PaymentSheetResult, bookingData: BookingData) async {
        switch result {
        case .completed:
            // Payment succeeded — create the job
            await createJobAfterPayment(bookingData: bookingData)

        case .canceled:
            // User dismissed the Payment Sheet — reset state, no error shown
            paymentSheet = nil

        case .failed(let error):
            // Payment failed — show error and reset
            errorMessage = "Payment failed: \(error.localizedDescription)"
            paymentSheet = nil

            // Haptic feedback
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.error)
        }
    }

    private func createJobAfterPayment(bookingData: BookingData) async {
        guard let serviceType = bookingData.serviceType,
              let selectedDate = bookingData.selectedDate,
              let selectedTimeSlot = bookingData.selectedTimeSlot else {
            errorMessage = "Missing booking information"
            return
        }

        isSubmitting = true
        errorMessage = nil

        do {
            // Step 1: Confirm payment on backend
            if let intentId = self.paymentIntentId {
                _ = try await PaymentService.shared.confirmPayment(
                    paymentIntentId: intentId,
                    paymentMethodType: "card"
                )
            }

            // Step 2: Upload photos first (if any)
            var photoUrls: [String] = []
            if !bookingData.photos.isEmpty {
                photoUrls = try await APIClient.shared.uploadPhotos(bookingData.photos)
            }

            // Step 3: Format date and time
            let dateFormatter = DateFormatter()
            dateFormatter.dateFormat = "yyyy-MM-dd"
            let scheduledDate = dateFormatter.string(from: selectedDate)

            // Step 4: Create job with all booking data
            let response = try await APIClient.shared.createJob(
                serviceType: serviceType.rawValue,
                address: bookingData.address.fullAddress,
                lat: bookingData.pickupCoordinate?.latitude ?? 0,
                lng: bookingData.pickupCoordinate?.longitude ?? 0,
                dropoffAddress: bookingData.needsDropoff ? bookingData.dropoffAddress.fullAddress : nil,
                dropoffLat: bookingData.dropoffCoordinate?.latitude,
                dropoffLng: bookingData.dropoffCoordinate?.longitude,
                photoUrls: photoUrls,
                scheduledDate: scheduledDate,
                scheduledTime: selectedTimeSlot,
                estimatedPrice: bookingData.estimatedPrice ?? 0,
                volumeTier: serviceType == .junkRemoval ? bookingData.volumeTier.rawValue : nil,
                vehicleInfo: serviceType == .autoTransport ? buildVehicleInfo(bookingData) : nil,
                distance: bookingData.estimatedDistance
            )

            // Step 5: Handle success
            if response.success, let jobId = response.jobId {
                createdJobId = jobId
                showSuccess = true

                // Haptic feedback
                let generator = UINotificationFeedbackGenerator()
                generator.notificationOccurred(.success)
            } else {
                errorMessage = response.message ?? "Failed to create booking"

                // Haptic feedback
                let generator = UINotificationFeedbackGenerator()
                generator.notificationOccurred(.error)
            }

        } catch {
            errorMessage = error.localizedDescription

            // Haptic feedback
            let generator = UINotificationFeedbackGenerator()
            generator.notificationOccurred(.error)
        }

        isSubmitting = false
    }

    private func buildVehicleInfo(_ bookingData: BookingData) -> [String: String] {
        var info: [String: String] = [
            "make": bookingData.vehicleMake,
            "model": bookingData.vehicleModel,
            "year": bookingData.vehicleYear,
            "running": bookingData.isVehicleRunning ? "yes" : "no",
            "enclosed": bookingData.needsEnclosedTrailer ? "yes" : "no"
        ]
        return info
    }
}
