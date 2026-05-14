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

    /// Get the title for a specific step. Order matches the web booking
    /// flow's progress bar: Address → Photos → Items → Schedule → Estimate.
    func stepTitle(for index: Int) -> String {
        switch index {
        case 0: return "Address"
        case 1: return "Photos"
        case 2: return "Items"
        case 3: return "Schedule"
        case 4: return "Estimate"
        default: return ""
        }
    }

    /// Check if a step is accessible (current, completed, or previous)
    func isStepAccessible(_ step: Int) -> Bool {
        step <= currentStep || completedSteps.contains(step)
    }

    // MARK: - Pricing

    /// Refresh pricing estimate based on the current items list.
    ///
    /// No-op when the user hasn't added any items yet — the backend would
    /// happily return the $89 minimum, but that would mis-set
    /// `estimatedPrice` on the Address/Photos screens and surface a phantom
    /// "Estimated Total" pill before the user has done anything.
    @MainActor
    func refreshPricing(bookingData: BookingData) async {
        guard bookingData.hasItems else { return }

        do {
            var scheduledDateString: String?
            if let date = bookingData.selectedDate, let timeSlot = bookingData.selectedTimeSlot {
                let dateFormatter = DateFormatter()
                dateFormatter.dateFormat = "yyyy-MM-dd"
                scheduledDateString = dateFormatter.string(from: date) + " " + timeSlot
            }

            let estimate = try await APIClient.shared.getPricingEstimate(
                items: bookingData.items,
                pickupLat: bookingData.pickupCoordinate?.latitude,
                pickupLng: bookingData.pickupCoordinate?.longitude,
                scheduledDate: scheduledDateString
            )

            bookingData.estimatedPrice = estimate.total
            bookingData.priceBreakdown = estimate
        } catch {
            print("[pricing] Error: \(error)")
            // Pricing updates are best-effort — the Estimate step has its
            // own fallback calc if the API is unreachable.
        }
    }
}
