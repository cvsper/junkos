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

        if bookingData.serviceType != nil {
            // Placeholder pricing: scale with the truck tier the user's
            // selected items fall into. Real pricing flows through
            // BookingWizardViewModel.refreshPricing → /api/pricing/estimate.
            estimatedPrice = bookingData.currentTruckTier.basePrice
        }

        // Update booking data with estimate
        bookingData.estimatedPrice = estimatedPrice

        // Create placeholder pricing breakdown
        let breakdown = PricingEstimate(
            total: estimatedPrice,
            itemsSubtotal: nil,
            basePrice: estimatedPrice * 0.85,
            volumeDiscount: 0.0,
            volumeDiscountLabel: nil,
            surgeMultiplier: nil,
            surgeAmount: estimatedPrice * 0.05,
            surgeReasons: nil,
            serviceFee: estimatedPrice * 0.10,
            recyclingFees: nil,
            laborFee: nil,
            minimumApplied: nil,
            minimumJobPrice: nil,
            estimatedDuration: 90,
            truckSize: "Standard Pickup",
            totalQuantity: nil
        )

        bookingData.priceBreakdown = breakdown

        isLoading = false
    }
}
