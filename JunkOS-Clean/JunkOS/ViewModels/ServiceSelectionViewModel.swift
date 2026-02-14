//
//  ServiceSelectionViewModel.swift
//  Umuve
//
//  ViewModel for service selection and pricing logic
//

import SwiftUI
import Combine

class ServiceSelectionViewModel: ObservableObject {
    // MARK: - Published Properties
    @Published var isLoading: Bool = false

    // MARK: - Public Methods

    /// Request pricing estimate based on booking configuration
    /// For now, this is a stub that sets a placeholder price
    /// Actual backend integration will happen in Plan 04
    @MainActor
    func requestPricingEstimate(for bookingData: BookingData) async {
        isLoading = true

        // Simulate network delay
        try? await Task.sleep(nanoseconds: 500_000_000) // 0.5 seconds

        // Calculate placeholder price based on service type
        var estimatedPrice: Double = 0.0

        if let serviceType = bookingData.serviceType {
            switch serviceType {
            case .junkRemoval:
                // Base price varies by volume tier
                let basePrice: Double = 150.0
                let tierMultiplier: Double = bookingData.volumeTier.fillLevel
                estimatedPrice = basePrice * (0.5 + tierMultiplier * 1.5) // Range: $75 - $375

            case .autoTransport:
                // Base price for auto transport
                estimatedPrice = 500.0

                // Add surcharges
                if !bookingData.isVehicleRunning {
                    estimatedPrice += 150.0 // Non-running vehicle surcharge
                }

                if bookingData.needsEnclosedTrailer {
                    estimatedPrice += 200.0 // Enclosed trailer surcharge
                }
            }
        }

        // Update booking data with estimate
        bookingData.estimatedPrice = estimatedPrice

        // Create placeholder pricing breakdown
        let breakdown = PricingEstimate(
            subtotal: estimatedPrice * 0.85,
            serviceFee: estimatedPrice * 0.10,
            volumeDiscount: 0.0,
            timeSurge: 0.0,
            zoneSurge: estimatedPrice * 0.05,
            total: estimatedPrice,
            estimatedDurationMinutes: 90,
            recommendedTruck: "Standard Pickup"
        )

        bookingData.priceBreakdown = breakdown

        isLoading = false
    }
}
