//
//  QuickStatsCard.swift
//  Umuve Pro
//
//  Today's earnings, jobs count, and rating in a compact card.
//

import SwiftUI

struct QuickStatsCard: View {
    let todayEarnings: Double
    let todayJobs: Int
    let rating: Double

    var body: some View {
        HStack(spacing: 0) {
            StatItem(
                value: String(format: "$%.0f", todayEarnings),
                label: "Today",
                icon: "dollarsign.circle.fill",
                color: .driverPrimary
            )

            Divider()
                .frame(height: 40)

            StatItem(
                value: "\(todayJobs)",
                label: "Jobs",
                icon: "briefcase.fill",
                color: .driverInfo
            )

            Divider()
                .frame(height: 40)

            StatItem(
                value: rating > 0 ? String(format: "%.1f", rating) : "—",
                label: "Rating",
                icon: "star.fill",
                color: .statusPending
            )
        }
        .driverCard()
    }
}

private struct StatItem: View {
    let value: String
    let label: String
    let icon: String
    let color: Color

    var body: some View {
        VStack(spacing: DriverSpacing.xxs) {
            Image(systemName: icon)
                .font(.system(size: 16))
                .foregroundStyle(color)

            Text(value)
                .font(DriverTypography.title3)
                .foregroundStyle(Color.driverText)

            Text(label)
                .font(DriverTypography.caption2)
                .foregroundStyle(Color.driverTextSecondary)
        }
        .frame(maxWidth: .infinity)
    }
}
