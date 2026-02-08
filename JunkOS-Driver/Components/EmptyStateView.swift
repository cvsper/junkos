//
//  EmptyStateView.swift
//  JunkOS Driver
//
//  Generic empty state with icon, title, and message.
//

import SwiftUI

struct EmptyStateView: View {
    let icon: String
    let title: String
    let message: String

    var body: some View {
        VStack(spacing: DriverSpacing.md) {
            Image(systemName: icon)
                .font(.system(size: 48))
                .foregroundStyle(Color.driverTextTertiary)

            Text(title)
                .font(DriverTypography.headline)
                .foregroundStyle(Color.driverText)

            Text(message)
                .font(DriverTypography.footnote)
                .foregroundStyle(Color.driverTextSecondary)
                .multilineTextAlignment(.center)
                .padding(.horizontal, DriverSpacing.xxl)
        }
        .frame(maxWidth: .infinity, maxHeight: .infinity)
    }
}
