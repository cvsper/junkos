//
//  EarningsModels.swift
//  Umuve Pro
//
//  Earnings and payout-related data models.
//

import Foundation

struct EarningsSummary {
    let todayEarnings: Double
    let weekEarnings: Double
    let monthEarnings: Double
    let todayJobs: Int
    let weekJobs: Int

    var formattedToday: String { String(format: "$%.2f", todayEarnings) }
    var formattedWeek: String { String(format: "$%.2f", weekEarnings) }
    var formattedMonth: String { String(format: "$%.2f", monthEarnings) }

    static let empty = EarningsSummary(
        todayEarnings: 0,
        weekEarnings: 0,
        monthEarnings: 0,
        todayJobs: 0,
        weekJobs: 0
    )
}

struct EarningsEntry: Identifiable {
    let id: String
    let jobId: String
    let address: String
    let amount: Double
    let date: Date
    let status: String

    var formattedAmount: String { String(format: "$%.2f", amount) }

    var formattedDate: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}
