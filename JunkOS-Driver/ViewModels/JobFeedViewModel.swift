//
//  JobFeedViewModel.swift
//  Umuve Pro
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

    func removeJob(id: String) {
        jobs.removeAll { $0.id == id }
    }

    func addJobIfNew(_ job: DriverJob) {
        guard !jobs.contains(where: { $0.id == job.id }) else { return }
        jobs.insert(job, at: 0)
    }
}
