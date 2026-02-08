//
//  StatusBadge.swift
//  JunkOS Driver
//
//  Color-coded job status pill.
//

import SwiftUI

struct StatusBadge: View {
    let status: JobStatus

    var body: some View {
        Text(status.displayName)
            .font(DriverTypography.caption)
            .foregroundStyle(status.color)
            .padding(.horizontal, DriverSpacing.xs)
            .padding(.vertical, DriverSpacing.xxxs)
            .background(
                Capsule().fill(status.color.opacity(0.12))
            )
    }
}
