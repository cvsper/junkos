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
    //
    // `stepCount` is how many in-wizard pages the user navigates through:
    // Address → Photos → Items → Schedule → Estimate. Five real steps that
    // BookingWizardView's stepContent switch routes to.
    //
    // `displayedStepCount` is what the progress indicator renders. The web
    // shows six dots because Payment is its own page; on iOS the Stripe
    // Payment Sheet appears as a modal sheet after Estimate, so it's still
    // a perceived step from the user's POV but not a wizard page. We render
    // six dots to match the web's progress treatment.
    let stepCount: Int = 5
    let displayedStepCount: Int = 6

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
    /// flow's progress bar verbatim: Address → Photos → Items → Schedule →
    /// Estimate → Payment.
    /// Step 5 ("Payment") is rendered for the progress indicator only —
    /// the user reaches that surface via the Stripe Payment Sheet modal
    /// triggered from step 4's "Pay" button, not via the wizard's
    /// stepContent router.
    func stepTitle(for index: Int) -> String {
        switch index {
        case 0: return "Address"
        case 1: return "Photos"
        case 2: return "Items"
        case 3: return "Schedule"
        case 4: return "Estimate"
        case 5: return "Payment"
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
