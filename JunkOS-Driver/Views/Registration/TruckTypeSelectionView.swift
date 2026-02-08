//
//  TruckTypeSelectionView.swift
//  JunkOS Driver
//
//  Grid of truck types for contractor registration.
//

import SwiftUI

struct TruckTypeSelectionView: View {
    @Binding var selectedType: TruckType?

    var body: some View {
        ScrollView {
            VStack(spacing: DriverSpacing.sm) {
                ForEach(TruckType.allCases) { type in
                    TruckTypeCard(
                        type: type,
                        isSelected: selectedType == type
                    ) {
                        withAnimation(AnimationConstants.snappySpring) {
                            selectedType = type
                        }
                        HapticManager.shared.mediumTap()
                    }
                }
            }
            .padding(.horizontal, DriverSpacing.xl)
        }
    }
}

private struct TruckTypeCard: View {
    let type: TruckType
    let isSelected: Bool
    let onTap: () -> Void

    var body: some View {
        Button(action: onTap) {
            HStack(spacing: DriverSpacing.md) {
                Image(systemName: "truck.box.fill")
                    .font(.system(size: 28))
                    .foregroundStyle(isSelected ? Color.driverPrimary : Color.driverTextSecondary)
                    .frame(width: 48, height: 48)
                    .background(
                        Circle()
                            .fill(isSelected ? Color.driverPrimary.opacity(0.1) : Color.driverDivider)
                    )

                VStack(alignment: .leading, spacing: DriverSpacing.xxxs) {
                    Text(type.displayName)
                        .font(DriverTypography.headline)
                        .foregroundStyle(Color.driverText)

                    Text(type.capacityLabel)
                        .font(DriverTypography.footnote)
                        .foregroundStyle(Color.driverTextSecondary)
                }

                Spacer()

                Image(systemName: isSelected ? "checkmark.circle.fill" : "circle")
                    .font(.system(size: 24))
                    .foregroundStyle(isSelected ? Color.driverPrimary : Color.driverBorder)
            }
            .padding(DriverSpacing.md)
            .background(Color.driverSurface)
            .clipShape(RoundedRectangle(cornerRadius: DriverRadius.lg))
            .overlay(
                RoundedRectangle(cornerRadius: DriverRadius.lg)
                    .stroke(isSelected ? Color.driverPrimary : Color.driverBorder, lineWidth: isSelected ? 2 : 1)
            )
        }
        .buttonStyle(.plain)
    }
}
