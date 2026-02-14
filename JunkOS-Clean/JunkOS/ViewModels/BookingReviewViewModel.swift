//
//  BookingReviewViewModel.swift
//  Umuve
//
//  View model for booking review and job creation
//

import Foundation
import SwiftUI

class BookingReviewViewModel: ObservableObject {
    @Published var isSubmitting = false
    @Published var showSuccess = false
    @Published var errorMessage: String?
    @Published var createdJobId: String?

    @MainActor
    func confirmBooking(bookingData: BookingData) async {
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

        isSubmitting = true
        errorMessage = nil

        do {
            // Step 1: Upload photos first (if any)
            var photoUrls: [String] = []
            if !bookingData.photos.isEmpty {
                photoUrls = try await APIClient.shared.uploadPhotos(bookingData.photos)
            }

            // Step 2: Format date and time
            let dateFormatter = DateFormatter()
            dateFormatter.dateFormat = "yyyy-MM-dd"
            let scheduledDate = dateFormatter.string(from: selectedDate)

            // Step 3: Create job with all booking data
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

            // Step 4: Handle success
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
