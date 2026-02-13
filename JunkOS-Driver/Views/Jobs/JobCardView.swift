//
//  JobCardView.swift
//  Umuve Pro
//
//  Job card showing address, price, distance, and scheduled time.
//

import SwiftUI

struct JobCardView: View {
    let job: DriverJob

    var body: some View {
        VStack(alignment: .leading, spacing: DriverSpacing.sm) {
            // Top row: address + price
            HStack(alignment: .top) {
                VStack(alignment: .leading, spacing: DriverSpacing.xxxs) {
                    Text(job.shortAddress)
                        .font(DriverTypography.headline)
                        .foregroundStyle(Color.driverText)
                        .lineLimit(1)

                    Text(job.address)
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverTextSecondary)
                        .lineLimit(1)
                }

                Spacer()

                PriceBadge(text: job.formattedPrice)
            }

            // Badges row
            HStack(spacing: DriverSpacing.xs) {
                DistanceBadge(text: job.formattedDistance)
                StatusBadge(status: job.jobStatus)

                Spacer()

                if let date = job.scheduledDate {
                    Text(date, style: .relative)
                        .font(DriverTypography.caption2)
                        .foregroundStyle(Color.driverTextTertiary)
                }
            }

            // Items preview
            if let items = job.items, !items.isEmpty {
                Text(items.prefix(3).joined(separator: " · "))
                    .font(DriverTypography.caption)
                    .foregroundStyle(Color.driverTextSecondary)
                    .lineLimit(1)
            }
        }
        .driverCard()
    }
}
