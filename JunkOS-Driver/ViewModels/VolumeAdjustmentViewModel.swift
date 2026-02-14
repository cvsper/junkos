//
//  VolumeAdjustmentViewModel.swift
//  Umuve Pro
//
//  Handles volume adjustment proposal logic and Socket.IO response listening.
//

import Foundation
import Combine

@Observable
final class VolumeAdjustmentViewModel {
    var volumeInput: String = ""
    var isSubmitting = false
    var isWaitingForApproval = false
    var wasApproved: Bool? = nil  // nil = pending, true = approved, false = declined
    var autoApproved = false  // true when price decreased and was auto-approved
    var newPrice: Double? = nil
    var originalPrice: Double? = nil
    var errorMessage: String? = nil
    var tripFee: Double? = nil  // set on decline

    private var cancellables = Set<AnyCancellable>()
    private let api = DriverAPIClient.shared

    init() {
        // Subscribe to volume:approved Socket.IO event
        NotificationCenter.default.publisher(for: NSNotification.Name("socket:volume:approved"))
            .receive(on: RunLoop.main)
            .sink { [weak self] _ in
                self?.wasApproved = true
                self?.isWaitingForApproval = false
                HapticManager.shared.success()
            }
            .store(in: &cancellables)

        // Subscribe to volume:declined Socket.IO event
        NotificationCenter.default.publisher(for: NSNotification.Name("socket:volume:declined"))
            .receive(on: RunLoop.main)
            .sink { [weak self] notification in
                self?.wasApproved = false
                self?.isWaitingForApproval = false
                self?.tripFee = (notification.userInfo?["trip_fee"] as? NSNumber)?.doubleValue ?? 50.0
                HapticManager.shared.error()
            }
            .store(in: &cancellables)
    }

    var parsedVolume: Double? {
        Double(volumeInput)
    }

    var isValid: Bool {
        guard let volume = parsedVolume else { return false }
        return volume > 0
    }

    func proposeAdjustment(jobId: String) async {
        guard isValid else { return }

        isSubmitting = true
        errorMessage = nil

        do {
            let response = try await api.proposeVolumeAdjustment(jobId: jobId, actualVolume: parsedVolume!)

            newPrice = response.newPrice
            originalPrice = response.originalPrice

            if response.autoApproved == true {
                // Price decreased - auto-approved
                autoApproved = true
                wasApproved = true
                HapticManager.shared.success()
            } else {
                // Price increased - waiting for customer approval
                isWaitingForApproval = true
            }
        } catch {
            errorMessage = error.localizedDescription
            HapticManager.shared.error()
        }

        isSubmitting = false
    }
}
