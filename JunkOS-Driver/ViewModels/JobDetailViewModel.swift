//
//  JobDetailViewModel.swift
//  Umuve Pro
//
//  Single job detail and accept logic.
//

import Foundation

@Observable
final class JobDetailViewModel {
    var job: DriverJob?
    var isAccepting = false
    var errorMessage: String?
    var didAccept = false

    private let api = DriverAPIClient.shared

    func acceptJob(jobId: String) async {
        isAccepting = true
        errorMessage = nil
        do {
            let response = try await api.acceptJob(jobId: jobId)
            job = response.job
            didAccept = true
            HapticManager.shared.success()
        } catch {
            errorMessage = error.localizedDescription
            HapticManager.shared.error()
        }
        isAccepting = false
    }
}
