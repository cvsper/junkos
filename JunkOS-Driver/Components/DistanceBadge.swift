//
//  DistanceBadge.swift
//  Umuve Pro
//
//  "2.3 mi" distance badge.
//

import SwiftUI

struct DistanceBadge: View {
    let text: String

    var body: some View {
        HStack(spacing: DriverSpacing.xxxs) {
            Image(systemName: "location.fill")
                .font(.system(size: 10))
            Text(text)
                .font(DriverTypography.caption)
        }
        .foregroundStyle(Color.driverInfo)
        .padding(.horizontal, DriverSpacing.xs)
        .padding(.vertical, DriverSpacing.xxxs)
        .background(
            Capsule().fill(Color.driverInfo.opacity(0.1))
        )
    }
}
