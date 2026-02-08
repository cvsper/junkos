//
//  ConnectionStatusBanner.swift
//  JunkOS Driver
//
//  Banner showing socket connection state.
//

import SwiftUI

struct ConnectionStatusBanner: View {
    let isConnected: Bool

    var body: some View {
        if !isConnected {
            HStack(spacing: DriverSpacing.xs) {
                Image(systemName: "wifi.slash")
                    .font(.system(size: 12, weight: .semibold))

                Text("Reconnecting...")
                    .font(DriverTypography.caption)
            }
            .foregroundStyle(.white)
            .padding(.vertical, DriverSpacing.xxs)
            .padding(.horizontal, DriverSpacing.sm)
            .frame(maxWidth: .infinity)
            .background(Color.driverWarning)
            .transition(.move(edge: .top).combined(with: .opacity))
        }
    }
}
