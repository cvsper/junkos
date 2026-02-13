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
        todayJobs = profile.totalJobs
    }
}
