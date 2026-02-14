//
//  BookingWizardViewModel.swift
//  Umuve
//
//  ViewModel managing wizard step navigation and completion state
//

import Foundation

class BookingWizardViewModel: ObservableObject {
    // MARK: - Published Properties
    @Published var currentStep: Int = 0
    @Published var completedSteps: Set<Int> = []

    // MARK: - Constants
    let stepCount: Int = 5

    // MARK: - Step Navigation

    /// Navigate to a specific step (only if it's accessible)
    func goToStep(_ step: Int) {
        guard isStepAccessible(step) else { return }
        currentStep = step
    }

    /// Mark current step as complete and advance to next step
    func completeCurrentStep() {
        completedSteps.insert(currentStep)
        if currentStep < stepCount - 1 {
            currentStep += 1
        }
    }

    /// Go back to previous step
    func goBack() {
        if currentStep > 0 {
            currentStep -= 1
        }
    }

    // MARK: - Computed Properties

    var canGoBack: Bool {
        currentStep > 0
    }

    var isLastStep: Bool {
        currentStep == stepCount - 1
    }

    /// Get the title for a specific step
    func stepTitle(for index: Int) -> String {
        switch index {
        case 0: return "Service"
        case 1: return "Address"
        case 2: return "Photos"
        case 3: return "Schedule"
        case 4: return "Review"
        default: return ""
        }
    }

    /// Check if a step is accessible (current, completed, or previous)
    func isStepAccessible(_ step: Int) -> Bool {
        step <= currentStep || completedSteps.contains(step)
    }

    // MARK: - Pricing

    /// Refresh pricing estimate based on current booking data
    @MainActor
    func refreshPricing(bookingData: BookingData) async {
        // Only call API if we have at least service type
        guard let serviceType = bookingData.serviceType else { return }

        do {
            let serviceTypeString: String
            switch serviceType {
            case .junkRemoval:
                serviceTypeString = "Junk Removal"
            case .autoTransport:
                serviceTypeString = "Auto Transport"
            }

            // Prepare vehicle info for auto transport
            var vehicleInfo: [String: Any]?
            if serviceType == .autoTransport {
                vehicleInfo = [
                    "make": bookingData.vehicleMake,
                    "model": bookingData.vehicleModel,
                    "year": bookingData.vehicleYear,
                    "is_running": bookingData.isVehicleRunning,
                    "needs_enclosed_trailer": bookingData.needsEnclosedTrailer
                ]
            }

            // Format scheduled date if available
            var scheduledDateString: String?
            if let date = bookingData.selectedDate, let timeSlot = bookingData.selectedTimeSlot {
                let dateFormatter = DateFormatter()
                dateFormatter.dateFormat = "yyyy-MM-dd"
                scheduledDateString = dateFormatter.string(from: date) + " " + timeSlot
            }

            let estimate = try await APIClient.shared.getPricingEstimate(
                serviceType: serviceTypeString,
                volumeTier: serviceType == .junkRemoval ? bookingData.volumeTier.rawValue : nil,
                vehicleInfo: vehicleInfo,
                pickupLat: bookingData.pickupCoordinate?.latitude,
                pickupLng: bookingData.pickupCoordinate?.longitude,
                dropoffLat: bookingData.dropoffCoordinate?.latitude,
                dropoffLng: bookingData.dropoffCoordinate?.longitude,
                scheduledDate: scheduledDateString
            )

            bookingData.estimatedPrice = estimate.total
            bookingData.priceBreakdown = estimate
        } catch {
            print("[pricing] Error: \(error)")
            // Don't show error to user — pricing updates are best-effort
        }
    }
}
