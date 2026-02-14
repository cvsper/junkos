//
//  EarningsModels.swift
//  Umuve Pro
//
//  Earnings and payout-related data models.
//

import Foundation

enum PayoutStatus: String {
    case pending = "pending"
    case processing = "processing"
    case paid = "paid"

    var displayName: String {
        switch self {
        case .pending: return "Pending"
        case .processing: return "Processing"
        case .paid: return "Paid"
        }
    }

    var color: String {  // Use string for Color lookup
        switch self {
        case .pending: return "driverWarning"
        case .processing: return "driverPrimary"
        case .paid: return "driverSuccess"
        }
    }
}

struct EarningsSummary {
    let todayEarnings: Double
    let weekEarnings: Double
    let monthEarnings: Double
    let allTimeEarnings: Double
    let todayJobs: Int
    let weekJobs: Int

    var formattedToday: String { String(format: "$%.2f", todayEarnings) }
    var formattedWeek: String { String(format: "$%.2f", weekEarnings) }
    var formattedMonth: String { String(format: "$%.2f", monthEarnings) }
    var formattedAllTime: String { String(format: "$%.2f", allTimeEarnings) }

    static let empty = EarningsSummary(
        todayEarnings: 0,
        weekEarnings: 0,
        monthEarnings: 0,
        allTimeEarnings: 0,
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
    let payoutStatus: PayoutStatus

    var formattedAmount: String { String(format: "$%.2f", amount) }

    var formattedDate: String {
        let formatter = DateFormatter()
        formatter.dateStyle = .medium
        formatter.timeStyle = .short
        return formatter.string(from: date)
    }
}
