//
//  JobAlertOverlay.swift
//  Umuve Pro
//
//  Accept/decline card that slides up when a new job arrives.
//  Shows countdown ring, address, price, distance.
//

import SwiftUI

struct JobAlertOverlay: View {
    let job: DriverJob
    let countdown: Int
    let onAccept: () -> Void
    let onDecline: () -> Void

    private let totalCountdown: Double = 30

    var body: some View {
        VStack(spacing: DriverSpacing.md) {
            // Header: "New Job Request"
            HStack {
                Image(systemName: "bell.badge.fill")
                    .font(.system(size: 16, weight: .semibold))
                    .foregroundStyle(Color.driverPrimary)

                Text("New Job Request")
                    .font(DriverTypography.headline)
                    .foregroundStyle(Color.driverText)

                Spacer()

                // Countdown ring
                ZStack {
                    Circle()
                        .stroke(Color.driverBorder, lineWidth: 3)
                        .frame(width: 40, height: 40)

                    Circle()
                        .trim(from: 0, to: Double(countdown) / totalCountdown)
                        .stroke(Color.driverPrimary, style: StrokeStyle(lineWidth: 3, lineCap: .round))
                        .frame(width: 40, height: 40)
                        .rotationEffect(.degrees(-90))
                        .animation(.linear(duration: 1), value: countdown)

                    Text("\(countdown)")
                        .font(.system(size: 14, weight: .bold, design: .rounded))
                        .foregroundStyle(Color.driverText)
                }
            }

            // Address
            HStack(spacing: DriverSpacing.sm) {
                Image(systemName: "mappin.circle.fill")
                    .font(.system(size: 24))
                    .foregroundStyle(Color.driverPrimary)

                VStack(alignment: .leading, spacing: DriverSpacing.xxxs) {
                    Text(job.shortAddress)
                        .font(DriverTypography.headline)
                        .foregroundStyle(Color.driverText)

                    Text(job.address)
                        .font(DriverTypography.caption)
                        .foregroundStyle(Color.driverTextSecondary)
                        .lineLimit(1)
                }

                Spacer()
            }

            // Badges: Price + Distance
            HStack(spacing: DriverSpacing.sm) {
                // Price badge
                HStack(spacing: DriverSpacing.xxs) {
                    Image(systemName: "dollarsign.circle.fill")
                        .foregroundStyle(Color.driverPrimary)
                    Text(job.formattedPrice)
                        .font(DriverTypography.price)
                        .foregroundStyle(Color.driverText)
                }
                .padding(.horizontal, DriverSpacing.md)
                .padding(.vertical, DriverSpacing.xs)
                .background(Color.driverSurfaceElevated)
                .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))

                // Distance badge
                HStack(spacing: DriverSpacing.xxs) {
                    Image(systemName: "location.fill")
                        .foregroundStyle(Color.driverInfo)
                    Text(job.formattedDistance)
                        .font(DriverTypography.headline)
                        .foregroundStyle(Color.driverText)
                }
                .padding(.horizontal, DriverSpacing.md)
                .padding(.vertical, DriverSpacing.xs)
                .background(Color.driverSurfaceElevated)
                .clipShape(RoundedRectangle(cornerRadius: DriverRadius.md))

                Spacer()
            }

            // Items preview
            if let items = job.items, !items.isEmpty {
                HStack(spacing: DriverSpacing.xxs) {
                    Image(systemName: "cube.box.fill")
                        .font(.system(size: 12))
                        .foregroundStyle(Color.driverTextSecondary)
                    Text(items.prefix(3).joined(separator: ", "))
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverTextSecondary)
                        .lineLimit(1)
                }
            }

            // Buttons
            VStack(spacing: DriverSpacing.xs) {
                Button(action: onAccept) {
                    Text("Accept Job")
                }
                .buttonStyle(DriverPrimaryButtonStyle())

                Button(action: onDecline) {
                    Text("Decline")
                        .font(DriverTypography.headline)
                        .foregroundStyle(Color.driverTextSecondary)
                        .frame(maxWidth: .infinity)
                        .padding(.vertical, DriverSpacing.sm)
                }
            }
        }
        .padding(DriverSpacing.lg)
        .background(Color.driverSurface)
        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.xl))
        .shadow(color: .black.opacity(0.15), radius: 20, y: -5)
        .padding(.horizontal, DriverSpacing.md)
        .transition(.move(edge: .bottom).combined(with: .opacity))
    }
}
