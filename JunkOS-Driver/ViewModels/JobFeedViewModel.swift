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
    var offers: [DriverOffer] = []   // broadcast offers (first-to-accept)
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
        // Broadcast offers load alongside available jobs; a failure here must
        // not blank the whole feed.
        do {
            offers = try await api.getOffers().offers
        } catch {
            // leave offers as-is
        }
        isLoading = false
    }

    /// Claim a broadcast offer. Returns true only on a successful claim.
    func acceptOffer(_ offer: DriverOffer) async -> Bool {
        do {
            let res = try await api.acceptOffer(token: offer.acceptToken)
            offers.removeAll { $0.id == offer.id }
            if !res.success {
                errorMessage = res.message ?? "That job was just taken."
                return false
            }
            return true
        } catch {
            // A lost race (HTTP 409) throws before decoding, so the card would
            // otherwise linger. Re-fetch from the server: a claimed offer
            // disappears; a transient error just keeps the current list.
            errorMessage = "Couldn't claim that job — it may have been taken."
            offers = (try? await api.getOffers().offers) ?? offers
            return false
        }
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
