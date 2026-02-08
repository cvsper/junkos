//
//  JobFeedViewModel.swift
//  JunkOS Driver
//
//  Available jobs list with pull-to-refresh.
//

import Foundation

@Observable
final class JobFeedViewModel {
    var jobs: [DriverJob] = []
    var isLoading = false
    var errorMessage: String?

    private let api = DriverAPIClient.shared

    func loadJobs() async {
        isLoading = true
        errorMessage = nil
        do {
            let response = try await api.getAvailableJobs()
            jobs = response.jobs
        } catch {
            errorMessage = error.localizedDescription
        }
        isLoading = false
    }

    func refresh() async {
        await loadJobs()
    }
}
