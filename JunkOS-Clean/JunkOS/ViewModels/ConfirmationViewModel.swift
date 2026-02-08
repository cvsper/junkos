//
//  ConfirmationViewModel.swift
//  JunkOS
//
//  ViewModel for ConfirmationView
//

import SwiftUI
import Combine

class ConfirmationViewModel: ObservableObject {
    // MARK: - Published Properties
    @Published var isSubmitting = false
    @Published var showSuccess = false
    @Published var elementsVisible = false
    @Published var celebrationScale: CGFloat = 1.0
    @Published var errorMessage: String?
    @Published var bookingResponse: BookingResponse?
    
    // MARK: - Properties
    @Published var priceBreakdown = PriceBreakdown()
    private let apiClient = APIClient.shared
    
    // MARK: - Public Methods
    
    /// Start entrance animations
    func startAnimations() {
        withAnimation(AnimationConstants.smoothSpring) {
            elementsVisible = true
        }
    }
    
    /// Update price breakdown with service tier and commercial discount
    func updatePriceBreakdown(serviceTier: ServiceTier, isCommercial: Bool) {
        priceBreakdown = PriceBreakdown(serviceTier: serviceTier, isCommercial: isCommercial)
    }
    
    /// Submit booking to API
    @MainActor
    func submitBooking(
        address: Address,
        serviceIds: [String],
        photos: [Data],
        scheduledDateTime: String,
        customerName: String,
        customerEmail: String,
        customerPhone: String,
        notes: String?,
        completion: @escaping (Bool) -> Void
    ) async {
        // Light haptic on button press
        HapticManager.shared.lightTap()
        
        isSubmitting = true
        errorMessage = nil
        
        do {
            let customer = CustomerInfo(
                name: customerName,
                email: customerEmail,
                phone: customerPhone
            )
            
            let response = try await apiClient.createBooking(
                address: address,
                serviceIds: serviceIds,
                photos: photos,
                scheduledDateTime: scheduledDateTime,
                customer: customer,
                notes: notes
            )
            
            bookingResponse = response
            isSubmitting = false
            
            // Success haptic + celebration animation
            HapticManager.shared.success()
            
            withAnimation(AnimationConstants.bouncySpring) {
                celebrationScale = 1.1
            }
            
            // Reset scale after animation
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                withAnimation(AnimationConstants.bouncySpring) {
                    self.celebrationScale = 1.0
                }
            }
            
            showSuccess = true
            completion(true)
            
        } catch {
            isSubmitting = false
            errorMessage = error.localizedDescription
            HapticManager.shared.error()
            completion(false)
            print("Error submitting booking: \(error)")
        }
    }
    
    /// Submit booking with animation and haptics (legacy method for backward compatibility)
    func submitBooking(completion: @escaping () -> Void) {
        // Light haptic on button press
        HapticManager.shared.lightTap()
        
        isSubmitting = true
        
        // Simulate API call
        DispatchQueue.main.asyncAfter(deadline: .now() + 2) { [weak self] in
            guard let self = self else { return }
            
            self.isSubmitting = false
            
            // Success haptic + celebration animation
            HapticManager.shared.success()
            
            withAnimation(AnimationConstants.bouncySpring) {
                self.celebrationScale = 1.1
            }
            
            // Reset scale after animation
            DispatchQueue.main.asyncAfter(deadline: .now() + 0.3) {
                withAnimation(AnimationConstants.bouncySpring) {
                    self.celebrationScale = 1.0
                }
            }
            
            self.showSuccess = true
            completion()
        }
    }
    
    /// Format price for display
    func formatPrice(_ price: Double) -> String {
        String(format: "%.2f", price)
    }
    
    /// Get booking summary for a service ID
    func getServiceName(by id: String) -> String? {
        Service.all.first(where: { $0.id == id })?.name
    }
}
