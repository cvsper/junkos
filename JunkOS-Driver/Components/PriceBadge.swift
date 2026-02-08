//
//  PriceBadge.swift
//  JunkOS Driver
//
//  "$145" price badge.
//

import SwiftUI

struct PriceBadge: View {
    let text: String

    var body: some View {
        Text(text)
            .font(DriverTypography.priceSmall)
            .foregroundStyle(Color.driverPrimary)
            .padding(.horizontal, DriverSpacing.sm)
            .padding(.vertical, DriverSpacing.xxs)
            .background(
                Capsule().fill(Color.driverPrimary.opacity(0.1))
            )
    }
}
