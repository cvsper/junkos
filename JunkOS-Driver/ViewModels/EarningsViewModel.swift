//
//  EarningsViewModel.swift
//  JunkOS Driver
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

    enum EarningsPeriod: String, CaseIterable {
        case today = "Today"
        case week = "This Week"
        case month = "This Month"
    }

    var displayedAmount: String {
        switch selectedPeriod {
        case .today: return summary.formattedToday
        case .week: return summary.formattedWeek
        case .month: return summary.formattedMonth
        }
    }
}
