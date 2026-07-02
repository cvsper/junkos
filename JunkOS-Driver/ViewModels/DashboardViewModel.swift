//
//  DashboardViewModel.swift
//  Umuve Pro
//
//  Home screen logic: online toggle, today stats, active job.
//

import Foundation

@Observable
final class DashboardViewModel {
    var todayEarnings: Double = 0
    var todayJobs: Int = 0
    var rating: Double = 0
    var isLoading = false

    private let api = DriverAPIClient.shared

    func loadStats(from profile: ContractorProfile?) {
        guard let profile else { return }
        rating = profile.avgRating
    }

    /// Wire the "Today" card from real earnings history (summary.today +
    /// entries dated today) instead of lifetime profile numbers.
    func loadTodayStats() async {
        isLoading = true
        defer { isLoading = false }
        do {
            let response = try await api.getEarningsHistory()
            todayEarnings = response.summary.today
            todayJobs = response.todayJobCount
        } catch {
            // Keep last-known values — a transient failure shouldn't zero the card.
        }
    }
}
