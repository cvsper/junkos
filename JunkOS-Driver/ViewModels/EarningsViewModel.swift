//
//  EarningsViewModel.swift
//  Umuve Pro
//
//  Earnings history and totals.
//

import Foundation

@Observable
final class EarningsViewModel {
    var summary = EarningsSummary.empty
    var entries: [EarningsEntry] = []
    var isLoading = false
    var selectedPeriod: EarningsPeriod = .today
    var errorMessage: String?

    enum EarningsPeriod: String, CaseIterable {
        case today = "Today"
        case week = "This Week"
        case month = "This Month"
        case all = "All Time"
    }

    var displayedAmount: String {
        switch selectedPeriod {
        case .today: return summary.formattedToday
        case .week: return summary.formattedWeek
        case .month: return summary.formattedMonth
        case .all: return summary.formattedAllTime
        }
    }

    var filteredEntries: [EarningsEntry] {
        let calendar = Calendar.current
        let now = Date()

        switch selectedPeriod {
        case .today:
            return entries.filter { calendar.isDateInToday($0.date) }
        case .week:
            guard let weekAgo = calendar.date(byAdding: .day, value: -7, to: now) else {
                return entries
            }
            return entries.filter { $0.date >= weekAgo }
        case .month:
            guard let monthAgo = calendar.date(byAdding: .day, value: -30, to: now) else {
                return entries
            }
            return entries.filter { $0.date >= monthAgo }
        case .all:
            return entries
        }
    }

    @MainActor
    func fetchEarnings() async {
        isLoading = true
        errorMessage = nil

        do {
            let response = try await DriverAPIClient.shared.getEarningsHistory()

            // Map summary
            summary = EarningsSummary(
                todayEarnings: response.summary.today,
                weekEarnings: response.summary.week,
                monthEarnings: response.summary.month,
                allTimeEarnings: response.summary.allTime,
                todayJobs: 0,  // Not provided by API yet
                weekJobs: 0    // Not provided by API yet
            )

            // Map entries
            let iso8601Formatter = ISO8601DateFormatter()
            entries = response.entries.compactMap { entry in
                // Parse date
                let date: Date
                if let dateString = entry.date, let parsedDate = iso8601Formatter.date(from: dateString) {
                    date = parsedDate
                } else {
                    date = Date()  // Fallback to now if parsing fails
                }

                // Parse payout status
                let payoutStatus = PayoutStatus(rawValue: entry.payoutStatus) ?? .pending

                return EarningsEntry(
                    id: entry.id,
                    jobId: entry.jobId,
                    address: entry.address,
                    amount: entry.amount,  // Already driver's 80% take from backend
                    date: date,
                    payoutStatus: payoutStatus
                )
            }

            isLoading = false
        } catch {
            errorMessage = error.localizedDescription
            isLoading = false
        }
    }
}
