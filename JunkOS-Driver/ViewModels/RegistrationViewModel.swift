//
//  RegistrationViewModel.swift
//  JunkOS Driver
//
//  Multi-step contractor registration flow.
//

import Foundation
import UIKit

@Observable
final class RegistrationViewModel {
    // Step tracking (3 steps: truck → license → insurance)
    var currentStep = 0
    let totalSteps = 3

    // Step 1: Truck
    var selectedTruckType: TruckType?
    var truckCapacity: String = ""

    // Step 2: License
    var licenseImage: UIImage?

    // Step 3: Insurance
    var insuranceImage: UIImage?

    // State
    var isLoading = false
    var errorMessage: String?
    var isComplete = false

    var canProceed: Bool {
        switch currentStep {
        case 0: return selectedTruckType != nil
        case 1: return licenseImage != nil
        case 2: return insuranceImage != nil
        default: return false
        }
    }

    var stepTitle: String {
        switch currentStep {
        case 0: return "Your Truck"
        case 1: return "Driver's License"
        case 2: return "Insurance"
        default: return ""
        }
    }

    var stepSubtitle: String {
        switch currentStep {
        case 0: return "Select the type of vehicle you'll use for pickups"
        case 1: return "Take a photo of your valid driver's license"
        case 2: return "Upload proof of commercial insurance"
        default: return ""
        }
    }

    func nextStep() {
        guard currentStep < totalSteps - 1 else { return }
        currentStep += 1
        HapticManager.shared.mediumTap()
    }

    func previousStep() {
        guard currentStep > 0 else { return }
        currentStep -= 1
        HapticManager.shared.lightTap()
    }

    func submit() async {
        guard let truckType = selectedTruckType else { return }
        isLoading = true
        errorMessage = nil

        do {
            // Upload images if present (non-fatal if upload fails)
            var licenseUrl: String? = nil
            var insuranceUrl: String? = nil

            if let img = licenseImage {
                licenseUrl = (try? await ImageUploadService.shared.uploadPhotos([img]))?.first
            }
            if let img = insuranceImage {
                insuranceUrl = (try? await ImageUploadService.shared.uploadPhotos([img]))?.first
            }

            let capacity = Double(truckCapacity)
            let request = RegistrationRequest(
                truckType: truckType.rawValue,
                truckCapacity: capacity,
                licenseUrl: licenseUrl,
                insuranceUrl: insuranceUrl,
                truckPhotos: nil
            )

            _ = try await DriverAPIClient.shared.registerContractor(request)
            isComplete = true
            HapticManager.shared.success()
        } catch {
            errorMessage = error.localizedDescription
            HapticManager.shared.error()
        }
        isLoading = false
    }
}
