//
//  JobStatusStepperView.swift
//  JunkOS Driver
//
//  Visual 5-step progress bar for job lifecycle.
//

import SwiftUI

struct JobStatusStepperView: View {
    let currentStatus: JobStatus

    private let steps = JobStatus.lifecycleSteps

    var body: some View {
        HStack(spacing: 0) {
            ForEach(Array(steps.enumerated()), id: \.element) { index, step in
                // Step circle
                VStack(spacing: DriverSpacing.xxs) {
                    ZStack {
                        Circle()
                            .fill(stepColor(for: step))
                            .frame(width: 28, height: 28)

                        if isCompleted(step) {
                            Image(systemName: "checkmark")
                                .font(.system(size: 12, weight: .bold))
                                .foregroundStyle(.white)
                        } else if isCurrent(step) {
                            Circle()
                                .fill(.white)
                                .frame(width: 10, height: 10)
                        }
                    }

                    Text(step.displayName)
                        .font(.system(size: 9, weight: isCurrent(step) ? .bold : .medium))
                        .foregroundStyle(isCurrent(step) ? Color.driverPrimary : Color.driverTextTertiary)
                        .lineLimit(1)
                }

                // Connector line
                if index < steps.count - 1 {
                    Rectangle()
                        .fill(isCompleted(step) ? Color.driverPrimary : Color.driverBorder)
                        .frame(height: 2)
                        .frame(maxWidth: .infinity)
                        .padding(.bottom, 18) // Align with circle center
                }
            }
        }
    }

    private func isCompleted(_ step: JobStatus) -> Bool {
        step.stepIndex < currentStatus.stepIndex
    }

    private func isCurrent(_ step: JobStatus) -> Bool {
        step == currentStatus
    }

    private func stepColor(for step: JobStatus) -> Color {
        if isCompleted(step) { return .driverPrimary }
        if isCurrent(step) { return .driverPrimary }
        return .driverBorder
    }
}
