//
//  ActiveJobMapOverlay.swift
//  Umuve Pro
//
//  Bottom sheet for accepted job: address, ETA, status actions, navigate button.
//

import SwiftUI

struct ActiveJobMapOverlay: View {
    let job: DriverJob
    let eta: String?
    let isUpdating: Bool
    let onNavigate: () -> Void
    let onStatusUpdate: () async -> Void

    @State private var expanded = false

    var body: some View {
        VStack(spacing: 0) {
            // Drag handle
            Capsule()
                .fill(Color.driverBorder)
                .frame(width: 36, height: 5)
                .padding(.top, DriverSpacing.xs)
                .padding(.bottom, DriverSpacing.sm)

            // Compact view (always shown)
            VStack(spacing: DriverSpacing.md) {
                // Address + ETA row
                HStack {
                    VStack(alignment: .leading, spacing: DriverSpacing.xxxs) {
                        Text(job.shortAddress)
                            .font(DriverTypography.headline)
                            .foregroundStyle(Color.driverText)

                        HStack(spacing: DriverSpacing.xs) {
                            // Status badge
                            Text(job.jobStatus.displayName)
                                .font(DriverTypography.caption)
                                .foregroundStyle(.white)
                                .padding(.horizontal, DriverSpacing.xs)
                                .padding(.vertical, DriverSpacing.xxxs)
                                .background(Capsule().fill(job.jobStatus.color))

                            if let eta {
                                Text(eta)
                                    .font(DriverTypography.caption)
                                    .foregroundStyle(Color.driverTextSecondary)
                            }
                        }
                    }

                    Spacer()

                    Text(job.formattedPrice)
                        .font(DriverTypography.price)
                        .foregroundStyle(Color.driverPrimary)
                }

                // Status stepper
                JobStatusStepper(currentStatus: job.jobStatus)

                // Action buttons
                HStack(spacing: DriverSpacing.sm) {
                    // Navigate button
                    Button(action: onNavigate) {
                        Label("Navigate", systemImage: "location.fill")
                            .font(DriverTypography.headline)
                            .foregroundStyle(Color.driverPrimary)
                            .frame(maxWidth: .infinity)
                            .padding(.vertical, 14)
                            .background(
                                RoundedRectangle(cornerRadius: DriverRadius.md)
                                    .stroke(Color.driverPrimary, lineWidth: 1.5)
                            )
                    }

                    // Status action button
                    Button {
                        Task { await onStatusUpdate() }
                    } label: {
                        if isUpdating {
                            ProgressView()
                                .tint(.white)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                        } else {
                            Text(nextStatusLabel)
                                .font(DriverTypography.headline)
                                .foregroundStyle(.white)
                                .frame(maxWidth: .infinity)
                                .padding(.vertical, 14)
                        }
                    }
                    .background(
                        RoundedRectangle(cornerRadius: DriverRadius.md)
                            .fill(Color.driverPrimary)
                    )
                    .disabled(isUpdating)
                }

                // Expanded detail
                if expanded {
                    VStack(alignment: .leading, spacing: DriverSpacing.sm) {
                        Divider()

                        // Full address
                        Label(job.address, systemImage: "mappin")
                            .font(DriverTypography.footnote)
                            .foregroundStyle(Color.driverTextSecondary)

                        // Items
                        if let items = job.items, !items.isEmpty {
                            Label(items.joined(separator: ", "), systemImage: "cube.box")
                                .font(DriverTypography.footnote)
                                .foregroundStyle(Color.driverTextSecondary)
                        }

                        // Notes
                        if let notes = job.notes, !notes.isEmpty {
                            Label(notes, systemImage: "note.text")
                                .font(DriverTypography.footnote)
                                .foregroundStyle(Color.driverTextSecondary)
                        }
                    }
                    .transition(.opacity.combined(with: .move(edge: .top)))
                }
            }
            .padding(.horizontal, DriverSpacing.lg)
            .padding(.bottom, DriverSpacing.lg)
        }
        .background(Color.driverSurface)
        .clipShape(RoundedRectangle(cornerRadius: DriverRadius.xl))
        .shadow(color: .black.opacity(0.12), radius: 16, y: -4)
        .padding(.horizontal, DriverSpacing.xs)
        .onTapGesture {
            withAnimation(.spring(response: 0.3)) {
                expanded.toggle()
            }
        }
    }

    private var nextStatusLabel: String {
        switch job.jobStatus {
        case .accepted: return "Mark En Route"
        case .enRoute: return "Mark Arrived"
        case .arrived: return "Start Job"
        case .started: return "Complete Job"
        default: return "Update Status"
        }
    }
}

// MARK: - Compact Status Stepper

private struct JobStatusStepper: View {
    let currentStatus: JobStatus

    private let steps: [JobStatus] = JobStatus.lifecycleSteps

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(steps.enumerated()), id: \.element) { index, step in
                // Dot
                Circle()
                    .fill(step.stepIndex <= currentStatus.stepIndex ? Color.driverPrimary : Color.driverBorder)
                    .frame(width: 10, height: 10)

                // Connecting line (not after last)
                if index < steps.count - 1 {
                    Rectangle()
                        .fill(step.stepIndex < currentStatus.stepIndex ? Color.driverPrimary : Color.driverBorder)
                        .frame(height: 2)
                }
            }
        }
        .padding(.vertical, DriverSpacing.xxs)
    }
}
